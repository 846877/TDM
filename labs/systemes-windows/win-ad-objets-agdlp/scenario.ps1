# Mise en situation : un domaine tout neuf où traînent trois comptes créés « à l'ancienne » dans CN=Users,
# un fichier d'embauches à importer et un dossier de la comptabilité sans droits adaptés.
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
New-Item C:\Admin, C:\Partages\Compta -ItemType Directory -Force | Out-Null
$pwd = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
$anciens = @(
    @{ Sam = 'jmartin';  Prenom = 'Julien'; Nom = 'Martin';  Service = 'Compta';  Fonction = 'Comptable' },
    @{ Sam = 'pleroy';   Prenom = 'Paul';   Nom = 'Leroy';   Service = 'Atelier'; Fonction = 'Tourneur' },
    @{ Sam = 'tinterim'; Prenom = 'Thomas'; Nom = 'Intérim'; Service = 'Atelier'; Fonction = 'Intérimaire' }
)
foreach ($u in $anciens) {
    if (-not (Get-ADUser -Filter "SamAccountName -eq '$($u.Sam)'")) {
        New-ADUser -Name "$($u.Prenom) $($u.Nom)" -GivenName $u.Prenom -Surname $u.Nom -SamAccountName $u.Sam `
            -UserPrincipalName "$($u.Sam)@durand.lan" -Department $u.Service -Title $u.Fonction `
            -AccountPassword $pwd -Enabled $true -Path 'CN=Users,DC=durand,DC=lan'
    }
}
# Paul Leroy a accumulé des droits au fil des années (il quitte l'entreprise : exercice « départ »).
foreach ($g in 'Remote Desktop Users', 'Print Operators') {
    try { Add-ADGroupMember -Identity $g -Members pleroy } catch { Write-Host "  $g : $_" }
}
Set-Content C:\Admin\embauches.csv -Encoding UTF8 -Value @(
    'Prenom;Nom;Login;Service;Fonction',
    'Alice;Garcia;agarcia;Compta;Comptable',
    'Bruno;Lefebvre;blefebvre;Atelier;Soudeur',
    "Chloé;Moreau;cmoreau;Atelier;Chef d'atelier",
    'David;Petit;dpetit;Direction;Directeur administratif',
    'Emma;Roux;eroux;Compta;Assistante comptable',
    'Farid;Benali;fbenali;Atelier;Magasinier',
    'Gaëlle;Fournier;gfournier;Atelier;Opératrice',
    'Hugo;Girard;hgirard;Direction;Directeur général'
)
Set-Content C:\Partages\Compta\LISEZMOI.txt 'Dossier de la comptabilité : droits à poser selon AGDLP.' -Encoding UTF8
