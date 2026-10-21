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

``<dossier>`` est un chemin relatif à ``--root`` contenant un Vagrantfile. Pour /ssh, l'agent ouvre
un relais TCP accessible depuis Docker vers le port SSH de la VM (que VirtualBox n'écoute que sur
127.0.0.1).

Labs embarqués (``lab=tdm:<nom>``) : les labs Windows livrés avec TDM (``labs/systemes-windows``,
option ``--bundled``). Avant chaque ``vagrant up``, l'agent copie le lab (et le dossier partagé
``_commun``) dans un dossier persistant (``--work-dir``, par défaut ``%LOCALAPPDATA%\\TDM\\vagrant``) et
lance Vagrant depuis cette copie : l'état ``.vagrant`` et la clé SSH générée y survivent, même quand
l'application Windows se décompresse dans un dossier temporaire différent à chaque lancement.
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
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
BUNDLED_PREFIX = "tdm:"
SHARED_DIR = "_commun"  # fichiers partagés par les labs embarqués (copiés à côté de chaque lab)
MANIFEST = ".tdm-manifest"
_BUNDLED_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


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


def _last_progress(text: str) -> str:
    """« Progress: 10% …Progress: 40% … » (progressions collées) -> « Progress: 40% … »."""
    return "Progress:" + text.rsplit("Progress:", 1)[1] if "Progress:" in text else text


class Job:
    """Une suite de commandes vagrant exécutées l'une après l'autre en arrière-plan."""

    def __init__(self, action: str, commands: list[list[str]], cwd: Path):
        self.action = action
        self.log: deque[str] = deque(maxlen=200)
        self.returncode: int | None = None
        self._thread = threading.Thread(target=self._run, args=(commands, cwd), daemon=True)
        self._thread.start()

    def _run(self, commands: list[list[str]], cwd: Path) -> None:
        code = 0
        for argv in commands:
            self.log.append("$ vagrant " + " ".join(argv[1:]))
            process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self._read(process.stdout)
            code = process.wait()
            if code != 0:
                break
        self.returncode = code

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
                 work_dir: Path | None = None):
        self.root = root.resolve() if root else None  # None : seulement les labs embarqués
        self.bundled = (bundled or default_bundled_dir()).resolve()
        self.work_dir = (work_dir or default_work_dir()).resolve()
        self.vagrant = vagrant
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
        source = self.bundled / name
        if not (source / "Vagrantfile").exists():
            raise ValueError(f"lab embarqué introuvable : {name}")
        return source, self.work_dir / name

    def prepare(self, lab: str) -> None:
        """Copie (ou met à jour) un lab embarqué dans sa copie de travail avant `vagrant up`."""
        if not lab.startswith(BUNDLED_PREFIX):
            return
        source, work = self.bundled_dirs(lab)
        sync_tree(source, work)
        shared = self.bundled / SHARED_DIR
        if shared.is_dir():
            sync_tree(shared, self.work_dir / SHARED_DIR)

    def _vagrant(self, path: Path, *args: str, timeout: float = 120) -> subprocess.CompletedProcess:
        return subprocess.run([self.vagrant, *args], cwd=path, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)

    def run_job(self, lab: str, action: str, *commands: list[str]) -> None:
        path = self.lab_dir(lab)
        with self.lock:
            job = self.jobs.get(lab)
            if job and job.running:
                return
            if action == "up":
                self.prepare(lab)
            elif not (path / "Vagrantfile").exists():
                return  # lab embarqué jamais démarré : rien à arrêter
            self.jobs[lab] = Job(action, [[self.vagrant, *c] for c in commands], path)

    def status(self, lab: str) -> dict:
        path = self.lab_dir(lab)
        job = self.jobs.get(lab)
        log = "\n".join(list(job.log)[-15:]) if job else ""
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
                                         "work_dir": str(agent.work_dir)})
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
                actions = {
                    "/up": ("up", [["up"]]),
                    "/halt": ("halt", [["halt"]]),
                    "/reset": ("up", [["destroy", "-f"], ["up"]]),
                }
                if method == "POST" and url.path in actions:
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
