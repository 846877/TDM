#!/usr/bin/env python3
"""Agent Vagrant de TDM : à lancer sur la machine qui a Vagrant + VirtualBox.

La plateforme (souvent dans un conteneur Docker) ne peut pas démarrer elle-même des machines
virtuelles VirtualBox. Ce petit serveur, sans dépendance, le fait à sa place :

    python scripts/vagrant_agent.py --root "C:\\Users\\moi\\Desktop\\INFORMATIQUE\\devops\\vagrant"

Il expose une API HTTP protégée par un jeton (variable TDM_VAGRANT_TOKEN ou fichier .env) :

    GET  /health
    GET  /status?lab=<dossier>        -> {"status": "running|stopped|starting|stopping", "log": "..."}
    POST /up?lab=<dossier>            -> démarre `vagrant up` en arrière-plan
    POST /halt?lab=<dossier>          -> `vagrant halt` en arrière-plan
    POST /reset?lab=<dossier>         -> `vagrant destroy -f` puis `vagrant up`
    GET  /ssh?lab=<dossier>&machine=  -> {"port": ..., "user": ..., "key": "..."}
    POST /exclusive?lab=<dossier>     -> met en pause les autres labs embarqués qui tournent -> {"paused": [...]}

``<dossier>`` est un chemin relatif à ``--root`` contenant un Vagrantfile. Pour /ssh, l'agent ouvre
un relais TCP accessible depuis Docker vers le port SSH de la VM (que VirtualBox n'écoute que sur
127.0.0.1).

Labs embarqués (``lab=tdm:<nom>``) : les labs Windows livrés avec TDM (``labs/systemes-windows``,
option ``--bundled``). Avant chaque ``vagrant up``, l'agent copie le lab (et le dossier partagé
``_commun``) dans un dossier persistant (``--work-dir``, par défaut ``%LOCALAPPDATA%\\TDM\\vagrant``) et
lance Vagrant depuis cette copie : l'état ``.vagrant`` et la clé SSH générée y survivent, même quand
l'application Windows se décompresse dans un dossier temporaire différent à chaque lancement.

Moteur Docker (``lab=tdm:moteur-docker``) : petite VM Linux livrée avec TDM (``labs/moteur-docker``) qui
remplace Docker Desktop, voir ``backend/app/devops/engine.py``. ``POST /up`` accepte ``ports=8080,8929``
(ports publiés par les labs, redirigés vers l'hôte) ; « arrêter » le moteur le met en pause.

Une seule famille de labs tourne à la fois : avant de démarrer un lab Windows ou le moteur Docker, la
plateforme appelle ``/exclusive``, qui met en pause (``vagrant suspend``) les autres labs embarqués.
"""

from __future__ import annotations

import argparse
import codecs
import filecmp
import hmac
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
BUNDLED_PREFIX = "tdm:"
SHARED_DIR = "_commun"  # fichiers partagés par les labs embarqués (copiés à côté de chaque lab)
MANIFEST = ".tdm-manifest"
SNAPSHOT = "tdm-initial"  # instantané des VM d'un lab embarqué juste après leur préparation
_BUNDLED_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ENGINE_NAME = "moteur-docker"  # VM du moteur Docker de TDM (labs/moteur-docker)
ENGINE = BUNDLED_PREFIX + ENGINE_NAME


def default_work_dir() -> Path:
    """Copie persistante des labs embarqués : %LOCALAPPDATA%\\TDM\\vagrant (ou ~/.local/share/TDM/vagrant)."""
    explicit = os.environ.get("TDM_VAGRANT_WORK_DIR")
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share"
    return Path(base) / "TDM" / "vagrant"


def default_bundled_dir() -> Path:
    explicit = os.environ.get("TDM_WINDOWS_LABS_DIR")
    return Path(explicit).expanduser() if explicit else ROOT_DIR / "labs" / "systemes-windows"


def default_engine_dir() -> Path:
    explicit = os.environ.get("TDM_DOCKER_ENGINE_DIR")
    return Path(explicit).expanduser() if explicit else ROOT_DIR / "labs" / ENGINE_NAME


