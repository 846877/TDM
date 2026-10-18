# Labs DevOps

Chaque sous-dossier est un lab. La plateforme lit le fichier `lab.yaml` de chaque dossier
(variable `TDM_LABS_DIR` pour pointer vers un autre dossier, par exemple ta propre collection).

## Format de `lab.yaml`

```yaml
title: Serveur web Nginx          # obligatoire
level: intermediaire              # debutant | intermediaire | avance | expert
order: 1                          # ordre dans le niveau
tags: [nginx, web]
summary: Une phrase affichée dans la liste.
description: |                    # Markdown ; à défaut, le README.md du dossier est utilisé
  ...

# --- Comment lancer le lab (un seul des trois) ---
build: .                          # construit le Dockerfile du dossier (par défaut s'il existe)
image: alpine/git:latest          # ou une image existante
compose: docker-compose.yml       # ou docker compose (indiquer aussi `service`)
service: web                      # service compose dans lequel ouvrir le terminal

command: ["sleep", "infinity"]    # commande du conteneur (par défaut : sleep infinity)
ports: ["8088:8080"]              # ports publiés sur ta machine
privileged: false                 # true pour docker-in-docker, systemd, etc.
shell: bash                       # shell du terminal web
user: eleve                       # utilisateur du terminal et des vérifications
workdir: /home/eleve
setup: |                          # commandes lancées une fois le conteneur démarré
  ...

exercises:
  - id: site
    title: Publier un site
    description: Markdown de l'énoncé
    hint: Indice affiché en cas d'échec
    check: test -f /etc/nginx/sites-enabled/tdm      # une vérification simple…
    checks:                                          # …ou plusieurs, chacune avec son libellé
      - desc: Le site répond
        run: curl -fsS http://localhost:8080
```

Une vérification réussit si sa commande se termine avec le code `0`. Elle est exécutée **dans** le
conteneur du lab avec `sh -c`.

## Importer une collection de labs existante

```bash
python scripts/import_labs.py /chemin/vers/mes-labs --dest labs/devops
```

Le script copie chaque sous-dossier et génère un `lab.yaml` de départ (titre, description depuis le
README, Dockerfile ou docker-compose détecté) qu'il ne reste plus qu'à compléter avec des exercices.
