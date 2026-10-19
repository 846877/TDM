# Préparation commune de toutes les VM Windows de TDM (lancé par Vagrant, en administrateur, via WinRM).
#  - cartes réseau renommées « NAT » (Vagrant) et « LAN » (réseau du lab), adresse fixe si demandée ;
#  - fuseau horaire de Paris et clavier français (AZERTY) pour la console et le bureau à distance ;
#  - OpenSSH Server avec PowerShell comme shell, et la clé du lab : c'est par là que passent le terminal
#    de la plateforme et les vérifications des exercices.
param(
    [Parameter(Mandatory)][string]$PublicKeyB64,
    [Parameter(Mandatory)][string]$LanMac,
    [string]$LanIp,
    [int]$Prefix = 24,
    [string]$Gateway,
    [string]$Dns
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Step($text) { Write-Host "[TDM] $text" }

# --- Confort : fuseau horaire, clavier, pas de veille -------------------------------------------
Step 'Fuseau horaire et clavier français'
try { Set-TimeZone -Id 'Romance Standard Time' } catch { Write-Host "  fuseau : $_" }
try {
    $langs = New-WinUserLanguageList -Language 'fr-FR'
    $langs.Add('en-US')
    Set-WinUserLanguageList -LanguageList $langs -Force
    Set-WinDefaultInputMethodOverride -InputTip '040C:0000040C'
} catch { Write-Host "  clavier : $_" }
try { powercfg /change standby-timeout-ac 0 | Out-Null; powercfg /hibernate off | Out-Null } catch { }

# --- Réseau -----------------------------------------------------------------------------------
Step "Cartes réseau (LAN = $LanMac)"
$lan = Get-NetAdapter -Physical | Where-Object { $_.MacAddress -eq $LanMac.ToUpper() }
if (-not $lan) { throw "Carte LAN $LanMac introuvable" }
Get-NetAdapter -Physical | Where-Object { $_.MacAddress -ne $LanMac.ToUpper() -and $_.Name -ne 'NAT' } |
    Select-Object -First 1 | Rename-NetAdapter -NewName 'NAT'
if ($lan.Name -ne 'LAN') { $lan | Rename-NetAdapter -NewName 'LAN'; $lan = Get-NetAdapter -Name 'LAN' }
# Le réseau du lab est un réseau privé (le profil Public bloque le partage de fichiers, le ping...).
Start-Sleep -Seconds 5
Get-NetConnectionProfile -InterfaceAlias 'LAN' -ErrorAction SilentlyContinue |
    Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue
if ($LanIp) {
    Get-NetIPAddress -InterfaceAlias 'LAN' -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -ne $LanIp } | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    if (-not (Get-NetIPAddress -InterfaceAlias 'LAN' -IPAddress $LanIp -ErrorAction SilentlyContinue)) {
        $params = @{ InterfaceAlias = 'LAN'; IPAddress = $LanIp; PrefixLength = $Prefix }
        if ($Gateway) { $params.DefaultGateway = $Gateway }
        New-NetIPAddress @params | Out-Null
    }
}
if ($Dns) { Set-DnsClientServerAddress -InterfaceAlias 'LAN' -ServerAddresses $Dns }
# Les requêtes DNS du lab passent d'abord par la carte LAN (domaine durand.lan).
Set-NetIPInterface -InterfaceAlias 'LAN' -InterfaceMetric 10 -ErrorAction SilentlyContinue
Set-NetIPInterface -InterfaceAlias 'NAT' -InterfaceMetric 50 -ErrorAction SilentlyContinue

# --- OpenSSH Server -----------------------------------------------------------------------------
Step 'OpenSSH Server'
if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {
    try {
        Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0' | Out-Null
    } catch { Write-Host "  Add-WindowsCapability a échoué ($_), installation depuis GitHub" }
}
if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {
    $zip = Join-Path $env:TEMP 'OpenSSH-Win64.zip'
    Invoke-WebRequest 'https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.5.0.0p1-Beta/OpenSSH-Win64.zip' `
        -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $env:ProgramFiles -Force
    & (Join-Path $env:ProgramFiles 'OpenSSH-Win64\install-sshd.ps1')
    $env:Path += ";$env:ProgramFiles\OpenSSH-Win64"
    [Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'Machine') +
        ";$env:ProgramFiles\OpenSSH-Win64", 'Machine')
}
Set-Service sshd -StartupType Automatic
Start-Service sshd   # le premier démarrage crée C:\ProgramData\ssh et les clés d'hôte
$shell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
New-Item 'HKLM:\SOFTWARE\OpenSSH' -Force | Out-Null
New-ItemProperty 'HKLM:\SOFTWARE\OpenSSH' -Name DefaultShell -Value $shell -PropertyType String -Force | Out-Null
if (-not (Get-NetFirewallRule -Name 'TDM-SSH' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'TDM-SSH' -DisplayName 'TDM - OpenSSH (terminal de la plateforme)' -Direction Inbound `
        -Protocol TCP -LocalPort 22 -Action Allow -Profile Any | Out-Null
}

# Clé du lab : vagrant est administrateur, sshd lit donc administrators_authorized_keys.
$key = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($PublicKeyB64))
$adminKeys = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
Set-Content -Path $adminKeys -Value $key -Encoding Ascii
icacls.exe $adminKeys /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null
$userSsh = 'C:\Users\vagrant\.ssh'
New-Item $userSsh -ItemType Directory -Force | Out-Null
Set-Content -Path (Join-Path $userSsh 'authorized_keys') -Value $key -Encoding Ascii
Restart-Service sshd
Step 'Prêt : terminal PowerShell par SSH'
