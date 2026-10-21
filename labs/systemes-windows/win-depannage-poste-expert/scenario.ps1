# Mise en situation : le poste d'un commercial revenu de déplacement, « lent et bizarre ». Pannes posées :
# spouleur avec une dépendance inexistante, persistance suspecte (tâche, clé Run, script), faux certificat
# racine, journal Application minuscule sans écrasement, carte LAN en profil Public, Windows Update coupé,
# vidage mémoire désactivé, fichier hosts détourné, exclusion Defender sur tout C:\.
# Le script tourne aussi sur les runners Windows Server de la CI : chaque étape propre au poste est protégée.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin, C:\ProgramData\Updater -ItemType Directory -Force | Out-Null

# Spouleur : dépendance vers un service fantôme, désactivé et dont l'exécutable n'existe pas.
if (-not (Get-Service TDMFantome -ErrorAction SilentlyContinue)) {
    sc.exe create TDMFantome binPath= 'C:\Windows\System32\tdm-fantome.exe' start= disabled DisplayName= 'Assistant de compatibilité' | Out-Null
}
Stop-Service Spooler -Force -ErrorAction SilentlyContinue
$dep = @((Get-Service Spooler).ServicesDependedOn.Name | Where-Object { $_ -ne 'TDMFantome' }) + 'TDMFantome'
sc.exe config Spooler depend= ($dep -join '/') start= auto | Out-Null

# Persistance : script caché lancé par une tâche planifiée et par la clé Run.
Set-Content C:\ProgramData\Updater\maj.ps1 "Add-Content `$env:TEMP\maj.log (Get-Date)"
$action = New-ScheduledTaskAction -Execute powershell.exe -Argument '-WindowStyle Hidden -ExecutionPolicy Bypass -File C:\ProgramData\Updater\maj.ps1'
Register-ScheduledTask -TaskName MiseAJourAdobe -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogOn) -User SYSTEM -Force | Out-Null
Set-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Run -Name OneDriveSync -Value 'powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\ProgramData\Updater\maj.ps1'

# Faux certificat racine.
if (-not (Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -eq 'CN=DigiCert Global Root G9')) {
    $c = New-SelfSignedCertificate -Subject 'CN=DigiCert Global Root G9' -CertStoreLocation Cert:\LocalMachine\My -KeyUsage CertSign, CRLSign -NotAfter (Get-Date).AddYears(5)
    $magasin = New-Object Security.Cryptography.X509Certificates.X509Store 'Root', 'LocalMachine'
    $magasin.Open('ReadWrite'); $magasin.Add($c); $magasin.Close()
    Remove-Item "Cert:\LocalMachine\My\$($c.Thumbprint)" -DeleteKey
}

# Journal Application : 1 Mo, conservation (plus rien n'est écrit une fois plein).
wevtutil sl Application /ms:1048576 /rt:true

# Carte LAN en profil Public (absente des runners de CI).
if (Get-NetConnectionProfile -InterfaceAlias LAN -ErrorAction SilentlyContinue) {
    Set-NetConnectionProfile -InterfaceAlias LAN -NetworkCategory Public
}

# Windows Update coupé : service désactivé et stratégie NoAutoUpdate.
sc.exe config wuauserv start= disabled | Out-Null
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
$au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
if (-not (Test-Path $au)) { New-Item $au -Force | Out-Null }
Set-ItemProperty $au -Name NoAutoUpdate -Value 1 -Type DWord

# Plus aucun fichier de vidage en cas d'écran bleu.
Set-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl -Name CrashDumpEnabled -Value 0 -Type DWord

# Fichier hosts détourné.
$hosts = 'C:\Windows\System32\drivers\etc\hosts'
if (-not (Select-String -Path $hosts -Pattern '203.0.113.66' -SimpleMatch -Quiet)) {
    Add-Content $hosts "`r`n203.0.113.66 www.microsoft.com`r`n203.0.113.66 download.windowsupdate.com`r`n203.0.113.66 go.microsoft.com"
}

# Exclusion Defender sur tout le disque (si Defender est présent).
if (Get-Command Add-MpPreference -ErrorAction SilentlyContinue) {
    try { Add-MpPreference -ExclusionPath 'C:\' } catch { Write-Host "Defender : $_" }
}
