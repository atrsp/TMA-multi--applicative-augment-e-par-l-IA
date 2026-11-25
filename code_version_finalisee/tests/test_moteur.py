"""Tests du moteur d'analyse. Lancer avec :  pytest

Chaque test vérifie UNE promesse du moteur, sur le jeu de démonstration ou sur un
petit exemple écrit à la main.
"""
import csv
import random
from datetime import datetime

import numpy as np
from sklearn.metrics import adjusted_rand_score

from app.moteur import groupes, pipeline, recurrences, semaines, vecteurs
from app.moteur.nettoyage import construire_motif, nettoyer
from conftest import CACHE, DEMO, charger_demo


def groupe_nomme(analyse, mot):
    """Retrouve un groupe par un mot présent dans ses mots-clés (ex. « batch »)."""
    return next(g for g in analyse["groupes"] if mot in " ".join(g["mots_cles"]))


# ------------------------------------------------------------------ nettoyage ----------
def test_nettoyage_retire_identifiants_et_entites_html():
    motif = construire_motif(["CLI", "DOS"])
    texte = nettoyer("PDF vide sur l&#39;écran pour le dossier DOS-20745, client CLI-4821.", motif)
    assert "&#39;" not in texte and "l'écran" in texte
    assert "DOS-20745" not in texte and "CLI-4821" not in texte


def test_nettoyage_garde_les_codes_erreur():
    """ORA-01555 est une information utile : il ne doit pas être pris pour un identifiant."""
    assert "ORA-01555" in nettoyer("Erreur ORA-01555 pour CLI-1234", construire_motif(["CLI", "DOS"]))


def test_mots_cles_sans_identifiants(analyse_demo):
    for g in analyse_demo["groupes"]:
        mots = " ".join(g["mots_cles"] + g["exemples"])
        assert "&#" not in mots
        assert "dos" not in g["mots_cles"] and "cli" not in g["mots_cles"]
        assert "DOS-" not in mots and "CLI-" not in mots


# ------------------------------------------------------------------ regroupement -------
def test_regroupement_proche_de_la_verite_terrain(analyse_demo):
    """L'ARI compare nos groupes aux vraies familles (1 = identique, 0 = hasard)."""
    fichier_verite = DEMO.parent / "verite_terrain.csv"
    verite = {ligne["key"]: ligne["famille"] for ligne in csv.DictReader(open(fichier_verite, encoding="utf-8"))}
    vrai = [verite[a["cle"]] for a in analyse_demo["affectations"]]
    trouve = [a["groupe"] for a in analyse_demo["affectations"]]
    assert adjusted_rand_score(vrai, trouve) > 0.8


def test_groupes_recopies_signales_a_verifier(analyse_demo):
    """Un groupe fait d'un seul texte recopié n'est PAS un problème récurrent."""
    a_verifier = [g for g in analyse_demo["groupes"] if g["statut"] == "a_verifier"]
    assert len(a_verifier) >= 1
    assert any("orthographe" in g["nom"].lower() for g in a_verifier)
    for g in a_verifier:
        assert g["gain"] is None                       # pas de gain annoncé pour ces groupes
    # Le batch nocturne, lui, a de nombreuses formulations : c'est une vraie récurrence.
    assert groupe_nomme(analyse_demo, "batch")["statut"] == "recurrent"


def test_groupe_heterogene_signale_a_verifier(analyse_demo):
    """Les vrais problèmes de la démo sont cohérents ; un seuil de cohésion très exigeant
    les ferait tous basculer en « à vérifier » pour hétérogénéité."""
    for g in analyse_demo["groupes"]:
        if g["statut"] == "recurrent":
            assert g["cohesion"] >= 0.75 and g["motif_verification"] is None
    stricte = pipeline.analyser(charger_demo(), {"cohesion_min": 0.99}, dossier_cache=CACHE)
    assert not [g for g in stricte["groupes"] if g["statut"] == "recurrent"]
    assert "heterogene" in {g["motif_verification"] for g in stricte["groupes"]}


def test_detection_texte_recopie():
    assert groupes.est_un_texte_recopie(["Faute sur la page"] * 20)
    assert not groupes.est_un_texte_recopie(["Batch en échec", "Job planté", "Traitement KO"] * 5)


# ------------------------------------------------------------------ pics ---------------
def test_pic_batch_semaine_9_detecte(analyse_demo):
    """Le pic caché dans le jeu de démonstration (F-BATCH, semaine 9) doit être retrouvé."""
    batch = groupe_nomme(analyse_demo, "batch")
    pics_batch = [p for p in analyse_demo["pics"] if p["groupe"] == batch["id"]]
    assert [p["semaine"] for p in pics_batch] == [9]
    assert pics_batch[0]["observe"] > 2 * pics_batch[0]["attendu"]


def test_aucune_fausse_alerte(analyse_demo):
    assert len(analyse_demo["pics"]) == 1


def test_poisson_sur_une_serie_simple():
    serie = [10, 11, 9, 10, 10, 30, 10]            # la 6e semaine est anormale
    alertes = recurrences.detecter_pics(serie, premiere=1, alpha=0.01, pic_min=5, historique=4)
    assert [a["semaine"] for a in alertes] == [6]


