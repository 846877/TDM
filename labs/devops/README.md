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

# --- Comment lancer le lab (un seul des quatre) ---
build: .                          # construit le Dockerfile du dossier (par défaut s'il existe)
image: alpine/git:latest          # ou une image existante
compose: docker-compose.yml       # ou docker compose (indiquer aussi `service`)
service: web                      # service compose dans lequel ouvrir le terminal
vagrant: kubernetes/kubernetes_ubuntu22   # ou une VM Vagrant : chemin relatif à TDM_VAGRANT_DIR
machine: master                   # VM du terminal pour un Vagrantfile à plusieurs machines

command: ["sleep", "infinity"]    # commande du conteneur (par défaut : sleep infinity ; [] = celle de l'image)
entrypoint: ""                    # remplace l'entrypoint de l'image si besoin
ports: ["8088:8080"]              # ports publiés sur ta machine
privileged: false                 # true pour docker-in-docker, systemd, etc.
shell: bash                       # shell du terminal web
user: eleve                       # utilisateur du terminal et des vérifications
workdir: /home/eleve
setup: |                          # commandes lancées une fois le conteneur démarré
  ...

cours: |                          # Markdown : le cours du lab (notions, schémas, « Pour réviser »)
  ...
docs:                             # liens vers la documentation officielle (1 à 4)
  - title: Documentation de Nginx
    url: https://nginx.org/en/docs/

exercises:
  - id: site
    title: Publier un site
    description: Markdown de l'énoncé
    hint: Indice affiché en cas d'échec
    cours: |                                         # Markdown : rappel de cours propre à l'exercice
      ...
    check: test -f /etc/nginx/sites-enabled/tdm      # une vérification simple…
    checks:                                          # …ou plusieurs, chacune avec son libellé
      - desc: Le site répond
        run: curl -fsS http://localhost:8080
        timeout: 60                                  # secondes (60 par défaut)
        machine: worker1                             # labs Vagrant : VM où lancer la vérification
```

Une vérification réussit si sa commande se termine avec le code `0`. Elle est exécutée **dans** le
conteneur du lab avec `sh -c` (en SSH, avec l'utilisateur `vagrant`, pour un lab Vagrant).

Astuce YAML : une commande qui contient `: ` ou ` #` doit être écrite en bloc (`run: |` puis la commande
à la ligne, indentée).

## Règles pour les labs docker compose

La plateforme tourne souvent elle-même dans un conteneur et pilote le Docker de ta machine. Les
montages de dossiers (`- ./config:/etc/...`) pointeraient alors vers un chemin qui n'existe pas côté
hôte : **copie les fichiers avec un `build`** (Dockerfile + `COPY`) et utilise des **volumes nommés**
pour les données partagées entre services.

## Labs Vagrant

Ils s'appuient sur l'agent `scripts/vagrant_agent.py`, lancé sur la machine qui a Vagrant et
VirtualBox (`start.bat` le démarre). Le statut affiché suit `vagrant status` ; le journal du
`vagrant up` en cours s'affiche sur la page du lab. **Réinitialiser** fait `vagrant destroy -f` puis
`vagrant up`.

## Importer une collection de labs existante

```bash
python scripts/import_labs.py /chemin/vers/mes-labs --dest labs/devops
```

Le script copie chaque sous-dossier et génère un `lab.yaml` de départ (titre, description depuis le
README, Dockerfile ou docker-compose détecté) qu'il ne reste plus qu'à compléter avec des exercices.
