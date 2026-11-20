# """Couche d'acces aux donnees.

# Adapter COLUMN_MAP pour le fichier normalise. Le schema interne reprend les
# champs du cahier des charges et les colonnes produites par l'analyse.
# """

# from __future__ import annotations

# import re
# import random
# import unicodedata
# from datetime import date, timedelta
# from pathlib import Path
# import os

# import pandas as pd

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# DATA_PATH = Path(os.getenv("TICKETS_CSV_PATH", str(PROJECT_ROOT / "data" / "tickets.csv")))
# if not DATA_PATH.is_absolute():
#     DATA_PATH = PROJECT_ROOT / DATA_PATH

# # nom interne -> nom de colonne du fichier reel
# COLUMN_MAP = {
#     "id": "id",
#     "date_ouverture": "date_ouverture",
#     "application": "application",
#     "type": "type",
#     "categorie": "categorie",
#     "priorite": "priorite",
#     "description": "description",
#     "resolution": "resolution",
#     "commentaires": "commentaires",
#     "statut": "statut",
#     "temps_passe_h": "temps_passe_h",
#     "famille": "famille",
#     "cause_racine": "cause_racine",
# }

# REQUIRED = [
#     "id", "date_ouverture", "type", "famille", "cause_racine", "temps_passe_h"
# ]

# _COLUMN_ALIASES = {
#     "date_ouverture": ("date_d_ouverture", "created_at", "date_creation", "date"),
#     "type": ("ticket_type", "type_ticket"),
#     "categorie": ("category",),
#     "priorite": ("priority", "urgence"),
#     "resolution": ("solution",),
#     "commentaires": ("comments",),
#     "statut": ("status", "etat"),
#     "temps_passe_h": ("time_spent_hours", "hours_spent", "temps_passe", "charge_h"),
#     "famille": ("family", "family_name"),
#     "cause_racine": ("root_cause", "cause"),
# }


# def _normalize_header(value: str) -> str:
#     ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
#     return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


# def _fake_tickets(n: int = 250, seed: int = 42) -> pd.DataFrame:
#     """Jeu de donnees fictif reproductible pour le developpement local."""
#     rng = random.Random(seed)
#     families = {
#         "export_pdf_timeout": ("Gestion Contrats", "incident", "Edition", "Timeout du service de rendu PDF", "L'export PDF du contrat echoue", "Relance du service de rendu", 18, 3),
#         "droits_acces": ("Portail Client", "support", "Habilitations", "Profil utilisateur mal configure", "Impossible d'acceder a un ecran", "Ajustement du profil", 25, 1.5),
#         "lenteur_batch_nuit": ("Facturation", "incident", "Performance", "Saturation de la base en fin de nuit", "Le batch de facturation depasse sa fenetre", "Purge et relance du batch", 10, 9),
#         "validation_formulaire": ("Portail Client", "incident", "Saisie", "Validation cote client defaillante", "Le formulaire refuse une saisie valide", "Contournement de saisie", 20, 2.5),
#         "reinit_mot_de_passe": ("Portail Client", "support", "Habilitations", "Expiration de compte non notifiee", "Compte verrouille apres expiration", "Reinitialisation du compte", 22, 0.5),
#         "flux_partenaire": ("Reporting", "incident", "Integration", "Changement de format cote partenaire", "Le fichier partenaire est rejete", "Adaptation du mapping", 5, 12),
#     }
#     names = list(families)
#     weights = [family[6] for family in families.values()]
#     today = date.today()
#     rows = []
#     for index in range(n):
#         family_name = rng.choices(names, weights=weights)[0]
#         app, ticket_type, category, cause, description, resolution, _, mean = families[family_name]
#         rows.append({
#             "id": f"TMA-{1000 + index}",
#             "date_ouverture": today - timedelta(days=rng.randint(0, 100)),
#             "application": app,
#             "type": ticket_type,
#             "categorie": category,
#             "priorite": rng.choice(["basse", "moyenne", "haute"]),
#             "description": f"{description} (cas {index})",
#             "resolution": resolution,
#             "commentaires": "",
#             "statut": rng.choice(["resolu", "resolu", "resolu", "en cours"]),
#             "temps_passe_h": round(max(0.25, rng.gauss(mean, mean / 2)), 2),
#             "famille": family_name,
#             "cause_racine": cause,
#         })
#     return pd.DataFrame(rows)


# def load_tickets(csv_path: str | Path | None = None) -> pd.DataFrame:
#     """Retourne les tickets analyses avec les noms de colonnes internes."""
#     path = Path(csv_path) if csv_path is not None else DATA_PATH
#     if path.exists():
#         try:
#             df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
#         except pd.errors.EmptyDataError:
#             df = pd.DataFrame()
#     else:
#         df = _fake_tickets()

