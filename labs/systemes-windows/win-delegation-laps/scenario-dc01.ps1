# Mise en situation : arborescence Ateliers Durand, groupes GG_Support (jroux) et GG_RH (aperrin), comptes des
# services, et un ancien administrateur sorti des Admins du domaine mais encore marqué adminCount = 1.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
    'Direction', 'Compta', 'Atelier', 'Informatique', 'RH' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path "OU=Utilisateurs,$racine" }
}
redircmp "OU=Postes,$racine" | Out-Null
$mdp = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
$comptes = @(
    @('hgirard', 'Hugo', 'Girard', 'Direction'), @('mdupont', 'Marie', 'Dupont', 'Compta'),
    @('cmoreau', 'Chloé', 'Moreau', 'Atelier'), @('jroux', 'Julien', 'Roux', 'Informatique'),
    @('aperrin', 'Agnès', 'Perrin', 'RH'), @('ancien.admin', 'Ancien', 'Admin', 'Informatique')
)
foreach ($c in $comptes) {
    if (-not (Get-ADUser -Filter "SamAccountName -eq '$($c[0])'")) {
        New-ADUser -Name "$($c[1]) $($c[2])" -GivenName $c[1] -Surname $c[2] -SamAccountName $c[0] `
            -UserPrincipalName "$($c[0])@durand.lan" -Department $c[3] -AccountPassword $mdp -Enabled $true `
            -Path "OU=$($c[3]),OU=Utilisateurs,$racine"
    }
}
foreach ($g in @(@('GG_Support', 'jroux'), @('GG_RH', 'aperrin'), @('GG_Compta', 'mdupont'), @('GG_Atelier', 'cmoreau'))) {
    if (-not (Get-ADGroup -Filter "Name -eq '$($g[0])'")) {
        New-ADGroup -Name $g[0] -GroupScope Global -GroupCategory Security -Path "OU=Groupes,$racine"
        Add-ADGroupMember $g[0] -Members $g[1]
    }
}
# Trace d'un ancien passage chez les Admins du domaine : SDProp a posé adminCount = 1 et coupé l'héritage.
$ancien = Get-ADUser ancien.admin
Set-ADUser $ancien -Replace @{ adminCount = 1 }
$chemin = "AD:$($ancien.DistinguishedName)"
$acl = Get-Acl $chemin
$acl.SetAccessRuleProtection($true, $true)
Set-Acl $chemin $acl
New-Item C:\Admin -ItemType Directory -Force | Out-Null
