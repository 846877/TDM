# Serveur de fichiers : Samba installé avec la configuration Ubuntu par défaut, non démarré.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       samba samba-vfs-modules smbclient openssh-server iproute2 iputils-ping procps acl tree vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/samba /srv/partages/procedures \
    && printf 'Procédure d arrivée d un salarié\n' > /srv/partages/procedures/guide-arrivee.txt \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
