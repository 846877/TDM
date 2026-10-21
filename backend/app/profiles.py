"""Profils joueurs : expérience (XP), niveaux, titres et classement.

Les profils et les exercices réussis sont enregistrés dans une base SQLite
(``TDM_DATA_DIR/tdm.db``). L'XP n'est accordée qu'après une validation faite par le serveur
(moulinette Python, vérification réseau ou vérification d'un exercice de lab), une seule fois par
exercice.
"""

from __future__ import annotations

import contextlib
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from . import config

XP_BY_LEVEL = {"debutant": 10, "intermediaire": 25, "avance": 50, "expert": 100}

# (niveau minimal, titre, description)
TITLES = [
    (1, "Recrue", "Premiers pas dans le terminal."),
    (3, "Apprenti", "Les bases sont là."),
    (5, "Technicien", "Tu dépannes sans paniquer."),
    (8, "Administrateur", "Tu tiens une infra debout."),
    (12, "Ingénieur", "Tu conçois, automatises et documentes."),
    (16, "Expert", "On vient te chercher pour les problèmes difficiles."),
    (20, "Architecte", "Tu vois le système dans son ensemble."),
    (25, "Légende", "Plus grand-chose ne te résiste."),
]
GOD_TITLE = ("GOD", "Créateur de la plateforme. Au-dessus de tous les niveaux.")

CATEGORY_TITLES = {
    "python": ["Pythoniste débutant", "Pythoniste", "Pythoniste confirmé", "Maître Python"],
    "reseaux": ["Câbleur", "Technicien réseau", "Ingénieur réseau", "Maître Cisco"],
    "systemes": ["Technicien de proximité", "Technicien systèmes et réseaux", "Administrateur systèmes et réseaux",
                 "Maître de l'infra"],
    "devops": ["Bidouilleur", "Opérateur", "Ingénieur DevOps", "Maître SRE"],
}

NAME_PATTERN = re.compile(r"^[\w .'-]{2,24}$", re.UNICODE)
_lock = threading.Lock()


class ProfileError(ValueError):
    pass


def god_names() -> set[str]:
    return {n.strip().lower() for n in os.environ.get("TDM_GOD_PROFILES", "TDM").split(",") if n.strip()}


def db_path() -> Path:
    return config.DATA_DIR / "tdm.db"


@contextlib.contextmanager
def _connect():
    """Connexion courte : validée (commit) puis fermée à la sortie du bloc."""
    conn = _open()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _open() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS completions (
            profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            category TEXT NOT NULL,
            item_id TEXT NOT NULL,
            level TEXT NOT NULL,
            xp INTEGER NOT NULL,
            completed_at REAL NOT NULL,
            PRIMARY KEY (profile_id, category, item_id)
        );
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Niveaux et titres
# ---------------------------------------------------------------------------

def xp_for_level(level: int) -> int:
    """XP totale nécessaire pour atteindre ``level`` (niveau 1 = 0 XP, puis de plus en plus long)."""
    return 25 * level * (level - 1)


def level_for_xp(xp: int) -> int:
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


def title_for(level: int, name: str = "") -> dict[str, str]:
    if name.lower() in god_names():
        return {"name": GOD_TITLE[0], "description": GOD_TITLE[1], "god": True}
    current = TITLES[0]
    for entry in TITLES:
        if level >= entry[0]:
            current = entry
    return {"name": current[1], "description": current[2], "god": False}


def category_title(category: str, done: int, total: int) -> str | None:
    if not done or not total:
        return None
    ratio = done / total
    index = 0 if ratio < 0.25 else 1 if ratio < 0.5 else 2 if ratio < 0.9 else 3
    return CATEGORY_TITLES[category][index]


# ---------------------------------------------------------------------------
# Profils
# ---------------------------------------------------------------------------

