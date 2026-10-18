"""Labs DevOps : chargement des définitions et pilotage des conteneurs Docker.

Chaque lab est un dossier contenant un ``lab.yaml`` (voir ``labs/devops/README.md``).
Le lab tourne soit dans un conteneur (``image`` ou ``build``), soit via docker compose
(``compose`` + ``service``).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .. import config
from ..catalog import LEVELS
from . import vagrant


class LabError(RuntimeError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def load_labs(labs_dir: Path | None = None) -> list[dict[str, Any]]:
    root = labs_dir or config.LABS_DIR
    labs = []
    if not root.is_dir():
        return labs
    for path in sorted(root.glob("*/lab.yaml")):
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        data["id"] = _slug(data.get("id") or path.parent.name)
        data["dir"] = str(path.parent)
        data.setdefault("title", path.parent.name)
        data.setdefault("level", "debutant")
        if data["level"] not in LEVELS:
            data["level"] = "debutant"
        if not data.get("description"):
            readme = path.parent / "README.md"
            data["description"] = readme.read_text(encoding="utf-8") if readme.exists() else ""
        if not any(k in data for k in ("image", "build", "compose", "vagrant")):
            if (path.parent / "Dockerfile").exists():
                data["build"] = "."
            elif (path.parent / "docker-compose.yml").exists():
                data["compose"] = "docker-compose.yml"
            else:
                data["image"] = "ubuntu:24.04"
        data.setdefault("shell", "bash")
        data.setdefault("exercises", [])
        for index, exercise in enumerate(data["exercises"], start=1):
            exercise.setdefault("id", f"ex{index}")
        labs.append(data)
    order = {level: i for i, level in enumerate(LEVELS)}
    return sorted(labs, key=lambda lab: (order[lab["level"]], lab.get("order", 999), lab["id"]))


def public(lab: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": lab["id"],
        "title": lab["title"],
        "level": lab["level"],
        "tags": lab.get("tags", []),
        "summary": lab.get("summary", ""),
        "description": lab["description"],
        "ports": lab.get("ports", []),
        "kind": "vagrant" if "vagrant" in lab else "docker",
        "exercises": [
            {k: e.get(k) for k in ("id", "title", "description", "hint") if e.get(k) is not None}
            for e in lab["exercises"]
        ],
    }


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

def _require_docker() -> None:
    if not config.docker_available():
        raise LabError("Docker n'est pas disponible sur cette machine : il est nécessaire pour lancer les labs DevOps.")


def _run(cmd: list[str], timeout: float = 600, cwd: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as exc:
        raise LabError(f"Commande trop longue : {' '.join(cmd)}") from exc


def container_name(lab: dict[str, Any]) -> str:
    return f"tdm-lab-{lab['id']}"


def _compose_base(lab: dict[str, Any]) -> list[str]:
    return ["docker", "compose", "-p", container_name(lab), "-f", str(Path(lab["dir"]) / lab["compose"])]


def status(lab: dict[str, Any]) -> str:
    return status_with_log(lab)[0]


def status_with_log(lab: dict[str, Any]) -> tuple[str, str]:
    if "vagrant" in lab:
        return vagrant.status(lab)
    return _docker_status(lab), ""


def _docker_status(lab: dict[str, Any]) -> str:
    if not config.docker_available():
        return "unavailable"
    if "compose" in lab:
        result = _run(_compose_base(lab) + ["ps", "--status", "running", "-q", lab.get("service", "")], timeout=20)
        return "running" if result.returncode == 0 and result.stdout.strip() else "stopped"
    result = _run(["docker", "inspect", "-f", "{{.State.Running}}", container_name(lab)], timeout=20)
    return "running" if result.stdout.strip() == "true" else "stopped"


def start(lab: dict[str, Any]) -> str:
    if "vagrant" in lab:
        return _agent(vagrant.start, lab)
    _require_docker()
    if status(lab) == "running":
        return "running"
    if "compose" in lab:
        result = _run(_compose_base(lab) + ["up", "-d", "--build"], cwd=lab["dir"])
        if result.returncode != 0:
            raise LabError(result.stderr.strip()[-2000:])
        return "running"

    image = lab.get("image")
    if "build" in lab:
        image = f"tdm-lab-{lab['id']}:latest"
        result = _run(["docker", "build", "-t", image, str(Path(lab["dir"]) / lab["build"])])
        if result.returncode != 0:
            raise LabError("Échec de la construction de l'image :\n" + result.stderr.strip()[-2000:])
    _run(["docker", "rm", "-f", container_name(lab)], timeout=30)
    cmd = ["docker", "run", "-d", "--name", container_name(lab), "--hostname", lab["id"][:63],
           "--label", "tdm.lab=" + lab["id"]]
    for port in lab.get("ports", []):
        cmd += ["-p", str(port)]
    if lab.get("privileged"):
        cmd.append("--privileged")
    if lab.get("entrypoint") is not None:
        cmd.append(f"--entrypoint={lab['entrypoint']}")
    cmd.append(image)
    command = lab.get("command", ["sleep", "infinity"])
    cmd += command if isinstance(command, list) else ["sh", "-c", command]
    result = _run(cmd)
    if result.returncode != 0:
        raise LabError(result.stderr.strip()[-2000:])
    setup = lab.get("setup")
    if setup:
        _run(["docker", "exec", container_name(lab), "sh", "-c", setup], timeout=300)
    return "running"


def stop(lab: dict[str, Any]) -> str:
    if "vagrant" in lab:
        return _agent(vagrant.stop, lab)
    _require_docker()
    if "compose" in lab:
        _run(_compose_base(lab) + ["down", "-v"], cwd=lab["dir"])
    else:
        _run(["docker", "rm", "-f", container_name(lab)], timeout=60)
    return "stopped"


def reset(lab: dict[str, Any]) -> str:
    if "vagrant" in lab:
        return _agent(vagrant.reset, lab)
    stop(lab)
    return start(lab)


def _agent(fn, *args):
    try:
        return fn(*args)
    except vagrant.AgentError as exc:
        raise LabError(str(exc)) from exc


def terminal_argv(lab: dict[str, Any]) -> list[str]:
    if "vagrant" in lab:
        return _agent(vagrant.ssh_argv, lab)
    return exec_argv(lab, [lab["shell"]], interactive=True)


def _check_argv(lab: dict[str, Any], item: dict[str, Any]) -> list[str]:
    if "vagrant" in lab:
        return _agent(vagrant.ssh_argv, lab, item["run"], item.get("machine"))
    return exec_argv(lab, ["sh", "-c", item["run"]], interactive=False)


def exec_argv(lab: dict[str, Any], command: list[str], interactive: bool) -> list[str]:
    flags = ["-it"] if interactive else []
    workdir = lab.get("workdir")
    if workdir:
        flags += ["-w", workdir]
    user = lab.get("user")
    if user:
        flags += ["-u", user]
    if "compose" in lab:
        if not interactive:
            flags = ["-T"] + flags
        return _compose_base(lab) + ["exec"] + [f for f in flags if f != "-it"] + [lab["service"]] + command
    return ["docker", "exec"] + flags + [container_name(lab)] + command


def check(lab: dict[str, Any], exercise_id: str) -> dict[str, Any]:
    if "vagrant" not in lab:
        _require_docker()
    exercise = next((e for e in lab["exercises"] if e["id"] == exercise_id), None)
    if exercise is None:
        raise LabError("Exercice inconnu")
    if status(lab) != "running":
        raise LabError("Le lab n'est pas démarré.")
    checks = exercise.get("checks") or [{"desc": exercise.get("title", exercise_id), "run": exercise["check"]}]
    results = []
    for item in checks:
        result = _run(_check_argv(lab, item), timeout=item.get("timeout", 60))
        ok = result.returncode == 0
        message = "" if ok else (item.get("hint") or (result.stdout + result.stderr).strip()[-500:])
        results.append({"name": item.get("desc", "vérification"), "passed": ok, "message": message})
    passed = sum(r["passed"] for r in results)
    return {"success": passed == len(results), "passed": passed, "total": len(results), "results": results}
