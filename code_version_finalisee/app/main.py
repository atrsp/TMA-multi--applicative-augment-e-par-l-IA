"""L'application web : routes de l'API et pages statiques.

Lancer :  uvicorn app.main:app          puis ouvrir http://localhost:8000

Chaque route est courte : elle vérifie la demande, appelle une fonction de lectures.py
(ou db.py) et renvoie le résultat en JSON. Aucune route n'écrit dans Jira.
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, lectures, service
from .config import RACINE, llm_configure
from .copilote import llm
from .moteur.pipeline import REGLAGES_PAR_DEFAUT


@asynccontextmanager
async def cycle_de_vie(application):
    """Au démarrage : préparer la base et lancer une première analyse en arrière-plan."""
    service.demarrer()
    yield


app = FastAPI(title="Copilote RUN", lifespan=cycle_de_vie)


# ------------------------------------------------------------------ formes des demandes
class DemandeAnalyse(BaseModel):
    recharger_source: bool = True


class Reglages(BaseModel):
    """Les seuils modifiables. Les bornes (ge = minimum, le = maximum) évitent les valeurs absurdes."""
    semaine_ref: Optional[str] = None
    fenetre_semaines: Optional[int] = Field(None, ge=0, le=520)
    taille_min_groupe: Optional[int] = Field(None, ge=0, le=500)
    semaines_min: Optional[int] = Field(None, ge=1, le=52)
    alpha: Optional[float] = Field(None, gt=0, le=0.5)
    pic_min: Optional[int] = Field(None, ge=1, le=1000)
    historique_pics: Optional[int] = Field(None, ge=1, le=52)
    seuil_nouveaute: Optional[float] = Field(None, ge=0, le=1)
    cohesion_min: Optional[float] = Field(None, ge=0, le=1)
    taux_pessimiste: Optional[float] = Field(None, ge=0, le=1)
    taux_median: Optional[float] = Field(None, ge=0, le=1)
    taux_optimiste: Optional[float] = Field(None, ge=0, le=1)
    nommage_llm: Optional[bool] = None


class TexteTicket(BaseModel):
    texte: str = Field(min_length=3, max_length=5000)


class NouveauPlan(BaseModel):
    probleme_id: int
    titre: str = Field(min_length=3, max_length=200)
    actions: list[str] = Field(min_length=1, max_length=8)


class ModificationPlan(BaseModel):
    statut: Optional[str] = None
    titre: Optional[str] = Field(None, min_length=3, max_length=200)
    actions: Optional[list[str]] = Field(None, min_length=1, max_length=8)
    commentaire: Optional[str] = Field(None, max_length=1000)


class Message(BaseModel):
    role: str
    content: str


class Conversation(BaseModel):
    historique: list[Message] = Field(min_length=1)


# ------------------------------------------------------------------ état et analyse ----
@app.get("/api/etat")
def lire_etat():
    return lectures.etat()


@app.post("/api/analyse")
def relancer_analyse(demande: DemandeAnalyse):
    lancee = service.lancer_analyse(demande.recharger_source)
    return {"lancee": lancee, "message": "Analyse lancée." if lancee else "Une analyse est déjà en cours."}


@app.get("/api/reglages")
def lire_reglages():
    return {"valeurs": service.reglages(), "par_defaut": REGLAGES_PAR_DEFAUT}


@app.put("/api/reglages")
def modifier_reglages(nouveaux: Reglages):
    """Enregistre les seuils. Ils s'appliquent à la prochaine analyse."""
    changes = {nom: valeur for nom, valeur in nouveaux.model_dump().items() if valeur is not None}
    db.ecrire_reglages(changes)
    return {"valeurs": service.reglages()}


# ------------------------------------------------------------------ pages d'analyse ----
@app.get("/api/tableau-de-bord")
def tableau_de_bord():
    return lectures.tableau_de_bord()


@app.get("/api/problemes")
def liste_problemes():
    return lectures.problemes()


