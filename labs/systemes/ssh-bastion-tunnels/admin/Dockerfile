# Poste d'administration sur le réseau bureautique.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-client iproute2 iputils-ping dnsutils netcat-openbsd curl procps \
       vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /root
CMD ["sleep", "infinity"]
