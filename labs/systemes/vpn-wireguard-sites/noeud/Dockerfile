# Passerelles VPN, postes et nomade : WireGuard (outils + wireguard-go en secours), nftables, outils réseau.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server wireguard-tools wireguard-go nftables iproute2 iputils-ping traceroute \
       netcat-openbsd curl busybox tcpdump procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /etc/wireguard && chmod 700 /etc/wireguard
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY commun/nommer-interfaces.sh /usr/local/bin/nommer-interfaces.sh
COPY noeud/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/nommer-interfaces.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
