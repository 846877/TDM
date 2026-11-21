#!/bin/sh
# Serveur du lab : autorise la clé du poste d'administration (volume /lab-ssh), démarre sshd,
# puis lance le rôle de la machine (/usr/local/bin/role.sh) s'il existe.
mkdir -p /root/.ssh /run/sshd
chmod 700 /root/.ssh
i=0
while [ ! -s /lab-ssh/id_ed25519.pub ] && [ $i -lt 60 ]; do sleep 1; i=$((i+1)); done
if [ -s /lab-ssh/id_ed25519.pub ] && ! grep -qF "$(cat /lab-ssh/id_ed25519.pub)" /root/.ssh/authorized_keys 2>/dev/null; then
  cat /lab-ssh/id_ed25519.pub >> /root/.ssh/authorized_keys
fi
chmod 600 /root/.ssh/authorized_keys 2>/dev/null
/usr/sbin/sshd
[ -x /usr/local/bin/role.sh ] && /usr/local/bin/role.sh
exec sleep infinity
