# Ubuntu avec systemd comme PID 1 (le lab est lancé en mode privilégié).
FROM ubuntu:24.04
ENV container=docker
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       systemd systemd-sysv dbus cron logrotate python3 curl procps nano vim less \
    && rm -rf /var/lib/apt/lists/* \
    && find /etc/systemd/system /lib/systemd/system -path '*.wants/*' \( -name '*getty*' -o -name '*udev*' -o -name 'systemd-resolved*' -o -name 'systemd-timesyncd*' \) -delete \
    && systemctl mask systemd-udevd.service systemd-udevd-kernel.socket systemd-udevd-control.socket getty.target console-getty.service \
    && systemctl disable cron
COPY fichiers/mystere.service fichiers/rapport.service /etc/systemd/system/
COPY fichiers/rapport.py /opt/rapport/rapport.py
RUN systemctl enable mystere.service rapport.service \
    && mkdir -p /srv/api /var/log/tdm \
    && echo '{"status": "ok"}' > /srv/api/health \
    && for i in $(seq 1 500); do echo "2026-10-18 10:00:00 INFO requête $i traitée"; done > /var/log/tdm/app.log
# systemd (PID 1) laisse un umask 0000 aux sessions docker exec : on rétablit 022 pour le terminal.
RUN echo 'umask 022' >> /etc/bash.bashrc
STOPSIGNAL SIGRTMIN+3
WORKDIR /root
CMD ["/lib/systemd/systemd"]
