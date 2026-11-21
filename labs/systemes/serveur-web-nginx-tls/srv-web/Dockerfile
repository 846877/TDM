# Serveur web : nginx installé avec sa configuration Ubuntu par défaut, non démarré ; openssl et htpasswd.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       nginx openssl apache2-utils curl ca-certificates openssh-server iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/listen \[::\]/d' /etc/nginx/sites-available/default \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
