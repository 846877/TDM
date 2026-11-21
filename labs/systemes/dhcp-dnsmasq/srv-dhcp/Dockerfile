# Serveur DHCP/DNS : dnsmasq installé mais ni configuré ni démarré.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server dnsmasq tcpdump iproute2 iputils-ping dnsutils procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'conf-dir=/etc/dnsmasq.d/,*.conf' >> /etc/dnsmasq.conf \
    && mkdir -p /var/lib/misc
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