#     header_map = {_normalize_header(str(column)): column for column in df.columns}
#     rename_map = {}
#     for internal, external in COLUMN_MAP.items():
#         candidates = (external, *_COLUMN_ALIASES.get(internal, ()))
#         source = next(
#             (header_map[_normalize_header(candidate)] for candidate in candidates
#              if _normalize_header(candidate) in header_map),
#             None,
#         )
#         if source is not None:
#             rename_map[source] = internal
#     df = df.rename(columns=rename_map)

#     missing = [column for column in REQUIRED if column not in df.columns]
#     if missing:
#         raise ValueError(
#             f"Colonnes manquantes dans {path.name} : {missing} (voir COLUMN_MAP)"
#         )

#     for column in COLUMN_MAP:
#         if column not in df.columns:
#             df[column] = ""
#     df["date_ouverture"] = pd.to_datetime(df["date_ouverture"])
#     df["temps_passe_h"] = pd.to_numeric(df["temps_passe_h"], errors="raise")
#     return df

"""Couche d'acces aux donnees (Support du format Jira JSON imbriqué et ultra-sécurisé)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = Path(os.getenv("TICKETS_JSON_PATH", str(PROJECT_ROOT.parent / "tma-data" / "data" / "tickets.json"))).resolve()

REQUIRED = [
    "id", "date_ouverture", "type", "application", "temps_passe_h"
]

def load_tickets(json_path: str | Path | None = None) -> pd.DataFrame:
    """Charge les tickets depuis un fichier JSON au format Jira (liste ou dict avec issues) et retourne un DataFrame propre."""
    path = Path(json_path) if json_path is not None else DATA_PATH
    
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, Exception):
            raw_data = []
    else:
        raw_data = []

    # Gérer le cas d'un export Jira standard (dictionnaire avec une clé "issues" ou "tickets")
    if isinstance(raw_data, dict):
        raw_data = raw_data.get("issues") or raw_data.get("tickets") or []

    # Si ce n'est toujours pas une liste, on force à vide
    if not isinstance(raw_data, list):
        raw_data = []

    rows = []
    for item in raw_data:
        # Sécurité : si l'élément n'est pas un dictionnaire, on l'ignore
        if not isinstance(item, dict):
            continue

        # Extraction sécurisée des champs Jira imbriqués
        key = item.get("key", "") or ""
        fields = item.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        
        date_ouverture = fields.get("created", "") or ""
        
        issuetype_obj = fields.get("issuetype")
        ticket_type = "Inconnu"
        if isinstance(issuetype_obj, dict):
            ticket_type = issuetype_obj.get("name", "Inconnu") or "Inconnu"
        
        components = fields.get("components")
        application = "Général"
        if isinstance(components, list) and len(components) > 0:
            comp0 = components[0]
            if isinstance(comp0, dict):
                application = comp0.get("name", "Général") or "Général"
        
        priority_obj = fields.get("priority")
        priorite = "Moyenne"
        if isinstance(priority_obj, dict):
            priorite = priority_obj.get("name", "Moyenne") or "Moyenne"
        
        status_obj = fields.get("status")
        statut = ""
        if isinstance(status_obj, dict):
            statut = status_obj.get("name", "") or ""
        
        resolution_obj = fields.get("resolution")
        resolution = ""
        if isinstance(resolution_obj, dict):
            resolution = resolution_obj.get("name", "") or ""
        
        # Gestion ultra-robuste du temps passé (timespent en secondes)
        timespent_sec = fields.get("timespent")
        try:
            temps_passe_h = round(float(timespent_sec) / 3600.0, 2) if timespent_sec is not None else 0.0
        except (ValueError, TypeError):
            temps_passe_h = 0.0
            
        description = fields.get("description", "") or ""
        summary = fields.get("summary", "") or ""
        
        comment_obj = fields.get("comment")
        comments_list = []
        if isinstance(comment_obj, dict):
            c_list = comment_obj.get("comments")
            if isinstance(c_list, list):
                comments_list = c_list
        
        commentaires_parts = []
        for c in comments_list:
            if isinstance(c, dict):
                body = c.get("body")
                if body:
                    commentaires_parts.append(str(body))
        commentaires = " | ".join(commentaires_parts)

        rows.append({
            "id": str(key),
            "date_ouverture": date_ouverture,
            "application": str(application),
            "type": str(ticket_type),
            "categorie": str(summary),
            "priorite": str(priorite),
            "description": str(description),
            "resolution": str(resolution),
            "commentaires": commentaires,
            "statut": str(statut),
            "temps_passe_h": temps_passe_h,
            "famille": str(application),
            "cause_racine": str(resolution) if resolution else "Non déterminée",
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(columns=["id", "date_ouverture", "type", "application", "temps_passe_h", "famille", "cause_racine"])

    # Conversion propre des types
    df["date_ouverture"] = pd.to_datetime(df["date_ouverture"], errors="coerce")
    df["temps_passe_h"] = pd.to_numeric(df["temps_passe_h"], errors="coerce").fillna(0.0)
    
    return df

import pandas as pd

def calculer_kpis_tma(df: pd.DataFrame) -> dict:
    """Calcule les 4 KPI principaux avec comparaison N vs N-1 (30 derniers jours vs 30 jours d'avant)."""
    if df.empty:
        return {}

    # S'assurer que les dates sont au format datetime
    df["date_ouverture"] = pd.to_datetime(df["date_ouverture"], errors="coerce")
    
    # Définition de la date de référence (la plus récente du dataset ou du jour)
    date_ref = df["date_ouverture"].max()
    if pd.isna(date_ref):
        date_ref = pd.Timestamp.now()

    # Périodes : P1 (30 derniers jours) et P2 (30 jours précédents)
    p1_start = date_ref - pd.Timedelta(days=30)
    p2_start = date_ref - pd.Timedelta(days=60)

    # Filtrage des DataFrames
    df_p1 = df[(df["date_ouverture"] > p1_start) & (df["date_ouverture"] <= date_ref)]
    df_p2 = df[(df["date_ouverture"] > p2_start) & (df["date_ouverture"] <= p1_start)]

    # Helper pour le calcul du pourcentage de variation
    def calc_evolution(val_p1, val_p2):
        if val_p2 == 0:
            return 0.0 if val_p1 == 0 else 100.0
        return round(((val_p1 - val_p2) / val_p2) * 100, 1)

    # --- KPI 1 : Tickets Reçus ---
    recus_p1 = len(df_p1)
    recus_p2 = len(df_p2)
    ev_recus = calc_evolution(recus_p1, recus_p2)

    # --- KPI 2 : Tickets Résolus ---
    # On filtre les tickets ayant un statut résolu/fermé ou une date de résolution
    resolved_mask_p1 = df_p1["statut"].str.casefold().isin(["résolu", "resolu", "fermé", "ferme", "closed", "resolved"])
    resolved_mask_p2 = df_p2["statut"].str.casefold().isin(["résolu", "resolu", "fermé", "ferme", "closed", "resolved"])
    
    resolus_p1 = int(resolved_mask_p1.sum())
    resolus_p2 = int(resolved_mask_p2.sum())
    ev_resolus = calc_evolution(resolus_p1, resolus_p2)

    # --- KPI 3 : MTTR (Temps Moyen de Résolution en heures) ---
    # (Basé sur le temps passé ou une différence de date si tu l'as, ici on utilise la moyenne de 'temps_passe_h' des résolus)
    mttr_p1 = round(df_p1[resolved_mask_p1]["temps_passe_h"].mean(), 1) if resolus_p1 > 0 else 0.0
    mttr_p2 = round(df_p2[resolved_mask_p2]["temps_passe_h"].mean(), 1) if resolus_p2 > 0 else 0.0
    ev_mttr = calc_evolution(mttr_p1, mttr_p2)

    # --- KPI 4 : Charge Totale Consommée (Heures) ---
    charge_p1 = round(df_p1["temps_passe_h"].sum(), 1)
    charge_p2 = round(df_p2["temps_passe_h"].sum(), 1)
    ev_charge = calc_evolution(charge_p1, charge_p2)

    return {
        "recus": {"valeur": recus_p1, "evolution": ev_recus},
        "resolus": {"valeur": resolus_p1, "evolution": ev_resolus},
        "mttr": {"valeur": mttr_p1, "evolution": ev_mttr},  # ex: en heures par ticket
        "charge": {"valeur": charge_p1, "evolution": ev_charge}, # ex: en heures totales
    }

STATUTS_RESOLUS = {"résolu", "resolu", "fermé", "ferme", "closed", "resolved"}
JOURS_PAR_PERIODE = {
    "1 semaine": 7,
    "2 semaines": 14,
    "1 mois": 30,
}
COLONNES_SORTIE = ["date_str", "nombre"]


def _filtrer_tickets_resolus(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne les lignes résolues avec une date d'ouverture valide et sans fuseau."""
    if "date_ouverture" not in df.columns or "statut" not in df.columns:
        return pd.DataFrame()

    data = df.copy()
    data["date_ouverture"] = pd.to_datetime(
        data["date_ouverture"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    est_resolu = data["statut"].astype(str).str.strip().str.casefold().isin(STATUTS_RESOLUS)
    return data[est_resolu].dropna(subset=["date_ouverture"])


def _filtrer_fenetre_temporelle(
    resolved_df: pd.DataFrame,
    all_dates: pd.Series,
    periode: str,
    date_debut: str | pd.Timestamp | None = None,
    date_fin: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Filtre les tickets résolus selon une plage explicite ou une période relative."""
    debut_dt = pd.to_datetime(date_debut, errors="coerce") if date_debut else pd.NaT
    fin_dt = pd.to_datetime(date_fin, errors="coerce") if date_fin else pd.NaT

    if not pd.isna(debut_dt) or not pd.isna(fin_dt):
        masque = pd.Series(True, index=resolved_df.index)
        if not pd.isna(debut_dt):
            masque &= resolved_df["date_ouverture"] >= debut_dt.normalize()
        if not pd.isna(fin_dt):
            fin_borne = fin_dt.normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            masque &= resolved_df["date_ouverture"] <= fin_borne
        return resolved_df[masque]

    nb_jours = JOURS_PAR_PERIODE.get(periode)
    if nb_jours is None:
        return resolved_df

    date_ref = all_dates.dropna().max()
    if pd.isna(date_ref):
        date_ref = pd.Timestamp.now().normalize()

    date_debut_fenetre = (date_ref - pd.Timedelta(days=nb_jours - 1)).normalize()
    return resolved_df[resolved_df["date_ouverture"] >= date_debut_fenetre]


def get_resolved_tickets_by_period(
    df: pd.DataFrame,
    periode: str = "2 semaines",
    date_debut: str | pd.Timestamp | None = None,
    date_fin: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Retourne le nombre de tickets résolus par jour sur une période ou une plage donnée."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLONNES_SORTIE)

    resolved_df = _filtrer_tickets_resolus(df)
    if resolved_df.empty:
        return pd.DataFrame(columns=COLONNES_SORTIE)

    all_dates = pd.to_datetime(df["date_ouverture"], errors="coerce", utc=True).dt.tz_localize(None)
    filtered = _filtrer_fenetre_temporelle(
        resolved_df,
        all_dates=all_dates,
        periode=periode,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    if filtered.empty:
        return pd.DataFrame(columns=COLONNES_SORTIE)

    daily = (
        filtered.assign(date_str=filtered["date_ouverture"].dt.strftime("%Y-%m-%d"))
        .groupby("date_str", as_index=False)
        .size()
        .rename(columns={"size": "nombre"})
        .sort_values("date_str")
    )

    plage_explicite = bool(date_debut or date_fin)
    if not plage_explicite and periode not in JOURS_PAR_PERIODE:
        daily = daily.tail(60)

    return daily[COLONNES_SORTIE].reset_index(drop=True)

def get_operational_alerts(df: pd.DataFrame) -> list[dict]:
    """Analyse le DataFrame et retourne une liste de dictionnaires d'alertes."""
    if df.empty:
        return []

    alerts = []
    df = df.copy()
    df["date_ouverture"] = pd.to_datetime(df["date_ouverture"], errors="coerce")
    
    # 1. Alerte : Incidents Critiques ou Hauts non résolus
    if "priorite" in df.columns and "statut" in df.columns:
        critiques_non_resolus = df[
            df["priorite"].str.casefold().isin(["high", "highest", "critique", "élevée", "elevee"]) &
            ~df["statut"].str.casefold().isin(["résolu", "resolu", "fermé", "ferme", "closed", "resolved"])
        ]
        for _, row in critiques_non_resolus.iterrows():
            alerts.append({
                "niveau": "error", # rouge
                "titre": f"Priorité Critique : {row.get('id', 'N/A')}",
                "message": f"Application **{row.get('application', 'Inconnue')}** — {row.get('categorie', 'Pas de résumé')} (Statut : {row.get('statut', 'Inconnu')})"
            })

    # 2. Alerte : Tickets sans résolution mais avec un temps passé élevé (> 5h par exemple)
    if "temps_passe_h" in df.columns:
        longs_tickets = df[
            (df["temps_passe_h"] > 5.0) & 
            ~df["statut"].str.casefold().isin(["résolu", "resolu", "fermé", "ferme", "closed", "resolved"])
        ]
        for _, row in longs_tickets.iterrows():
            alerts.append({
                "niveau": "warning", # orange
                "titre": f"Consommation élevée : {row.get('id', 'N/A')}",
                "message": f"Déjà **{row.get('temps_passe_h')}h** passées sur l'application *{row.get('application')}* sans être résolu."
            })

    # 3. Alerte d'information générale si l'équipe a beaucoup de charge récente
    charge_totale = df["temps_passe_h"].sum() if "temps_passe_h" in df.columns else 0
    if charge_totale > 0:
        alerts.append({
            "niveau": "info", # bleu
            "titre": "Point d'activité global",
            "message": f"Volume total cumulé sur le périmètre analysé : **{round(charge_totale, 1)} heures** de TMA."
        })

    return alerts