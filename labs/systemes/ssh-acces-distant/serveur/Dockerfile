# Serveur Ubuntu avec OpenSSH : compte tech (mot de passe Tech2024!, sudo avec mot de passe).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server sudo rsync procps iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd \
    && useradd -m -s /bin/bash -c "Technicien" -G sudo tech \
    && echo 'tech:Tech2024!' | chpasswd \
    && mkdir -p /var/log/app /var/www/site \
    && printf '2026-10-01 08:00:01 INFO demarrage\n2026-10-01 08:12:44 ERROR disque presque plein\n' > /var/log/app/app.log \
    && echo "<p>ancienne page</p>" > /var/www/site/obsolete.html \
    && chown -R tech:tech /var/www/site
CMD ["/bin/sh", "-c", "echo \"$(hostname)\" > /etc/nom-serveur; exec /usr/sbin/sshd -D -e"]
