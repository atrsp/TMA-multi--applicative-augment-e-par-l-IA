"""Outils deterministes que le LLM peut appeler pour interroger les tickets."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import pandas as pd

from data_layer import load_tickets

MAX_SOURCES = 10
MAX_RESULTS = 10
COMPACT_COLUMNS = ["id", "date_ouverture", "application", "type", "famille", "temps_passe_h"]


@lru_cache(maxsize=1)
def _tickets() -> pd.DataFrame:
    return load_tickets()


def _filtre(periode: str, application: str | None = None) -> pd.DataFrame:
    df = _tickets()
    if periode != "tout":
        match = re.fullmatch(r"(\d+)j", periode)
        if not match:
            raise ValueError("periode doit etre de la forme '7j', '30j', '90j' ou 'tout'")
        latest = df["date_ouverture"].max()
        df = df[df["date_ouverture"] > latest - pd.Timedelta(days=int(match.group(1)))]
    if application:
        df = df[df["application"].astype(str).str.casefold() == application.casefold()]
    return df


def _ids(df: pd.DataFrame) -> list[str]:
    return df["id"].dropna().astype(str).loc[lambda values: values != ""].head(MAX_SOURCES).tolist()


def _base(df: pd.DataFrame, periode: str, application: str | None) -> dict[str, Any]:
    result = {
        "periode": periode,
        "application": application or "toutes",
        "nb_tickets_analyses": len(df),
        "tickets_sources": _ids(df),
    }
    if df.empty:
        result["avertissement"] = "Aucun ticket sur ce perimetre : je ne peux pas repondre."
    return result


def _compact(df: pd.DataFrame) -> list[dict[str, Any]]:
    compact = df[COMPACT_COLUMNS].copy()
    compact["date_ouverture"] = compact["date_ouverture"].dt.strftime("%Y-%m-%d")
    return compact.astype(object).where(pd.notna(compact), None).to_dict(orient="records")


def _agreger(df: pd.DataFrame, column: str, n: int, tri: str) -> list[dict[str, Any]]:
    if tri not in {"nombre", "temps"}:
        raise ValueError("tri doit etre 'nombre' ou 'temps'")
    total_hours = float(df["temps_passe_h"].sum()) or 1.0
    rows = []
    for value, group in df.groupby(column):
        hours = float(group["temps_passe_h"].sum())
        rows.append({
            column: str(value),
            "nombre": len(group),
            "temps_total_h": round(hours, 1),
            "part_charge_pct": round(100 * hours / total_hours, 1),
            "tickets_sources": _ids(group.sort_values("temps_passe_h", ascending=False)),
        })
    key = "nombre" if tri == "nombre" else "temps_total_h"
    return sorted(rows, key=lambda row: row[key], reverse=True)[:n]


def _bounded_count(value: int, default: int = 5) -> int:
    try:
        return max(1, min(int(value), MAX_RESULTS))
    except (TypeError, ValueError):
        return default


def top_tickets_chronophages(
    n: int = 3, periode: str = "30j", application: str | None = None
) -> dict[str, Any]:
    df = _filtre(periode, application)
    result = _base(df, periode, application)
    if not df.empty:
        top = df.sort_values("temps_passe_h", ascending=False).head(_bounded_count(n, 3))
        result["tickets"] = _compact(top)
        result["tickets_sources"] = _ids(top)
    return result


def familles_recurrentes(
    n: int = 5, periode: str = "90j", application: str | None = None,
    tri: str = "nombre",
) -> dict[str, Any]:
    df = _filtre(periode, application)
    result = _base(df, periode, application)
    if not df.empty:
        result["tri"] = tri
        result["familles"] = _agreger(df, "famille", _bounded_count(n), tri)
    return result


def type_ticket_plus_recurrent(
    periode: str = "30j", application: str | None = None
) -> dict[str, Any]:
    df = _filtre(periode, application)
    result = _base(df, periode, application)
    if not df.empty:
        result["repartition"] = _agreger(df, "type", MAX_RESULTS, "nombre")
    return result


def causes_racines_frequentes(
    n: int = 5, periode: str = "90j", application: str | None = None
) -> dict[str, Any]:
    df = _filtre(periode, application)
    result = _base(df, periode, application)
    if not df.empty:
        result["causes"] = _agreger(df, "cause_racine", _bounded_count(n), "nombre")
    return result


def tickets_par_famille(famille: str, limite: int = 5) -> dict[str, Any]:
    df = _tickets()
    selected = df[df["famille"] == famille]
    if selected.empty:
        return {
            "erreur": f"famille inconnue : {famille}",
            "familles_disponibles": sorted(value for value in df["famille"].unique() if value),
            "tickets_sources": [],
        }
    causes = selected["cause_racine"].mode()
    return {
        "famille": famille,
        "nb_tickets": len(selected),
        "temps_total_h": round(float(selected["temps_passe_h"].sum()), 1),
        "cause_racine": causes.iloc[0] if not causes.empty else "",
        "resolutions_connues": selected["resolution"].value_counts().head(3).index.tolist(),
        "exemples": _compact(selected.head(_bounded_count(limite))),
        "tickets_sources": _ids(selected),
    }


def synthese_hebdo(application: str | None = None) -> dict[str, Any]:
    df = _tickets()
    if application:
        df = df[df["application"].astype(str).str.casefold() == application.casefold()]
    dated = df.dropna(subset=["date_ouverture"])
    if dated.empty:
        return {
            "semaine_se_terminant_le": None,
            "application": application or "toutes",
            "nb_tickets": 0,
            "nb_tickets_semaine_precedente": 0,
            "temps_total_h": 0.0,
            "tickets_sources": [],
            "avertissement": "Aucun ticket date sur ce perimetre.",
        }
    end = dated["date_ouverture"].max()
    this_week = dated[dated["date_ouverture"] > end - pd.Timedelta(days=7)]
    previous_week = dated[
        (dated["date_ouverture"] <= end - pd.Timedelta(days=7))
        & (dated["date_ouverture"] > end - pd.Timedelta(days=14))
    ]
    result = {
        "semaine_se_terminant_le": end.strftime("%Y-%m-%d"),
        "application": application or "toutes",
        "nb_tickets": len(this_week),
        "nb_tickets_semaine_precedente": len(previous_week),
        "temps_total_h": round(float(this_week["temps_passe_h"].sum()), 1),
        "tickets_sources": [],
    }
    if not this_week.empty:
        top = this_week.sort_values("temps_passe_h", ascending=False).head(3)
        result["top3_chronophages"] = _compact(top)
        result["familles_principales"] = _agreger(this_week, "famille", 3, "nombre")
        result["tickets_sources"] = _ids(top)
    else:
        result["avertissement"] = "Aucun ticket cette semaine."
    return result


def detail_ticket(id: str) -> dict[str, Any]:
    selected = _tickets()
    selected = selected[selected["id"] == id]
    if selected.empty:
        return {"erreur": f"ticket introuvable : {id}", "tickets_sources": []}
    row = selected.iloc[0].where(pd.notna(selected.iloc[0]), None).to_dict()
    row["date_ouverture"] = selected.iloc[0]["date_ouverture"].strftime("%Y-%m-%d")
    row["tickets_sources"] = [id]
    return row


FUNCTIONS = {
    function.__name__: function
    for function in (
        top_tickets_chronophages,
        familles_recurrentes,
        type_ticket_plus_recurrent,
        causes_racines_frequentes,
        tickets_par_famille,
        synthese_hebdo,
        detail_ticket,
    )
}

_PERIODE = {"type": "string", "description": "Periode : '7j', '30j', '90j' ou 'tout'."}
_APPLICATION = {"type": "string", "description": "Filtrer sur une application (optionnel)."}


def _tool(
    name: str, description: str, properties: dict[str, Any], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


TOOLS_SCHEMA = [
    _tool("top_tickets_chronophages", "Tickets ayant consomme le plus de temps.", {
        "n": {"type": "integer"}, "periode": _PERIODE, "application": _APPLICATION,
    }),
    _tool("familles_recurrentes", "Familles classees par frequence ou charge.", {
        "n": {"type": "integer"}, "periode": _PERIODE, "application": _APPLICATION,
        "tri": {"type": "string", "enum": ["nombre", "temps"]},
    }),
    _tool("type_ticket_plus_recurrent", "Repartition des tickets par type.", {
        "periode": _PERIODE, "application": _APPLICATION,
    }),
    _tool("causes_racines_frequentes", "Causes racines les plus frequentes.", {
        "n": {"type": "integer"}, "periode": _PERIODE, "application": _APPLICATION,
    }),
    _tool("tickets_par_famille", "Detail des tickets d'une famille.", {
        "famille": {"type": "string"}, "limite": {"type": "integer"},
    }, ["famille"]),
    _tool("synthese_hebdo", "Synthese de la derniere semaine.", {"application": _APPLICATION}),
    _tool("detail_ticket", "Detail d'un ticket par identifiant.", {"id": {"type": "string"}}, ["id"]),
]


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    function = FUNCTIONS.get(name)
    if function is None:
        return {"erreur": f"outil inconnu : {name}"}
    return function(**arguments)