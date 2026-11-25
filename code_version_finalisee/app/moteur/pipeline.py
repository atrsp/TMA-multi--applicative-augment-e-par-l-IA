"""Enchaîner toutes les étapes du moteur d'analyse.

    tickets ──► nettoyer ──► choisir la période ──► vectoriser ──► regrouper ──► décrire
            ──► récurrences, pics, gain ──► résultat (un dictionnaire)

La fonction principale est analyser(). Elle ne lit ni n'écrit aucune base de données :
on lui donne des tickets et des réglages, elle renvoie un résultat. C'est ce qui la rend
facile à tester et indépendante de la source des tickets (Jira, démo, fichier).

FORMAT D'UN TICKET attendu en entrée (dictionnaire) :
    cle, titre, description, application, type, priorite, statut,
    cree (datetime), heures (nombre décimal), solution (texte, peut être vide)
"""
from collections import Counter
from datetime import date

import numpy as np

from . import etiquettes, groupes as mod_groupes, nouveau_ticket, recurrences, semaines, vecteurs
from .nettoyage import construire_motif, nettoyer

# Réglages par défaut. Ils sont tous modifiables dans la page « Connecteurs et seuils ».
REGLAGES_PAR_DEFAUT = {
    "semaine_ref": "",          # lundi de la semaine de référence ("" = dernière semaine complète)
    "fenetre_semaines": 12,     # nombre de semaines d'historique analysées (0 = tout l'historique)
    "taille_min_groupe": 0,     # taille minimale d'un groupe (0 = automatique selon le volume)
    "semaines_min": 4,          # un problème récurrent apparaît dans au moins 4 semaines
    "alpha": 0.01,              # p-valeur sous laquelle on déclare un pic
    "pic_min": 5,               # nombre minimal de tickets pour parler de pic
    "historique_pics": 4,       # semaines de passé exigées avant de chercher des pics
    "seuil_nouveaute": 0.6,     # similarité minimale pour dire « problème connu »
    "cohesion_min": 0.75,       # ressemblance moyenne minimale entre un groupe et ses tickets
    "taux_pessimiste": 0.3,     # part des tickets évités si l'on traite la cause (3 scénarios)
    "taux_median": 0.5,
    "taux_optimiste": 0.8,
    "nommage_llm": True,        # laisser le LLM rédiger nom et description (si un LLM est configuré)
}

NB_CLES_REPRESENTATIVES = 5     # tickets cités comme exemples d'un groupe
LONGUEUR_EXTRAIT = 220          # longueur maximale d'un extrait de description


# ----------------------------------------------------------------------------------------
# Étape 1 : préparer les textes
# ----------------------------------------------------------------------------------------
def preparer_textes(tickets, prefixes_identifiants):
    """Ajoute à chaque ticket son titre nettoyé et le texte complet à analyser."""
    motif = construire_motif(prefixes_identifiants)
    for t in tickets:
        t["titre_propre"] = nettoyer(t["titre"], motif)
        description = nettoyer(t["description"], motif)
        # Si la description ne fait que répéter le titre, inutile de la doubler.
        t["texte_propre"] = (t["titre_propre"] if description.rstrip(".") == t["titre_propre"].rstrip(".")
                             else f'{t["titre_propre"]}. {description}'.strip())
    return tickets


# ----------------------------------------------------------------------------------------
# Étape 2 : choisir la période analysée
# ----------------------------------------------------------------------------------------
def choisir_periode(calendrier, semaine_ref, fenetre):
    """Renvoie (semaine de référence, numéro de la première semaine analysée).

    semaine_ref : lundi choisi par l'utilisateur ("" = automatique).
    fenetre     : nombre de semaines d'historique (0 = depuis le début).
    """
    choisie = next((s for s in calendrier if s["lundi"] == semaine_ref), None)
    reference = choisie or semaines.semaine_par_defaut(calendrier)
    premiere = 1 if fenetre <= 0 else max(1, reference["numero"] - fenetre + 1)
    return reference, premiere


