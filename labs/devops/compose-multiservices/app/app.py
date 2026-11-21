"""Compteur de visites : une petite application Flask qui stocke son compteur dans Redis."""
import os
import socket

import redis
from flask import Flask

app = Flask(__name__)
cache = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    password=os.environ.get("REDIS_PASSWORD") or None,
)


@app.route("/")
def index():
    visites = cache.incr("visites")
    version = os.environ.get("APP_VERSION", "1.0")
    return f"Bonjour ! {visites} visites - servi par {socket.gethostname()} - version {version}\n"


@app.route("/health")
def health():
    cache.ping()
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
