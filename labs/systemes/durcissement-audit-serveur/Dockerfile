# Serveur hérité à auditer et durcir. Les failles sont posées au build et au démarrage (entrypoint.sh).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       sudo cron socat lynis libpam-pwquality libpwquality-tools procps iproute2 netcat-openbsd \
       findutils acl vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i '/pam_loginuid.so/s/^/#/' /etc/pam.d/cron
# --- Comptes : un second compte d'UID 0 et un compte sans mot de passe ---
RUN useradd -o -u 0 -g 0 -M -d /root -s /bin/bash maintenance \
    && useradd -m -s /bin/bash test && passwd -d test \
    && useradd -m -s /bin/bash dev && echo 'dev:Dev!2024-durand' | chpasswd \
    && useradd -m -s /bin/bash stagiaire && echo 'stagiaire:Stage!2024-durand' | chpasswd \
    && useradd -m -s /bin/bash comptable && echo 'comptable:Compta!2024-durand' | chpasswd
# --- Binaires SUID suspects ---
RUN mkdir -p /opt/outils \
    && cp /bin/bash /usr/local/bin/sauvegarde-rapide && chmod 4755 /usr/local/bin/sauvegarde-rapide \
    && cp /usr/bin/find /opt/outils/find && chmod 4755 /opt/outils/find
# --- Fichiers modifiables par tous, exécutés par root ---
RUN printf '#!/bin/sh\n# Mise a jour nocturne\nfind /tmp -type f -mtime +7 -delete\n' > /usr/local/sbin/maj.sh \
    && chmod 777 /usr/local/sbin/maj.sh \
    && printf '# Nettoyage nocturne\n0 3 * * * root /usr/local/sbin/maj.sh\n' > /etc/cron.d/nettoyage \
    && chmod 666 /etc/cron.d/nettoyage \
    && printf 'Bienvenue sur srv-legacy\n' > /etc/motd && chmod 666 /etc/motd
# --- sudo trop permissif ---
RUN printf 'dev ALL=(ALL) NOPASSWD: ALL\nstagiaire ALL=(root) NOPASSWD: /usr/bin/vim, /usr/bin/less /var/log/*\n' > /etc/sudoers.d/equipe \
    && chmod 440 /etc/sudoers.d/equipe
# --- Services hérités lancés au démarrage ---
RUN mkdir -p /etc/demarrage.d /srv/ftp \
    && printf '#!/bin/sh\n# Acces telnet pour le vieux terminal de l atelier\nsocat TCP-LISTEN:23,fork,reuseaddr EXEC:/bin/login,pty,stderr >/dev/null 2>&1 &\n' > /etc/demarrage.d/telnet.sh \
    && printf '#!/bin/sh\n# Depot FTP anonyme du copieur\nsocat TCP-LISTEN:21,fork,reuseaddr SYSTEM:\042echo 220 FTP anonyme pret\042 >/dev/null 2>&1 &\n' > /etc/demarrage.d/ftp.sh \
    && printf '#!/bin/sh\ncron\n' > /etc/demarrage.d/cron.sh \
    && chmod 755 /etc/demarrage.d/*.sh
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN chmod 755 /usr/local/sbin/entrypoint.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
CMD ["sleep", "infinity"]
