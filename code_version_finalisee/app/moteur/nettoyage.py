"""Nettoyer le texte des tickets avant l'analyse et l'affichage.

Deux défauts du moteur d'origine sont corrigés ici :
  1. les entités HTML (« l&#39;écran ») sont décodées (« l'écran ») ;
  2. les identifiants pseudonymisés (CLI-1234, DOS-12345) sont retirés : ils changent à
     chaque ticket, n'apportent aucun sens, et polluaient les mots-clés (« dos », « cli »).

Attention : on ne retire QUE les préfixes listés. Un code d'erreur comme ORA-01555 est
une information utile, il doit rester.
"""
import html
import re


# Petits mots (prépositions, articles) qui n'ont plus de sens s'ils terminent un texte.
MOT_ORPHELIN_FINAL = re.compile(r"(?:\s+(?:pour|de|du|des|par|sur|au|aux|à|le|la|les|:))+$", re.IGNORECASE)


def construire_motif(prefixes):
    """Fabrique l'expression régulière qui repère les identifiants à retirer.

    prefixes : liste de préfixes, par exemple ["CLI", "DOS"].
    Renvoie None si la liste est vide (rien à retirer).
    """
    prefixes = [p.strip() for p in prefixes if p.strip()]
    if not prefixes:
        return None
    # \b = frontière de mot ; (?:CLI|DOS) = l'un des préfixes ; -\d+ = un tiret puis des chiffres
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in prefixes) + r")-\d+\b", re.IGNORECASE)


def decoder(texte):
    """Décode les entités HTML. Deux passes, car on rencontre parfois « &amp;#39; »."""
    return html.unescape(html.unescape(texte or ""))


def nettoyer(texte, motif=None):
    """Renvoie le texte prêt pour l'analyse : décodé, sans identifiants, sans espaces en trop."""
    texte = decoder(texte)
    retire = False
    if motif is not None:
        texte, nb = motif.subn("", texte)
        retire = nb > 0
    texte = re.sub(r"\s+", " ", texte)              # plusieurs espaces / retours à la ligne -> un espace
    texte = re.sub(r"\s+([,.])", r"\1", texte)      # « dossier , » -> « dossier, »
    texte = texte.strip()
    if retire:
        # « Connexion impossible pour CLI-1234 » devient « Connexion impossible pour » :
        # on retire le petit mot resté seul en fin de texte.
        texte = MOT_ORPHELIN_FINAL.sub("", texte)
    return texte


def normaliser_pour_comparer(texte):
    """Version simplifiée d'un texte, pour savoir si deux tickets sont des copies l'un de l'autre.

    On ignore la casse et les chiffres : « 166 secondes » et « 222 secondes » comptent
    comme le même texte recopié.
    """
    texte = re.sub(r"\d+", "0", texte.lower())
    return re.sub(r"\s+", " ", texte).strip()
