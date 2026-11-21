# Serveur de messagerie du partenaire (partenaire.example), déjà configuré ; sert aussi de machine
# « Internet » pour tester le relais ouvert.
FROM ubuntu:24.04
RUN printf '%s\n' 'postfix postfix/main_mailer_type select Internet Site' 'postfix postfix/mailname string partenaire.example' \
      | debconf-set-selections \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       postfix swaks openssh-server iproute2 iputils-ping procps \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash contact \
    && postconf -e 'myhostname = mx.partenaire.example' 'mydestination = partenaire.example, localhost' \
         'mynetworks = 127.0.0.0/8' 'inet_interfaces = all' 'inet_protocols = ipv4' 'home_mailbox = Maildir/' \
         'maillog_file = /var/log/postfix.log' 'smtpd_tls_security_level = none'
RUN printf '#!/bin/sh\npostfix start >/dev/null 2>&1\n' > /usr/local/bin/role.sh
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
