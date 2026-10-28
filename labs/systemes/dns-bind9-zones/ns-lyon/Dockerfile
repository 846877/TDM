# DNS de l'agence de Lyon (déjà en production) : zones lyon.durand.lan et fournisseur.example.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bind9 bind9-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/named && chown bind:bind /run/named
COPY ns-lyon/named.conf /etc/bind/named.conf
COPY ns-lyon/db.lyon.durand.lan ns-lyon/db.fournisseur.example /etc/bind/
RUN named-checkconf -z /etc/bind/named.conf
CMD ["named", "-g", "-u", "bind"]
