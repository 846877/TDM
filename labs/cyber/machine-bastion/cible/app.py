#!/usr/bin/env python3
"""Cible vulnérable de la machine « Bastion » (pédagogique, réseau interne du lab uniquement).

« Bastion Intranet » journalise chaque requête (dont le User-Agent) et propose un moteur de rapports qui
**inclut un fichier** (paramètre ``modele``) et évalue les expressions ``{{ ... }}`` qu'il contient. Deux
failles s'enchaînent : une **inclusion de fichier locale** (on peut inclure n'importe quel chemin, dont
le journal d'accès) et un **empoisonnement de journal** (on contrôle le User-Agent écrit dans ce journal).
En incluant le journal empoisonné, le moteur évalue notre code : exécution de code (RCE) en tant que
l'utilisateur de service ``bastion``. L'élévation vers root se fait via ``sudo perl`` mal configuré.

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import html
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

MODELES = "/srv/modeles"
JOURNAL = "/var/log/bastion/access.log"

ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Bastion Intranet</title></head>
<body><h1>Bastion Intranet</h1>
<p>Moteur de rapports : /rapport?modele=accueil.tpl (inclut un modele et rend les {{ expressions }}).</p>
<p>Journal d'acces : /var/log/bastion/access.log</p>
<p><small>Bastion v2.0.</small></p></body></html>"""


def rendre(texte):
    def rep(m):
        try:
            return str(eval(m.group(1).strip()))  # noqa: S307 - vulnérabilité pédagogique
        except Exception as e:  # noqa: BLE001
            return f"[erreur: {e}]"
    return re.sub(r"\{\{(.+?)\}\}", rep, texte)


class Handler(BaseHTTPRequestHandler):
    server_version = "Bastion/2.0"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _journaliser(self):
        # VOLONTAIREMENT VULNÉRABLE : le User-Agent (contrôlé par le client) est écrit tel quel.
        ua = self.headers.get("User-Agent", "-")
        ligne = f'{self.client_address[0]} - [{time.strftime("%d/%b/%Y:%H:%M:%S")}] ' \
                f'"{self.requestline}" "{ua}"\n'
        try:
            with open(JOURNAL, "a") as f:
                f.write(ligne)
        except OSError:
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
        self._journaliser()
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, ACCUEIL)
        if url.path == "/rapport":
            modele = parse_qs(url.query).get("modele", ["accueil.tpl"])[0]
            # VOLONTAIREMENT VULNÉRABLE : chemin d'inclusion non validé (LFI) + rendu des {{ }}.
            chemin = os.path.join(MODELES, modele)
            try:
                with open(chemin, "r", errors="replace") as f:
                    contenu = f.read(200000)
            except Exception as e:  # noqa: BLE001
                return self._send(200, f"<pre>[modele introuvable: {html.escape(str(e))}]</pre>")
            rendu = rendre(contenu)
            return self._send(200, f"<!doctype html><meta charset=utf-8><pre>{html.escape(rendu)}</pre>")
        return self._send(404, "<h1>404</h1>")


if __name__ == "__main__":
    os.makedirs(MODELES, exist_ok=True)
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    open(JOURNAL, "a").close()
    with open(os.path.join(MODELES, "accueil.tpl"), "w") as f:
        f.write("Rapport Bastion - genere le {{ __import__('time').strftime('%Y-%m-%d') }}\n")
    os.chdir("/tmp")
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
