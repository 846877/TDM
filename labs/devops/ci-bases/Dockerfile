# Poste Ubuntu pour découvrir l'intégration continue : git, make, Python, pytest, pyflakes.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       sudo nano vim less git make python3 python3-pytest python3-pyflakes ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash eleve \
    && echo "eleve ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/eleve \
    && mkdir -p /srv/git /srv/ci /opt/ci-reference && chown -R eleve:eleve /srv
COPY --chown=eleve:eleve projet/ /home/eleve/projet/
COPY preparer.sh /tmp/preparer.sh
RUN cd /home/eleve/projet && sha256sum tests/*.py > /opt/ci-reference/tests.sha256
USER eleve
RUN sh /tmp/preparer.sh
WORKDIR /home/eleve/projet
