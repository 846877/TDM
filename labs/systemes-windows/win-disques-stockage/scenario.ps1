# Mise en situation : trois disques virtuels (VHDX) branchés sur le serveur, comme trois nouveaux disques.
#   donnees.vhdx  2 Go   neuf (RAW)
#   archives.vhdx 1,5 Go neuf (RAW)
#   journaux.vhdx 1 Go   déjà formaté (L:, 500 Mo, plein)
# Une tâche planifiée les rebranche à chaque démarrage (un VHDX attaché à la main ne l'est plus après un redémarrage).
$ErrorActionPreference = 'Stop'
New-Item C:\VHD, C:\Admin -ItemType Directory -Force | Out-Null
if (-not (Get-LocalUser mdupont -ErrorAction SilentlyContinue)) {
    New-LocalUser mdupont -FullName 'Marie Dupont' -Password (ConvertTo-SecureString 'Bienvenue2024!' -AsPlainText -Force) | Out-Null
}
$disks = @{ donnees = 2048; archives = 1536; journaux = 1024 }
$attach = @()
foreach ($name in $disks.Keys) {
    $file = "C:\VHD\$name.vhdx"
    if (-not (Test-Path $file)) {
        Set-Content C:\VHD\creer.txt "create vdisk file=`"$file`" maximum=$($disks[$name]) type=expandable" -Encoding Ascii
        diskpart.exe /s C:\VHD\creer.txt | Out-Null
    }
    $attach += "select vdisk file=`"$file`"", 'attach vdisk'
}
Set-Content C:\VHD\attacher.txt $attach -Encoding Ascii
diskpart.exe /s C:\VHD\attacher.txt | Out-Null   # erreur sans gravité si déjà attaché
Start-Sleep -Seconds 3

$action = New-ScheduledTaskAction -Execute 'diskpart.exe' -Argument '/s C:\VHD\attacher.txt'
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'TDM-Disques-Virtuels' -Description 'Rebranche les VHDX du lab au démarrage' `
    -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $principal -Force | Out-Null

# Stratégie SAN de Windows Server : un nouveau disque peut arriver hors ligne ou en lecture seule.
Get-Disk | Where-Object { $_.Size -in 1GB, 1536MB, 2GB } | ForEach-Object {
    if ($_.IsOffline) { Set-Disk -Number $_.Number -IsOffline $false }
    if ($_.IsReadOnly) { Set-Disk -Number $_.Number -IsReadOnly $false }
}

# Le disque des journaux : MBR, une partition de 500 Mo (L:) presque pleine.
$j = Get-Disk | Where-Object Size -eq 1GB
if ($j.PartitionStyle -eq 'RAW') {
    Initialize-Disk -Number $j.Number -PartitionStyle MBR
    New-Partition -DiskNumber $j.Number -Size 500MB -DriveLetter L |
        Format-Volume -FileSystem NTFS -NewFileSystemLabel LOGS -Confirm:$false | Out-Null
    fsutil.exe file createnew L:\journaux-applicatifs.bak 450000000 | Out-Null
}
