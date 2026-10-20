# Mise en situation du poste PC01 : programmes indésirables au démarrage, spouleur prêt pour les imprimantes.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Set-Service Spooler -StartupType Automatic
Start-Service Spooler
New-Item C:\ProgramData\UpdaterPro -ItemType Directory -Force | Out-Null
Set-Content C:\ProgramData\UpdaterPro\updater.cmd '@echo off'
Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name UpdaterPro -Value 'C:\ProgramData\UpdaterPro\updater.cmd /silent'
# Pour l'utilisateur courant (vagrant dans la VM) : un « nettoyeur » publicitaire.
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (-not (Test-Path $run)) { New-Item $run -Force | Out-Null }  # absente sur certains profils neufs
Set-ItemProperty $run -Name PubCleaner -Value 'C:\ProgramData\UpdaterPro\updater.cmd /pub'
