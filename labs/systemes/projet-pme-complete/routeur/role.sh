#!/bin/sh
/usr/local/bin/nommer-interfaces.sh
case "$ROLE" in
  internet)
    # Le « fournisseur d'accès » route (à tort) les réseaux privés de la PME vers gw : sans pare-feu,
    # Internet pourrait les joindre directement. Serveur HTTP qui renvoie l'IP source vue de l'extérieur.
    ip route add 192.168.100.0/24 via 203.0.113.2
    ip route add 10.100.0.0/24 via 203.0.113.2
    socat TCP-LISTEN:80,fork,reuseaddr EXEC:/usr/local/bin/echo-ip.sh >/dev/null 2>&1 &
    ;;
esac
