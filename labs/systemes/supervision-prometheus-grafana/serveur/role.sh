#!/bin/sh
# Rôle des serveurs supervisés. srv-web : nginx et cron démarrés, node exporter installé mais ARRÊTÉ.
# srv-bdd : node exporter déjà lancé, mais sur le port non standard 9101.
cron
case "$ROLE" in
  web)
    echo "<h1>Intranet Ateliers Durand</h1>" > /var/www/html/index.html
    nginx
    ;;
  bdd)
    nohup prometheus-node-exporter --web.listen-address=:9101 \
      --collector.textfile.directory=/var/lib/prometheus/node-exporter >/var/log/node-exporter.log 2>&1 &
    ;;
esac
