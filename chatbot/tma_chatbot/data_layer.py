"""Couche d'acces aux donnees.

Adapter COLUMN_MAP pour le fichier normalise. Le schema interne reprend les
champs du cahier des charges et les colonnes produites par l'analyse.
"""

from __future__ import annotations

import re
import random
import unicodedata
from datetime import date, timedelta
from pathlib import Path
import os

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = Path(os.getenv("TICKETS_CSV_PATH", str(PROJECT_ROOT / "data" / "tickets.csv")))
if not DATA_PATH.is_absolute():
    DATA_PATH = PROJECT_ROOT / DATA_PATH

# nom interne -> nom de colonne du fichier reel
COLUMN_MAP = {
    "id": "id",
    "date_ouverture": "date_ouverture",
    "application": "application",
    "type": "type",
    "categorie": "categorie",
    "priorite": "priorite",
    "description": "description",
    "resolution": "resolution",
    "commentaires": "commentaires",
    "statut": "statut",
    "temps_passe_h": "temps_passe_h",
    "famille": "famille",
    "cause_racine": "cause_racine",
}

REQUIRED = [
    "id", "date_ouverture", "type", "famille", "cause_racine", "temps_passe_h"
]

_COLUMN_ALIASES = {
    "date_ouverture": ("date_d_ouverture", "created_at", "date_creation", "date"),
    "type": ("ticket_type", "type_ticket"),
    "categorie": ("category",),
    "priorite": ("priority", "urgence"),
    "resolution": ("solution",),
    "commentaires": ("comments",),
    "statut": ("status", "etat"),
    "temps_passe_h": ("time_spent_hours", "hours_spent", "temps_passe", "charge_h"),
    "famille": ("family", "family_name"),
    "cause_racine": ("root_cause", "cause"),
}


def _normalize_header(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def _fake_tickets(n: int = 250, seed: int = 42) -> pd.DataFrame:
    """Jeu de donnees fictif reproductible pour le developpement local."""
    rng = random.Random(seed)
    families = {
        "export_pdf_timeout": ("Gestion Contrats", "incident", "Edition", "Timeout du service de rendu PDF", "L'export PDF du contrat echoue", "Relance du service de rendu", 18, 3),
        "droits_acces": ("Portail Client", "support", "Habilitations", "Profil utilisateur mal configure", "Impossible d'acceder a un ecran", "Ajustement du profil", 25, 1.5),
        "lenteur_batch_nuit": ("Facturation", "incident", "Performance", "Saturation de la base en fin de nuit", "Le batch de facturation depasse sa fenetre", "Purge et relance du batch", 10, 9),
        "validation_formulaire": ("Portail Client", "incident", "Saisie", "Validation cote client defaillante", "Le formulaire refuse une saisie valide", "Contournement de saisie", 20, 2.5),
        "reinit_mot_de_passe": ("Portail Client", "support", "Habilitations", "Expiration de compte non notifiee", "Compte verrouille apres expiration", "Reinitialisation du compte", 22, 0.5),
        "flux_partenaire": ("Reporting", "incident", "Integration", "Changement de format cote partenaire", "Le fichier partenaire est rejete", "Adaptation du mapping", 5, 12),
    }
    names = list(families)
    weights = [family[6] for family in families.values()]
    today = date.today()
    rows = []
    for index in range(n):
        family_name = rng.choices(names, weights=weights)[0]
        app, ticket_type, category, cause, description, resolution, _, mean = families[family_name]
        rows.append({
            "id": f"TMA-{1000 + index}",
            "date_ouverture": today - timedelta(days=rng.randint(0, 100)),
            "application": app,
            "type": ticket_type,
            "categorie": category,
            "priorite": rng.choice(["basse", "moyenne", "haute"]),
            "description": f"{description} (cas {index})",
            "resolution": resolution,
            "commentaires": "",
            "statut": rng.choice(["resolu", "resolu", "resolu", "en cours"]),
            "temps_passe_h": round(max(0.25, rng.gauss(mean, mean / 2)), 2),
            "famille": family_name,
            "cause_racine": cause,
        })
    return pd.DataFrame(rows)


def load_tickets(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Retourne les tickets analyses avec les noms de colonnes internes."""
    path = Path(csv_path) if csv_path is not None else DATA_PATH
    if path.exists():
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
    else:
        df = _fake_tickets()

    header_map = {_normalize_header(str(column)): column for column in df.columns}
    rename_map = {}
    for internal, external in COLUMN_MAP.items():
        candidates = (external, *_COLUMN_ALIASES.get(internal, ()))
        source = next(
            (header_map[_normalize_header(candidate)] for candidate in candidates
             if _normalize_header(candidate) in header_map),
            None,
        )
        if source is not None:
            rename_map[source] = internal
    df = df.rename(columns=rename_map)

    missing = [column for column in REQUIRED if column not in df.columns]
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {path.name} : {missing} (voir COLUMN_MAP)"
        )

    for column in COLUMN_MAP:
        if column not in df.columns:
            df[column] = ""
    df["date_ouverture"] = pd.to_datetime(df["date_ouverture"])
    df["temps_passe_h"] = pd.to_numeric(df["temps_passe_h"], errors="raise")
    return df