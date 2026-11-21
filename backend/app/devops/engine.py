"""Moteur Docker des labs : Docker Desktop (ou tout Docker déjà joignable), ou la VM moteur de TDM.

Docker Desktop (WSL2) garde l'hyperviseur Windows actif : VirtualBox perd alors VT-x et les VM Windows
des labs deviennent très lentes. TDM peut donc fournir son propre moteur Docker : une petite VM Linux
VirtualBox (``labs/moteur-docker``) que l'agent Vagrant démarre à la demande, au premier lab Docker.
Les commandes ``docker`` de la plateforme la visent alors par ``DOCKER_HOST=tcp://127.0.0.1:23750``
(l'API n'est redirigée que sur 127.0.0.1) et les ports publiés par les labs sont redirigés vers l'hôte
sous le même numéro.

Choix du moteur (variable ``TDM_DOCKER``) :

- ``auto`` (par défaut) : un Docker déjà joignable s'il y en a un, sinon la VM moteur si l'agent Vagrant
  (avec Vagrant et VirtualBox) est là ; une fois la VM moteur choisie, TDM s'y tient ;
- ``desktop`` : le Docker configuré sur la machine (comportement d'avant) ;
- ``vm`` : toujours la VM moteur.

Montages : avec un Docker distant, un montage d'un dossier de l'hôte (``-v C:\\...:/x``, ``- ./x:/x``)
monterait un dossier vide de la VM. Les labs n'en utilisent pas (vérifié par les tests) : les fichiers
passent par les images (``build``, envoyé au moteur par le client docker) et les volumes nommés.
Le bac à sable Python reste local (ou Docker Desktop) : la VM moteur ne sert qu'aux labs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from .. import config
from . import vagrant

ENGINE_LAB = {"id": "moteur-docker", "vagrant": "tdm:moteur-docker"}
_USER_DOCKER_HOST = os.environ.get("DOCKER_HOST")  # Docker configuré par l'utilisateur avant TDM
_cache: dict[str, tuple[float, Any]] = {}
_vm_selected = False  # la VM moteur a été choisie (démarrée par TDM ou trouvée allumée)


def _cached(key: str, ttl: float, fn: Callable[[], Any]) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = fn()
    _cache[key] = (now, value)
    return value


def reset_cache() -> None:
    global _vm_selected
    _cache.clear()
    _vm_selected = False


def _probe(host: str | None) -> bool:
    if not shutil.which("docker"):
        return False
    env = {k: v for k, v in os.environ.items() if k != "DOCKER_HOST"}
    if host:
        env["DOCKER_HOST"] = host
    try:
        result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True,
                                timeout=8, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def desktop_ready() -> bool:
    """Un Docker déjà configuré sur la machine (Docker Desktop, socket Linux, DOCKER_HOST) répond-il ?"""
    return _cached("desktop", 30, lambda: _probe(_USER_DOCKER_HOST))


def vm_ready() -> bool:
    return _cached("vm", 3, lambda: _probe(config.DOCKER_VM_HOST))


def _agent_info() -> dict[str, Any] | None:
    def fetch():
        try:
            return vagrant.health()
        except vagrant.AgentError:
            return None
    return _cached("agent", 10, fetch)


def vm_possible() -> bool:
    """La VM moteur peut-elle être démarrée ? (client docker, agent Vagrant récent, Vagrant et VirtualBox)"""
    info = _agent_info()
    return bool(shutil.which("docker") and info and info.get("engine") and info.get("vagrant")
                and info.get("virtualbox"))


def _apply(choice: str) -> None:
    """Oriente les commandes docker de la plateforme (et des terminaux) vers le moteur choisi."""
    if choice == "vm":
        os.environ["DOCKER_HOST"] = config.DOCKER_VM_HOST
    elif os.environ.get("DOCKER_HOST") == config.DOCKER_VM_HOST:
        if _USER_DOCKER_HOST:
            os.environ["DOCKER_HOST"] = _USER_DOCKER_HOST
        else:
            os.environ.pop("DOCKER_HOST", None)


def kind() -> str:
    """Moteur utilisé : "desktop", "vm" ou "none" (aucun moteur possible)."""
    global _vm_selected
    mode = config.DOCKER_MODE
    if mode == "desktop":
        choice = "desktop"
    elif mode == "vm" or _vm_selected:
        choice = "vm"
    elif desktop_ready():
        choice = "desktop"
    elif vm_ready():  # VM moteur restée allumée (lancement précédent de TDM)
        _vm_selected = True
        choice = "vm"
    elif vm_possible():
        choice = "vm"
    else:
        choice = "none"
    _apply(choice)
    return choice


def state() -> dict[str, str]:
    """{"engine": desktop|vm|none, "status": ready|starting|stopping|stopped|error|unavailable, "log": ...}"""
    engine = kind()
    if engine == "desktop":
        return {"engine": engine, "status": "ready" if desktop_ready() else "unavailable", "log": ""}
    if engine == "none":
        return {"engine": engine, "status": "unavailable", "log": ""}
    if vm_ready():
        return {"engine": engine, "status": "ready", "log": ""}
    status, log = vagrant.status(ENGINE_LAB)
    if status == "running":  # la VM tourne mais dockerd ne répond pas encore
        status, log = "starting", (log + "\n" if log else "") + "Démarrage de Docker dans la VM…"
    return {"engine": engine, "status": status, "log": log}


def ready() -> bool:
    return state()["status"] == "ready"


def ensure() -> dict[str, str]:
    """Démarre la VM moteur si c'est elle qui sert et qu'elle est arrêtée (ou en pause) ; renvoie l'état."""
    global _vm_selected
    current = state()
    if current["engine"] != "vm" or current["status"] not in ("stopped", "error"):
        return current
    vagrant.start_engine(ENGINE_LAB, lab_ports())
    _vm_selected = True
    _cache.pop("vm", None)
    return {"engine": "vm", "status": "starting", "log": "Moteur Docker en démarrage…"}


