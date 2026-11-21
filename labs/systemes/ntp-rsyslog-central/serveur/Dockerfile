# Serveur Ubuntu avec chrony, rsyslog et logrotate installés mais non configurés ni démarrés.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server chrony rsyslog logrotate iproute2 iputils-ping netcat-openbsd procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/^module(load="imklog"/#&/' /etc/rsyslog.conf
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY serveur/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
