"""Petit service HTTP (bibliothèque standard uniquement) qui a besoin d'une clé d'API."""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


def cle_api():
    """La clé vient d'un fichier (API_KEY_FILE, recommandé) ou, à défaut, de la variable API_KEY."""
    chemin = os.environ.get("API_KEY_FILE")
    if chemin and os.path.isfile(chemin):
        with open(chemin) as f:
            return f.read().strip()
    return os.environ.get("API_KEY", "")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        etat = "chargee" if cle_api() else "absente"
        corps = f"Service TDM - uid {os.getuid()} - cle {etat}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
