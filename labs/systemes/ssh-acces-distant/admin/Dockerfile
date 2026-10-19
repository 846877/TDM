# Poste d'administration : client SSH, rsync et quelques fichiers à déployer.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-client rsync iputils-ping dnsutils netcat-openbsd procps vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/*
COPY site/ /root/site/
COPY maj.sh /root/outils/maj.sh
RUN chmod +x /root/outils/maj.sh && mkdir -p /root/logs
WORKDIR /root
CMD ["sleep", "infinity"]
