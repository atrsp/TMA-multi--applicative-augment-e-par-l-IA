"""Lire les tickets par l'API REST de Jira Cloud — EN LECTURE SEULE.

Règle non négociable : ce fichier ne contient que des requêtes GET. Il n'existe aucune
fonction pour créer, modifier ou commenter un ticket, et il ne faut pas en ajouter.

Identifiants (dans le fichier .env, jamais dans le code) :
    JIRA_URL    https://votre-espace.atlassian.net
    JIRA_EMAIL  l'adresse du compte
    JIRA_TOKEN  un jeton d'API (https://id.atlassian.com/manage-profile/security/api-tokens)
"""
import requests
from requests.auth import HTTPBasicAuth

from .format import depuis_jira

# Seuls les champs utiles à l'analyse sont demandés (moins de données, réponses plus rapides).
CHAMPS = "summary,description,issuetype,priority,status,components,project,created,timespent,comment"
TAILLE_PAGE = 100
DELAI_MAX = 30          # secondes d'attente maximale par requête


class ErreurJira(Exception):
    """Erreur lisible renvoyée quand Jira ne répond pas comme prévu."""


def requete_jql(config):
    """La requête JQL utilisée : celle du .env si elle existe, sinon tout le projet."""
    return config.get("jira_jql") or f'project = "{config["jira_projet"]}" ORDER BY created DESC'


def lire_page(config, jeton_page=None):
    """Demande une page de tickets à Jira (requête GET) et renvoie la réponse décodée."""
    parametres = {"jql": requete_jql(config), "maxResults": TAILLE_PAGE, "fields": CHAMPS}
    if jeton_page:
        parametres["nextPageToken"] = jeton_page
    try:
        reponse = requests.get(
            f'{config["jira_url"].rstrip("/")}/rest/api/3/search/jql',
            auth=HTTPBasicAuth(config["jira_email"], config["jira_token"]),
            headers={"Accept": "application/json"},
            params=parametres,
            timeout=DELAI_MAX,
        )
    except requests.RequestException as erreur:
        raise ErreurJira(f"Jira est injoignable : {erreur.__class__.__name__}") from erreur
    if not reponse.ok:
        # On ne recopie pas le corps entier de la réponse : seulement le code et un extrait.
        raise ErreurJira(f"Jira a répondu {reponse.status_code} : {reponse.text[:200]}")
    return reponse.json()


def lire_tickets(config):
    """Lit tous les tickets du projet, page par page, et les convertit au format interne."""
    manquants = [nom for nom in ("jira_url", "jira_email", "jira_token") if not config.get(nom)]
    if manquants:
        raise ErreurJira("Configuration Jira incomplète dans .env : "
                         + ", ".join(m.upper() for m in manquants))

    tickets, jeton_page = [], None
    while len(tickets) < config["jira_max_tickets"]:
        page = lire_page(config, jeton_page)
        tickets.extend(depuis_jira(issue) for issue in page.get("issues", []))
        jeton_page = page.get("nextPageToken")
        if not jeton_page or page.get("isLast"):
            break
    return tickets[:config["jira_max_tickets"]]
