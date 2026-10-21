# Mise en situation : SRV-RTR01 fait confiance à PC01 pour la gestion à distance (groupe de travail).
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Set-Item WSMan:\localhost\Client\TrustedHosts -Value '192.168.10.101,PC01' -Force
