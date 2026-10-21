# Poste Linux : client NSS LDAP (nslcd) installé, non configuré.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       libnss-ldapd nslcd ldap-utils openssh-server iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/^\(passwd\|group\|shadow\):.*/\1:         files/' /etc/nsswitch.conf \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
