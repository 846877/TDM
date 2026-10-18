"""Chaque exercice Python doit être validé par sa solution et refusé avec le code de départ."""

import pytest

from app.catalog import load_exercises
from app.python import grader

EXERCISES = load_exercises("python")


def test_catalogue_non_vide():
    assert len(EXERCISES) >= 40


@pytest.mark.parametrize("exercise", EXERCISES, ids=[e["id"] for e in EXERCISES])
def test_solution_validee(exercise):
    result = grader.grade(exercise, exercise["solution"])
    assert result["success"], result["results"]


@pytest.mark.parametrize("exercise", EXERCISES, ids=[e["id"] for e in EXERCISES])
def test_code_de_depart_refuse(exercise):
    result = grader.grade(exercise, exercise.get("starter", ""))
    assert not result["success"]


def test_boucle_infinie():
    exercise = next(e for e in EXERCISES if e.get("mode", "function") == "function")
    result = grader.grade(exercise, "while True:\n    pass\n")
    assert not result["success"]


def test_execution_simple():
    result = grader.run("print(input()[::-1])", stdin="abc\n")
    assert result["stdout"].strip() == "cba"