# ----------------------------------------------------------------------------------------
# Étape 6 : décrire un groupe
# ----------------------------------------------------------------------------------------
def solution_habituelle(tickets_du_groupe):
    """La résolution la plus souvent notée dans le groupe, et dans combien de tickets."""
    compte = Counter(t["solution"].strip() for t in tickets_du_groupe if t["solution"].strip())
    if not compte:
        return "", 0
    return compte.most_common(1)[0]


def decrire_groupe(numero, membres, tickets, X, mots, premiere, derniere, reglages):
    """Construit la fiche complète d'un groupe (un dictionnaire).

    membres : positions des tickets du groupe dans la liste `tickets` (et dans X).
    """
    du_groupe = [tickets[i] for i in membres]
    serie = recurrences.serie_hebdomadaire([t["semaine"] for t in du_groupe], premiere, derniere)
    resume = recurrences.resume_du_groupe(du_groupe, serie)
    nb_semaines = derniere - premiere + 1

    ordre = etiquettes.indices_representatifs(X, membres)        # du plus typique au moins typique
    exemples = etiquettes.titres_representatifs([t["titre_propre"] for t in tickets], ordre)
    solution, solution_nb = solution_habituelle(du_groupe)

    # Cohésion : ressemblance moyenne des tickets avec le centre du groupe (1 = identiques).
    # Un groupe peu cohérent est un « fourre-tout » : ses tickets ne parlent pas vraiment
    # du même problème, on ne doit pas le présenter comme une récurrence.
    cohesion = mod_groupes.cohesion(X, membres)

    # Statut : « à vérifier » (texte recopié ou groupe hétérogène), « récurrent » ou « ponctuel ».
    part_dominante = mod_groupes.part_du_texte_dominant([t["texte_propre"] for t in du_groupe])
    motif_verification = None
    if part_dominante >= mod_groupes.PART_TEXTE_RECOPIE:
        statut, motif_verification = "a_verifier", "texte_recopie"
    elif cohesion < reglages["cohesion_min"]:
        statut, motif_verification = "a_verifier", "heterogene"
    elif recurrences.est_recurrent(resume["semaines_actives"], reglages["semaines_min"], nb_semaines):
        statut = "recurrent"
    else:
        statut = "ponctuel"

    taux = {"pessimiste": reglages["taux_pessimiste"], "median": reglages["taux_median"],
            "optimiste": reglages["taux_optimiste"]}

    # Extraits courts de descriptions distinctes : matière pour la description du groupe.
    extraits = list(dict.fromkeys(tickets[i]["texte_propre"][:LONGUEUR_EXTRAIT] for i in ordre))[:3]

    return {
        "numero_interne": numero,
        "statut": statut,
        "nom": etiquettes.nom_sans_llm(exemples, mots),
        "description": etiquettes.description_sans_llm(resume["application"], resume["type"],
                                                       exemples, mots, solution),
        "origine_nom": "moteur",          # deviendra « llm » si le copilote rédige le nom
        "mots_cles": mots,
        "exemples": exemples,
        "extraits": extraits,
        **resume,
        "par_semaine": round(resume["tickets"] / nb_semaines, 1),
        "serie": serie,
        # Le gain n'a de sens que pour un problème réellement récurrent.
        "gain": recurrences.gain_annuel(resume["heures_total"], nb_semaines, taux)
                if statut == "recurrent" else None,
        "solution": solution,
        "solution_nb": solution_nb,
        "part_texte_dominant": round(part_dominante, 2),
        "cohesion": round(cohesion, 2),
        "motif_verification": motif_verification,     # pourquoi le groupe est « à vérifier »
        "cles_representatives": [tickets[i]["cle"] for i in ordre[:NB_CLES_REPRESENTATIVES]],
    }


