# Cible de la machine « Bastion ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « bastion ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo perl procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash bastion \
 && mkdir -p /srv/modeles /var/log/bastion \
 && chown -R bastion:bastion /srv/modeles /var/log/bastion

# Drapeaux : user.txt lisible par bastion ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{b4st10n_lf1_l0g_p01s0n1ng}\n' > /home/bastion/user.txt \
 && chown bastion:bastion /home/bastion/user.txt && chmod 644 /home/bastion/user.txt \
 && printf 'TDM{b4st10n_sud0_p3rl_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration sudo : bastion peut lancer perl en root sans mot de passe (perl lance n'importe
# quelle commande -> root).
RUN echo 'bastion ALL=(root) NOPASSWD: /usr/bin/perl' > /etc/sudoers.d/bastion \
 && chmod 440 /etc/sudoers.d/bastion

COPY app.py /opt/app.py

CMD ["runuser", "-u", "bastion", "--", "python3", "/opt/app.py"]
