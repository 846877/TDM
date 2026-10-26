#!/usr/bin/env python3
"""Cible volontairement vulnérable du lab « Reconnaissance web » (usage pédagogique, en local uniquement).

Un petit intranet « Ateliers Durand » qui cumule des erreurs classiques :
  - en-tête ``Server`` qui divulgue la version applicative ;
  - ``/robots.txt`` qui révèle un chemin « caché » (/gestion/) ;
  - une sauvegarde oubliée ``/backup/config.php.bak`` qui fuit des identifiants ;
  - un panneau d'administration ``/gestion/`` protégé par ces mêmes identifiants (Basic Auth).

Aucune de ces failles ne touche l'hôte : tout est servi en mémoire, sur 127.0.0.1.
"""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVER_VERSION = "DurandCMS/2.3.1"
ADMIN_USER = "admin"
ADMIN_PASS = "Durand2019!"
FLAG = "TDM{r3co_w3b_1ntranet_expose}"

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Ateliers Durand</title></head>
<body><h1>Ateliers Durand - Intranet</h1>
<p>Bienvenue sur le portail interne. Accès reserve au personnel.</p>
<ul><li><a href="/">Accueil</a></li><li><a href="/contact.html">Contact</a></li></ul>
<!-- TODO: retirer l'ancienne sauvegarde de config avant la mise en production --></body></html>"""

CONTACT = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Contact</title></head>
<body><h1>Contact</h1><p>support@ateliers-durand.lan</p></body></html>"""

ROBOTS = "User-agent: *\nDisallow: /gestion/\nDisallow: /backup/\n"

CONFIG_BAK = f"""<?php
// Sauvegarde de configuration - NE PAS LAISSER EN LIGNE
$DB_HOST = 'localhost';
$ADMIN_USER = '{ADMIN_USER}';
$ADMIN_PASS = '{ADMIN_PASS}';
?>
"""

GESTION = f"""<!doctype html><html lang=fr><head><meta charset=utf-8><title>Gestion</title></head>
<body><h1>Panneau de gestion</h1><p>Authentification reussie.</p>
<p>Jeton d'acces : <code>{FLAG}</code></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = SERVER_VERSION
    sys_version = ""  # ne pas ajouter « Python/3.x » derrière le Server

    def log_message(self, *a):  # silencieux
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _authorized(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            user, _, passwd = base64.b64decode(header[6:]).decode().partition(":")
        except Exception:
            return False
        return user == ADMIN_USER and passwd == ADMIN_PASS

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send(200, ACCUEIL)
        if path == "/contact.html":
            return self._send(200, CONTACT)
        if path == "/robots.txt":
            return self._send(200, ROBOTS, "text/plain; charset=utf-8")
        if path == "/backup/config.php.bak":
            return self._send(200, CONFIG_BAK, "text/plain; charset=utf-8")
        if path.rstrip("/") == "/gestion":
            if self._authorized():
                return self._send(200, GESTION)
            return self._send(401, "<h1>401 Authentification requise</h1>",
                              headers={"WWW-Authenticate": 'Basic realm="Gestion"'})
        return self._send(404, "<h1>404 Introuvable</h1>")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 80), Handler).serve_forever()
