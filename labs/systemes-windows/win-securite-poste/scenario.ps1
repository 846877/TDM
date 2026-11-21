# Mise en situation : un portable revenu d'un prestataire « peu soigneux ». Exclusions Defender suspectes,
# règle de pare-feu entrante ouverte, profil Public désactivé, invité actif, UAC sans invite, un disque de
# données V: (« COFFRE ») non chiffré, audit des ouvertures de session coupé.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
New-Item C:\Admin, C:\VHD, C:\ProgramData\Updater -ItemType Directory -Force | Out-Null

# Disque de données (VHDX rebranché à chaque démarrage).
$vhd = 'C:\VHD\coffre.vhdx'
if (-not (Test-Path $vhd)) {
    Set-Content C:\VHD\creer.txt "create vdisk file=`"$vhd`" maximum=1024 type=expandable" -Encoding Ascii
    diskpart.exe /s C:\VHD\creer.txt | Out-Null
}
Set-Content C:\VHD\attacher.txt "select vdisk file=`"$vhd`"", 'attach vdisk' -Encoding Ascii
diskpart.exe /s C:\VHD\attacher.txt | Out-Null
Start-Sleep -Seconds 3
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'TDM-Disque-Coffre' -Principal $principal -Force `
    -Action (New-ScheduledTaskAction -Execute 'diskpart.exe' -Argument '/s C:\VHD\attacher.txt') `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) | Out-Null
$disk = Get-Disk | Where-Object { $_.Location -like '*coffre.vhdx' } | Select-Object -First 1
if ($disk.IsOffline) { Set-Disk -Number $disk.Number -IsOffline $false }
if ($disk.PartitionStyle -eq 'RAW') {
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT
    New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter V |
        Format-Volume -FileSystem NTFS -NewFileSystemLabel COFFRE -Confirm:$false | Out-Null
    Set-Content V:\contrats-clients.txt 'Contrats clients 2026 - confidentiel' -Encoding UTF8
}

# Microsoft Defender : exclusions laissées par « l'outil de mise à jour » et protection PUA coupée.
try {
    Add-MpPreference -ExclusionPath C:\ProgramData\Updater -ExclusionProcess svchost64.exe
    Set-MpPreference -PUAProtection Disabled
} catch { Write-Host "  Defender : $_" }

# Pare-feu : une porte ouverte et un profil désactivé.
if (-not (Get-NetFirewallRule -DisplayName 'Assistance distante (TCP 4444)' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName 'Assistance distante (TCP 4444)' -Direction Inbound -Protocol TCP `
        -LocalPort 4444 -Action Allow -Profile Any | Out-Null
}
Set-NetFirewallProfile -Profile Public -Enabled False

# Comptes : invité activé.
Get-LocalUser | Where-Object { $_.SID.Value -like '*-501' } | Enable-LocalUser

# UAC : élévation sans invite pour les administrateurs, pas de bureau sécurisé.
$uac = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
Set-ItemProperty $uac -Name ConsentPromptBehaviorAdmin -Value 0
Set-ItemProperty $uac -Name PromptOnSecureDesktop -Value 0

# Audit : le prestataire a coupé l'audit des ouvertures de session, des verrouillages et de la gestion des
# comptes (« ça remplissait le journal »). Une image durcie peut déjà les auditer : on part d'un état connu.
foreach ($sous in '{0CCE9215-69AE-11D9-BED3-505054503030}', '{0CCE9217-69AE-11D9-BED3-505054503030}',
                  '{0CCE9235-69AE-11D9-BED3-505054503030}') {
    auditpol.exe /set /subcategory:$sous /success:disable /failure:disable | Out-Null
}
