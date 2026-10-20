# Serveur d'« Ateliers Durand » : gestion des paquets avec APT et dpkg, dépôt interne dans /srv/depot.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       dpkg-dev nano vim-tiny less tree file bash-completion \
    && rm -rf /var/lib/apt/lists/*
COPY construire-depot.sh /usr/local/sbin/construire-depot.sh
RUN sh /usr/local/sbin/construire-depot.sh && rm /usr/local/sbin/construire-depot.sh
WORKDIR /root
CMD ["sleep", "infinity"]
