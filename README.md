# TDM · plateforme d'entraînement

Une plateforme web pour s'entraîner **en pratiquant**, organisée en catégories :

| Catégorie | Ce qu'on y fait | Correction |
|-----------|-----------------|------------|
| 🐍 **Python** | 120 exercices (30 par niveau), du « Bonjour le monde » jusqu'aux métaclasses, asyncio, A* et parsers, avec un éditeur, une console et un vrai terminal | Une **moulinette** lance des tests sur ton code dans un bac à sable |
| 🌐 **Réseaux** | 60 exercices Cisco IOS (15 par niveau) : VLAN, trunks, EtherChannel, VTP, STP, routage statique, RIP, EIGRP, OSPF multizone, IPv6, HSRP, DHCP snooping, ACL, NAT, AAA, SNMP, projets complets dans un terminal IOS simulé | La moulinette inspecte la configuration obtenue |
| 🚀 **DevOps** | 18 labs lancés **en un clic** : conteneurs Docker (Linux, Git, Docker, Swarm, Ansible, Jenkins, HAProxy, PKI, Terraform, GitLab…) ou machines virtuelles Vagrant (Kubernetes, Minikube, Argo CD, Jenkins multi-nœuds, OpenShift), avec un terminal dans le navigateur | Des scripts de vérification s'exécutent dans le lab |

Chaque catégorie a quatre niveaux : **Débutant, Intermédiaire, Avancé, Expert**. La progression est mémorisée dans le navigateur.

## Application Windows (TDM.exe)

