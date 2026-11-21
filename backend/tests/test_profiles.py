"""Profils : création, XP accordée une seule fois, niveaux, titres et classement."""

import pytest
import yaml
from fastapi.testclient import TestClient

from app import config, profiles
from app.main import app

client = TestClient(app)


def _solution(exercise_id):
    return yaml.safe_load((config.CONTENT_DIR / "python" / f"{exercise_id}.yaml").read_text(encoding="utf-8"))["solution"]


def _create(name):
    response = client.post("/api/profiles", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


def test_niveaux_et_titres():
    assert profiles.level_for_xp(0) == 1
    assert profiles.level_for_xp(49) == 1 and profiles.level_for_xp(50) == 2
    assert profiles.level_for_xp(profiles.xp_for_level(12)) == 12
    assert profiles.title_for(1)["name"] == "Recrue"
    assert profiles.title_for(12)["name"] == "Ingénieur"
    assert profiles.title_for(1, "tdm") == {"name": "GOD", "description": profiles.GOD_TITLE[1], "god": True}


def test_pseudo_invalide_ou_pris():
    _create("Alice")
    assert client.post("/api/profiles", json={"name": "alice"}).status_code == 400
    assert client.post("/api/profiles", json={"name": "x"}).status_code == 400


def test_xp_une_seule_fois_et_classement():
    bob = _create("Bob")
    headers = {"X-TDM-Profile": str(bob["id"])}
    first = client.post("/api/python/exercises/003-addition/submit", json={"code": _solution("003-addition")},
                        headers=headers).json()
    assert first["success"] and first["reward"]["xp_gained"] == profiles.XP_BY_LEVEL["debutant"]
    again = client.post("/api/python/exercises/003-addition/submit", json={"code": _solution("003-addition")},
                        headers=headers).json()
    assert again["reward"]["xp_gained"] == 0
    failed = client.post("/api/python/exercises/003-addition/submit", json={"code": "def addition(a, b): pass"},
                         headers=headers).json()
    assert "reward" not in failed

    detail = client.get(f"/api/profiles/{bob['id']}").json()
    assert detail["xp"] == 10 and detail["completed_items"]["python"] == ["003-addition"]
    assert detail["categories"]["python"]["total"] >= 40
    assert detail["rank"] == 1
    ranking = client.get("/api/profiles").json()
    assert ranking[0]["name"] == "Bob" and [p["rank"] for p in ranking] == list(range(1, len(ranking) + 1))


def test_profil_god():
    god = _create("TDM")
    assert god["title"]["god"] and god["title"]["name"] == "GOD"


@pytest.mark.parametrize("exercise_id", ["101-trunk"])
def test_xp_reseau(exercise_id):
    carol = _create("Carol")
    session = client.post(f"/api/network/exercises/{exercise_id}/session").json()
    exercise = yaml.safe_load((config.CONTENT_DIR / "network" / f"{exercise_id}.yaml").read_text(encoding="utf-8"))
    for line in ["enable", *exercise["solution"].splitlines()]:
        client.post(f"/api/network/sessions/{session['session_id']}/command", json={"line": line})
    result = client.post(f"/api/network/sessions/{session['session_id']}/check",
                         headers={"X-TDM-Profile": str(carol["id"])}).json()
    assert result["success"] and result["reward"]["xp_gained"] == profiles.XP_BY_LEVEL[exercise["level"]]


def test_suppression():
    dave = _create("Dave")
    assert client.delete(f"/api/profiles/{dave['id']}").status_code == 200
    assert client.get(f"/api/profiles/{dave['id']}").status_code == 404
