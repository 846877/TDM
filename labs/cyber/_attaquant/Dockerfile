# Poste d'attaque commun à toutes les machines offensives : un environnement Kali Linux complet, en
# ligne de commande ET en interface graphique (bureau Kali XFCE accessible dans le navigateur via
# noVNC). Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au
# cache Docker). Le conteneur attaquant atteint la cible par le réseau interne du lab ; son bureau est
# publié sur 127.0.0.1:6080 via un réseau bridge dédié.
#
# On N'UTILISE PAS les métapaquets kali-tools-* / kali-linux-default : ils tiraient des centaines de
# paquets et l'installation échouait de façon répétée (exit 100). On installe à la place, en couches
# (chacune mise en cache : un build interrompu reprend au lieu de tout refaire), un jeu d'outils Kali
# complet mais fiable, Metasploit et les outils d'énumération de privesc (LinPEAS…) compris.
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

# Couche 2 : outils en ligne de commande (recon, web, mots de passe).
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

# Couche 4 : outils graphiques emblématiques (Burp Suite, Wireshark), dans leur propre couche.
RUN apt-get update \
 && apt-get install -y \
      burpsuite wireshark \
 && rm -rf /var/lib/apt/lists/*

# Couche 5 : Metasploit Framework (gros paquet, isolé dans sa couche pour ne pas refaire le reste).
RUN apt-get update \
 && apt-get install -y metasploit-framework \
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
COPY demarrer-bureau.sh /opt/demarrer-bureau.sh
RUN chmod +x /opt/demarrer-bureau.sh \
 && mkdir -p /root/reponses

WORKDIR /root
CMD ["sleep", "infinity"]
