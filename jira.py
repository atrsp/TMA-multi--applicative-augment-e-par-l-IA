import random
import requests
from requests.auth import HTTPBasicAuth


JIRA_URL = "https://malakmilib.atlassian.net"
EMAIL = "malakmilib14@gmail.com"
API_TOKEN = "ATATT3xFfGF0PRXFP-jBopxUtzXhShIB_SeeBILqqQU9xI7zXf_VYUmBmx0Ly5cIGA4YkSreWQiLosxkVWgybzawj8FvMsCqag-gvWZVfjrX6WJzXPY2snaOgNmqkGqbDhQqrS6yasm3iw9nEMfurC3SbKtTaRpgQPT7RMJaeiVTLuAD06y7PM0=4A835DAE"




def create_ticket(summary, description):
    url1 = f"{JIRA_URL}/rest/api/3/issue"


    data = {
        "fields": {
            "project": {
                "key": "TMA"
            },
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {
                "name": "Bug"
            }
        }
    }


    response = requests.post(
        url1,
        auth=HTTPBasicAuth(EMAIL, API_TOKEN),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        json=data
    )


    return response




def get_tickets():
    url2 = f"{JIRA_URL}/rest/api/3/search/jql"


    params = {
        "jql": "project = TMA",
        "maxResults": 20,
        "fields": "summary,description"
    }


    response = requests.get(
        url2,
        auth=HTTPBasicAuth(EMAIL, API_TOKEN),
        headers={
            "Accept": "application/json"
        },
        params=params
    )


    data = response.json()


    tickets = []


    for issue in data["issues"]:
        ticket = {
            "key": issue["key"],
            "summary": issue["fields"]["summary"],
            "description": issue["fields"]["description"]["content"][0]["content"][0]["text"]
        }


        tickets.append(ticket)


    return tickets




ticket_model = [
    {
        "summary": "Erreur de connexion",
        "user": "Un utilisateur",
        "action": "se connecter",
        "category": "Authentification",
        "severity": "Critique"
    },
    {
        "summary": "Erreur de paiement",
        "user": "Un client",
        "action": "effectuer un paiement",
        "category": "Paiement",
        "severity": "Majeure"
    },
    {
        "summary": "Page lente",
        "user": "Un utilisateur",
        "action": "charger la page",
        "category": "Performance",
        "severity": "Mineure"
    },
    {
        "summary": "Problème d'inscription",
        "user": "Un nouvel utilisateur",
        "action": "créer un compte",
        "category": "Inscription",
        "severity": "Majeure"
    },
    {
        "summary": "Erreur de profil",
        "user": "Un utilisateur",
        "action": "modifier son profil",
        "category": "Profil",
        "severity": "Mineure"
    }
]


tickets = get_tickets()


for ticket in tickets:
    print(ticket)




# for i in range(10):


#     ticket = random.choice(ticket_model)


#     description = (
#         f"{ticket['user']} rencontre un problème "
#         f"lorsqu'il essaie de {ticket['action']}.\n"
#         f"Catégorie : {ticket['category']}\n"
#         f"Sévérité : {ticket['severity']}"
#     )


#     response = create_ticket(
#         ticket["summary"],
#         description
#     )


#     print(response.status_code)
#     print(response.json())
