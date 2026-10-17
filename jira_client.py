import requests
from requests.auth import HTTPBasicAuth
from ticket import Ticket

class JiraError(Exception):
    pass

class JiraClient:
    def __init__(self, url, email, token, project_key = "TMA"):
        self.url = url
        self.project_key = project_key

        self.auth = HTTPBasicAuth(email,token)
        self.headers = {"Accept": "application/json"}


    def _chek(self, response):
        if not response.ok:
            raise JiraError(f"Jira a repondu {response.status_code} : {response.text}")
        return response.json()


    
    def get_tickets(self, max_results=20):
        response = requests.get(
            f"{self.url}/rest/api/3/search/jql",
            auth = self.auth,
            headers = self.headers,
            params = {
                "jql": f"project: {self.project_key}",
                "maxResult": max_results,
                "fields": "summary, description"
            },
        )
        data = self._check(response)

        tickets = []
        for issue in data["issues"]:
            ticket = Ticket(
                key=issue["key"],
                description=adf_to_text(issue["fields"].get("description")),
            )
            tickets.append(ticket)
        return tickets


    def create_ticket(self, summary, description, issue_type="Bug"):
        data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
                "issuetype": {"name": issue_type},
            }
        }
        response = requests.post(
            f"{self.url}/rest/api/3/issue",
            auth=self.auth,
            # Content-Type n'est utile qu'ici (on envoie du JSON) :
            # on l'ajoute aux headers communs seulement pour cet appel.
            headers={**self.headers, "Content-Type": "application/json"},
            json=data,
        )
        return self._check(response)


def adf_to_text(node):
    """Jira renvoie la description dans un format JSON imbriqué (ADF),
    pas en texte. Cette fonction parcourt ce JSON et récupère tout le texte."""
    if node is None:
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    morceaux = [adf_to_text(enfant) for enfant in node.get("content", [])]
    separateur = "\n" if node.get("type") == "doc" else ""
    return separateur.join(morceaux)