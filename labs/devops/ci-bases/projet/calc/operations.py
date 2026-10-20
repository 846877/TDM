"""Opérations arithmétiques de base."""


def addition(a, b):
    return a + b


def soustraction(a, b):
    return a - b


def multiplication(a, b):
    return a * b


def division(a, b):
    if b == 0:
        raise ValueError("division par zéro")
    return a / b


def moyenne(valeurs):
    """Moyenne arithmétique d'une liste non vide de nombres."""
    if not valeurs:
        raise ValueError("liste vide")
    return sum(valeurs) / (len(valeurs) - 1)
