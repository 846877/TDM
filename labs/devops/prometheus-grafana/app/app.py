"""Application de démonstration qui expose des métriques Prometheus (bibliothèque standard uniquement).

  GET /            une « vraie » requête (1 sur 10 renvoie une erreur 500)
  GET /charge?n=N  fixe la taille de la file d'attente à N (pour déclencher une alerte)
  GET /metrics     métriques au format Prometheus
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

etat = {"file": 3, "200": 0, "500": 0}


class Handler(BaseHTTPRequestHandler):
    def repondre(self, code, texte, type_="text/plain; charset=utf-8"):
        corps = texte.encode()
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/metrics":
            lignes = [
                "# HELP tdm_queue_size Nombre de tâches en attente.",
                "# TYPE tdm_queue_size gauge",
                f"tdm_queue_size {etat['file']}",
                "# HELP tdm_requests_total Requêtes traitées, par code HTTP.",
                "# TYPE tdm_requests_total counter",
                f'tdm_requests_total{{code="200"}} {etat["200"]}',
                f'tdm_requests_total{{code="500"}} {etat["500"]}',
            ]
            self.repondre(200, "\n".join(lignes) + "\n", "text/plain; version=0.0.4")
        elif url.path == "/charge":
            etat["file"] = int(parse_qs(url.query).get("n", ["0"])[0])
            self.repondre(200, f"file d'attente : {etat['file']}\n")
        elif url.path == "/":
            total = etat["200"] + etat["500"]
            code = "500" if total % 10 == 9 else "200"
            etat[code] += 1
            self.repondre(int(code), f"réponse {code}\n")
        else:
            self.repondre(404, "introuvable\n")

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