Télécharge `TDM.exe` dans la [préversion Windows](https://github.com/846877/TDM/releases/tag/windows-preview)
et double-clique dessus : la plateforme s'ouvre dans sa propre fenêtre, sans installation.

- Les exercices **Python** et **Réseaux** marchent tout de suite (Python est embarqué dans l'application).
- Les labs **Vagrant** utilisent Vagrant et VirtualBox installés sur le PC ; le dossier des labs se règle
  dans `%APPDATA%\TDM\tdm.env` (détecté automatiquement s'il est dans `Bureau\INFORMATIQUE\devops\vagrant`).
- Les labs **Docker** demandent Docker Desktop démarré.

Pour la construire soi-même : `powershell -ExecutionPolicy Bypass -File desktop\build.ps1` (crée `dist\TDM.exe`).

## Démarrer sous Windows avec Docker

Prérequis : **Docker Desktop** démarré. Pour les labs en machine virtuelle : **Vagrant**, **VirtualBox**
et **Python 3** (pour le petit agent qui pilote Vagrant).

1. Double-clique sur `start.bat`.
2. Au premier lancement, il crée un fichier `.env` avec un jeton secret et le dossier des labs Vagrant
   (`%USERPROFILE%\Desktop\INFORMATIQUE\devops\vagrant` par défaut ; modifie `TDM_VAGRANT_DIR` si besoin).
3. Il démarre l'agent Vagrant dans une fenêtre à part (si Vagrant est installé), construit et lance la
   plateforme dans Docker, puis ouvre <http://localhost:8000>.

Windows peut demander d'autoriser Python dans le pare-feu : accepte pour les **réseaux privés**, c'est ce
qui permet au conteneur de la plateforme de joindre l'agent. Sous Linux ou macOS : `docker compose up --build`,
et `python3 scripts/vagrant_agent.py` à côté pour les labs Vagrant.

### Labs Docker et labs Vagrant

- Les **labs Docker** tournent dans des conteneurs démarrés par la plateforme (via le Docker de ta
  machine). Ils démarrent en quelques secondes.
- Les **labs Vagrant** (`vagrant:` dans `lab.yaml`) réutilisent les Vagrantfile de ton dossier de
  formation, sans les copier. L'agent `scripts/vagrant_agent.py` tourne sur ta machine, lance
  `vagrant up` / `halt` / `destroy` à la demande de la plateforme et ouvre un relais vers le port SSH de
  la VM : le terminal web et les vérifications passent par SSH.

## Démarrer en local (sans conteneur)

Prérequis : **Python 3.10+**. **Docker** est fortement recommandé (bac à sable isolé + labs DevOps).

```bash
git clone https://github.com/846877/TDM.git
cd TDM
./run.sh
```

Puis ouvre <http://localhost:8000>.

`run.sh` crée un environnement virtuel, installe les dépendances, construit l'image du bac à sable
Python si Docker est présent, puis démarre le serveur. Équivalent manuel :

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
docker build -t tdm-python-sandbox -f sandbox/python.Dockerfile sandbox   # si Docker
cd backend && uvicorn app.main:app --reload
```

### Variables d'environnement

| Variable | Défaut | Rôle |
|----------|--------|------|
| `TDM_SANDBOX` | `auto` | `docker`, `local` ou `auto` (Docker s'il est disponible) |
| `TDM_LABS_DIR` | `labs/devops` | Dossier des labs DevOps (pour pointer vers ta propre collection) |
| `TDM_CONTENT_DIR` | `content` | Dossier des exercices Python et réseau |
| `TDM_RUN_TIMEOUT` | `10` | Durée maximale d'exécution d'un code (secondes) |
| `TDM_MEMORY_MB` | `256` | Mémoire maximale d'une exécution |
| `TDM_VAGRANT_DIR` | | Dossier des labs Vagrant (lu par l'agent) |
| `TDM_VAGRANT_TOKEN` | | Jeton partagé entre la plateforme et l'agent Vagrant |
| `TDM_VAGRANT_AGENT_PORT` | `7777` | Port de l'agent Vagrant |
| `TDM_VAGRANT_HOST` | `host.docker.internal` en conteneur, sinon `127.0.0.1` | Machine où tourne l'agent |

> ⚠️ En mode `local` (sans Docker), le code et le terminal s'exécutent directement sur ta machine.
> C'est pratique pour un usage personnel, mais n'expose jamais la plateforme sur un réseau dans ce mode.

## Comment ça marche

```
navigateur (HTML/JS, CodeMirror, xterm.js)
   │  REST + WebSocket
   ▼
backend FastAPI (backend/app)
   ├── python/     moulinette : exécute tests.py contre ton solution.py dans le bac à sable
   ├── network/    simulateur Cisco IOS (modes, abréviations, show, ...) + vérifications
   ├── devops/     pilote Docker (build/run/exec/stop) et l'agent Vagrant, scripts de vérification
   ├── sandbox.py  conteneur jetable sans réseau (ou sous-processus limité en mode local)
   └── terminal.py pont WebSocket ⇄ pseudo-terminal (terminal Python et terminal des labs)
```

- **Python** : chaque exercice est un fichier YAML (`content/python/`) avec l'énoncé, le code de départ,
  les tests et une solution de référence (jamais envoyée au navigateur). Le bouton **Valider** lance la
  moulinette, **Exécuter** lance ton programme, l'onglet **Terminal** ouvre un shell où ton fichier
  `solution.py` est synchronisé en direct.
- **Réseaux** : Cisco Packet Tracer ne peut pas tourner dans un navigateur ni être piloté par une
  moulinette. La plateforme embarque donc un **simulateur IOS** (switch 2960 / routeur ISR) qui reproduit
  les modes, les abréviations (`conf t`, `int fa0/1`, `sh vlan br`), l'aide `?`, les commandes `show` et
  la sauvegarde. La moulinette inspecte ensuite l'état de l'équipement. Prochaine étape envisagée : des
  topologies multi-équipements avec de vrais systèmes réseau via
  [containerlab](https://containerlab.dev) (FRRouting, Arista cEOS, Cisco IOL si tu as les images).
- **DevOps** : chaque lab est un dossier avec un `lab.yaml` (image, Dockerfile ou docker compose, ports,
  exercices et scripts de vérification). Le format est décrit dans [`labs/devops/README.md`](labs/devops/README.md).

## Importer ta collection de labs DevOps

```bash
python scripts/import_labs.py /chemin/vers/tes-labs --dest labs/devops
```

Chaque sous-dossier est copié ; un `lab.yaml` de départ est généré quand il n'en a pas (titre et
description depuis le README, Dockerfile ou docker-compose détecté). Il reste à y décrire les exercices
et leurs vérifications. Tu peux aussi laisser tes labs où ils sont : `TDM_LABS_DIR=/chemin/vers/tes-labs ./run.sh`.

## Ajouter des exercices

Voir [`docs/ajouter-des-exercices.md`](docs/ajouter-des-exercices.md). Les tests vérifient
automatiquement que chaque solution de référence passe la moulinette et que le code de départ échoue :

```bash
pip install -r backend/requirements-dev.txt
cd backend && python -m pytest -q
```
