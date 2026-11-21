# Cible de la machine « Citadelle ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « svc ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash svc

# Drapeaux : user.txt lisible par svc ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{c1t4d3ll3_ssrf_s3rv1c3_1nt3rn3}\n' > /home/svc/user.txt \
 && chown svc:svc /home/svc/user.txt && chmod 644 /home/svc/user.txt \
 && printf 'TDM{c1t4d3ll3_scr1pt_sud0_mod1f1abl3}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Script de sauvegarde lancé en root via sudo... mais MODIFIABLE par svc (mauvaise permission).
RUN printf '#!/bin/sh\n# Sauvegarde nocturne des archives\necho "Sauvegarde terminee a $(date)"\n' \
      > /usr/local/bin/sauvegarde.sh \
 && chown svc:svc /usr/local/bin/sauvegarde.sh \
 && chmod 775 /usr/local/bin/sauvegarde.sh

# Mauvaise configuration sudo : svc peut lancer le script en root sans mot de passe.
RUN echo 'svc ALL=(root) NOPASSWD: /usr/local/bin/sauvegarde.sh' > /etc/sudoers.d/svc \
 && chmod 440 /etc/sudoers.d/svc

COPY app.py /opt/app.py

CMD ["runuser", "-u", "svc", "--", "python3", "/opt/app.py"]
