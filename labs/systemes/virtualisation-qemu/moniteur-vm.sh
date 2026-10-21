#!/bin/sh
# Envoie une commande au moniteur QEMU d'une VM (socket /srv/vms/<vm>.monitor) et affiche la réponse.
# Usage : moniteur-vm vm1 "info status"      (sans commande : session interactive, Ctrl+C pour quitter)
vm=${1:-vm1}
shift 2>/dev/null
if [ $# -gt 0 ]; then
  printf '%s\n' "$*" | socat -t 5 - "UNIX-CONNECT:/srv/vms/$vm.monitor" | tr -d '\r' | grep -v '^(qemu)\|^QEMU .* monitor'
else
  exec socat -,escape=0x03 "UNIX-CONNECT:/srv/vms/$vm.monitor"
fi
