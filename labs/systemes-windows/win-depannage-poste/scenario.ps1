# Mise en situation : le poste PC01 cumule les pannes typiques remontées par les utilisateurs.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
New-Item C:\Admin -ItemType Directory -Force | Out-Null

# 1. Imprimante de la compta en pause, avec des documents bloqués.
Set-Service Spooler -StartupType Automatic
Start-Service Spooler
if (-not (Get-Printer -Name Compta-Laser -ErrorAction SilentlyContinue)) {
    if (-not (Get-PrinterPort -Name IP_192.168.10.60 -ErrorAction SilentlyContinue)) {
        Add-PrinterPort -Name IP_192.168.10.60 -PrinterHostAddress 192.168.10.60
    }
    Add-PrinterDriver -Name 'Generic / Text Only'
    Add-Printer -Name Compta-Laser -PortName IP_192.168.10.60 -DriverName 'Generic / Text Only'
}
$printer = Get-CimInstance Win32_Printer -Filter "Name='Compta-Laser'"
Invoke-CimMethod -InputObject $printer -MethodName Pause | Out-Null
1..3 | ForEach-Object { "Facture $_" | Out-Printer -Name Compta-Laser }

# 2. Fichier hosts détourné (hameçonnage).
$hosts = 'C:\Windows\System32\drivers\etc\hosts'
if (-not (Select-String -Path $hosts -Pattern 'impots' -Quiet)) {
    Add-Content $hosts "`r`n10.66.66.66`twww.impots.gouv.fr"
}

# 3. Proxy inexistant pour l'utilisateur et pour WinHTTP.
$ie = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
Set-ItemProperty $ie -Name ProxyEnable -Value 1 -Type DWord
Set-ItemProperty $ie -Name ProxyServer -Value '10.0.0.99:3128'
netsh.exe winhttp set proxy 10.0.0.99:3128 | Out-Null

# 4. Disque encombré par une vieille vidéo.
if (-not (Test-Path 'C:\Users\Public\Videos\Formation\export-camera-2019.mp4')) {
    New-Item 'C:\Users\Public\Videos\Formation' -ItemType Directory -Force | Out-Null
    fsutil.exe file createnew 'C:\Users\Public\Videos\Formation\export-camera-2019.mp4' 1500000000 | Out-Null
    Set-Content 'C:\Users\Public\Videos\Formation\lisezmoi.txt' 'Vidéos de formation'
}

# 5. Plus de son : service audio désactivé.
Stop-Service Audiosrv -Force -ErrorAction SilentlyContinue
Set-Service Audiosrv -StartupType Disabled

# 6. Mauvais fuseau horaire (le poste vient d'un salon aux États-Unis).
Set-TimeZone -Id 'Pacific Standard Time'

# 7. Clavier QWERTY seulement.
Set-WinUserLanguageList -LanguageList (New-WinUserLanguageList -Language 'en-US') -Force

# 8. Le logiciel de comptabilité plante.
if (-not [Diagnostics.EventLog]::SourceExists('ComptaPro')) { New-EventLog -LogName Application -Source ComptaPro }
1..4 | ForEach-Object {
    Write-EventLog -LogName Application -Source ComptaPro -EventId 1000 -EntryType Error `
        -Message "ComptaPro.exe s'est arrêté de façon inattendue. Module défaillant : licence-ng.dll, version 3.2.1. Code 0xc0000005."
}

# 9. Carte réseau du LAN désactivée (seulement dans la VM du lab).
if (Get-NetAdapter -Name LAN -ErrorAction SilentlyContinue) { Disable-NetAdapter -Name LAN -Confirm:$false }
