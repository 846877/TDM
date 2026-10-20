# Serveur de fichiers de « Ateliers Durand » : utilisateurs déjà créés, arborescence à construire.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       acl sudo procps vim-tiny nano less tree bash-completion \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 2001 compta && groupadd -g 2002 rh && groupadd -g 2004 direction \
    && groupadd -g 2100 personnel \
    && useradd -m -s /bin/bash -c "Alice Moreau" -G compta,personnel alice \
    && useradd -m -s /bin/bash -c "Bruno Petit" -G compta,personnel bruno \
    && useradd -m -s /bin/bash -c "Chloe Roux" -G rh,personnel chloe \
    && useradd -m -s /bin/bash -c "Dimitri Blanc" -G direction,personnel dimitri
# Héritage de l'ancien serveur : des archives aux droits douteux.
RUN mkdir -p /srv/partages/archives/2019 /srv/partages/archives/outils \
    && echo "Budget 2019" > /srv/partages/archives/2019/budget.txt \
    && echo "Notes de frais 2019" > /srv/partages/archives/2019/frais.txt \
    && echo "Liste du personnel 2019" > /srv/partages/archives/2019/personnel.txt \
    && chmod 777 /srv/partages/archives/2019 && chmod 666 /srv/partages/archives/2019/*.txt \
    && chown -R 1500:1500 /srv/partages/archives/2019 \
    && cp /usr/bin/id /srv/partages/archives/outils/diag && chmod 4755 /srv/partages/archives/outils/diag
# Procédures du service informatique à publier dans le dossier commun.
RUN mkdir -p /srv/procedures/2026 \
    && echo "Procedure de sauvegarde" > /srv/procedures/2026/sauvegarde.txt \
    && echo "Procedure d'arrivee d'un salarie" > /srv/procedures/2026/arrivee.txt
WORKDIR /srv/partages
CMD ["sleep", "infinity"]
