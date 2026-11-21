# Mise en situation : Paul Leroy (comptable parti hier) a encore un compte actif et administrateur.
$ErrorActionPreference = 'Stop'
$password = ConvertTo-SecureString 'Ancien2023!Mdp' -AsPlainText -Force
if (-not (Get-LocalUser pleroy -ErrorAction SilentlyContinue)) {
    New-LocalUser pleroy -FullName 'Paul Leroy' -Description 'Comptabilité' -Password $password | Out-Null
}
foreach ($sid in 'S-1-5-32-544', 'S-1-5-32-545') {
    if (-not (Get-LocalGroupMember -SID $sid | Where-Object Name -like '*\pleroy')) {
        Add-LocalGroupMember -SID $sid -Member pleroy
    }
}
New-Item C:\Admin -ItemType Directory -Force | Out-Null
