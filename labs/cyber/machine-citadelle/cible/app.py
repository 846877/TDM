#!/usr/bin/env python3
"""Cible vulnérable de la machine « Citadelle » (pédagogique, réseau interne du lab uniquement).

Deux services tournent dans la cible, tous deux sous l'utilisateur peu privilégié ``svc`` :

  * un **portail public** sur 0.0.0.0:80 avec un « récupérateur de ressources » qui va chercher une URL
    côté serveur : c'est une **SSRF** (Server-Side Request Forgery) ;
  * un **panneau d'administration interne** sur 127.0.0.1:8080, censé n'être joignable que depuis la
    machine elle-même, qui expose un endpoint de maintenance exécutant des commandes.

La SSRF du portail public permet d'atteindre le panneau interne (sinon inaccessible depuis le réseau) et
donc d'obtenir une RCE en tant que ``svc`` (drapeau utilisateur). L'élévation vers root se fait ensuite
via un script lancé en sudo mais **modifiable** par ``svc`` (drapeau root).

Seul le port 80 est exposé au réseau du lab ; le 8080 reste sur la boucle locale de la cible.
"""
import html
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Citadelle Portail</title></head>
<body><h1>Citadelle - Portail public</h1>
<p>Recuperateur de ressources : indique une URL, le serveur la telecharge pour toi.</p>
<form action="/recuperer" method="get">
  URL : <input name="url" size=50 value="http://cible/"> <button>Recuperer</button>
</form>
<p><small>Services internes reserves a l'administration (non exposes).</small></p></body></html>"""

ADMIN_ACCUEIL = """<!doctype html><html><head><meta charset=utf-8><title>Admin interne</title></head>
<body><h1>Citadelle - Administration interne</h1>
<p>Zone reservee (127.0.0.1 uniquement).</p>
<ul><li>GET /run?cmd=... : execute une commande de maintenance</li></ul></body></html>"""


class PublicHandler(BaseHTTPRequestHandler):
    server_version = "Citadelle/3.1"
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
        if url.path == "/recuperer":
            cible_url = parse_qs(url.query).get("url", [""])[0]
            # VOLONTAIREMENT VULNÉRABLE : aucune validation de l'URL -> SSRF (accès aux services internes).
            try:
                with urlopen(cible_url, timeout=8) as r:  # noqa: S310
                    contenu = r.read(65536).decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                contenu = f"[erreur de recuperation: {e}]"
            page = f"<!doctype html><html><head><meta charset=utf-8><title>Ressource</title></head>" \
                   f"<body><h1>Ressource recuperee</h1><pre>{html.escape(contenu)}</pre>" \
                   f"<p><a href='/'>Retour</a></p></body></html>"
            return self._send(200, page)
        return self._send(404, "<h1>404</h1>")


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "CitadelleAdmin/3.1"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, ADMIN_ACCUEIL)
        if url.path == "/run":
            cmd = parse_qs(url.query).get("cmd", [""])[0]
            # Panneau interne "de confiance" : exécute la commande (accessible via la SSRF -> RCE).
            try:
                out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                sortie = out.stdout + out.stderr
            except subprocess.TimeoutExpired:
                sortie = "(délai dépassé)"
            return self._send(200, sortie or "(pas de sortie)", "text/plain; charset=utf-8")
        return self._send(404, "404")


def demarrer_admin():
    ThreadingHTTPServer(("127.0.0.1", 8080), AdminHandler).serve_forever()


if __name__ == "__main__":
    os.chdir("/tmp")
    threading.Thread(target=demarrer_admin, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 80), PublicHandler).serve_forever()
