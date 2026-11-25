"""Tests de l'API, des outils du copilote et de la boucle d'agent.

Aucun vrai LLM n'est appelé : un « faux client » rejoue des réponses écrites à l'avance.
On vérifie ainsi la mécanique (outils appelés, plan créé, citations contrôlées) sans clé
ni connexion.
"""
import json
import os
from types import SimpleNamespace

import pytest

from conftest import DEMO


# ------------------------------------------------------------------ préparation --------
@pytest.fixture(scope="module")
def appli(tmp_path_factory):
    """Une application complète sur le jeu de démo, dans un dossier temporaire, SANS LLM.

    Les variables d'environnement sont fixées AVANT d'importer l'application : elles ont
    priorité sur le fichier .env, donc ces tests ne dépendent pas de la configuration locale.
    """
    if not DEMO.exists():
        pytest.skip("Jeu de démonstration introuvable")
    os.environ.update({"SOURCE": "demo", "DEMO_TICKETS": str(DEMO),
                       "DOSSIER_DONNEES": str(tmp_path_factory.mktemp("donnees")),
                       "AZURE_OPENAI_ENDPOINT": "", "AZURE_OPENAI_KEY": "", "LLM_BASE_URL": ""})
    from app import db, service
    db.initialiser(service.CONFIG["dossier_donnees"] / "tma.sqlite")
    service.executer_analyse(recharger_source=True)          # analyse directe, sans thread
    return SimpleNamespace(db=db, service=service)


@pytest.fixture(scope="module")
def client(appli):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)          # sans « with » : l'analyse de démarrage n'est pas relancée


def groupe_batch(appli):
    return next(g for g in appli.db.lire_groupes() if "batch" in " ".join(g["mots_cles"]))


# ------------------------------------------------------------------ faux LLM -----------
def appel_outil(nom, arguments, identifiant="appel_1"):
    return SimpleNamespace(id=identifiant, function=SimpleNamespace(name=nom, arguments=json.dumps(arguments)))


class FauxMessage:
    """Imite un message de réponse de l'API (contenu texte OU appels d'outils)."""
    def __init__(self, content=None, tool_calls=None):
        self.content, self.tool_calls = content, tool_calls

    def model_dump(self, exclude_none=True):
        message = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            message["tool_calls"] = [{"id": a.id, "type": "function",
                                      "function": {"name": a.function.name, "arguments": a.function.arguments}}
                                     for a in self.tool_calls]
        return message


class FauxClient:
    """Imite client.chat.completions.create : renvoie les réponses prévues, dans l'ordre."""
    def __init__(self, reponses):
        self.reponses, self.recus = list(reponses), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.creer))

    def creer(self, **demande):
        self.recus.append(demande)
        return SimpleNamespace(choices=[SimpleNamespace(message=self.reponses.pop(0))])


# ------------------------------------------------------------------ sans LLM -----------
def test_sans_llm_le_chat_explique_et_le_reste_fonctionne(client):
    reponse = client.post("/api/copilote", json={"historique": [{"role": "user", "content": "Bonjour"}]})
    assert reponse.status_code == 503
    assert "Copilote désactivé" in reponse.json()["detail"]
    # Tout le reste répond normalement.
    for route in ("etat", "tableau-de-bord", "problemes", "pics", "gain", "nouveaux-tickets", "synthese", "plans"):
        assert client.get("/api/" + route).status_code == 200, route
    assert client.get("/api/etat").json()["llm"]["actif"] is False


def test_page_nouveau_ticket(client):
    connu = client.post("/api/nouveau-ticket", json={"texte": "Le batch de nuit a planté avec ORA-01555"}).json()
    nouveau = client.post("/api/nouveau-ticket", json={"texte": "Demande de devis pour une nouvelle imprimante"}).json()
    assert connu["connu"] is True and len(connu["similaires"]) == 3
    assert nouveau["connu"] is False


def test_synthese_exportable_en_markdown(client):
    reponse = client.get("/api/synthese.md?semaine=9")
    assert reponse.status_code == 200
    assert reponse.text.startswith("# Synthèse hebdomadaire")
    assert "Pic anormal" in reponse.text


