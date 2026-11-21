#!/usr/bin/env python3
"""Importe une collection de labs DevOps dans la plateforme.

Usage :
    python scripts/import_labs.py /chemin/vers/mes-labs [--dest labs/devops] [--dry-run]

Chaque sous-dossier de la source devient un lab. Si le dossier contient déjà un ``lab.yaml``,
il est copié tel quel ; sinon un ``lab.yaml`` de départ est généré à partir de ce qui est trouvé
(README, Dockerfile, docker-compose, scripts de vérification ``check*.sh``).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

LEVEL_HINTS = {
    "debutant": ("intro", "basic", "base", "debut", "101", "beginner", "getting-started"),
    "avance": ("advanced", "avance", "prod", "ha", "cluster", "security"),
    "expert": ("expert", "chaos", "multi-cluster", "operator"),
}
COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def guess_level(name: str) -> str:
    low = name.lower()
    for level, hints in LEVEL_HINTS.items():
        if any(h in low for h in hints):
            return level
    return "intermediaire"


def title_from(folder: Path, readme: str) -> str:
    match = re.search(r"^#\s+(.+)$", readme, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return re.sub(r"[-_]+", " ", folder.name).strip().capitalize()


def build_lab(folder: Path) -> dict:
    readme_path = next((p for p in folder.iterdir() if p.name.lower() == "readme.md"), None)
    readme = readme_path.read_text(encoding="utf-8", errors="replace") if readme_path else ""
    lab: dict = {
        "title": title_from(folder, readme),
        "level": guess_level(folder.name),
        "summary": "",
        "tags": [],
    }
    compose = next((folder / n for n in COMPOSE_NAMES if (folder / n).exists()), None)
    if (folder / "Dockerfile").exists():
        lab["build"] = "."
    elif compose:
        lab["compose"] = compose.name
        services = list((yaml.safe_load(compose.read_text()) or {}).get("services", {}))
        lab["service"] = services[0] if services else "TODO"
    else:
        lab["image"] = "ubuntu:24.04"
    exercises = []
    for index, script in enumerate(sorted(folder.glob("check*.sh")), start=1):
        exercises.append({
            "id": script.stem,
            "title": f"Étape {index}",
            "description": "TODO : décrire l'objectif.",
            "check": f"sh /lab/{script.name}",
        })
    if exercises:
        lab["setup"] = "mkdir -p /lab"
        lab["note"] = "Les scripts check*.sh doivent être copiés dans /lab (Dockerfile ou setup)."
    else:
        exercises.append({
            "id": "ex1",
            "title": "TODO",
            "description": "TODO : décrire l'objectif de l'exercice.",
            "check": "true",
        })
    lab["exercises"] = exercises
    return lab


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("--dest", type=Path, default=Path(__file__).resolve().parents[1] / "labs" / "devops")
    parser.add_argument("--dry-run", action="store_true", help="afficher sans rien écrire")
    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"Dossier introuvable : {args.source}", file=sys.stderr)
        return 1
    folders = [p for p in sorted(args.source.iterdir()) if p.is_dir() and not p.name.startswith(".")]
    for folder in folders:
        target = args.dest / folder.name
        has_yaml = (folder / "lab.yaml").exists()
        print(f"{'[existant]' if has_yaml else '[généré] '} {folder.name} -> {target}")
        if args.dry_run:
            continue
        if target.exists():
            print(f"  ignoré : {target} existe déjà")
            continue
        shutil.copytree(folder, target)
        if not has_yaml:
            with (target / "lab.yaml").open("w", encoding="utf-8") as fh:
                yaml.safe_dump(build_lab(folder), fh, allow_unicode=True, sort_keys=False)
    print(f"{len(folders)} lab(s) traité(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
