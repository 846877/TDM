#!/bin/sh
# Simule Charlie, un collègue, qui pousse une correction sur la branche main du dépôt partagé.
set -e
cd /srv/charlie/boutique
export GIT_AUTHOR_NAME=Charlie GIT_AUTHOR_EMAIL=charlie@exemple.fr
export GIT_COMMITTER_NAME=Charlie GIT_COMMITTER_EMAIL=charlie@exemple.fr
git pull -q --rebase origin main
if git log --format=%s origin/main | grep -qx "fix: calcul de la TVA"; then
  echo "Charlie a déjà poussé sa correction."
  exit 0
fi
sed -i 's/return round(prix_ht \* (1 + TVA), 2)/return round(prix_ht * (1 + TVA) + 1e-9, 2)/' app.py
printf -- '- correction de l arrondi de la TVA\n' >> CHANGELOG.md
git commit -q -am "fix: calcul de la TVA"
git push -q origin main
echo "Charlie vient de pousser « fix: calcul de la TVA » sur main."
