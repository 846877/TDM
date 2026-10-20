"""Application de planning des ateliers : répond en texte avec le chemin et les en-têtes reçus."""
from http.server import BaseHTTPRequestHandler, HTTPServer


class Planning(BaseHTTPRequestHandler):
    def do_GET(self):
        lignes = [
            "Planning des ateliers",
            f"chemin={self.path}",
            f"Host={self.headers.get('Host')}",
            f"X-Forwarded-For={self.headers.get('X-Forwarded-For')}",
            f"X-Forwarded-Proto={self.headers.get('X-Forwarded-Proto')}",
        ]
        corps = ("\n".join(lignes) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


HTTPServer(("0.0.0.0", 8000), Planning).serve_forever()
