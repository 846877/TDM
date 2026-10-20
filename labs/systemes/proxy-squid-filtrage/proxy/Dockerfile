# Proxy : Squid installé avec sa configuration Ubuntu par défaut, non démarré ; un ancien journal à analyser.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       squid apache2-utils curl openssh-server iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY proxy/ancien-journal.sh /usr/local/sbin/ancien-journal.sh
RUN sh /usr/local/sbin/ancien-journal.sh > /var/log/squid/access.log.1 && rm /usr/local/sbin/ancien-journal.sh \
    && chown proxy:proxy /var/log/squid/access.log.1
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
