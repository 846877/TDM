#!/bin/sh
# Prépare les fichiers du lab « Premiers pas sous Linux » (exécuté une fois pendant la construction).
set -e

# Dossier d'accueil : fichiers visibles, fichiers cachés, modèles de documents.
mkdir -p /srv/accueil/modeles
cat > /srv/accueil/bienvenue.txt <<'EOF'
Bienvenue chez Ateliers Durand !
Ton poste est prêt. Les modèles de documents sont dans le dossier modeles.
Pense à lire aussi les fichiers cachés de ce dossier.
EOF
printf 'poste=PC-TECH-07\ncode=ATD-4821\n' > /srv/accueil/.config-poste
printf 'ne plus utiliser ce fichier\n' > /srv/accueil/.ancien-memo
for m in courrier facture devis; do
  printf 'Modèle de %s - Ateliers Durand\n' "$m" > "/srv/accueil/modeles/$m.txt"
done

# Annuaire interne (séparateur ;).
cat > /srv/accueil/annuaire.csv <<'EOF'
nom;prenom;service;telephone;ville
Durand;Paul;direction;04 72 10 20 01;Lyon
Martin;Sophie;compta;04 72 10 20 11;Lyon
Leroy;Martin;atelier;04 72 10 20 35;Villeurbanne
Bernard;Lucie;compta;04 72 10 20 12;Lyon
Petit;Hugo;commercial;04 72 10 20 21;Lyon
Robert;Emma;atelier;04 72 10 20 36;Villeurbanne
Richard;Louis;informatique;04 72 10 20 41;Lyon
Moreau;Chloé;rh;04 72 10 20 05;Lyon
Simon;Nathan;commercial;04 72 10 20 22;Grenoble
Laurent;Léa;atelier;04 72 10 20 37;Villeurbanne
Lefebvre;Jules;compta;04 72 10 20 13;Lyon
Michel;Manon;commercial;04 72 10 20 23;Grenoble
Garcia;Adam;atelier;04 72 10 20 38;Villeurbanne
David;Camille;informatique;04 72 10 20 42;Lyon
Bertrand;Inès;direction;04 72 10 20 02;Lyon
Roux;Théo;atelier;04 72 10 20 39;Villeurbanne
EOF

# Fichiers du dossier personnel de root.
printf 'Idées pour la migration :\n- inventaire\n- sauvegardes\n' > /root/brouillon.txt
mkdir -p /root/a-supprimer/vieux
printf 'obsolète\n' > /root/a-supprimer/notes.txt
printf 'obsolète\n' > /root/a-supprimer/vieux/ancien.txt
cat > /root/config-poste.ini <<'EOF'
# Configuration du poste de travail
serveur=srv-fichiers.durand.lan
mode=test
imprimante=
langue=fr
EOF

# Journal de démarrage de l'application (plus de 1000 lignes, quelques erreurs).
mkdir -p /var/log/appli
i=1
while [ $i -le 1287 ]; do
  s=$(( i % 60 )); m=$(( 30 + i / 60 ))
  if [ $(( i % 97 )) -eq 0 ]; then niveau="ERREUR connexion à la base refusée"; else niveau="INFO requête $i traitée"; fi
  printf '2026-10-19 08:%02d:%02d %s\n' "$m" "$s" "$niveau"
  i=$(( i + 1 ))
done > /var/log/appli/demarrage.log

# Partage de fichiers : une procédure enfouie et quelques gros fichiers.
mkdir -p /srv/partage/informatique/2025/procedures /srv/partage/informatique/2024 \
         /srv/partage/compta/2025 /srv/partage/atelier/plans /srv/partage/commercial
printf '%%PDF-1.4 procédure VPN\n' > /srv/partage/informatique/2025/procedures/procedure-vpn.pdf
printf 'procédure imprimante\n' > /srv/partage/informatique/2025/procedures/procedure-imprimante.txt
printf 'ancienne procédure\n' > /srv/partage/informatique/2024/procedure-vpn-ancienne.txt
head -c 3M /dev/urandom > /srv/partage/atelier/plans/plan-usine.dwg
head -c 2M /dev/urandom > /srv/partage/compta/2025/grand-livre.xlsx
head -c 1500K /dev/urandom > /srv/partage/commercial/catalogue.pdf
head -c 200K /dev/urandom > /srv/partage/commercial/tarifs.pdf
printf 'bilan\n' > /srv/partage/compta/2025/bilan.txt
