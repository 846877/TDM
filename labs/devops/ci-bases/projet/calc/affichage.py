"""Mise en forme des résultats."""
import os
import sys


def formater(resultat, decimales=2):
    """Renvoie le résultat arrondi, précédé d'une étiquette."""
    valeur = round(resultat, decimales)
    return f"Résultat : {valeur}"
