# Mise en situation : groupes de service, dossier Commun partagé sur SRV-DC01 avec quelques documents.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Serveurs' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
}
foreach ($s in 'Direction', 'Compta', 'Atelier') {
    if (-not (Get-ADGroup -Filter "Name -eq 'GG_$s'")) {
        New-ADGroup -Name "GG_$s" -GroupScope Global -GroupCategory Security -Path "OU=Groupes,$racine"
    }
}
New-Item C:\Admin, C:\Partages\Commun -ItemType Directory -Force | Out-Null
1..5 | ForEach-Object { Set-Content "C:\Partages\Commun\note-de-service-$_.txt" "Note de service n°$_ des Ateliers Durand." }
if (-not (Get-SmbShare -Name Commun -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name Commun -Path C:\Partages\Commun -ChangeAccess '*S-1-5-11' | Out-Null
    icacls C:\Partages\Commun /grant '*S-1-5-11:(OI)(CI)M' | Out-Null
}
