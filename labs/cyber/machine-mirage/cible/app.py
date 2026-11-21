#!/usr/bin/env python3
"""Cible vulnérable de la machine « Mirage » (pédagogique, réseau interne du lab uniquement).

« Mirage Dashboard » restaure les préférences d'un utilisateur à partir d'un blob **sérialisé** (pickle)
encodé en base64 et fourni par le client. L'application fait ``pickle.loads`` sur cette donnée : c'est une
**désérialisation non sécurisée** qui mène à l'exécution de code (RCE). Le serveur tourne sous
l'utilisateur peu privilégié ``app`` : accès ``app`` (drapeau utilisateur) puis élévation via sudo
(drapeau root).

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import base64
import html
import os
import pickle  # noqa: S403 - désérialisation volontairement non sécurisée (pédagogique)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


def _prefs_demo():
    # Préférences d'exemple, telles que l'application les sérialise pour le cookie « prefs ».
    return base64.b64encode(pickle.dumps({"theme": "sombre", "langue": "fr"})).decode()


ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Mirage Dashboard</title></head>
<body><h1>Mirage Dashboard</h1>
<p>Tes preferences sont restaurees depuis un jeton serialise (base64).</p>
<form action="/charger" method="get">
  Jeton de preferences : <input name="data" size=60 value="{demo}"> <button>Restaurer</button>
</form>
<p><small>API v2.3 - les preferences sont (de)serialisees cote serveur.</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Mirage/2.3"
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
            return self._send(200, ACCUEIL.format(demo=html.escape(_prefs_demo())))
        if url.path == "/charger":
            jeton = parse_qs(url.query).get("data", [""])[0]
            try:
                brut = base64.b64decode(jeton)
                # VOLONTAIREMENT VULNÉRABLE : désérialisation d'une donnée contrôlée par le client.
                obj = pickle.loads(brut)  # noqa: S301
                rendu = str(obj)
            except Exception as e:  # noqa: BLE001
                rendu = f"[preferences illisibles: {e}]"
            page = f"<!doctype html><html><head><meta charset=utf-8><title>Preferences</title></head>" \
                   f"<body><h1>Preferences restaurees</h1><pre>{html.escape(rendu)}</pre>" \
                   f"<p><a href='/'>Retour</a></p></body></html>"
            return self._send(200, page)
        return self._send(404, "<h1>404</h1>")


if __name__ == "__main__":
    os.chdir("/tmp")
    ThreadingHTTPServer(("0.0.0.0", 80), Handler).serve_forever()
