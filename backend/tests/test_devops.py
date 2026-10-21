"""Tests des labs DevOps : définitions, labs Vagrant et agent Vagrant (avec un faux vagrant)."""

import json
import urllib.error
import socket
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.devops import labs, vagrant
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import vagrant_agent  # noqa: E402

client = TestClient(app)


def test_definitions_des_labs():
    loaded = labs.load_labs()
    assert len(loaded) >= 15
    for lab in loaded:
        assert lab["exercises"], lab["id"]
        for exercise in lab["exercises"]:
            assert exercise.get("title") and exercise.get("checks"), (lab["id"], exercise["id"])
            assert all(c.get("desc") and c.get("run") for c in exercise["checks"]), (lab["id"], exercise["id"])


def test_identifiants_uniques():
    ids = [lab["id"] for lab in labs.load_labs()]
    assert len(ids) == len(set(ids)), sorted(i for i in ids if ids.count(i) > 1)


def test_labs_compose_sans_montage_de_dossier():
    # La plateforme pilote le Docker de l'hôte depuis un conteneur : un montage relatif ne marcherait pas.
    for compose in (ROOT / "labs").glob("*/*/docker-compose.yml"):
        for line in compose.read_text(encoding="utf-8").splitlines():
            assert not line.strip().startswith(("- ./", "- ../", "- /")), f"{compose}: {line}"


def test_lab_vagrant_sans_agent(monkeypatch):
    monkeypatch.setenv("TDM_VAGRANT_AGENT", "http://127.0.0.1:9")
    data = client.get("/api/devops/labs/kubernetes").json()
    assert data["kind"] == "vagrant" and data["status"] == "unavailable"
    response = client.post("/api/devops/labs/kubernetes/start")
    assert response.status_code == 503 and "agent" in response.json()["detail"].lower()


FAKE_VAGRANT = """#!/bin/sh
case "$1" in
  status) if [ -f up ]; then s=running; else s=poweroff; fi; echo "1,default,state,$s" ;;
  up) echo "Bringing machine up"; touch up ;;
  halt) rm -f up ;;
  destroy) rm -f up ;;
  ssh-config) printf '  HostName 127.0.0.1\\n  User vagrant\\n  Port %s\\n  IdentityFile "%s/key"\\n' "$SSH_PORT" "$PWD" ;;
esac
"""


