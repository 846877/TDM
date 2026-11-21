# Mise en situation : un serveur neuf, adresse IP fixe mais aucun serveur DNS sur la carte LAN.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Set-DnsClientServerAddress -InterfaceAlias LAN -ResetServerAddresses
Set-Content C:\Admin\LISEZMOI.txt @(
    'SRV-DC01 : futur contrôleur du domaine durand.lan (NetBIOS DURAND).',
    'Mot de passe de restauration des services d''annuaire (DSRM) imposé : Azerty123!',
    'Plan IP : 192.168.10.0/24, ce serveur en .10.'
) -Encoding UTF8
