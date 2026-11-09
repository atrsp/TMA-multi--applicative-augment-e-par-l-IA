"""Demande à Ollama plusieurs façons réalistes d'écrire chaque famille de tickets.
Sortie : data/variantes_ollama.json (à relire à la main, puis à versionner sur Git)."""
import json

from generer_tickets import FAMILLES, SORTIE, remplir
from ollama_client import MODELE, demander_json

NB_VARIANTES = 15
STYLES = ["utilisateur pressé, très court, sans majuscules",
          "conseiller bancaire précis et poli",
          "technicien qui utilise du jargon et des abréviations",
          "utilisateur stressé qui fait des fautes d'orthographe",
          "message vague qui manque d'informations"]

PROMPT = """Tu génères des tickets Jira fictifs pour une équipe de maintenance applicative bancaire.
Application concernée : {app}
Type de ticket : {type}
Problème réel (à ne pas recopier mot pour mot) : {titre}. {detail}
Style d'écriture : {style}
Contraintes : en français, aucun nom de personne réel, titre de 12 mots maximum,
description de 1 à 3 phrases.
Réponds uniquement en JSON : {{"summary": "...", "description": "..."}}"""


def valide(v):
    """Garde-fou : on rejette les réponses incomplètes ou trop longues."""
    return (isinstance(v, dict)
            and isinstance(v.get("summary"), str) and 3 <= len(v["summary"]) <= 120
            and isinstance(v.get("description"), str) and 10 <= len(v["description"]) <= 600)


def main():
    fichier = SORTIE / "variantes_ollama.json"
    variantes = json.loads(fichier.read_text(encoding="utf-8")) if fichier.exists() else {}
    for famille in FAMILLES:
        liste = variantes.setdefault(famille["id"], [])
        essai = 0
        while len(liste) < NB_VARIANTES and essai < NB_VARIANTES * 2:
            essai += 1
            prompt = PROMPT.format(app=famille["app"], type=famille["type"],
                                   titre=famille["titres"][0], detail=remplir(famille["detail"]),
                                   style=STYLES[essai % len(STYLES)])
            try:
                v = demander_json(prompt, seed=essai)
            except Exception as erreur:                   # Ollama éteint, JSON cassé...
                print(f"  {famille['id']} essai {essai} : échec ({erreur})")
                continue
            if valide(v) and v["summary"] not in [x["summary"] for x in liste]:
                liste.append({"summary": v["summary"].strip(), "description": v["description"].strip()})
        print(f"{famille['id']} : {len(liste)} variantes")
        fichier.write_text(json.dumps(variantes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Modèle utilisé : {MODELE}. Fichier : {fichier}")


if __name__ == "__main__":
    main()
