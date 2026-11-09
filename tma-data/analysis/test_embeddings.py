"""
=====================================================================================
BAC À SABLE : voir comment le modèle du projet juge la ressemblance entre phrases
=====================================================================================
Utilise la fonction vectoriser de baseline_clustering.py : on teste donc EXACTEMENT
le même modèle que celui qu'on mesure. Modifie librement la liste PHRASES.

Usage : python3 test_embeddings.py
=====================================================================================
"""
from baseline_clustering import vectoriser

PHRASES = [
    "Batch de nuit en échec",              # 0  famille BATCH
    "Traitement nocturne KO",              # 1  BATCH, paraphrase sans mot commun
    "bacth de nuit plantée",               # 2  BATCH, avec des fautes
    "Batch de nuit trop lent",             # 3  mêmes mots, mais autre problème (lenteur)
    "Mot de passe bloqué",                 # 4  famille MDP
    "login failed on customer portal",     # 5  connexion, en anglais
    "Connexion au portail client KO",      # 6  famille SSO
]

# Une ligne de 384 nombres par phrase, chaque ligne de norme 1.
X = vectoriser(PHRASES, "sbert")
print("Forme de la matrice :", X.shape)    # (nombre de phrases, 384)

# Produit matriciel X . X^T : la case (i, j) est le produit scalaire des phrases i et j.
# Les vecteurs étant de norme 1, ce produit scalaire EST leur similarité cosinus.
similarites = X @ X.T

# Construire la liste des paires (score, phrase A, phrase B), chaque paire une seule fois
# (j commence à i + 1 pour ne pas compter A-B puis B-A, ni A-A).
paires = []
for i in range(len(PHRASES)):
    for j in range(i + 1, len(PHRASES)):
        paires.append((float(similarites[i][j]), PHRASES[i], PHRASES[j]))

# Trier de la plus proche à la plus éloignée (reverse=True = ordre décroissant).
print("\nPaires classées par similarité :")
for score, a, b in sorted(paires, reverse=True):
    print(f"{score:.2f}   {a}  <->  {b}")
