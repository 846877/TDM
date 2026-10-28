# Poste d'administration : client Kerberos, SMB, LDAP et DNS.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-client krb5-user smbclient ldap-utils dnsutils iproute2 iputils-ping netcat-openbsd \
       vim-tiny nano less bash-completion ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && printf '[libdefaults]\n    dns_lookup_kdc = true\n    dns_lookup_realm = false\n    rdns = false\n' > /etc/krb5.conf
COPY commun/admin-init.sh /usr/local/bin/admin-init.sh
COPY commun/ssh_config /etc/ssh/ssh_config.d/lab.conf
RUN chmod +x /usr/local/bin/admin-init.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/admin-init.sh"]
CMD ["sleep", "infinity"]