# ------------------------------------------------------------------ outils -------------
def test_outils_citent_des_tickets_existants(appli):
    from app.copilote import outils
    resultat = outils.top_recurrences(n=3)
    assert len(resultat["problemes"]) == 3
    for probleme in resultat["problemes"]:
        assert probleme["statut"] == "recurrent"
        assert appli.db.cles_existantes(probleme["tickets_sources"]) == set(probleme["tickets_sources"])
    assert 9 in [p["semaine"] for p in outils.pics()["pics"]]
    # Filtré sur une semaine sans pic, l'outil rappelle les pics du reste de la période.
    filtre = outils.pics(semaine=12)
    assert filtre["pics"] == [] and filtre["semaines_de_pic_sur_toute_la_periode"] == [9]


def test_outils_n_envoient_que_des_extraits(appli):
    from app.copilote import outils
    cle = groupe_batch(appli)["cles_representatives"][0]
    fiche = outils.detail_ticket(cle)
    assert len(fiche["resume"]) <= outils.LONGUEUR_EXTRAIT
    assert "description" not in fiche                     # jamais le ticket complet


def test_aucun_outil_n_ecrit_dans_jira():
    """Lecture seule : le client Jira ne contient aucune requête d'écriture."""
    from pathlib import Path
    import app.sources.jira as jira
    code = Path(jira.__file__).read_text(encoding="utf-8")
    for interdit in ("requests.post", "requests.put", "requests.delete", "requests.patch"):
        assert interdit not in code


def test_plan_propose_avec_gain_calcule_par_le_moteur(appli):
    from app.copilote import outils
    batch = groupe_batch(appli)
    resultat = outils.proposer_plan_action(batch["id"], "Traiter la cause du batch",
                                           ["Redimensionner l'undo tablespace"],
                                           [batch["cles_representatives"][0], "TMA-999999"])
    plan = appli.db.lire_plan(resultat["plan_id"])
    assert plan["statut"] == "propose" and plan["origine"] == "copilote"
    assert plan["gain"] == batch["gain"]                  # chiffre du moteur, pas du LLM
    assert resultat["cles_refusees"] == ["TMA-999999"]    # clé inventée : refusée
    assert "TMA-999999" not in plan["tickets"]


def test_pas_de_plan_pour_un_groupe_a_verifier(appli):
    from app.copilote import outils
    recopie = next(g for g in appli.db.lire_groupes() if g["statut"] == "a_verifier")
    assert "erreur" in outils.proposer_plan_action(recopie["id"], "Plan", ["Action"])


def test_seul_l_humain_change_le_statut(client, appli):
    from app.copilote import outils
    assert not any("valid" in nom or "rejet" in nom or "statut" in nom for nom in outils.FONCTIONS)
    identifiant = client.post("/api/plans", json={"probleme_id": groupe_batch(appli)["id"], "titre": "Plan test",
                                                  "actions": ["Vérifier l'espace"]}).json()["id"]
    assert client.patch(f"/api/plans/{identifiant}", json={"statut": "valide"}).json()["statut"] == "valide"
    assert client.patch(f"/api/plans/{identifiant}", json={"statut": "n_importe_quoi"}).status_code == 422


# ------------------------------------------------------------------ boucle d'agent -----
def test_boucle_agent_appelle_les_outils_et_cree_un_plan(appli):
    from app.copilote import llm
    batch = groupe_batch(appli)
    vraie_cle = batch["cles_representatives"][0]
    faux = FauxClient([
        FauxMessage(tool_calls=[appel_outil("top_recurrences", {"n": 3})]),
        FauxMessage(tool_calls=[appel_outil("proposer_plan_action", {
            "probleme_id": batch["id"], "titre": "Traiter la cause racine du batch",
            "actions": ["Redimensionner l'undo tablespace", "Ajouter une alerte d'espace"],
            "tickets_sources": [vraie_cle]})]),
        FauxMessage(content=f"Priorité : le batch nocturne ({vraie_cle}). Voir aussi TMA-999999."),
    ])
    resultat = llm.repondre([{"role": "user", "content": "Que traiter en priorité ?"}],
                            {**appli.service.CONFIG, "llm_max_tours": 6}, client=faux, modele="faux")

    assert [o["outil"] for o in resultat["outils"]] == ["top_recurrences", "proposer_plan_action"]
    assert resultat["tickets_cites"] == [vraie_cle]
    assert resultat["cles_inconnues"] == ["TMA-999999"]           # citation inventée : signalée
    assert appli.db.lire_plan(resultat["plans_crees"][0])["statut"] == "propose"
    # Le prompt système rappelle que le texte des tickets est une donnée.
    assert "DONNÉE" in faux.recus[0]["messages"][0]["content"]
    # Le résultat d'un outil revient au LLM avec le rôle « tool ».
    assert faux.recus[1]["messages"][-1]["role"] == "tool"


