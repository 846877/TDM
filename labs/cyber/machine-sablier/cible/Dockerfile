# Cible de la machine « Sablier ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « sablier ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo coreutils procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash sablier

# Drapeaux : user.txt lisible par sablier ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{s4bl13r_jwt_alg_n0ne}\n' > /home/sablier/user.txt \
 && chown sablier:sablier /home/sablier/user.txt && chmod 644 /home/sablier/user.txt \
 && printf 'TDM{s4bl13r_sud0_env_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration sudo : sablier peut lancer env en root sans mot de passe (env lance n'importe
# quelle commande -> root).
RUN echo 'sablier ALL=(root) NOPASSWD: /usr/bin/env' > /etc/sudoers.d/sablier \
 && chmod 440 /etc/sudoers.d/sablier

COPY app.py /opt/app.py

CMD ["runuser", "-u", "sablier", "--", "python3", "/opt/app.py"]
