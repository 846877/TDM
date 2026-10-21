# Serveur Ubuntu avec systemd comme PID 1 (lab lancé en mode privilégié) : services à démarrer,
# arrêter, dépanner, créer et planifier ; journaux à lire et à rendre persistants.
FROM ubuntu:24.04
ENV container=docker
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       systemd systemd-sysv dbus nginx python3 curl procps nano vim-tiny less \
    && rm -rf /var/lib/apt/lists/* \
    && find /etc/systemd/system /lib/systemd/system -path '*.wants/*' \( -name '*getty*' -o -name '*udev*' -o -name 'systemd-resolved*' -o -name 'systemd-timesyncd*' \) -delete \
    && systemctl mask systemd-udevd.service systemd-udevd-kernel.socket systemd-udevd-control.socket getty.target console-getty.service
COPY preparer.sh /usr/local/sbin/preparer.sh
RUN sh /usr/local/sbin/preparer.sh && rm /usr/local/sbin/preparer.sh
# systemd (PID 1) laisse un umask 0000 aux sessions docker exec : on rétablit 022 pour le terminal.
RUN echo 'umask 022' >> /etc/bash.bashrc
STOPSIGNAL SIGRTMIN+3
WORKDIR /root
CMD ["/lib/systemd/systemd"]
