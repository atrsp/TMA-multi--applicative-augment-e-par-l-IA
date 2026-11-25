"""Persistance dans SQLite : tickets, résultats d'analyse, plans d'action, réglages.

SQLite est une base de données contenue dans un seul fichier (data/tma.sqlite) : rien à
installer. Chaque fonction ouvre une connexion, fait UNE chose, et referme.

Les listes et dictionnaires Python sont enregistrés en texte JSON dans une colonne
(json.dumps pour écrire, json.loads pour relire).
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

CHEMIN = None       # chemin du fichier de base, fixé par initialiser()

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    cle TEXT PRIMARY KEY, titre TEXT, titre_propre TEXT, description TEXT, application TEXT,
    type TEXT, priorite TEXT, statut TEXT, cree TEXT, heures REAL, solution TEXT);
CREATE TABLE IF NOT EXISTS groupes (
    id INTEGER PRIMARY KEY, statut TEXT, nom TEXT, description TEXT, origine_nom TEXT,
    donnees TEXT);                       -- donnees = le reste de la fiche, en JSON
CREATE TABLE IF NOT EXISTS affectations (
    cle TEXT PRIMARY KEY, semaine INTEGER, groupe INTEGER, meilleur_groupe INTEGER, score REAL);
CREATE TABLE IF NOT EXISTS pics (
    groupe INTEGER, semaine INTEGER, observe INTEGER, attendu REAL, p_valeur REAL);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cree TEXT, maj TEXT, statut TEXT, origine TEXT,
    titre TEXT, probleme_nom TEXT, semaine_ref TEXT, actions TEXT, tickets TEXT,
    nb_tickets INTEGER, heures_total REAL, gain TEXT, commentaire TEXT);
CREATE TABLE IF NOT EXISTS reglages (nom TEXT PRIMARY KEY, valeur TEXT);
CREATE TABLE IF NOT EXISTS memo (nom TEXT PRIMARY KEY, valeur TEXT);
CREATE TABLE IF NOT EXISTS noms_llm (empreinte TEXT PRIMARY KEY, nom TEXT, description TEXT);
"""

STATUTS_PLAN = ("propose", "valide", "rejete")


def initialiser(chemin):
    """Crée le fichier de base et ses tables s'ils n'existent pas encore."""
    global CHEMIN
    CHEMIN = Path(chemin)
    CHEMIN.parent.mkdir(parents=True, exist_ok=True)
    with connexion() as c:
        c.executescript(SCHEMA)


@contextmanager
def connexion():
    """Ouvre une connexion, valide les écritures à la sortie du bloc `with`, puis referme."""
    c = sqlite3.connect(CHEMIN, timeout=30)
    c.row_factory = sqlite3.Row          # permet d'écrire ligne["titre"] au lieu de ligne[1]
    try:
        yield c
        c.commit()
    finally:
        c.close()


def lignes(requete, parametres=()):
    """Exécute une requête de lecture et renvoie une liste de dictionnaires."""
    with connexion() as c:
        return [dict(ligne) for ligne in c.execute(requete, parametres).fetchall()]


# ------------------------------------------------------------------ tickets ------------
def remplacer_tickets(tickets):
    """Remplace tous les tickets enregistrés par ceux qui viennent d'être lus à la source."""
    with connexion() as c:
        c.execute("DELETE FROM tickets")
        c.executemany(
            "INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(t["cle"], t["titre"], t.get("titre_propre", t["titre"]), t["description"],
              t["application"], t["type"], t["priorite"], t["statut"],
              t["cree"].isoformat() if t["cree"] else None, t["heures"], t["solution"])
             for t in tickets if t["cle"]])


def lire_tous_les_tickets():
    """Relit les tickets enregistrés, au format interne (la date redevient un datetime)."""
    tickets = lignes("SELECT * FROM tickets")
    for t in tickets:
        t["cree"] = datetime.fromisoformat(t["cree"]) if t["cree"] else None
    return tickets


def lire_ticket(cle):
    """Un ticket et son rattachement (groupe, semaine, ressemblance), ou None s'il n'existe pas."""
    trouve = lignes("""SELECT t.*, a.semaine, a.groupe, a.meilleur_groupe, a.score
                       FROM tickets t LEFT JOIN affectations a ON a.cle = t.cle
                       WHERE t.cle = ? COLLATE NOCASE""", (cle.strip(),))
    return trouve[0] if trouve else None


def cles_existantes(cles):
    """Parmi une liste de clés, celles qui existent vraiment dans la base."""
    if not cles:
        return set()
    marques = ",".join("?" * len(cles))
    return {l["cle"] for l in lignes(f"SELECT cle FROM tickets WHERE cle IN ({marques})", list(cles))}


def prefixes_des_cles():
    """Les préfixes de clés présents dans la base (ex. {"TMA"}), pour reconnaître une citation."""
    return {l["cle"].rsplit("-", 1)[0] for l in lignes("SELECT cle FROM tickets") if "-" in l["cle"]}


def tickets_analyses(condition="", parametres=()):
    """Les tickets de la période analysée, avec leur groupe. `condition` filtre (clause SQL)."""
    return lignes(f"""SELECT t.cle, t.titre_propre AS titre, t.application, t.type, t.priorite,
                             t.cree, t.heures, a.semaine, a.groupe, a.meilleur_groupe, a.score
                      FROM affectations a JOIN tickets t ON t.cle = a.cle
                      {condition} ORDER BY t.cree DESC""", parametres)


