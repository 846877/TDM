# Mise en situation (poste) : une fois PC01 joint, plusieurs pannes sont posées.
# Sur SRV-DC01 (à distance) : redirecteur DNS faux, enregistrements SRV du localisateur supprimés, mot de passe
# du compte ordinateur PC01 changé dans l'annuaire seulement (canal sécurisé rompu).
# Sur PC01 : service de temps désactivé et mal configuré, horloge en avance, DNS vers une adresse inexistante.
$ErrorActionPreference = 'Stop'
$cred = New-Object PSCredential 'DURAND\vagrant', (ConvertTo-SecureString 'vagrant' -AsPlainText -Force)
Invoke-Command -ComputerName SRV-DC01 -Credential $cred -ScriptBlock {
    $ErrorActionPreference = 'Stop'
    Set-DnsServerForwarder -IPAddress 192.0.2.53
    Get-DnsServerResourceRecord -ZoneName _msdcs.durand.lan -RRType Srv |
        Where-Object { $_.HostName -like '_ldap._tcp.dc*' -or $_.HostName -like '_kerberos._tcp.dc*' } |
        Remove-DnsServerResourceRecord -ZoneName _msdcs.durand.lan -Force
    $alea = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    Set-ADAccountPassword -Identity 'PC01$' -Reset -NewPassword (ConvertTo-SecureString "$alea!9a" -AsPlainText -Force)
}
New-Item C:\Admin -ItemType Directory -Force | Out-Null
w32tm /config /manualpeerlist:"horloge.invalid,0x8" /syncfromflags:manual | Out-Null
Stop-Service W32Time -Force
Set-Service W32Time -StartupType Disabled
Set-Date (Get-Date).AddMinutes(3) | Out-Null
Set-DnsClientServerAddress -InterfaceAlias LAN, NAT -ServerAddresses 192.168.10.53
Clear-DnsClientCache
