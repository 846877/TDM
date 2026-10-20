# Poste Ubuntu avec Git, un dépôt partagé (/srv/git) et un collègue simulé (Charlie).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       sudo nano vim less git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash eleve \
    && echo "eleve ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/eleve \
    && mkdir -p /srv/git /srv/charlie && chown -R eleve:eleve /srv
COPY --chown=eleve:eleve preparer.sh /tmp/preparer.sh
COPY --chown=eleve:eleve outils/ /home/eleve/outils/
RUN chmod +x /home/eleve/outils/*.sh
USER eleve
RUN sh /tmp/preparer.sh
WORKDIR /home/eleve
