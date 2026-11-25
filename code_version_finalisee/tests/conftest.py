"""Préparation commune à tous les tests.

Les tests du moteur tournent sur le VRAI jeu de démonstration (tma-data/data/tickets.json)
avec le vrai modèle SBERT. L'analyse complète n'est lancée qu'une fois pour toute la
session de tests (scope="session"), puis réutilisée par chaque test.
"""
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))            # pour pouvoir écrire « from app... » dans les tests

from app.moteur import pipeline            # noqa: E402  (import après la ligne ci-dessus)
from app.sources import fichier            # noqa: E402

DEMO = RACINE.parent / "tma-data" / "data" / "tickets.json"
CACHE = RACINE / "data"                    # même cache d'embeddings que l'application


def charger_demo():
    """Relit le jeu de démonstration (une liste neuve à chaque appel)."""
    return fichier.lire_tickets(DEMO)


@pytest.fixture(scope="session")
def analyse_demo():
    """Analyse du jeu de démonstration avec les réglages par défaut."""
    if not DEMO.exists():
        pytest.skip(f"Jeu de démonstration introuvable : {DEMO}")
    return pipeline.analyser(charger_demo(), dossier_cache=CACHE)
