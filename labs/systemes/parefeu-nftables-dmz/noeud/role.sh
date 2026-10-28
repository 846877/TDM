#!/bin/sh
/usr/local/bin/nommer-interfaces.sh
mkdir -p /www
case "$ROLE" in
  fw)
    # ulogd2 écrit les paquets journalisés par nftables (« log group 0 ») dans /var/log/ulog/syslogemu.log.
    ulogd -d
    ;;
  web)
    echo "<h1>Site public Ateliers Durand</h1>" > /www/index.html
    busybox httpd -p 80 -h /www
    ;;
  externe)
    # Serveur « Internet » qui renvoie l'adresse source vue de l'extérieur.
    socat TCP-LISTEN:80,fork,reuseaddr EXEC:/usr/local/bin/echo-ip.sh >/dev/null 2>&1 &
    ;;
esac
