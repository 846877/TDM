# Serveur de bureaux à distance : xrdp, TigerVNC et un bureau XFCE léger, installés mais non configurés.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       openssh-server xrdp xorgxrdp tigervnc-standalone-server tigervnc-tools \
       xfce4-session xfwm4 xfce4-panel xfdesktop4 xfce4-terminal thunar dbus-x11 x11-xserver-utils \
       openssl netcat-openbsd iproute2 procps sudo vim-tiny nano less \
    && rm -rf /var/lib/apt/lists/* \
    && usermod -aG ssl-cert xrdp
COPY commun/srv-init.sh /usr/local/bin/srv-init.sh
RUN chmod +x /usr/local/bin/srv-init.sh
ENTRYPOINT ["/usr/local/bin/srv-init.sh"]
