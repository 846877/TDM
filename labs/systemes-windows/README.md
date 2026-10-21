# Labs Windows (Systèmes & réseaux › Windows)

Chaque sous-dossier est un lab qui démarre de **vraies VM Windows** (Windows Server 2022, Windows 11)
avec Vagrant + VirtualBox sur le PC de l'élève. Les labs sont rangés dans la catégorie `systemes` avec
`os: windows` (sélecteur Windows / Linux de la page Systèmes & réseaux). Le terminal de la plateforme
ouvre une session **PowerShell** dans la VM et chaque vérification est un extrait **PowerShell**.

```
labs/systemes-windows/
├── _commun/                 partagé par tous les labs (pas de lab.yaml : ce n'est pas un lab)
│   ├── tdm.rb               aide Ruby des Vagrantfile (boxes, réseau, SSH, AD...)
│   └── provision/           base.ps1 (réseau, clavier FR, OpenSSH), ad-forest.ps1, ad-ready.ps1, join-domain.ps1
└── <lab>/
    ├── lab.yaml             énoncés, cours, vérifications, solutions
    ├── Vagrantfile          quelques lignes grâce à _commun/tdm.rb
    └── scenario.ps1         (facultatif) mise en situation : fichiers, comptes, pannes à réparer...
```

## Ce qu'il faut sur le PC

- **VirtualBox 7** et **Vagrant 2.4** (ou plus récents), virtualisation activée dans le BIOS
  (et Hyper-V/« Plateforme de machine virtuelle » de préférence désactivés).
- **RAM** : 2 Go par Windows Server, 3 Go par Windows 11 → 8 Go minimum sur le PC pour un lab à une VM,
  16 Go conseillés pour les labs à deux VM.
- **Disque** : chaque box se télécharge une fois (≈ 7 Go pour Windows Server 2022, ≈ 8 Go pour
  Windows 11, ≈ 15 Go chacune une fois décompressée) ; chaque VM est ensuite un clone lié (2 à 6 Go).
- Le premier démarrage d'un lab prend 10 à 30 min (téléchargement, puis provisionnement ; un domaine
  Active Directory ajoute ≈ 10 min). Ensuite, **Mettre en pause** fait un `vagrant suspend` (état
  sauvegardé) : la reprise ne prend que quelques secondes, là où l'élève s'était arrêté.
- **Hyper-V** (activé par Docker Desktop/WSL2, l'intégrité de la mémoire ou la protection du code PIN
  Windows Hello) oblige VirtualBox à passer par lui : une tortue verte apparaît en bas de la fenêtre de
  la VM. Les labs fonctionnent quand même, mais Windows démarre plus lentement, surtout la première fois
  (écran noir de plusieurs minutes possible). Il faut pour cela la fonctionnalité **« Plateforme de
  l'hyperviseur Windows »** (« Activer ou désactiver des fonctionnalités Windows ») : sans elle,
  VirtualBox refuse de démarrer les VM (« VT-x is not available ») et l'interface le signale. Pour
  limiter la lenteur, les VM ont moins de tâches de fond (indexation, SysMain, télémétrie coupées par
  `provision/base.ps1`), l'état initial est un instantané à chaud (une réinitialisation ne redémarre
  pas Windows) et **Mettre en pause** évite de redémarrer Windows. TDM ne désactive jamais
  l'hyperviseur lui-même ; pour le faire soi-même, dans un terminal **administrateur** :
  `bcdedit /set hypervisorlaunchtype off`, puis redémarrer Windows (retour : `auto`).
- **Un seul lab à la fois** : démarrer un lab Windows met en pause (`vagrant suspend`) le lab Windows
  qui tournait déjà et le moteur Docker (après arrêt des conteneurs des labs Docker) ; démarrer un lab
  Docker met en pause les VM Windows. Un lab encore en train de démarrer est mis en pause dès la fin
  de son démarrage. L'interface affiche ce qui a été mis en pause ; il reprend en quelques secondes
  au prochain démarrage. À la fermeture de `TDM.exe`, toutes les VM lancées par TDM sont mises en pause.

Boxes utilisées (fournisseur `virtualbox`, versions d'évaluation de Windows, renouvelées
régulièrement par leur auteur) : `gusztavvargadr/windows-server-2022-standard` et
`gusztavvargadr/windows-11`. Pour en utiliser d'autres : variables d'environnement
`TDM_WIN_SERVER_BOX` et `TDM_WIN_CLIENT_BOX` (avant de lancer TDM).

## Comment la plateforme lance un lab

1. `lab.yaml` contient `vagrant: bundled` (valeur par défaut dans ce dossier) : le chargeur
   (`backend/app/devops/labs.py`) le transforme en `tdm:<dossier>`.
