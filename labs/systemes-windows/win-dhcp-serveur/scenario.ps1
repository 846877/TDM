# Mise en situation : contrôleur de domaine sans rôle DHCP ; plan d'adressage déposé dans C:\Admin.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Set-Content C:\Admin\plan-adressage.txt -Encoding UTF8 -Value @(
    'Réseau du siège : 192.168.10.0/24',
    '  .1 à .99     serveurs et équipements à adresse fixe (SRV-DC01 = .10)',
    '  .100 à .109  imprimantes (adresses fixes, à exclure du DHCP)',
    '  .110 à .199  postes en DHCP',
    '  .254         passerelle (pare-feu)',
    'DNS : 192.168.10.10, domaine durand.lan'
)
