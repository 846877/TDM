"""Traitement d'une commande de la boutique (version non instrumentée).

Utilisation : python commande.py NUMERO [--echec] [--lent]
  --echec : la banque refuse le paiement
  --lent  : la préparation prend du retard (environ 0,7 s)
"""
import sys
import time

# --- Instrumentation OpenTelemetry : à ajouter ici -------------------------------------


# ----------------------------------------------------------------------------------------

CLIENTS = {"alice@example.com": 42.0}


def verifier_stock(commande_id):
    """Vérifie que les articles sont disponibles (simulé localement pour l'instant)."""
    time.sleep(0.05)
    return True


def payer(commande_id, montant, echec=False):
    """Demande le paiement à la banque. Renvoie "acceptee" ou "refusee" (pas d'exception)."""
    time.sleep(0.1)
    if echec:
        return "refusee"
    return "acceptee"


def traiter_commande(commande_id, echec=False, lent=False):
    client_email = "alice@example.com"
    montant = CLIENTS[client_email]
    if not verifier_stock(commande_id):
        return "rupture"
    if lent:
        time.sleep(0.7)
    return payer(commande_id, montant, echec)


if __name__ == "__main__":
    args = sys.argv[1:]
    numero = args[0] if args and not args[0].startswith("--") else "1"
    resultat = traiter_commande(numero, echec="--echec" in args, lent="--lent" in args)
    print(f"commande {numero} : {resultat}")
