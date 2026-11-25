"""Regrouper les tickets qui parlent du même problème (HDBSCAN).

HDBSCAN trouve seul le nombre de groupes et met de côté les tickets isolés (le « bruit »,
numéro de groupe -1). Son seul réglage important est la taille minimale d'un groupe.
"""
from collections import Counter

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import normalize

from .nettoyage import normaliser_pour_comparer

# Au-delà de cette part de tickets au texte identique, un groupe n'est pas un vrai
# problème récurrent : c'est un seul texte recopié. On le signale « à vérifier ».
PART_TEXTE_RECOPIE = 0.9


def taille_min_auto(nb_tickets):
    """Taille minimale d'un groupe adaptée au volume de tickets.

    30 convient à ~1 500 tickets (réglage validé sur le jeu de démonstration), mais
    serait bien trop grand pour un fichier de 100 tickets : aucun groupe ne sortirait.
    On prend donc environ 2 % du volume, borné entre 5 et 30.
        100 tickets -> 5      500 tickets -> 10      1 440 tickets et plus -> 30
    """
    return max(5, min(30, nb_tickets // 48))


def regrouper(X, taille_min):
    """Renvoie le numéro de groupe de chaque ticket (-1 = aucun groupe).

    X : matrice des vecteurs (une ligne par ticket, norme 1).
    """
    if len(X) < 2 * taille_min:
        # Trop peu de tickets pour former ne serait-ce que deux groupes : tout est isolé.
        return np.full(len(X), -1, dtype=int)
    return HDBSCAN(min_cluster_size=taille_min, copy=True).fit_predict(X)


def centres_des_groupes(X, groupes):
    """Un vecteur « centre » par groupe : la moyenne de ses tickets, ramenée à la norme 1.

    Renvoie (ids, centres) : la liste des numéros de groupe et la matrice des centres,
    dans le même ordre.
    """
    ids = sorted(int(g) for g in set(groupes.tolist()) if g != -1)
    if not ids:
        return [], np.zeros((0, X.shape[1] if X.ndim == 2 else 0), dtype=np.float32)
    centres = np.array([X[groupes == k].mean(axis=0) for k in ids])
    return ids, normalize(centres)


def cohesion(X, membres):
    """Ressemblance moyenne (cosinus) entre les tickets d'un groupe et son centre.

    Proche de 1 : les tickets disent presque la même chose. Sous 0,75 environ : le groupe
    mélange des sujets différents.
    """
    centre = X[membres].mean(axis=0)
    centre = centre / max(float(np.linalg.norm(centre)), 1e-12)
    return float((X[membres] @ centre).mean())


def part_du_texte_dominant(textes):
    """Part des tickets du groupe qui portent exactement le même texte (entre 0 et 1).

    1.0 signifie : tous les tickets sont la copie d'un seul texte.
    """
    if not textes:
        return 0.0
    compte = Counter(normaliser_pour_comparer(t) for t in textes)
    return compte.most_common(1)[0][1] / len(textes)


def est_un_texte_recopie(textes):
    """Vrai si le groupe est formé (presque) d'un seul texte recopié."""
    return part_du_texte_dominant(textes) >= PART_TEXTE_RECOPIE
