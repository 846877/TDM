#!/bin/sh
# Prépare, à la construction de l'image, le dépôt partagé de l'équipe et le poste de Charlie.
set -e
export GIT_AUTHOR_NAME=Charlie GIT_AUTHOR_EMAIL=charlie@exemple.fr
export GIT_COMMITTER_NAME=Charlie GIT_COMMITTER_EMAIL=charlie@exemple.fr

git init -q --bare -b main /srv/git/boutique.git
git -C /srv/git/boutique.git config core.logAllRefUpdates true
git init -q --bare -b main /srv/git/miroir.git

git clone -q /srv/git/boutique.git /srv/charlie/boutique 2>/dev/null
cd /srv/charlie/boutique
git symbolic-ref HEAD refs/heads/main

cat > README.md <<'EOF'
# Boutique

Petite application de boutique en ligne, développée en équipe.
EOF
git add README.md
GIT_AUTHOR_DATE="2025-03-03T09:00:00" GIT_COMMITTER_DATE="2025-03-03T09:00:00" git commit -q -m "chore: initialisation du projet"

cat > app.py <<'EOF'
TVA = 0.2


def prix_ttc(prix_ht):
    return round(prix_ht * (1 + TVA), 2)


if __name__ == "__main__":
    print(prix_ttc(10))
EOF
git add app.py
GIT_AUTHOR_DATE="2025-03-04T10:00:00" GIT_COMMITTER_DATE="2025-03-04T10:00:00" git commit -q -m "feat: calcul du prix TTC"

printf '# Journal des modifications\n\n- calcul du prix TTC\n' > CHANGELOG.md
git add CHANGELOG.md
GIT_AUTHOR_DATE="2025-03-05T11:00:00" GIT_COMMITTER_DATE="2025-03-05T11:00:00" git commit -q -m "docs: journal des modifications"

git push -q -u origin main
