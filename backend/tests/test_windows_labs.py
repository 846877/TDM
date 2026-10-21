"""Labs Windows (labs/systemes-windows) : chargement, copie persistante, enveloppe des vérifications."""

import base64
import os
import shutil
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.devops import labs, vagrant, windows
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import vagrant_agent  # noqa: E402
import windows_labs_ci  # noqa: E402

client = TestClient(app)


def _windows_labs():
    return [lab for lab in labs.load_labs() if lab.get("os") == "windows"]


def _powershell():
    for candidate in (os.environ.get("TDM_POWERSHELL"), "powershell", "pwsh"):
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    return None


# ---------------------------------------------------------------------------
# Définitions
# ---------------------------------------------------------------------------

def test_labs_windows_charges():
    loaded = _windows_labs()
    assert len(loaded) >= 13
    assert {lab["level"] for lab in loaded} >= {"debutant", "intermediaire"}
    for lab in loaded:
        folder = Path(lab["dir"])
        assert folder.parent == config.WINDOWS_LABS_DIR
        assert lab["category"] == "systemes" and lab["shell"] == "powershell"
        assert lab["vagrant"] == "tdm:" + folder.name, lab["id"]
        assert (folder / "Vagrantfile").exists(), lab["id"]
        assert "_commun/tdm" in (folder / "Vagrantfile").read_text(encoding="utf-8"), lab["id"]
        assert len(lab.get("cours", "").split()) >= 300, lab["id"]
        assert 1 <= len(lab.get("docs") or []) <= 4, lab["id"]
        for doc in lab["docs"]:
            assert doc["title"] and doc["url"].startswith("https://learn.microsoft.com/fr-fr/"), lab["id"]
        assert len(lab["exercises"]) >= 6, lab["id"]


def test_exercices_windows_complets():
    for lab in _windows_labs():
        for exercise in lab["exercises"]:
            where = f"{lab['id']}/{exercise['id']}"
            assert exercise["id"].startswith("win-"), where
            assert exercise.get("title") and exercise.get("description") and exercise.get("hint"), where
            assert len((exercise.get("cours") or "").split()) >= 50, where
            assert exercise.get("checks"), where
            for check in exercise["checks"]:
                assert check.get("desc") and check.get("run"), where
                assert set(check) <= {"desc", "run", "machine", "timeout", "hint"}, where
            if exercise.get("ci"):
                assert exercise.get("solution"), f"{where} : ci sans solution"
                assert not any(c.get("machine") for c in exercise["checks"]), f"{where} : ci sur une autre VM"


def test_exercices_avances_et_experts_documentes():
    for lab in _windows_labs():
        if lab["level"] not in {"avance", "expert"}:
            continue
        for exercise in lab["exercises"]:
            where = f"{lab['id']}/{exercise['id']}"
            assert 1 <= len(exercise.get("docs") or []) <= 4, where
            for doc in exercise["docs"]:
                assert doc["title"] and doc["url"].startswith("https://learn.microsoft.com/fr-fr/"), where


def test_identifiants_exercices_windows_uniques_partout():
    all_ids = [e["id"] for lab in labs.load_labs() for e in lab["exercises"]]
    for lab in _windows_labs():
        for exercise in lab["exercises"]:
            assert all_ids.count(exercise["id"]) == 1, exercise["id"]


def test_machines_des_verifications_existent():
    for lab in _windows_labs():
        vagrantfile = (Path(lab["dir"]) / "Vagrantfile").read_text(encoding="utf-8")
        machines = {lab.get("machine")} | {c.get("machine") for e in lab["exercises"] for c in e["checks"]}
        for machine in machines - {None}:
            assert f'"{machine}"' in vagrantfile, (lab["id"], machine)


def test_api_cache_solutions_et_filtre_os():
    listed = client.get("/api/devops/labs", params={"category": "systemes"}).json()
    windows_ids = {lab["id"] for lab in listed if lab["os"] == "windows"}
    assert windows_ids == {lab["id"] for lab in _windows_labs()}
    assert any(lab["os"] == "linux" for lab in listed)
    lab_id = sorted(windows_ids)[0]
    detail = client.get(f"/api/devops/labs/{lab_id}").json()
    assert detail["kind"] == "vagrant" and detail["os"] == "windows" and detail["cours"]
    for exercise in detail["exercises"]:
        assert "solution" not in exercise and "checks" not in exercise and "ci" not in exercise


# ---------------------------------------------------------------------------
# Enveloppe PowerShell des vérifications
# ---------------------------------------------------------------------------

