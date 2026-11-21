#!/bin/bash
# Simule une application qui lit ses secrets dans des variables d'environnement.
recu=$(printf '%s' "${DB_PASSWORD:-}" | sha256sum | cut -d' ' -f1)
if [ -z "${DB_PASSWORD:-}" ] || [ -z "${API_TOKEN:-}" ]; then
  echo "échec : DB_PASSWORD et API_TOKEN doivent être définis" >&2
  exit 1
fi
if [ "$recu" != "$(cat /opt/reference/prod.sha256)" ]; then
  echo "échec : mot de passe de la base incorrect" >&2
  exit 1
fi
echo "connexion OK (utilisateur ${DB_USER:-?}, environnement ${ENV:-?})"
