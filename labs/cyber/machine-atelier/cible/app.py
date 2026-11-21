#!/usr/bin/env python3
"""Cible vulnérable de la machine « Atelier » (pédagogique, réseau interne du lab uniquement).

« Atelier Media » affiche des pages à partir d'un paramètre ``page`` concaténé à un chemin, sans
validation : c'est une **inclusion de fichier locale / traversée de répertoire** (LFI). Elle permet de
lire des fichiers arbitraires, dont un **jeton d'administration** qui débloque une console exécutant des
commandes (RCE) en tant que l'utilisateur de service ``atelier``. L'élévation vers root se fait via
``sudo python3`` mal configuré.

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import html
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PAGES = "/srv/pages"

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Atelier Media</title></head>
<body><h1>Atelier Media</h1>
<p>Consulte une page : <a href="/voir?page=accueil.html">accueil</a>.</p>
<p>Console d'administration : /console?jeton=...&cmd=... (jeton dans la configuration serveur).</p>
<p><small>CMS Atelier v0.8.</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Atelier/0.8"
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
        if url.path == "/voir":
            page = q.get("page", ["accueil.html"])[0]
            # VOLONTAIREMENT VULNÉRABLE : le chemin est construit sans validation (LFI / traversée).
            chemin = os.path.join(PAGES, page)
            try:
                with open(chemin, "r", errors="replace") as f:
                    contenu = f.read(65536)
            except Exception as e:  # noqa: BLE001
                contenu = f"[fichier introuvable: {e}]"
            return self._send(200, f"<!doctype html><meta charset=utf-8><pre>{html.escape(contenu)}</pre>")
        if url.path == "/console":
            jeton = q.get("jeton", [""])[0]
            cmd = q.get("cmd", [""])[0]
            try:
                attendu = open("/opt/jeton.txt").read().strip()
            except OSError:
                attendu = None
            if not attendu or jeton != attendu:
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
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
