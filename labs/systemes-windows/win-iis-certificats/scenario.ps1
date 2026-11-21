# Mise en situation : le contenu de l'intranet est prêt dans C:\Sites\Intranet (avec un sous-dossier admin),
# mais IIS n'est pas installé. Un ancien réglage SCHANNEL active encore TLS 1.0 et 1.1 côté serveur.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin, C:\Sites\Intranet\admin -ItemType Directory -Force | Out-Null
Set-Content C:\Sites\Intranet\index.html '<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Intranet</title></head><body><h1>Intranet des Ateliers Durand</h1></body></html>' -Encoding UTF8
Set-Content C:\Sites\Intranet\admin\index.html '<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Administration</title></head><body><h1>Administration de l''intranet</h1></body></html>' -Encoding UTF8
foreach ($v in 'TLS 1.0', 'TLS 1.1') {
    $cle = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\$v\Server"
    if (-not (Test-Path $cle)) { New-Item $cle -Force | Out-Null }   # crée aussi les clés parentes manquantes
    Set-ItemProperty $cle -Name Enabled -Value 1 -Type DWord
    Set-ItemProperty $cle -Name DisabledByDefault -Value 0 -Type DWord
}
