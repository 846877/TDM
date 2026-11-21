# Serveur d'annuaire : OpenLDAP (slapd) préconfiguré pour dc=durand,dc=lan, base vide, non démarré.
FROM ubuntu:24.04
RUN printf '%s\n' \
      'slapd slapd/no_configuration boolean false' \
      'slapd slapd/domain string durand.lan' \
      'slapd shared/organization string Ateliers Durand' \
      'slapd slapd/password1 password AdminLdap2026!' \
      'slapd slapd/password2 password AdminLdap2026!' \
      'slapd slapd/purge_database boolean true' \
      'slapd slapd/move_old_database boolean true' | debconf-set-selections \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       slapd ldap-utils openssh-server iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /srv/sauvegardes /run/slapd && chown openldap:openldap /run/slapd \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
