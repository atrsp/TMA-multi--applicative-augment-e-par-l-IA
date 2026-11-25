"""Un nouveau ticket arrive : à quel problème connu ressemble-t-il ?

On compare le vecteur du ticket au CENTRE de chaque groupe :
  - assez proche d'un centre -> « problème connu » ;
  - trop loin de tous        -> « nouveau problème », à traiter normalement.
"""
import numpy as np


def rattacher(x, ids, centres, seuil):
    """Compare un vecteur aux centres des groupes.

    x       : vecteur du nouveau ticket (norme 1)
    ids     : numéros des groupes, dans l'ordre des lignes de `centres`
    seuil   : similarité minimale pour dire « problème connu » (0,6 par défaut)

    Renvoie {"connu": bool, "groupe": numéro du groupe le plus proche ou None, "score": cosinus}.
    """
    if len(ids) == 0:
        return {"connu": False, "groupe": None, "score": 0.0}
    similarites = centres @ x                    # cosinus avec chaque centre (vecteurs de norme 1)
    meilleur = int(np.argmax(similarites))
    score = float(similarites[meilleur])
    return {"connu": score >= seuil, "groupe": ids[meilleur], "score": round(score, 3)}


def rattacher_tous(X, ids, centres):
    """Même calcul pour toute une matrice de tickets. Renvoie (meilleur groupe, score) par ticket."""
    if len(ids) == 0 or len(X) == 0:
        return [None] * len(X), [0.0] * len(X)
    similarites = X @ centres.T
    meilleurs = similarites.argmax(axis=1)
    scores = similarites.max(axis=1)
    return [ids[i] for i in meilleurs], [round(float(s), 3) for s in scores]


def plus_proches(x, X, positions, nb=3):
    """Les `nb` tickets passés les plus proches du nouveau ticket, parmi `positions`.

    Renvoie une liste de (position dans X, cosinus), du plus proche au moins proche.
    """
    if len(positions) == 0:
        return []
    similarites = X[positions] @ x
    ordre = np.argsort(-similarites)[:nb]
    return [(int(positions[i]), round(float(similarites[i]), 3)) for i in ordre]
