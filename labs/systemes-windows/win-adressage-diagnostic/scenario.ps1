# PC01 : réseau en profil Public (erreur classique) et un programme inconnu qui écoute sur le port 4444.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
if (Get-NetAdapter -Name LAN -ErrorAction SilentlyContinue) {
    Get-NetConnectionProfile -InterfaceAlias LAN -ErrorAction SilentlyContinue |
        Set-NetConnectionProfile -NetworkCategory Public -ErrorAction SilentlyContinue
}
$code = '$l = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, 4444); $l.Start(); ' +
        'while ($true) { $c = $l.AcceptTcpClient(); $c.Close() }'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -Command `"$code`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
if (-not (Get-ScheduledTask -TaskName MiseAJourAuto -ErrorAction SilentlyContinue)) {
    Register-ScheduledTask -TaskName MiseAJourAuto -Description 'Updater' -Action $action -Trigger $trigger `
        -Principal $principal | Out-Null
}
Start-ScheduledTask -TaskName MiseAJourAuto
$deadline = (Get-Date).AddSeconds(60)
while (-not (Get-NetTCPConnection -LocalPort 4444 -State Listen -ErrorAction SilentlyContinue)) {
    if ((Get-Date) -gt $deadline) { throw 'Le programme de test n''écoute pas sur le port 4444' }
    Start-Sleep -Seconds 2
}
