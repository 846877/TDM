"""Exécution isolée du code des élèves.

Deux modes :
- ``docker`` : un conteneur jetable, sans réseau, mémoire/CPU/processus limités ;
- ``local``  : un sous-processus avec des limites ``resource`` (pratique pour développer,
  mais ce n'est PAS une vraie isolation : à réserver à un usage personnel).
"""

from __future__ import annotations

import io
import os
import secrets
import shlex
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _limit_resources() -> None:  # pragma: no cover - exécuté dans le processus fils
    import resource

    memory = config.MEMORY_LIMIT_MB * 1024 * 1024
    cpu = int(config.RUN_TIMEOUT) + 1
    for limit, value in (
        (resource.RLIMIT_AS, memory),
        (resource.RLIMIT_CPU, cpu),
        (resource.RLIMIT_FSIZE, 10 * 1024 * 1024),
    ):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            pass
    os.setsid()


def _local_env(workdir: Path) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
           "HOME": str(workdir)}
    if os.name == "nt":  # variables sans lesquelles Python ne démarre pas correctement sous Windows
        for key in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "COMSPEC"):
            if key in os.environ:
                env[key] = os.environ[key]
    return env


def _docker_limits() -> list[str]:
    return [
        "--network", "none",
        "--memory", f"{config.MEMORY_LIMIT_MB}m",
        "--cpus", "1",
        "--pids-limit", "128",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:exec,mode=1777,size=64m",
        "--tmpfs", "/work:exec,mode=1777,size=64m",
        "-w", "/work",
    ]


def _tar(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def run_python(files: dict[str, str], argv: list[str], stdin: str = "", timeout: float | None = None) -> RunResult:
    """Lance ``python <argv>`` dans le bac à sable avec ``files`` dans son dossier de travail.

    Les chemins dans ``argv`` peuvent utiliser ``{workdir}`` pour désigner ce dossier.
    """
    timeout = timeout or config.RUN_TIMEOUT
    if config.use_docker_sandbox():
        return _run_docker(files, argv, stdin, timeout)
    with tempfile.TemporaryDirectory(prefix="tdm-run-") as tmp:
        workdir = Path(tmp)
        for name, content in files.items():
            (workdir / name).write_text(content, encoding="utf-8")
        cmd = [*config.python_command(), *(a.replace("{workdir}", str(workdir)) for a in argv)]
        try:
            proc = subprocess.run(
                cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout, cwd=workdir, env=_local_env(workdir),
                # Pas de limites « resource » sous Windows : seul le délai maximal s'applique.
                preexec_fn=_limit_resources if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(-1, _decode(exc.stdout), _decode(exc.stderr), timed_out=True)
        return RunResult(proc.returncode, proc.stdout, proc.stderr)


def _run_docker(files: dict[str, str], argv: list[str], stdin: str, timeout: float) -> RunResult:
    # Les fichiers passent par l'entrée standard (archive tar) plutôt que par un volume :
    # ça fonctionne aussi quand la plateforme tourne elle-même dans un conteneur (Windows, macOS).
    name = "tdm-run-" + secrets.token_hex(6)
    inner = " ".join(shlex.quote(a.replace("{workdir}", "/work")) for a in argv)
    script = f"tar -x -C /work && exec timeout -s KILL {int(timeout) + 1} python {inner} < /work/.stdin"
    cmd = ["docker", "run", "--rm", "-i", "--name", name, *_docker_limits(), config.SANDBOX_IMAGE, "sh", "-c", script]
    payload = _tar({**files, ".stdin": stdin})
    try:
        proc = subprocess.run(cmd, input=payload, capture_output=True, timeout=timeout + 15)
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        return RunResult(-1, _decode(exc.stdout), _decode(exc.stderr), timed_out=True)
    stdout, stderr = _decode(proc.stdout), _decode(proc.stderr)
    return RunResult(proc.returncode, stdout, stderr, timed_out=proc.returncode == 137)


def start_terminal_container(name: str) -> None:
    """Démarre un conteneur de bac à sable persistant pour le terminal d'un exercice."""
    cmd = ["docker", "run", "-d", "--rm", "--name", name, *_docker_limits(),
           "-e", "TERM=xterm-256color", "-e", "PS1=tdm:\\W$ ", config.SANDBOX_IMAGE, "sleep", "infinity"]
    subprocess.run(cmd, capture_output=True, check=True, timeout=60)


def write_to_container(name: str, filename: str, content: str) -> None:
    subprocess.run(["docker", "exec", "-i", name, "sh", "-c", f"cat > /work/{shlex.quote(filename)}"],
                   input=content.encode("utf-8"), capture_output=True, timeout=10)


def _decode(data) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data
