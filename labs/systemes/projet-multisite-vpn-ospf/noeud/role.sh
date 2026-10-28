#!/bin/sh
/usr/local/bin/nommer-interfaces.sh
case "$ROLE" in
  routeur)
    # Au siège, le lien « lan » n'est qu'un support de VLAN : on retire l'adresse non tagguée.
    [ "$VIDER_LAN" = 1 ] && ip -4 addr flush dev lan
    # Configuration persistante éventuelle (après un redémarrage).
    [ -x /usr/local/bin/vlans-siege.sh ] && /usr/local/bin/vlans-siege.sh
    [ -f /etc/wireguard/wg0.conf ] && wg-quick up wg0 >/var/log/wg-quick.log 2>&1
    [ -f /etc/nftables.conf ] && nft -f /etc/nftables.conf
    /usr/lib/frr/frrinit.sh start >/var/log/frr-start.log 2>&1
    ;;
  vlan)
    # Hôte du siège dans un VLAN : interface tagguée sur le lien « lan », adresse non tagguée retirée.
    ip -4 addr flush dev lan
    ip link add link lan name "lan.$VLAN" type vlan id "$VLAN"
    ip addr add "$IPVLAN" dev "lan.$VLAN"
    ip link set "lan.$VLAN" up
    ip route add default via "$GWVLAN"
    if [ "$WEB" = 1 ]; then
      mkdir -p /www
      echo "<h1>Serveur du siege</h1>" > /www/index.html
      busybox httpd -p 80 -h /www
    fi
    ;;
esac
