#!/usr/bin/env bash
# Lance la plateforme TDM en local : ./run.sh  (puis http://localhost:8000)
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

if [ ! -d .venv ]; then
  echo "→ Création de l'environnement Python (.venv)"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if ! docker image inspect tdm-python-sandbox >/dev/null 2>&1; then
    echo "→ Construction de l'image du bac à sable Python"
    docker build -t tdm-python-sandbox -f sandbox/python.Dockerfile sandbox
  fi
  echo "→ Docker détecté : le code s'exécute dans des conteneurs isolés, les labs DevOps sont disponibles."
else
  echo "⚠ Docker n'est pas disponible : le code Python s'exécutera directement sur ta machine"
  echo "  et les labs DevOps seront désactivés. N'expose pas la plateforme sur un réseau dans ce mode."
fi

echo "→ TDM démarre sur http://${HOST}:${PORT}"
cd backend
exec uvicorn app.main:app --host "$HOST" --port "$PORT" "$@"
