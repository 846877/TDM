# Mise en situation du serveur de fichiers SRV-FIC01 : comptes, groupes, arborescence et un partage mal réglé.
$ErrorActionPreference = 'Stop'
$password = ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force
$groups = @{ Compta = 'Service comptabilité'; RH = 'Ressources humaines'; Direction = 'Direction';
             Atelier = 'Atelier de production'; BureauEtudes = "Bureau d'études" }
foreach ($g in $groups.Keys) {
    if (-not (Get-LocalGroup $g -ErrorAction SilentlyContinue)) { New-LocalGroup $g -Description $groups[$g] | Out-Null }
}
$users = @(
    @{ n = 'mdupont'; f = 'Marie Dupont'; g = 'Compta' }, @{ n = 'jmartin'; f = 'Julien Martin'; g = 'RH' },
    @{ n = 'pdurand'; f = 'Pierre Durand'; g = 'Direction' }, @{ n = 'lgarnier'; f = 'Luc Garnier'; g = $null },
    @{ n = 'crobert'; f = 'Claire Robert'; g = 'BureauEtudes' }, @{ n = 'pleroy'; f = 'Paul Leroy'; g = $null }
)
foreach ($u in $users) {
    if (-not (Get-LocalUser $u.n -ErrorAction SilentlyContinue)) {
        New-LocalUser $u.n -FullName $u.f -Password $password | Out-Null
        Add-LocalGroupMember -SID S-1-5-32-545 -Member $u.n
        if ($u.g) { Add-LocalGroupMember -Group $u.g -Member $u.n }
    }
}

# Arborescence : droits de base propres (Administrateurs et SYSTEM : contrôle total, Users : lecture).
foreach ($d in 'Compta', 'Compta\Salaires', 'RH', 'Direction', 'Commun', 'Logiciels') {
    New-Item "C:\Partages\$d" -ItemType Directory -Force | Out-Null
}
New-Item C:\Admin -ItemType Directory -Force | Out-Null
icacls.exe C:\Partages /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
icacls.exe C:\Partages\Commun /grant '*S-1-5-32-545:(OI)(CI)M' | Out-Null
Set-Content C:\Partages\Compta\Salaires\salaires-2024.xlsx 'confidentiel'
Set-Content C:\Partages\RH\entretiens.docx 'confidentiel'
Set-Content C:\Partages\Logiciels\LISEZMOI.txt 'Installeurs validés par le service informatique'
# Archive laissée par un ancien salarié, qui en est encore propriétaire.
Set-Content C:\Partages\Commun\archive-2019.zip 'archive'
icacls.exe C:\Partages\Commun\archive-2019.zip /setowner pleroy | Out-Null

# Partage « Commun » créé par le prestataire : lecture seule pour Tout le monde (erreur classique).
if (-not (Get-SmbShare Commun -ErrorAction SilentlyContinue)) {
    New-SmbShare -Name Commun -Path C:\Partages\Commun -ReadAccess Everyone -Description 'Dossier commun' | Out-Null
}
