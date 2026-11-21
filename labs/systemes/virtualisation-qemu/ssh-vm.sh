#!/bin/sh
# Connexion SSH à une VM CirrOS dont le port 22 est redirigé sur 127.0.0.1:<port> (cirros / gocubsgo).
# Usage : ssh-vm 2222 [commande...]
port=${1:-2222}
shift 2>/dev/null
exec sshpass -p gocubsgo ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR -o ConnectTimeout=10 -p "$port" cirros@127.0.0.1 "$@"
