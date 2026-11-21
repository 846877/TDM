# Poste d'administration (LAN + réseau d'administration hors bande).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-client iproute2 iputils-ping traceroute dnsutils netcat-openbsd curl tcpdump nmap \
       vim-tiny nano less bash-completion ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY commun/admin-init.sh /usr/local/bin/admin-init.sh
COPY commun/nommer-interfaces.sh /usr/local/bin/nommer-interfaces.sh
COPY commun/ssh_config /etc/ssh/ssh_config.d/lab.conf
COPY admin/hotes.conf /etc/ssh/ssh_config.d/00-hotes.conf
COPY admin/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/admin-init.sh /usr/local/bin/nommer-interfaces.sh /usr/local/bin/role.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/admin-init.sh"]
CMD ["sleep", "infinity"]
