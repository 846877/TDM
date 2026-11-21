# Poste de contrôle Ansible (utilisateur eleve) avec un projet de départ.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ansible-core openssh-client python3 sudo nano vim less curl tree \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash eleve \
    && echo "eleve ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/eleve
COPY --chown=eleve:eleve ansible/ /home/eleve/ansible/
COPY demarrer.sh /usr/local/bin/demarrer.sh
RUN chmod +x /usr/local/bin/demarrer.sh
WORKDIR /home/eleve/ansible
CMD ["/usr/local/bin/demarrer.sh"]