def _summary(row: sqlite3.Row) -> dict[str, Any]:
    xp = row["xp"] or 0
    level = level_for_xp(xp)
    return {
        "id": row["id"],
        "name": row["name"],
        "xp": xp,
        "level": level,
        "title": title_for(level, row["name"]),
        "completed": row["completed"] or 0,
        "level_xp": xp_for_level(level),
        "next_level_xp": xp_for_level(level + 1),
    }


_SUMMARY_SQL = """
    SELECT p.id, p.name, p.created_at, COALESCE(SUM(c.xp), 0) AS xp, COUNT(c.item_id) AS completed
    FROM profiles p LEFT JOIN completions c ON c.profile_id = p.id
"""


def list_profiles() -> list[dict[str, Any]]:
    """Profils triés pour le classement : XP décroissante, puis le plus ancien en premier."""
    with _connect() as conn:
        rows = conn.execute(_SUMMARY_SQL + " GROUP BY p.id ORDER BY xp DESC, p.created_at ASC").fetchall()
    ranked = []
    for rank, row in enumerate(rows, start=1):
        ranked.append(_summary(row) | {"rank": rank})
    return ranked


def create_profile(name: str) -> dict[str, Any]:
    name = " ".join(name.split())
    if not NAME_PATTERN.match(name):
        raise ProfileError("Le pseudo doit faire 2 à 24 caractères (lettres, chiffres, espace, . ' - _).")
    with _lock, _connect() as conn:
        try:
            cur = conn.execute("INSERT INTO profiles (name, created_at) VALUES (?, ?)", (name, time.time()))
        except sqlite3.IntegrityError as exc:
            raise ProfileError("Ce pseudo est déjà pris.") from exc
        profile_id = cur.lastrowid
    return get_profile(profile_id)


def delete_profile(profile_id: int) -> None:
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM completions WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


def get_profile(profile_id: int) -> dict[str, Any] | None:
    ranked = list_profiles()
    entry = next((p for p in ranked if p["id"] == profile_id), None)
    if entry is None:
        return None
    with _connect() as conn:
        rows = conn.execute(
            "SELECT category, item_id, level, xp, completed_at FROM completions WHERE profile_id = ? "
            "ORDER BY completed_at DESC", (profile_id,)).fetchall()
    completed: dict[str, list[str]] = {}
    by_category: dict[str, dict[str, Any]] = {}
    for row in rows:
        completed.setdefault(row["category"], []).append(row["item_id"])
        stats = by_category.setdefault(row["category"], {"done": 0, "xp": 0, "levels": {}})
        stats["done"] += 1
        stats["xp"] += row["xp"]
        stats["levels"][row["level"]] = stats["levels"].get(row["level"], 0) + 1
    recent = [dict(row) for row in rows[:10]]
    return entry | {
        "total_profiles": len(ranked),
        "completed_items": completed,
        "categories": by_category,
        "recent": recent,
    }


def record_success(profile_id: int, category: str, item_id: str, level: str) -> dict[str, Any] | None:
    """Enregistre un exercice réussi. Renvoie le gain d'XP (0 si déjà réussi) et l'état du profil."""
    before = get_profile(profile_id)
    if before is None:
        return None
    xp = XP_BY_LEVEL.get(level, XP_BY_LEVEL["debutant"])
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO completions (profile_id, category, item_id, level, xp, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)", (profile_id, category, item_id, level, xp, time.time()))
        gained = xp if cur.rowcount else 0
    after = get_profile(profile_id)
    return {
        "xp_gained": gained,
        "level_up": after["level"] > before["level"],
        "new_title": after["title"]["name"] if after["title"]["name"] != before["title"]["name"] else None,
        "profile": {k: after[k] for k in ("id", "name", "xp", "level", "title", "rank", "level_xp", "next_level_xp",
                                          "completed")},
    }


def titles_ladder() -> list[dict[str, Any]]:
    return [{"level": lvl, "name": name, "description": desc, "xp": xp_for_level(lvl)} for lvl, name, desc in TITLES]