def find_vboxmanage() -> str | None:
    """VBoxManage (pas toujours dans le PATH sous Windows) : sert à lister vite les VM allumées."""
    found = shutil.which("VBoxManage")
    if found:
        return found
    for base in (os.environ.get("VBOX_MSI_INSTALL_PATH"), os.environ.get("VBOX_INSTALL_PATH"),
                 r"C:\Program Files\Oracle\VirtualBox"):
        if base and (Path(base) / "VBoxManage.exe").exists():
            return str(Path(base) / "VBoxManage.exe")
    return None


def parse_ports(text: str) -> list[int]:
    """« 8080,8929 » -> [8080, 8929] ; refuse tout ce qui n'est pas un port non privilégié."""
    ports = []
    for item in filter(None, (p.strip() for p in text.split(","))):
        if not item.isdigit() or not 1024 <= int(item) <= 65535:
            raise ValueError(f"port invalide : {item}")
        ports.append(int(item))
    return sorted(set(ports))


def sync_tree(src: Path, dest: Path) -> list[str]:
    """Copie ``src`` dans ``dest`` sans toucher à ce qui n'en vient pas (``.vagrant``, clé SSH générée...).

    Seuls les fichiers modifiés sont réécrits ; les fichiers copiés lors d'une synchronisation précédente
    et disparus de ``src`` sont supprimés (liste tenue dans ``.tdm-manifest``). Renvoie les fichiers copiés.
    """
    dest.mkdir(parents=True, exist_ok=True)
    manifest = dest / MANIFEST
    previous = set(manifest.read_text(encoding="utf-8").splitlines()) if manifest.exists() else set()
    current, copied = set(), []
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if not path.is_file() or rel.parts[0] in (".vagrant", ".tdm", MANIFEST) or "__pycache__" in rel.parts:
            continue
        current.add(rel.as_posix())
        target = dest / rel
        if target.exists() and filecmp.cmp(path, target, shallow=False):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied.append(rel.as_posix())
    for stale in previous - current:
        (dest / stale).unlink(missing_ok=True)
    manifest.write_text("\n".join(sorted(current)), encoding="utf-8")
    return copied


# --- Vérifications avant de lancer les VM Windows d'un lab embarqué ------------------------------
# Valeurs par défaut de _commun/tdm.rb (à garder en phase).
SERVER_BOX = os.environ.get("TDM_WIN_SERVER_BOX") or "gusztavvargadr/windows-server-2022-standard"
CLIENT_BOX = os.environ.get("TDM_WIN_CLIENT_BOX") or "gusztavvargadr/windows-11"
_MACHINE = re.compile(r"^\s*lab\.(server|client)\s+\"[^\"]+\"(.*)$", re.MULTILINE)


def lab_machines(vagrantfile: Path) -> list[tuple[str, int]]:
    """[(box, mémoire en Mo)] des VM déclarées par ``lab.server`` / ``lab.client`` dans un Vagrantfile."""
    machines = []
    for kind, rest in _MACHINE.findall(vagrantfile.read_text(encoding="utf-8", errors="replace")):
        memory = re.search(r"memory:\s*(\d+)", rest)
        default = 2048 if kind == "server" else 3072
        machines.append((SERVER_BOX if kind == "server" else CLIENT_BOX, int(memory.group(1)) if memory else default))
    return machines


def free_memory_mb() -> int | None:
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.ullAvailPhys // (1024 * 1024)
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def hypervisor_present() -> bool:
    """Hyper-V (WSL2, Docker Desktop, intégrité de la mémoire...) actif : VirtualBox perd VT-x."""
    if sys.platform != "win32":
        return False
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                             "(Get-CimInstance Win32_ComputerSystem).HypervisorPresent"],
                            capture_output=True, text=True, timeout=30,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return result.stdout.strip().lower() == "true"


