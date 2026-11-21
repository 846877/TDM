#!/bin/sh
# Démarre (ou redémarre) la cible web vulnérable sur 127.0.0.1:80, en arrière-plan.
pkill -f /opt/cible/serveur.py 2>/dev/null
nohup python3 /opt/cible/serveur.py >/var/log/cible.log 2>&1 &
# Attendre qu'elle réponde
for i in $(seq 1 20); do
  curl -s -o /dev/null http://localhost/ && break
  sleep 0.5
done
