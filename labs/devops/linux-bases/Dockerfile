FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends sudo nano vim less procps tree file \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash eleve \
    && echo "eleve ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/eleve
COPY donnees/ /home/eleve/donnees/
# Des archives de tailles variées pour l'exercice de recherche de fichiers.
RUN mkdir -p /home/eleve/donnees/archives/2025 \
    && cd /home/eleve/donnees/archives \
    && for f in lundi:12 mardi:340 mercredi:87 jeudi:150 vendredi:64; do head -c "${f#*:}K" /dev/zero > "backup-${f%%:*}.tar"; done \
    && for f in janvier:512 fevrier:3 mars:260 avril:45; do head -c "${f#*:}K" /dev/zero > "2025/export-${f%%:*}.csv"; done
# Un processus « gourmand » lancé au démarrage du lab (voir setup dans lab.yaml).
RUN printf '#!/bin/sh\necho $$ > /var/tmp/.gourmand.pid\nwhile true; do sleep 1; done\n' > /usr/local/bin/gourmand \
    && chmod 755 /usr/local/bin/gourmand
RUN chown -R eleve:eleve /home/eleve
USER eleve
WORKDIR /home/eleve
