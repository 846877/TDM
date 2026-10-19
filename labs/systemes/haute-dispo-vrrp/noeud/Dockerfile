# Routeurs (keepalived installé, non configuré), poste et serveur.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server keepalived rsyslog iproute2 iputils-ping iputils-arping netcat-openbsd curl busybox \
       tcpdump procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/^module(load="imklog"/#&/' /etc/rsyslog.conf
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY commun/nommer-interfaces.sh /usr/local/bin/nommer-interfaces.sh
COPY noeud/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/nommer-interfaces.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
