#!/usr/bin/env python3
"""Cible vulnérable de la machine « Sablier » (pédagogique, réseau interne du lab uniquement).

« Sablier RH » délivre un jeton **JWT** à la connexion et protège son espace d'administration par ce
jeton. La vérification accepte l'algorithme ``none`` (aucune signature vérifiée) : un attaquant forge un
jeton ``{"alg":"none"}`` avec ``role=admin`` et accède à la console d'administration qui exécute des
commandes (RCE) en tant que l'utilisateur de service ``sablier``. L'élévation vers root se fait via
``sudo env`` mal configuré.

Exposé sur 0.0.0.0:80 pour n'être joignable que par le conteneur « attaquant » du même réseau Docker.
"""
import base64
import hashlib
import hmac
import html
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

SECRET = os.urandom(24)  # secret du serveur, inconnu de l'attaquant (il n'en a pas besoin : alg none)


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64ud(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def emettre(role):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = b64u(json.dumps({"role": role}).encode())
    sig = b64u(hmac.new(SECRET, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


def role_du_jeton(tok):
    try:
        h, p, s = tok.split(".")
        hdr = json.loads(b64ud(h))
        pay = json.loads(b64ud(p))
    except Exception:  # noqa: BLE001
        return None
    # VOLONTAIREMENT VULNÉRABLE : si l'en-tête annonce alg "none", on ne vérifie pas la signature.
    if hdr.get("alg") == "none":
        return pay.get("role")
    attendu = b64u(hmac.new(SECRET, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return pay.get("role") if hmac.compare_digest(attendu, s) else None


ACCUEIL = """<!doctype html><html lang=fr><head><meta charset=utf-8><title>Sablier RH</title></head>
<body><h1>Sablier RH</h1>
<p>Connexion invite : <a href="/connexion?nom=invite&mdp=invite">/connexion?nom=invite&mdp=invite</a>
(te renvoie un jeton JWT).</p>
<p>Espace admin : /admin?token=JWT&cmd=... (role=admin requis).</p>
<p><small>Auth JWT v1.0.</small></p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Sablier/1.0"
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
            mdp = q.get("mdp", [""])[0]
            if nom == "invite" and mdp == "invite":
                tok = emettre("invite")
                return self._send(200, f"<h1>Bienvenue invite</h1><p>Ton jeton :</p>"
                                       f"<pre>{html.escape(tok)}</pre>")
            return self._send(401, "<h1>Identifiants invalides</h1>")
        if url.path == "/admin":
            token = q.get("token", [""])[0]
            cmd = q.get("cmd", [""])[0]
            role = role_du_jeton(token)
            if role != "admin":
                return self._send(403, f"<h1>Acces refuse</h1><p>role={html.escape(str(role))}</p>")
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
