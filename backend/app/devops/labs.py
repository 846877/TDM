"""Labs DevOps : chargement des définitions et pilotage des conteneurs Docker.

Chaque lab est un dossier contenant un ``lab.yaml`` (voir ``labs/devops/README.md``).
Le lab tourne soit dans un conteneur (``image`` ou ``build``), soit via docker compose
(``compose`` + ``service``), soit dans des VM Vagrant (``vagrant``).

Les labs Windows (``labs/systemes-windows``, voir son README) sont des VM Vagrant livrées avec TDM :
``vagrant: bundled`` y devient ``tdm:<dossier>``, que l'agent Vagrant lance depuis une copie persistante.
"""

from __future__ import annotations

import copy
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

import yaml

from .. import config
from ..catalog import LEVELS
from . import engine, vagrant


class LabError(RuntimeError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


LAB_CATEGORIES = ("devops", "systemes")
BUNDLED_PREFIX = "tdm:"  # lab Vagrant embarqué (cf. scripts/vagrant_agent.py)


def load_labs(labs_dir: Path | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Labs DevOps (``labs/devops``) et labs Systèmes & réseaux (``labs/systemes``).

    ``category`` filtre sur l'une des deux catégories ; ``labs_dir`` charge un seul dossier.
    """
    if labs_dir is not None:
        sources = [(labs_dir, "devops", {})]
    else:
        sources = [(config.LABS_DIR, "devops", {}), (config.SYSTEMS_LABS_DIR, "systemes", {}),
                   (config.WINDOWS_LABS_DIR, "systemes", {"os_name": "windows", "bundled": True})]
    labs = []
    for root, default_category, defaults in sources:
        if root.is_dir():
            labs += _load_dir(root, default_category, **defaults)
    if category:
        labs = [lab for lab in labs if lab["category"] == category]
    order = {level: i for i, level in enumerate(LEVELS)}
    return sorted(labs, key=lambda lab: (order[lab["level"]], lab.get("order", 999), lab["id"]))


# lab.yaml déjà lus : chemin -> ((mtime, taille), contenu). L'analyse YAML de la centaine de labs prend
# plusieurs secondes sous Windows ; elle n'est refaite que pour les fichiers modifiés.
_yaml_cache: dict[Path, tuple[tuple[int, int], Any]] = {}


def _read_yaml(path: Path) -> dict[str, Any]:
    stat = path.stat()
    key = (stat.st_mtime_ns, stat.st_size)
    hit = _yaml_cache.get(path)
    if hit is None or hit[0] != key:
        with path.open(encoding="utf-8") as fh:
            hit = (key, yaml.safe_load(fh) or {})
        _yaml_cache[path] = hit
    return copy.deepcopy(hit[1])  # les appelants complètent le dictionnaire : jamais le cache lui-même


def _load_dir(root: Path, default_category: str, os_name: str = "linux", bundled: bool = False) -> list[dict[str, Any]]:
    labs = []
    for path in sorted(root.glob("*/lab.yaml")):
        data = _read_yaml(path)
        if bundled and data.get("vagrant", "bundled") == "bundled" and (path.parent / "Vagrantfile").exists():
            data["vagrant"] = BUNDLED_PREFIX + path.parent.name
        data["id"] = _slug(data.get("id") or path.parent.name)
        data["category"] = default_category
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
        data.setdefault("os", os_name)
        data.setdefault("shell", "powershell" if data["os"] == "windows" else "bash")
        data.setdefault("exercises", [])
        for index, exercise in enumerate(data["exercises"], start=1):
            exercise.setdefault("id", f"ex{index}")
        labs.append(data)
    return labs


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
        "category": lab["category"],
        "os": lab.get("os", "linux"),
        "cours": lab.get("cours", ""),
        "docs": lab.get("docs", []),
        "exercises": [
            {k: e.get(k) for k in ("id", "title", "description", "hint", "cours", "docs") if e.get(k) is not None}
            for e in lab["exercises"]
        ],
    }


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

def _no_engine_message(current: dict[str, str]) -> str:
    if current["engine"] == "desktop":
        return ("Docker ne répond pas : lance Docker Desktop, ou mets TDM_DOCKER=auto pour utiliser le moteur "
                "Docker de TDM (une petite VM VirtualBox).")
    return ("Aucun moteur Docker : installe VirtualBox et Vagrant (TDM démarre alors son propre moteur Docker, "
            "une petite VM) ou Docker Desktop.")


def _require_docker() -> None:
    current = engine.state()
    if current["status"] == "unavailable":
        raise LabError(_no_engine_message(current))
    if current["status"] != "ready":
        raise LabError("Le moteur Docker démarre encore : patiente un peu puis réessaie.")


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
    return _docker_status(lab)


# Labs Docker lancés pendant que la VM moteur démarre : id -> {"thread", "error", "cancel"}.
_pending: dict[str, dict[str, Any]] = {}


def _docker_status(lab: dict[str, Any]) -> tuple[str, str]:
    pending = _pending.get(lab["id"])
    if pending and pending["thread"].is_alive():
        current = engine.state()
        if current["status"] == "ready":
            return "starting", "Moteur Docker prêt : lancement du lab (construction de l'image au premier lancement)…"
        return "starting", ("Moteur Docker en démarrage… (le tout premier lancement télécharge la VM moteur "
                            "et installe Docker : quelques minutes)\n" + current.get("log", "")).strip()
    if pending and pending["error"]:
        return "error", pending["error"]
    current = engine.state()
    if current["status"] == "unavailable":
        return "unavailable", ""
    if current["status"] != "ready":
        return "stopped", ""  # moteur en pause ou arrêté : il redémarrera au lancement du lab
    if "compose" in lab:
        result = _run(_compose_base(lab) + ["ps", "--status", "running", "-q", lab.get("service", "")], timeout=20)
        return ("running" if result.returncode == 0 and result.stdout.strip() else "stopped"), ""
    result = _run(["docker", "inspect", "-f", "{{.State.Running}}", container_name(lab)], timeout=20)
    return ("running" if result.stdout.strip() == "true" else "stopped"), ""


def start(lab: dict[str, Any]) -> str:
    return launch(lab)["status"]


def launch(lab: dict[str, Any]) -> dict[str, Any]:
    """Démarre un lab ; ``notices`` dit ce qui a été arrêté ou mis en pause pour lui faire de la place.

    Les labs Windows embarqués et les labs Docker ne tournent jamais en même temps (ni deux labs Windows) :
    la mémoire ne suffirait pas.
    """
    if "vagrant" in lab:
        notices = _make_room_for_vm(lab) if _exclusive(lab) else []
        return {"status": _agent(vagrant.start, lab), "notices": notices}
    pending = _pending.get(lab["id"])
    if pending and pending["thread"].is_alive():
        return {"status": "starting", "notices": []}
    notices = _make_room_for_docker()
    current = engine.state()
    if current["status"] == "unavailable":
        raise LabError(_no_engine_message(current))
    if current["status"] == "ready":
        return {"status": _docker_start(lab), "notices": notices}
    _agent(engine.ensure)  # VM moteur arrêtée ou en pause : le lab démarrera dès qu'elle sera prête
    _start_when_ready(lab)
    return {"status": "starting", "notices": notices}


def _start_when_ready(lab: dict[str, Any]) -> None:
    entry: dict[str, Any] = {"error": "", "cancel": False}

    def run() -> None:
        try:
            current = engine.wait_ready(should_stop=lambda: entry["cancel"])
            if entry["cancel"]:
                return
            if current["status"] != "ready":
                entry["error"] = ("Le moteur Docker n'a pas démarré.\n" + current.get("log", "")).strip()
                return
            _docker_start(lab)
        except (LabError, vagrant.AgentError) as exc:
            entry["error"] = str(exc)

    entry["thread"] = threading.Thread(target=run, daemon=True)
    _pending[lab["id"]] = entry
    entry["thread"].start()


def _docker_start(lab: dict[str, Any]) -> str:
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
    pending = _pending.pop(lab["id"], None)
    if pending:
        pending["cancel"] = True
    if not engine.ready():
        return "stopped"  # moteur arrêté ou en pause : rien ne tourne (et on ne le démarre pas pour ça)
    if "compose" in lab:
        _run(_compose_base(lab) + ["down", "-v"], cwd=lab["dir"])
    else:
        _run(["docker", "rm", "-f", container_name(lab)], timeout=60)
    return "stopped"


def reset(lab: dict[str, Any]) -> str:
    return relaunch(lab)["status"]


def relaunch(lab: dict[str, Any]) -> dict[str, Any]:
    if "vagrant" in lab:
        notices = _make_room_for_vm(lab) if _exclusive(lab) else []
        return {"status": _agent(vagrant.reset, lab), "notices": notices}
    stop(lab)
    return launch(lab)


# ---------------------------------------------------------------------------
# Une seule famille de labs à la fois : labs Docker ou un lab Windows
# ---------------------------------------------------------------------------

def _exclusive(lab: dict[str, Any]) -> bool:
    """Lab Windows embarqué : il prend toute la place (VM gourmandes)."""
    return lab.get("os") == "windows" and str(lab.get("vagrant", "")).startswith(BUNDLED_PREFIX)


def stop_docker_labs() -> list[str]:
    """Arrête (``docker stop``) les conteneurs des labs Docker ; renvoie les identifiants des labs arrêtés.

    Ne démarre jamais le moteur : s'il est arrêté ou en pause, aucun lab Docker ne tourne.
    """
    if not engine.ready():
        return []
    result = _run(["docker", "ps", "--filter", "name=^tdm-lab-", "--format",
                   '{{.Names}}\t{{.Label "com.docker.compose.project"}}'], timeout=30)
    if result.returncode != 0:
        return []
    names, lab_ids = [], []
    for line in result.stdout.splitlines():
        name, _, project = line.strip().partition("\t")
        if not name.startswith("tdm-lab-"):
            continue
        names.append(name)
        lab_id = (project or name).removeprefix("tdm-lab-")
        if lab_id not in lab_ids:
            lab_ids.append(lab_id)
    if names:
        _run(["docker", "stop", *names], timeout=180)
    return lab_ids


def _make_room_for_vm(lab: dict[str, Any]) -> list[str]:
    for pending in _pending.values():
        pending["cancel"] = True  # un lab Docker en attente du moteur ne doit pas le rallumer
    titles = {other["id"]: other["title"] for other in load_labs()}
    notices = [f"Le lab Docker « {titles.get(lab_id, lab_id)} » a été arrêté pour libérer la mémoire."
               for lab_id in stop_docker_labs()]
    return notices + _paused_notices(_agent(vagrant.exclusive, lab["vagrant"]))


def _make_room_for_docker() -> list[str]:
    try:
        paused = vagrant.exclusive(engine.ENGINE_LAB["vagrant"])
    except vagrant.AgentError:
        return []  # pas d'agent Vagrant (Docker Desktop seul) : aucune VM à mettre en pause
    return _paused_notices(paused)


def _paused_notices(paused: list[str]) -> list[str]:
    titles = {lab["vagrant"]: lab["title"] for lab in load_labs() if "vagrant" in lab}
    notices = []
    for name in paused:
        if name == engine.ENGINE_LAB["vagrant"]:
            notices.append("Le moteur Docker a été mis en pause pour libérer la mémoire "
                           "(il reprendra au prochain lab Docker).")
        else:
            notices.append(f"Le lab Windows « {titles.get(name, name)} » a été mis en pause pour libérer la mémoire.")
    return notices


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
