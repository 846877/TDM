#!/bin/sh
# Simule un traitement oublié qui garde un verrou exclusif sur la table clients de la base ventes.
# Lancé automatiquement au démarrage du lab.
PGAPPNAME=traitement-bloquant psql -q -U postgres -d ventes \
  -c "BEGIN; LOCK TABLE clients IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(86400);" >/dev/null 2>&1