2. L'agent Vagrant (`scripts/vagrant_agent.py`, intégré à `TDM.exe`) **copie** le lab et `_commun`
   dans un dossier persistant — `%LOCALAPPDATA%\TDM\vagrant\<lab>` (réglable avec
   `TDM_VAGRANT_WORK_DIR`) — puis y lance `vagrant up`. Seuls les fichiers modifiés sont recopiés et
   `.vagrant` (l'état des VM) n'est jamais touché : l'application peut se décompresser ailleurs à chaque
   lancement, les VM sont retrouvées. Juste après la première préparation complète, l'agent prend un
   instantané `tdm-initial` de toutes les VM (`vagrant snapshot save`). **Réinitialiser** le restaure
   (une minute environ) ; sans instantané valable (lab mis à jour par une nouvelle version de TDM, VM
   supprimées à la main...), il reconstruit tout : `vagrant destroy -f` puis `vagrant up`.
3. Au premier `vagrant up`, `tdm.rb` génère une clé SSH propre au lab (`<copie>\.tdm\id_rsa`).
   Vagrant communique en **WinRM** (vagrant / vagrant) ; `provision/base.ps1` installe **OpenSSH
   Server**, met **Windows PowerShell 5.1** comme shell par défaut et autorise la clé du lab.
4. La plateforme demande `vagrant ssh-config <machine>` à l'agent et ouvre `ssh` : le terminal donne
   `PS C:\Users\vagrant>` ; les vérifications passent par la même connexion.

Les labs « historiques » qui pointent vers le dossier personnel de l'élève (`TDM_VAGRANT_DIR`) ne
changent pas.

### Réseau

| Carte | Rôle |
|-------|------|
| `NAT` | celle de Vagrant (Internet, WinRM, SSH 2222→22, RDP 33389→3389 sur 127.0.0.1 ; ports décalés automatiquement s'ils sont pris) |
| `LAN` | réseau interne VirtualBox `tdm-<lab>`, isolé du PC et des autres labs : 192.168.10.0/24 |

Plan d'adressage commun : `192.168.10.10` contrôleur de domaine / premier serveur (SRV-DC01 ou
SRV01), `.11`-`.19` autres serveurs, `.101`-`.199` postes. Domaine : **durand.lan** (NetBIOS
`DURAND`) pour l'entreprise fictive *Ateliers Durand*. Comptes : `vagrant` / `vagrant` (administrateur,
et administrateur du domaine sur les labs AD), Administrateur du domaine / DSRM : `Azerty123!`.

Accès graphique : bouton **Afficher** de la VM dans VirtualBox, ou `mstsc /v:127.0.0.1:33389`
(utilisateur `vagrant`, mot de passe `vagrant` ; voir le port réel avec `vagrant port <machine>`).
Les VM sont en anglais (noms des groupes intégrés : *Administrators*, *Users*...) avec le clavier
français et le fuseau de Paris.

## Écrire un Vagrantfile

```ruby
require_relative "../_commun/tdm"

Vagrant.configure("2") do |config|
  TDM.lab(config, __dir__) do |lab|
    lab.server "dc01", hostname: "SRV-DC01", ip: "192.168.10.10", dns: "127.0.0.1",
               domain: :forest, primary: true
    lab.client "pc01", hostname: "PC01", ip: "192.168.10.101", dns: "192.168.10.10", join: true,
               scenario: "scenario.ps1"
  end
end
```

