#!/usr/bin/env python3
"""Cible vulnérable de la machine « Buanderie » (pédagogique, réseau interne du lab uniquement).

« Buanderie Pro » est un portail de gestion. Son formulaire de connexion construit une requête SQL par
**concaténation de chaînes** : c'est une **injection SQL** (contournement d'authentification + extraction
de données par UNION). Un jeton d'administration ainsi extrait ouvre un outil de maintenance qui exécute
des commandes (RCE) en tant que l'utilisateur de service ``linge``. L'élévation vers root se fait via un
binaire **SUID** mal configuré.

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import html
import os
import sqlite3
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB = "/tmp/buanderie.db"


def init_db():
    c = sqlite3.connect(DB)
    c.execute("DROP TABLE IF EXISTS comptes")
    c.execute("CREATE TABLE comptes (id INTEGER, nom TEXT, motdepasse TEXT, jeton TEXT)")
    c.executemany("INSERT INTO comptes VALUES (?,?,?,?)", [
        (1, "admin", "L1nge2019!", "ADM-7F3A9C2E-MAINT"),
        (2, "paul", "bonjour1", "USR-0001"),
    ])
    c.commit()
    c.close()


ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Buanderie Pro</title></head>
<body><h1>Buanderie Pro - Espace gestion</h1>
<form action="/connexion" method="get">
  Nom : <input name="nom" value="admin"><br>
  Mot de passe : <input name="motdepasse" type="text" value=""><br>
  <button>Se connecter</button>
</form>
<p><small>Portail v1.2 - acces reserve au personnel.</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Buanderie/1.2"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            return self._send(200, ACCUEIL)
        if url.path == "/connexion":
            nom = q.get("nom", [""])[0]
            mdp = q.get("motdepasse", [""])[0]
            # VOLONTAIREMENT VULNÉRABLE : la requête est construite par concaténation (injection SQL).
            requete = f"SELECT nom FROM comptes WHERE nom='{nom}' AND motdepasse='{mdp}'"
            c = sqlite3.connect(DB)
            try:
                lignes = [r[0] for r in c.execute(requete).fetchall()]
            except Exception as e:  # noqa: BLE001
                lignes = [f"[erreur SQL: {e}]"]
            finally:
                c.close()
            if lignes:
                corps = "<h1>Connexion reussie</h1><ul>" + \
                        "".join(f"<li>{html.escape(str(x))}</li>" for x in lignes) + "</ul>" + \
                        "<p>Outil de maintenance : /outil?jeton=VOTRE_JETON&cmd=...</p>"
            else:
                corps = "<h1>Identifiants invalides</h1>"
            return self._send(200, f"<!doctype html><html><meta charset=utf-8><body>{corps}"
                                   f"<p><a href='/'>Retour</a></p></body></html>")
        if url.path == "/outil":
            jeton = q.get("jeton", [""])[0]
            cmd = q.get("cmd", [""])[0]
            c = sqlite3.connect(DB)
            valide = c.execute("SELECT 1 FROM comptes WHERE nom='admin' AND jeton=?",
                               (jeton,)).fetchone()
            c.close()
            if not valide:
                return self._send(403, "<h1>Jeton invalide</h1>")
            try:
                out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                sortie = out.stdout + out.stderr
            except subprocess.TimeoutExpired:
                sortie = "(délai dépassé)"
            return self._send(200, f"<pre>{html.escape(sortie)}</pre>")
        return self._send(404, "<h1>404</h1>")


if __name__ == "__main__":
    os.chdir("/tmp")
    init_db()
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
