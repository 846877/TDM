#!/bin/sh
# Prépare, à la construction de l'image, le dépôt du projet et son dépôt partagé (/srv/git/calc.git).
set -e
export GIT_AUTHOR_NAME=Equipe GIT_AUTHOR_EMAIL=equipe@exemple.fr
export GIT_COMMITTER_NAME=Equipe GIT_COMMITTER_EMAIL=equipe@exemple.fr
export GIT_AUTHOR_DATE="2025-04-01T09:00:00" GIT_COMMITTER_DATE="2025-04-01T09:00:00"
cd /home/eleve/projet
git init -q -b main
git add -A
git commit -q -m "chore: version initiale de calc"
git init -q --bare -b main /srv/git/calc.git
git remote add origin /srv/git/calc.git
git push -q -u origin main
mkdir -p /srv/ci/artefacts
