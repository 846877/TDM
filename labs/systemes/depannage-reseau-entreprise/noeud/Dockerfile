# Machines du réseau en panne : routeur nftables, serveur web nginx, serveur DNS dnsmasq, poste client.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server nftables nginx dnsmasq-base dnsutils iproute2 iputils-ping traceroute netcat-openbsd \
       curl socat tcpdump procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY commun/nommer-interfaces.sh /usr/local/bin/nommer-interfaces.sh
COPY noeud/role.sh /usr/local/bin/role.sh
COPY noeud/echo-ip.sh /usr/local/bin/echo-ip.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/nommer-interfaces.sh /usr/local/bin/role.sh /usr/local/bin/echo-ip.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
