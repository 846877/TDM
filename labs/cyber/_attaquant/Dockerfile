# Poste d'attaque commun à toutes les machines offensives : un environnement Kali Linux complet, en
# ligne de commande ET en interface graphique (bureau Kali XFCE accessible dans le navigateur via
# noVNC). Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au
# cache Docker). Le conteneur attaquant atteint la cible par le réseau interne du lab ; son bureau est
# publié sur 127.0.0.1:6080 via un réseau bridge dédié.
#
# On N'UTILISE PAS les métapaquets kali-tools-* / kali-linux-default : ils tiraient des centaines de
# paquets et l'installation échouait de façon répétée (exit 100). On installe à la place, en couches
# (chacune mise en cache : un build interrompu reprend au lieu de tout refaire), un jeu d'outils Kali
# ciblé mais complet pour le pentest, Metasploit et les outils d'énumération de privesc (LinPEAS…) compris.
# apt est configuré pour réessayer les téléchargements (miroirs Kali rolling parfois capricieux).
#
# IMAGE ALLÉGÉE : on garde l'essentiel (Metasploit/msfconsole, searchsploit, nmap, sqlmap, hydra,
# gobuster, Python/impacket, Burp Suite et le bureau graphique) pour que le build soit 2 à 3× plus
# rapide et tienne sur le disque. Les deux gros morceaux rarement indispensables — les immenses listes
# de mots « seclists » et l'analyseur réseau « wireshark » — ne sont PAS installés d'office. On peut les
# ajouter à la demande dans le conteneur avec : /opt/installer-extras.sh seclists wireshark
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

# Couche 2 : outils en ligne de commande (recon, web, mots de passe).
RUN apt-get update \
 && apt-get install -y \
      nmap netcat-traditional socat \
      gobuster ffuf dirb nikto wfuzz sqlmap whatweb wpscan \
      hydra john hashcat \
      smbclient enum4linux nbtscan dnsutils netdiscover \
 && rm -rf /var/lib/apt/lists/*

# Couche 3 : listes de mots (rockyou via « wordlists » ; les immenses « seclists » s'ajoutent à la
# demande, cf. /opt/installer-extras.sh), Python/impacket et utilitaires de base.
RUN apt-get update \
 && apt-get install -y \
      wordlists \
      python3 python3-pip impacket-scripts \
      git jq vim nano less iproute2 net-tools iputils-ping procps ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# Couche 4 : Burp Suite (proxy d'interception web). Wireshark n'est PAS installé d'office (gros paquet) ;
# on l'ajoute à la demande via /opt/installer-extras.sh.
RUN apt-get update \
 && apt-get install -y \
      burpsuite \
 && rm -rf /var/lib/apt/lists/*

# Couche 5 : Metasploit Framework (msfconsole) + exploitdb (searchsploit). Gros paquets isolés dans leur
# couche pour ne pas refaire le reste si leur téléchargement est interrompu.
RUN apt-get update \
 && apt-get install -y metasploit-framework exploitdb \
 && rm -rf /var/lib/apt/lists/*

# Couche 6 : outils d'énumération d'élévation de privilèges. unix-privesc-check via apt ; LinPEAS,
# linux-exploit-suggester et LinEnum récupérés dans /root/tools (téléchargements non bloquants : si l'un
# échoue, le build continue). Les scripts sont aussi exposés dans la cible via le réseau du lab au besoin.
RUN apt-get update \
 && apt-get install -y unix-privesc-check \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /root/tools \
 && curl -fsSL -o /root/tools/linpeas.sh https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh || true \
 && curl -fsSL -o /root/tools/linux-exploit-suggester.sh https://raw.githubusercontent.com/The-Z-Labs/linux-exploit-suggester/master/linux-exploit-suggester.sh || true \
 && curl -fsSL -o /root/tools/LinEnum.sh https://raw.githubusercontent.com/rebootuser/LinEnum/master/LinEnum.sh || true \
 && chmod +x /root/tools/*.sh 2>/dev/null || true

# Script de démarrage du bureau (idempotent) : lance Xtigervnc sans mot de passe (lab local isolé) puis
# la session Kali XFCE et le pont noVNC sur le port 6080. Appelé à la demande par la plateforme. On
# n'utilise pas le script `vncserver` (ni son xstartup) : il échoue sur Kali à la migration de
# /root/.vnc vers /root/.config/tigervnc. Le script lance donc Xtigervnc et la session XFCE lui-même.
# Réinstallation à la demande des gros paquets retirés de l'image allégée (seclists, wireshark…).
# Usage dans le conteneur :  /opt/installer-extras.sh seclists wireshark
# Sans argument, installe les deux. Télécharge seulement ce qui manque, au moment où tu en as besoin.
RUN printf '%s\n' \
  '#!/bin/sh' \
  '# Installe à la demande les outils volumineux non inclus dans le Kali allégé.' \
  'set -e' \
  'PAQUETS="$*"' \
  '[ -z "$PAQUETS" ] && PAQUETS="seclists wireshark"' \
  'echo "Installation de : $PAQUETS"' \
  'apt-get update' \
  'DEBIAN_FRONTEND=noninteractive apt-get install -y $PAQUETS' \
  'echo "Termine. Outils disponibles : $PAQUETS"' \
  > /opt/installer-extras.sh \
 && chmod +x /opt/installer-extras.sh

COPY demarrer-bureau.sh /opt/demarrer-bureau.sh
RUN chmod +x /opt/demarrer-bureau.sh \
 && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
