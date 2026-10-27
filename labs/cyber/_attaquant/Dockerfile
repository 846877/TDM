# Poste d'attaque commun à toutes les machines offensives : un VRAI environnement Kali Linux complet,
# en ligne de commande ET en interface graphique (bureau Kali XFCE accessible dans le navigateur via
# noVNC). Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au
# cache Docker). Le conteneur attaquant atteint la cible par le réseau interne du lab ; son bureau est
# publié sur 127.0.0.1:6080 (port 6080) via un réseau bridge dédié.
#
# ATTENTION : image volumineuse (bureau Kali XFCE + jeu d'outils kali-linux-default). Le TOUT PREMIER
# build télécharge plusieurs Go et dure un bon moment ; ensuite tout est servi depuis le cache Docker.
# Le bureau n'est lancé qu'à la demande (bouton « Interface graphique »).
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

# Couche 1 : bureau Kali (XFCE) + serveur VNC + pont noVNC (accès navigateur) + Firefox.
RUN apt-get update \
 && apt-get install -y \
      kali-desktop-xfce \
      tigervnc-standalone-server tigervnc-common \
      novnc websockify \
      dbus-x11 \
      firefox-esr \
 && rm -rf /var/lib/apt/lists/*

# Couche 2 : jeu d'outils Kali par défaut (Metasploit, Burp Suite, Wireshark, sqlmap, hydra, john,
# aircrack-ng, gobuster, nikto, wordlists, impacket, responder, nmap, etc.) + quelques utilitaires.
RUN apt-get update \
 && apt-get install -y \
      kali-linux-default \
      curl wget git jq vim less \
      iputils-ping dnsutils iproute2 net-tools \
 && rm -rf /var/lib/apt/lists/*

# Script de démarrage du bureau (idempotent) : lance Xtigervnc sans mot de passe (lab local isolé) puis
# le bureau Kali XFCE et le pont noVNC sur le port 6080. Appelé à la demande par la plateforme. On
# n'utilise pas le script `vncserver` (ni son xstartup) : il échoue sur Kali à la migration de
# /root/.vnc vers /root/.config/tigervnc. Le script lance donc Xtigervnc et la session XFCE lui-même.
COPY demarrer-bureau.sh /opt/demarrer-bureau.sh
RUN chmod +x /opt/demarrer-bureau.sh \
 && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
