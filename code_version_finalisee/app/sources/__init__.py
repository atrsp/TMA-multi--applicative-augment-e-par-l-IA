"""Sources de tickets interchangeables : Jira (API REST), démonstration, ou fichier.

Chaque source renvoie la même chose : une liste de tickets au FORMAT INTERNE
(voir format.py). Le moteur d'analyse ne sait donc jamais d'où viennent les tickets.
"""
from datetime import datetime

from . import fichier, jira


def charger_tickets(config):
    """Lit les tickets de la source choisie dans le fichier .env (variable SOURCE).

    Renvoie (tickets, informations) où informations décrit la source pour l'affichage :
    {"source", "detail", "vivante", "fin_des_donnees"}.
    """
    source = config["source"]
    if source == "jira":
        tickets = jira.lire_tickets(config)
        # Jira est une source « vivante » : les données sont à jour à l'instant de la lecture.
        return tickets, {"source": "jira", "detail": f'{config["jira_url"]} · projet {config["jira_projet"]}',
                         "vivante": True, "fin_des_donnees": datetime.now()}

    chemin = config["demo_tickets"] if source == "demo" else config["fichier_tickets"]
    tickets = fichier.lire_tickets(chemin)
    dates = [t["cree"] for t in tickets if t["cree"]]
    return tickets, {"source": source, "detail": str(chemin), "vivante": False,
                     "fin_des_donnees": max(dates) if dates else None}
