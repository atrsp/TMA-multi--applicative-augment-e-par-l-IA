"""
=====================================================================================
ÉTAPE 0 DU BLOC LOGIQUE MÉTIER : BANC D'ÉVALUATION ET BASELINES
=====================================================================================
But : regrouper automatiquement les 1 440 tickets, puis NOTER ce regroupement en le
comparant à la vérité terrain (la vraie famille de chaque ticket).

Le script suit 4 étapes, une fonction par étape :
    1. charger()     -> lire les tickets et leur vraie famille
    2. vectoriser()  -> transformer chaque texte en vecteur de nombres
                        (théorie : Notions 1, 2 et 3 du guide)
    3. regrouper     -> K-means et HDBSCAN, dans main()
                        (théorie : Notions 4 et 5)
    4. evaluer()     -> calculer ARI, NMI, nombre de groupes, bruit
                        (théorie : Notion 6)

Usage, depuis le dossier analysis, avec (.venv) activé :
    python3 baseline_clustering.py tfidf     # baseline lexicale (compte les mots)
    python3 baseline_clustering.py sbert     # baseline sémantique (embeddings)
=====================================================================================
"""

# -------------------------------------------------------------------------------
# IMPORTS : on charge les outils dont on a besoin
# -------------------------------------------------------------------------------
import csv          # lire le fichier verite_terrain.csv
import json         # lire le fichier tickets.json
import sys          # lire l'argument tapé après le nom du script (tfidf ou sbert)
from pathlib import Path   # manipuler les chemins de fichiers proprement

import numpy as np         # calcul numérique (tableaux, moyennes)
import pandas as pd        # tableaux de résultats (affichage + export CSV)
from sklearn.cluster import HDBSCAN, KMeans                  # les 2 algorithmes de clustering
from sklearn.decomposition import TruncatedSVD               # la SVD tronquée (LSA)
from sklearn.feature_extraction.text import TfidfVectorizer  # le calcul TF-IDF
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score  # ARI et NMI
from sklearn.preprocessing import normalize                  # ramener chaque vecteur à une norme 1

# Chemin du dossier data :
#   __file__        = ce fichier (tma-data/analysis/baseline_clustering.py)
#   .resolve()      = son chemin complet sur le disque
#   .parent         = le dossier analysis
#   .parent.parent  = le dossier tma-data
#   / "data"        = on descend dans tma-data/data
DATA = Path(__file__).resolve().parent.parent / "data"


# ===============================================================================
# ÉTAPE 1 : CHARGER LES DONNÉES
# ===============================================================================
def charger():
    """Renvoie 3 listes alignées : les clés, les textes et la vraie famille de chaque ticket.
    'Alignées' veut dire : l'élément n°i de chaque liste concerne le MÊME ticket."""

    # Lire tickets.json (texte JSON) et le transformer en dictionnaire Python,
    # puis garder uniquement la liste des tickets (clé "issues").
    issues = json.loads((DATA / "tickets.json").read_text(encoding="utf-8"))["issues"]

    # Lire verite_terrain.csv ligne par ligne et construire un dictionnaire
    # clé du ticket -> famille, par exemple {"TMA-1": "F-SSO", "TMA-2": "F-BATCH", ...}.
    # La syntaxe {a: b for r in ...} s'appelle une "compréhension de dictionnaire".
    verite = {r["key"]: r["famille"]
              for r in csv.DictReader(open(DATA / "verite_terrain.csv", encoding="utf-8"))}

    # Liste des clés, dans l'ordre des tickets : ["TMA-1", "TMA-2", ...]
    cles = [t["key"] for t in issues]

    # Liste des textes : titre + ". " + description, pour chaque ticket.
    # f'...' est une f-string : les {...} sont remplacés par leur valeur.
    textes = [f'{t["fields"]["summary"]}. {t["fields"]["description"]}' for t in issues]

    # On renvoie la vraie famille DANS LE MÊME ORDRE que les textes (crucial pour l'évaluation).
    return cles, textes, [verite[c] for c in cles]


# ===============================================================================
# ÉTAPE 2 : VECTORISER (transformer chaque texte en vecteur de nombres)
# ===============================================================================
def vectoriser(textes, methode):
    """Renvoie une matrice X : une ligne par ticket, chaque ligne de norme 1."""

    if methode == "tfidf":
        # --- Méthode lexicale : on compte les mots (Notion 1) ---------------------------
        # TfidfVectorizer calcule tous les poids w(t,d). Réglages :
        #   ngram_range=(1, 2) : garder les mots seuls ET les paires de mots ("mot de", "de passe")
        #   min_df=2           : ignorer les termes présents dans un seul ticket (ex. CLI-4821)
        #   sublinear_tf=True  : utiliser 1 + log(tf) au lieu de tf (mot répété = effet atténué)
        # fit_transform : apprend le vocabulaire sur nos textes ET calcule la matrice.
        # Résultat : une matrice 1440 x (taille du vocabulaire), presque remplie de zéros.
        X = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit_transform(textes)

        # --- LSA : compresser cette matrice en 50 colonnes par SVD tronquée (Notion 2) --
        # random_state=0 rend le calcul reproductible (même résultat à chaque fois).
        # Résultat : une matrice 1440 x 50.
        X = TruncatedSVD(n_components=50, random_state=0).fit_transform(X)

    elif methode == "sbert":
        # --- Méthode sémantique : embeddings d'un encodeur pré-entraîné (Notion 3) -------
        # L'import est ici (et pas en haut) pour que le mode tfidf n'ait pas besoin de
        # sentence-transformers, ni de charger PyTorch.
        from sentence_transformers import SentenceTransformer
        # Charger le modèle (téléchargé une seule fois, puis gardé sur le disque).
        modele = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        # Encoder tous les textes, 64 à la fois. Résultat : une matrice 1440 x 384.
        X = modele.encode(textes, batch_size=64, show_progress_bar=True)

    else:
        # Si l'argument n'est ni tfidf ni sbert, on arrête le programme avec un message clair.
        raise ValueError("méthode inconnue : tfidf ou sbert")

    # Diviser chaque ligne par sa norme : chaque vecteur a alors une norme 1, et la
    # distance euclidienne devient une fonction du cosinus (Notion 3).
    return normalize(X)


