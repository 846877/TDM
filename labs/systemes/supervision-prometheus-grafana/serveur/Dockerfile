# Serveurs Ubuntu à superviser : node exporter (paquet Ubuntu), nginx sur srv-web, cron.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server prometheus-node-exporter nginx cron curl iproute2 procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/pam_loginuid.so/s/^/#/' /etc/pam.d/cron \
    && mkdir -p /var/lib/prometheus/node-exporter
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY serveur/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
