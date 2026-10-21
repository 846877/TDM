#!/bin/bash
# Préparation du moteur Docker de TDM (exécutée une fois, au premier `vagrant up`).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "Installation de Docker Engine et du plugin compose…"
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2

# dockerd écoute aussi en tcp (sans TLS) pour l'hôte. La VM n'a qu'une carte NAT : le port 2375 n'est
# joignable que par la redirection de VirtualBox, limitée à 127.0.0.1 sur l'hôte (voir Vagrantfile).
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/tdm.conf <<'CONF'
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd -H fd:// -H tcp://0.0.0.0:2375 --containerd=/run/containerd/containerd.sock
CONF

mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'CONF'
{
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"}
}
CONF

# Labs Kubernetes (k3s), observabilité : beaucoup de fichiers surveillés.
cat > /etc/sysctl.d/90-tdm.conf <<'CONF'
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches = 524288
vm.max_map_count = 262144
CONF
sysctl --system >/dev/null

# Un peu d'échange : un lab gourmand ralentit au lieu d'être tué faute de mémoire.
if [ ! -f /swapfile-tdm ]; then
  fallocate -l 2G /swapfile-tdm
  chmod 600 /swapfile-tdm
  mkswap /swapfile-tdm >/dev/null
  echo "/swapfile-tdm none swap sw 0 0" >> /etc/fstab
fi
swapon /swapfile-tdm 2>/dev/null || true

usermod -aG docker vagrant
systemctl daemon-reload
systemctl enable docker
systemctl restart docker
docker version --format 'Moteur Docker prêt : {{.Server.Version}}'
