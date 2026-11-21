#!/usr/bin/env python3
"""Génère des journaux réalistes d'un incident (brute force SSH + scan web) pour le lab défensif.

Déterministe : les quantités sont fixes, les vérifications du lab s'appuient dessus.
L'incident : l'IP 185.220.101.42 force SSH (comptes root/admin/sauvegarde), finit par entrer sur
« sauvegarde », puis scanne le site et atteint /gestion/ (200).
"""
import os
from datetime import datetime, timedelta

OUT = "/var/log/incident"
ATTAQUANT = "185.220.101.42"
LEGITIME = "192.168.10.24"
COMPTE_COMPROMIS = "sauvegarde"
FAILED = 47  # tentatives SSH échouées de l'attaquant (vérifié par le lab)

os.makedirs(OUT, exist_ok=True)
base = datetime(2026, 3, 14, 2, 11, 0)


def ts(dt):
    return dt.strftime("%b %e %H:%M:%S")


# --- auth.log -------------------------------------------------------------------------------------
auth = []
t = base
host = "srv-intra"
# un peu de trafic légitime avant l'attaque
for u in ("alice", "bruno"):
    auth.append(f"{ts(t)} {host} sshd[{os.getpid()%9000}]: Accepted password for {u} from {LEGITIME} port 52344 ssh2")
    t += timedelta(minutes=3)

# brute force : 47 échecs répartis sur root, admin, sauvegarde
cibles = ["root"] * 20 + ["admin"] * 17 + [COMPTE_COMPROMIS] * 10
for i, u in enumerate(cibles):
    port = 40000 + i
    auth.append(f"{ts(t)} {host} sshd[{2000+i}]: Failed password for {'invalid user ' if u=='admin' else ''}{u} "
                f"from {ATTAQUANT} port {port} ssh2")
    t += timedelta(seconds=7)

# puis une réussite sur le compte faible
auth.append(f"{ts(t)} {host} sshd[2999]: Accepted password for {COMPTE_COMPROMIS} from {ATTAQUANT} port 40777 ssh2")
t += timedelta(seconds=2)
auth.append(f"{ts(t)} {host} sshd[2999]: pam_unix(sshd:session): session opened for user {COMPTE_COMPROMIS} by (uid=0)")

with open(f"{OUT}/auth.log", "w") as f:
    f.write("\n".join(auth) + "\n")

# --- access.log (nginx, format combiné) -----------------------------------------------------------
web = []
tw = base + timedelta(minutes=20)


def line(ip, path, code, size=512, ua="Mozilla/5.0"):
    stamp = tw.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'{ip} - - [{stamp}] "GET {path} HTTP/1.1" {code} {size} "-" "{ua}"'


# trafic normal
for p in ("/", "/contact.html", "/style.css"):
    web.append(line(LEGITIME, p, 200))
    tw += timedelta(seconds=20)

# scan de répertoires de l'attaquant : beaucoup de 404/401, un 200 sur la zone sensible
for p in ("/admin", "/wp-login.php", "/.git/config", "/backup", "/config.php", "/phpmyadmin"):
    web.append(line(ATTAQUANT, p, 404, 169, ua="gobuster/3.6"))
    tw += timedelta(seconds=1)
for _ in range(6):
    web.append(line(ATTAQUANT, "/gestion/", 401, 188, ua="gobuster/3.6"))
    tw += timedelta(seconds=1)
# accès réussi après récupération d'identifiants
web.append(line(ATTAQUANT, "/gestion/", 200, 931, ua="curl/8.5.0"))

with open(f"{OUT}/access.log", "w") as f:
    f.write("\n".join(web) + "\n")

print(f"Journaux générés dans {OUT} ({FAILED} échecs SSH, compte compromis : {COMPTE_COMPROMIS})")
