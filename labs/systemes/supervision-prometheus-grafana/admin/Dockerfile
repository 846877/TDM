# Poste d'administration : SSH, curl, jq. /srv/prometheus est le volume de configuration de Prometheus.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-client curl jq iproute2 iputils-ping dnsutils netcat-openbsd \
       vim-tiny nano less bash-completion ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY commun/admin-init.sh /usr/local/bin/admin-init.sh
COPY commun/ssh_config /etc/ssh/ssh_config.d/lab.conf
# Même contenu que dans l'image Prometheus : le volume partagé démarre identique quel que soit l'ordre.
COPY prometheus/prometheus.yml /srv/prometheus/prometheus.yml
RUN chmod +x /usr/local/bin/admin-init.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/admin-init.sh"]
CMD ["sleep", "infinity"]
