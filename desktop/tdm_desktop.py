"""Application de bureau TDM (Windows) : la plateforme dans sa propre fenêtre.

Au lancement :
- lit les réglages de ``%APPDATA%\\TDM\\tdm.env`` (créé au premier lancement) ;
- démarre l'agent Vagrant dans le même processus, pour les labs en machine virtuelle et le moteur
  Docker de TDM (petite VM VirtualBox démarrée au premier lab Docker, sans Docker Desktop) ;
- démarre le serveur sur 127.0.0.1 et l'affiche dans une fenêtre (WebView2, via pywebview).

À la fermeture de la fenêtre, les VM lancées par TDM (labs, moteur Docker) sont mises en pause
(``vagrant suspend``) pour libérer la mémoire. Si TDM est tué brutalement, elles restent simplement
allumées et sont reprises au lancement suivant.

``TDM.exe --no-window`` démarre seulement le serveur (utile pour les tests).
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

APP_NAME = "TDM"
DEFAULT_PORT = 8765  # port fixe : la progression est mémorisée par origine dans la fenêtre

SETTINGS_TEMPLATE = """# Réglages de l'application TDM. Relance TDM après une modification.

# Dossier qui contient tes labs Vagrant (un Vagrantfile par lab).
TDM_VAGRANT_DIR={vagrant_dir}

# Les labs Windows livrés avec TDM (Systèmes & réseaux > Windows) sont copiés et lancés depuis
# %LOCALAPPDATA%\TDM\vagrant. Décommente pour choisir un autre dossier (disque avec de la place) :
# TDM_VAGRANT_WORK_DIR=D:\VM\TDM

# Exécution du code Python des exercices : local (rapide) ou docker (isolé, Docker Desktop requis).
TDM_SANDBOX=local

# Moteur Docker des labs : auto (Docker Desktop s'il répond, sinon le moteur de TDM : une petite VM
# VirtualBox démarrée au premier lab Docker), desktop (toujours Docker Desktop) ou vm (toujours la VM).
# Avec la VM, l'hyperviseur Windows peut rester désactivé : les VM Windows des labs vont bien plus vite.
TDM_DOCKER=auto
# Mémoire de la VM moteur en Mo (GitLab, k3s : 4096 conseillés).
# TDM_DOCKER_VM_MEMORY=2048
"""


def settings_dir() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / ".config") / APP_NAME


def data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / APP_NAME


def guess_vagrant_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [home / "Desktop", home / "Bureau"]
    for onedrive in ("OneDrive", *(p.name for p in home.glob("OneDrive*"))):
        candidates += [home / onedrive / "Desktop", home / onedrive / "Bureau"]
    for desktop in candidates:
        folder = desktop / "INFORMATIQUE" / "devops" / "vagrant"
        if folder.is_dir():
            return folder
    return home / "Desktop" / "INFORMATIQUE" / "devops" / "vagrant"


def load_settings() -> dict[str, str]:
    path = settings_dir() / "tdm.env"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SETTINGS_TEMPLATE.format(vagrant_dir=guess_vagrant_dir()), encoding="utf-8")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def hide_console_windows() -> None:
    """Sans console (application fenêtrée), chaque appel à docker/vagrant ouvrirait une fenêtre noire."""
    if os.name != "nt":
        return
    original = subprocess.Popen.__init__

    def init(self, *args, **kwargs):
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        kwargs.setdefault("stdin", subprocess.DEVNULL)
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = init


def redirect_output() -> None:
    """Une application fenêtrée n'a pas de sortie standard : on écrit le journal dans un fichier."""
    if sys.stdout is None or sys.stderr is None:
        data_dir().mkdir(parents=True, exist_ok=True)
        log = open(data_dir() / "tdm.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def free_port(preferred: int) -> int:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


def setup_docker_cli() -> None:
    """Client docker embarqué (docker.exe + plugin compose) quand aucun n'est installé (pas de Docker Desktop).

    Il ne sert qu'à parler au moteur Docker de TDM (VM). Le plugin compose est copié dans
    %LOCALAPPDATA%\\TDM\\docker\\cli-plugins, désigné par DOCKER_CONFIG.
    """
    from app import config

    bundled = config.ROOT_DIR / "docker"
    if shutil.which("docker") or not (bundled / "docker.exe").exists():
        return
    os.environ["PATH"] = str(bundled) + os.pathsep + os.environ.get("PATH", "")
    docker_config = data_dir() / "docker"
    plugin = bundled / "cli-plugins" / "docker-compose.exe"
    target = docker_config / "cli-plugins" / "docker-compose.exe"
    if plugin.exists() and (not target.exists() or target.stat().st_size != plugin.stat().st_size):
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(plugin, target)
        except OSError as exc:  # plugin en cours d'utilisation par un ancien TDM : on garde l'ancien
            print(f"Plugin compose non mis à jour : {exc}", flush=True)
    os.environ.setdefault("DOCKER_CONFIG", str(docker_config))


def start_vagrant_agent(settings: dict[str, str]):
    import vagrant_agent

    from app import config

    token = secrets.token_hex(16)
    vagrant = shutil.which("vagrant") or "vagrant"
    # Les labs Windows embarqués sont dans le dossier temporaire de l'exe (_MEIPASS) : l'agent les copie
    # dans %LOCALAPPDATA%\TDM\vagrant avant chaque `vagrant up`, pour que l'état des VM survive.
    # Il en va de même du moteur Docker de TDM (labs/moteur-docker).
    agent = vagrant_agent.Agent(Path(settings.get("TDM_VAGRANT_DIR") or guess_vagrant_dir()), vagrant, relay=False,
                                bundled=config.WINDOWS_LABS_DIR, engine_dir=config.DOCKER_ENGINE_DIR,
                                work_dir=Path(settings.get("TDM_VAGRANT_WORK_DIR") or data_dir() / "vagrant"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), vagrant_agent.make_handler(agent, token))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ.update({
        "TDM_VAGRANT_AGENT": f"http://127.0.0.1:{server.server_address[1]}",
        "TDM_VAGRANT_TOKEN": token,
        "TDM_VAGRANT_HOST": "127.0.0.1",
    })
    return agent


def suspend_vms(agent) -> None:
    """Fermeture : met en pause les VM lancées par TDM (labs, moteur Docker) pour libérer la mémoire."""
    try:
        paused = agent.suspend_all()
    except Exception as exc:  # noqa: BLE001 - la fermeture ne doit jamais échouer pour ça
        print(f"Mise en pause des VM impossible : {exc!r}", flush=True)
        return
    if paused:
        print("VM mises en pause : " + ", ".join(paused), flush=True)


def start_server(port: int):
    import uvicorn

    from app.main import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None,
                                          loop="asyncio", http="h11", ws="auto"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1)
            return server, url
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Le serveur TDM n'a pas démarré (voir tdm.log).")