def installed_boxes(vagrant: str) -> set[str]:
    result = subprocess.run([vagrant, "box", "list", "--machine-readable"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    return set(re.findall(r"^\d*,[^,]*,box-name,([^,\n]+)", result.stdout, re.MULTILINE))


def preflight_warnings(vagrantfile: Path, vagrant: str) -> list[str]:
    machines = lab_machines(vagrantfile)
    if not machines:
        return []
    warnings = []
    needed, free = sum(m for _, m in machines), free_memory_mb()
    if free is not None and free < needed + 1024:
        warnings.append(f"⚠ Mémoire libre : {free / 1024:.1f} Go pour {needed / 1024:.1f} Go de VM (plus 1 Go de marge). "
                        "Ferme les applications gourmandes (navigateur, jeux...) sinon Windows sera très lent.")
    if hypervisor_present():
        warnings.append("⚠ Hyper-V est actif (Docker Desktop/WSL2 ou « Intégrité de la mémoire ») : VirtualBox tourne "
                        "en mode lent (tortue verte) et Windows peut rester longtemps sur un écran noir. "
                        "TDM n'a pas besoin de Docker Desktop (il a son propre moteur Docker) : voir le README "
                        "des labs Windows pour désactiver l'hyperviseur soi-même.")
    missing = sorted({box for box, _ in machines} - installed_boxes(vagrant))
    for box in missing:
        warnings.append(f"ℹ Box {box} pas encore téléchargée : environ 8 Go à télécharger une seule fois "
                        "(la progression s'affiche ci-dessous ; ne relance pas pendant ce temps).")
    return warnings


def _last_progress(text: str) -> str:
    """« Progress: 10% …Progress: 40% … » (progressions collées) -> « Progress: 40% … »."""
    return "Progress:" + text.rsplit("Progress:", 1)[1] if "Progress:" in text else text


class Job:
    """Une suite d'étapes exécutées l'une après l'autre en arrière-plan.

    Une étape est une commande (liste d'arguments) ou une fonction ``étape(job) -> code`` qui peut
    elle-même lancer des commandes avec ``job.call``.
    """

    def __init__(self, action: str, commands: list, cwd: Path):
        self.action = action
        self.cwd = cwd
        self.log: deque[str] = deque(maxlen=200)
        self.warnings: list[str] = []  # affichés en tête du journal tant que le job est le dernier du lab
        self.returncode: int | None = None
        self.then: list = []  # étapes ajoutées pendant l'exécution (ex. pause demandée pendant `vagrant up`)
        self._thread = threading.Thread(target=self._run, args=(commands,), daemon=True)
        self._thread.start()

    def _run(self, commands: list) -> None:
        code = 0
        try:
            for step in commands:
                code = step(self) if callable(step) else self.call(step)
                if code != 0:
                    break
            while code == 0 and self.then:
                step = self.then.pop(0)
                code = step(self) if callable(step) else self.call(step)
        except Exception as exc:  # une étape en Python ne doit pas laisser le job « en cours » pour toujours
            self.log.append(f"Erreur : {exc}")
            code = 1
        self.returncode = code

    def call(self, argv: list[str]) -> int:
        self.log.append("$ vagrant " + " ".join(argv[1:]))
        process = subprocess.Popen(argv, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._read(process.stdout)
        return process.wait()

    def _read(self, stream) -> None:
        """Recopie la sortie de vagrant dans le journal, ligne par ligne.

        Sans terminal, Vagrant écrit la progression du téléchargement d'une box (« Progress: 12% … »)
        sans jamais aller à la ligne : une lecture par lignes resterait bloquée jusqu'à la fin du
        téléchargement (plusieurs Go pour une box Windows). On lit donc par blocs, et la dernière
        progression reçue remplace la ligne en cours.
        """
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        pending = ""
        partial = False  # la dernière entrée du journal est une ligne pas encore terminée
        while True:
            chunk = stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096)
            text = decoder.decode(chunk or b"", final=not chunk)
            pending += text
            parts = re.split(r"\r\n|\r|\n", pending)
            pending = parts.pop()
            for line in parts:
                self._append(_last_progress(line), partial)
                partial = False
            pending = _last_progress(pending)
            if pending.strip():
                self._append(pending, partial)
                partial = True
            if not chunk:
                break
        stream.close()

    def _append(self, line: str, replace: bool) -> None:
        line = line.rstrip()
        if replace and self.log:
            self.log[-1] = line
        else:
            self.log.append(line)

    @property
    def running(self) -> bool:
        return self._thread.is_alive()


class Agent:
    def __init__(self, root: Path | None, vagrant: str, relay: bool = True, bundled: Path | None = None,
                 work_dir: Path | None = None, engine_dir: Path | None = None, vboxmanage: str | None = ""):
        self.root = root.resolve() if root else None  # None : seulement les labs embarqués
        self.bundled = (bundled or default_bundled_dir()).resolve()
        self.engine_dir = (engine_dir or default_engine_dir()).resolve()
        self.work_dir = (work_dir or default_work_dir()).resolve()
        self.vagrant = vagrant
        self.vboxmanage = find_vboxmanage() if vboxmanage == "" else vboxmanage  # None : via `vagrant status`
        self.engine_ports: list[int] | None = None  # ports à rediriger, fournis par la plateforme
        self.engine_reload = False  # ports changés alors que la VM existe déjà : `vagrant reload` après `up`
        self.use_relay = relay  # False quand la plateforme tourne sur la même machine (application Windows)
        self.jobs: dict[str, Job] = {}
        self.relays: dict[int, int] = {}  # port SSH de la VM -> port du relais
        self.lock = threading.Lock()

    def lab_dir(self, lab: str) -> Path:
        if not shutil.which(self.vagrant):
            raise ValueError("Vagrant n'est pas installé (ou pas dans le PATH).")
        if lab.startswith(BUNDLED_PREFIX):
            return self.bundled_dirs(lab)[1]
        if self.root is None or not self.root.is_dir():
            raise ValueError(f"dossier des labs Vagrant introuvable : {self.root or 'TDM_VAGRANT_DIR non défini'}")
        path = (self.root / lab).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("chemin hors du dossier des labs")
        if not (path / "Vagrantfile").exists():
            raise ValueError(f"pas de Vagrantfile dans {lab}")
        return path

    def bundled_dirs(self, lab: str) -> tuple[Path, Path]:
        """Lab embarqué ``tdm:<nom>`` : (dossier source livré avec TDM, copie de travail persistante)."""
        name = lab[len(BUNDLED_PREFIX):]
        if not _BUNDLED_NAME.match(name):
            raise ValueError("nom de lab embarqué invalide")
        source = self.engine_dir if name == ENGINE_NAME else self.bundled / name
        if not (source / "Vagrantfile").exists():
            raise ValueError(f"lab embarqué introuvable : {name}")
        return source, self.work_dir / name

    def prepare(self, lab: str) -> None:
        """Copie (ou met à jour) un lab embarqué dans sa copie de travail avant `vagrant up`."""
        if not lab.startswith(BUNDLED_PREFIX):
            return
        source, work = self.bundled_dirs(lab)
        changed = sync_tree(source, work)
        if lab == ENGINE:
            self._write_engine_ports(work)
            return
        shared = self.bundled / SHARED_DIR
        if shared.is_dir():
            changed += sync_tree(shared, self.work_dir / SHARED_DIR)
        if changed:  # lab mis à jour : la prochaine réinitialisation reconstruit les VM avec la nouvelle version
            (work / ".tdm" / "instantane-initial").unlink(missing_ok=True)

    def _write_engine_ports(self, work: Path) -> None:
        if self.engine_ports is None:
            return
        ports_file = work / "ports.txt"
        content = "\n".join(map(str, self.engine_ports))
        previous = ports_file.read_text(encoding="utf-8") if ports_file.exists() else None
        if previous != content:
            ports_file.write_text(content, encoding="utf-8")
            # Les redirections de ports ne s'appliquent qu'au démarrage de la VM.
            self.engine_reload = self._created(work)

    @staticmethod
    def _created(path: Path) -> bool:
        return any(path.glob(".vagrant/machines/*/virtualbox/id"))

    def _vagrant(self, path: Path, *args: str, timeout: float = 120) -> subprocess.CompletedProcess:
        return subprocess.run([self.vagrant, *args], cwd=path, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)

    def run_job(self, lab: str, action: str, *steps) -> None:
        path = self.lab_dir(lab)
        with self.lock:
            job = self.jobs.get(lab)
            if job and job.running:
                return
            if action == "up":
                self.prepare(lab)
            elif not (path / "Vagrantfile").exists():
                return  # lab embarqué jamais démarré : rien à arrêter
            self.jobs[lab] = Job(action, list(steps), path)

    # --- Labs embarqués (VM Windows) : pause et instantané pour aller vite ----------------------
    # Une VM Windows met de longues minutes à démarrer et à se préparer (OpenSSH, domaine...). Pour les
    # labs embarqués, l'agent :
    #   - met les VM en pause (`vagrant suspend`, état sauvegardé) au lieu de les éteindre : le
    #     démarrage suivant reprend en quelques secondes, là où l'élève s'était arrêté ;
    #   - prend un instantané « tdm-initial » juste après la première préparation complète : la
    #     réinitialisation restaure cet instantané au lieu de tout détruire et reconstruire.
    def lab_actions(self, lab: str) -> dict[str, tuple[str, list]]:
        if not lab.startswith(BUNDLED_PREFIX):
            return {
                "/up": ("up", [[self.vagrant, "up"]]),
                "/halt": ("halt", [[self.vagrant, "halt"]]),
                "/reset": ("up", [[self.vagrant, "destroy", "-f"], [self.vagrant, "up"]]),
            }
        if lab == ENGINE:
            return {
                "/up": ("up", [self._wait_pauses, [self.vagrant, "up"], self._reload_engine]),
                "/halt": ("halt", [[self.vagrant, "suspend"]]),
                "/reset": ("up", [self._wait_pauses, [self.vagrant, "destroy", "-f"], [self.vagrant, "up"]]),
            }
        return {
            "/up": ("up", [self._wait_pauses, self._preflight, [self.vagrant, "up"], self._snapshot_once]),
            "/halt": ("halt", [[self.vagrant, "suspend"]]),
            "/reset": ("up", [self._wait_pauses, self._preflight, self._restore_or_rebuild]),
        }

    def _reload_engine(self, job: Job) -> int:
        if not self.engine_reload:
            return 0
        job.log.append("Nouveaux ports publiés par les labs : redémarrage du moteur Docker…")
        code = job.call([self.vagrant, "reload"])
        if code == 0:
            self.engine_reload = False
        return code

    # --- Une seule famille de labs à la fois ---------------------------------------------------
    # Les VM Windows et le moteur Docker ne tournent jamais en même temps (la mémoire ne suffirait pas) :
    # avant d'en démarrer un, la plateforme demande /exclusive, qui met les autres en pause.
    def running_bundled(self) -> list[str]:
        """Labs embarqués (moteur Docker compris) dont une VM tourne ou est en train de démarrer."""
        if not self.work_dir.is_dir():
            return []
        running_ids = self._running_vm_ids()
        labs = []
        for path in sorted(p for p in self.work_dir.iterdir() if p.is_dir() and p.name != SHARED_DIR):
            lab = BUNDLED_PREFIX + path.name
            job = self.jobs.get(lab)
            if job and job.running:
                if job.action == "up":
                    labs.append(lab)
                continue
            if not self._created(path):
                continue
            if running_ids is not None:
                ids = {f.read_text(encoding="utf-8").strip() for f in path.glob(".vagrant/machines/*/virtualbox/id")}
                if ids & running_ids:
                    labs.append(lab)
            else:
                result = self._vagrant(path, "status", "--machine-readable")
                if "running" in re.findall(r"^\d*,[^,]*,state,([^,\n]+)", result.stdout, re.MULTILINE):
                    labs.append(lab)
        return labs

    def _running_vm_ids(self) -> set[str] | None:
        if not self.vboxmanage:
            return None
        try:
            result = subprocess.run([self.vboxmanage, "list", "runningvms"], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        return set(re.findall(r"\{([^{}\s]+)\}", result.stdout))

    def exclusive(self, lab: str) -> list[str]:
        """Met en pause (en arrière-plan) les labs embarqués qui tournent, sauf ``lab`` ; renvoie leurs noms.

        Un lab encore en train de démarrer sera mis en pause dès la fin de son démarrage.
        """
        suspend = [self.vagrant, "suspend"]
        paused = []
        for other in self.running_bundled():
            if other == lab:
                continue
            job = self.jobs.get(other)
            if job and job.running:
                if suspend not in job.then:
                    job.then.append(suspend)
                if job.running or suspend not in job.then:
                    paused.append(other)
                    continue
                job.then.remove(suspend)  # le démarrage vient de se terminer : pause normale ci-dessous
            self.run_job(other, "halt", suspend)
            paused.append(other)
        return paused

    def _wait_pauses(self, job: Job) -> int:
        """Attend la fin des mises en pause en cours : la mémoire des autres VM est alors libérée."""
        deadline = time.monotonic() + 900
        announced = False
        while time.monotonic() < deadline:
            if not any(other is not job and other.running and other.action == "halt"
                       for other in list(self.jobs.values())):
                break
            if not announced:
                job.log.append("Mise en pause des autres labs pour libérer la mémoire…")
                announced = True
            time.sleep(0.5)
        return 0

    def suspend_all(self, timeout: float = 300) -> list[str]:
        """Fermeture de TDM : met en pause les VM qu'il a lancées (labs embarqués, moteur Docker, labs de
        l'utilisateur démarrés pendant la session). Renvoie les labs concernés.

        Sans risque si TDM est tué avant la fin : la VM reste allumée et sera reprise au prochain lancement.
        """
        labs = self.running_bundled()
        labs += [lab for lab, job in list(self.jobs.items())
                 if not lab.startswith(BUNDLED_PREFIX) and job.action == "up" and job.returncode == 0]
        threads = []
        for lab in labs:
            try:
                path = self.lab_dir(lab)
            except ValueError:
                continue
            thread = threading.Thread(target=self._suspend_quietly, args=(path, timeout), daemon=True)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join(timeout)
        return labs

    def _suspend_quietly(self, path: Path, timeout: float) -> None:
        try:
            self._vagrant(path, "suspend", timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            pass  # la VM reste allumée : elle sera reprise au prochain lancement

    def _preflight(self, job: Job) -> int:
        """Prévient (sans bloquer) de ce qui rendra le lancement lent ou impossible."""
        try:
            job.warnings = preflight_warnings(job.cwd / "Vagrantfile", self.vagrant)
        except Exception as exc:  # une vérification ratée ne doit jamais empêcher le lab de démarrer
            job.log.append(f"(vérifications préalables impossibles : {exc})")
        return 0

    @staticmethod
    def _snapshot_marker(job: Job) -> Path:
        return job.cwd / ".tdm" / "instantane-initial"  # voir aussi prepare()

    def _snapshot_once(self, job: Job) -> int:
        marker = self._snapshot_marker(job)
        if marker.exists():
            return 0
        job.log.append("Instantané de l'état initial (pour des réinitialisations rapides)…")
        if job.call([self.vagrant, "snapshot", "save", SNAPSHOT, "--force"]) == 0:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(SNAPSHOT, encoding="utf-8")
        else:
            job.log.append("Instantané impossible : la réinitialisation reconstruira les VM.")
        return 0  # le lab tourne : un instantané manqué n'est pas un échec

    def _restore_or_rebuild(self, job: Job) -> int:
        marker = self._snapshot_marker(job)
        if marker.exists():
            if job.call([self.vagrant, "snapshot", "restore", SNAPSHOT, "--no-provision"]) == 0:
                return job.call([self.vagrant, "up", "--no-provision"])  # reprend une VM restaurée en pause
            job.log.append("Restauration impossible : reconstruction complète des VM.")
            marker.unlink(missing_ok=True)
        code = job.call([self.vagrant, "destroy", "-f"])
        if code == 0:
            code = job.call([self.vagrant, "up"])
        return self._snapshot_once(job) if code == 0 else code

    def status(self, lab: str) -> dict:
        path = self.lab_dir(lab)
        job = self.jobs.get(lab)
        log = "\n".join(job.warnings + list(job.log)[-15:]) if job else ""
        if job and job.running:
            return {"status": "starting" if job.action == "up" else "stopping", "log": log}
        if not (path / "Vagrantfile").exists():
            return {"status": "stopped", "log": log}  # lab embarqué pas encore copié
        result = self._vagrant(path, "status", "--machine-readable")
        states = re.findall(r"^\d*,[^,]*,state,([^,\n]+)", result.stdout, re.MULTILINE)
        running = bool(states) and all(s == "running" for s in states)
        if job and job.returncode not in (0, None) and not running:
            return {"status": "error", "log": log}
        return {"status": "running" if running else "stopped", "log": log}

    def ssh(self, lab: str, machine: str = "") -> dict:
        path = self.lab_dir(lab)
        if not (path / "Vagrantfile").exists():
            raise ValueError("le lab n'est pas démarré")
        args = ["ssh-config"] + ([machine] if machine else [])
        result = self._vagrant(path, *args)
        if result.returncode != 0:
            raise ValueError(result.stderr.strip() or "vagrant ssh-config a échoué")
        config = {}
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0] not in config:
                config[parts[0]] = parts[1].strip('"')
        key_path = Path(config["IdentityFile"])
        port = int(config["Port"])
        if self.use_relay:
            port = self.relay(config.get("HostName", "127.0.0.1"), port)
        return {"port": port, "user": config["User"], "key": key_path.read_text(encoding="utf-8"),
                "key_path": str(key_path)}

    def relay(self, host: str, port: int) -> int:
        """Ouvre (une fois) un relais 0.0.0.0:<libre> -> host:port et renvoie le port local."""
        with self.lock:
            if port in self.relays:
                return self.relays[port]
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", 0))
            server.listen(16)
            self.relays[port] = server.getsockname()[1]
        threading.Thread(target=_accept_loop, args=(server, host, port), daemon=True).start()
        return self.relays[port]


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while data := src.recv(65536):
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _accept_loop(server: socket.socket, host: str, port: int) -> None:
    while True:
        client, _ = server.accept()
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            client.close()
            continue
        upstream.settimeout(None)
        threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
        threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()


def make_handler(agent: Agent, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # journal discret
            sys.stderr.write("[agent] " + fmt % args + "\n")

        def _reply(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle(self, method: str) -> None:
            url = urlparse(self.path)
            if url.path == "/health":
                return self._reply(200, {"status": "ok", "root": str(agent.root), "bundled": str(agent.bundled),
                                         "work_dir": str(agent.work_dir),
                                         "vagrant": bool(shutil.which(agent.vagrant)),
                                         "virtualbox": bool(agent.vboxmanage),
                                         "engine": (agent.engine_dir / "Vagrantfile").exists()})
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if not token or not hmac.compare_digest(supplied, token):
                return self._reply(401, {"detail": "jeton invalide"})
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            lab = query.get("lab", "")
            try:
                if method == "GET" and url.path == "/status":
                    return self._reply(200, agent.status(lab))
                if method == "GET" and url.path == "/ssh":
                    return self._reply(200, agent.ssh(lab, query.get("machine", "")))
                if method == "POST" and url.path == "/exclusive":
                    return self._reply(200, {"paused": agent.exclusive(lab)})
                if method == "POST" and url.path == "/up" and lab == ENGINE and "ports" in query:
                    agent.engine_ports = parse_ports(query["ports"])
                actions = agent.lab_actions(lab) if method == "POST" else {}
                if url.path in actions:
                    action, commands = actions[url.path]
                    agent.run_job(lab, action, *commands)
                    return self._reply(202, {"status": "starting" if action == "up" else "stopping"})
            except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
                return self._reply(400, {"detail": str(exc)})
            return self._reply(404, {"detail": "inconnu"})

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler


def read_env_file(path: Path) -> dict[str, str]:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"')
    return values


def main() -> int:
    env = {**read_env_file(ROOT_DIR / ".env"), **os.environ}
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=env.get("TDM_VAGRANT_DIR"), help="dossier contenant les labs Vagrant")
    parser.add_argument("--port", type=int, default=int(env.get("TDM_VAGRANT_AGENT_PORT", 7777)))
    parser.add_argument("--token", default=env.get("TDM_VAGRANT_TOKEN"))
    parser.add_argument("--vagrant", default=shutil.which("vagrant") or "vagrant")
    parser.add_argument("--bundled", default=env.get("TDM_WINDOWS_LABS_DIR") or str(default_bundled_dir()),
                        help="dossier des labs embarqués (labs/systemes-windows)")
    parser.add_argument("--work-dir", default=env.get("TDM_VAGRANT_WORK_DIR") or str(default_work_dir()),
                        help="copie persistante des labs embarqués")
    args = parser.parse_args()
    if not args.root or not Path(args.root).is_dir():
        # Les labs Windows embarqués fonctionnent quand même : on prévient seulement.
        print("Dossier de tes labs Vagrant introuvable (--root ou TDM_VAGRANT_DIR dans .env) : "
              "seuls les labs embarqués de TDM seront disponibles.", file=sys.stderr)
    if not args.token:
        print("Jeton manquant : définis TDM_VAGRANT_TOKEN (start.bat le crée dans .env).", file=sys.stderr)
        return 1
    agent = Agent(Path(args.root) if args.root else None, args.vagrant, bundled=Path(args.bundled), work_dir=Path(args.work_dir))
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(agent, args.token))
    print(f"Agent Vagrant TDM prêt sur le port {args.port} (labs : {agent.root} ; "
          f"labs embarqués : {agent.bundled}, copiés dans {agent.work_dir})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
