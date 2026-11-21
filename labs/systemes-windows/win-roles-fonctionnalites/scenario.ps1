# Mise en situation : le prestataire a installé un client TFTP « pour un test » et l'a oublié.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
if (-not (Get-WindowsFeature TFTP-Client).Installed) { Install-WindowsFeature TFTP-Client | Out-Null }
