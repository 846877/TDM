# Serveur géré : sshd, python3 (nécessaire aux modules Ansible), sudo. Pas de systemd.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server python3 sudo iproute2 procps vim-tiny less \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY serveur/role.sh /usr/local/bin/role.sh
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
