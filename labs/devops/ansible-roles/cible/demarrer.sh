#!/bin/bash
# Attend la clé publique du poste de contrôle (volume partagé), l'autorise pour deploy, puis lance sshd.
for i in $(seq 1 120); do [ -s /cles/id_ed25519.pub ] && break; sleep 1; done
install -o deploy -g deploy -m 600 /cles/id_ed25519.pub /home/deploy/.ssh/authorized_keys
exec /usr/sbin/sshd -D -e
