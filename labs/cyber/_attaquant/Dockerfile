# Poste d'attaque commun à toutes les machines offensives : un vrai environnement Kali Linux,
# en ligne de commande ET en interface graphique (bureau XFCE accessible dans le navigateur via noVNC).
# Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au cache
# Docker). Le conteneur n'atteint la cible que par le réseau interne du lab.
#
# NB : le tout premier démarrage télécharge l'image Kali et installe les outils + le bureau (plusieurs
# minutes, une seule fois) ; ensuite les machines démarrent en quelques secondes. Le bureau graphique
# n'est lancé qu'à la demande (bouton « Interface graphique »), pour ne pas ralentir le démarrage.
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

# Outils de pentest en ligne de commande.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      nmap gobuster dirb nikto whatweb \
      sqlmap hydra \
      curl wget netcat-traditional \
      python3 python3-pip python3-impacket \
      iputils-ping dnsutils iproute2 net-tools \
      jq git vim less procps ca-certificates \
      wordlists \
 && rm -rf /var/lib/apt/lists/*
# (rockyou.txt reste compressé dans /usr/share/wordlists/ ; décompresse-le au besoin avec `gunzip`.)

# Bureau graphique (XFCE) + serveur VNC + pont noVNC (accès par navigateur) + outils GUI (Firefox, Burp).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      xfce4 xfce4-terminal dbus-x11 xterm \
      tigervnc-standalone-server tigervnc-common \
      novnc websockify \
      firefox-esr burpsuite \
 && rm -rf /var/lib/apt/lists/*

# Script de démarrage du bureau (idempotent) : lance Xvnc sans mot de passe (lab local isolé) puis
# le pont noVNC sur le port 6080. Appelé à la demande par la plateforme.
COPY demarrer-bureau.sh /opt/demarrer-bureau.sh
RUN chmod +x /opt/demarrer-bureau.sh \
 && mkdir -p /root/reponses /root/.vnc \
 && printf '#!/bin/sh\nunset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS\nexec dbus-launch --exit-with-session startxfce4\n' > /root/.vnc/xstartup \
 && chmod +x /root/.vnc/xstartup

WORKDIR /root
CMD ["sleep", "infinity"]