# ----------------------------------------------------------------------------------------
# Fonction principale
# ----------------------------------------------------------------------------------------
def analyser(tickets, reglages=None, dossier_cache="data", fin_des_donnees=None,
             source_vivante=False, prefixes_identifiants=("CLI", "DOS"),
             nom_modele=vecteurs.MODELE_PAR_DEFAUT):
    """Analyse complète. Renvoie un dictionnaire avec 5 parties :

        meta          : période analysée, volumes, avertissements
        groupes       : une fiche par groupe (triées par heures consommées)
        affectations  : pour chaque ticket analysé, son groupe et sa ressemblance
        pics          : les semaines anormales
        memoire       : les vecteurs et les centres (gardés en mémoire pour rattacher
                        les nouveaux tickets ; jamais enregistrés en base)
    """
    reglages = {**REGLAGES_PAR_DEFAUT, **(reglages or {})}
    avertissements = []

    tickets = [t for t in tickets if t.get("cree") is not None]
    if not tickets:
        return resultat_vide(reglages, ["Aucun ticket daté à analyser."])
    preparer_textes(tickets, prefixes_identifiants)

    # --- Période : semaine de référence + fenêtre d'historique -------------------------
    dates = [t["cree"] for t in tickets]
    fin = fin_des_donnees or max(dates)
    calendrier = semaines.calendrier(dates, fin, inclure_aujourdhui=source_vivante)
    origine = date.fromisoformat(calendrier[0]["lundi"])
    reference, premiere = choisir_periode(calendrier, reglages["semaine_ref"],
                                          reglages["fenetre_semaines"])
    derniere = reference["numero"]
    nb_semaines = derniere - premiere + 1

    for t in tickets:
        t["semaine"] = semaines.numero_de(semaines.lundi_de(t["cree"]), origine)
    nb_base = len(tickets)
    # On ne garde que la période : les tickets créés APRÈS la semaine de référence sont
    # ignorés, comme si l'on était à la fin de cette semaine.
    tickets = [t for t in tickets if premiere <= t["semaine"] <= derniere]

    meta = {
        "semaine_ref": {**reference, "libelle": semaines.libelle(reference["lundi"])},
        "premiere_semaine": premiere,
        "nb_semaines": nb_semaines,
        "semaines": [s for s in calendrier if premiere <= s["numero"] <= derniere],
        "semaines_disponibles": calendrier,
        "nb_tickets": len(tickets),
        "nb_tickets_base": nb_base,
        "heures_total": round(sum(t["heures"] for t in tickets), 1),
        "serie_totale": recurrences.serie_hebdomadaire([t["semaine"] for t in tickets],
                                                       premiere, derniere),
        "reglages": reglages,
        "avertissements": avertissements,
    }
    if not reference["complete"]:
        avertissements.append("La semaine de référence n'est pas terminée : ses volumes sont partiels.")
    if not tickets:
        avertissements.append("Aucun ticket sur la période choisie.")
        return {**resultat_vide(reglages, avertissements), "meta": {**meta, "taille_min_groupe": 0,
                                                                     "nb_vecteurs_calcules": 0}}
    sans_temps = sum(1 for t in tickets if t["heures"] <= 0)
    if sans_temps:
        avertissements.append(f"{sans_temps} ticket(s) sans temps passé : les heures consommées "
                              "et le gain sont sous-estimés.")

    # --- Vecteurs (cache disque) puis groupes ------------------------------------------
    X, nb_calcules = vecteurs.vectoriser([t["texte_propre"] for t in tickets],
                                         dossier_cache, nom_modele)
    taille_min = reglages["taille_min_groupe"] or mod_groupes.taille_min_auto(len(tickets))
    etiquettes_brutes = mod_groupes.regrouper(X, taille_min)
    meta["taille_min_groupe"] = taille_min
    meta["nb_vecteurs_calcules"] = nb_calcules

    # --- Fiche de chaque groupe ---------------------------------------------------------
    mots = etiquettes.mots_cles_ctfidf([t["texte_propre"] for t in tickets], etiquettes_brutes)
    fiches = [decrire_groupe(k, np.where(etiquettes_brutes == k)[0], tickets, X, mots[k],
                             premiere, derniere, reglages)
              for k in sorted(mots)]
    if not fiches:
        avertissements.append("Aucun groupe trouvé : trop peu de tickets semblables sur la période. "
                              "Essayez une taille minimale de groupe plus petite.")

    # Numéros définitifs : 1 = le groupe le plus coûteux en heures, 2 = le suivant...
    fiches.sort(key=lambda f: -f["heures_total"])
    nouveau_numero = {f["numero_interne"]: rang for rang, f in enumerate(fiches, start=1)}
    for f in fiches:
        f["id"] = nouveau_numero[f.pop("numero_interne")]
    groupe_de = np.array([nouveau_numero.get(int(k), -1) for k in etiquettes_brutes])

    # --- Pics (jamais sur un groupe « à vérifier ») -------------------------------------
    pics = []
    for f in fiches:
        if f["statut"] == "a_verifier":
            continue
        for alerte in recurrences.detecter_pics(f["serie"], premiere, reglages["alpha"],
                                                reglages["pic_min"], reglages["historique_pics"]):
            pics.append({"groupe": f["id"], **alerte})

    # --- Ressemblance de chaque ticket avec les centres ---------------------------------
    ids, centres = mod_groupes.centres_des_groupes(X, groupe_de)
    meilleurs, scores = nouveau_ticket.rattacher_tous(X, ids, centres)
    affectations = [{"cle": t["cle"], "semaine": t["semaine"], "groupe": int(g),
                     "meilleur_groupe": m, "score": s}
                    for t, g, m, s in zip(tickets, groupe_de, meilleurs, scores)]

    return {"meta": meta, "groupes": fiches, "affectations": affectations, "pics": pics,
            "memoire": {"X": X, "cles": [t["cle"] for t in tickets], "groupe_de": groupe_de,
                        "ids": ids, "centres": centres, "nom_modele": nom_modele}}