@app.get("/api/problemes/{identifiant}")
def fiche_probleme(identifiant: int):
    fiche = lectures.probleme(identifiant)
    if fiche is None:
        raise HTTPException(404, "Problème introuvable (les numéros changent après une nouvelle analyse).")
    return fiche


@app.get("/api/pics")
def liste_pics():
    return lectures.pics()


@app.get("/api/gain")
def gain_estime():
    return lectures.gain()


@app.get("/api/nouveaux-tickets")
def derniers_tickets():
    return {"tickets": lectures.nouveaux_tickets(12)}


@app.post("/api/nouveau-ticket")
def classer_texte(demande: TexteTicket):
    resultat = lectures.analyser_texte(demande.texte)
    if not resultat["pret"]:
        raise HTTPException(503, "L'analyse n'est pas encore terminée. Réessayez dans un instant.")
    return resultat


@app.get("/api/tickets/{cle}")
def detail_ticket(cle: str):
    ticket = lectures.ticket(cle)
    if ticket is None:
        raise HTTPException(404, "Ticket introuvable.")
    return ticket


@app.get("/api/synthese")
def synthese(semaine: Optional[int] = None):
    resultat = lectures.synthese_hebdo(semaine)
    if resultat is None:
        raise HTTPException(404, "Aucune synthèse pour cette semaine (hors de la période analysée).")
    return resultat


@app.get("/api/synthese.md", response_class=PlainTextResponse)
def synthese_markdown(semaine: Optional[int] = None):
    """Le même contenu, en fichier Markdown téléchargeable."""
    resultat = lectures.synthese_hebdo(semaine)
    if resultat is None:
        raise HTTPException(404, "Aucune synthèse pour cette semaine.")
    nom = f"synthese_S{resultat['semaine']['numero']}_{resultat['semaine']['lundi']}.md"
    return PlainTextResponse(resultat["markdown"], media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nom}"'})


# ------------------------------------------------------------------ plans d'action -----
@app.get("/api/plans")
def liste_plans():
    return {"plans": lectures.plans()}


@app.post("/api/plans")
def creer_plan(demande: NouveauPlan):
    """Plan écrit à la main par l'équipe. Il naît « proposé », comme ceux du copilote."""
    plan, _ = lectures.preparer_plan(demande.probleme_id, demande.titre, demande.actions, [], "equipe")
    if plan is None:
        raise HTTPException(404, "Problème introuvable.")
    return db.creer_plan(plan)


@app.patch("/api/plans/{identifiant}")
def modifier_plan(identifiant: int, demande: ModificationPlan):
    """Valider, modifier ou rejeter un plan : une action réservée à l'humain.
    (Le copilote n'a aucun outil qui appelle cette route.)"""
    if db.lire_plan(identifiant) is None:
        raise HTTPException(404, "Plan introuvable.")
    if demande.statut is not None and demande.statut not in db.STATUTS_PLAN:
        raise HTTPException(422, f"Statut inconnu. Valeurs possibles : {', '.join(db.STATUTS_PLAN)}.")
    return db.modifier_plan(identifiant, demande.model_dump())


# ------------------------------------------------------------------ copilote -----------
@app.post("/api/copilote")
def copilote(conversation: Conversation):
    """Pose une question au copilote. Sans LLM, renvoie une explication claire (code 503)."""
    if not llm_configure(service.CONFIG):
        raise HTTPException(503, llm.MESSAGE_DESACTIVE)
    if lectures.meta() is None:
        raise HTTPException(503, "L'analyse n'est pas encore terminée. Réessayez dans un instant.")
    try:
        return llm.repondre([m.model_dump() for m in conversation.historique], service.CONFIG)
    except llm.LLMIndisponible as erreur:
        raise HTTPException(503, str(erreur))


# ------------------------------------------------------------------ pages statiques ----
@app.get("/")
def page_principale():
    return FileResponse(RACINE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=RACINE / "static"), name="static")
