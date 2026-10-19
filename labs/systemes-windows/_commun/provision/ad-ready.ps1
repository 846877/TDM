# Après la promotion : attend qu'Active Directory réponde, donne les droits d'administration du domaine
# au compte vagrant (celui du terminal) et règle le DNS (adresse LAN seulement, redirecteur Internet).
param([Parameter(Mandatory)][string]$Domain)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Write-Host '[TDM] Attente des services Active Directory'
$deadline = (Get-Date).AddMinutes(15)
while ($true) {
    try { Get-ADDomain -ErrorAction Stop | Out-Null; break } catch {
        if ((Get-Date) -gt $deadline) { throw "Active Directory ne répond pas : $_" }
        Start-Sleep -Seconds 15
    }
}
foreach ($group in 'Domain Admins', 'Enterprise Admins', 'Schema Admins', 'Group Policy Creator Owners') {
    $members = Get-ADGroupMember $group | Select-Object -ExpandProperty SamAccountName
    if ($members -notcontains 'vagrant') { Add-ADGroupMember $group -Members vagrant }
}
# Le compte vagrant garde son mot de passe « vagrant » (labs uniquement !).
Set-ADUser vagrant -PasswordNeverExpires $true
# Redirecteur vers le DNS de VirtualBox (carte NAT) pour que le domaine résolve aussi Internet.
try {
    if (-not (Get-DnsServerForwarder).IPAddress) { Add-DnsServerForwarder -IPAddress 10.0.2.3 }
} catch { Write-Host "  redirecteur : $_" }
Set-DnsClientServerAddress -InterfaceAlias 'NAT' -ServerAddresses 127.0.0.1
# Le DC ne doit s'enregistrer dans le DNS qu'avec son adresse LAN (pas celle de la carte NAT).
Set-DnsClient -InterfaceAlias 'NAT' -RegisterThisConnectionsAddress $false -ErrorAction SilentlyContinue
Get-DnsServerResourceRecord -ZoneName $Domain -RRType A -ErrorAction SilentlyContinue |
    Where-Object { $_.RecordData.IPv4Address.IPAddressToString -like '10.0.2.*' } |
    Remove-DnsServerResourceRecord -ZoneName $Domain -Force -ErrorAction SilentlyContinue
$listen = (Get-NetIPAddress -InterfaceAlias 'LAN' -AddressFamily IPv4).IPAddress
dnscmd.exe /ResetListenAddresses $listen | Out-Null
ipconfig.exe /registerdns | Out-Null
Write-Host "[TDM] Domaine $Domain prêt"
