# Image commune aux machines du réseau (routeur, serveurs, imprimante) : le rôle est choisi par ROLE.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       iproute2 iputils-ping busybox dnsmasq socat tcpdump \
    && rm -rf /var/lib/apt/lists/*
COPY dnsmasq.conf /etc/dnsmasq.d/durand.conf
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
