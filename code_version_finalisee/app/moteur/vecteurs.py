"""Transformer chaque texte en vecteur de nombres (embedding SBERT), avec cache sur disque.

Calculer un embedding est l'étape la plus lente. On ne la fait donc qu'UNE fois par texte :
  - chaque texte reçoit une empreinte (un résumé SHA-1 de son contenu) ;
  - le cache associe empreinte -> vecteur, dans un fichier .npz ;
  - à chaque analyse, seuls les textes dont l'empreinte est inconnue sont calculés.
Conséquence : si les tickets ne changent pas, rien n'est recalculé ; si 10 tickets arrivent,
seuls ces 10 sont calculés. Deux tickets au texte identique partagent le même vecteur.
"""
import hashlib
from pathlib import Path

import numpy as np

MODELE_PAR_DEFAUT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Le modèle est gros (~470 Mo en mémoire) : on le charge une seule fois et on le garde ici.
_modeles_charges = {}


def charger_modele(nom=MODELE_PAR_DEFAUT):
    """Charge le modèle SBERT (téléchargé au premier lancement, puis lu sur le disque)."""
    if nom not in _modeles_charges:
        # Import ici et pas en haut du fichier : PyTorch est long à charger, on ne le
        # paie que si l'on a vraiment un texte à vectoriser.
        from sentence_transformers import SentenceTransformer
        _modeles_charges[nom] = SentenceTransformer(nom)
    return _modeles_charges[nom]


def empreinte(texte):
    """Identifiant court et stable d'un texte (le même texte donne toujours la même empreinte)."""
    return hashlib.sha1(texte.encode("utf-8")).hexdigest()


def encoder(textes, nom_modele=MODELE_PAR_DEFAUT):
    """Calcule réellement les vecteurs (sans cache). Chaque vecteur est ramené à la norme 1,
    ce qui permet de calculer un cosinus par simple produit scalaire."""
    modele = charger_modele(nom_modele)
    return np.asarray(modele.encode(list(textes), batch_size=64, show_progress_bar=False,
                                    normalize_embeddings=True), dtype=np.float32)


def _fichier_cache(dossier_cache, nom_modele):
    """Un fichier de cache par modèle : changer de modèle ne mélange pas les vecteurs."""
    nom = nom_modele.replace("/", "__")
    return Path(dossier_cache) / f"embeddings__{nom}.npz"


def lire_cache(fichier):
    """Renvoie le dictionnaire empreinte -> vecteur enregistré sur le disque (vide si absent)."""
    if not fichier.exists():
        return {}
    contenu = np.load(fichier, allow_pickle=False)
    return dict(zip(contenu["empreintes"].tolist(), contenu["vecteurs"]))


def ecrire_cache(fichier, cache):
    """Enregistre le dictionnaire empreinte -> vecteur sur le disque."""
    fichier.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(fichier, empreintes=np.array(list(cache.keys())),
                        vecteurs=np.array(list(cache.values()), dtype=np.float32))


def vectoriser(textes, dossier_cache, nom_modele=MODELE_PAR_DEFAUT):
    """Renvoie (X, nb_calcules).

    X           : matrice avec une ligne par texte, dans le même ordre que `textes`
    nb_calcules : nombre de textes qu'il a fallu réellement calculer (0 = tout venait du cache)
    """
    fichier = _fichier_cache(dossier_cache, nom_modele)
    cache = lire_cache(fichier)
    empreintes = [empreinte(t) for t in textes]

    # Textes absents du cache, sans doublon (dict.fromkeys garde l'ordre et retire les copies).
    manquants = list(dict.fromkeys(t for t, e in zip(textes, empreintes) if e not in cache))
    if manquants:
        for texte, vecteur in zip(manquants, encoder(manquants, nom_modele)):
            cache[empreinte(texte)] = vecteur
        ecrire_cache(fichier, cache)

    if not textes:
        return np.zeros((0, 384), dtype=np.float32), 0
    return np.array([cache[e] for e in empreintes], dtype=np.float32), len(manquants)
