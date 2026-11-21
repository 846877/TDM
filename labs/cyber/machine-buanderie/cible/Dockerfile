# Cible de la machine « Buanderie ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « linge ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 findutils procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash linge

# Drapeaux : user.txt lisible par linge ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{bu4nd3r1e_un10n_sql_1nj3ct10n}\n' > /home/linge/user.txt \
 && chown linge:linge /home/linge/user.txt && chmod 644 /home/linge/user.txt \
 && printf 'TDM{bu4nd3r1e_su1d_f1nd_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration : find porte le bit SUID (s'exécute avec les droits de root).
RUN chmod u+s /usr/bin/find

COPY app.py /opt/app.py

CMD ["runuser", "-u", "linge", "--", "python3", "/opt/app.py"]