def test_commande_encodee():
    command = windows.check_command("Get-LocalUser 'élève'")
    assert command.startswith("powershell.exe ") and "-EncodedCommand" in command
    script = base64.b64decode(command.split()[-1]).decode("utf-16-le")
    inner = script.split("FromBase64String('")[1].split("'")[0]
    assert base64.b64decode(inner).decode("utf-8") == "Get-LocalUser 'élève'"
    assert all(ch.isalnum() or ch in " -.+/=" for ch in command)  # rien à échapper côté SSH


def test_ssh_argv_windows(monkeypatch):
    monkeypatch.setattr(vagrant, "_request", lambda *a, **k: {"port": 2222, "user": "vagrant", "key": "K",
                                                             "key_path": ""})
    monkeypatch.setenv("TDM_VAGRANT_HOST", "127.0.0.1")
    lab = {"id": "t", "vagrant": "tdm:t", "os": "windows"}
    argv = vagrant.ssh_argv(lab, "$true")
    assert argv[-1] == windows.check_command("$true")
    assert vagrant.ssh_argv({**lab, "os": "linux"}, "true")[-1] == "sh -c true"
    assert "-t" in vagrant.ssh_argv(lab)


VERDICTS = [
    ("$true", 0), ("1 -eq 2", 1), ("@()", 1), ("Get-Item '/n/existe/pas'", 1), ("throw 'non'", 1),
    ("'texte'", 0), ("0", 1), ("$null", 1), ("exit 0", 0), ("exit 3", 3), ("if (", 1),
    ("-not (Get-Item '/n/existe/pas' -ErrorAction SilentlyContinue)", 0), ("return $true; $false", 0),
    ("'a'; $false", 1), ("$false; 'a'", 0),
]


