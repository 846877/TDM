"""Moteur Docker de TDM (VM VirtualBox), exclusivité labs Docker / labs Windows, notice hyperviseur.

Faux ``docker`` et faux ``vagrant`` en shell, comme dans test_devops.py et test_windows_labs.py.
"""

import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app import config, hypervisor
from app.devops import engine, labs, vagrant
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import vagrant_agent  # noqa: E402

client = TestClient(app)

# Répond à `docker info` seulement si le fichier ok-<moteur> existe (local : Docker de la machine,
# vm : moteur de TDM joint par DOCKER_HOST=tcp://127.0.0.1:23750).
FAKE_DOCKER = """#!/bin/sh
h=local; case "$DOCKER_HOST" in *:23750) h=vm ;; ?*) h=autre ;; esac
echo "$h $*" >> "$FAKE_DOCKER/calls"
case "$1" in
  info) [ -f "$FAKE_DOCKER/ok-$h" ] && echo 27.5.1 && exit 0; exit 1 ;;
  ps) cat "$FAKE_DOCKER/ps" 2>/dev/null; exit 0 ;;
  inspect) if [ -f "$FAKE_DOCKER/run" ]; then echo true; else echo false; fi ;;
  run) touch "$FAKE_DOCKER/run"; echo id ;;
esac
exit 0
"""


@pytest.fixture
def docker(tmp_path, monkeypatch):
    """Faux client docker dans le PATH ; renvoie son dossier d'état (calls, ok-local, ok-vm, ps...)."""
    if sys.platform == "win32":
        pytest.skip("faux docker en shell")
    state = tmp_path / "docker"
    (state / "bin").mkdir(parents=True)
    fake = state / "bin" / "docker"
    fake.write_text(FAKE_DOCKER)
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{state / 'bin'}:/usr/bin:/bin")
    monkeypatch.setenv("FAKE_DOCKER", str(state))
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(engine, "_USER_DOCKER_HOST", None)
    monkeypatch.setattr(config, "DOCKER_MODE", "auto")
    monkeypatch.setattr(vagrant, "health", lambda: {"engine": True, "vagrant": True, "virtualbox": True})
    monkeypatch.setattr(vagrant, "status", lambda lab: ("stopped", ""))
    engine.reset_cache()
    yield state
    for entry in labs._pending.values():
        entry["cancel"] = True
        entry["thread"].join(5)
    labs._pending.clear()
    engine.reset_cache()
    os.environ.pop("DOCKER_HOST", None)  # posé par le moteur : ne doit pas fuir dans les autres tests


def _calls(state: Path) -> list[str]:
    path = state / "calls"
    return path.read_text().splitlines() if path.exists() else []


# --- Ports publiés par les labs ------------------------------------------------------------------

@pytest.mark.parametrize("spec, expected", [
    ("8080:80", [8080]), ("127.0.0.1:8081:80/tcp", [8081]), ("8000-8002:80-82", [8000, 8001, 8002]),
    ("80", []), (80, []), ({"target": 80, "published": 8443}, [8443]), ({"target": 80}, []),
])
def test_ports_de_l_hote(spec, expected):
    assert engine.host_ports(spec) == expected


def test_ports_des_labs_rediriges():
    ports = engine.lab_ports()
    # lab.yaml (gitlab : 8929 et 2224) et docker-compose.yml (haproxy : 8090, 8404 ; xrdp : 9489).
    assert {8929, 2224, 8090, 8404, 9489} <= set(ports)
    assert all(1024 <= p <= 65535 for p in ports)
    assert int(config.DOCKER_VM_HOST.rsplit(":", 1)[1]) not in ports


def test_labs_docker_sans_montage_de_l_hote():
    """Avec un moteur Docker distant (VM), un dossier de l'hôte monté serait vide : aucun lab n'en monte."""
    for lab in labs.load_labs():
        assert "volumes" not in lab, lab["id"]
        if "compose" in lab:
            data = yaml.safe_load((Path(lab["dir"]) / lab["compose"]).read_text(encoding="utf-8"))
            for name, service in (data.get("services") or {}).items():
                for volume in (service or {}).get("volumes") or []:
                    source = volume.get("source", "") if isinstance(volume, dict) else str(volume).split(":")[0]
                    assert not source.startswith((".", "/", "~", "$")) and ":\\" not in str(volume), \
                        (lab["id"], name, volume)


