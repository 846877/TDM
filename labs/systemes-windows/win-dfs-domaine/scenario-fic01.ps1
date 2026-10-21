# Mise en situation : SRV-FIC01 partage Compta (avec des documents) et un dossier Commun encore vide.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin, C:\Partages\Commun, C:\Partages\Compta -ItemType Directory -Force | Out-Null
Set-Content C:\Partages\Compta\budget-2025.csv "poste;montant`nachats;125000`nsalaires;480000"
foreach ($s in 'Commun', 'Compta') {
    if (-not (Get-SmbShare -Name $s -ErrorAction SilentlyContinue)) {
        New-SmbShare -Name $s -Path "C:\Partages\$s" -ChangeAccess '*S-1-5-11' | Out-Null
        icacls "C:\Partages\$s" /grant '*S-1-5-11:(OI)(CI)M' | Out-Null
    }
}
