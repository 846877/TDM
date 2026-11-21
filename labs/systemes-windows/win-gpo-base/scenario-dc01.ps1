# Mise en situation : OU, comptes et groupes en place, nouveaux ordinateurs redirigés vers l'OU Postes,
# partage Commun et fond d'écran de l'entreprise dans NETLOGON. Aucune GPO personnalisée.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$racine = 'OU=Ateliers Durand,DC=durand,DC=lan'
if (-not (Get-ADOrganizationalUnit -Filter "Name -eq 'Ateliers Durand'")) {
    New-ADOrganizationalUnit -Name 'Ateliers Durand' -Path 'DC=durand,DC=lan'
    'Utilisateurs', 'Groupes', 'Postes' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path $racine }
    'Direction', 'Compta', 'Atelier' | ForEach-Object { New-ADOrganizationalUnit -Name $_ -Path "OU=Utilisateurs,$racine" }
}
redircmp "OU=Postes,$racine" | Out-Null
$mdp = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
$comptes = @(
    @('hgirard', 'Hugo', 'Girard', 'Direction'), @('mdupont', 'Marie', 'Dupont', 'Compta'),
    @('cmoreau', 'Chloé', 'Moreau', 'Atelier'), @('blefebvre', 'Bruno', 'Lefebvre', 'Atelier')
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
New-Item C:\Admin, C:\Partages\Commun -ItemType Directory -Force | Out-Null
if (-not (Get-SmbShare -Name Commun -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name Commun -Path C:\Partages\Commun -ChangeAccess '*S-1-5-11' | Out-Null
    icacls C:\Partages\Commun /grant '*S-1-5-11:(OI)(CI)M' | Out-Null
}
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap 1280, 720
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::FromArgb(0, 70, 120))
$font = New-Object System.Drawing.Font 'Segoe UI', 48
$g.DrawString('Ateliers Durand', $font, [System.Drawing.Brushes]::White, 380, 300)
$bmp.Save('C:\Windows\SYSVOL\sysvol\durand.lan\scripts\fond-durand.jpg', [System.Drawing.Imaging.ImageFormat]::Jpeg)
$g.Dispose(); $bmp.Dispose()
