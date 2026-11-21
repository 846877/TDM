# Serveur de fichiers d'« Ateliers Durand » : espace disque, nettoyage, images disque, fstab, archives.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       fdisk lsof psmisc zip unzip xz-utils tree file nano vim-tiny less bash-completion \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /srv/partage/atelier /srv/partage/compta/2025 /srv/partage/commercial /srv/cache/sessions \
             /srv/archives-2023 /var/log/appli \
    && head -c 40M /dev/zero > /srv/partage/atelier/plans-usine.dwg \
    && head -c 5M /dev/zero > /srv/partage/compta/2025/grand-livre.xlsx \
    && printf 'bilan 2025\n' > /srv/partage/compta/2025/bilan.txt \
    && head -c 12M /dev/zero > /srv/partage/commercial/catalogue.pdf \
    && for m in 01 02 03 04 05 06; do printf 'rapport %s/2023\n' $m > /srv/archives-2023/rapport-2023-$m.txt; done \
    && cp /usr/bin/sleep /usr/local/bin/appli-dbg \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY inventaire-disques.txt /root/inventaire-disques.txt
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
