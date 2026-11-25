"""Les outils que le LLM peut appeler. C'est par eux — et seulement par eux — qu'il obtient
des chiffres.

Trois principes :
  1. chaque outil lit les résultats du moteur (lectures.py) : il ne recalcule rien lui-même ;
  2. chaque résultat contient des « tickets_sources » : les clés que le LLM doit citer ;
  3. on n'envoie au LLM que des extraits courts (titres, résumés), jamais les tickets complets.

Un seul outil écrit quelque chose : proposer_plan_action. Il écrit dans NOTRE base SQLite,
au statut « proposé ». Aucun outil n'écrit dans Jira.
"""
from .. import db, lectures

MAX_RESULTATS = 10          # nombre maximal d'éléments renvoyés par un outil
LONGUEUR_EXTRAIT = 300      # longueur maximale d'un extrait de ticket envoyé au LLM


def periode():
    """La période analysée, rappelée dans chaque résultat."""
    m = lectures.meta()
    if not m or not m["semaine_ref"]:
        return None
    ref = m["semaine_ref"]
    return {"semaine_reference": f"S{ref['numero']} ({ref['libelle']})",
            "semaines_analysees": m["nb_semaines"], "tickets_analyses": m["nb_tickets"]}


def borner(valeur, defaut=5):
    """Ramène un nombre demandé par le LLM entre 1 et MAX_RESULTATS."""
    try:
        return max(1, min(int(valeur), MAX_RESULTATS))
    except (TypeError, ValueError):
        return defaut


def fiche_courte(g):
    """Les chiffres d'un problème, tels que le LLM peut les citer."""
    return {"probleme_id": g["id"], "nom": g["nom"], "statut": g["statut"],
            "application": g["application"], "tickets": g["tickets"],
            "heures_total": g["heures_total"], "tickets_par_semaine": g["par_semaine"],
            "gain_annuel_h": g["gain"], "tickets_sources": g["cles_representatives"]}


# ------------------------------------------------------------------ les 8 outils -------
def top_recurrences(n=5, tri="heures", application=None):
    groupes = [g for g in db.lire_groupes() if g["statut"] == "recurrent"]
    if application:
        groupes = [g for g in groupes if g["application"].casefold() == application.casefold()]
    cle_de_tri = {"heures": lambda g: -g["heures_total"], "tickets": lambda g: -g["tickets"],
                  "gain": lambda g: -g["gain"]["median"]}.get(tri)
    if cle_de_tri is None:
        return {"erreur": "tri doit valoir « heures », « tickets » ou « gain »"}
    pics_par_groupe = {}
    for p in db.lire_pics():
        pics_par_groupe.setdefault(p["groupe"], []).append(p["semaine"])
    choisis = sorted(groupes, key=cle_de_tri)[:borner(n)]
    resultat = {"periode": periode(), "tri": tri, "nb_problemes_recurrents": len(groupes),
                "problemes": [{**fiche_courte(g), "semaines_de_pic": pics_par_groupe.get(g["id"], [])}
                              for g in choisis]}
    if not groupes:
        resultat["avertissement"] = "Aucun problème récurrent sur ce périmètre."
    return resultat


def pics(semaine=None):
    donnees = lectures.pics()
    if not donnees["pret"]:
        return {"erreur": "analyse indisponible"}
    liste = [p for p in donnees["pics"] if semaine is None or p["semaine"] == int(semaine)]
    resultat = {"periode": periode(), "regle": donnees["regles"],
                "pics": [{"probleme_id": p["groupe"], "nom": p["nom"], "semaine": p["semaine"],
                          "tickets_observes": p["observe"], "tickets_attendus": p["attendu"],
                          "p_valeur": p["p_valeur"], "dans_la_semaine_de_reference": p["est_semaine_ref"],
                          "tickets_sources": p["cles"][:5]} for p in liste[:MAX_RESULTATS]]}
    if semaine is not None:
        # Garde-fou : « aucun pic en semaine 12 » ne veut pas dire « aucun pic sur la période ».
        resultat["filtre"] = f"semaine {int(semaine)} uniquement"
        resultat["semaines_de_pic_sur_toute_la_periode"] = sorted({p["semaine"] for p in donnees["pics"]})
    if not liste:
        resultat["avertissement"] = ("Aucun pic anormal en semaine " + str(int(semaine)) + "."
                                     if semaine is not None else "Aucun pic anormal sur toute la période analysée.")
    return resultat


