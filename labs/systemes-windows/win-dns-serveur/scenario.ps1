# Mise en situation : rôle DNS installé (hors domaine, zones stockées dans des fichiers), une zone obsolète
# héritée de l'ancien site et une zone « outils.lan » avec un enregistrement faux.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
if (-not (Get-WindowsFeature DNS).Installed) { Install-WindowsFeature DNS -IncludeManagementTools | Out-Null }
Start-Service DNS
foreach ($zone in 'ancien-site.lan', 'outils.lan') {
    if (-not (Get-DnsServerZone -Name $zone -ErrorAction SilentlyContinue)) {
        Add-DnsServerPrimaryZone -Name $zone -ZoneFile "$zone.dns"
    }
}
foreach ($r in @(@('ancien-site.lan', 'srv-old', '192.168.50.10'), @('ancien-site.lan', 'imp-old', '192.168.50.100'),
                 @('outils.lan', 'erp', '192.168.10.99'), @('outils.lan', 'ged', '192.168.10.31'))) {
    if (-not (Get-DnsServerResourceRecord -ZoneName $r[0] -Name $r[1] -RRType A -ErrorAction SilentlyContinue)) {
        Add-DnsServerResourceRecordA -ZoneName $r[0] -Name $r[1] -IPv4Address $r[2]
    }
}
Set-Content C:\Admin\ticket-erp.txt -Encoding UTF8 -Value @(
    'Ticket 3307 : « L''ERP ne répond plus depuis la migration du serveur. »',
    'Le nouveau serveur ERP a l''adresse 192.168.10.30 (l''ancien, 192.168.10.99, est éteint).'
)
