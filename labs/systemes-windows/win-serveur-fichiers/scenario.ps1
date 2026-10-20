# Mise en situation : arborescence des partages en place, deux partages déjà publiés (Commun, Direction),
# des fichiers multimédias qui encombrent Commun, SMB 1 encore actif.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
$dossiers = 'Commun', 'Commun\Formation', 'Direction', 'Projets', 'Projets\Chantier-Lyon', 'Projets\Chantier-Grenoble',
            'Utilisateurs', 'Utilisateurs\mdupont', 'Utilisateurs\cmoreau'
foreach ($d in $dossiers) { New-Item "C:\Partages\$d" -ItemType Directory -Force | Out-Null }
foreach ($s in 'Commun', 'Direction') {
    if (-not (Get-SmbShare -Name $s -ErrorAction SilentlyContinue)) {
        New-SmbShare -Name $s -Path "C:\Partages\$s" -ChangeAccess '*S-1-5-11' | Out-Null
    }
}
fsutil.exe file createnew C:\Partages\Commun\playlist-pause-dej.mp3 15000000 | Out-Null
fsutil.exe file createnew C:\Partages\Projets\Chantier-Lyon\plans-v3.dwg 80000000 | Out-Null
fsutil.exe file createnew C:\Partages\Projets\Chantier-Lyon\video-drone.mp4 260000000 | Out-Null
Set-Content C:\Partages\Commun\LISEZMOI.txt 'Partage commun : documents de travail uniquement.' -Encoding UTF8
# SMB 1 : protocole obsolète laissé actif par l'ancien serveur.
Set-SmbServerConfiguration -EnableSMB1Protocol $true -Force -ErrorAction SilentlyContinue