def resultat_vide(reglages, avertissements):
    """Résultat renvoyé quand il n'y a rien à analyser (l'application reste utilisable)."""
    meta = {"semaine_ref": None, "premiere_semaine": 1, "nb_semaines": 0, "semaines": [],
            "semaines_disponibles": [], "nb_tickets": 0, "nb_tickets_base": 0, "heures_total": 0.0,
            "serie_totale": [], "reglages": reglages, "avertissements": avertissements,
            "taille_min_groupe": 0, "nb_vecteurs_calcules": 0}
    return {"meta": meta, "groupes": [], "affectations": [], "pics": [],
            "memoire": {"X": np.zeros((0, 384), dtype=np.float32), "cles": [],
                        "groupe_de": np.zeros(0, dtype=int), "ids": [],
                        "centres": np.zeros((0, 384), dtype=np.float32),
                        "nom_modele": vecteurs.MODELE_PAR_DEFAUT}}


# ----------------------------------------------------------------------------------------
# Rattacher un texte libre (page « Nouveaux tickets » et outil tickets_similaires)
# ----------------------------------------------------------------------------------------
def analyser_nouveau_texte(texte, memoire, seuil, prefixes_identifiants=("CLI", "DOS"), nb=3):
    """Compare un texte libre aux groupes de la dernière analyse.

    Renvoie {"connu", "groupe", "score", "similaires": [(clé, cosinus), ...]}.
    Les tickets similaires sont cherchés dans le groupe le plus proche si le problème est
    connu, sinon dans tous les tickets analysés.
    """
    propre = nettoyer(texte, construire_motif(prefixes_identifiants))
    if not propre or len(memoire["cles"]) == 0:
        return {"connu": False, "groupe": None, "score": 0.0, "similaires": []}
    x = vecteurs.encoder([propre], memoire["nom_modele"])[0]
    verdict = nouveau_ticket.rattacher(x, memoire["ids"], memoire["centres"], seuil)
    if verdict["connu"]:
        positions = np.where(memoire["groupe_de"] == verdict["groupe"])[0]
    else:
        positions = np.arange(len(memoire["cles"]))
    proches = nouveau_ticket.plus_proches(x, memoire["X"], positions, nb)
    verdict["similaires"] = [(memoire["cles"][i], score) for i, score in proches]
    return verdict
