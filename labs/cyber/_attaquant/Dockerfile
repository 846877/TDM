# Poste d'attaque commun à toutes les machines offensives : un environnement Kali Linux, en ligne de
# commande ET en interface graphique (bureau Kali XFCE accessible dans le navigateur via noVNC). Image
# partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au cache Docker).
# Le conteneur attaquant atteint la cible par le réseau interne du lab ; son bureau est publié sur
# 127.0.0.1:6080 via un réseau bridge dédié.
#
# On N'UTILISE PAS les métapaquets kali-tools-* / kali-linux-default : ils tiraient des centaines de
# paquets (dont Metasploit, Java, Maltego…) et l'installation échouait de façon répétée (exit 100). On
# installe à la place un jeu d'outils Kali ciblé mais complet pour résoudre les machines, bien plus
# fiable et plus rapide. L'installation reste découpée en couches : un build interrompu reprend au cache.
# apt est configuré pour réessayer les téléchargements (miroirs Kali rolling parfois capricieux).
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "60";\n' > /etc/apt/apt.conf.d/80-tdm-retries

# Couche 1 : bureau Kali (XFCE) + serveur VNC + pont noVNC (accès navigateur) + Firefox.
RUN apt-get update \
 && apt-get install -y \
      kali-desktop-xfce \
      tigervnc-standalone-server tigervnc-common \
      novnc websockify \
      dbus-x11 \
      firefox-esr \
 && rm -rf /var/lib/apt/lists/*

# Couche 2 : outils en ligne de commande (recon, web, mots de passe) — l'essentiel pour les machines.
RUN apt-get update \
 && apt-get install -y \
      nmap netcat-traditional socat \
      gobuster ffuf dirb nikto wfuzz sqlmap whatweb wpscan \
      hydra john hashcat \
      smbclient enum4linux nbtscan dnsutils netdiscover \
 && rm -rf /var/lib/apt/lists/*

# Couche 3 : listes de mots, Python/impacket et utilitaires de base.
RUN apt-get update \
 && apt-get install -y \
      wordlists seclists \
      python3 python3-pip impacket-scripts \
      git jq vim nano less iproute2 net-tools iputils-ping procps ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Couche 4 : outils graphiques emblématiques (Burp Suite, Wireshark). Dans leur propre couche : s'ils
# posent souci, tout le reste est déjà construit et en cache.
RUN apt-get update \
 && apt-get install -y \
      burpsuite wireshark \
 && rm -rf /var/lib/apt/lists/*

# Script de démarrage du bureau (idempotent) : lance Xtigervnc sans mot de passe (lab local isolé) puis
# la session Kali XFCE et le pont noVNC sur le port 6080. Appelé à la demande par la plateforme. On
# n'utilise pas le script `vncserver` (ni son xstartup) : il échoue sur Kali à la migration de
# /root/.vnc vers /root/.config/tigervnc. Le script lance donc Xtigervnc et la session XFCE lui-même.
COPY demarrer-bureau.sh /opt/demarrer-bureau.sh
RUN chmod +x /opt/demarrer-bureau.sh \
 && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
