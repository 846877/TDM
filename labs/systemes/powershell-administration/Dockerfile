# PowerShell 7 (image officielle Microsoft) avec les données d'exploitation du service informatique.
FROM mcr.microsoft.com/powershell:7.4-ubuntu-22.04
COPY ps/ /srv/ps/
RUN mkdir -p /srv/ps/scripts /srv/ps/sortie /srv/ps/archives \
    && for f in rapport-2015 devis-2017 bilan-2018 planning-recent notes-recentes; do echo "Document $f" > /srv/ps/archives/$f.txt; done \
    && touch -d 2015-06-30 /srv/ps/archives/rapport-2015.txt \
    && touch -d 2017-03-15 /srv/ps/archives/devis-2017.txt \
    && touch -d 2018-12-31 /srv/ps/archives/bilan-2018.txt
WORKDIR /srv/ps
CMD ["sleep", "infinity"]
