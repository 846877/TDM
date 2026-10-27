# Poste d'attaque commun à toutes les machines offensives : un environnement Kali Linux, en ligne de
# commande ET en interface graphique (bureau léger accessible dans le navigateur via noVNC).
# Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au cache
# Docker). Le conteneur n'atteint la cible que par le réseau interne du lab.
#
# Image volontairement ALLÉGÉE pour se construire de façon fiable dans la VM moteur (bureau léger
# Fluxbox + Firefox ; pas de métapaquet XFCE ni de Burp, qui faisaient planter la construction).
# Le bureau n'est lancé qu'à la demande (bouton « Interface graphique »).
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

# Couche 1 : outils de pentest en ligne de commande (l'essentiel pour résoudre les machines).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      nmap gobuster dirb nikto whatweb \
      sqlmap hydra \
      curl wget netcat-traditional \
      python3 \
      iputils-ping dnsutils iproute2 net-tools \
      jq git vim less procps ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Couche 2 : bureau graphique léger (Fluxbox) + Firefox + serveur VNC + pont noVNC (accès navigateur).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      fluxbox xterm dbus-x11 \
      tigervnc-standalone-server tigervnc-common \
      novnc websockify \
      firefox-esr \
 && rm -rf /var/lib/apt/lists/*

# Script de démarrage du bureau (idempotent) : lance Xvnc sans mot de passe (lab local isolé) puis
# le pont noVNC sur le port 6080. Appelé à la demande par la plateforme.
COPY demarrer-bureau.sh /opt/demarrer-bureau.sh
RUN chmod +x /opt/demarrer-bureau.sh \
 && mkdir -p /root/reponses /root/.vnc \
 && printf '#!/bin/sh\nxterm -geometry 100x28+20+20 &\nfirefox-esr http://cible/ &\nexec fluxbox\n' > /root/.vnc/xstartup \
 && chmod +x /root/.vnc/xstartup

WORKDIR /root
CMD ["sleep", "infinity"]
