"""Moulinette Python : exécutée DANS le bac à sable, uniquement avec la stdlib.

Usage : python runner.py <dossier> <jeton>

Le dossier contient ``solution.py`` (le code de l'élève) et ``spec.json`` :
    {"mode": "function", "tests": "<code python avec des fonctions test_*>"}
    {"mode": "stdio", "cases": [{"input": "...", "output": "...", "name": "..."}]}

Le résultat est écrit sur la sortie standard sur une ligne préfixée par le jeton.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import traceback

CASE_TIMEOUT = 5


def _short_traceback(exc):
    frames = traceback.extract_tb(exc.__traceback__)
    student = [f for f in frames if f.filename.endswith("solution.py")]
    where = ""
    if student:
        last = student[-1]
        where = " (solution.py, ligne %d)" % last.lineno
    return "%s: %s%s" % (type(exc).__name__, exc, where)


def _load_solution(workdir):
    spec = importlib.util.spec_from_file_location("solution", os.path.join(workdir, "solution.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["solution"] = module
    spec.loader.exec_module(module)
    return module


def run_function_tests(workdir, tests_code):
    results = []
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            solution = _load_solution(workdir)
    except BaseException as exc:  # noqa: BLE001 - on veut tout attraper
        return [{
            "name": "chargement",
            "passed": False,
            "message": "Impossible de charger ton code : " + _short_traceback(exc),
        }], captured.getvalue()

    namespace = {"solution": solution, "__name__": "tests"}
    exec(compile(tests_code, "tests.py", "exec"), namespace)
    tests = [(name, fn) for name, fn in namespace.items() if name.startswith("test_") and callable(fn)]

    for name, fn in tests:
        label = (fn.__doc__ or name).strip()
        try:
            with contextlib.redirect_stdout(captured):
                fn()
        except AssertionError as exc:
            message = str(exc) or "Le résultat n'est pas celui attendu."
            results.append({"name": label, "passed": False, "message": message})
        except BaseException as exc:  # noqa: BLE001
            results.append({"name": label, "passed": False, "message": _short_traceback(exc)})
        else:
            results.append({"name": label, "passed": True, "message": ""})
    return results, captured.getvalue()


def _normalize(text):
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def run_stdio_tests(workdir, cases):
    results = []
    for index, case in enumerate(cases, start=1):
        name = case.get("name") or "Cas %d" % index
        try:
            proc = subprocess.run(
                [sys.executable, "solution.py"],
                cwd=workdir,
                input=case.get("input", ""),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CASE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            results.append({"name": name, "passed": False, "message": "Temps dépassé (boucle infinie ?)"})
            continue
        got = _normalize(proc.stdout)
        expected = _normalize(case.get("output", ""))
        if proc.returncode != 0 and got != expected:
            err = proc.stderr.strip().splitlines()
            results.append({
                "name": name,
                "passed": False,
                "message": "Erreur à l'exécution : " + (err[-1] if err else "code %d" % proc.returncode),
            })
        elif got == expected:
            results.append({"name": name, "passed": True, "message": ""})
        else:
            message = "Entrée :\n%s\nAttendu :\n%s\nObtenu :\n%s" % (
                case.get("input", "").rstrip() or "(aucune)", expected, got or "(rien)")
            results.append({"name": name, "passed": False, "message": message})
    return results, ""


def main():
    workdir, token = sys.argv[1], sys.argv[2]
    del sys.argv[1:]
    with open(os.path.join(workdir, "spec.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    sys.path.insert(0, workdir)
    os.chdir(workdir)
    if spec["mode"] == "stdio":
        results, output = run_stdio_tests(workdir, spec["cases"])
    else:
        results, output = run_function_tests(workdir, spec["tests"])
    payload = {"results": results, "output": output[-5000:]}
    sys.__stdout__.write("\n" + token + json.dumps(payload) + "\n")
    sys.__stdout__.flush()


if __name__ == "__main__":
    main()
