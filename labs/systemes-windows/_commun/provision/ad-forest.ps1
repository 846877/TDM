# Promotion automatique du premier contrôleur de domaine (labs qui ont besoin d'un domaine tout prêt).
# Vagrant redémarre la VM juste après (option reboot: true), puis lance ad-ready.ps1.
param(
    [Parameter(Mandatory)][string]$Domain,
    [Parameter(Mandatory)][string]$Netbios
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ((Get-CimInstance Win32_ComputerSystem).DomainRole -ge 4) {
    Write-Host '[TDM] Déjà contrôleur de domaine'
    return
}
Write-Host '[TDM] Installation du rôle AD DS'
Install-WindowsFeature AD-Domain-Services, DNS -IncludeManagementTools | Out-Null
# Le compte Administrateur local devient l'administrateur du domaine : son mot de passe doit être complexe.
$password = ConvertTo-SecureString 'Azerty123!' -AsPlainText -Force
Get-LocalUser | Where-Object { $_.SID -like '*-500' } | Set-LocalUser -Password $password
Write-Host "[TDM] Création de la forêt $Domain (quelques minutes)"
Import-Module ADDSDeployment
Install-ADDSForest -DomainName $Domain -DomainNetbiosName $Netbios -InstallDns `
    -SafeModeAdministratorPassword $password -DomainMode WinThreshold -ForestMode WinThreshold `
    -NoRebootOnCompletion -Force | Out-Null
