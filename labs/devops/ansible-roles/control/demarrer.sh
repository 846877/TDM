#!/bin/bash
# Crée (une fois) la paire de clés SSH du poste de contrôle et partage la clé publique avec les cibles.
if [ ! -s /cles/id_ed25519 ]; then
  ssh-keygen -q -t ed25519 -N '' -C ansible-controle -f /cles/id_ed25519
fi
install -d -o eleve -g eleve -m 700 /home/eleve/.ssh
install -o eleve -g eleve -m 600 /cles/id_ed25519 /home/eleve/.ssh/id_ed25519
install -o eleve -g eleve -m 644 /cles/id_ed25519.pub /home/eleve/.ssh/id_ed25519.pub
exec sleep infinity