# ===============================================================================
# ÉTAPE 4 : ÉVALUER (comparer les groupes trouvés à la vérité terrain)
# ===============================================================================
def evaluer(nom, predit, vrai):
    """Renvoie un dictionnaire = une ligne du tableau de résultats.
    nom    : le nom de la méthode à afficher, ex. "HDBSCAN (min=10)"
    predit : la liste des groupes trouvés, un numéro par ticket (-1 = bruit)
    vrai   : la liste des vraies familles, dans le même ordre"""
    return {
        "Méthode": nom,
        # ARI : accord sur les paires de tickets, corrigé du hasard (1 = parfait, 0 = hasard)
        "ARI": round(adjusted_rand_score(vrai, predit), 3),
        # NMI : combien le groupe renseigne sur la famille (1 = parfaitement, 0 = rien)
        "NMI": round(normalized_mutual_info_score(vrai, predit), 3),
        # set(predit) garde chaque numéro de groupe une fois ; on retire -1 (le bruit) ; on compte.
        "Groupes": len(set(predit) - {-1}),
        # (np.array(predit) == -1) donne True/False par ticket ; la moyenne = part de bruit.
        "Bruit (%)": round(100 * np.mean(np.array(predit) == -1)),
    }
    # IMPORTANT : "return" RENVOIE les résultats au code qui appelle la fonction.
    # Un simple "print" les afficherait, puis la fonction renverrait None (rien).


# ===============================================================================
# PROGRAMME PRINCIPAL : enchaîner les 4 étapes
# ===============================================================================
def main():
    # sys.argv = la liste des mots tapés dans le terminal :
    #   "python3 baseline_clustering.py sbert" -> sys.argv = ["baseline_clustering.py", "sbert"]
    # On prend le 2e mot s'il existe, sinon "tfidf" par défaut (cas du bouton ▶ de VS Code).
    methode = sys.argv[1] if len(sys.argv) > 1 else "tfidf"

    cles, textes, vrai = charger()               # ÉTAPE 1
    X = vectoriser(textes, methode)              # ÉTAPE 2

    # Nombre de vraies familles, sans compter "AUCUNE" (les tickets isolés).
    nb_familles = len(set(vrai) - {"AUCUNE"})
    print(f"{len(textes)} tickets, {nb_familles} familles réelles, représentation : {methode}\n")

    # ÉTAPE 3 (regrouper) + ÉTAPE 4 (évaluer) ------------------------------------------
    lignes = []   # la liste qui va recevoir une ligne de résultats par algorithme

    # Référence : K-means à qui on DONNE le bon nombre de groupes (7 familles + 1 pour
    # les tickets isolés). Irréaliste, volontairement : c'est un point de comparaison.
    #   n_init=10       : 10 départs différents, on garde le meilleur (Notion 4)
    #   fit_predict(X)  : calcule les groupes ET renvoie le numéro de groupe de chaque ticket
    lignes.append(evaluer("KMeans (k connu)",
                          KMeans(n_clusters=nb_familles + 1, n_init=10, random_state=0).fit_predict(X),
                          vrai))

    # Méthode réaliste : HDBSCAN trouve seul le nombre de groupes et isole le bruit (Notion 5).
    # On essaie 3 valeurs de min_cluster_size (taille minimale d'un groupe) : c'est
    # une petite analyse de sensibilité.
    for taille in (10, 30, 60):
        lignes.append(evaluer(f"HDBSCAN (min={taille})",
                              HDBSCAN(min_cluster_size=taille, copy=True).fit_predict(X),
                              vrai))

    # Transformer la liste de dictionnaires en tableau : chaque clé devient une colonne.
    tableau = pd.DataFrame(lignes)
    print(tableau.to_string(index=False))        # afficher le tableau dans le terminal

    # Enregistrer le tableau dans analysis/resultats_tfidf.csv (ou resultats_sbert.csv).
    fichier = Path(__file__).resolve().parent / f"resultats_{methode}.csv"
    tableau.to_csv(fichier, index=False)
    print(f"\nRésultats enregistrés dans {fichier.name}")


# Ce bloc ne s'exécute que si on LANCE ce fichier (python3 baseline_clustering.py).
# Si un autre fichier fait "from baseline_clustering import vectoriser", main() n'est
# PAS lancé : on récupère seulement les fonctions.
if __name__ == "__main__":
    main()
