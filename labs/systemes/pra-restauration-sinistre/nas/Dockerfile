# NAS de sauvegarde : trois sauvegardes quotidiennes de l'ancien srv-web (dont une abîmée), accessibles au
# compte « sauvegarde ». Les sauvegardes sont fabriquées dans une étape séparée.
FROM ubuntu:24.04 AS fabrique
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends mariadb-server mariadb-client cron \
    && rm -rf /var/lib/apt/lists/*
COPY nas/fabriquer-sauvegardes.sh /fabriquer-sauvegardes.sh
RUN sh /fabriquer-sauvegardes.sh

FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server rsync iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash sauvegarde \
    && mkdir -p /srv/sauvegardes
COPY --from=fabrique /out/srv-web /srv/sauvegardes/srv-web
RUN chown -R sauvegarde:sauvegarde /srv/sauvegardes
COPY nas/role.sh /usr/local/bin/role.sh
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
