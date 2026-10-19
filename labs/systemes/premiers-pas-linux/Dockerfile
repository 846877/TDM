# Poste Linux d'un nouveau technicien d'« Ateliers Durand » : fichiers d'accueil, journal, annuaire, partage.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       nano vim-tiny less tree file bash-completion \
    && rm -rf /var/lib/apt/lists/*
COPY preparer.sh /usr/local/sbin/preparer.sh
RUN sh /usr/local/sbin/preparer.sh && rm /usr/local/sbin/preparer.sh
WORKDIR /root
CMD ["sleep", "infinity"]
