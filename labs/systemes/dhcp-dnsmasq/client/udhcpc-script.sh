#!/bin/sh
# Script appelé par udhcpc : ajoute l'adresse obtenue en adresse secondaire (l'adresse Docker reste
# en place) et publie le bail reçu dans /www/bail.txt.
B=/www/bail.txt
case "$1" in
  bound|renew)
    old=$(cat /run/dhcp-ip 2>/dev/null)
    if [ -n "$old" ] && [ "$old" != "$ip" ]; then
      ip addr del "$old/${mask:-24}" dev "$interface" 2>/dev/null
    fi
    ip addr add "$ip/${mask:-24}" dev "$interface" 2>/dev/null
    echo "$ip" > /run/dhcp-ip
    {
      echo "etat=ok"
      echo "ip=$ip"
      echo "masque=$subnet"
      echo "routeur=$router"
      echo "dns=$dns"
      echo "domaine=$domain"
      echo "bail=$lease"
      echo "serveur=$serverid"
    } > $B.tmp && mv $B.tmp $B
    ;;
  leasefail|nak)
    echo "etat=echec" > $B
    ;;
esac
exit 0
