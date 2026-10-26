# Cible de la machine « Depot ». Volontairement vulnérable, joignable uniquement sur le réseau
# interne du lab (jamais publiée vers l'hôte). Elle tourne sous l'utilisateur peu privilégié « depot ».
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 libcap2-bin procps \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash depot \
 && mkdir -p /opt/plugins && chown depot:depot /opt/plugins

# Drapeaux : user.txt lisible par depot ; root.txt réservé à root (d'où l'élévation de privilèges).
RUN printf 'TDM{d3p0t_upl04d_n0n_r3str31nt}\n' > /home/depot/user.txt \
 && chown depot:depot /home/depot/user.txt && chmod 644 /home/depot/user.txt \
 && printf 'TDM{d3p0t_c4p4b1l1ty_s3tu1d}\n' > /root/root.txt \
 && chmod 600 /root/root.txt

# Mauvaise configuration : python3 porte la capability cap_setuid (il peut devenir root).
# On copie l'interpréteur pour ne pas affecter le python3 système utilisé par le service.
RUN cp /usr/bin/python3 /usr/local/bin/python3-cap \
 && setcap cap_setuid+ep /usr/local/bin/python3-cap

COPY app.py /opt/app.py

CMD ["runuser", "-u", "depot", "--", "python3", "/opt/app.py"]
