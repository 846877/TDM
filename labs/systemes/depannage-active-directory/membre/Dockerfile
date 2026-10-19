# Membres du domaine : Samba/winbind (serveur de fichiers) et SSSD/adcli (poste), joints au premier démarrage.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server samba samba-common-bin winbind libnss-winbind libpam-winbind smbclient \
       sssd-ad sssd-tools adcli libnss-sss libpam-sss krb5-user \
       acl dnsutils iproute2 iputils-ping procps sudo vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/samba/smb.conf
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
COPY membre/role.sh /usr/local/bin/role.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