def open_window(url: str, test: bool = False) -> bool:
    """Affiche la plateforme dans une fenêtre ; False si c'est impossible (le navigateur prend le relais)."""
    try:
        import webview

        storage = data_dir() / "webview"
        storage.mkdir(parents=True, exist_ok=True)
        window = webview.create_window("TDM - plateforme d'entraînement", url, width=1400, height=900,
                                       min_size=(900, 600))
        loaded = threading.Event()
        window.events.loaded += loaded.set

        def close_when_loaded() -> None:
            if loaded.wait(60):
                print("Fenêtre chargée", flush=True)
            window.destroy()

        webview.start(close_when_loaded if test else None, private_mode=False, storage_path=str(storage))
        return loaded.is_set() or not test
    except Exception as exc:  # noqa: BLE001 - WebView2 absent, etc.
        print(f"Fenêtre indisponible : {exc!r}", flush=True)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(prog="TDM")
    parser.add_argument("--no-window", action="store_true", help="démarre seulement le serveur")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--window-test", action="store_true", help=argparse.SUPPRESS)  # ouvre puis ferme la fenêtre
    args = parser.parse_args()

    redirect_output()
    hide_console_windows()
    settings = load_settings()
    for key, value in settings.items():
        os.environ.setdefault(key, value)
    os.environ.setdefault("TDM_SANDBOX", "local")
    setup_docker_cli()
    agent = start_vagrant_agent(settings)
    server, url = start_server(free_port(args.port))
    print(f"TDM prêt sur {url}", flush=True)

    if args.no_window:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    elif not open_window(url, args.window_test):
        if args.window_test:
            return 1
        import webbrowser

        webbrowser.open(url)
        while True:
            time.sleep(1)
    server.should_exit = True
    if not args.window_test:
        suspend_vms(agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
