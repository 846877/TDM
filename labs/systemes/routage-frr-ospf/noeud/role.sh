#!/bin/sh
# Interfaces nommées d'après leur réseau, puis FRRouting démarré (configuration vide) sur les routeurs.
/usr/local/bin/nommer-interfaces.sh
if [ "$ROLE" = routeur ]; then
  /usr/lib/frr/frrinit.sh start >/var/log/frr-start.log 2>&1
fi
