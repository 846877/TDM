#!/bin/sh
# Boucle DHCP : DISCOVER / OFFER / REQUEST / ACK toutes les 10 secondes environ.
mkdir -p /www
echo "etat=attente" > /www/bail.txt
busybox httpd -p 80 -h /www
while true; do
  busybox udhcpc -i eth0 -q -n -t 3 -T 2 -s /usr/local/bin/udhcpc-script -x "hostname:$(hostname)" >/dev/null 2>&1
  sleep 10
done
