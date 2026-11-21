"""Service de stock de la boutique (version non instrumentée).

Lancement : nohup python /opt/appli/stock.py > /var/log/stock.log 2>&1 &
Requête   : curl http://localhost:8001/stock/42
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --- Instrumentation OpenTelemetry : à ajouter ici -------------------------------------


# ----------------------------------------------------------------------------------------


class Stock(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self.path.startswith("/stock/"):
            self.send_error(404)
            return
        article = self.path.rsplit("/", 1)[-1]
        corps = json.dumps({"commande": article, "disponible": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8001), Stock).serve_forever()
