#!/bin/sh
# Docker numérote les interfaces (eth0, eth1...) dans un ordre imprévisible : on les renomme d'après
# leur sous-réseau. IFNAMES="10.1.1.=lan 10.0.12.=vers-r2 ..." (préfixe d'adresse = nom).
for pair in $IFNAMES; do
  pfx=${pair%%=*}
  nom=${pair#*=}
  dev=$(ip -o -4 addr show | awk -v p="$pfx" 'index($4, p) == 1 { print $2; exit }')
  if [ -n "$dev" ] && [ "$dev" != "$nom" ]; then
    ip link set "$dev" down
    ip link set "$dev" name "$nom"
    ip link set "$nom" up
  fi
done
# Pas de route par défaut vers le pont Docker : le routage est l'affaire du lab.
ip route del default 2>/dev/null || true
if [ -n "$PASSERELLE" ]; then
  ip route add default via "$PASSERELLE"
fi
exit 0
