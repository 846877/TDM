# Serveur applicatif Ubuntu dont plusieurs services sont en panne (pannes injectées par entrypoint.sh).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       nginx openssh-server cron logrotate busybox socat netcat-openbsd curl lsof psmisc procps iproute2 \
       file dos2unix vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/pam_loginuid.so/s/^/#/' /etc/pam.d/cron \
    && rm -f /etc/nginx/sites-enabled/default \
    && useradd -r -s /usr/sbin/nologin -d /srv/appli appli \
    && useradd -m -s /bin/bash comptable
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
COPY journal-appli /usr/local/bin/journal-appli
COPY appli-service /usr/local/bin/appli-service
RUN chmod +x /usr/local/sbin/entrypoint.sh /usr/local/bin/journal-appli /usr/local/bin/appli-service
WORKDIR /root
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
CMD ["sleep", "infinity"]
