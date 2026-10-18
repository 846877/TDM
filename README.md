# TDM · plateforme d'entraînement

Une plateforme web pour s'entraîner **en pratiquant**, organisée en catégories :

| Catégorie | Ce qu'on y fait | Correction |
|-----------|-----------------|------------|
| 🐍 **Python** | 44 exercices du « Bonjour le monde » jusqu'aux métaclasses, asyncio et Dijkstra, avec un éditeur, une console et un vrai terminal | Une **moulinette** lance des tests sur ton code dans un bac à sable |
| 🌐 **Réseaux** | 19 exercices Cisco IOS (VLAN, trunks, SVI, routage statique, router-on-a-stick, SSH, DHCP, OSPF, port-security, STP, ACL, NAT, projet complet) dans un terminal IOS simulé | La moulinette inspecte la configuration obtenue |
| 🚀 **DevOps** | Des labs lancés **en un clic** dans Docker (Linux, Git, Nginx pour commencer), avec un terminal dans le navigateur | Des scripts de vérification s'exécutent dans le conteneur du lab |

Chaque catégorie a quatre niveaux : **Débutant, Intermédiaire, Avancé, Expert**. La progression est mémorisée dans le navigateur.

## Démarrer en local

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
   ├── devops/     pilote Docker : build/run/exec/stop des labs, scripts de vérification
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
