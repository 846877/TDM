#!/usr/bin/env python3
"""Cible vulnérable de la machine « Fonderie » (pédagogique, réseau interne du lab uniquement).

Un mini-portail de supervision « Fonderie SA » qui propose un outil de diagnostic réseau. Le paramètre
``host`` est passé tel quel à un ``ping`` shell : c'est une **injection de commande** (RCE). Le serveur
tourne sous l'utilisateur peu privilégié ``www`` : l'attaquant obtient d'abord un accès ``www`` (drapeau
utilisateur), puis élève ses privilèges (sudo mal configuré) pour lire le drapeau root.

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import html
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Fonderie SA - Supervision</title></head>
<body><h1>Fonderie SA - Supervision interne</h1>
<p>Outil de diagnostic reseau.</p>
<form action="/diag" method="get">
  Hote a tester : <input name="host" value="127.0.0.1"> <button>Ping</button>
</form>
<p><small>v1.4 - usage reserve a l'exploitation.</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Fonderie/1.4"
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
        if url.path in ("/", "/index.html"):
            return self._send(200, ACCUEIL)
        if url.path == "/diag":
            host = parse_qs(url.query).get("host", ["127.0.0.1"])[0]
            # VULNÉRABLE À DESSEIN : le paramètre host est concaténé dans une commande shell.
            try:
                out = subprocess.run(f"ping -c 1 -W 1 {host}", shell=True, capture_output=True,
                                     text=True, timeout=15)
                sortie = out.stdout + out.stderr
            except subprocess.TimeoutExpired:
                sortie = "(délai dépassé)"
            page = f"<!doctype html><html><head><meta charset=utf-8><title>Diag</title></head><body>" \
                   f"<h1>Resultat du diagnostic</h1><pre>{html.escape(sortie)}</pre>" \
                   f"<p><a href='/'>Retour</a></p></body></html>"
            return self._send(200, page)
        return self._send(404, "<h1>404</h1>")


if __name__ == "__main__":
    os.chdir("/tmp")
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
