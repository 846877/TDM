# Serveur de messagerie : Postfix (« Internet Site », configuration Ubuntu par défaut) et Dovecot installés,
# non démarrés. Une table de transport existe déjà (ancien fournisseur, injoignable).
FROM ubuntu:24.04
RUN printf '%s\n' 'postfix postfix/main_mailer_type select Internet Site' 'postfix postfix/mailname string durand.lan' \
      | debconf-set-selections \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       postfix dovecot-imapd swaks openssh-server iproute2 iputils-ping procps vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash amartin && useradd -m -s /bin/bash bleroy \
    && printf 'amartin:Alice2026!\nbleroy:Bruno2026!\n' | chpasswd \
    && echo 'ancien-fournisseur.example smtp:[10.176.1.99]' > /etc/postfix/transport \
    && postmap /etc/postfix/transport \
    && postconf -e 'transport_maps = hash:/etc/postfix/transport' \
    && echo 'listen = *' > /etc/dovecot/conf.d/00-ipv4.conf \
    && postconf -e 'inet_protocols = ipv4' \
    && echo 'umask 022' >> /etc/bash.bashrc
COPY srv-mail/role.sh /usr/local/bin/role.sh
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh /usr/local/bin/role.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
