# Serveur de base de données : MariaDB installé (non démarré), avec un compte anonyme et une base « test »
# hérités d'une vieille installation, un script SQL à importer et une sauvegarde à restaurer.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       mariadb-server mariadb-client cron openssh-server iproute2 iputils-ping procps gzip vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/pam_loginuid.so/s/^/#/' /etc/pam.d/cron \
    && mkdir -p /var/log/mysql && chown mysql:adm /var/log/mysql \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY srv-bdd/gestion.sql /root/gestion.sql
COPY srv-bdd/preparer.sh /usr/local/sbin/preparer.sh
RUN sh /usr/local/sbin/preparer.sh && rm /usr/local/sbin/preparer.sh
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY srv-bdd/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
