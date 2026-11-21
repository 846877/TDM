# Jonction automatique d'une VM au domaine du lab (labs où le poste doit déjà être dans le domaine).
# Vagrant redémarre la VM juste après (option reboot: true).
param(
    [Parameter(Mandatory)][string]$Domain,
    [Parameter(Mandatory)][string]$Netbios
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ((Get-CimInstance Win32_ComputerSystem).PartOfDomain) {
    Write-Host '[TDM] Déjà membre du domaine'
    return
}
# Toutes les requêtes DNS vont au contrôleur de domaine (il relaie Internet), y compris par la carte NAT.
$dns = (Get-DnsClientServerAddress -InterfaceAlias 'LAN' -AddressFamily IPv4).ServerAddresses
if (-not $dns) { throw 'Pas de serveur DNS sur la carte LAN : indique dns: dans le Vagrantfile' }
Set-DnsClientServerAddress -InterfaceAlias 'NAT' -ServerAddresses $dns
Write-Host "[TDM] Attente du contrôleur de domaine $Domain"
$deadline = (Get-Date).AddMinutes(15)
while (-not (Resolve-DnsName "_ldap._tcp.dc._msdcs.$Domain" -Type SRV -ErrorAction SilentlyContinue)) {
    if ((Get-Date) -gt $deadline) { throw "Le domaine $Domain est introuvable (DNS de la carte LAN ?)" }
    Start-Sleep -Seconds 15
}
$credential = New-Object PSCredential("$Netbios\vagrant", (ConvertTo-SecureString 'vagrant' -AsPlainText -Force))
Add-Computer -DomainName $Domain -Credential $credential -Force
Write-Host "[TDM] Membre du domaine $Domain (redémarrage)"
