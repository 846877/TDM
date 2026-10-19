# PowerShell 7 (image officielle Microsoft) avec les données d'exploitation du service informatique.
FROM mcr.microsoft.com/powershell:7.4-ubuntu-22.04
COPY ps/ /srv/ps/
RUN mkdir -p /srv/ps/scripts /srv/ps/sortie
WORKDIR /srv/ps
CMD ["sleep", "infinity"]
