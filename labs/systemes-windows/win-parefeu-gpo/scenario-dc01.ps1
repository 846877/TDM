# Mise en situation : arborescence Ateliers Durand, nouveaux ordinateurs redirigés vers l'OU Postes.
# Aucune GPO de pare-feu : chaque poste garde ses règles locales d'origine.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes', 'Serveurs' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
}
redircmp "OU=Postes,$racine" | Out-Null
New-Item C:\Admin -ItemType Directory -Force | Out-Null
