"""API de la plateforme TDM et service du frontend."""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, terminal
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
            {"id": "devops", "title": "DevOps", "count": len(devops.load_labs()),
             "description": "Des labs lancés en un clic dans des conteneurs, avec exercices vérifiés."},
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
def python_submit(exercise_id: str, body: CodeIn):
    return py_grader.grade(_python_exercise(exercise_id), body.code)


@app.websocket("/ws/python/{exercise_id}")
async def python_terminal(websocket: WebSocket, exercise_id: str, client: str = "anon"):
    await websocket.accept()
    if python_catalog.get(exercise_id) is None:
        await websocket.close(code=4404)
        return
    client = re.sub(r"[^A-Za-z0-9_-]", "", client)[:64] or "anon"
    workspace = config.WORKSPACES_DIR / client / exercise_id
    workspace.mkdir(parents=True, exist_ok=True)
    os.chmod(workspace, 0o777)

    def write_file(name: str, content: str) -> None:
        safe = Path(name).name
        if safe and not safe.startswith("."):
            (workspace / safe).write_text(content, encoding="utf-8")

    on_close = None
    if config.use_docker_sandbox():
        name = "tdm-term-" + secrets.token_hex(6)
        args = config_docker_terminal(workspace, name)
        env = None

        def on_close() -> None:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    else:
        args = ["bash", "--noprofile", "--norc", "-i"] if shutil.which("bash") else ["sh", "-i"]
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(workspace),
            "TERM": "xterm-256color",
            "LANG": "C.UTF-8",
            "PS1": r"\[\e[32m\]tdm\[\e[0m\]:\[\e[34m\]\W\[\e[0m\]$ ",
        }
    await terminal.bridge(websocket, args, cwd=workspace, env=env, on_file=write_file, on_close=on_close)


def config_docker_terminal(workspace: Path, name: str) -> list[str]:
    from .sandbox import docker_run_args

    args = docker_run_args(workspace, interactive=True)
    return args[:2] + ["--name", name, "-e", "TERM=xterm-256color", "-e", "PS1=tdm:\\W$ "] + args[2:] + ["bash"]


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
def network_check(session_id: str):
    exercise_id, session = _net_session(session_id)
    return net_grader.check(_network_exercise(exercise_id), session.device)


# ---------------------------------------------------------------------------
# DevOps
# ---------------------------------------------------------------------------

@app.get("/api/devops/labs")
def devops_labs():
    return [
        {k: v for k, v in devops.public(lab).items() if k != "description"} | {"exercise_count": len(lab["exercises"])}
        for lab in devops.load_labs()
    ]


@app.get("/api/devops/labs/{lab_id}")
def devops_lab(lab_id: str):
    lab = _lab(lab_id)
    return devops.public(lab) | {"status": devops.status(lab)}


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
    _lab_action(devops.stop, lab)
    return {"status": _lab_action(devops.start, lab)}


@app.post("/api/devops/labs/{lab_id}/exercises/{exercise_id}/check")
def devops_check(lab_id: str, exercise_id: str):
    return _lab_action(devops.check, _lab(lab_id), exercise_id)


@app.websocket("/ws/devops/{lab_id}")
async def devops_terminal(websocket: WebSocket, lab_id: str):
    await websocket.accept()
    lab = next((lab for lab in devops.load_labs() if lab["id"] == lab_id), None)
    if lab is None or devops.status(lab) != "running":
        await websocket.send_text("\x1b[31mLe lab n'est pas démarré.\x1b[0m\r\n")
        await websocket.close()
        return
    argv = devops.exec_argv(lab, [lab["shell"]], interactive=True)
    await terminal.bridge(websocket, argv)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")
