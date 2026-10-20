"""Labs Windows : exécution des vérifications PowerShell (voir ``labs/systemes-windows/README.md``).

Une vérification (``run``) est un extrait PowerShell exécuté dans la VM Windows (Windows PowerShell 5.1,
par SSH). La plateforme l'enveloppe pour obtenir un verdict clair :

1. une erreur (exception, ou erreur d'une cmdlet : ``$ErrorActionPreference = 'Stop'``) -> échec ;
2. ``exit <n>`` -> le code ``n`` décide (0 = réussite) ;
3. aucune valeur produite -> échec (évite qu'un filtre vide passe pour une réussite) ;
4. la dernière valeur produite est un booléen -> elle décide ;
5. sinon, ``$LASTEXITCODE`` non nul (dernière commande native : netsh, icacls...) -> échec ;
6. sinon, la dernière valeur est évaluée comme un booléen PowerShell ($null, 0, '' -> échec).
"""

from __future__ import annotations

import base64

# Script exécuté par powershell.exe ; {code} est remplacé par l'extrait encodé en base64 (UTF-8).
_WRAPPER = r"""$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$__ok = $false
try {
  $__code = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{code}'))
  $global:LASTEXITCODE = 0
  $__out = @(& ([ScriptBlock]::Create($__code)))
  if ($__out.Count -eq 0) {
    'Aucun résultat : la vérification ne produit rien.'
  } else {
    $__last = $__out[-1]
    if ($__last -is [bool]) { $__ok = $__last }
    elseif ($global:LASTEXITCODE -ne 0) { "Code de sortie : $global:LASTEXITCODE" }
    else { $__ok = [bool]$__last }
    if (-not $__ok) { 'Résultat : ' + (($__out | Select-Object -Last 5 | Out-String).Trim()) }
  }
} catch {
  'Erreur : ' + $_.Exception.Message
}
if ($__ok) { exit 0 } else { exit 1 }
"""


def wrap_check(code: str) -> str:
    """Script PowerShell complet qui exécute ``code`` et sort avec 0 (réussite) ou 1 (échec)."""
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    return _WRAPPER.replace("{code}", encoded)


def encoded_command(script: str) -> str:
    """Ligne de commande ``powershell.exe -EncodedCommand`` (le script n'a ainsi aucun souci de guillemets)."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return f"powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {encoded}"


def check_command(code: str) -> str:
    """Commande à lancer dans la VM (par SSH) pour la vérification ``code``."""
    return encoded_command(wrap_check(code))


def encoded_argv(script: str, exe: str = "powershell.exe") -> list[str]:
    """Même chose sous forme de liste d'arguments, pour un PowerShell local (CI, tests)."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded]
