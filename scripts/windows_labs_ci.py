#!/usr/bin/env python3
"""Validation des labs Windows (labs/systemes-windows), utilisée par la CI Windows.

    python scripts/windows_labs_ci.py static [--commands]   # analyse de tous les scripts PowerShell
    python scripts/windows_labs_ci.py list                  # labs qui ont des exercices « ci: true » (JSON)
    python scripts/windows_labs_ci.py run --lab <id>        # rejoue ces exercices sur la machine locale

``static`` analyse (parseur PowerShell) chaque ``run`` et ``solution`` des exercices, les ``scenario*.ps1``
des labs et les scripts de ``_commun``. Avec ``--commands`` (Windows avec les outils RSAT), chaque
commande citée doit aussi exister (``Get-Command``) : une faute de frappe dans une cmdlet est ainsi
repérée sans VM, même pour les exercices Active Directory.

``run`` exécute le ``scenario.ps1`` du lab puis, pour chaque exercice marqué ``ci: true`` et dans
l'ordre : les vérifications (au moins une doit échouer), la ``solution``, de nouveau les vérifications
(toutes doivent réussir). Les vérifications passent par la même enveloppe que sur la plateforme
(``backend/app/devops/windows.py``). À lancer en administrateur, sur une machine jetable (runner CI).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.devops import labs as labs_mod  # noqa: E402
from app.devops import windows  # noqa: E402

# Commandes qui n'existent pas sur le runner (Windows Server) mais bien dans les VM du lab.
ALWAYS_KNOWN = {"winget", "Get-WindowsUpdateLog", "manage-bde", "Get-BitLockerVolume", "Enable-BitLocker",
                "Add-BitLockerKeyProtector", "Suspend-BitLocker", "Resume-BitLocker", "Backup-BitLockerKeyProtector",
                "Checkpoint-Computer", "Get-ComputerRestorePoint", "Enable-ComputerRestore",
                "Disable-ComputerRestore", "Restore-Computer", "rstrui", "wsreset", "sfc", "DISM", "dism",
                # outils des contrôleurs de domaine (présents seulement après promotion ou avec certains RSAT)
                "redircmp", "redirusr", "nltest", "dcdiag", "dsacls",
                # Microsoft Defender (module absent si Defender est retiré de l'image du runner)
                "Get-MpPreference", "Set-MpPreference", "Add-MpPreference", "Remove-MpPreference",
                "Get-MpComputerStatus", "Update-MpSignature", "Start-MpScan", "Get-MpThreatDetection"}

PARSE_SCRIPT = r"""
param([string]$InFile, [string]$OutFile)
$items = Get-Content -Raw -Encoding UTF8 $InFile | ConvertFrom-Json
$result = foreach ($item in $items) {
  $tokens = $null; $errors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseInput([string]$item.code, [ref]$tokens, [ref]$errors)
  $commands = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true) |
    ForEach-Object { $_.GetCommandName() } | Where-Object { $_ })
  $functions = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) |
    ForEach-Object { $_.Name })
  [pscustomobject]@{ name = $item.name; errors = @($errors | ForEach-Object { $_.Message + ' (ligne ' + $_.Extent.StartLineNumber + ')' });
                     commands = $commands; functions = $functions }
}
ConvertTo-Json -InputObject @($result) -Depth 5 | Set-Content -Encoding UTF8 $OutFile
"""

COMMANDS_SCRIPT = r"""
param([string]$InFile, [string]$OutFile)
$names = Get-Content -Raw -Encoding UTF8 $InFile | ConvertFrom-Json
$missing = @($names | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
ConvertTo-Json -InputObject $missing | Set-Content -Encoding UTF8 $OutFile
"""


def powershell() -> str:
    for candidate in (os.environ.get("TDM_POWERSHELL"), "powershell", "pwsh"):
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    raise SystemExit("PowerShell introuvable (powershell.exe, pwsh ou TDM_POWERSHELL).")


def ps_env() -> dict:
    """Environnement des sous-processus PowerShell.

    Lancé depuis pwsh (shell par défaut des runners GitHub), Windows PowerShell 5.1 hérite d'un PSModulePath
    qui pointe d'abord vers les modules de PowerShell 7 : Microsoft.PowerShell.Security/Utility version 7
    refusent alors de se charger et Get-Acl, Get-FileHash, Get-ExecutionPolicy... deviennent « inconnus ».
    Sans PSModulePath, powershell.exe reconstruit son chemin par défaut.
    """
    env = dict(os.environ)  # sous Windows, les noms y sont en majuscules (PSMODULEPATH)
    if powershell().replace("\\", "/").rsplit("/", 1)[-1].lower() == "powershell.exe":
        env = {k: v for k, v in env.items() if k.lower() != "psmodulepath"}
    return env


def windows_labs() -> list[dict]:
    return [lab for lab in labs_mod.load_labs() if lab.get("os") == "windows"]


def _run_ps_file(script: str, *args: str, timeout: float = 600) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "script.ps1"
        path.write_text(script, encoding="utf-8-sig")
        subprocess.run([powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(path), *args], check=True, timeout=timeout, env=ps_env())


def _powershell_json(script: str, payload) -> object:
    with tempfile.TemporaryDirectory() as tmp:
        infile, outfile = Path(tmp) / "in.json", Path(tmp) / "out.json"
        infile.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _run_ps_file(script, str(infile), str(outfile))
        return json.loads(outfile.read_text(encoding="utf-8-sig"))


def snippets(lab: dict) -> list[dict]:
    """Tous les morceaux de PowerShell d'un lab : vérifications, solutions et scénarios."""
    items = []
    for exercise in lab["exercises"]:
        for i, check in enumerate(exercise.get("checks") or []):
            items.append({"name": f"{lab['id']}/{exercise['id']}/check{i + 1}", "code": check["run"]})
        if exercise.get("solution"):
            items.append({"name": f"{lab['id']}/{exercise['id']}/solution", "code": exercise["solution"]})
    for script in sorted(Path(lab["dir"]).glob("*.ps1")):
        items.append({"name": f"{lab['id']}/{script.name}", "code": script.read_text(encoding="utf-8-sig")})
    return items


def static(check_commands: bool) -> int:
    items, extra = [], set(ALWAYS_KNOWN)
    for lab in windows_labs():
        items += snippets(lab)
        extra.update(lab.get("extra_commands") or [])
    for script in sorted((config.WINDOWS_LABS_DIR / "_commun").rglob("*.ps1")):
        items.append({"name": f"_commun/{script.relative_to(config.WINDOWS_LABS_DIR / '_commun').as_posix()}",
                      "code": script.read_text(encoding="utf-8-sig")})
    parsed = _powershell_json(PARSE_SCRIPT, items)
    failures = 0
    defined = {f.lower() for p in parsed for f in (p["functions"] or [])}
    for p in parsed:
        for error in p["errors"] or []:
            print(f"ERREUR de syntaxe {p['name']} : {error}")
            failures += 1
    print(f"{len(parsed)} scripts PowerShell analysés, {failures} erreur(s) de syntaxe.")
    if check_commands:
        known = {e.lower() for e in extra} | defined
        names = sorted({c for p in parsed for c in (p["commands"] or [])
                        if c.lower() not in known and not any(ch in c for ch in "\\/$")})
        missing = _powershell_json(COMMANDS_SCRIPT, names) or []
        if isinstance(missing, str):
            missing = [missing]
        for name in missing:
            where = [p["name"] for p in parsed if name in (p["commands"] or [])]
            print(f"COMMANDE INCONNUE {name} : {', '.join(where[:5])}")
        failures += len(missing)
        print(f"{len(names)} commandes vérifiées, {len(missing)} inconnue(s).")
    return 1 if failures else 0


def ci_labs() -> list[str]:
    return [lab["id"] for lab in windows_labs() if any(e.get("ci") for e in lab["exercises"])]


def _ps(code: str, timeout: float) -> tuple[int, str]:
    try:
        result = subprocess.run(windows.encoded_argv(code, powershell()), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, env=ps_env())
    except subprocess.TimeoutExpired:
        return 124, "délai dépassé"
    return result.returncode, (result.stdout + result.stderr).strip()


SOLUTION_WRAPPER = r"""$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
  $__code = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{code}'))
  & ([ScriptBlock]::Create($__code)) | Out-Host
} catch {
  'Erreur : ' + $_.Exception.Message + ' (ligne ' + $_.InvocationInfo.ScriptLineNumber + ')'
  exit 1
}
exit 0
"""


def run_solution(code: str) -> tuple[int, str]:
    import base64

    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    return _ps(SOLUTION_WRAPPER.replace("{code}", encoded), timeout=1800)


def run_checks(exercise: dict) -> list[tuple[str, int, str]]:
    return [(c["desc"], *_ps(windows.wrap_check(c["run"]), timeout=c.get("timeout", 120)))
            for c in exercise["checks"]]


def run_lab(lab_id: str) -> int:
    lab = next((lab for lab in windows_labs() if lab["id"] == lab_id), None)
    if lab is None:
        raise SystemExit(f"lab Windows inconnu : {lab_id}")
    scenario = Path(lab["dir"]) / "scenario.ps1"
    if scenario.exists():
        print(f"== {lab_id} : scenario.ps1", flush=True)
        subprocess.run([powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(scenario)], check=True, timeout=1800, env=ps_env())
    errors = []
    for exercise in lab["exercises"]:
        if not exercise.get("ci"):
            continue
        name = f"{lab_id}/{exercise['id']}"
        start = time.monotonic()
        before = run_checks(exercise)
        if all(code == 0 for _, code, _ in before):
            errors.append(f"{name} : les vérifications passent AVANT la solution")
        code, output = run_solution(exercise["solution"])
        if code != 0:
            errors.append(f"{name} : la solution échoue\n{output[-1500:]}")
        after = run_checks(exercise)
        for desc, rc, out in after:
            if rc != 0:
                errors.append(f"{name} : « {desc} » échoue APRÈS la solution\n{out[-800:]}")
        status = "OK" if not any(e.startswith(name + " ") for e in errors) else "ÉCHEC"
        print(f"{status:5} {name} ({time.monotonic() - start:.0f} s ; avant : "
              f"{sum(rc == 0 for _, rc, _ in before)}/{len(before)} ; après : "
              f"{sum(rc == 0 for _, rc, _ in after)}/{len(after)})", flush=True)
    for error in errors:
        print("::error::" + error.replace("\n", "%0A") if os.environ.get("GITHUB_ACTIONS") else "ERREUR " + error)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    st = sub.add_parser("static")
    st.add_argument("--commands", action="store_true", help="vérifie aussi que chaque commande existe")
    sub.add_parser("list")
    rn = sub.add_parser("run")
    rn.add_argument("--lab", required=True)
    args = parser.parse_args()
    if args.action == "static":
        return static(args.commands)
    if args.action == "list":
        print(json.dumps(ci_labs()))
        return 0
    return run_lab(args.lab)


if __name__ == "__main__":
    sys.exit(main())
