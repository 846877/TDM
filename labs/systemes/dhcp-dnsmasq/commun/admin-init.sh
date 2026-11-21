#!/bin/sh
# Poste d'administration : crée la clé SSH d'administration du lab et la partage avec les serveurs
# par le volume nommé /lab-ssh (les serveurs l'ajoutent à leur authorized_keys au démarrage).
mkdir -p /root/.ssh /lab-ssh
chmod 700 /root/.ssh
if [ ! -s /lab-ssh/id_ed25519.pub ]; then
  rm -f /lab-ssh/id_ed25519 /lab-ssh/id_ed25519.pub
  ssh-keygen -q -t ed25519 -N '' -C admin@lab -f /lab-ssh/id_ed25519
fi
cp /lab-ssh/id_ed25519 /lab-ssh/id_ed25519.pub /root/.ssh/
chmod 600 /root/.ssh/id_ed25519
[ -x /usr/local/bin/role.sh ] && /usr/local/bin/role.sh
exec "$@"
