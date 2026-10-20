# Mise en situation côté contrôleur : arborescence d'OU, groupes et une utilisatrice déjà prêts.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
}
foreach ($g in 'GG_Support', 'GG_Compta') {
    if (-not (Get-ADGroup -Filter "Name -eq '$g'")) {
        New-ADGroup -Name $g -GroupScope Global -GroupCategory Security -Path "OU=Groupes,$racine"
    }
}
if (-not (Get-ADUser -Filter "SamAccountName -eq 'mdupont'")) {
    New-ADUser -Name 'Marie Dupont' -GivenName Marie -Surname Dupont -SamAccountName mdupont `
        -UserPrincipalName mdupont@durand.lan -Department Compta -Path "OU=Utilisateurs,$racine" `
        -AccountPassword (ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force) -Enabled $true
    Add-ADGroupMember GG_Compta -Members mdupont
}
if (-not (Get-ADUser -Filter "SamAccountName -eq 'tech'")) {
    New-ADUser -Name 'Technicien Support' -SamAccountName tech -UserPrincipalName tech@durand.lan `
        -Path "OU=Utilisateurs,$racine" -AccountPassword (ConvertTo-SecureString 'Support2024!' -AsPlainText -Force) -Enabled $true
    Add-ADGroupMember GG_Support -Members tech
}
