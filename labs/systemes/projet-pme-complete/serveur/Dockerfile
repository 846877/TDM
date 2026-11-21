# Serveurs de la PME : srv (web, fichiers Samba) et nas (cible de sauvegarde rsync).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server openssh-client samba smbclient nginx rsync cron sudo dnsutils iproute2 iputils-ping \
       netcat-openbsd curl procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/pam_loginuid.so/s/^/#/' /etc/pam.d/cron
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY commun/nommer-interfaces.sh /usr/local/bin/nommer-interfaces.sh
COPY serveur/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/nommer-interfaces.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
