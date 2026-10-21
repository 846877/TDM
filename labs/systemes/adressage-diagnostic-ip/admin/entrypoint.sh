#!/bin/sh
# Le poste démarre sans passerelle : c'est au technicien de la configurer.
ip route del default 2>/dev/null || true
# Un agent d'inventaire tourne en local sur un port inconnu (exercice ss).
/usr/local/sbin/inventaire-agt TCP-LISTEN:8731,fork,reuseaddr SYSTEM:'echo inventaire-ok' >/dev/null 2>&1 &
exec "$@"
