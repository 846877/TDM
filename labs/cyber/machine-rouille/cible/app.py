#!/usr/bin/env python3
"""Cible vulnérable de la machine « Rouille » (pédagogique, réseau interne du lab uniquement).

« Rouille Notes » est un carnet de notes d'équipe qui propose un aperçu de modèles. Les expressions
entre ``{{ ... }}`` sont évaluées côté serveur par un ``eval`` : c'est une **injection de modèle côté
serveur (SSTI)** qui mène à l'exécution de code (RCE). Le serveur tourne sous l'utilisateur peu
privilégié ``web`` : l'attaquant obtient d'abord un accès ``web`` (drapeau utilisateur), puis élève ses
privilèges via un ``sudo`` mal configuré (drapeau root).

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import html
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Rouille Notes</title></head>
<body><h1>Rouille Notes</h1>
<p>Carnet de notes d'equipe. Teste le rendu d'un modele avant publication.</p>
<form action="/apercu" method="get">
  Modele : <input name="modele" size=50 value="Bonjour {{ 7*6 }}"> <button>Apercu</button>
</form>
<p><small>Moteur de modeles maison v0.9 - placeholders {{ expression }}.</small></p></body></html>"""


def rendre(modele):
    """Rend le modèle en évaluant chaque expression {{ ... }}. VOLONTAIREMENT vulnérable (eval)."""
    def remplacer(m):
        expr = m.group(1).strip()
        try:
            return str(eval(expr))  # noqa: S307 - vulnérabilité pédagogique
        except Exception as e:  # noqa: BLE001
            return f"[erreur: {e}]"
    return re.sub(r"\{\{(.+?)\}\}", remplacer, modele)


class Handler(BaseHTTPRequestHandler):
    server_version = "Rouille/0.9"
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
        if url.path == "/apercu":
            modele = parse_qs(url.query).get("modele", [""])[0]
            rendu = rendre(modele)
            page = f"<!doctype html><html><head><meta charset=utf-8><title>Apercu</title></head><body>" \
                   f"<h1>Apercu du modele</h1><pre>{html.escape(rendu)}</pre>" \
                   f"<p><a href='/'>Retour</a></p></body></html>"
            return self._send(200, page)
        return self._send(404, "<h1>404</h1>")


if __name__ == "__main__":
    os.chdir("/tmp")
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