def gain_estime(probleme_id=None):
    donnees = lectures.gain()
    if not donnees["pret"]:
        return {"erreur": "analyse indisponible"}
    lignes = donnees["problemes"]
    if probleme_id is not None:
        lignes = [l for l in lignes if l["id"] == int(probleme_id)]
        if not lignes:
            return {"erreur": f"aucun gain pour le problème {probleme_id} : il n'existe pas ou n'est pas récurrent"}
    par_id = {g["id"]: g for g in db.lire_groupes()}
    return {"periode": periode(),
            "hypothese": "gain = heures consommées par semaine x 52 x part des tickets évités",
            "part_evitee_par_scenario": donnees["taux"],
            "gain_total_h_par_an": donnees["total"] if probleme_id is None else None,
            "problemes": [{"probleme_id": l["id"], "nom": l["nom"], "heures_total": l["heures_total"],
                           "gain_annuel_h": l["gain"],
                           "tickets_sources": par_id[l["id"]]["cles_representatives"]}
                          for l in lignes[:MAX_RESULTATS]],
            "avertissements": donnees["avertissements"]}


def detail_probleme(probleme_id):
    g = db.lire_groupe(int(probleme_id))
    if not g:
        return {"erreur": f"problème inconnu : {probleme_id}",
                "problemes_disponibles": [{"probleme_id": x["id"], "nom": x["nom"]} for x in db.lire_groupes()]}
    fiche = {**fiche_courte(g), "description": g["description"], "mots_cles": g["mots_cles"],
             "titres_representatifs": g["exemples"], "semaines_actives": g["semaines_actives"],
             "heures_moyennes_par_ticket": g["heures_moy"], "tickets_par_semaine_serie": g["serie"],
             "solution_habituelle": g["solution"][:LONGUEUR_EXTRAIT],
             "solution_appliquee_dans_n_tickets": g["solution_nb"],
             "semaines_de_pic": [p["semaine"] for p in db.lire_pics() if p["groupe"] == g["id"]],
             "periode": periode()}
    if g["statut"] == "a_verifier":
        raison = ("ses tickets sont un même texte recopié" if g["motif_verification"] == "texte_recopie"
                  else "ses tickets sont trop différents les uns des autres (groupe hétérogène)")
        fiche["avertissement"] = f"Groupe « à vérifier » : {raison}, ce n'est pas un problème récurrent établi."
    return fiche


def tickets_similaires(texte):
    resultat = lectures.analyser_texte(str(texte)[:1000], nb=5)
    if not resultat["pret"]:
        return {"erreur": "analyse indisponible"}
    p = resultat["probleme"]
    return {"verdict": "problème connu" if resultat["connu"] else "nouveau problème",
            "ressemblance": resultat["score"], "seuil": resultat["seuil"],
            "probleme_le_plus_proche": {"probleme_id": p["id"], "nom": p["nom"], "statut": p["statut"],
                                        "solution_habituelle": p["solution"][:LONGUEUR_EXTRAIT]} if p else None,
            "tickets_similaires": [{"cle": s["cle"], "titre": s["titre"], "ressemblance": s["score"]}
                                   for s in resultat["similaires"]],
            "tickets_sources": [s["cle"] for s in resultat["similaires"]]}


def detail_ticket(cle):
    t = lectures.ticket(str(cle))
    if not t:
        return {"erreur": f"ticket introuvable : {cle}", "tickets_sources": []}
    return {"cle": t["cle"], "titre": t["titre_propre"], "application": t["application"],
            "type": t["type"], "priorite": t["priorite"], "statut": t["statut"],
            "cree": (t["cree"] or "")[:10], "heures": round(t["heures"], 2),
            "resume": t["description"][:LONGUEUR_EXTRAIT],
            "resolution": t["solution"][:LONGUEUR_EXTRAIT],
            "probleme": t["probleme"], "tickets_sources": [t["cle"]]}


def synthese_hebdo(semaine=None):
    s = lectures.synthese_hebdo(int(semaine) if semaine else None)
    if not s:
        return {"erreur": "semaine hors de la période analysée"}
    sources = [c for p in s["pics"] for c in p["cles"]] + [c for p in s["problemes"] for c in p["cles"][:2]]
    return {"semaine": f"S{s['semaine']['numero']} ({s['semaine']['libelle']})",
            "semaine_complete": s["semaine"]["complete"],
            "tickets": s["nb_tickets"], "heures": s["heures"],
            "semaine_precedente": s["semaine_precedente"],
            "pics": [{"probleme_id": p["probleme_id"], "nom": p["nom"], "tickets_observes": p["observe"],
                      "tickets_attendus": p["attendu"], "tickets_sources": p["cles"]} for p in s["pics"]],
            "problemes_les_plus_presents": [{"probleme_id": p["id"], "nom": p["nom"], "statut": p["statut"],
                                             "tickets": p["tickets"], "niveau_habituel": p["habituel"],
                                             "heures": p["heures"], "tickets_sources": p["cles"]}
                                            for p in s["problemes"]],
            "tickets_sans_probleme_connu": s["nouveaux"],
            "plans": s["plans"],
            "tickets_sources": list(dict.fromkeys(sources))[:10]}


