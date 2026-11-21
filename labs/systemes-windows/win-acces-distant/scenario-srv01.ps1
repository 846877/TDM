# SRV01 : Bureau à distance désactivé (et sans NLA), compte du support à préparer.
$ErrorActionPreference = 'Stop'
$ts = 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server'
Set-ItemProperty $ts -Name fDenyTSConnections -Value 1 -Type DWord
Set-ItemProperty "$ts\WinStations\RDP-Tcp" -Name UserAuthentication -Value 0 -Type DWord
Disable-NetFirewallRule -Group '@FirewallAPI.dll,-28752' -ErrorAction SilentlyContinue   # groupe « Remote Desktop »
if (-not (Get-LocalGroup Support -ErrorAction SilentlyContinue)) {
    New-LocalGroup Support -Description 'Support informatique de premier niveau' | Out-Null
}
if (-not (Get-LocalUser hdesk -ErrorAction SilentlyContinue)) {
    $password = ConvertTo-SecureString 'Support2024!' -AsPlainText -Force
    New-LocalUser hdesk -FullName 'Hotline Support' -Password $password -PasswordNeverExpires | Out-Null
    Add-LocalGroupMember -SID S-1-5-32-545 -Member hdesk
    Add-LocalGroupMember -Group Support -Member hdesk
}
New-Item C:\Admin -ItemType Directory -Force | Out-Null
