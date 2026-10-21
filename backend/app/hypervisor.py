"""Hyperviseur Windows : avertissement quand il est actif alors que TDM n'en a pas besoin.

Quand l'hyperviseur Windows tourne (Docker Desktop/WSL2, Hyper-V, « Intégrité de la mémoire »),
VirtualBox n'a plus accès à VT-x et passe par lui (mode NEM, tortue verte) : les VM Windows deviennent
très lentes. Si TDM n'utilise pas Docker Desktop (son moteur Docker est alors une VM VirtualBox),
l'interface l'explique une fois, en texte seulement : TDM ne modifie jamais la configuration de
démarrage de Windows (voir labs/systemes-windows/README.md pour le faire soi-même).
"""

from __future__ import annotations

import subprocess
import sys

from .devops import engine

_present: bool | None = None  # ne change qu'au redémarrage de Windows


def is_windows() -> bool:
    return sys.platform == "win32"


def present() -> bool:
    """Win32_ComputerSystem.HypervisorPresent (toujours False hors de Windows)."""
    global _present
    if not is_windows():
        return False
    if _present is None:
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                     "(Get-CimInstance Win32_ComputerSystem).HypervisorPresent"],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            _present = result.stdout.strip().lower() == "true"
        except (OSError, subprocess.SubprocessError):
            _present = False
    return _present


def notice() -> dict:
    """Faut-il avertir ? Seulement sous Windows, si l'hyperviseur est actif et que TDM n'utilise pas
    Docker Desktop (qui en a besoin)."""
    is_present = present()
    docker = engine.kind() if is_present else ""
    return {"show": is_present and docker != "desktop", "present": is_present, "engine": docker}
