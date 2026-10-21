# Serveurs Linux : compte tech (mot de passe Tech2024!). Sur le bastion, tech a sudo sans mot de passe.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server openssh-client sudo busybox netcat-openbsd iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd \
    && useradd -m -s /bin/bash -c "Technicien" tech \
    && echo 'tech:Tech2024!' | chpasswd
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
