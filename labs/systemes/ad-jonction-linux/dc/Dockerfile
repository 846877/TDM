# Contrôleur de domaine DURAND.LAN : provisionné automatiquement au premier démarrage (role.sh).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server samba-ad-dc samba-ad-provision samba-common-bin samba-vfs-modules winbind \
       smbclient krb5-user ldb-tools dnsutils attr acl iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/*
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY dc/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
