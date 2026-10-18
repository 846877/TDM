FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends sudo nano vim less procps tree \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash eleve \
    && echo "eleve ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/eleve
COPY donnees/ /home/eleve/donnees/
RUN chown -R eleve:eleve /home/eleve
USER eleve
WORKDIR /home/eleve