def test_boucle_agent_limitee_en_nombre_de_tours(appli):
    from app.copilote import llm
    faux = FauxClient([FauxMessage(tool_calls=[appel_outil("pics", {})]) for _ in range(10)])
    resultat = llm.repondre([{"role": "user", "content": "?"}], {**appli.service.CONFIG, "llm_max_tours": 3},
                            client=faux, modele="faux")
    assert len(resultat["outils"]) == 3
    assert "nombre raisonnable" in resultat["reponse"]


# ------------------------------------------------------------------ nommage ------------
def test_nom_llm_accepte_s_il_est_fidele_refuse_s_il_invente(appli):
    from app.copilote import nommage
    batch = groupe_batch(appli)
    matiere = nommage.matiere_du_groupe(batch)
    assert nommage.est_fidele("Échec du batch nocturne avec l'erreur ORA-01555",
                              "Le traitement de nuit s'arrête avec l'erreur ORA-01555. Il est relancé à la main.", matiere)
    # ORA-00600 ne figure dans aucun ticket du groupe : détail inventé, réponse refusée.
    assert not nommage.est_fidele("Échec du batch nocturne avec l'erreur ORA-00600",
                                  "Le traitement de nuit s'arrête avec l'erreur ORA-00600 depuis 3 jours.", matiere)


def test_nommage_par_llm_renomme_seulement_les_reponses_fideles(appli):
    from app.copilote import nommage
    groupes = appli.db.lire_groupes()
    reponses = [FauxMessage(content=json.dumps({
        "nom": "Problème inventé numéro 42 sur le serveur X99",
        "description": "Description contenant un détail inventé, le serveur X99, absent des tickets."}))
        for _ in groupes]
    # Première réponse fidèle (aucun code ni nombre), les suivantes inventent « 42 » et « X99 ».
    reponses[0] = FauxMessage(content='Voici : {"nom": "Arrêt du traitement nocturne avec erreur de snapshot", '
                                      '"description": "Le traitement de nuit s\'arrête en erreur et doit être relancé à la main."}')
    rediges = nommage.nommer_les_groupes(appli.service.CONFIG, client=FauxClient(reponses), modele="faux")
    apres = appli.db.lire_groupes()
    assert rediges == 1
    assert apres[0]["origine_nom"] == "llm" and apres[0]["nom"].startswith("Arrêt du traitement")
    assert all(g["origine_nom"] == "moteur" for g in apres[1:])
    assert all("X99" not in g["nom"] for g in apres)


# ------------------------------------------------------------------ sources ------------
def test_conversion_d_un_ticket_jira_reel():
    """Un ticket Jira Cloud : description au format ADF, champs manquants."""
    from app.sources.format import depuis_jira
    issue = {"key": "ABC-7", "fields": {
        "summary": "Erreur 500 sur l&#39;accueil",
        "description": {"type": "doc", "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "La page ne répond plus."}]}]},
        "created": "2026-03-02T10:15:00.000+0100", "timespent": None, "components": [],
        "project": {"name": "Portail"}, "comment": {"comments": []}}}
    ticket = depuis_jira(issue)
    assert ticket["titre"] == "Erreur 500 sur l'accueil"
    assert ticket["description"] == "La page ne répond plus."
    assert ticket["heures"] == 0.0 and ticket["application"] == "Portail"
    assert ticket["cree"].year == 2026 and ticket["solution"] == ""


def test_lecture_d_un_fichier_csv(tmp_path):
    from app.sources import fichier
    chemin = tmp_path / "tickets.csv"
    chemin.write_text('"identifiant","date_creation","titre","description","application"\n'
                      '"X-1","2026-04-02T09:23:00.000Z","Paiement en erreur","Écran figé","Paiements"\n',
                      encoding="utf-8")
    tickets = fichier.lire_tickets(chemin)
    assert tickets[0]["cle"] == "X-1" and tickets[0]["application"] == "Paiements"
    assert tickets[0]["cree"].month == 4 and tickets[0]["heures"] == 0.0
