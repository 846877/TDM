# Mise en situation : un domaine où les comptes du quotidien sont administrateurs du domaine, un compte de
# service « kerberoastable » lui aussi administrateur, et un mot de passe krbtgt jamais changé.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
New-Item C:\Admin -ItemType Directory -Force | Out-Null
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes', 'Serveurs', 'Services' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
}
redircmp "OU=Postes,$racine" | Out-Null
$mdp = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
$comptes = @(
    @('hgirard', 'Hugo', 'Girard'), @('jroux', 'Julien', 'Roux'), @('mdupont', 'Marie', 'Dupont'), @('cmoreau', 'Chloé', 'Moreau')
)
foreach ($c in $comptes) {
    if (-not (Get-ADUser -Filter "SamAccountName -eq '$($c[0])'")) {
        New-ADUser -Name "$($c[1]) $($c[2])" -GivenName $c[1] -Surname $c[2] -SamAccountName $c[0] `
            -UserPrincipalName "$($c[0])@durand.lan" -AccountPassword $mdp -Enabled $true -Path "OU=Utilisateurs,$racine"
    }
}
# Compte de service de la sauvegarde : SPN, mot de passe qui n'expire jamais, RC4 accepté.
if (-not (Get-ADUser -Filter "SamAccountName -eq 'svc-backup'")) {
    New-ADUser -Name 'svc-backup' -SamAccountName 'svc-backup' -AccountPassword (ConvertTo-SecureString 'Sauvegarde2019' -AsPlainText -Force) `
        -Enabled $true -PasswordNeverExpires $true -Path "OU=Services,$racine" `
        -ServicePrincipalNames 'MSSQLSvc/SRV-SQL01.durand.lan:1433'
}
Set-ADUser svc-backup -Replace @{ 'msDS-SupportedEncryptionTypes' = 28 }   # RC4 + AES
# Les comptes du quotidien et le compte de service sont administrateurs du domaine.
$da = Get-ADGroup "$((Get-ADDomain).DomainSID)-512"
Add-ADGroupMember $da -Members jroux, hgirard, svc-backup
# Trace de l'âge du mot de passe krbtgt avant les exercices.
(Get-ADUser krbtgt -Properties pwdLastSet).pwdLastSet | Set-Content C:\Admin\krbtgt-initial.txt -Encoding Ascii
