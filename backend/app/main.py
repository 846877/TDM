"""API de la plateforme TDM et service du frontend."""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, profiles, sandbox, terminal
from .catalog import LEVEL_LABELS, LEVELS, Catalog, summary
from .devops import labs as devops
from .network import grader as net_grader
from .python import grader as py_grader

app = FastAPI(title="TDM - plateforme d'entraînement")

python_catalog = Catalog("python")
network_catalog = Catalog("network")

HIDDEN_PYTHON_FIELDS = {"solution", "tests", "cases"}


class CodeIn(BaseModel):
    code: str = Field(max_length=100_000)
    stdin: str = Field(default="", max_length=100_000)


class CommandIn(BaseModel):
    line: str = Field(max_length=2000)


class ProfileIn(BaseModel):
    name: str = Field(max_length=64)


ProfileHeader = Header(default=None, alias="X-TDM-Profile")


def _reward(result: dict, profile_id: int | None, category: str, item_id: str, level: str) -> dict:
    """Ajoute l'XP gagnée au résultat d'une validation réussie (si un profil est actif)."""
    if profile_id and result.get("success"):
        reward = profiles.record_success(profile_id, category, item_id, level)
        if reward:
            result = result | {"reward": reward}
    return result


def _python_exercise(exercise_id: str) -> dict:
    exercise = python_catalog.get(exercise_id)
    if exercise is None:
        raise HTTPException(404, "Exercice introuvable")
    return exercise


def _network_exercise(exercise_id: str) -> dict:
    exercise = network_catalog.get(exercise_id)
    if exercise is None:
        raise HTTPException(404, "Exercice introuvable")
    return exercise


def _lab(lab_id: str) -> dict:
    lab = next((lab for lab in devops.load_labs() if lab["id"] == lab_id), None)
    if lab is None:
        raise HTTPException(404, "Lab introuvable")
    return lab


# ---------------------------------------------------------------------------
# Général
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "sandbox": "docker" if config.use_docker_sandbox() else "local",
        "docker": config.docker_available(),
    }


@app.get("/api/categories")
def categories():
    return {
        "levels": [{"id": level, "label": LEVEL_LABELS[level]} for level in LEVELS],
        "categories": [
            {"id": "python", "title": "Python", "count": len(python_catalog.all()),
             "description": "Des bases jusqu'aux sujets avancés, corrigés par une moulinette."},
            {"id": "reseaux", "title": "Réseaux", "count": len(network_catalog.all()),
             "description": "Configuration Cisco IOS dans un terminal simulé : VLAN, trunks, routage, sécurité."},
            {"id": "systemes", "title": "Systèmes & réseaux", "count": len(devops.load_labs(category="systemes")),
             "description": "Le parcours du technicien : postes, accès distants, Active Directory, DNS/DHCP, "
                            "VLAN, routage, pare-feu, virtualisation, supervision."},
            {"id": "devops", "title": "DevOps", "count": len(devops.load_labs(category="devops")),
             "description": "Des labs lancés en un clic, en conteneur Docker ou en VM Vagrant, avec exercices vérifiés."},
        ],
    }


@app.post("/api/reload")
def reload_content():
    python_catalog.reload()
    network_catalog.reload()
    return {"python": len(python_catalog.all()), "network": len(network_catalog.all())}


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

@app.get("/api/python/exercises")
def python_exercises():
    return [summary(e) for e in python_catalog.all()]


@app.get("/api/python/exercises/{exercise_id}")
def python_exercise(exercise_id: str):
    exercise = _python_exercise(exercise_id)
    data = {k: v for k, v in exercise.items() if k not in HIDDEN_PYTHON_FIELDS}
    data.setdefault("starter", "")
    data["mode"] = exercise.get("mode", "function")
    return data


@app.post("/api/python/exercises/{exercise_id}/run")
def python_run(exercise_id: str, body: CodeIn):
    _python_exercise(exercise_id)
    return py_grader.run(body.code, body.stdin)


@app.post("/api/python/exercises/{exercise_id}/submit")
def python_submit(exercise_id: str, body: CodeIn, profile: int | None = ProfileHeader):
    exercise = _python_exercise(exercise_id)
    return _reward(py_grader.grade(exercise, body.code), profile, "python", exercise_id, exercise["level"])


