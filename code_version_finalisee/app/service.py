"""Chef d'orchestre : lire la source, lancer le moteur, enregistrer les résultats.

L'analyse tourne dans un fil d'exécution à part (thread) : l'application reste utilisable
pendant le calcul, et la page affiche l'étape en cours.

Ce fichier garde aussi en mémoire les vecteurs de la dernière analyse (ETAT["memoire"]),
nécessaires pour rattacher un nouveau ticket sans tout recalculer.
"""
import threading
import traceback

from . import db, sources
from .config import lire_config, llm_configure
from .moteur import pipeline

CONFIG = lire_config()

# État partagé entre l'analyse (thread) et les pages web.
ETAT = {"en_cours": False, "etape": "", "erreur": None, "memoire": None}
_verrou = threading.Lock()          # empêche deux analyses de démarrer en même temps


def demarrer():
    """Appelée une fois au lancement de l'application."""
    db.initialiser(CONFIG["dossier_donnees"] / "tma.sqlite")
    lancer_analyse(recharger_source=True)


def reglages():
    """Les seuils actuels (ceux de la page « Connecteurs et seuils »)."""
    return db.lire_reglages(pipeline.REGLAGES_PAR_DEFAUT)


def lancer_analyse(recharger_source=True):
    """Démarre une analyse en arrière-plan. Renvoie False si une analyse tourne déjà.

    recharger_source : vrai pour relire Jira / le fichier ; faux pour réanalyser les tickets
    déjà enregistrés (suffisant quand on change seulement de semaine ou de seuil).
    """
    with _verrou:
        if ETAT["en_cours"]:
            return False
        ETAT.update(en_cours=True, erreur=None, etape="Démarrage")
    threading.Thread(target=_executer, args=(recharger_source,), daemon=True).start()
    return True


def _executer(recharger_source):
    """Le travail fait dans le thread : toute erreur est notée au lieu de faire planter l'appli."""
    try:
        executer_analyse(recharger_source)
    except Exception as erreur:                       # on garde un message lisible pour la page
        traceback.print_exc()
        ETAT["erreur"] = f"{erreur.__class__.__name__} : {erreur}"
    finally:
        ETAT.update(en_cours=False, etape="")


def lire_la_source():
    """Lit les tickets à la source et les enregistre. En cas d'échec (Jira injoignable...),
    on garde les tickets déjà enregistrés et on note l'erreur."""
    ETAT["etape"] = "Lecture des tickets"
    try:
        tickets, infos = sources.charger_tickets(CONFIG)
    except Exception as erreur:
        ETAT["erreur"] = (f"Lecture de la source « {CONFIG['source']} » impossible : {erreur}. "
                          "Analyse faite sur les tickets déjà enregistrés.")
        return
    pipeline.preparer_textes(tickets, CONFIG["identifiants_a_retirer"])
    db.remplacer_tickets(tickets)
    db.ecrire_memo("source", {**infos, "nb_tickets": len(tickets)})


def executer_analyse(recharger_source=True):
    """Une analyse complète, étape par étape."""
    from datetime import datetime
    if recharger_source or not db.lire_memo("source"):
        lire_la_source()
    infos = db.lire_memo("source") or {"vivante": False, "fin_des_donnees": None}
    fin = datetime.fromisoformat(infos["fin_des_donnees"]) if infos.get("fin_des_donnees") else None

    ETAT["etape"] = "Regroupement et calcul des récurrences"
    resultat = pipeline.analyser(
        db.lire_tous_les_tickets(), reglages(), dossier_cache=CONFIG["dossier_donnees"],
        fin_des_donnees=fin, source_vivante=infos.get("vivante", False),
        prefixes_identifiants=CONFIG["identifiants_a_retirer"], nom_modele=CONFIG["modele_embeddings"])
    db.enregistrer_analyse(resultat)
    ETAT["memoire"] = resultat["memoire"]

    # Le tableau de bord est déjà disponible. Le LLM, s'il existe, améliore ensuite les noms.
    if llm_configure(CONFIG) and reglages()["nommage_llm"]:
        ETAT["etape"] = "Rédaction des noms de problèmes par le LLM"
        from .copilote import llm, nommage
        try:
            nommage.nommer_les_groupes(CONFIG)
        except llm.LLMIndisponible as erreur:
            # L'analyse est déjà enregistrée : on signale seulement que les noms restent ceux du moteur.
            ETAT["erreur"] = f"Noms de problèmes non rédigés par le LLM. {erreur}"
