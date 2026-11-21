# Cible de la machine « Atelier ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « atelier ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash atelier \
 && mkdir -p /srv/pages \
 && printf '<h1>Bienvenue a l Atelier</h1>\n' > /srv/pages/accueil.html

# Jeton d'administration déposé dans la configuration serveur (lisible via la LFI).
RUN printf 'ATL-9D4C-CONSOLE-2024\n' > /opt/jeton.txt && chmod 644 /opt/jeton.txt

# Drapeaux : user.txt lisible par atelier ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{4t3l13r_lf1_tr4v3rs33}\n' > /home/atelier/user.txt \
 && chown atelier:atelier /home/atelier/user.txt && chmod 644 /home/atelier/user.txt \
 && printf 'TDM{4t3l13r_sud0_pyth0n_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration sudo : atelier peut lancer python3 en root sans mot de passe.
RUN echo 'atelier ALL=(root) NOPASSWD: /usr/bin/python3' > /etc/sudoers.d/atelier \
 && chmod 440 /etc/sudoers.d/atelier

COPY app.py /opt/app.py

CMD ["runuser", "-u", "atelier", "--", "python3", "/opt/app.py"]
