"""Hyperviseur Windows : le désactiver rend toute sa vitesse à VirtualBox (VM Windows des labs).

Quand l'hyperviseur Windows tourne (Docker Desktop/WSL2, Hyper-V, « Intégrité de la mémoire »),
VirtualBox n'a plus accès à VT-x et passe par lui (mode NEM, tortue verte) : les VM Windows deviennent
très lentes. Si TDM n'utilise pas Docker Desktop (son moteur Docker est alors une VM VirtualBox),
l'interface propose une fois de le désactiver : ``bcdedit /set hypervisorlaunchtype off``, lancé avec
élévation (UAC) seulement après un clic explicite, puis un redémarrage de Windows.
Retour en arrière : ``bcdedit /set hypervisorlaunchtype auto`` (en administrateur), puis redémarrer.
"""

from __future__ import annotations

import subprocess
import sys

from .devops import engine

REVERT_COMMAND = "bcdedit /set hypervisorlaunchtype auto"
# Start-Process -Verb RunAs affiche la demande UAC ; un refus lève une erreur (code de sortie non nul).
DISABLE_SCRIPT = ("$p = Start-Process -FilePath bcdedit.exe -ArgumentList '/set','hypervisorlaunchtype','off' "
                  "-Verb RunAs -WindowStyle Hidden -Wait -PassThru; exit $p.ExitCode")

_present: bool | None = None  # ne change qu'au redémarrage de Windows


def _powershell(script: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def present() -> bool:
    """Win32_ComputerSystem.HypervisorPresent (toujours False hors de Windows)."""
    global _present
    if sys.platform != "win32":
        return False
    if _present is None:
        try:
            result = _powershell("(Get-CimInstance Win32_ComputerSystem).HypervisorPresent")
            _present = result.stdout.strip().lower() == "true"
        except (OSError, subprocess.SubprocessError):
            _present = False
    return _present


def notice() -> dict:
    """Faut-il proposer de désactiver l'hyperviseur ? Seulement sous Windows, s'il est actif et que TDM
    n'utilise pas Docker Desktop (qui en a besoin)."""
    is_present = present()
    docker = engine.kind() if is_present else ""
    return {"show": is_present and docker != "desktop", "present": is_present, "engine": docker,
            "revert": REVERT_COMMAND}


def disable() -> dict:
    """Lance ``bcdedit /set hypervisorlaunchtype off`` avec élévation (demande UAC)."""
    if sys.platform != "win32":
        return {"ok": False, "message": "Réservé à Windows."}
    try:
        result = _powershell(DISABLE_SCRIPT, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "message": f"Impossible de lancer bcdedit : {exc}"}
    if result.returncode != 0:
        return {"ok": False, "message": "Opération annulée ou refusée (demande d'autorisation Windows). "
                                        "Rien n'a été modifié."}
    return {"ok": True, "message": "C'est fait : redémarre Windows pour que VirtualBox retrouve toute sa vitesse. "
                                   f"Pour revenir en arrière (Docker Desktop, WSL2) : « {REVERT_COMMAND} » "
                                   "dans un terminal administrateur, puis redémarre."}
