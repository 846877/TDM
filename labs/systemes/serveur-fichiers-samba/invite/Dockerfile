# Poste du réseau Wi-Fi invités : client SMB (ne doit pas pouvoir utiliser les partages).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       smbclient openssh-server iproute2 iputils-ping netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
