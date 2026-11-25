"""Décrire chaque groupe SANS LLM : mots-clés, titres représentatifs, nom et description.

Le nom et la description produits ici servent toujours :
  - seuls, quand aucun LLM n'est configuré ;
  - comme matière première (et comme garde-fou) quand le LLM rédige un nom plus soigné.
Tout vient des tickets eux-mêmes : rien n'est inventé.
"""
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

NB_MOTS = 6          # mots-clés gardés par groupe
NB_EXEMPLES = 6      # titres représentatifs gardés par groupe

# Mots trop courants pour caractériser un groupe (ceux de 1 ou 2 lettres sont déjà ignorés).
MOTS_VIDES = ["les", "des", "une", "pour", "dans", "sur", "avec", "est", "pas", "par", "qui",
              "que", "aux", "ses", "son", "sont", "été", "depuis", "plus", "nous", "vous", "leur",
              "cette", "elle", "ont", "lors", "mais", "fait", "très", "the", "and", "for",
              "merci", "bonjour", "suite", "afin", "être", "avoir", "sans", "sous", "entre"]


def mots_cles_ctfidf(textes, groupes):
    """c-TF-IDF (la méthode de BERTopic) : un TF-IDF calculé sur les GROUPES.

    On colle tous les textes d'un groupe en un seul grand document. Un mot est
    caractéristique s'il est fréquent DANS ce groupe et rare dans les autres.
    Renvoie un dictionnaire {numéro de groupe: [mots-clés]}.
    """
    ids = sorted(int(g) for g in set(groupes.tolist()) if g != -1)
    if not ids:
        return {}
    documents = [" ".join(t for t, g in zip(textes, groupes) if g == k) for k in ids]

    compteur = CountVectorizer(ngram_range=(1, 2), stop_words=MOTS_VIDES, lowercase=True,
                               token_pattern=r"(?u)\b[^\W\d_]{3,}\b")  # mots d'au moins 3 lettres
    try:
        C = compteur.fit_transform(documents).toarray().astype(float)   # lignes = groupes
    except ValueError:                      # vocabulaire vide (textes sans aucun mot utile)
        return {k: [] for k in ids}

    tf = C / np.maximum(C.sum(axis=1, keepdims=True), 1)   # fréquence du mot DANS le groupe
    moyenne = C.sum() / len(ids)                           # nombre moyen de mots par groupe
    idf = np.log(1 + moyenne / C.sum(axis=0))              # rareté du mot entre les groupes
    poids = tf * idf

    vocabulaire = compteur.get_feature_names_out()
    return {k: [str(vocabulaire[j]) for j in poids[i].argsort()[::-1][:NB_MOTS] if poids[i][j] > 0]
            for i, k in enumerate(ids)}


def indices_representatifs(X, membres):
    """Les tickets du groupe, du plus central (le plus « typique ») au plus excentré.

    membres : positions des tickets du groupe dans X.
    """
    centre = X[membres].mean(axis=0)
    return membres[np.argsort(-(X[membres] @ centre))]


def titres_representatifs(titres, ordre, nb=NB_EXEMPLES):
    """Les `nb` premiers titres distincts, en suivant l'ordre « du plus typique au moins typique »."""
    choisis = []
    for i in ordre:
        if titres[i] and titres[i] not in choisis:
            choisis.append(titres[i])
        if len(choisis) == nb:
            break
    return choisis


def nom_sans_llm(exemples, mots_cles):
    """Nom du groupe quand aucun LLM n'est disponible : le titre le plus typique.

    C'est un vrai titre de ticket, donc précis et fidèle. À défaut de titre, les mots-clés.
    """
    if exemples:
        return exemples[0]
    return ", ".join(mots_cles[:3]) or "Groupe sans titre"


def description_sans_llm(application, type_ticket, exemples, mots_cles, solution):
    """Description détaillée construite par assemblage de faits tirés des tickets.

    Elle permet à l'opérateur de comprendre le groupe quand le nom seul ne suffit pas.
    """
    phrases = [f"Tickets de type « {type_ticket} » sur l'application « {application} »."]
    if len(exemples) > 1:
        autres = " ; ".join(f"« {t} »" for t in exemples[1:4])
        phrases.append(f"Autres formulations rencontrées : {autres}.")
    if mots_cles:
        phrases.append(f"Mots caractéristiques : {', '.join(mots_cles)}.")
    if solution:
        phrases.append(f"Résolution la plus souvent notée : {solution}")
    return " ".join(phrases)
