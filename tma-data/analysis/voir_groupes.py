"""
=====================================================================================
OUVRIR LA BOÎTE : afficher le contenu de chaque groupe trouvé par HDBSCAN
=====================================================================================
ARI et NMI résument tout en un chiffre. Ce script montre CE QU'IL Y A dans chaque
groupe, pour comprendre pourquoi un score est bon ou mauvais.

Usage : python3 voir_groupes.py tfidf 10     (méthode, puis min_cluster_size)
=====================================================================================
"""
import sys
from collections import Counter     # compter des éléments, ex. combien de tickets par famille

from sklearn.cluster import HDBSCAN

# On RÉUTILISE les fonctions du script principal : même chargement, même vectorisation.
from baseline_clustering import charger, vectoriser

# Lire les deux arguments du terminal, avec des valeurs par défaut.
methode = sys.argv[1] if len(sys.argv) > 1 else "tfidf"
taille = int(sys.argv[2]) if len(sys.argv) > 2 else 10     # int() : texte "10" -> nombre 10

cles, textes, vrai = charger()                              # tickets + vraies familles
X = vectoriser(textes, methode)                             # vecteurs
groupes = HDBSCAN(min_cluster_size=taille, copy=True).fit_predict(X)   # un numéro de groupe par ticket

# Parcourir chaque numéro de groupe, dans l'ordre (-1 = bruit en premier).
for g in sorted(set(groupes)):
    # Les positions des tickets qui appartiennent au groupe g.
    membres = [i for i in range(len(textes)) if groupes[i] == g]

    # Compter les vraies familles dans ce groupe, ex. Counter({"F-SSO": 48, "F-MDP": 2}).
    familles = Counter(vrai[i] for i in membres)
    # most_common(1) renvoie la famille la plus fréquente et son nombre, ex. ("F-SSO", 48).
    famille, nb = familles.most_common(1)[0]

    nom = "BRUIT" if g == -1 else f"Groupe {g}"
    # nb / len(membres) = la PURETÉ du groupe : part de tickets de la famille majoritaire.
    print(f"\n{nom} : {len(membres)} tickets, famille majoritaire {famille} ({nb / len(membres):.0%})")

    # Afficher 3 titres d'exemple : texte complet coupé au premier point = le titre.
    for i in membres[:3]:
        print("   -", textes[i].split(".")[0])
