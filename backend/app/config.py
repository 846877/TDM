"""Configuration de la plateforme, lue depuis les variables d'environnement."""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _path_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


CONTENT_DIR = _path_env("TDM_CONTENT_DIR", ROOT_DIR / "content")
LABS_DIR = _path_env("TDM_LABS_DIR", ROOT_DIR / "labs" / "devops")
FRONTEND_DIR = ROOT_DIR / "frontend"
WORKSPACES_DIR = _path_env("TDM_WORKSPACES_DIR", ROOT_DIR / ".workspaces")

# "auto" (docker si disponible, sinon local), "docker" ou "local".
SANDBOX_MODE = os.environ.get("TDM_SANDBOX", "auto").lower()
SANDBOX_IMAGE = os.environ.get("TDM_SANDBOX_IMAGE", "tdm-python-sandbox")
RUN_TIMEOUT = float(os.environ.get("TDM_RUN_TIMEOUT", "10"))
MEMORY_LIMIT_MB = int(os.environ.get("TDM_MEMORY_MB", "256"))


@lru_cache(maxsize=1)
def docker_available() -> bool:
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


def use_docker_sandbox() -> bool:
    if SANDBOX_MODE == "docker":
        return True
    if SANDBOX_MODE == "local":
        return False
    return docker_available()
