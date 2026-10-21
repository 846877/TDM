# Mise en situation : arborescence Ateliers Durand (avec Postes\Formation), comptes et groupes, nouveaux
# ordinateurs redirigés vers l'OU Postes, et trois GPO déjà liées à Postes dans un ordre à revoir.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory, GroupPolicy
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
    'Direction', 'Compta', 'Atelier', 'Informatique' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path "OU=Utilisateurs,$racine" }
    New-ADOrganizationalUnit -Name 'Formation' -Path "OU=Postes,$racine"
}
redircmp "OU=Postes,$racine" | Out-Null
$mdp = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
$comptes = @(
    @('hgirard', 'Hugo', 'Girard', 'Direction'), @('mdupont', 'Marie', 'Dupont', 'Compta'),
    @('slambert', 'Sophie', 'Lambert', 'Compta'), @('cmoreau', 'Chloé', 'Moreau', 'Atelier'),
    @('blefebvre', 'Bruno', 'Lefebvre', 'Atelier'), @('jroux', 'Julien', 'Roux', 'Informatique')
)
foreach ($c in $comptes) {
    if (-not (Get-ADUser -Filter "SamAccountName -eq '$($c[0])'")) {
        New-ADUser -Name "$($c[1]) $($c[2])" -GivenName $c[1] -Surname $c[2] -SamAccountName $c[0] `
            -UserPrincipalName "$($c[0])@durand.lan" -Department $c[3] -AccountPassword $mdp -Enabled $true `
            -Path "OU=$($c[3]),OU=Utilisateurs,$racine"
    }
}
foreach ($s in 'Direction', 'Compta', 'Atelier') {
    if (-not (Get-ADGroup -Filter "Name -eq 'GG_$s'")) {
        New-ADGroup -Name "GG_$s" -GroupScope Global -GroupCategory Security -Path "OU=Groupes,$racine"
        Add-ADGroupMember "GG_$s" -Members (Get-ADUser -Filter "Department -eq '$s'")
    }
}
if (-not (Get-ADGroup -Filter "Name -eq 'GG_Support'")) {
    New-ADGroup -Name GG_Support -GroupScope Global -GroupCategory Security -Path "OU=Groupes,$racine"
    Add-ADGroupMember GG_Support -Members jroux
}
New-Item C:\Admin -ItemType Directory -Force | Out-Null
# Trois GPO liées à Postes : la sécurité minimale en tête, les exceptions ensuite, un vieux proxy oublié.
$postes = "OU=Postes,$racine"
foreach ($g in @(
        @('C - Securite minimale', '600'), @('C - Exceptions atelier', '1800'), @('C - Ancien proxy', $null))) {
    if (-not (Get-GPO -Name $g[0] -ErrorAction SilentlyContinue)) {
        $gpo = New-GPO -Name $g[0]
        $gpo | New-GPLink -Target $postes | Out-Null
        if ($g[1]) {
            Set-GPRegistryValue -Name $g[0] -Key 'HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\System' `
                -ValueName InactivityTimeoutSecs -Type DWord -Value ([int]$g[1]) | Out-Null
        } else {
            Set-GPRegistryValue -Name $g[0] -Key 'HKLM\Software\Policies\Microsoft\Windows\CurrentVersion\Internet Settings' `
                -ValueName ProxySettingsPerUser -Type DWord -Value 0 | Out-Null
        }
    }
}
