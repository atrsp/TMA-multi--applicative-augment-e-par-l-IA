"""Le FORMAT INTERNE d'un ticket, commun à toutes les sources.

    cle          « TMA-42 »
    titre        résumé du ticket (entités HTML décodées)
    description  texte de la description
    application  composant / application concernée
    type         Incident, Demande de support...
    priorite, statut
    cree         date de création (datetime) ou None
    heures       temps passé en heures (0 si inconnu)
    solution     dernier commentaire ou champ « résolution » (peut être vide)

Les vraies données sont souvent incomplètes : chaque champ manquant reçoit une valeur
neutre plutôt que de faire planter l'analyse.
"""
from ..moteur.nettoyage import decoder
from ..moteur.semaines import lire_date

NON_RENSEIGNE = "Non renseigné"


def adf_en_texte(noeud):
    """Jira Cloud renvoie descriptions et commentaires dans un format JSON imbriqué (ADF).
    Cette fonction parcourt ce JSON et récupère tout le texte. Un texte simple est rendu tel quel."""
    if noeud is None:
        return ""
    if isinstance(noeud, str):
        return noeud
    if isinstance(noeud, list):
        return " ".join(adf_en_texte(n) for n in noeud)
    if noeud.get("type") == "text":
        return noeud.get("text", "")
    morceaux = [adf_en_texte(enfant) for enfant in noeud.get("content", [])]
    separateur = "\n" if noeud.get("type") in ("doc", "bulletList", "orderedList") else ""
    return separateur.join(m for m in morceaux if m)


def nom_de(champ):
    """Beaucoup de champs Jira sont des objets {"name": "..."}. Renvoie le nom, ou "" si absent."""
    if isinstance(champ, dict):
        return str(champ.get("name") or champ.get("value") or "")
    return str(champ or "")


def depuis_jira(issue):
    """Convertit un ticket au format de l'API Jira (clé « fields ») vers le format interne."""
    champs = issue.get("fields") or {}
    composants = champs.get("components") or []
    commentaires = (champs.get("comment") or {}).get("comments") or []
    # La résolution est en général expliquée dans le DERNIER commentaire.
    solution = adf_en_texte(commentaires[-1].get("body")) if commentaires else ""
    return ticket(
        cle=issue.get("key"),
        titre=champs.get("summary"),
        description=adf_en_texte(champs.get("description")),
        application=nom_de(composants[0]) if composants else nom_de(champs.get("project")),
        type_=nom_de(champs.get("issuetype")),
        priorite=nom_de(champs.get("priority")),
        statut=nom_de(champs.get("status")),
        cree=champs.get("created"),
        heures=(champs.get("timespent") or 0) / 3600,       # Jira stocke des secondes
        solution=solution,
    )


def ticket(cle, titre, description="", application="", type_="", priorite="", statut="",
           cree=None, heures=0.0, solution=""):
    """Fabrique un ticket au format interne en remplaçant les valeurs manquantes."""
    try:
        heures = max(float(str(heures).replace(",", ".") or 0), 0.0)
    except ValueError:
        heures = 0.0
    return {
        "cle": str(cle or "").strip(),
        "titre": decoder(str(titre or "")).strip() or "(sans titre)",
        "description": decoder(str(description or "")).strip(),
        "application": str(application or "").strip() or NON_RENSEIGNE,
        "type": str(type_ or "").strip() or NON_RENSEIGNE,
        "priorite": str(priorite or "").strip() or NON_RENSEIGNE,
        "statut": str(statut or "").strip() or NON_RENSEIGNE,
        "cree": lire_date(cree),
        "heures": heures,
        "solution": decoder(str(solution or "")).strip(),
    }
