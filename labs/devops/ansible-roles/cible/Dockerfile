# Serveur géré par Ansible : SSH, Python, sudo et Nginx (installé mais arrêté).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server python3 sudo nginx curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default \
    && useradd --create-home --shell /bin/bash deploy \
    && echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy \
    && mkdir -p /run/sshd /home/deploy/.ssh && chown deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh
COPY demarrer.sh /usr/local/bin/demarrer.sh
RUN chmod +x /usr/local/bin/demarrer.sh
CMD ["/usr/local/bin/demarrer.sh"]
