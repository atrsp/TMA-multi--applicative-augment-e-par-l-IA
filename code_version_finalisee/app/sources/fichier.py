"""Lire des tickets depuis un fichier : le jeu de démonstration, ou un fichier fourni.

Deux formats sont acceptés :
  - JSON au format de l'API Jira : {"issues": [...]} (ou directement une liste de tickets) ;
  - CSV avec une ligne d'en-tête. Les noms de colonnes sont reconnus souplement
    (« identifiant », « id » ou « key » pour la clé, etc. : voir ALIAS).
"""
import csv
import json
import re
import unicodedata
from pathlib import Path

from .format import depuis_jira, ticket

# Pour chaque champ interne, les noms de colonnes CSV acceptés (déjà simplifiés :
# minuscules, sans accent, mots séparés par « _ »).
ALIAS = {
    "cle": ("cle", "key", "id", "identifiant", "ticket"),
    "titre": ("titre", "summary", "resume", "objet", "title"),
    "description": ("description", "detail", "details"),
    "application": ("application", "app", "composant", "component", "components"),
    "type_": ("type", "issuetype", "type_ticket", "ticket_type", "categorie", "categorie_technique"),
    "priorite": ("priorite", "priority", "urgence"),
    "statut": ("statut", "status", "etat"),
    "cree": ("cree", "created", "date_creation", "date_ouverture", "date_d_ouverture", "date"),
    "heures": ("heures", "temps_passe_h", "temps_passe", "charge_h", "time_spent_hours"),
    "secondes": ("timespent",),                 # comme Jira : un temps en secondes
    "solution": ("solution", "resolution", "commentaire", "commentaires", "comments"),
}


def simplifier_entete(nom):
    """« Date d'ouverture » -> « date_d_ouverture » : pour comparer les noms de colonnes."""
    sans_accent = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sans_accent.lower()).strip("_")


def trouver(ligne, champ):
    """Valeur du champ interne `champ` dans une ligne CSV (première colonne reconnue)."""
    for nom in ALIAS[champ]:
        if ligne.get(nom) not in (None, ""):
            return ligne[nom]
    return ""


def depuis_ligne_csv(ligne, numero):
    """Convertit une ligne CSV (dictionnaire colonne -> valeur) vers le format interne."""
    ligne = {simplifier_entete(k): v for k, v in ligne.items() if k}
    heures = trouver(ligne, "heures")
    if not heures and trouver(ligne, "secondes"):
        heures = float(trouver(ligne, "secondes")) / 3600
    description = trouver(ligne, "description")
    return ticket(
        cle=trouver(ligne, "cle") or f"LIGNE-{numero}",
        # Sans colonne de titre, on prend le début de la description.
        titre=trouver(ligne, "titre") or description[:80],
        description=description,
        application=trouver(ligne, "application"), type_=trouver(ligne, "type_"),
        priorite=trouver(ligne, "priorite"), statut=trouver(ligne, "statut"),
        cree=trouver(ligne, "cree"), heures=heures, solution=trouver(ligne, "solution"),
    )


def lire_tickets(chemin):
    """Lit un fichier JSON ou CSV et renvoie la liste des tickets au format interne."""
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier de tickets introuvable : {chemin}")

    if chemin.suffix.lower() == ".csv":
        # utf-8-sig : tolère le marqueur invisible qu'Excel ajoute en début de fichier.
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            echantillon = f.read(2048)
            f.seek(0)
            separateur = ";" if echantillon.count(";") > echantillon.count(",") else ","
            return [depuis_ligne_csv(ligne, n)
                    for n, ligne in enumerate(csv.DictReader(f, delimiter=separateur), start=1)]

    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    issues = contenu.get("issues", []) if isinstance(contenu, dict) else contenu
    return [depuis_jira(issue) for issue in issues]