@app.websocket("/ws/python/{exercise_id}")
async def python_terminal(websocket: WebSocket, exercise_id: str, client: str = "anon"):
    await websocket.accept()
    if python_catalog.get(exercise_id) is None:
        await websocket.close(code=4404)
        return
    if config.use_docker_sandbox():
        await _docker_python_terminal(websocket)
    else:
        await _local_python_terminal(websocket, exercise_id, client)


def _safe_filename(name: str) -> str | None:
    safe = Path(name).name
    return safe if safe and not safe.startswith(".") else None


async def _docker_python_terminal(websocket: WebSocket) -> None:
    name = "tdm-term-" + secrets.token_hex(6)
    try:
        await asyncio.to_thread(sandbox.start_terminal_container, name)
    except (subprocess.SubprocessError, OSError):
        await websocket.send_text("\x1b[31mImpossible de démarrer le bac à sable Docker.\x1b[0m\r\n")
        await websocket.close()
        return

    def write_file(filename: str, content: str) -> None:
        safe = _safe_filename(filename)
        if safe:
            sandbox.write_to_container(name, safe, content)

    def on_close() -> None:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)

    await terminal.bridge(websocket, ["docker", "exec", "-it", name, "bash"], on_file=write_file, on_close=on_close)


async def _local_python_terminal(websocket: WebSocket, exercise_id: str, client: str) -> None:
    client = re.sub(r"[^A-Za-z0-9_-]", "", client)[:64] or "anon"
    workspace = config.WORKSPACES_DIR / client / exercise_id
    workspace.mkdir(parents=True, exist_ok=True)

    def write_file(filename: str, content: str) -> None:
        safe = _safe_filename(filename)
        if safe:
            (workspace / safe).write_text(content, encoding="utf-8")

    python_dir = str(Path(config.python_command()[0]).parent)
    if os.name == "nt":
        # PowerShell, avec le Python de la plateforme en tête du PATH (« python solution.py »).
        args = ["powershell.exe", "-NoLogo", "-NoProfile", "-NoExit", "-Command",
                "function prompt { \"tdm:$(Split-Path -Leaf (Get-Location))> \" }"]
        env = {**os.environ, "PATH": python_dir + os.pathsep + os.environ.get("PATH", ""), "PYTHONUTF8": "1"}
    else:
        args = ["bash", "--noprofile", "--norc", "-i"] if shutil.which("bash") else ["sh", "-i"]
        env = {
            "PATH": python_dir + os.pathsep + os.environ.get("PATH", ""),
            "HOME": str(workspace),
            "TERM": "xterm-256color",
            "LANG": "C.UTF-8",
            "PS1": r"\[\e[32m\]tdm\[\e[0m\]:\[\e[34m\]\W\[\e[0m\]$ ",
        }
    await terminal.bridge(websocket, args, cwd=workspace, env=env, on_file=write_file)


# ---------------------------------------------------------------------------
# Réseaux
# ---------------------------------------------------------------------------

@app.get("/api/network/exercises")
def network_exercises():
    return [summary(e) | {"device": e.get("device", "switch")} for e in network_catalog.all()]


@app.get("/api/network/exercises/{exercise_id}")
def network_exercise(exercise_id: str):
    exercise = _network_exercise(exercise_id)
    data = {k: v for k, v in exercise.items() if k not in ("solution", "checks", "initial")}
    data["checks"] = [c["desc"] for c in exercise.get("checks", [])]
    data["device"] = exercise.get("device", "switch")
    return data


@app.post("/api/network/exercises/{exercise_id}/session")
def network_session(exercise_id: str):
    session_id, session = net_grader.create_session(_network_exercise(exercise_id))
    banner = (f"Simulateur Cisco IOS TDM - {session.device.kind}\n"
              "Astuce : les abréviations (conf t, int fa0/1...) et « ? » fonctionnent.\n\n"
              "Press RETURN to get started.")
    return {"session_id": session_id, "prompt": session.prompt, "banner": banner}


def _net_session(session_id: str):
    found = net_grader.get_session(session_id)
    if found is None:
        raise HTTPException(404, "Session expirée, recharge l'exercice.")
    return found


@app.post("/api/network/sessions/{session_id}/command")
def network_command(session_id: str, body: CommandIn):
    _, session = _net_session(session_id)
    output = session.execute(body.line)
    return {"output": output, "prompt": session.prompt}


