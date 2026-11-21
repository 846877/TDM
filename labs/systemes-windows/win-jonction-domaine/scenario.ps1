# Mise en situation côté poste : PC01 en groupe de travail, adresse fixe, aucun DNS d'entreprise.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Set-DnsClientServerAddress -InterfaceAlias LAN -ResetServerAddresses
