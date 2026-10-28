"""Labs en machine virtuelle : client de l'agent Vagrant (scripts/vagrant_agent.py).

L'agent tourne sur la machine hôte (là où sont Vagrant et VirtualBox). La plateforme lui demande
de démarrer/arrêter les VM, puis se connecte à la VM en SSH (terminal et vérifications).
"""

from __future__ import annotations

import json
import os
import shlex
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .. import config
from . import windows

_KEYS_DIR = Path(tempfile.gettempdir()) / "tdm-vagrant-keys"


class AgentError(RuntimeError):
    def __init__(self, message: str, reachable: bool = False):
        super().__init__(message)
        self.reachable = reachable  # l'agent a répondu, mais avec une erreur


def agent_url() -> str:
    return os.environ.get("TDM_VAGRANT_AGENT", f"http://{agent_host()}:{os.environ.get('TDM_VAGRANT_AGENT_PORT', '7777')}")


def agent_host() -> str:
    explicit = os.environ.get("TDM_VAGRANT_HOST")
    if explicit:
        return explicit
    return "host.docker.internal" if config.running_in_container() else "127.0.0.1"


def _request(method: str, path: str, params: dict[str, str] | None = None, timeout: float = 120) -> dict[str, Any]:
    url = agent_url() + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": "Bearer " + os.environ.get("TDM_VAGRANT_TOKEN", "")})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("detail", str(exc))
        except ValueError:
            detail = str(exc)
        raise AgentError(f"Agent Vagrant : {detail}", reachable=True) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise AgentError(
            "L'agent Vagrant ne répond pas. Lance-le sur ta machine (start.bat le fait si Vagrant est installé)."
        ) from exc


def health() -> dict[str, Any]:
    return _request("GET", "/health", timeout=2)


def available() -> bool:
    try:
        health()
    except AgentError:
        return False
    return True


def exclusive(name: str) -> list[str]:
    """Met en pause les labs embarqués qui tournent (VM Windows, moteur Docker), sauf ``name``."""
    return _request("POST", "/exclusive", {"lab": name}, timeout=300).get("paused", [])


def start_engine(lab: dict[str, Any], ports: list[int]) -> str:
    """Démarre la VM moteur Docker en lui donnant les ports publiés par les labs."""
    return _request("POST", "/up", {"lab": lab["vagrant"], "ports": ",".join(map(str, ports))})["status"]


def status(lab: dict[str, Any]) -> tuple[str, str]:
    try:
        data = _request("GET", "/status", {"lab": lab["vagrant"]}, timeout=60)
    except AgentError as exc:
        return ("error", str(exc)) if exc.reachable else ("unavailable", "")
    return data.get("status", "stopped"), data.get("log", "")


def start(lab: dict[str, Any]) -> str:
    return _request("POST", "/up", {"lab": lab["vagrant"]})["status"]


def stop(lab: dict[str, Any]) -> str:
    return _request("POST", "/halt", {"lab": lab["vagrant"]})["status"]


def reset(lab: dict[str, Any]) -> str:
    return _request("POST", "/reset", {"lab": lab["vagrant"]})["status"]


def desktops(lab: dict[str, Any]) -> list[dict[str, Any]]:
    """[{"machine": "srv01", "port": 33389}, ...] : VM du lab joignables en Bureau à distance."""
    return _request("GET", "/desktops", {"lab": lab["vagrant"]}, timeout=60).get("desktops", [])


def open_desktop(lab: dict[str, Any], machine: str) -> dict[str, Any]:
    return _request("POST", "/desktop", {"lab": lab["vagrant"], "machine": machine}, timeout=60)


def ssh_argv(lab: dict[str, Any], command: str | None = None, machine: str | None = None) -> list[str]:
    """Commande ``ssh`` vers la VM : interactive si ``command`` est None.

    VM Linux : ``command`` est lancée avec ``sh -c``. VM Windows (``os: windows``) : c'est un extrait
    PowerShell, enveloppé par :func:`windows.check_command` (le shell SSH par défaut y est PowerShell).
    """
    info = _request("GET", "/ssh", {"lab": lab["vagrant"], "machine": machine or lab.get("machine", "")})
    if info.get("key_path") and agent_host() in ("127.0.0.1", "localhost") and Path(info["key_path"]).exists():
        # Même machine que l'agent : la clé de Vagrant a déjà les bons droits (important sous Windows).
        key_path = Path(info["key_path"])
    else:
        _KEYS_DIR.mkdir(mode=0o700, exist_ok=True)
        key_path = _KEYS_DIR / (lab["id"] + (f"-{machine}" if machine else ""))
        key_path.write_text(info["key"], encoding="utf-8")
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    argv = ["ssh", "-i", str(key_path), "-p", str(info["port"]),
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=10", f"{info['user']}@{agent_host()}"]
    if command is None:
        return argv[:1] + ["-t"] + argv[1:]
    if lab.get("os") == "windows":
        return argv + [windows.check_command(command)]
    return argv + ["sh -c " + shlex.quote(command)]
