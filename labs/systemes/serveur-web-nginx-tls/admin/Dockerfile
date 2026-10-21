# Poste du LAN : navigateur en ligne de commande (curl), openssl, client SSH.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       curl openssl ca-certificates openssh-client iproute2 iputils-ping netcat-openbsd vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/*
COPY commun/admin-init.sh /usr/local/bin/admin-init.sh
COPY commun/ssh_config /etc/ssh/ssh_config.d/lab.conf
RUN chmod +x /usr/local/bin/admin-init.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/admin-init.sh"]
CMD ["sleep", "infinity"]
