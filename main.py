import csv
import os

from jira_client import JiraClient


def lire_variable(nom):
    """Lit une variable d'environnement et s'arrête proprement si elle manque."""
    valeur = os.environ.get(nom)
    if valeur is None:
        raise SystemExit(f"La variable d'environnement {nom} n'est pas définie.")
    return valeur


def exporter_csv(tickets, chemin):
    """Écrit une liste de Ticket dans un fichier CSV."""
    with open(chemin, "w", newline="", encoding="utf-8-sig") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=["key", "description"])
        writer.writeheader()
        for ticket in tickets:
            writer.writerow(ticket.to_dict())


if __name__ == "__main__":
    client = JiraClient(
        url="https://malakmilib.atlassian.net",
        email=lire_variable("JIRA_EMAIL"),
        token=lire_variable("JIRA_TOKEN"),
    )

    tickets = client.get_tickets()
    exporter_csv(tickets, "tickets.csv")

    print(f"{len(tickets)} tickets enregistrés dans tickets.csv")
    for ticket in tickets:
        print(ticket.to_dict())