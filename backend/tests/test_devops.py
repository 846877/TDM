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
