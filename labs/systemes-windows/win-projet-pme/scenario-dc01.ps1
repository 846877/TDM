# Mise en situation : domaine tout neuf, aucune OU personnalisée. La liste du personnel fournie par la
# direction attend dans C:\Admin\import\personnel.csv.
$ErrorActionPreference = 'Stop'
New-Item C:\Admin\import -ItemType Directory -Force | Out-Null
@'
Identifiant;Prenom;Nom;Service;Fonction
hgirard;Hugo;Girard;Direction;Gérant
nroussel;Nathalie;Roussel;Direction;Assistante de direction
slambert;Sophie;Lambert;Compta;Responsable comptable
mdupont;Marie;Dupont;Compta;Comptable
cmoreau;Chloé;Moreau;Atelier;Cheffe d'atelier
blefebvre;Bruno;Lefebvre;Atelier;Technicien
kbenali;Karim;Benali;Atelier;Technicien
lfontaine;Léa;Fontaine;Commercial;Commerciale
tmartin;Thomas;Martin;Commercial;Commercial
jroux;Julien;Roux;Informatique;Technicien support
'@ | Set-Content C:\Admin\import\personnel.csv -Encoding UTF8
