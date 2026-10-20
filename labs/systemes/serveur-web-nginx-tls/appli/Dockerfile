# Application interne de planning (HTTP sur le port 8000) : affiche le chemin et les en-têtes reçus.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY appli/planning.py /usr/local/bin/planning.py
CMD ["python3", "/usr/local/bin/planning.py"]
