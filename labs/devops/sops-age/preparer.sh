#!/bin/sh
# Construction de l'image : dépôt Git d'infrastructure, clé de l'équipe et empreintes de référence.
set -e
mkdir -p /opt/reference /opt/equipe
age-keygen -o /opt/equipe/keys.txt 2>/dev/null
age-keygen -y /opt/equipe/keys.txt > /home/eleve/infra/cles/equipe.pub
chmod 644 /opt/equipe/keys.txt
printf '%s' 'Pr0d-S3cret!2025' | sha256sum | cut -d' ' -f1 > /opt/reference/prod.sha256
sha256sum < /home/eleve/infra/donnees/sauvegarde.sql | cut -d' ' -f1 > /opt/reference/sauvegarde.sha256
chown -R eleve:eleve /home/eleve
su eleve -c '
  set -e
  cd /home/eleve/infra
  export GIT_AUTHOR_NAME=Equipe GIT_AUTHOR_EMAIL=equipe@exemple.fr GIT_COMMITTER_NAME=Equipe GIT_COMMITTER_EMAIL=equipe@exemple.fr
  export GIT_AUTHOR_DATE=2024-06-01T10:00:00 GIT_COMMITTER_DATE=2024-06-01T10:00:00
  git init -q -b main
  git add README.md outils ancien cles/equipe.pub
  git commit -q -m "Configuration initiale"
  git config user.name Eleve
  git config user.email eleve@exemple.fr
'
