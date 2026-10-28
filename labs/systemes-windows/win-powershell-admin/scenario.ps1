# Mise en situation : fichiers d'entrée des scripts d'administration.
$ErrorActionPreference = 'Stop'
New-Item C:\Scripts\Donnees, C:\Scripts\Sortie, C:\Scripts\Telecharge -ItemType Directory -Force | Out-Null
$csv = @'
Prenom;Nom;Service;Fonction
Élodie;Le Gall;Compta;Comptable
François;Hervé;Atelier;Chef d'équipe
Anaïs;Dupont-Martin;RH;Chargée de recrutement
Jérôme;N'Diaye;Atelier;Soudeur
Chloé;Bérard;Direction;Assistante de direction
'@
# UTF-8 avec BOM : c'est ce que produit Excel (« CSV UTF-8 ») et ce que Windows PowerShell 5.1 lit sans surprise.
[IO.File]::WriteAllText('C:\Scripts\Donnees\nouveaux.csv', $csv, (New-Object Text.UTF8Encoding($true)))
Set-Content C:\Scripts\Donnees\serveurs.txt 'localhost', '127.0.0.1', 'srv-inexistant.invalid'
# Un script « téléchargé sur Internet » : Windows l'a marqué (flux Zone.Identifier).
Set-Content C:\Scripts\Telecharge\outil.ps1 "'Outil du prestataire'"
Set-Content C:\Scripts\Telecharge\outil.ps1 -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3"