# ------------------------------------------------------------------ analyse ------------
def enregistrer_analyse(resultat):
    """Remplace les résultats de l'analyse précédente par les nouveaux."""
    colonnes = ("id", "statut", "nom", "description", "origine_nom")
    with connexion() as c:
        for table in ("groupes", "affectations", "pics"):
            c.execute(f"DELETE FROM {table}")
        for g in resultat["groupes"]:
            reste = {k: v for k, v in g.items() if k not in colonnes}
            c.execute("INSERT INTO groupes VALUES (?,?,?,?,?,?)",
                      (*[g[k] for k in colonnes], json.dumps(reste, ensure_ascii=False)))
        c.executemany("INSERT OR REPLACE INTO affectations VALUES (?,?,?,?,?)",
                      [(a["cle"], a["semaine"], a["groupe"], a["meilleur_groupe"], a["score"])
                       for a in resultat["affectations"]])
        c.executemany("INSERT INTO pics VALUES (?,?,?,?,?)",
                      [(p["groupe"], p["semaine"], p["observe"], p["attendu"], p["p_valeur"])
                       for p in resultat["pics"]])
    meta = {**resultat["meta"], "date_analyse": datetime.now().isoformat(timespec="seconds")}
    ecrire_memo("meta", meta)


def lire_groupes():
    """Toutes les fiches de groupe, de la plus coûteuse en heures à la moins coûteuse."""
    return [{**{k: v for k, v in g.items() if k != "donnees"}, **json.loads(g["donnees"])}
            for g in lignes("SELECT * FROM groupes ORDER BY id")]


def lire_groupe(identifiant):
    """La fiche d'un groupe, ou None s'il n'existe pas."""
    return next((g for g in lire_groupes() if g["id"] == identifiant), None)


def renommer_groupe(identifiant, nom, description, origine):
    """Change le nom et la description d'un groupe (utilisé après la rédaction par le LLM)."""
    with connexion() as c:
        c.execute("UPDATE groupes SET nom = ?, description = ?, origine_nom = ? WHERE id = ?",
                  (nom, description, origine, identifiant))


def lire_pics():
    return lignes("SELECT * FROM pics ORDER BY semaine DESC, p_valeur ASC")


# ------------------------------------------------------------------ mémo et réglages ---
def ecrire_memo(nom, valeur):
    """Enregistre une petite information nommée (ex. la période de la dernière analyse)."""
    with connexion() as c:
        c.execute("INSERT OR REPLACE INTO memo VALUES (?, ?)",
                  (nom, json.dumps(valeur, ensure_ascii=False, default=str)))


def lire_memo(nom, defaut=None):
    trouve = lignes("SELECT valeur FROM memo WHERE nom = ?", (nom,))
    return json.loads(trouve[0]["valeur"]) if trouve else defaut


def lire_reglages(par_defaut):
    """Les réglages enregistrés, complétés par les valeurs par défaut."""
    enregistres = {l["nom"]: json.loads(l["valeur"]) for l in lignes("SELECT * FROM reglages")}
    return {**par_defaut, **{k: v for k, v in enregistres.items() if k in par_defaut}}


def ecrire_reglages(reglages):
    with connexion() as c:
        c.executemany("INSERT OR REPLACE INTO reglages VALUES (?, ?)",
                      [(nom, json.dumps(valeur)) for nom, valeur in reglages.items()])


# ------------------------------------------------------------------ noms rédigés -------
def lire_nom_llm(empreinte):
    trouve = lignes("SELECT nom, description FROM noms_llm WHERE empreinte = ?", (empreinte,))
    return trouve[0] if trouve else None


def ecrire_nom_llm(empreinte, nom, description):
    with connexion() as c:
        c.execute("INSERT OR REPLACE INTO noms_llm VALUES (?,?,?)", (empreinte, nom, description))


# ------------------------------------------------------------------ plans d'action -----
def _plan_lisible(plan):
    """Redonne leur forme de liste / dictionnaire aux colonnes enregistrées en JSON."""
    for colonne in ("actions", "tickets", "gain"):
        plan[colonne] = json.loads(plan[colonne]) if plan[colonne] else None
    return plan


def creer_plan(plan):
    """Enregistre un nouveau plan, TOUJOURS au statut « proposé ». Renvoie le plan créé."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    with connexion() as c:
        curseur = c.execute(
            """INSERT INTO plans (cree, maj, statut, origine, titre, probleme_nom, semaine_ref,
                                  actions, tickets, nb_tickets, heures_total, gain, commentaire)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (maintenant, maintenant, "propose", plan["origine"], plan["titre"], plan["probleme_nom"],
             plan["semaine_ref"], json.dumps(plan["actions"], ensure_ascii=False),
             json.dumps(plan["tickets"]), plan["nb_tickets"], plan["heures_total"],
             json.dumps(plan["gain"]), ""))
        identifiant = curseur.lastrowid
    return lire_plan(identifiant)


def lire_plans():
    return [_plan_lisible(p) for p in lignes("SELECT * FROM plans ORDER BY id DESC")]


def lire_plan(identifiant):
    trouve = lignes("SELECT * FROM plans WHERE id = ?", (identifiant,))
    return _plan_lisible(trouve[0]) if trouve else None


def modifier_plan(identifiant, changements):
    """Modifie un plan. `changements` peut contenir statut, titre, actions, commentaire."""
    champs, valeurs = ["maj = ?"], [datetime.now().isoformat(timespec="seconds")]
    for nom in ("statut", "titre", "commentaire"):
        if changements.get(nom) is not None:
            champs.append(f"{nom} = ?")
            valeurs.append(changements[nom])
    if changements.get("actions") is not None:
        champs.append("actions = ?")
        valeurs.append(json.dumps(changements["actions"], ensure_ascii=False))
    with connexion() as c:
        c.execute(f"UPDATE plans SET {', '.join(champs)} WHERE id = ?", (*valeurs, identifiant))
    return lire_plan(identifiant)
