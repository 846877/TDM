# Poste d'administration : ansible-core, client SSH, et un ancien playbook à corriger dans /root/parc.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ansible-core openssh-client python3 iproute2 iputils-ping vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /root/parc \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY admin/maj-annuaire.yml /root/parc/maj-annuaire.yml
COPY commun/admin-init.sh /usr/local/bin/admin-init.sh
COPY commun/ssh_config /etc/ssh/ssh_config.d/lab.conf
RUN chmod +x /usr/local/bin/admin-init.sh && chmod 644 /root/parc/maj-annuaire.yml
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/admin-init.sh"]
CMD ["sleep", "infinity"]
