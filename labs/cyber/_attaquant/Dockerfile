# Poste d'attaque commun à toutes les machines offensives : un VRAI environnement Kali Linux complet,
# en ligne de commande ET en interface graphique (bureau Kali XFCE accessible dans le navigateur via
# noVNC). Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au
# cache Docker). Le conteneur attaquant atteint la cible par le réseau interne du lab ; son bureau est
# publié sur 127.0.0.1:6080 via un réseau bridge dédié.
#
# ATTENTION : image volumineuse. Le TOUT PREMIER build télécharge plusieurs Go et dure longtemps.
# L'installation est DÉCOUPÉE en plusieurs couches (bureau, puis groupes d'outils Kali) : chaque couche
# terminée est mise en cache. Ainsi, si un build est interrompu (délai, coupure), le suivant REPREND là
# où il s'était arrêté au lieu de tout recommencer. Ensuite tout est servi depuis le cache.
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

# Couche 2 : les outils Kali les plus courants (Metasploit, Burp Suite, Wireshark, nmap, sqlmap,
# hydra, john, aircrack-ng…). Groupe « top 10 » de Kali.
RUN apt-get update \
 && apt-get install -y kali-tools-top10 \
 && rm -rf /var/lib/apt/lists/*

# Couche 3 : reconnaissance / énumération (nmap avancé, dns, smb, enum4linux, whatweb…).
RUN apt-get update \
 && apt-get install -y kali-tools-information-gathering \
 && rm -rf /var/lib/apt/lists/*

# Couche 4 : tests web (gobuster, ffuf, dirb, nikto, wfuzz, wpscan…).
RUN apt-get update \
 && apt-get install -y kali-tools-web \
 && rm -rf /var/lib/apt/lists/*

# Couche 5 : mots de passe / hash (john, hashcat, hydra, crackmapexec…).
RUN apt-get update \
 && apt-get install -y kali-tools-passwords \
 && rm -rf /var/lib/apt/lists/*

# Couche 6 : extras utiles pour l'élévation de privilèges et le réseau + utilitaires de base.
RUN apt-get update \
 && apt-get install -y \
      wordlists seclists impacket-scripts responder \
      netcat-traditional curl wget git jq vim less \
      iputils-ping dnsutils iproute2 net-tools procps ca-certificates \
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
