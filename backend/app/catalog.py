"""Chargement des contenus (exercices Python, exercices réseau, labs DevOps)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import config

LEVELS = ["debutant", "intermediaire", "avance", "expert"]
LEVEL_LABELS = {
    "debutant": "Débutant",
    "intermediaire": "Intermédiaire",
    "avance": "Avancé",
    "expert": "Expert",
}


class ContentError(ValueError):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ContentError(f"{path}: le fichier doit contenir un objet YAML")
    data.setdefault("id", path.stem)
    return data


def _sort_key(item: dict[str, Any]):
    level = item.get("level", "debutant")
    return (LEVELS.index(level) if level in LEVELS else len(LEVELS), item.get("order", 999), item["id"])


def load_exercises(category: str, content_dir: Path | None = None) -> list[dict[str, Any]]:
    folder = (content_dir or config.CONTENT_DIR) / category
    if not folder.is_dir():
        return []
    items = []
    for path in sorted(folder.glob("*.yaml")):
        data = _load_yaml(path)
        for key in ("title", "level", "description"):
            if key not in data:
                raise ContentError(f"{path}: champ obligatoire manquant : {key}")
        if data["level"] not in LEVELS:
            raise ContentError(f"{path}: niveau inconnu {data['level']!r} (attendu : {', '.join(LEVELS)})")
        items.append(data)
    ids = [item["id"] for item in items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ContentError(f"identifiants dupliqués dans {category}: {sorted(duplicates)}")
    return sorted(items, key=_sort_key)


class Catalog:
    """Cache simple, rechargé à la demande (pratique pendant qu'on écrit des exercices)."""

    def __init__(self, category: str):
        self.category = category
        self._items: dict[str, dict[str, Any]] | None = None

    def reload(self) -> None:
        self._items = {item["id"]: item for item in load_exercises(self.category)}

    def all(self) -> list[dict[str, Any]]:
        if self._items is None:
            self.reload()
        return list(self._items.values())

    def get(self, exercise_id: str) -> dict[str, Any] | None:
        if self._items is None:
            self.reload()
        return self._items.get(exercise_id)


PUBLIC_SUMMARY_FIELDS = ("id", "title", "level", "order", "tags", "summary")


def summary(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in PUBLIC_SUMMARY_FIELDS if key in item}
