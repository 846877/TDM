# Mise en situation : un seul contrôleur, un seul site (Default-First-Site-Name), aucun sous-réseau déclaré.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
New-Item C:\Admin -ItemType Directory -Force | Out-Null
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes', 'Serveurs' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
}
