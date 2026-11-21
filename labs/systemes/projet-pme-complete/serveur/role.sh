#!/bin/sh
/usr/local/bin/nommer-interfaces.sh
cron
case "$ROLE" in
  srv)
    echo "<h1>Site public PME Durand</h1>" > /var/www/html/index.html
    nginx
    ;;
  nas)
    id sauvegarde >/dev/null 2>&1 || useradd -m -s /bin/bash sauvegarde
    mkdir -p /sauvegardes
    chown sauvegarde:sauvegarde /sauvegardes
    chmod 750 /sauvegardes
    ;;
esac
