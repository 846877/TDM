# Mise en situation : données de l'entreprise dans C:\Donnees (empreintes SHA-256 dans C:\Admin\empreintes.csv),
# un disque virtuel E: « SAUVEGARDE » de 6 Go, et une procédure RH abîmée après un cliché instantané.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
New-Item C:\Admin, C:\VHD -ItemType Directory -Force | Out-Null

# Disque de sauvegarde (VHDX rebranché à chaque démarrage par une tâche planifiée).
$vhd = 'C:\VHD\sauvegarde.vhdx'
if (-not (Test-Path $vhd)) {
    Set-Content C:\VHD\creer.txt "create vdisk file=`"$vhd`" maximum=6144 type=expandable" -Encoding Ascii
    diskpart.exe /s C:\VHD\creer.txt | Out-Null
}
Set-Content C:\VHD\attacher.txt "select vdisk file=`"$vhd`"", 'attach vdisk' -Encoding Ascii
diskpart.exe /s C:\VHD\attacher.txt | Out-Null
Start-Sleep -Seconds 3
$action = New-ScheduledTaskAction -Execute 'diskpart.exe' -Argument '/s C:\VHD\attacher.txt'
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'TDM-Disque-Sauvegarde' -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Principal $principal -Force | Out-Null
$disk = Get-Disk | Where-Object { $_.Location -like '*sauvegarde.vhdx' -or ($_.Size -eq 6GB -and $_.BusType -eq 'File Backed Virtual') } | Select-Object -First 1
if ($disk.IsOffline) { Set-Disk -Number $disk.Number -IsOffline $false }
if ($disk.IsReadOnly) { Set-Disk -Number $disk.Number -IsReadOnly $false }
if ($disk.PartitionStyle -eq 'RAW') {
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT
    New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter E |
        Format-Volume -FileSystem NTFS -NewFileSystemLabel SAUVEGARDE -Confirm:$false | Out-Null
}

# Données de l'entreprise.
$fichiers = [ordered]@{
    'Compta\bilan-2025.xlsx'       = 'Bilan 2025 - total actif 1 254 300 EUR'
    'Compta\factures-octobre.csv'  = "num;client;montant`r`nF2025-101;Garage Morel;1250`r`nF2025-102;SCI Lumière;830"
    'RH\procedure-accueil.txt'     = 'Procédure d''accueil des nouveaux salariés - version 1 validée par la direction'
    'RH\registre-personnel.csv'    = "matricule;nom`r`n001;Girard`r`n002;Dupont"
    'Atelier\gamme-usinage-A12.txt' = 'Gamme A12 : tournage, fraisage, contrôle tridimensionnel'
}
foreach ($f in $fichiers.Keys) {
    $chemin = "C:\Donnees\$f"
    New-Item (Split-Path $chemin) -ItemType Directory -Force | Out-Null
    Set-Content $chemin $fichiers[$f] -Encoding UTF8
}
Get-ChildItem C:\Donnees -Recurse -File | ForEach-Object {
    [pscustomobject]@{ Fichier = $_.FullName; SHA256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
} | Export-Csv C:\Admin\empreintes.csv -NoTypeInformation -Encoding UTF8

# Un cliché instantané de C:, puis la procédure RH est écrasée par erreur.
vssadmin.exe create shadow /for=C: | Out-Null
Set-Content C:\Donnees\RH\procedure-accueil.txt 'CORROMPU - fichier écrasé par une macro' -Encoding UTF8
