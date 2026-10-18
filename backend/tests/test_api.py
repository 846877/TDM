"""Tests de l'API HTTP (mode d'exécution local, sans Docker)."""

import json

import pytest

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_categories():
    data = client.get("/api/categories").json()
    counts = {c["id"]: c["count"] for c in data["categories"]}
    assert counts["python"] >= 40 and counts["reseaux"] >= 15 and counts["devops"] >= 3


def test_exercice_python_sans_solution():
    data = client.get("/api/python/exercises/003-addition").json()
    assert data["title"] and "solution" not in data and "tests" not in data


def test_exercice_inconnu():
    assert client.get("/api/python/exercises/nope").status_code == 404


def test_soumission_python():
    ok = client.post("/api/python/exercises/003-addition/submit",
                     json={"code": "def addition(a, b):\n    return a + b\n"}).json()
    assert ok["success"] and ok["passed"] == ok["total"] == 3
    ko = client.post("/api/python/exercises/003-addition/submit",
                     json={"code": "def addition(a, b):\n    return a * b\n"}).json()
    assert not ko["success"]


def test_erreur_de_syntaxe():
    res = client.post("/api/python/exercises/003-addition/submit", json={"code": "def addition(a, b)\n"}).json()
    assert not res["success"] and "SyntaxError" in res["results"][0]["message"]


def test_execution():
    res = client.post("/api/python/exercises/002-saluer/run",
                      json={"code": "print('Salut', input(), '!')", "stdin": "Zoé\n"}).json()
    assert res["stdout"].strip() == "Salut Zoé !"


def test_session_reseau():
    session = client.post("/api/network/exercises/001-modes-hostname/session").json()
    sid = session["session_id"]
    assert session["prompt"] == "Switch>"
    for line in ["enable", "conf t", "hostname SW1", "end"]:
        res = client.post(f"/api/network/sessions/{sid}/command", json={"line": line}).json()
    assert res["prompt"] == "SW1#"
    assert client.post(f"/api/network/sessions/{sid}/check").json()["success"]


def test_detail_reseau_masque_la_correction():
    data = client.get("/api/network/exercises/101-trunk").json()
    assert "solution" not in data and all(isinstance(c, str) for c in data["checks"])


def test_labs_listes():
    labs = client.get("/api/devops/labs").json()
    assert {"linux-bases", "nginx-web", "git-bases"} <= {lab["id"] for lab in labs}
    assert all('"checks"' not in json.dumps(lab) and '"run"' not in json.dumps(lab) for lab in labs)


def test_terminal_python_local(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.WORKSPACES_DIR", tmp_path)
    monkeypatch.setattr("app.config.SANDBOX_MODE", "local")
    with client.websocket_connect("/ws/python/003-addition?client=test") as ws:
        ws.send_text(json.dumps({"type": "file", "name": "solution.py", "content": "print(6 * 7)\n"}))
        ws.send_text(json.dumps({"type": "input", "data": "python3 solution.py; exit\n"}))
        output = ""
        while "42" not in output:
            output += ws.receive_text()
    assert (tmp_path / "test" / "003-addition" / "solution.py").exists()


@pytest.mark.skipif(not config.docker_available(), reason="Docker indisponible")
def test_terminal_python_docker(monkeypatch):
    monkeypatch.setattr("app.config.SANDBOX_MODE", "docker")
    with client.websocket_connect("/ws/python/003-addition") as ws:
        ws.send_text(json.dumps({"type": "file", "name": "solution.py", "content": "print(6 * 7)\n"}))
        ws.send_text(json.dumps({"type": "input", "data": "python solution.py; exit\n"}))
        output = ""
        while "42" not in output:
            output += ws.receive_text()