# ------------------------------------------------------------------ gain ---------------
def test_gain_annuel_formule():
    taux = {"pessimiste": 0.3, "median": 0.5, "optimiste": 0.8}
    # 120 h sur 12 semaines = 10 h/semaine = 520 h/an ; la moitié évitée = 260 h.
    assert recurrences.gain_annuel(120, 12, taux) == {"pessimiste": 156, "median": 260, "optimiste": 416}


# ------------------------------------------------------------------ nouveau ticket -----
def test_ticket_hors_sujet_classe_nouveau(analyse_demo):
    verdict = pipeline.analyser_nouveau_texte("Demande de devis pour une nouvelle imprimante",
                                              analyse_demo["memoire"], seuil=0.6)
    assert verdict["connu"] is False
    assert verdict["score"] < 0.6


def test_ticket_batch_rattache_au_probleme_connu(analyse_demo):
    verdict = pipeline.analyser_nouveau_texte("Le batch de nuit a planté avec ORA-01555",
                                              analyse_demo["memoire"], seuil=0.6)
    assert verdict["connu"] is True
    assert verdict["groupe"] == groupe_nomme(analyse_demo, "batch")["id"]
    assert len(verdict["similaires"]) == 3


# ------------------------------------------------------------------ semaine au choix ---
def test_semaine_par_defaut_est_la_derniere_complete(analyse_demo):
    reference = analyse_demo["meta"]["semaine_ref"]
    assert reference["numero"] == 12 and reference["complete"] is True


def test_semaine_de_reference_au_choix():
    """Analyser « comme si l'on était en semaine 9 » : aucun ticket postérieur n'est utilisé,
    et le pic de la semaine 9 est déjà visible."""
    analyse = pipeline.analyser(charger_demo(), {"semaine_ref": "2026-07-27"}, dossier_cache=CACHE)
    assert analyse["meta"]["semaine_ref"]["numero"] == 9
    assert max(a["semaine"] for a in analyse["affectations"]) == 9
    assert 9 in [p["semaine"] for p in analyse["pics"]]


def test_semaine_passee_sans_pic():
    """En se plaçant en semaine 6, le pic de la semaine 9 n'existe pas encore."""
    analyse = pipeline.analyser(charger_demo(), {"semaine_ref": "2026-07-06"}, dossier_cache=CACHE)
    assert analyse["pics"] == []


def test_calendrier_et_semaine_incomplete():
    dates = [datetime(2026, 6, 1, 9), datetime(2026, 6, 17, 9)]      # lundi S1 et mercredi S3
    cal = semaines.calendrier(dates, fin_des_donnees=datetime(2026, 6, 17, 9))
    assert [s["numero"] for s in cal] == [1, 2, 3]
    assert [s["complete"] for s in cal] == [True, True, False]
    assert semaines.semaine_par_defaut(cal)["numero"] == 2


# ------------------------------------------------------------------ robustesse ---------
def test_petit_fichier_de_100_tickets():
    """Avec une centaine de tickets, la taille de groupe s'adapte et l'analyse aboutit."""
    random.seed(1)
    analyse = pipeline.analyser(random.sample(charger_demo(), 100), dossier_cache=CACHE)
    assert analyse["meta"]["taille_min_groupe"] == 5
    assert len(analyse["groupes"]) >= 3


def test_tickets_incomplets_ne_font_pas_planter():
    """Tickets sans temps passé, sans application, voire sans date : l'analyse aboutit."""
    tickets = charger_demo()[:200]
    for t in tickets:
        t["heures"], t["application"], t["solution"] = 0.0, "Non renseigné", ""
    tickets[0]["cree"] = None
    analyse = pipeline.analyser(tickets, dossier_cache=CACHE)
    assert analyse["meta"]["nb_tickets_base"] == 199       # le ticket sans date est écarté
    assert analyse["meta"]["nb_tickets"] > 0
    assert any("sans temps passé" in a for a in analyse["meta"]["avertissements"])


def test_aucun_ticket():
    analyse = pipeline.analyser([], dossier_cache=CACHE)
    assert analyse["groupes"] == [] and analyse["meta"]["nb_tickets"] == 0


# ------------------------------------------------------------------ cache --------------
def test_cache_embeddings_evite_le_recalcul(tmp_path):
    textes = ["Batch de nuit en échec", "Export PDF vide", "Batch de nuit en échec"]
    X1, calcules1 = vecteurs.vectoriser(textes, tmp_path)
    X2, calcules2 = vecteurs.vectoriser(textes, tmp_path)
    assert calcules1 == 2                   # 2 textes distincts calculés (le 3e est une copie)
    assert calcules2 == 0                   # deuxième passage : tout vient du cache
    assert np.allclose(X1, X2)
    _, calcules3 = vecteurs.vectoriser(textes + ["Virement SEPA rejeté"], tmp_path)
    assert calcules3 == 1                   # seul le nouveau texte est calculé
