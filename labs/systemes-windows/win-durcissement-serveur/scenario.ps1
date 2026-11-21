# Mise en situation : un serveur installé « par défaut et un peu plus », avec plusieurs réglages faibles
# posés explicitement pour que chaque exercice parte d'un état connu (y compris sur les runners de la CI).
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
Copy-Item C:\Windows\System32\whoami.exe C:\Users\Public\outil.exe -Force   # « outil » déposé hors des dossiers système

function Set-Valeur([string]$Cle, [string]$Nom, $Valeur, [string]$Type = 'DWord') {
    if (-not (Test-Path $Cle)) { New-Item $Cle -Force | Out-Null }   # crée la clé et ses parents manquants
    Set-ItemProperty $Cle -Name $Nom -Value $Valeur -Type $Type
}

# AppLocker : aucune règle, service d'identité des applications arrêté et manuel.
Stop-Service AppIDSvc -Force -ErrorAction SilentlyContinue
sc.exe config AppIDSvc start= demand | Out-Null

# PowerShell : ni journalisation des blocs de script ni transcription.
foreach ($c in 'ScriptBlockLogging', 'Transcription') {
    Remove-Item "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\$c" -Recurse -Force -ErrorAction SilentlyContinue
}

# LSA non protégée et WDigest qui garde les mots de passe en clair en mémoire.
Set-Valeur 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' RunAsPPL 0
Set-Valeur 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest' UseLogonCredential 1

# LLMNR et NetBIOS actifs, SMB sans signature obligatoire.
Set-Valeur 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient' EnableMulticast 1
Get-ChildItem HKLM:\SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces | ForEach-Object {
    Set-ItemProperty $_.PSPath -Name NetbiosOptions -Value 0 -Type DWord
}
Set-SmbServerConfiguration -RequireSecuritySignature $false -Force

# SSL 3.0 et TLS 1.0 explicitement activés, .NET sans cryptographie forte.
foreach ($v in 'SSL 3.0', 'TLS 1.0') {
    foreach ($r in 'Server', 'Client') {
        $cle = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\$v\$r"
        Set-Valeur $cle Enabled 1
        Set-Valeur $cle DisabledByDefault 0
    }
}
foreach ($cle in 'HKLM:\SOFTWARE\Microsoft\.NETFramework\v4.0.30319', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\.NETFramework\v4.0.30319') {
    Set-Valeur $cle SchUseStrongCrypto 0
}

# Audit minimal : rien sur les ouvertures de session, la validation des identifiants et les processus.
foreach ($g in '{0CCE9215-69AE-11D9-BED3-505054503030}', '{0CCE922B-69AE-11D9-BED3-505054503030}', '{0CCE923F-69AE-11D9-BED3-505054503030}') {
    auditpol /set /subcategory:$g /success:disable /failure:disable | Out-Null
}
Set-Valeur 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit' ProcessCreationIncludeCmdLine_Enabled 0
wevtutil sl Security /ms:20971520

# NTLM : niveau d'authentification LAN Manager faible et condensats LM conservés.
Set-Valeur 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' LmCompatibilityLevel 1
Set-Valeur 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' NoLMHash 0

# Spouleur d'impression démarré sur un serveur qui n'imprime pas.
Set-Service Spooler -StartupType Automatic
Start-Service Spooler -ErrorAction SilentlyContinue