# --- Choix du moteur -----------------------------------------------------------------------------

def test_auto_garde_docker_desktop_quand_il_repond(docker):
    (docker / "ok-local").touch()
    assert engine.kind() == "desktop"
    assert "DOCKER_HOST" not in os.environ
    assert engine.state()["status"] == "ready"


def test_auto_choisit_la_vm_moteur_sans_docker_desktop(docker):
    assert engine.kind() == "vm"
    assert os.environ["DOCKER_HOST"] == config.DOCKER_VM_HOST == "tcp://127.0.0.1:23750"
    assert engine.state() == {"engine": "vm", "status": "stopped", "log": ""}
    # Le bac à sable Python ne bascule jamais sur la VM moteur.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "SANDBOX_MODE", "auto")
        mp.setattr(config, "_docker_cache", (time.monotonic(), True))
        assert config.docker_is_tdm_vm() and not config.use_docker_sandbox()


def test_vm_allumee_mais_docker_pas_pret(docker, monkeypatch):
    monkeypatch.setattr(vagrant, "status", lambda lab: ("running", ""))
    current = engine.state()
    assert current["status"] == "starting" and "Docker" in current["log"]
    (docker / "ok-vm").touch()
    engine._cache.pop("vm")
    assert engine.state()["status"] == "ready"


def test_mode_desktop_et_aucun_moteur(docker, monkeypatch):
    monkeypatch.setattr(config, "DOCKER_MODE", "desktop")
    assert engine.kind() == "desktop" and engine.state()["status"] == "unavailable"
    monkeypatch.setattr(config, "DOCKER_MODE", "auto")

    def no_agent():
        raise vagrant.AgentError("absent")
    monkeypatch.setattr(vagrant, "health", no_agent)
    engine.reset_cache()
    assert engine.kind() == "none"
    lab = {"id": "essai", "image": "alpine", "exercises": []}
    assert labs.status_with_log(lab) == ("unavailable", "")
    with pytest.raises(labs.LabError, match="VirtualBox"):
        labs.launch(lab)


def test_agent_sans_virtualbox(docker, monkeypatch):
    monkeypatch.setattr(vagrant, "health", lambda: {"engine": True, "vagrant": True, "virtualbox": False})
    assert engine.kind() == "none"


# --- Démarrage à la demande ----------------------------------------------------------------------

def test_lab_docker_demarre_le_moteur_a_la_demande(docker, monkeypatch, tmp_path):
    started = []

    def start_engine(lab, ports):
        started.append(ports)
        (docker / "ok-vm").touch()  # la VM démarre et Docker y répond
        return "starting"

    paused = []
    monkeypatch.setattr(vagrant, "start_engine", start_engine)
    monkeypatch.setattr(vagrant, "exclusive", lambda name: paused.append(name) or ["tdm:win-gpo-base"])
    lab = {"id": "essai", "image": "alpine", "ports": ["8088:80"], "exercises": [], "dir": str(tmp_path)}

    result = labs.launch(lab)
    assert result["status"] == "starting"
    assert paused == ["tdm:moteur-docker"]  # les VM Windows passent en pause, pas le moteur
    assert result["notices"] and "a été mis en pause pour libérer la mémoire" in result["notices"][0]
    assert started and 8929 in started[0]
    for _ in range(100):
        if labs.status(lab) == "running":
            break
        time.sleep(0.1)
    assert labs.status(lab) == "running"
    run = next(c for c in _calls(docker) if " run " in f" {c} ")
    assert run.startswith("vm run -d --name tdm-lab-essai") and "-p 8088:80" in run


def test_lab_docker_arrete_sans_demarrer_le_moteur(docker, monkeypatch):
    monkeypatch.setattr(vagrant, "start_engine", lambda lab, ports: pytest.fail("moteur démarré"))
    lab = {"id": "essai", "image": "alpine", "exercises": []}
    assert labs.status(lab) == "stopped"  # moteur arrêté : le lab est simplement arrêté (démarrable)
    assert labs.stop(lab) == "stopped"
    assert labs.stop_docker_labs() == []


# --- Une seule famille de labs à la fois ---------------------------------------------------------

