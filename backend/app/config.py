"""Configuration de la plateforme, lue depuis les variables d'environnement."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Application Windows (PyInstaller) : les fichiers embarqués sont décompressés dans sys._MEIPASS.
FROZEN = getattr(sys, "frozen", False)
ROOT_DIR = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parents[2]


def _path_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


CONTENT_DIR = _path_env("TDM_CONTENT_DIR", ROOT_DIR / "content")
LABS_DIR = _path_env("TDM_LABS_DIR", ROOT_DIR / "labs" / "devops")
SYSTEMS_LABS_DIR = _path_env("TDM_SYSTEMS_LABS_DIR", ROOT_DIR / "labs" / "systemes")
# Labs Windows (VM Vagrant livrées avec TDM), rangés dans la catégorie Systèmes & réseaux.
WINDOWS_LABS_DIR = _path_env("TDM_WINDOWS_LABS_DIR", ROOT_DIR / "labs" / "systemes-windows")
CYBER_LABS_DIR = _path_env("TDM_CYBER_LABS_DIR", ROOT_DIR / "labs" / "cyber")
FRONTEND_DIR = ROOT_DIR / "frontend"
# VM du moteur Docker de TDM (voir devops/engine.py), lancée par l'agent Vagrant.
DOCKER_ENGINE_DIR = _path_env("TDM_DOCKER_ENGINE_DIR", ROOT_DIR / "labs" / "moteur-docker")

# Moteur Docker des labs : "auto" (Docker déjà joignable, sinon la VM moteur de TDM), "desktop"
# (Docker Desktop ou tout Docker déjà configuré) ou "vm" (toujours la VM moteur).
DOCKER_MODE = os.environ.get("TDM_DOCKER", "auto").lower()
DOCKER_VM_HOST = f"tcp://127.0.0.1:{os.environ.get('TDM_DOCKER_VM_PORT', '23750')}"



def user_data_dir() -> Path:
    """Dossier des données de l'utilisateur (application Windows) : %LOCALAPPDATA%\\TDM."""
    base = os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share"
    return Path(base) / "TDM"


DATA_DIR = _path_env("TDM_DATA_DIR", user_data_dir() if FROZEN else ROOT_DIR / ".data")
WORKSPACES_DIR = _path_env("TDM_WORKSPACES_DIR", user_data_dir() / "workspaces" if FROZEN else ROOT_DIR / ".workspaces")

# "auto" (docker si disponible, sinon local), "docker" ou "local".
SANDBOX_MODE = os.environ.get("TDM_SANDBOX", "auto").lower()
SANDBOX_IMAGE = os.environ.get("TDM_SANDBOX_IMAGE", "tdm-python-sandbox")
RUN_TIMEOUT = float(os.environ.get("TDM_RUN_TIMEOUT", "10"))
MEMORY_LIMIT_MB = int(os.environ.get("TDM_MEMORY_MB", "256"))


_docker_cache: tuple[float, bool] = (0.0, False)


def docker_available() -> bool:
    """Docker répond-il ? Résultat gardé 30 s, pour voir Docker Desktop démarrer sans relancer TDM."""
    global _docker_cache
    checked_at, value = _docker_cache
    if time.monotonic() - checked_at < 30 and checked_at:
        return value
    value = _probe_docker()
    _docker_cache = (time.monotonic(), value)
    return value


def _probe_docker() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def python_command() -> list[str]:
    """Interpréteur Python utilisé pour le code des élèves en mode local."""
    if FROZEN:
        # L'application embarque la distribution « embeddable » officielle de Python.
        return [str(ROOT_DIR / "python" / "python.exe")]
    return [sys.executable]


def use_docker_sandbox() -> bool:
    if SANDBOX_MODE == "docker":
        return True
    if SANDBOX_MODE == "local":
        return False
    # Le moteur Docker de TDM (VM) sert aux labs seulement : le code Python reste exécuté localement.
    return not docker_is_tdm_vm() and docker_available()


def docker_is_tdm_vm() -> bool:
    """Les commandes docker visent-elles la VM moteur de TDM (DOCKER_HOST posé par devops/engine.py) ?"""
    return os.environ.get("DOCKER_HOST") == DOCKER_VM_HOST


def running_in_container() -> bool:
    return Path("/.dockerenv").exists()
