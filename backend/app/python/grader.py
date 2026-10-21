"""Exécution et correction des exercices Python."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from .. import sandbox

RUNNER_SOURCE = (Path(__file__).parent / "runner.py").read_text(encoding="utf-8")


def build_spec(exercise: dict[str, Any]) -> dict[str, Any]:
    if exercise.get("mode", "function") == "stdio":
        return {"mode": "stdio", "cases": exercise.get("cases", [])}
    return {"mode": "function", "tests": exercise.get("tests", "")}


def grade(exercise: dict[str, Any], code: str) -> dict[str, Any]:
    token = "@@TDM-" + secrets.token_hex(8) + "@@"
    files = {
        "solution.py": code,
        "spec.json": json.dumps(build_spec(exercise)),
        "_tdm_runner.py": RUNNER_SOURCE,
    }
    run = sandbox.run_python(files, ["{workdir}/_tdm_runner.py", "{workdir}", token])
    if run.timed_out:
        return _failure("Temps dépassé : ton code met trop de temps (boucle infinie ?).")

    payload = None
    for line in reversed(run.stdout.splitlines()):
        if line.startswith(token):
            payload = json.loads(line[len(token):])
            break
    if payload is None:
        detail = (run.stderr.strip().splitlines() or ["erreur inconnue"])[-1]
        if "MemoryError" in run.stderr:
            detail = "Mémoire dépassée."
        return _failure(f"La moulinette n'a pas pu s'exécuter : {detail}")

    results = payload["results"]
    passed = sum(1 for r in results if r["passed"])
    return {
        "success": bool(results) and passed == len(results),
        "passed": passed,
        "total": len(results),
        "results": results,
        "output": payload.get("output", ""),
    }


def run(code: str, stdin: str = "") -> dict[str, Any]:
    result = sandbox.run_python({"solution.py": code}, ["{workdir}/solution.py"], stdin=stdin)
    return {
        "stdout": result.stdout[-20000:],
        "stderr": result.stderr[-20000:],
        "returncode": result.returncode,
        "timed_out": result.timed_out,
    }


def _failure(message: str) -> dict[str, Any]:
    return {
        "success": False,
        "passed": 0,
        "total": 0,
        "results": [{"name": "moulinette", "passed": False, "message": message}],
        "output": "",
    }