def proposer_plan_action(probleme_id, titre, actions, tickets_sources=None):
    g = db.lire_groupe(int(probleme_id))
    if not g:
        return {"erreur": f"problème inconnu : {probleme_id}"}
    if g["statut"] == "a_verifier":
        return {"erreur": "ce groupe est « à vérifier » (texte recopié ou groupe hétérogène) : aucun plan n'est proposé"}
    if not isinstance(actions, list) or not [a for a in actions if str(a).strip()]:
        return {"erreur": "il faut au moins une action"}
    plan, refusees = lectures.preparer_plan(int(probleme_id), str(titre), [str(a) for a in actions],
                                            tickets_sources, origine="copilote")
    cree = db.creer_plan(plan)
    resultat = {"plan_id": cree["id"], "statut": "proposé — en attente de validation par l'équipe RUN",
                "titre": cree["titre"], "probleme": cree["probleme_nom"], "actions": cree["actions"],
                "tickets_concernes": cree["nb_tickets"], "gain_annuel_h": cree["gain"],
                "tickets_sources": cree["tickets"]}
    if refusees:
        resultat["cles_refusees"] = refusees
        resultat["avertissement"] = "Certaines clés citées n'appartiennent pas à ce problème : elles ont été retirées."
    return resultat


# ------------------------------------------------------------------ déclaration --------
FONCTIONS = {f.__name__: f for f in (top_recurrences, pics, gain_estime, detail_probleme,
                                     tickets_similaires, detail_ticket, synthese_hebdo,
                                     proposer_plan_action)}

_ID = {"type": "integer", "description": "Numéro du problème (champ probleme_id renvoyé par les autres outils)."}
_SEMAINE = {"type": "integer", "description": "Numéro de semaine (ex. 9 pour S9). Par défaut : la semaine de référence."}


def declarer(nom, description, proprietes, obligatoires=()):
    """Décrit un outil dans le format attendu par l'API (JSON Schema)."""
    return {"type": "function",
            "function": {"name": nom, "description": description,
                         "parameters": {"type": "object", "properties": proprietes,
                                        "required": list(obligatoires)}}}


SCHEMA_OUTILS = [
    declarer("top_recurrences", "Problèmes récurrents classés par heures consommées, nombre de tickets ou gain.", {
        "n": {"type": "integer", "description": "Nombre de problèmes (1 à 10)."},
        "tri": {"type": "string", "enum": ["heures", "tickets", "gain"]},
        "application": {"type": "string", "description": "Filtrer sur une application (optionnel)."}}),
    declarer("pics", "Pics anormaux de tickets détectés par test statistique. Sans argument : TOUS les pics "
                     "de la période analysée (à utiliser pour toute question sur la période).",
             {"semaine": {"type": "integer", "description": "Optionnel : ne garder que cette semaine (ex. 9 pour S9). "
                                                            "Ne pas renseigner pour voir toute la période."}}),
    declarer("gain_estime", "Gain annuel estimé (heures/an, 3 scénarios) si la cause d'un problème est traitée. "
                            "Sans probleme_id : tous les problèmes et le total.", {"probleme_id": _ID}),
    declarer("detail_probleme", "Fiche d'un problème : description, chiffres, série hebdomadaire, "
                                "solution habituelle, tickets représentatifs.", {"probleme_id": _ID}, ["probleme_id"]),
    declarer("tickets_similaires", "Compare un texte de ticket aux problèmes connus : verdict "
                                   "connu / nouveau et tickets passés les plus proches.",
             {"texte": {"type": "string", "description": "Titre ou description du ticket."}}, ["texte"]),
    declarer("detail_ticket", "Détail d'un ticket par sa clé (ex. TMA-1293).",
             {"cle": {"type": "string"}}, ["cle"]),
    declarer("synthese_hebdo", "Faits marquants d'une semaine : volume, pics, problèmes les plus présents, "
                               "tickets sans problème connu, plans.", {"semaine": _SEMAINE}),
    declarer("proposer_plan_action", "Enregistre un plan d'action PROPOSÉ pour un problème. Il devra être "
                                     "validé par l'équipe RUN. Le gain est calculé par le moteur, ne le fournis pas.", {
        "probleme_id": _ID,
        "titre": {"type": "string", "description": "Titre court du plan."},
        "actions": {"type": "array", "items": {"type": "string"}, "description": "2 à 5 actions concrètes."},
        "tickets_sources": {"type": "array", "items": {"type": "string"},
                            "description": "Clés de tickets du problème qui justifient le plan."}},
             ["probleme_id", "titre", "actions"]),
]


def appeler_outil(nom, arguments):
    """Exécute l'outil demandé par le LLM. Une erreur devient un message, jamais un plantage."""
    fonction = FONCTIONS.get(nom)
    if fonction is None:
        return {"erreur": f"outil inconnu : {nom}"}
    try:
        return fonction(**arguments)
    except Exception as erreur:
        return {"erreur": f"appel invalide de {nom} : {erreur.__class__.__name__} : {erreur}"}
