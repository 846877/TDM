#!/bin/sh
# État initial d'un serveur : annuaire du parc, et version de l'application métier (srv1 et srv2,
# tirée au hasard au premier démarrage).
mkdir -p /etc/parc
[ -f /etc/parc/hosts-parc ] || printf '10.178.0.11 srv1.parc.lan\n10.178.0.12 srv2.parc.lan\n10.178.0.13 srv3.parc.lan\n' > /etc/parc/hosts-parc
case "$(hostname)" in
  srv1|srv2)
    mkdir -p /etc/tdm
    [ -s /etc/tdm/version-appli ] || echo "2.$(shuf -i 1-9 -n 1).$(shuf -i 0-20 -n 1)" > /etc/tdm/version-appli
    ;;
esac