def test_lab_windows_met_en_pause_le_moteur_et_les_autres_vm(docker, monkeypatch):
    (docker / "ok-local").touch()
    (docker / "ps").write_text("tdm-lab-docker-bases\t\ntdm-lab-haproxy-lb-1\ttdm-lab-haproxy\n"
                               "tdm-lab-haproxy-web-1\ttdm-lab-haproxy\n")
    windows_lab = next(lab for lab in labs.load_labs() if lab.get("os") == "windows")
    other = next(lab for lab in labs.load_labs() if lab.get("os") == "windows" and lab["id"] != windows_lab["id"])
    asked = []
    monkeypatch.setattr(vagrant, "exclusive", lambda name: asked.append(name) or ["tdm:moteur-docker", other["vagrant"]])
    monkeypatch.setattr(vagrant, "start", lambda lab: "starting")

    result = labs.launch(windows_lab)
    assert result["status"] == "starting" and asked == [windows_lab["vagrant"]]
    assert "local stop tdm-lab-docker-bases tdm-lab-haproxy-lb-1 tdm-lab-haproxy-web-1" in _calls(docker)
    notices = "\n".join(result["notices"])
    assert "Le lab Docker « " in notices and "a été arrêté pour libérer la mémoire" in notices
    assert f"Le lab Windows « {other['title']} » a été mis en pause pour libérer la mémoire." in notices
    assert "Le moteur Docker a été mis en pause" in notices

    # Les labs Vagrant de l'utilisateur ne déclenchent rien.
    monkeypatch.setattr(vagrant, "exclusive", lambda name: pytest.fail("pause inattendue"))
    assert labs.launch({"id": "k8s", "vagrant": "k8s/ubuntu", "exercises": []})["notices"] == []


def test_api_renvoie_les_mises_en_pause(docker, monkeypatch):
    monkeypatch.setattr(vagrant, "exclusive", lambda name: ["tdm:moteur-docker"])
    monkeypatch.setattr(vagrant, "start", lambda lab: "starting")
    windows_lab = next(lab for lab in labs.load_labs() if lab.get("os") == "windows")
    data = client.post(f"/api/devops/labs/{windows_lab['id']}/start").json()
    assert data["status"] == "starting" and "moteur Docker" in data["notices"][0]
    docker_lab = client.get("/api/devops/labs/docker-bases").json()
    assert docker_lab["engine"] == "vm" and docker_lab["status"] == "stopped"


# --- Agent : moteur embarqué, exclusivité, pause à la fermeture ----------------------------------

FAKE_VAGRANT = """#!/bin/sh
echo "$(basename "$PWD") $*" >> "$CALLS"
case "$1" in
  status) if [ -f up ]; then s=running; else s=saved; fi; echo "1,default,state,$s" ;;
  up|reload) mkdir -p .vagrant/machines/default/virtualbox; echo "id-$(basename "$PWD")" \\
       > .vagrant/machines/default/virtualbox/id; touch up ;;
  suspend|halt) rm -f up ;;
esac
exit 0
"""


