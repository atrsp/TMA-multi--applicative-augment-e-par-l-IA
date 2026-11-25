"""Lire les résultats d'analyse et les mettre en forme pour les pages et pour le copilote.

Les routes de l'API (main.py) ET les outils de l'agent (copilote/outils.py) passent par
ces fonctions : les chiffres affichés à l'écran et ceux cités par le copilote sont donc
exactement les mêmes.
"""
from . import db, service
from .config import llm_configure
from .moteur import pipeline, semaines, synthese


# ------------------------------------------------------------------ petites aides ------
def meta():
    """La période et les volumes de la dernière analyse (None si aucune analyse n'a abouti)."""
    return db.lire_memo("meta")


def etiquette_semaine(numero, meta_):
    """Texte court d'une semaine : « S9 · 27/07 »."""
    semaine = next((s for s in meta_["semaines_disponibles"] if s["numero"] == numero), None)
    if not semaine:
        return f"S{numero}"
    jour, mois = semaine["lundi"][8:10], semaine["lundi"][5:7]
    return f"S{numero} · {jour}/{mois}"


def groupe_de_chaque_plan(plans):
    """Associe chaque plan au groupe ACTUEL de ses tickets.

    Les numéros de groupe changent d'une analyse à l'autre ; les clés de tickets, non.
    On retrouve donc le problème d'un plan grâce aux tickets qu'il cite.
    """
    liens = {}
    for plan in plans:
        for cle in plan["tickets"] or []:
            ticket = db.lire_ticket(cle)
            if ticket and ticket["groupe"] not in (None, -1):
                liens[plan["id"]] = ticket["groupe"]
                break
    return liens


def statut_plan_par_groupe():
    """Pour chaque groupe : le statut du plan le plus récent qui le concerne (ou rien)."""
    plans = db.lire_plans()                       # du plus récent au plus ancien
    liens = groupe_de_chaque_plan(plans)
    statuts = {}
    for plan in plans:
        groupe = liens.get(plan["id"])
        if groupe is not None and groupe not in statuts:
            statuts[groupe] = plan["statut"]
    return statuts


def resume_groupe(g, pics, statuts_plan):
    """La ligne d'un groupe dans les tableaux (sans la longue description)."""
    return {"id": g["id"], "nom": g["nom"], "statut": g["statut"], "origine_nom": g["origine_nom"],
            "application": g["application"], "type": g["type"], "tickets": g["tickets"],
            "semaines_actives": g["semaines_actives"], "heures_total": g["heures_total"],
            "heures_moy": g["heures_moy"], "par_semaine": g["par_semaine"], "serie": g["serie"],
            "gain": g["gain"], "mots_cles": g["mots_cles"],
            "cohesion": g["cohesion"], "motif_verification": g["motif_verification"],
            "pics": [p["semaine"] for p in pics if p["groupe"] == g["id"]],
            "plan": statuts_plan.get(g["id"])}


# ------------------------------------------------------------------ état général -------
def etat():
    """Ce que l'en-tête et la page « Connecteurs » affichent en permanence."""
    m, source = meta(), db.lire_memo("source") or {}
    config = service.CONFIG
    # Petits compteurs affichés dans le menu latéral.
    compteurs = {"problemes": 0, "pics": 0, "plans": 0}
    if m and m["semaine_ref"]:
        compteurs = {
            "problemes": sum(1 for g in db.lire_groupes() if g["statut"] == "recurrent"),
            "pics": sum(1 for p in db.lire_pics() if p["semaine"] == m["semaine_ref"]["numero"]),
            "plans": sum(1 for p in db.lire_plans() if p["statut"] == "propose"),
        }
    return {
        "compteurs": compteurs,
        "avertissements": m["avertissements"] if m else [],
        "pret": m is not None,
        "analyse_en_cours": service.ETAT["en_cours"],
        "etape": service.ETAT["etape"],
        "erreur": service.ETAT["erreur"],
        "source": {"type": config["source"], "detail": source.get("detail", ""),
                   "nb_tickets": source.get("nb_tickets", 0), "lecture_seule": True},
        "llm": {"actif": llm_configure(config),
                "modele": (config["azure_deploiement"] if config["azure_endpoint"] else config["llm_modele"])
                          if llm_configure(config) else None},
        "date_analyse": m["date_analyse"] if m else None,
        "semaine_ref": m["semaine_ref"] if m else None,
        "semaines_disponibles": m["semaines_disponibles"] if m else [],
        "fenetre_semaines": service.reglages()["fenetre_semaines"],
        "semaine_ref_auto": service.reglages()["semaine_ref"] == "",
    }


