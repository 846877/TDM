# Mise en situation : PC01 n'a plus de route par défaut par la carte NAT de VirtualBox (qui reste joignable
# pour la gestion, 10.0.2.0/24 étant directement connecté). Une tâche planifiée la retire à chaque démarrage
# et toutes les heures, au cas où un renouvellement DHCP la remettrait.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin -ItemType Directory -Force | Out-Null
$script = 'C:\Admin\sans-route-nat.ps1'
Set-Content $script "Get-NetRoute -DestinationPrefix 0.0.0.0/0 -InterfaceAlias NAT -ErrorAction SilentlyContinue | Remove-NetRoute -Confirm:`$false"
& $script
$action = New-ScheduledTaskAction -Execute powershell.exe -Argument "-NoProfile -ExecutionPolicy Bypass -File $script"
$declencheurs = @((New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)))
Register-ScheduledTask -TaskName 'TDM - sans route NAT' -Action $action -Trigger $declencheurs -User SYSTEM -RunLevel Highest -Force | Out-Null
