# Mise en situation (contrôleur) : annuaire des Ateliers Durand avec trois pannes qui n'empêchent pas la
# jonction de PC01 : compte mdupont inutilisable, chaîne AGDLP de la compta coupée, GPO des postes inopérante.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory, GroupPolicy
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
}
redircmp "OU=Postes,$racine" | Out-Null
$mdp = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
foreach ($c in @(@('mdupont', 'Marie', 'Dupont', 'Compta'), @('slambert', 'Sophie', 'Lambert', 'Compta'), @('hgirard', 'Hugo', 'Girard', 'Direction'))) {
    if (-not (Get-ADUser -Filter "SamAccountName -eq '$($c[0])'")) {
        New-ADUser -Name "$($c[1]) $($c[2])" -GivenName $c[1] -Surname $c[2] -SamAccountName $c[0] `
            -UserPrincipalName "$($c[0])@durand.lan" -Department $c[3] -AccountPassword $mdp -Enabled $true `
            -Path "OU=Utilisateurs,$racine"
    }
}
if (-not (Get-ADGroup -Filter "Name -eq 'GG_Compta'")) {
    New-ADGroup -Name GG_Compta -GroupScope Global -GroupCategory Security -Path "OU=Groupes,$racine"
    Add-ADGroupMember GG_Compta -Members mdupont, slambert
    New-ADGroup -Name DL_Compta_RW -GroupScope DomainLocal -GroupCategory Security -Path "OU=Groupes,$racine"
}
New-Item C:\Admin, C:\Partages\Compta -ItemType Directory -Force | Out-Null
if (-not (Get-SmbShare -Name Compta -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name Compta -Path C:\Partages\Compta -ChangeAccess '*S-1-5-11' | Out-Null
    icacls C:\Partages\Compta /inheritance:r /grant '*S-1-5-32-544:(OI)(CI)F' 'DURAND\DL_Compta_RW:(OI)(CI)M' | Out-Null
}
# Panne : compte mdupont désactivé, expiré, sans aucune plage horaire autorisée.
Set-ADUser mdupont -Enabled $false -AccountExpirationDate (Get-Date).AddDays(-3) -Replace @{ logonHours = [byte[]](@(0) * 21) }
# Panne : la GPO des postes existe mais son lien est désactivé et Utilisateurs authentifiés n'y a plus accès.
if (-not (Get-GPO -Name 'C - Postes securite' -ErrorAction SilentlyContinue)) {
    New-GPO -Name 'C - Postes securite' | New-GPLink -Target "OU=Postes,$racine" -LinkEnabled No | Out-Null
    $cle = 'HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\System'
    Set-GPRegistryValue -Name 'C - Postes securite' -Key $cle -ValueName legalnoticecaption -Type String -Value 'Ateliers Durand' | Out-Null
    Set-GPRegistryValue -Name 'C - Postes securite' -Key $cle -ValueName legalnoticetext -Type String -Value 'Accès réservé au personnel autorisé.' | Out-Null
    $au = (New-Object Security.Principal.SecurityIdentifier 'S-1-5-11').Translate([Security.Principal.NTAccount]).Value.Split('\')[-1]
    Set-GPPermission -Name 'C - Postes securite' -TargetName $au -TargetType Group -PermissionLevel None -Replace | Out-Null
}