# ------------------------------------------------------------------ tableau de bord ----
def tableau_de_bord():
    m = meta()
    if not m or not m["semaine_ref"]:
        return {"pret": False, "avertissements": m["avertissements"] if m else []}
    groupes, pics, plans = db.lire_groupes(), db.lire_pics(), db.lire_plans()
    statuts = statut_plan_par_groupe()
    recurrents = [g for g in groupes if g["statut"] == "recurrent"]
    par_id = {g["id"]: g for g in groupes}
    numero_ref = m["semaine_ref"]["numero"]

    # --- Indicateurs -------------------------------------------------------------------
    nb_recurrents = sum(g["tickets"] for g in recurrents)
    heures_rec = round(sum(g["heures_total"] for g in recurrents), 1)
    indicateurs = {
        "part_tickets_recurrents": round(100 * nb_recurrents / m["nb_tickets"]) if m["nb_tickets"] else 0,
        "nb_problemes": len(recurrents),
        "nb_a_verifier": sum(1 for g in groupes if g["statut"] == "a_verifier"),
        "heures_recurrences": heures_rec,
        "part_heures": round(100 * heures_rec / m["heures_total"]) if m["heures_total"] else 0,
        "gain": {nom: sum(g["gain"][nom] for g in recurrents)
                 for nom in ("pessimiste", "median", "optimiste")},
        "plans": {s: sum(1 for p in plans if p["statut"] == s) for s in db.STATUTS_PLAN},
    }

    # --- Alerte : le pic le plus net de la semaine de référence -----------------------
    pics_ref = [p for p in pics if p["semaine"] == numero_ref and p["groupe"] in par_id]
    alerte = None
    if pics_ref:
        p = min(pics_ref, key=lambda p: p["p_valeur"])
        alerte = {**p, "nom": par_id[p["groupe"]]["nom"], "autres": len(pics_ref) - 1}

    # --- Graphique hebdomadaire : tous les tickets + le groupe à surveiller -----------
    pics_connus = [p for p in pics if p["groupe"] in par_id]
    a_suivre = (par_id[alerte["groupe"]] if alerte
                else par_id[min(pics_connus, key=lambda p: p["p_valeur"])["groupe"]] if pics_connus
                else recurrents[0] if recurrents else None)
    serie = m["serie_totale"]
    completes = [n for n, s in zip(serie, m["semaines"]) if s["complete"]] or serie
    hebdo = {
        "etiquettes": [etiquette_semaine(s["numero"], m) for s in m["semaines"]],
        "numeros": [s["numero"] for s in m["semaines"]],
        "total": serie,
        "suivi": {"id": a_suivre["id"], "nom": a_suivre["nom"], "serie": a_suivre["serie"]} if a_suivre else None,
        "pics": sorted({p["semaine"] for p in pics_connus}),
        "moyenne": round(sum(completes) / len(completes)) if completes else 0,
        "valeur_ref": serie[-1] if serie else 0,
        "nb_pics": len(pics_connus),
    }

    return {
        "pret": True,
        "periode": {"semaine_ref": m["semaine_ref"], "nb_semaines": m["nb_semaines"],
                    "debut": m["semaines"][0]["lundi"], "nb_tickets": m["nb_tickets"],
                    "nb_applications": len({g["application"] for g in groupes}),
                    "heures_total": m["heures_total"], "taille_min_groupe": m["taille_min_groupe"]},
        "indicateurs": indicateurs,
        "alerte": alerte,
        "problemes": [resume_groupe(g, pics, statuts) for g in recurrents[:6]],
        "hebdo": hebdo,
        "nouveaux": nouveaux_tickets(4),
        "avertissements": m["avertissements"],
    }


