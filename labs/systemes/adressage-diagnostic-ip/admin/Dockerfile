# Poste d'administration du technicien : outils de diagnostic réseau.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       iproute2 iputils-ping iputils-arping traceroute mtr-tiny dnsutils netcat-openbsd curl \
       tcpdump nmap ipcalc socat procps vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/* \
    && cp /usr/bin/socat /usr/local/sbin/inventaire-agt
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
