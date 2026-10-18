"""Exécution isolée du code des élèves.

Deux modes :
- ``docker`` : un conteneur jetable, sans réseau, mémoire/CPU/processus limités ;
- ``local``  : un sous-processus avec des limites ``resource`` (pratique pour développer,
  mais ce n'est PAS une vraie isolation : à réserver à un usage personnel).
"""

from __future__ import annotations

import os
import subprocess
import sys
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


def docker_run_args(workdir: Path, interactive: bool = False) -> list[str]:
    args = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", f"{config.MEMORY_LIMIT_MB}m",
        "--cpus", "1",
        "--pids-limit", "128",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "-v", f"{workdir}:/work",
        "-w", "/work",
    ]
    if interactive:
        args += ["-it"]
    else:
        args += ["-i", "--read-only", "--tmpfs", "/tmp"]
    return args + [config.SANDBOX_IMAGE]


def run_python(files: dict[str, str], argv: list[str], stdin: str = "", timeout: float | None = None) -> RunResult:
    """Écrit ``files`` dans un dossier temporaire et lance ``python <argv>`` dans le bac à sable.

    Les chemins dans ``argv`` peuvent utiliser ``{workdir}`` pour désigner ce dossier.
    """
    timeout = timeout or config.RUN_TIMEOUT
    with tempfile.TemporaryDirectory(prefix="tdm-run-") as tmp:
        workdir = Path(tmp)
        os.chmod(workdir, 0o777)
        for name, content in files.items():
            (workdir / name).write_text(content, encoding="utf-8")

        if config.use_docker_sandbox():
            inner = [a.replace("{workdir}", "/work") for a in argv]
            cmd = docker_run_args(workdir) + ["python", *inner]
            kwargs: dict = {}
        else:
            inner = [a.replace("{workdir}", str(workdir)) for a in argv]
            cmd = [sys.executable, *inner]
            kwargs = {
                "cwd": workdir,
                "preexec_fn": _limit_resources,
                "env": {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "HOME": str(workdir)},
            }
        try:
            proc = subprocess.run(
                cmd, input=stdin, capture_output=True, text=True, timeout=timeout + (5 if config.use_docker_sandbox() else 0),
                **kwargs,
            )
        except subprocess.TimeoutExpired as exc:
            return RunResult(-1, _decode(exc.stdout), _decode(exc.stderr), timed_out=True)
        return RunResult(proc.returncode, proc.stdout, proc.stderr)


def _decode(data) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data