# ------------------------------------------------------------------ problèmes ----------
def problemes():
    """Tous les groupes, rangés par statut : récurrents, ponctuels, à vérifier."""
    m = meta()
    if not m:
        return {"pret": False}
    pics, statuts = db.lire_pics(), statut_plan_par_groupe()
    lignes = [resume_groupe(g, pics, statuts) for g in db.lire_groupes()]
    return {"pret": True,
            "etiquettes": [etiquette_semaine(s["numero"], m) for s in m["semaines"]],
            "recurrents": [g for g in lignes if g["statut"] == "recurrent"],
            "ponctuels": [g for g in lignes if g["statut"] == "ponctuel"],
            "a_verifier": [g for g in lignes if g["statut"] == "a_verifier"]}


def probleme(identifiant, nb_tickets=200):
    """La fiche détaillée d'un problème : description, série, solution, tickets."""
    m, g = meta(), db.lire_groupe(identifiant)
    if not m or not g:
        return None
    tickets = db.tickets_analyses("WHERE a.groupe = ?", (identifiant,))
    plans = db.lire_plans()
    liens = groupe_de_chaque_plan(plans)
    return {**g,
            "etiquettes": [etiquette_semaine(s["numero"], m) for s in m["semaines"]],
            "numeros": [s["numero"] for s in m["semaines"]],
            "pics": [p for p in db.lire_pics() if p["groupe"] == identifiant],
            "tickets_liste": tickets[:nb_tickets],
            "plans": [p for p in plans if liens.get(p["id"]) == identifiant],
            "taux": {n: m["reglages"][f"taux_{n}"] for n in ("pessimiste", "median", "optimiste")},
            "nb_semaines": m["nb_semaines"]}


# ------------------------------------------------------------------ pics et gain -------
def pics():
    m = meta()
    if not m:
        return {"pret": False}
    par_id = {g["id"]: g for g in db.lire_groupes()}
    liste = []
    for p in db.lire_pics():
        g = par_id.get(p["groupe"])
        if not g:
            continue
        cles = [t["cle"] for t in db.tickets_analyses("WHERE a.groupe = ? AND a.semaine = ?",
                                                      (p["groupe"], p["semaine"]))]
        liste.append({**p, "nom": g["nom"], "application": g["application"],
                      "etiquette": etiquette_semaine(p["semaine"], m), "serie": g["serie"],
                      "est_semaine_ref": p["semaine"] == m["semaine_ref"]["numero"],
                      "cles": cles[:8], "solution": g["solution"]})
    r = m["reglages"]
    return {"pret": True, "pics": liste,
            "etiquettes": [etiquette_semaine(s["numero"], m) for s in m["semaines"]],
            "numeros": [s["numero"] for s in m["semaines"]],
            "semaine_ref": m["semaine_ref"],
            "regles": {"alpha": r["alpha"], "pic_min": r["pic_min"], "historique": r["historique_pics"]}}


def gain():
    m = meta()
    if not m:
        return {"pret": False}
    recurrents = [g for g in db.lire_groupes() if g["statut"] == "recurrent"]
    lignes = [{"id": g["id"], "nom": g["nom"], "application": g["application"], "tickets": g["tickets"],
               "heures_total": g["heures_total"],
               "heures_par_semaine": round(g["heures_total"] / m["nb_semaines"], 1),
               "gain": g["gain"]} for g in recurrents]
    lignes.sort(key=lambda l: -l["gain"]["median"])
    return {"pret": True, "problemes": lignes, "nb_semaines": m["nb_semaines"],
            "total": {n: sum(l["gain"][n] for l in lignes) for n in ("pessimiste", "median", "optimiste")},
            "taux": {n: m["reglages"][f"taux_{n}"] for n in ("pessimiste", "median", "optimiste")},
            "avertissements": [a for a in m["avertissements"] if "temps passé" in a]}


# ------------------------------------------------------------------ nouveaux tickets ---
def verdict_lisible(groupe_id, score, seuil, groupes_par_id):
    """Transforme (groupe le plus proche, ressemblance) en verdict affichable."""
    g = groupes_par_id.get(groupe_id)
    connu = g is not None and score >= seuil
    return {"connu": connu, "score": score, "seuil": seuil,
            "probleme": {"id": g["id"], "nom": g["nom"], "statut": g["statut"], "tickets": g["tickets"],
                         "solution": g["solution"], "solution_nb": g["solution_nb"]} if g else None}


