# TDM · plateforme d'entraînement

Une plateforme web pour s'entraîner **en pratiquant**, organisée en catégories :

| Catégorie | Ce qu'on y fait | Correction |
|-----------|-----------------|------------|
| 🐍 **Python** | 180 exercices (50 débutant, 50 intermédiaire, 40 avancé, 40 expert), chacun avec son cours et ses liens de documentation, du « Bonjour le monde » jusqu'aux métaclasses, asyncio, A*, VLSM et pare-feu, avec un éditeur, une console et un vrai terminal | Une **moulinette** lance des tests sur ton code dans un bac à sable |
| 🌐 **Réseaux** | 120 exercices Cisco IOS (35 débutant, 35 intermédiaire, 25 avancé, 25 expert), chacun avec son cours et sa documentation : modes IOS, mots de passe, bannières, sauvegardes, VLAN, trunks, EtherChannel L2/L3, VTP, STP/RSTP/MST, SPAN, port-security, storm control, DHCP/DHCPv6, routage statique IPv4/IPv6, RIP, EIGRP (stub, résumés), OSPF/OSPFv3 multizone et authentifié, BGP (eBGP, multihoming), route-maps, PBR, redistribution, VRF-lite, HSRP, DHCP snooping, DAI, IP Source Guard, ACL, NAT, AAA RADIUS/TACACS+, SNMPv3, NTP authentifié, IPsec et GRE, QoS MQC, CoPP, tickets de dépannage et projets complets dans un terminal IOS simulé | La moulinette inspecte la configuration obtenue |
| 🖥️ **Systèmes & réseaux** | 39 labs (355 exercices), chacun avec son cours et sa documentation : le parcours complet d'un technicien systèmes et réseaux, des premiers pas sous Linux, paquets APT, services systemd, disques, comptes et droits, SSH, PowerShell, DHCP, DNS, VLAN, bureau à distance et sauvegardes jusqu'aux serveurs Samba, nginx/TLS, proxy Squid, MariaDB, OpenLDAP, messagerie Postfix/Dovecot, Active Directory (Samba), routage OSPF, pare-feu nftables, VPN WireGuard, VRRP, VM QEMU, supervision, automatisation Ansible, plan de reprise d'activité, dépannage et projets PME/multisite | Des scripts de vérification s'exécutent dans le lab |
| 🚀 **DevOps** | 39 labs (367 exercices) lancés **en un clic**, du débutant à l'expert, chacun avec son cours et ses liens de documentation : conteneurs Docker (Linux, Bash, réseau, YAML/JSON, Git en équipe, intégration continue, Dockerfile, Compose, systemd, Swarm, Ansible et ses rôles, Jenkins, HAProxy, Traefik, PKI, Terraform, GitLab, PostgreSQL, registre privé, Prometheus/Grafana, Loki, OpenTelemetry/Jaeger, k3s, Helm/Kustomize, sécurité Kubernetes, sécurité des conteneurs, Vault, SOPS/age…) ou machines virtuelles Vagrant (Kubernetes, Minikube, Argo CD, Jenkins multi-nœuds, OpenShift), avec un terminal dans le navigateur | Des scripts de vérification s'exécutent dans le lab |

Chaque catégorie a quatre niveaux : **Débutant, Intermédiaire, Avancé, Expert**. Chaque profil gagne de l'XP, des niveaux et des titres, avec un classement entre profils.

## Application Windows (TDM.exe)

