"""Génère un jeu de tickets TMA fictifs au format de l'API REST Jira.

Sorties :
  data/tickets.json         -> les tickets (ce que verront les algorithmes)
  data/verite_terrain.csv   -> la famille réelle de chaque ticket (pour évaluer F3/F4)
"""
import csv
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # même résultat à chaque exécution (C5 : reproductible)

NB_SEMAINES = 12
TICKETS_PAR_SEMAINE = 120
DEBUT = datetime(2026, 6, 1, 8, 0)
SORTIE = Path(__file__).resolve().parent.parent / "data"

# Familles de récurrence : chaque famille = un problème qui revient
FAMILLES = [
    {"id": "F-SSO", "app": "Portail Client", "type": "Incident", "poids": 14,
     "titres": ["Impossible de se connecter au portail", "Erreur SSO à la connexion",
                "Connexion portail client KO", "Boucle de redirection à la connexion"],
     "detail": "Le client {client} n'arrive plus à se connecter depuis {heure}. Message : 'Session expirée'.",
     "temps_h": (1, 4), "solution": "Purge du cache SSO et redémarrage du service d'authentification."},
    {"id": "F-BATCH", "app": "Batch Nocturne", "type": "Incident", "poids": 10,
     "titres": ["Batch de nuit en échec", "Traitement nocturne planté",
                "Job BATCH_CALC_INTERETS KO", "Le batch de 2h n'a pas tourné"],
     "detail": "Le job s'est arrêté à {heure} avec l'erreur ORA-01555 (snapshot too old).",
     "temps_h": (2, 8), "solution": "Relance manuelle du job après augmentation de l'undo tablespace."},
    {"id": "F-SEPA", "app": "Paiements SEPA", "type": "Incident", "poids": 9,
     "titres": ["Virement SEPA rejeté", "Rejet de virements en masse",
                "Paiements bloqués côté SEPA", "Fichier SEPA refusé par la banque"],
     "detail": "{nb} virements rejetés pour le client {client}, code retour AC04.",
     "temps_h": (2, 6), "solution": "Correction du format IBAN dans le fichier et renvoi."},
    {"id": "F-PDF", "app": "Espace Conseiller", "type": "Incident", "poids": 8,
     "titres": ["Export PDF vide", "Le relevé PDF ne se génère pas",
                "Génération de document en erreur", "PDF tronqué pour le contrat"],
     "detail": "Le conseiller obtient un PDF vide pour le dossier {dossier}.",
     "temps_h": (1, 3), "solution": "Redémarrage du service de génération documentaire."},
    {"id": "F-LENT", "app": "Back-office Crédit", "type": "Incident", "poids": 7,
     "titres": ["Lenteurs sur l'écran de simulation", "Back-office très lent",
                "Temps de réponse dégradé", "Simulation de crédit qui rame"],
     "detail": "Temps de réponse supérieur à {nb} secondes sur l'écran de simulation.",
     "temps_h": (2, 10), "solution": "Reconstruction des index de la table SIMULATION."},
    {"id": "F-DROITS", "app": "Espace Conseiller", "type": "Demande de support", "poids": 9,
     "titres": ["Demande d'ouverture de droits", "Accès manquant pour un nouveau conseiller",
                "Ajout de profil utilisateur", "Droits insuffisants sur l'espace conseiller"],
     "detail": "Merci d'ouvrir les droits {profil} pour l'utilisateur {client}.",
     "temps_h": (0.5, 1), "solution": "Ajout du profil dans l'annuaire."},
    {"id": "F-MDP", "app": "Portail Client", "type": "Demande de support", "poids": 8,
     "titres": ["Réinitialisation de mot de passe", "Mot de passe bloqué",
                "Compte verrouillé après 3 essais", "Reset mot de passe client"],
     "detail": "Le client {client} a bloqué son compte, demande de réinitialisation.",
     "temps_h": (0.25, 0.5), "solution": "Déverrouillage du compte et envoi d'un lien de réinitialisation."},
]

TICKETS_UNIQUES = [  # bruit : tickets qui n'appartiennent à aucune famille
    ("Back-office Crédit", "Demande d'évolution", "Ajouter une colonne 'taux' dans l'export Excel"),
    ("Paiements SEPA", "Demande de support", "Question sur le calendrier des prélèvements"),
    ("Portail Client", "Demande d'évolution", "Modifier le libellé du bouton Valider"),
    ("Batch Nocturne", "Demande de support", "Besoin d'un extract ponctuel des contrats clos"),
    ("Espace Conseiller", "Incident", "Faute d'orthographe sur la page d'accueil"),
]