def nouveaux_tickets(nb=10):
    """Les derniers tickets de la semaine de référence, chacun avec son verdict."""
    m = meta()
    if not m or not m["semaine_ref"]:
        return []
    seuil = m["reglages"]["seuil_nouveaute"]
    par_id = {g["id"]: g for g in db.lire_groupes()}
    derniers = db.tickets_analyses("WHERE a.semaine = ?", (m["semaine_ref"]["numero"],))[:nb]
    return [{**t, **verdict_lisible(t["meilleur_groupe"], t["score"], seuil, par_id)} for t in derniers]


def analyser_texte(texte, nb=3):
    """Rattache un texte libre à un problème connu, ou le déclare nouveau."""
    m, memoire = meta(), service.ETAT["memoire"]
    if not m or memoire is None:
        return {"pret": False}
    seuil = m["reglages"]["seuil_nouveaute"]
    brut = pipeline.analyser_nouveau_texte(texte, memoire, seuil,
                                           service.CONFIG["identifiants_a_retirer"], nb)
    par_id = {g["id"]: g for g in db.lire_groupes()}
    similaires = []
    for cle, score in brut["similaires"]:
        t = db.lire_ticket(cle)
        similaires.append({"cle": cle, "titre": t["titre_propre"], "score": score,
                           "application": t["application"], "solution": t["solution"]})
    return {"pret": True, **verdict_lisible(brut["groupe"], brut["score"], seuil, par_id),
            "similaires": similaires}


def ticket(cle):
    """Le détail d'un ticket, avec le nom de son problème."""
    t = db.lire_ticket(cle)
    if not t:
        return None
    g = db.lire_groupe(t["groupe"]) if t["groupe"] not in (None, -1) else None
    t["probleme"] = {"id": g["id"], "nom": g["nom"], "statut": g["statut"]} if g else None
    return t


# ------------------------------------------------------------------ synthèse -----------
def synthese_hebdo(numero=None):
    """Synthèse d'une semaine de la période analysée (par défaut : la semaine de référence)."""
    m = meta()
    if not m or not m["semaine_ref"]:
        return None
    numero = numero or m["semaine_ref"]["numero"]
    faits = synthese.construire(numero, m, db.lire_groupes(), db.tickets_analyses(), db.lire_pics(),
                                db.lire_plans(), m["reglages"]["seuil_nouveaute"])
    if faits is None:
        return None
    return {**faits, "markdown": synthese.en_markdown(faits),
            "semaines": [{"numero": s["numero"], "libelle": semaines.libelle(s["lundi"])}
                         for s in m["semaines"]]}


# ------------------------------------------------------------------ plans --------------
def preparer_plan(probleme_id, titre, actions, cles, origine):
    """Fabrique un plan prêt à enregistrer. Les CHIFFRES viennent toujours du moteur.

    Renvoie (plan, clés refusées). Le plan vaut None si le problème n'existe pas.
    Les clés citées sont vérifiées : seules celles qui appartiennent au problème sont gardées.
    """
    m, g = meta(), db.lire_groupe(probleme_id)
    if not m or not g:
        return None, list(cles or [])
    du_groupe = {t["cle"] for t in db.tickets_analyses("WHERE a.groupe = ?", (probleme_id,))}
    valides = [c for c in dict.fromkeys(cles or []) if c in du_groupe]
    refusees = [c for c in dict.fromkeys(cles or []) if c not in du_groupe]
    plan = {
        "origine": origine,
        "titre": titre.strip()[:200] or f"Traiter la cause : {g['nom']}",
        "probleme_nom": g["nom"],
        "semaine_ref": m["semaine_ref"]["lundi"],
        "actions": [a.strip()[:400] for a in actions if a and a.strip()][:8],
        # Sans clé valide fournie, on cite les tickets les plus représentatifs du problème.
        "tickets": valides[:10] or g["cles_representatives"],
        "nb_tickets": g["tickets"],
        "heures_total": g["heures_total"],
        "gain": g["gain"],
    }
    return plan, refusees


def plans():
    """Tous les plans, avec le numéro actuel du problème concerné (pour le lien)."""
    tous = db.lire_plans()
    liens = groupe_de_chaque_plan(tous)
    return [{**p, "probleme_id": liens.get(p["id"])} for p in tous]