Télécharge `TDM.exe` dans la [préversion Windows](https://github.com/846877/TDM/releases/tag/windows-preview)
et double-clique dessus : la plateforme s'ouvre dans sa propre fenêtre, sans installation.

- Les exercices **Python** et **Réseaux** marchent tout de suite (Python est embarqué dans l'application).
- Les labs **Vagrant** utilisent Vagrant et VirtualBox installés sur le PC ; le dossier des labs se règle
  dans `%APPDATA%\TDM\tdm.env` (détecté automatiquement s'il est dans `Bureau\INFORMATIQUE\devops\vagrant`).
- Les labs **Docker** n'ont plus besoin de Docker Desktop : avec VirtualBox et Vagrant installés, TDM
  démarre son propre **moteur Docker** (une petite VM Linux, voir plus bas) au premier lab Docker.
  Si Docker Desktop est déjà démarré, TDM l'utilise (réglage `TDM_DOCKER`).
- Un seul type de lab tourne à la fois : démarrer un lab Windows met en pause le moteur Docker (après
  arrêt des conteneurs des labs) et l'éventuel autre lab Windows ; démarrer un lab Docker met en pause
  les VM Windows. L'interface dit ce qui a été mis en pause.
- À la fermeture de la fenêtre, TDM met en pause (`vagrant suspend`) les VM qu'il a lancées, moteur
  Docker compris. S'il est fermé brutalement, elles restent allumées et sont reprises au lancement suivant.

Pour la construire soi-même : `powershell -ExecutionPolicy Bypass -File desktop\build.ps1` (crée `dist\TDM.exe`).

## Démarrer sous Windows avec Docker

Ce mode fait tourner la plateforme elle-même dans un conteneur : il demande Docker Desktop. Pour s'en
passer (et garder l'hyperviseur Windows désactivé), utilise plutôt `TDM.exe` et son moteur Docker.

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

### Moteur Docker de TDM (sans Docker Desktop)

Sur Windows, Docker Desktop (WSL2) garde l'**hyperviseur Windows** actif : VirtualBox perd alors VT-x
et les VM Windows des labs deviennent très lentes (tortue verte, écran noir). TDM fournit donc son
propre moteur Docker, pour que labs Docker et labs Windows marchent vite avec l'hyperviseur désactivé :

- une petite VM VirtualBox ([`labs/moteur-docker`](labs/moteur-docker/Vagrantfile) :
  `bento/ubuntu-24.04`, 2 Go de RAM, Docker Engine et le plugin compose installés au premier
  démarrage), lancée par l'agent Vagrant **à la demande**, au premier lab Docker (pas au lancement de
  TDM) ; le premier démarrage télécharge la box (≈ 1 Go) et installe Docker, en quelques minutes ;
  l'interface affiche « Moteur Docker en démarrage… » pendant ce temps ;
- l'API Docker (dockerd en tcp dans la VM) n'est redirigée que sur **127.0.0.1:23750** : la
  plateforme y envoie ses commandes `docker` par `DOCKER_HOST=tcp://127.0.0.1:23750` ;
- les ports publiés par les labs (`ports:` des `lab.yaml` et des `docker-compose.yml`) sont redirigés
  de l'hôte (127.0.0.1, même numéro) vers la VM : les liens et vérifications marchent comme avec
  Docker Desktop. Si un lab ajoute un port, le moteur est redémarré (`vagrant reload`) au démarrage suivant ;
- « arrêter » le moteur le met en pause (`vagrant suspend`) : la reprise prend quelques secondes ;
- `TDM.exe` embarque le client `docker` et le plugin compose pour le cas où Docker Desktop n'est pas
  installé ; le code Python des exercices reste exécuté localement (jamais dans la VM moteur).

Montages : avec ce moteur distant, un dossier de l'hôte monté dans un conteneur (`-v C:\x:/x`,
`- ./x:/x`) serait vide. Les labs n'en utilisent pas (un test le vérifie) : les fichiers passent par
les images (`build`, dont le contexte est envoyé au moteur) et les volumes nommés.

Si l'hyperviseur Windows est actif alors que TDM n'utilise pas Docker Desktop, l'interface l'explique
une fois (texte seulement : TDM ne modifie jamais la configuration de démarrage de Windows). La marche
à suivre pour le désactiver soi-même est dans [`labs/systemes-windows/README.md`](labs/systemes-windows/README.md).

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
| `TDM_SANDBOX` | `auto` | `docker`, `local` ou `auto` (Docker s'il est disponible, hors moteur Docker de TDM) |
| `TDM_DOCKER` | `auto` | Moteur des labs Docker : `auto` (Docker déjà joignable, sinon le moteur Docker de TDM), `desktop` (Docker de la machine) ou `vm` (toujours le moteur de TDM) |
| `TDM_DOCKER_VM_PORT` | `23750` | Port de l'API du moteur Docker de TDM sur 127.0.0.1 |
| `TDM_DOCKER_VM_MEMORY` | `2048` | Mémoire de la VM moteur en Mo (4096 conseillés pour GitLab ou k3s) |
| `TDM_DOCKER_VM_CPUS` | `2` | Processeurs de la VM moteur |
| `TDM_DOCKER_VM_BOX` | `bento/ubuntu-24.04` | Box Vagrant de la VM moteur |
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
   ├── devops/     pilote Docker (build/run/exec/stop) et l'agent Vagrant, scripts de vérification ;
   │               engine.py choisit le moteur Docker (Docker Desktop ou VM moteur de TDM)
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
