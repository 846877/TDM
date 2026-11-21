#!/bin/sh
# Prépare chaque serveur selon son rôle (au premier démarrage).
cron
case "$ROLE" in
  fichiers)
    if [ ! -d /srv/donnees ]; then
      mkdir -p /srv/donnees/compta /srv/donnees/rh/contrats /srv/donnees/commun /srv/donnees/cache
      echo "Bilan 2025 - total actif 1 254 300 EUR" > /srv/donnees/compta/bilan-2025.txt
      echo "Factures fournisseurs octobre" > /srv/donnees/compta/factures-octobre.csv
      echo "Contrat de travail - Dupont Marie - CDI - reference RH-2023-117" > /srv/donnees/rh/contrats/contrat-dupont.txt
      echo "Contrat de travail - Martin Julien - CDD - reference RH-2024-042" > /srv/donnees/rh/contrats/contrat-martin.txt
      echo "Planning des congés" > /srv/donnees/commun/planning.txt
      echo "brouillon" > /srv/donnees/commun/rapport.tmp
      echo "temporaire" > /srv/donnees/compta/export.tmp
      head -c 1M /dev/zero > /srv/donnees/cache/miniatures.bin
    fi
    ;;
  sauvegarde)
    for u in borg miroir; do
      id $u >/dev/null 2>&1 || useradd -m -s /bin/bash $u
    done
    echo 'borg:Borg2024!' | chpasswd
    echo 'miroir:Miroir2024!' | chpasswd
    mkdir -p /srv/borg /srv/rsync
    chown borg:borg /srv/borg
    chown miroir:miroir /srv/rsync
    ;;
esac
