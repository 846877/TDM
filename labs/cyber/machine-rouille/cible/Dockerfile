# Cible de la machine « Rouille ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « web ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo tar procps \
 && rm -rf /var/lib/apt/lists/*

# Utilisateur de service peu privilégié
RUN useradd -m -s /bin/bash web

# Drapeaux : user.txt lisible par web ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{r0u1ll3_sst1_3val_rce}\n' > /home/web/user.txt \
 && chown web:web /home/web/user.txt && chmod 644 /home/web/user.txt \
 && printf 'TDM{r0u1ll3_sud0_tar_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration sudo : web peut lancer tar en root sans mot de passe (chemin d'élévation).
RUN echo 'web ALL=(root) NOPASSWD: /usr/bin/tar' > /etc/sudoers.d/web \
 && chmod 440 /etc/sudoers.d/web

COPY app.py /opt/app.py

# Le serveur web tourne sous web (c'est ce que le SSTI exécutera).
CMD ["runuser", "-u", "web", "--", "python3", "/opt/app.py"]
