#!/bin/sh
# Génère le site final dans le dossier passé en argument (par défaut /out).
# À utiliser dans l'étape de construction d'un Dockerfile multi-étapes.
set -e
dest=${1:-/out}
mkdir -p "$dest"
cp site/*.html "$dest"/
n=$(ls site/*.html | wc -l)
echo "<p>Site généré le $(date -u +%F) : $n pages</p>" > "$dest/stats.html"
echo "Site généré dans $dest ($n pages)"
