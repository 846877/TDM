# Cible de la machine « Mirage ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « app ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 sudo findutils procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash app

# Drapeaux : user.txt lisible par app ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{m1r4g3_p1ckl3_d3s3r1al1z4t10n}\n' > /home/app/user.txt \
 && chown app:app /home/app/user.txt && chmod 644 /home/app/user.txt \
 && printf 'TDM{m1r4g3_sud0_f1nd_r00t}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration sudo : app peut lancer find en root sans mot de passe (chemin d'élévation).
RUN echo 'app ALL=(root) NOPASSWD: /usr/bin/find' > /etc/sudoers.d/app \
 && chmod 440 /etc/sudoers.d/app

COPY app.py /opt/app.py

CMD ["runuser", "-u", "app", "--", "python3", "/opt/app.py"]
