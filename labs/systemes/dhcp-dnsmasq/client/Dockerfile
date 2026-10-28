# Poste client : demande une adresse en DHCP toutes les ~10 s et publie son bail sur http://<poste>/bail.txt.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends busybox iproute2 \
    && rm -rf /var/lib/apt/lists/*
COPY client/udhcpc-script.sh /usr/local/bin/udhcpc-script
COPY client/client.sh /usr/local/bin/client.sh
RUN chmod +x /usr/local/bin/udhcpc-script /usr/local/bin/client.sh
ENTRYPOINT ["/usr/local/bin/client.sh"]
