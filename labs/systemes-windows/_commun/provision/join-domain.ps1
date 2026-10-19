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
Write-Host "[TDM] Attente du contrôleur de domaine $Domain"
$deadline = (Get-Date).AddMinutes(15)
while (-not (Resolve-DnsName "_ldap._tcp.dc._msdcs.$Domain" -Type SRV -ErrorAction SilentlyContinue)) {
    if ((Get-Date) -gt $deadline) { throw "Le domaine $Domain est introuvable (DNS de la carte LAN ?)" }
    Start-Sleep -Seconds 15
}
$credential = New-Object PSCredential("$Netbios\vagrant", (ConvertTo-SecureString 'vagrant' -AsPlainText -Force))
Add-Computer -DomainName $Domain -Credential $credential -Force
Write-Host "[TDM] Membre du domaine $Domain (redémarrage)"
