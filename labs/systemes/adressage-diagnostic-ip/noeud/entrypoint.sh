#!/bin/sh
# Passerelle par défaut vers le routeur du lab (au lieu du pont Docker).
if [ -n "$PASSERELLE" ]; then
  ip route del default 2>/dev/null || true
  ip route add default via "$PASSERELLE"
fi
mkdir -p /www
case "$ROLE" in
  routeur)
    ;;
  web)
    echo "<h1>Intranet Ateliers Durand</h1><p>Serveur srv-web</p>" > /www/index.html
    busybox httpd -p 80 -h /www
    ;;
  imprimante)
    echo "<h1>Imprimante RICOH IM C3000</h1><p>Numero de serie : IMP-4821-DR</p>" > /www/index.html
    busybox httpd -p 80 -h /www
    ;;
  bdd)
    socat TCP-LISTEN:5432,fork,reuseaddr SYSTEM:'echo PostgreSQL-16-durand' >/dev/null 2>&1 &
    ;;
  dns)
    dnsmasq --conf-file=/dev/null --conf-dir=/etc/dnsmasq.d --user=root
    ;;
esac
exec sleep infinity