PRIORITES = ["Highest", "High", "Medium", "Low"]
POIDS_PRIORITES = {"Incident": [10, 30, 45, 15], "Demande de support": [2, 10, 50, 38],
                   "Demande d'évolution": [0, 10, 50, 40]}


def remplir(texte):
    return texte.format(
        client=f"CLI-{random.randint(1000, 9999)}",          # identifiant déjà pseudonymisé
        heure=f"{random.randint(0, 23):02d}h{random.choice(['00', '15', '30', '45'])}",
        nb=random.randint(3, 250), dossier=f"DOS-{random.randint(10000, 99999)}",
        profil=random.choice(["CONSULTATION", "VALIDATION", "ADMIN_AGENCE"]))


def charger_variantes():
    """Lit les textes écrits par Ollama s'ils existent, sinon renvoie un dictionnaire vide."""
    fichier = SORTIE / "variantes_ollama.json"
    return json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}


VARIANTES = charger_variantes()


def rafraichir(texte):
    """Remplace les identifiants recopiés par Ollama par de nouveaux, pour éviter les doublons exacts."""
    texte = re.sub(r"CLI-\d+", lambda m: f"CLI-{random.randint(1000, 9999)}", texte)
    return re.sub(r"DOS-\d+", lambda m: f"DOS-{random.randint(10000, 99999)}", texte)


def creer_ticket(numero, date, famille=None):
    if famille and VARIANTES.get(famille["id"]):           # texte écrit par Ollama
        app, type_ = famille["app"], famille["type"]
        variante = random.choice(VARIANTES[famille["id"]])
        titre, description = variante["summary"], rafraichir(variante["description"])
        temps_h = random.uniform(*famille["temps_h"])
        commentaire = famille["solution"]
    elif famille:                                           # gabarit (si pas de variantes)
        app, type_, titre = famille["app"], famille["type"], random.choice(famille["titres"])
        description = remplir(famille["detail"])
        temps_h = random.uniform(*famille["temps_h"])
        commentaire = famille["solution"]
    else:
        app, type_, titre = random.choice(TICKETS_UNIQUES)
        description, temps_h, commentaire = titre + ".", random.uniform(0.5, 6), "Traité."
    resolu = date + timedelta(hours=random.uniform(1, 72))
    return {
        "key": f"TMA-{numero}",
        "fields": {
            "summary": titre,
            "description": description,
            "issuetype": {"name": type_},
            "priority": {"name": random.choices(PRIORITES, POIDS_PRIORITES[type_])[0]},
            "status": {"name": "Résolu"},
            "resolution": {"name": "Corrigé"},
            "components": [{"name": app}],
            "labels": [],
            "created": date.isoformat(timespec="seconds") + ".000+0200",
            "resolutiondate": resolu.isoformat(timespec="seconds") + ".000+0200",
            "timespent": int(temps_h * 3600),  # Jira stocke le temps passé en secondes
            "comment": {"comments": [{"body": commentaire}]},
        },
    }


def main():
    SORTIE.mkdir(exist_ok=True)
    poids = [f["poids"] for f in FAMILLES] + [15]  # poids des tickets uniques (environ 1 sur 5)
    tirages = []
    for semaine in range(NB_SEMAINES):
        for _ in range(TICKETS_PAR_SEMAINE):
            date = DEBUT + timedelta(weeks=semaine, minutes=random.randint(0, 7 * 24 * 60))
            choix = random.choices(FAMILLES + [None], poids)[0]
            if semaine == 8 and random.random() < 0.25:  # pic simulé en semaine 9
                choix = FAMILLES[1]
            tirages.append((date, choix))
    tirages.sort(key=lambda t: t[0])  # numéros TMA-1, TMA-2... dans l'ordre chronologique

    tickets, verite = [], []
    for numero, (date, choix) in enumerate(tirages, start=1):
        tickets.append(creer_ticket(numero, date, choix))
        verite.append((f"TMA-{numero}", choix["id"] if choix else "AUCUNE"))

    (SORTIE / "tickets.json").write_text(
        json.dumps({"total": len(tickets), "issues": tickets}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    with open(SORTIE / "verite_terrain.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("key", "famille")] + verite)
    print(f"{len(tickets)} tickets générés dans {SORTIE}")


if __name__ == "__main__":
    main()
