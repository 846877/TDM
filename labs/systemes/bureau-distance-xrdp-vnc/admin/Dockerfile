# Poste d'administration : SSH, netcat et openssl pour tester les services de bureau à distance.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-client iproute2 iputils-ping dnsutils netcat-openbsd curl openssl nmap \
       vim-tiny nano less bash-completion ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY commun/admin-init.sh /usr/local/bin/admin-init.sh
COPY commun/ssh_config /etc/ssh/ssh_config.d/lab.conf
RUN chmod +x /usr/local/bin/admin-init.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/admin-init.sh"]
CMD ["sleep", "infinity"]