Options de `lab.server` / `lab.client` : `hostname` (obligatoire, 15 caractères maximum), `ip`, `prefix`
(24), `gateway`, `dns` (carte LAN ; sans `ip`, la carte reste sans configuration : à l'élève de jouer),
`memory` (2048 serveur, 3072 client), `cpus` (2), `primary`, `domain: :forest` (installe AD DS + DNS et
crée la forêt durand.lan, avec redémarrage), `join: true` (joint la VM au domaine, la VM du DC doit être
définie avant), `scenario` (script du dossier du lab, exécuté en dernier).

Dans `lab.yaml`, `machine: <nom>` choisit la VM du terminal (sinon la VM `primary`) et chaque
vérification peut viser une autre VM avec `machine:`.

## Format des exercices

```yaml
title: Comptes et groupes locaux
level: debutant
order: 1
tags: [windows, comptes]
summary: ...
vagrant: bundled          # par défaut dans ce dossier
machine: srv01            # VM du terminal (facultatif)
description: |            # contexte, VM, RAM nécessaire
cours: |                  # cours Markdown du lab (onglet « 📖 Cours »)
docs:                     # liens de documentation (learn.microsoft.com/fr-fr)
  - {title: ..., url: ...}
extra_commands: [Get-Inventaire]   # commandes créées pendant le lab (fonctions d'un module...) : CI statique
exercises:
  - id: win-cpt-groupes   # unique dans TOUS les labs (devops, systemes, systemes-windows)
    title: ...
    description: |
    hint: ...
    cours: |              # 80 à 200 mots
    docs: [...]           # facultatif
    ci: true              # rejoué par la CI sur un Windows Server 2022 neuf (voir plus bas)
    checks:
      - desc: Le compte existe et est activé
        run: |
          (Get-LocalUser mdupont).Enabled
        machine: pc01     # facultatif
        timeout: 120      # secondes (60 par défaut)
    solution: |           # PowerShell ; jamais montrée à l'élève
      New-LocalUser ...
```

### Convention des vérifications (`run`)

Le `run` est enveloppé par `backend/app/devops/windows.py` puis lancé avec
`powershell.exe -EncodedCommand` (aucun souci de guillemets) :

1. une **erreur** fait échouer la vérification — `$ErrorActionPreference = 'Stop'` : une cmdlet qui ne
   trouve pas l'objet (`Get-LocalUser inconnu`) suffit ;
2. `exit <n>` : le code décide (0 = réussite) ;
3. **aucune valeur produite = échec** (un `Where-Object` qui ne trouve rien ne passe pas pour une réussite) ;
4. si la **dernière valeur** est un booléen, elle décide ;
5. sinon, un `$LASTEXITCODE` non nul (commande native en dernier : `icacls`, `netsh`...) fait échouer ;
6. sinon la dernière valeur est évaluée comme un booléen PowerShell (`$null`, `0`, `''` → échec).

Conseils :

- terminer par un test explicite : `(Get-SmbShare Compta).Path -eq 'D:\Partages\Compta'` ;
- pour tester une **absence**, `-ErrorAction SilentlyContinue` : `-not (Get-LocalUser stagiaire -ErrorAction SilentlyContinue)`,
  et toujours l'accompagner d'une vérification positive dans le même exercice (sinon il réussirait avant
  d'avoir rien fait) ;
- viser les groupes intégrés par leur **SID** (`S-1-5-32-544` Administrators, `S-1-5-32-545` Users,
  `S-1-5-32-555` Remote Desktop Users, `S-1-5-32-580` Remote Management Users) : les noms changent avec la
  langue de Windows (*Administrateurs* sur un Windows français) ;
- ne pas dépendre du compte qui exécute (`$env:USERNAME` vaut `vagrant` dans la VM mais pas en CI) ;
- Windows PowerShell **5.1** uniquement (pas de `??`, de ternaire, de `-Parallel`...) ;
- registre : jamais `New-Item -Force` sur une clé qui peut exister (elle est recréée **vide**) ;
  `if (-not (Test-Path $cle)) { New-Item $cle }` puis `Set-ItemProperty` ;
- noms de machines : en CI, `$env:COMPUTERNAME` n'est pas celui du lab (`\\$env:COMPUTERNAME\...` dans
  les vérifications d'un exercice `ci: true`, comme pour DFS) ;
- les lettres `D:` (disque temporaire des runners GitHub) et `E:` peuvent être prises en CI : un disque
  virtuel d'un exercice `ci: true` prend de préférence une lettre en fin d'alphabet ;
- les scripts `.ps1` sont enregistrés en **UTF-8 avec BOM** (sinon PowerShell 5.1 les lit en ANSI et
  abîme les accents).

Les labs avec contrôleur de domaine (`domain: :forest`) mettent 15 à 20 minutes au premier `vagrant up`
(promotion puis redémarrage). Les exercices côté contrôleur d'un lab à deux VM se font à distance
(`Invoke-Command -ComputerName SRV-DC01 -Credential DURAND\vagrant`) ou par une vérification `machine:`.

### CI (`.github/workflows/windows.yml`)

- **Statique**, pour tous les labs : chaque `run`, `solution`, `scenario*.ps1` et script de `_commun`
  est analysé par le parseur PowerShell, puis chaque commande citée doit exister sur un Windows Server 2022
  équipé des outils RSAT (AD, DNS, DHCP, GPO, DFS, FSRM, sauvegarde) — `extra_commands` et la liste
  `ALWAYS_KNOWN` de `scripts/windows_labs_ci.py` couvrent les exceptions (winget, BitLocker...).
- **Exécution**, pour chaque lab qui a des exercices `ci: true`, sur un runner neuf (un job par lab) :
  `scenario.ps1`, puis pour chaque exercice `ci: true` dans l'ordre : vérifications (au moins une doit
  échouer), `solution`, vérifications (toutes doivent réussir).
  Un exercice `ci: true` doit donc tourner sur un Windows Server 2022 **hors domaine, sans
  redémarrage**, et ne dépendre que des exercices `ci: true` qui le précèdent et du scénario.
  Les exercices Active Directory, réseau du lab, Windows 11 ou redémarrage restent vérifiés statiquement.

En local (avec PowerShell 7 sous Linux, seule l'analyse syntaxique fonctionne) :

```bash
python scripts/windows_labs_ci.py static            # syntaxe
python scripts/windows_labs_ci.py static --commands # + existence des commandes (Windows + RSAT)
python scripts/windows_labs_ci.py run --lab win-comptes-locaux   # Windows jetable, en administrateur !
```

## Ajouter un lab

1. Dossier `labs/systemes-windows/<lab>` avec `lab.yaml`, `Vagrantfile` (copier un lab proche) et au
   besoin `scenario.ps1` (idempotent, sans redémarrage, utilisable aussi par la CI).
2. Préfixer les `id` d'exercices pour qu'ils restent uniques (`win-<lab>-...`).
3. `cd backend && python3 -m pytest -q` (chargement, unicité, champs obligatoires),
   `python scripts/windows_labs_ci.py static`, puis un vrai `vagrant up` du lab.
