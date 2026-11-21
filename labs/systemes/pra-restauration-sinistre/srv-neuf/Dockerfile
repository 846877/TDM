# Serveur de remplacement installé à neuf : nginx, MariaDB et cron installés, rien de configuré ni démarré.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       nginx mariadb-server mariadb-client cron rsync openssh-server openssh-client curl iproute2 iputils-ping procps \
       vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/listen \[::\]/d' /etc/nginx/sites-available/default \
    && sed -i '/pam_loginuid.so/s/^/#/' /etc/pam.d/cron \
    && mkdir -p /run/mysqld /var/log/mysql && chown mysql:mysql /run/mysqld && chown mysql:adm /var/log/mysql \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY srv-neuf/role.sh /usr/local/bin/role.sh
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
