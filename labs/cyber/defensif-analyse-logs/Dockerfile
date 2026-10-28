# Lab défensif « Analyse de logs » : un poste d'analyste avec les journaux d'un incident déjà survenu.
# Tout est local et statique : on enquête, on ne lance rien vers l'extérieur.
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 grep gawk coreutils less vim-tiny procps ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY seed/generer.py /opt/generer.py
RUN python3 /opt/generer.py && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
