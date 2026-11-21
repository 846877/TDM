#!/bin/sh
# Trois vieux messages vers l'ancien fournisseur attendent dans la file de dépôt : ils partiront (et
# resteront bloqués) dès que Postfix sera démarré.
if [ ! -e /var/lib/postfix/.messages-anciens ]; then
  for i in 1 2 3; do
    printf 'Subject: Commande %s\n\nCommande envoyée avant la fermeture du fournisseur.\n' "$i" \
      | /usr/sbin/sendmail -f compta@durand.lan commandes@ancien-fournisseur.example 2>/dev/null
  done
  touch /var/lib/postfix/.messages-anciens
fi
