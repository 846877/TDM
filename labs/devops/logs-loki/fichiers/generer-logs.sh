#!/bin/bash
# Simule l'application « boutique » : écrit en continu des journaux JSON dans /var/log/boutique/app.log.
services=(panier paiement catalogue)
niveaux=(info info info info warn error)
mkdir -p /var/log/boutique
i=0
while true; do
  s=${services[RANDOM % 3]}
  n=${niveaux[RANDOM % 6]}
  d=$((RANDOM % 1200))
  u=$((RANDOM % 500))
  case $n in
    error) m="échec du traitement $s" ;;
    warn) m="traitement lent $s" ;;
    *) m="requête traitée $s" ;;
  esac
  printf '{"ts":"%s","niveau":"%s","service":"%s","message":"%s","duree_ms":%d,"user":"u%d","requete_id":"r%06d"}\n' \
    "$(date -u +%FT%TZ)" "$n" "$s" "$m" "$d" "$u" "$i" >> /var/log/boutique/app.log
  i=$((i + 1))
  sleep 0.3
done