@app.post("/api/network/sessions/{session_id}/check")
def network_check(session_id: str, profile: int | None = ProfileHeader):
    exercise_id, session = _net_session(session_id)
    exercise = _network_exercise(exercise_id)
    return _reward(net_grader.check(exercise, session.device), profile, "reseaux", exercise_id, exercise["level"])


# ---------------------------------------------------------------------------
# DevOps
# ---------------------------------------------------------------------------

@app.get("/api/devops/labs")
def devops_labs(category: str = "devops"):
    return [
        {k: v for k, v in devops.public(lab).items() if k != "description"} | {"exercise_count": len(lab["exercises"])}
        for lab in devops.load_labs(category=category)
    ]


@app.get("/api/devops/labs/{lab_id}")
def devops_lab(lab_id: str):
    lab = _lab(lab_id)
    status, log = devops.status_with_log(lab)
    return devops.public(lab) | {"status": status, "log": log}


def _lab_action(fn, *args):
    try:
        return fn(*args)
    except devops.LabError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/devops/labs/{lab_id}/start")
def devops_start(lab_id: str):
    return {"status": _lab_action(devops.start, _lab(lab_id))}


@app.post("/api/devops/labs/{lab_id}/stop")
def devops_stop(lab_id: str):
    return {"status": _lab_action(devops.stop, _lab(lab_id))}


@app.post("/api/devops/labs/{lab_id}/reset")
def devops_reset(lab_id: str):
    lab = _lab(lab_id)
    return {"status": _lab_action(devops.reset, lab)}


@app.post("/api/devops/labs/{lab_id}/exercises/{exercise_id}/check")
def devops_check(lab_id: str, exercise_id: str, profile: int | None = ProfileHeader):
    lab = _lab(lab_id)
    result = _lab_action(devops.check, lab, exercise_id)
    return _reward(result, profile, lab["category"], f"{lab_id}/{exercise_id}", lab["level"])


@app.websocket("/ws/devops/{lab_id}")
async def devops_terminal(websocket: WebSocket, lab_id: str):
    await websocket.accept()
    lab = next((lab for lab in devops.load_labs() if lab["id"] == lab_id), None)
    if lab is None or devops.status(lab) != "running":
        await websocket.send_text("\x1b[31mLe lab n'est pas démarré.\x1b[0m\r\n")
        await websocket.close()
        return
    try:
        argv = await asyncio.to_thread(devops.terminal_argv, lab)
    except devops.LabError as exc:
        await websocket.send_text(f"\x1b[31m{exc}\x1b[0m\r\n")
        await websocket.close()
        return
    await terminal.bridge(websocket, argv)


# ---------------------------------------------------------------------------
# Profils et classement
# ---------------------------------------------------------------------------

def _totals() -> dict[str, int]:
    return {
        "python": len(python_catalog.all()),
        "reseaux": len(network_catalog.all()),
        **{category: sum(len(lab["exercises"]) for lab in devops.load_labs(category=category))
           for category in devops.LAB_CATEGORIES},
    }


@app.get("/api/profiles")
def profiles_list():
    return profiles.list_profiles()


@app.post("/api/profiles")
def profiles_create(body: ProfileIn):
    try:
        return profiles.create_profile(body.name)
    except profiles.ProfileError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/profiles/{profile_id}")
def profiles_get(profile_id: int):
    profile = profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, "Profil introuvable")
    totals = _totals()
    for category, total in totals.items():
        stats = profile["categories"].setdefault(category, {"done": 0, "xp": 0, "levels": {}})
        stats["total"] = total
        stats["title"] = profiles.category_title(category, stats["done"], total)
    for item in profile["recent"]:
        item["title"] = _item_title(item["category"], item["item_id"])
    return profile | {"titles": profiles.titles_ladder()}


def _item_title(category: str, item_id: str) -> str:
    if category == "python":
        found = python_catalog.get(item_id)
    elif category == "reseaux":
        found = network_catalog.get(item_id)
    else:  # labs DevOps ou Systèmes & réseaux
        lab_id, _, exercise_id = item_id.partition("/")
        lab = next((lab for lab in devops.load_labs() if lab["id"] == lab_id), None)
        exercise = next((e for e in lab["exercises"] if e["id"] == exercise_id), None) if lab else None
        return f"{lab['title']} · {exercise['title']}" if exercise else item_id
    return found["title"] if found else item_id


@app.delete("/api/profiles/{profile_id}")
def profiles_delete(profile_id: int):
    profiles.delete_profile(profile_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")
