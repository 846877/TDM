# Lab offensif « Reconnaissance web » : la boîte à outils et la cible vulnérable sont dans le MÊME
# conteneur, isolé. L'élève attaque http://localhost : rien ne sort de la machine.
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      nmap nikto dirb curl ca-certificates python3 procps iproute2 less vim-tiny \
 && rm -rf /var/lib/apt/lists/*

# La cible volontairement vulnérable (petit site « Ateliers Durand »)
COPY cible/ /opt/cible/
# Démarrage de la cible au lancement du conteneur
COPY demarrer-cible.sh /usr/local/bin/demarrer-cible
RUN chmod +x /usr/local/bin/demarrer-cible && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
