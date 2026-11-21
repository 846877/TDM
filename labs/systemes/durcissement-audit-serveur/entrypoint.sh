#!/bin/sh
# Démarrage « à l'ancienne » : chaque script exécutable de /etc/demarrage.d est lancé.
for s in /etc/demarrage.d/*.sh; do
  [ -x "$s" ] && "$s"
done
exec "$@"
