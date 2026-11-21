# Serveur Ubuntu fraîchement installé chez « Ateliers Durand » : comptes à créer.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       sudo acl passwd login procps vim-tiny nano less bash-completion tree \
    && rm -rf /var/lib/apt/lists/*
# Un salarié parti récemment : son compte existe encore.
RUN useradd -m -s /bin/bash -c "Paul Leroy (parti)" pleroy \
    && echo 'pleroy:Ancien2023!' | chpasswd \
    && mkdir -p /home/pleroy/Documents \
    && echo "Inventaire des postes 2023" > /home/pleroy/Documents/inventaire.txt \
    && echo "Contrat fournisseur" > /home/pleroy/Documents/contrat.txt \
    && chown -R pleroy:pleroy /home/pleroy
# Claire Petit vient de se marier : son compte doit être renommé (cmoreau).
RUN useradd -m -u 1600 -s /bin/bash -c "Claire Petit" cpetit \
    && echo "Notes de reunion" > /home/cpetit/notes.txt \
    && chown cpetit:cpetit /home/cpetit/notes.txt
WORKDIR /root
CMD ["sleep", "infinity"]