@pytest.mark.skipif(_powershell() is None, reason="PowerShell absent")
@pytest.mark.parametrize("code,expected", VERDICTS)
def test_enveloppe_verdicts(code, expected):
    import subprocess

    result = subprocess.run(windows.encoded_argv(windows.wrap_check(code), _powershell()), capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    assert result.returncode == expected, (code, result.stdout, result.stderr)


@pytest.mark.skipif(_powershell() is None, reason="PowerShell absent")
def test_syntaxe_powershell_des_labs():
    assert windows_labs_ci.static(check_commands=False) == 0


def test_liste_ci():
    ci = windows_labs_ci.ci_labs()
    assert ci and set(ci) <= {lab["id"] for lab in _windows_labs()}


# ---------------------------------------------------------------------------
# Copie persistante des labs embarqués
# ---------------------------------------------------------------------------

def test_sync_tree(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    (src / "sous").mkdir(parents=True)
    (src / "Vagrantfile").write_text("v1")
    (src / "sous" / "a.ps1").write_text("a")
    (src / "vieux.ps1").write_text("x")
    assert sorted(vagrant_agent.sync_tree(src, dest)) == ["Vagrantfile", "sous/a.ps1", "vieux.ps1"]
    (dest / ".vagrant").mkdir()
    (dest / ".vagrant" / "id").write_text("vm")
    (dest / ".tdm").mkdir()
    (dest / ".tdm" / "id_rsa").write_text("cle")
    (src / "Vagrantfile").write_text("v2")
    (src / "vieux.ps1").unlink()
    assert vagrant_agent.sync_tree(src, dest) == ["Vagrantfile"]
    assert (dest / "Vagrantfile").read_text() == "v2"
    assert not (dest / "vieux.ps1").exists()
    assert (dest / ".vagrant" / "id").read_text() == "vm" and (dest / ".tdm" / "id_rsa").read_text() == "cle"
    assert vagrant_agent.sync_tree(src, dest) == []


def test_agent_noms_embarques(tmp_path, monkeypatch):
    monkeypatch.setattr(vagrant_agent.shutil, "which", lambda name: "/bin/vagrant")
    bundled = tmp_path / "bundled"
    (bundled / "mon-lab").mkdir(parents=True)
    (bundled / "mon-lab" / "Vagrantfile").write_text("")
    agent = vagrant_agent.Agent(None, "vagrant", bundled=bundled, work_dir=tmp_path / "work")
    assert agent.lab_dir("tdm:mon-lab") == (tmp_path / "work" / "mon-lab").resolve()
    for bad in ("tdm:../x", "tdm:Mon_Lab", "tdm:", "tdm:absent"):
        with pytest.raises(ValueError):
            agent.lab_dir(bad)
    with pytest.raises(ValueError):  # sans TDM_VAGRANT_DIR, seuls les labs embarqués existent
        agent.lab_dir("k8s/ubuntu")


FAKE_VAGRANT = """#!/bin/sh
case "$1" in
  status) if [ -f .vagrant/up ]; then s=running; else s=poweroff; fi; echo "1,dc01,state,$s" ;;
  up) mkdir -p .vagrant; touch .vagrant/up; echo "up depuis $PWD" ;;
  halt|suspend) rm -f .vagrant/up ;;
  destroy) rm -rf .vagrant ;;
  ssh-config) printf '  HostName 127.0.0.1\\n  User vagrant\\n  Port %s\\n  IdentityFile "%s/.tdm/id_rsa"\\n' "$SSH_PORT" "$PWD" ;;
esac
"""


def _wait(lab, wanted):
    for _ in range(100):
        state = vagrant.status(lab)[0]
        if state == wanted:
            return state
        time.sleep(0.05)
    return state


def test_agent_lab_embarque(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("faux vagrant en shell")
    bundled, work = tmp_path / "bundled", tmp_path / "work"
    (bundled / "_commun").mkdir(parents=True)
    (bundled / "_commun" / "tdm.rb").write_text("# commun")
    (bundled / "win-lab").mkdir()
    (bundled / "win-lab" / "Vagrantfile").write_text('require_relative "../_commun/tdm"')
    fake = tmp_path / "vagrant"
    fake.write_text(FAKE_VAGRANT)
    fake.chmod(0o755)
    target = socket.socket()
    target.bind(("127.0.0.1", 0))
    target.listen()
    monkeypatch.setenv("SSH_PORT", str(target.getsockname()[1]))
    agent = vagrant_agent.Agent(None, str(fake), relay=False, bundled=bundled, work_dir=work)
    server = ThreadingHTTPServer(("127.0.0.1", 0), vagrant_agent.make_handler(agent, "jeton"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("TDM_VAGRANT_AGENT", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("TDM_VAGRANT_TOKEN", "jeton")
    monkeypatch.setenv("TDM_VAGRANT_HOST", "127.0.0.1")
    lab = {"id": "win-lab", "vagrant": "tdm:win-lab", "os": "windows", "exercises": []}
    try:
        assert vagrant.status(lab)[0] == "stopped" and not work.exists()
        with pytest.raises(vagrant.AgentError):
            vagrant.ssh_argv(lab)
        assert vagrant.start(lab) == "starting"
        assert _wait(lab, "running") == "running"
        assert (work / "win-lab" / "Vagrantfile").exists() and (work / "_commun" / "tdm.rb").exists()
        assert "up depuis " + str(work / "win-lab") in vagrant.status(lab)[1]
        # Clé générée par le Vagrantfile dans la copie : la plateforme la lit sur place (même machine).
        (work / "win-lab" / ".tdm").mkdir(exist_ok=True)
        (work / "win-lab" / ".tdm" / "id_rsa").write_text("CLE")
        argv = vagrant.ssh_argv(lab, "$true")
        assert Path(argv[argv.index("-i") + 1]) == work / "win-lab" / ".tdm" / "id_rsa"
        assert argv[-1].startswith("powershell.exe ")
        # Arrêt puis redémarrage après une mise à jour de TDM : la copie est rafraîchie, l'état conservé.
        vagrant.stop(lab)
        assert _wait(lab, "stopped") == "stopped"
        (bundled / "win-lab" / "Vagrantfile").write_text("# v2")
        (work / "win-lab" / ".vagrant" / "machines").mkdir(parents=True)
        vagrant.start(lab)
        assert _wait(lab, "running") == "running"
        assert (work / "win-lab" / "Vagrantfile").read_text() == "# v2"
        assert (work / "win-lab" / ".vagrant" / "machines").is_dir()
        assert (work / "win-lab" / ".tdm" / "id_rsa").read_text() == "CLE"
    finally:
        server.shutdown()
        target.close()


def test_ci_powershell_51_sans_psmodulepath_de_pwsh(monkeypatch):
    monkeypatch.setenv("PSModulePath", r"C:\Program Files\PowerShell\7\Modules")
    monkeypatch.setattr(windows_labs_ci, "powershell", lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
    assert "psmodulepath" not in {k.lower() for k in windows_labs_ci.ps_env()}
    monkeypatch.setattr(windows_labs_ci, "powershell", lambda: "/usr/bin/pwsh")
    assert "psmodulepath" in {k.lower() for k in windows_labs_ci.ps_env()}


def test_ci_ne_rejoue_que_les_labs_modifies():
    labs = ["win-a", "win-b"]
    assert windows_labs_ci.changed_labs(labs, ["labs/systemes-windows/win-b/lab.yaml", "README.md"]) == ["win-b"]
    assert windows_labs_ci.changed_labs(labs, ["frontend/app.js"]) == []
    assert windows_labs_ci.changed_labs(labs, ["labs/systemes-windows/_commun/tdm.rb"]) == labs
    assert windows_labs_ci.changed_labs(labs, ["TOUT"]) == labs