def wait_ready(timeout: float = 1800, interval: float = 2,
               should_stop: Callable[[], bool] = lambda: False) -> dict[str, str]:
    """Attend le moteur (le premier démarrage télécharge la box et installe Docker : plusieurs minutes).

    ``should_stop`` interrompt l'attente (lab arrêté, ou lab Windows lancé entre-temps).
    """
    deadline = time.monotonic() + timeout
    current = ensure()
    while current["status"] not in ("ready", "unavailable", "error") and time.monotonic() < deadline:
        time.sleep(interval)
        if should_stop():
            break
        _cache.pop("vm", None)
        current = state()
        if current["status"] == "stopped":  # une mise en pause du moteur vient de se terminer : on relance
            current = ensure()
    return current


# ---------------------------------------------------------------------------
# Ports publiés par les labs : redirigés de l'hôte (127.0.0.1) vers la VM moteur
# ---------------------------------------------------------------------------

def host_ports(spec: Any) -> list[int]:
    """Ports de l'hôte d'une publication docker : "8080:80", "127.0.0.1:8080:80/tcp", "8000-8002:80-82",
    {"published": 8080}. Un port seul ("80", 80) est publié sur un port aléatoire : ignoré."""
    if isinstance(spec, dict):
        spec = str(spec.get("published") or "")
        parts = [spec, ""] if spec else []
    else:
        parts = str(spec).split("/", 1)[0].split(":")
    if len(parts) < 2:
        return []
    published = parts[-2]
    start, _, end = published.partition("-")
    if not start.isdigit() or (end and not end.isdigit()):
        return []
    first, last = int(start), int(end or start)
    return list(range(first, min(last, first + 50) + 1))


def lab_ports() -> list[int]:
    from . import labs  # import tardif : labs importe ce module

    ports: set[int] = set()
    for lab in labs.load_labs():
        if "vagrant" in lab:
            continue
        for spec in lab.get("ports", []):
            ports.update(host_ports(spec))
        if "compose" in lab:
            try:
                data = yaml.safe_load((Path(lab["dir"]) / lab["compose"]).read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            for service in (data.get("services") or {}).values():
                for spec in (service or {}).get("ports") or []:
                    ports.update(host_ports(spec))
    return sorted(p for p in ports if 1024 <= p <= 65535)


if config.DOCKER_MODE == "vm":
    _apply("vm")
