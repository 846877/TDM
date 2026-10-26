# Poste d'attaque commun à toutes les machines offensives : un vrai environnement Kali Linux.
# Image partagée (construite une seule fois, puis réutilisée par toutes les machines grâce au cache
# Docker). Le conteneur n'atteint la cible que par le réseau interne du lab.
#
# NB : le tout premier démarrage d'une machine télécharge l'image Kali et installe les outils
# (quelques minutes, une seule fois) ; ensuite les machines démarrent en quelques secondes.
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

# Outils de pentest essentiels pour résoudre les machines (sans les métapaquets lourds de Kali,
# pour garder l'image raisonnable et le démarrage rapide).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      nmap gobuster dirb nikto whatweb \
      sqlmap hydra \
      curl wget netcat-traditional \
      python3 python3-pip python3-impacket \
      iputils-ping dnsutils iproute2 \
      jq git vim less procps ca-certificates \
      wordlists \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /root/reponses
# (rockyou.txt reste compressé dans /usr/share/wordlists/ ; décompresse-le au besoin avec `gunzip`.)

WORKDIR /root
CMD ["sleep", "infinity"]
