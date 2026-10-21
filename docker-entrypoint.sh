#!/bin/sh
set -e
if ! docker info >/dev/null 2>&1; then
  echo "Docker est inaccessible depuis le conteneur : vérifie que Docker Desktop est lancé." >&2
  exit 1
fi
if ! docker image inspect "${TDM_SANDBOX_IMAGE:-tdm-python-sandbox}" >/dev/null 2>&1; then
  echo "→ Construction de l'image du bac à sable Python"
  docker build -t "${TDM_SANDBOX_IMAGE:-tdm-python-sandbox}" -f /app/sandbox/python.Dockerfile /app/sandbox
fi
cd /app/backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
