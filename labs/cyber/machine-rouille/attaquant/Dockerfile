# Poste de l'attaquant de la machine « Rouille » : c'est ici que s'ouvre le terminal du lab.
# Il ne peut atteindre la cible que par le réseau (hôte « cible »), jamais son système de fichiers.
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl nmap iputils-ping netcat-openbsd python3 ca-certificates less vim-tiny procps iproute2 \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
