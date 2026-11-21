#!/usr/bin/env python3
"""Cible vulnérable de la machine « Depot » (pédagogique, réseau interne du lab uniquement).

« Depot Express » accepte le **téléversement de greffons** (plugins) sans valider leur type : un fichier
``.py`` envoyé est **enregistré puis exécuté** côté serveur. C'est un **téléversement de fichier non
restreint** menant à l'exécution de code (RCE) en tant que l'utilisateur de service ``depot``. L'élévation
vers root exploite ensuite une **capability Linux** (``cap_setuid``) mal placée.

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import html
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PLUGINS = "/opt/plugins"

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Depot Express</title></head>
<body><h1>Depot Express - Gestion de greffons</h1>
<p>Televerse un greffon de rapport. Les greffons .py sont charges automatiquement.</p>
<p>POST /televerser?nom=mon_greffon.py  (corps = contenu du fichier)</p>
<p><small>Moteur de greffons v0.5.</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Depot/0.5"
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
        return self._send(404, "<h1>404</h1>")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/televerser":
            nom = parse_qs(url.query).get("nom", ["greffon.bin"])[0]
            nom = os.path.basename(nom)  # garde juste le nom de fichier
            taille = int(self.headers.get("Content-Length", 0))
            contenu = self.rfile.read(taille)
            # VOLONTAIREMENT VULNÉRABLE : aucun contrôle du type de fichier téléversé.
            chemin = os.path.join(PLUGINS, nom)
            with open(chemin, "wb") as f:
                f.write(contenu)
            if nom.endswith(".py"):
                # Les greffons Python sont « chargés » (exécutés) automatiquement.
                try:
                    out = subprocess.run(["python3", chemin], capture_output=True, text=True, timeout=15)
                    sortie = out.stdout + out.stderr
                except subprocess.TimeoutExpired:
                    sortie = "(délai dépassé)"
                return self._send(200, f"<h1>Greffon charge</h1><pre>{html.escape(sortie)}</pre>")
            return self._send(200, f"<h1>Fichier enregistre</h1><p>{html.escape(nom)}</p>")
        return self._send(404, "<h1>404</h1>")


if __name__ == "__main__":
    os.makedirs(PLUGINS, exist_ok=True)
    os.chdir("/tmp")
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
