# Passerelle de la PME (nftables, dnsmasq installés, non configurés) et « Internet ».
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server nftables dnsmasq dnsutils iproute2 iputils-ping traceroute netcat-openbsd curl socat \
       tcpdump procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'conf-dir=/etc/dnsmasq.d/,*.conf' >> /etc/dnsmasq.conf \
    && mkdir -p /var/lib/misc
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY commun/nommer-interfaces.sh /usr/local/bin/nommer-interfaces.sh
COPY routeur/role.sh /usr/local/bin/role.sh
COPY routeur/echo-ip.sh /usr/local/bin/echo-ip.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/nommer-interfaces.sh /usr/local/bin/role.sh /usr/local/bin/echo-ip.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
