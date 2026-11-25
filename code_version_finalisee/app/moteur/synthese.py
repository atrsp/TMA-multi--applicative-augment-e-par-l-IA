"""Synthèse hebdomadaire : les faits d'une semaine, puis leur mise en forme Markdown.

Deux fonctions :
    construire()   calcule les faits (un dictionnaire) ;
    en_markdown()  transforme ces faits en texte Markdown exportable.
Aucun LLM : la synthèse est disponible même quand le copilote est débranché.
"""
from .recurrences import mediane
from .semaines import libelle

NB_PROBLEMES = 5        # problèmes cités dans la synthèse
NB_EXEMPLES = 5         # clés de tickets citées par élément


def construire(numero, meta, groupes, tickets, pics, plans, seuil_nouveaute):
    """Rassemble les faits de la semaine `numero`.

    tickets : les tickets de la période analysée, avec « semaine », « groupe », « score ».
    """
    semaine = next((s for s in meta["semaines"] if s["numero"] == numero), None)
    if semaine is None:
        return None
    par_id = {g["id"]: g for g in groupes}
    de_la_semaine = [t for t in tickets if t["semaine"] == numero]
    precedents = [t for t in tickets if t["semaine"] == numero - 1]
    position = numero - meta["premiere_semaine"]          # rang de la semaine dans les séries

    # Problèmes les plus présents cette semaine, comparés à leur niveau habituel.
    problemes = []
    for g in groupes:
        siens = [t for t in de_la_semaine if t["groupe"] == g["id"]]
        if not siens:
            continue
        problemes.append({
            "id": g["id"], "nom": g["nom"], "statut": g["statut"],
            "tickets": len(siens),
            "heures": round(sum(t["heures"] for t in siens), 1),
            "habituel": mediane(sorted(g["serie"][:position])) if position > 0 else None,
            "cles": [t["cle"] for t in siens[:NB_EXEMPLES]],
        })
    problemes.sort(key=lambda p: -p["tickets"])

    # Tickets qui ne ressemblent à aucun problème connu.
    nouveaux = [t for t in de_la_semaine if t["groupe"] == -1 and t["score"] < seuil_nouveaute]

    return {
        "semaine": {**semaine, "libelle": libelle(semaine["lundi"])},
        "nb_tickets": len(de_la_semaine),
        "heures": round(sum(t["heures"] for t in de_la_semaine), 1),
        "semaine_precedente": ({"nb_tickets": len(precedents),
                                "heures": round(sum(t["heures"] for t in precedents), 1)}
                               if numero > meta["premiere_semaine"] else None),
        "problemes": problemes[:NB_PROBLEMES],
        "pics": [{"probleme_id": p["groupe"], "nom": par_id[p["groupe"]]["nom"],
                  "observe": p["observe"], "attendu": p["attendu"], "p_valeur": p["p_valeur"],
                  "cles": [t["cle"] for t in de_la_semaine if t["groupe"] == p["groupe"]][:NB_EXEMPLES]}
                 for p in pics if p["semaine"] == numero and p["groupe"] in par_id],
        "nouveaux": {"nombre": len(nouveaux),
                     "exemples": [{"cle": t["cle"], "titre": t["titre"]} for t in nouveaux[:NB_EXEMPLES]]},
        "plans": {"a_valider": [p["titre"] for p in plans if p["statut"] == "propose"],
                  "valides": [p["titre"] for p in plans if p["statut"] == "valide"]},
    }


def nombre(valeur):
    """Écrit un nombre à la française : 15.5 -> « 15,5 », 40.0 -> « 40 »."""
    texte = f"{valeur:.1f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def en_markdown(s):
    """Met la synthèse en forme Markdown (titres #, listes -, gras **)."""
    sem = s["semaine"]
    lignes = [f"# Synthèse hebdomadaire du RUN — semaine S{sem['numero']} ({sem['libelle']})", ""]
    if not sem["complete"]:
        lignes += ["> Semaine en cours : les volumes sont partiels.", ""]

    lignes += ["## Volume", "",
               f"- **{s['nb_tickets']} tickets** créés, **{nombre(s['heures'])} h** consommées."]
    avant = s["semaine_precedente"]
    if avant and avant["nb_tickets"]:
        ecart = round(100 * (s["nb_tickets"] - avant["nb_tickets"]) / avant["nb_tickets"])
        lignes.append(f"- Semaine précédente : {avant['nb_tickets']} tickets, "
                      f"{nombre(avant['heures'])} h (évolution : {ecart:+d} %).")
    lignes.append("")

    lignes += ["## Alertes", ""]
    if s["pics"]:
        for p in s["pics"]:
            lignes.append(f"- **Pic anormal — {p['nom']}** : {p['observe']} tickets pour "
                          f"{nombre(p['attendu'])} attendus. Exemples : {', '.join(p['cles'])}.")
    else:
        lignes.append("- Aucun pic anormal détecté cette semaine.")
    lignes.append("")

    lignes += ["## Problèmes les plus présents", ""]
    if s["problemes"]:
        lignes += ["| Problème | Tickets | Niveau habituel | Heures | Exemples |", "|---|---:|---:|---:|---|"]
        for p in s["problemes"]:
            habituel = nombre(p["habituel"]) if p["habituel"] is not None else "–"
            marque = " *(à vérifier)*" if p["statut"] == "a_verifier" else ""
            lignes.append(f"| {p['nom']}{marque} | {p['tickets']} | {habituel} | "
                          f"{nombre(p['heures'])} | {', '.join(p['cles'][:3])} |")
    else:
        lignes.append("Aucun ticket rattaché à un problème connu cette semaine.")
    lignes.append("")

    lignes += ["## Nouveaux problèmes possibles", ""]
    if s["nouveaux"]["nombre"]:
        lignes.append(f"{s['nouveaux']['nombre']} ticket(s) ne ressemblent à aucun problème connu :")
        lignes += [f"- {e['cle']} — {e['titre']}" for e in s["nouveaux"]["exemples"]]
    else:
        lignes.append("Tous les tickets de la semaine ressemblent à un problème déjà connu.")
    lignes.append("")

    lignes += ["## Plans d'action", ""]
    lignes += [f"- À valider : {t}" for t in s["plans"]["a_valider"]]
    lignes += [f"- Validé : {t}" for t in s["plans"]["valides"]]
    if not s["plans"]["a_valider"] and not s["plans"]["valides"]:
        lignes.append("- Aucun plan d'action en cours.")
    lignes += ["", "---", "*Chiffres calculés par le moteur d'analyse (sans LLM). "
                          "Les décisions reviennent à l'équipe RUN.*", ""]
    return "\n".join(lignes)