@pytest.fixture
def agent(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("faux vagrant en shell")
    bundled = tmp_path / "bundled"
    for name in ("win-a", "win-b"):
        (bundled / name).mkdir(parents=True)
        (bundled / name / "Vagrantfile").write_text(f"# {name}")
    engine_dir = tmp_path / "moteur"
    engine_dir.mkdir()
    (engine_dir / "Vagrantfile").write_text("# moteur")
    fake = tmp_path / "vagrant"
    fake.write_text(FAKE_VAGRANT)
    fake.chmod(0o755)
    monkeypatch.setenv("CALLS", str(tmp_path / "calls"))
    ag = vagrant_agent.Agent(None, str(fake), bundled=bundled, work_dir=tmp_path / "work",
                             engine_dir=engine_dir, vboxmanage=None)
    ag.calls = tmp_path / "calls"
    return ag


def _run(ag, lab, path):
    action, steps = ag.lab_actions(lab)[path]
    ag.run_job(lab, action, *steps)
    ag.jobs[lab]._thread.join(10)
    assert ag.jobs[lab].returncode == 0


def _take_calls(ag) -> list[str]:
    calls = ag.calls.read_text().splitlines() if ag.calls.exists() else []
    ag.calls.unlink(missing_ok=True)
    return [c for c in calls if " status " not in f" {c} "]


def test_agent_moteur_ports_et_rechargement(agent):
    agent.engine_ports = [8080, 8929]
    _run(agent, vagrant_agent.ENGINE, "/up")
    work = agent.work_dir / "moteur-docker"
    assert (work / "ports.txt").read_text() == "8080\n8929" and (work / "Vagrantfile").exists()
    assert _take_calls(agent) == ["moteur-docker up"]
    _run(agent, vagrant_agent.ENGINE, "/halt")
    assert _take_calls(agent) == ["moteur-docker suspend"]  # « arrêter » le moteur le met en pause
    _run(agent, vagrant_agent.ENGINE, "/up")
    assert _take_calls(agent) == ["moteur-docker up"]  # ports inchangés : simple reprise
    agent.engine_ports = [8080, 8929, 9000]  # nouveau lab : redirections à appliquer
    _run(agent, vagrant_agent.ENGINE, "/up")
    # Le rechargement passe AVANT `up` : la VM ne sert dockerd qu'une fois, déjà bien configurée
    # (sinon le backend lance le compose dès le premier `up`, puis le reload coupe l'API Docker).
    assert _take_calls(agent) == ["moteur-docker reload", "moteur-docker up"]
    with pytest.raises(ValueError):
        vagrant_agent.parse_ports("8080,22")


def test_agent_moteur_demarrage_incomplet_repart_propre(agent, tmp_path):
    """Un premier `vagrant up` du moteur qui échoue (délai de démarrage dépassé) alors que la VM n'a jamais
    été prête : elle a pu être créée sans Docker. L'agent la détruit et repart proprement une seule fois."""
    timeout_vagrant = """#!/bin/sh
echo "$(basename "$PWD") $*" >> "$CALLS"
case "$1" in
  status) if [ -f up ]; then s=running; else s=saved; fi; echo "1,default,state,$s" ;;
  up) mkdir -p .vagrant/machines/default/virtualbox; echo id > .vagrant/machines/default/virtualbox/id
      if [ -f clean ]; then touch up; exit 0; fi; exit 1 ;;
  destroy) rm -f up; touch clean ;;
esac
exit 0
"""
    fake = tmp_path / "vagrant-timeout"
    fake.write_text(timeout_vagrant)
    fake.chmod(0o755)
    agent.vagrant = str(fake)
    agent.engine_ports = []
    _run(agent, vagrant_agent.ENGINE, "/up")  # _run exige un code de retour final nul : le rattrapage a marché
    work = agent.work_dir / "moteur-docker"
    assert (work / ".tdm" / vagrant_agent.READY).exists()  # VM finalement prête
    assert _take_calls(agent) == ["moteur-docker up", "moteur-docker destroy -f", "moteur-docker up"]


def test_agent_un_seul_lab_a_la_fois(agent):
    agent.engine_ports = []
    for lab in ("tdm:win-a", vagrant_agent.ENGINE):
        _run(agent, lab, "/up")
    _take_calls(agent)
    assert agent.running_bundled() == ["tdm:moteur-docker", "tdm:win-a"]

    paused = agent.exclusive("tdm:win-b")  # lab Windows : tout le reste passe en pause
    assert sorted(paused) == ["tdm:moteur-docker", "tdm:win-a"]
    for lab in paused:
        agent.jobs[lab]._thread.join(10)
    assert sorted(_take_calls(agent)) == ["moteur-docker suspend", "win-a suspend"]
    assert agent.status("tdm:win-a")["status"] == "stopped"

    _run(agent, "tdm:win-b", "/up")
    _take_calls(agent)
    assert agent.exclusive(vagrant_agent.ENGINE) == ["tdm:win-b"]  # lab Docker : les VM Windows en pause
    agent.jobs["tdm:win-b"]._thread.join(10)
    assert _take_calls(agent) == ["win-b suspend"]


def test_agent_pause_d_un_lab_en_train_de_demarrer(agent, tmp_path):
    slow = tmp_path / "vagrant-lent"
    slow.write_text(FAKE_VAGRANT.replace("exit 0\n", '[ "$1" = up ] && sleep 1\nexit 0\n'))
    slow.chmod(0o755)
    agent.vagrant = str(slow)
    action, steps = agent.lab_actions("tdm:win-a")["/up"]
    agent.run_job("tdm:win-a", action, *steps)
    time.sleep(0.2)
    assert agent.exclusive("tdm:win-b") == ["tdm:win-a"]
    agent.jobs["tdm:win-a"]._thread.join(10)
    calls = _take_calls(agent)
    assert calls[-1] == "win-a suspend" and "win-a up" in calls  # mis en pause dès la fin du démarrage


def test_agent_attend_les_pauses_avant_de_demarrer(agent, tmp_path):
    slow = tmp_path / "vagrant-lent"
    slow.write_text(FAKE_VAGRANT.replace("exit 0\n", '[ "$1" = suspend ] && sleep 1\nexit 0\n'))
    slow.chmod(0o755)
    _run(agent, "tdm:win-a", "/up")
    agent.vagrant = str(slow)
    agent.exclusive("tdm:win-b")
    _run(agent, "tdm:win-b", "/up")
    calls = _take_calls(agent)
    assert calls.index("win-a suspend") < calls.index("win-b up")
    assert "Mise en pause des autres labs" in "\n".join(agent.jobs["tdm:win-b"].log)


def test_agent_vboxmanage_liste_les_vm_allumees(agent, tmp_path):
    _run(agent, "tdm:win-a", "/up")
    _run(agent, "tdm:win-b", "/up")
    fake = tmp_path / "VBoxManage"
    fake.write_text('#!/bin/sh\necho \'"tdm-win-b" {id-win-b}\'\n')
    fake.chmod(0o755)
    agent.vboxmanage = str(fake)
    assert agent.running_bundled() == ["tdm:win-b"]


def test_agent_fermeture_met_tout_en_pause(agent):
    agent.engine_ports = []
    _run(agent, "tdm:win-a", "/up")
    _run(agent, vagrant_agent.ENGINE, "/up")
    _take_calls(agent)
    assert sorted(agent.suspend_all(timeout=10)) == ["tdm:moteur-docker", "tdm:win-a"]
    assert sorted(_take_calls(agent)) == ["moteur-docker suspend", "win-a suspend"]
    assert agent.suspend_all(timeout=10) == []  # plus rien ne tourne


def test_agent_http_exclusive_et_sante(agent, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), vagrant_agent.make_handler(agent, "jeton"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("TDM_VAGRANT_AGENT", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("TDM_VAGRANT_TOKEN", "jeton")
    try:
        info = vagrant.health()
        assert info["engine"] is True and info["vagrant"] is True and info["virtualbox"] is False
        assert vagrant.start_engine(engine.ENGINE_LAB, [8080, 9000]) == "starting"
        agent.jobs[vagrant_agent.ENGINE]._thread.join(10)
        assert (agent.work_dir / "moteur-docker" / "ports.txt").read_text() == "8080\n9000"
        assert vagrant.exclusive("tdm:win-a") == ["tdm:moteur-docker"]
    finally:
        server.shutdown()


# --- Avertissement « hyperviseur Windows » (texte seulement) -------------------------------------

def test_avertissement_hyperviseur(monkeypatch):
    monkeypatch.setattr(hypervisor, "is_windows", lambda: False)
    assert client.get("/api/system/hypervisor").json()["show"] is False
    monkeypatch.setattr(hypervisor, "present", lambda: True)
    monkeypatch.setattr(engine, "kind", lambda: "vm")
    assert client.get("/api/system/hypervisor").json() == {"show": True, "present": True, "engine": "vm"}
    monkeypatch.setattr(engine, "kind", lambda: "desktop")  # Docker Desktop a besoin de l'hyperviseur
    assert client.get("/api/system/hypervisor").json()["show"] is False
    monkeypatch.setattr(hypervisor, "present", lambda: False)
    monkeypatch.setattr(engine, "kind", lambda: "vm")
    assert client.get("/api/system/hypervisor").json()["show"] is False


def test_tdm_ne_lance_jamais_bcdedit():
    """L'utilisateur désactive l'hyperviseur lui-même s'il le veut : aucune commande ni route pour ça."""
    assert client.post("/api/system/hypervisor/disable", json={"confirm": True}).status_code in (404, 405)
    for path in [ROOT / "backend" / "app", ROOT / "frontend" / "app.js", ROOT / "desktop", ROOT / "scripts"]:
        files = [path] if path.is_file() else path.rglob("*.py")
        for file in files:
            assert "bcdedit" not in file.read_text(encoding="utf-8").lower(), file
