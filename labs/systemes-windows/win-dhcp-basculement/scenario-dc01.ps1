# Mise en situation : SRV-DC01 est le seul serveur DHCP (autorisé dans l'annuaire) avec l'étendue LAN
# 192.168.10.100-200 et ses options. S'il tombe, plus aucun poste n'obtient d'adresse.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Install-WindowsFeature DHCP -IncludeManagementTools | Out-Null
netsh dhcp add securitygroups | Out-Null
Restart-Service DHCPServer
Set-ItemProperty HKLM:\SOFTWARE\Microsoft\ServerManager\Roles\12 -Name ConfigurationState -Value 2
if (-not (Get-DhcpServerInDC | Where-Object IPAddress -eq '192.168.10.10')) {
    Add-DhcpServerInDC -DnsName srv-dc01.durand.lan -IPAddress 192.168.10.10
}
if (-not (Get-DhcpServerv4Scope -ScopeId 192.168.10.0 -ErrorAction SilentlyContinue)) {
    Add-DhcpServerv4Scope -Name LAN -StartRange 192.168.10.100 -EndRange 192.168.10.200 -SubnetMask 255.255.255.0 -LeaseDuration 8.00:00:00
    Set-DhcpServerv4OptionValue -ScopeId 192.168.10.0 -DnsServer 192.168.10.10 -DnsDomain durand.lan -Router 192.168.10.254
}
