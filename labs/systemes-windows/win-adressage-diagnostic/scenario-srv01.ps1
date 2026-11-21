# SRV01 : serveur DNS (zone durand.lan et zone inverse) et site intranet (IIS), répond au ping.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Install-WindowsFeature DNS, Web-Server -IncludeManagementTools | Out-Null
if (-not (Get-DnsServerZone durand.lan -ErrorAction SilentlyContinue)) {
    Add-DnsServerPrimaryZone -Name durand.lan -ZoneFile durand.lan.dns
    Add-DnsServerPrimaryZone -NetworkId 192.168.10.0/24 -ZoneFile 10.168.192.in-addr.arpa.dns
    Add-DnsServerResourceRecordA -ZoneName durand.lan -Name srv01 -IPv4Address 192.168.10.10 -CreatePtr
    Add-DnsServerResourceRecordCName -ZoneName durand.lan -Name intranet -HostNameAlias srv01.durand.lan
    Add-DnsServerResourceRecordA -ZoneName durand.lan -Name mail -IPv4Address 192.168.10.25 -CreatePtr
    Add-DnsServerResourceRecordMX -ZoneName durand.lan -Name . -MailExchange mail.durand.lan -Preference 10
    Add-DnsServerResourceRecordA -ZoneName durand.lan -Name imprimante-rdc -IPv4Address 192.168.10.50 -CreatePtr
}
Set-Content C:\inetpub\wwwroot\index.html '<h1>Intranet Ateliers Durand</h1>' -Encoding UTF8
Enable-NetFirewallRule -Name FPS-ICMP4-ERQ-In -ErrorAction SilentlyContinue
if (-not (Get-NetFirewallRule -Name TDM-Ping -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name TDM-Ping -DisplayName 'Ping (ICMPv4) depuis le LAN' -Protocol ICMPv4 -IcmpType 8 `
        -Direction Inbound -Action Allow -Profile Any | Out-Null
}
