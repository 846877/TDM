#!/bin/sh
# Clé du kit PRA : autorisée pour le compte « sauvegarde », copiée dans le volume partagé avec srv-neuf.
if [ ! -s /kit-pra-partage/cle-sauvegarde ]; then
  ssh-keygen -q -t ed25519 -N '' -C kit-pra -f /kit-pra-partage/cle-sauvegarde
fi
mkdir -p /home/sauvegarde/.ssh
cp /kit-pra-partage/cle-sauvegarde.pub /home/sauvegarde/.ssh/authorized_keys
chown -R sauvegarde:sauvegarde /home/sauvegarde/.ssh
chmod 700 /home/sauvegarde/.ssh
chmod 600 /home/sauvegarde/.ssh/authorized_keys
