# Cible de la machine « Fonderie ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « www ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo iputils-ping procps \
 && rm -rf /var/lib/apt/lists/*

# Utilisateur de service peu privilégié
RUN useradd -m -s /bin/bash www

# Drapeaux : user.txt lisible par www ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{f0nd3r1e_1nj3ct10n_rce}\n' > /home/www/user.txt \
 && chown www:www /home/www/user.txt && chmod 644 /home/www/user.txt \
 && printf 'TDM{f0nd3r1e_sud0_awk_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration sudo : www peut lancer awk en root sans mot de passe (chemin d'élévation).
RUN echo 'www ALL=(root) NOPASSWD: /usr/bin/awk' > /etc/sudoers.d/www \
 && chmod 440 /etc/sudoers.d/www

COPY app.py /opt/app.py

# Le serveur web tourne sous www (c'est ce que l'injection de commande exécutera).
CMD ["runuser", "-u", "www", "--", "python3", "/opt/app.py"]