@pytest.fixture
def agent(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("faux vagrant en shell")
    lab = tmp_path / "k8s" / "ubuntu"
    lab.mkdir(parents=True)
    (lab / "Vagrantfile").write_text("")
    (lab / "key").write_text("CLE-PRIVEE")
    fake = tmp_path / "vagrant"
    fake.write_text(FAKE_VAGRANT)
    fake.chmod(0o755)
    target = socket.socket()
    target.bind(("127.0.0.1", 0))
    target.listen()
    monkeypatch.setenv("SSH_PORT", str(target.getsockname()[1]))
    server = ThreadingHTTPServer(("127.0.0.1", 0), vagrant_agent.make_handler(
        vagrant_agent.Agent(tmp_path, str(fake)), "jeton"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("TDM_VAGRANT_AGENT", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("TDM_VAGRANT_TOKEN", "jeton")
    monkeypatch.setenv("TDM_VAGRANT_HOST", "127.0.0.1")
    yield {"id": "k8s", "vagrant": "k8s/ubuntu", "exercises": []}, target
    server.shutdown()
    target.close()


def test_agent_refuse_sans_jeton(agent):
    url = vagrant.agent_url() + "/status?lab=k8s/ubuntu"
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(url)
    assert exc.value.code == 401


def test_agent_refuse_hors_dossier(agent):
    with pytest.raises(vagrant.AgentError):
        vagrant._request("GET", "/status", {"lab": "../.."})


def test_agent_cycle_de_vie(agent):
    lab, target = agent
    assert vagrant.status(lab)[0] == "stopped"
    assert vagrant.start(lab) == "starting"
    for _ in range(50):
        status, log = vagrant.status(lab)
        if status == "running":
            break
        time.sleep(0.1)
    assert status == "running" and "Bringing machine up" in log
    argv = vagrant.ssh_argv(lab, "echo ok")
    assert argv[0] == "ssh" and argv[-1] == "sh -c 'echo ok'" and "vagrant@127.0.0.1" in argv
    assert Path(argv[argv.index("-i") + 1]).read_text() == "CLE-PRIVEE"
    # Le relais transmet bien vers le port SSH de la VM.
    port = int(argv[argv.index("-p") + 1])
    with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
        upstream, _ = target.accept()
        conn.sendall(b"SSH-2.0-test")
        assert upstream.recv(64) == b"SSH-2.0-test"
        upstream.close()
    vagrant.stop(lab)
    for _ in range(50):
        if vagrant.status(lab)[0] == "stopped":
            break
        time.sleep(0.1)
    assert vagrant.status(lab)[0] == "stopped"


def test_agent_journal_progression_sans_fin_de_ligne():
    """Sans terminal, Vagrant écrit la progression d'un téléchargement sans retour à la ligne."""
    import io

    job = vagrant_agent.Job.__new__(vagrant_agent.Job)
    job.log = vagrant_agent.deque(maxlen=200)
    flux = io.BufferedReader(io.BytesIO(
        "Downloading: https://x/box\n    default: Progress: 10% (Rate: 5M/s)    default: Progress: 40% "
        "(Rate: 6M/s)\n==> default: Successfully added box 'é'\n".encode()))
    job._read(flux)
    assert list(job.log) == ["Downloading: https://x/box", "Progress: 40% (Rate: 6M/s)",
                             "==> default: Successfully added box 'é'"]


FAKE_VAGRANT_SNAPSHOT = """#!/bin/sh
echo "$*" >> calls
case "$1" in
  snapshot) [ "$2" = restore ] && [ -f casse ] && exit 1 ; exit 0 ;;
esac
exit 0
"""


def test_agent_labs_embarques_pause_et_instantane(tmp_path):
    """VM Windows : pause au lieu d'arrêt, instantané après la 1re préparation, restauration au reset."""
    if sys.platform == "win32":
        pytest.skip("faux vagrant en shell")
    bundled = tmp_path / "bundled"
    (bundled / "win-lab").mkdir(parents=True)
    (bundled / "win-lab" / "Vagrantfile").write_text("v1")
    fake = tmp_path / "vagrant"
    fake.write_text(FAKE_VAGRANT_SNAPSHOT)
    fake.chmod(0o755)
    ag = vagrant_agent.Agent(None, str(fake), bundled=bundled, work_dir=tmp_path / "work")
    work = tmp_path / "work" / "win-lab"

    def run(path):
        action, steps = ag.lab_actions("tdm:win-lab")[path]
        ag.run_job("tdm:win-lab", action, *steps)
        ag.jobs["tdm:win-lab"]._thread.join(10)
        assert ag.jobs["tdm:win-lab"].returncode == 0
        calls = (work / "calls").read_text().splitlines()
        (work / "calls").unlink()
        return calls

    assert run("/up") == ["up", "snapshot save tdm-initial --force"]
    assert run("/up") == ["up"]  # instantané déjà pris
    assert run("/halt") == ["suspend"]
    assert run("/reset") == ["snapshot restore tdm-initial --no-provision", "up --no-provision"]
    (work / "casse").write_text("")  # instantané perdu (VM supprimées à la main...) : reconstruction
    assert run("/reset") == ["snapshot restore tdm-initial --no-provision", "destroy -f", "up",
                             "snapshot save tdm-initial --force"]
    (bundled / "win-lab" / "Vagrantfile").write_text("v2")  # lab mis à jour : l'instantané est périmé
    assert run("/reset") == ["destroy -f", "up", "snapshot save tdm-initial --force"]
    # Les labs de l'utilisateur gardent le comportement d'origine.
    assert ag.lab_actions("k8s/ubuntu")["/halt"] == ("halt", [[str(fake), "halt"]])


def test_agent_verifications_prealables(tmp_path, monkeypatch):
    vagrantfile = tmp_path / "Vagrantfile"
    vagrantfile.write_text('lab.server "dc01", hostname: "DC01"\n    lab.client "pc01", hostname: "PC01", memory: 4096\n')
    assert vagrant_agent.lab_machines(vagrantfile) == [(vagrant_agent.SERVER_BOX, 2048), (vagrant_agent.CLIENT_BOX, 4096)]
    monkeypatch.setattr(vagrant_agent, "free_memory_mb", lambda: 3000)
    monkeypatch.setattr(vagrant_agent, "hypervisor_present", lambda: True)
    monkeypatch.setattr(vagrant_agent, "installed_boxes", lambda v: {vagrant_agent.SERVER_BOX})
    warnings = vagrant_agent.preflight_warnings(vagrantfile, "vagrant")
    assert len(warnings) == 3 and "Mémoire" in warnings[0] and "Hyper-V" in warnings[1]
    assert vagrant_agent.CLIENT_BOX in warnings[2]
    monkeypatch.setattr(vagrant_agent, "free_memory_mb", lambda: 16000)
    monkeypatch.setattr(vagrant_agent, "hypervisor_present", lambda: False)
    monkeypatch.setattr(vagrant_agent, "installed_boxes", lambda v: {vagrant_agent.SERVER_BOX, vagrant_agent.CLIENT_BOX})
    assert vagrant_agent.preflight_warnings(vagrantfile, "vagrant") == []
