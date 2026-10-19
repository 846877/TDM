#!/bin/sh
# Câblage de la salle informatique : un poste (espace de noms) par port du futur switch.
#   port    poste          adresse             bureau
#   sw-p1   pc-compta1     192.168.10.11/24    comptabilité
#   sw-p2   pc-compta2     192.168.10.12/24    comptabilité
#   sw-p3   pc-rh1         192.168.20.11/24    ressources humaines
#   sw-p4   srv-fichiers   192.168.30.10/24    salle serveurs
#   sw-p5   pc-nouveau     192.168.10.13/24    bureau RH (mal configuré)
#   sw-p6   pc-invite      192.168.40.10/24    salle d'attente (invités)
#   sw-p7   prise-reunion  192.168.10.99/24    prise murale libre de la salle de réunion
#   sw-p8   routeur        (aucune)            liaison vers le routeur
set -e
poste() { # poste <nom> <port> <adresse/prefixe> <passerelle>
  ip netns add "$1"
  ip link add "$2" type veth peer name eth0 netns "$1"
  ip link set "$2" up
  ip -n "$1" link set lo up
  ip -n "$1" link set eth0 up
  if [ -n "$3" ]; then
    ip -n "$1" addr add "$3" dev eth0
    ip -n "$1" route add default via "$4"
  fi
}
# Au redémarrage du conteneur, les anciens espaces de noms ne sont plus valides.
for n in pc-compta1 pc-compta2 pc-rh1 srv-fichiers pc-nouveau pc-invite prise-reunion routeur; do ip netns del "$n" 2>/dev/null || true; done
poste pc-compta1   sw-p1 192.168.10.11/24 192.168.10.254
poste pc-compta2   sw-p2 192.168.10.12/24 192.168.10.254
poste pc-rh1       sw-p3 192.168.20.11/24 192.168.20.254
poste srv-fichiers sw-p4 192.168.30.10/24 192.168.30.254
poste pc-nouveau   sw-p5 192.168.10.13/24 192.168.10.254
poste pc-invite    sw-p6 192.168.40.10/24 192.168.40.254
poste prise-reunion sw-p7 192.168.10.99/24 192.168.10.254
poste routeur      sw-p8 "" ""
