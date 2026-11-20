"""Interface Streamlit TMA Insight : Tableau de bord fixe sur une seule page avec assistant."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_layer import (
    calculer_kpis_tma,
    get_operational_alerts,
    get_resolved_tickets_by_period,
    load_tickets,
)
from llm import MODEL, chat

# 1. Configuration de la page : doit être la première commande Streamlit
st.set_page_config(page_title="TMA Insight", layout="wide")

OPTIONS_PERIODE = ["1 semaine", "2 semaines", "1 mois", "Tout"]
STATUTS_RESOLUS = ["résolu", "resolu", "fermé", "ferme", "closed", "resolved"]

CHEMIN_TICKETS = Path(__file__).resolve().parent.parent / "data" / "clusters_tickets.csv"
CHEMIN_GROUPES = Path(__file__).resolve().parent.parent / "data" / "clusters_groupes.csv"

OPTIONS_TRI = {
    "Date d'apparition": "date_creation",
    "Catégorie technique": "categorie_technique",
    "Nom du groupe": "nom_groupe",
}
HAUTEUR_TABLEAU_TICKETS = 480

# =====================================================================
# ÉTAT DU GRAPHIQUE (piloté par l'interface et par le chatbot)
# =====================================================================
ETAT_DEFAUT = {
    "periode": "2 semaines",
    "date_debut": None,
    "date_fin": None,
    "type": None,
    "application": None,
}

if "chart_etat" not in st.session_state:
    st.session_state.chart_etat = dict(ETAT_DEFAUT)

if "chart_periode_widget" not in st.session_state:
    st.session_state.chart_periode_widget = st.session_state.chart_etat["periode"]


def _normaliser_periode_depuis_commande(cmd: dict) -> str:
    if cmd.get("periode") in OPTIONS_PERIODE:
        return cmd["periode"]
    jours = cmd.get("jours")
    if jours is not None:
        try:
            j = float(jours)
            if j <= 7:
                return "1 semaine"
            if j <= 14:
                return "2 semaines"
            if j <= 31:
                return "1 mois"
            return "Tout"
        except (ValueError, TypeError):
            pass
    return st.session_state.chart_etat.get("periode") or "2 semaines"


def appliquer_commande(cmd: dict) -> None:
    """Applique la commande renvoyée par un outil du chatbot et met à jour le widget."""
    if not isinstance(cmd, dict):
        return
    if cmd.get("reset"):
        st.session_state.chart_etat = dict(ETAT_DEFAUT)
        st.session_state.chart_periode_widget = ETAT_DEFAUT["periode"]
        return

    etat = st.session_state.chart_etat

    if "debut" in cmd or "date_debut" in cmd:
        etat["date_debut"] = cmd.get("debut") if "debut" in cmd else cmd.get("date_debut")
    if "fin" in cmd or "date_fin" in cmd:
        etat["date_fin"] = cmd.get("fin") if "fin" in cmd else cmd.get("date_fin")

    if etat["date_debut"] or etat["date_fin"]:
        etat["periode"] = None
    else:
        periode_maj = _normaliser_periode_depuis_commande(cmd)
        etat["periode"] = periode_maj
        st.session_state.chart_periode_widget = periode_maj

    for cle in ("type", "application"):
        if cle in cmd:
            etat[cle] = None if cmd[cle] == "tous" else cmd[cle]


def _on_periode_change() -> None:
    choisie = st.session_state.get("chart_periode_widget") or "2 semaines"
    st.session_state.chart_etat["periode"] = choisie
    st.session_state.chart_etat["date_debut"] = None
    st.session_state.chart_etat["date_fin"] = None


def construire_donnees_graphe(df: pd.DataFrame, etat: dict) -> tuple[pd.DataFrame, str]:
    """Retourne le DataFrame des tickets résolus par jour et le titre du graphique."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["date_str", "nombre"]), "Tickets résolus par jour"

    d = df.copy()
    if etat.get("application") and "application" in d.columns:
        d = d[d["application"].astype(str).str.casefold() == str(etat["application"]).casefold()]
    if etat.get("type") and "type" in d.columns:
        d = d[d["type"].astype(str).str.casefold() == str(etat["type"]).casefold()]

    d1 = etat.get("date_debut") or None
    d2 = etat.get("date_fin") or None

    try:
        if d1 or d2:
            df_res = get_resolved_tickets_by_period(d, date_debut=d1, date_fin=d2)
            titre = f"Tickets résolus par jour ({d1 or 'début'} → {d2 or 'fin'})"
        else:
            periode = etat.get("periode") or "2 semaines"
            df_res = get_resolved_tickets_by_period(d, periode=periode)
            titre = f"Tickets résolus par jour ({periode})"
    except Exception:
        df_res = pd.DataFrame(columns=["date_str", "nombre"])
        titre = "Tickets résolus par jour"

    if etat.get("application"):
        titre += f" • {etat['application']}"
    if etat.get("type"):
        titre += f" • {etat['type']}"

    return df_res, titre


# =====================================================================
# VUES
# =====================================================================
@st.cache_data
def charger_tickets_clusters(chemin: str) -> pd.DataFrame:
    t = pd.read_csv(chemin, encoding="utf-8-sig")
    t["date_creation"] = pd.to_datetime(
        t["date_creation"], errors="coerce", utc=True
    ).dt.tz_localize(None)
    return t


def afficher_tickets() -> None:
    st.title("Tickets")

    if not CHEMIN_TICKETS.exists():
        st.info(f"Fichier introuvable : {CHEMIN_TICKETS}")
        return

    t = charger_tickets_clusters(str(CHEMIN_TICKETS))

    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        choix = st.selectbox("Trier par", list(OPTIONS_TRI.keys()), key="tickets_tri")
    with c2:
        ordre = st.radio("Ordre", ["Croissant", "Décroissant"], horizontal=True, key="tickets_ordre")
    colonne_tri = OPTIONS_TRI[choix]
    with c3:
        st.caption(f"{len(t)} tickets • tri sur « {colonne_tri} »")

    tri = t.sort_values(
        colonne_tri,
        ascending=(ordre == "Croissant"),
        na_position="last",
        kind="stable",
    )

    affichage = tri.copy()
    affichage["date_creation"] = affichage["date_creation"].dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(
        affichage,
        use_container_width=True,
        hide_index=True,
        height=HAUTEUR_TABLEAU_TICKETS,
    )


def afficher_vue_ensemble(df: pd.DataFrame) -> None:
    st.title("Vue d'ensemble du RUN")
    st.caption("Du 27 juillet au 15 octobre 2026 • 6 applications • 315 tickets analysés")

    kpis = calculer_kpis_tma(df)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Tickets Reçus (30j)",
            value=kpis.get("recus", {}).get("valeur", 0),
            delta=f"{kpis.get('recus', {}).get('evolution', 0)}% vs N-1",
        )
    with col2:
        st.metric(
            label="Tickets Résolus (30j)",
            value=kpis.get("resolus", {}).get("valeur", 0),
            delta=f"{kpis.get('resolus', {}).get('evolution', 0)}% vs N-1",
        )
    with col3:
        st.metric(
            label="Temps Moyen (MTTR)",
            value=f"{kpis.get('mttr', {}).get('valeur', 0)}h",
            delta=f"{kpis.get('mttr', {}).get('evolution', 0)}% vs N-1",
        )
    with col4:
        st.metric(
            label="Charge Consommée",
            value=f"{kpis.get('charge', {}).get('valeur', 0)}h",
            delta=f"{kpis.get('charge', {}).get('evolution', 0)}% vs N-1",
        )

    st.markdown("---")

    col_graphe, col_alertes = st.columns([2, 1])

    with col_graphe:
        st.segmented_control(
            "Période de résolution",
            options=OPTIONS_PERIODE,
            key="chart_periode_widget",
            on_change=_on_periode_change,
            label_visibility="collapsed",
        )

        etat = st.session_state.chart_etat
        df_graph, titre = construire_donnees_graphe(df, etat)

        if not df_graph.empty and df_graph["nombre"].sum() > 0:
            max_val = df_graph["nombre"].max()
            fig = px.bar(
                df_graph,
                x="date_str",
                y="nombre",
                title=titre,
                labels={"date_str": "Date", "nombre": "Tickets résolus"},
                text="nombre",
            )
            fig.update_traces(textposition="outside", cliponaxis=False, marker_color="#2b5c8f")
            fig.update_layout(
                xaxis_title="",
                yaxis_title="",
                margin=dict(l=10, r=10, t=35, b=10),
                height=210,
                title_font_size=14,
                xaxis=dict(tickangle=-30, type="category"),
                yaxis=dict(range=[0, max(1, max_val * 1.25)]),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucun ticket résolu sur cette plage sélectionnée.")

        if etat != ETAT_DEFAUT:
            if st.button("↺ Réinitialiser le graphique", key="reset_graphe"):
                st.session_state.chart_etat = dict(ETAT_DEFAUT)
                st.session_state.chart_periode_widget = ETAT_DEFAUT["periode"]
                st.rerun()

    with col_alertes:
        st.subheader("🚨 Alertes et Points Opérationnels")
        alerts_list = get_operational_alerts(df)

        if alerts_list:
            with st.container(height=150):
                for alert in alerts_list:
                    niveau = alert.get("niveau")
                    titre_alerte = alert.get("titre")
                    msg = alert.get("message")
                    if niveau == "error":
                        st.error(f"**{titre_alerte}** : {msg}", icon="🚨")
                    elif niveau == "warning":
                        st.warning(f"**{titre_alerte}** : {msg}", icon="⚠️")
                    else:
                        st.info(f"**{titre_alerte}** : {msg}", icon="ℹ️")
        else:
            st.success("Aucune alerte critique en cours sur le périmètre actuel.", icon="✅")

    st.markdown("---")

    if CHEMIN_GROUPES.exists():
        df_problemes = pd.read_csv(CHEMIN_GROUPES)
        with st.container(height=160):
            st.dataframe(df_problemes, use_container_width=True, hide_index=True)
    else:
        st.info("Lancez V1_Bertopic.py pour générer les problèmes récurrents.")


# 2. CSS global
st.markdown(
    """
    <style>
    .stPlotlyChart { margin-bottom: -15px !important; }
    div[data-testid="stVerticalBlock"] > div { margin-bottom: -5px !important; }

    .stDeployButton { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; visibility: hidden !important; }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 3. Barre latérale de navigation
with st.sidebar:
    st.markdown("### 📊 TMA Insight")
    page = st.radio(
        "Navigation",
        ["Vue d'ensemble", "Problèmes récurrents", "Tendances et pics", "Actions correctives", "Tickets"],
    )
    st.markdown("---")
    st.caption(f"Modèle : {MODEL}")
    st.caption("Projet 29 • IMT Atlantique")

df = load_tickets()

# 4. Deux colonnes : contenu principal à gauche, assistant à droite
col_dashboard, col_chatbot = st.columns([3, 1], gap="medium")

with col_dashboard:
    if page == "Tickets":
        afficher_tickets()
    else:
        afficher_vue_ensemble(df)

with col_chatbot:
    st.subheader("Assistant RUN")
    st.caption("chatbot d'aide")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_container = st.container(height=520)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(
                message["role"],
                avatar=None if message["role"] == "user" else "🤖",
            ):
                st.markdown(message["content"])

    user_input = st.chat_input("Poser une question sur les tickets...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]

        with st.spinner("Analyse..."):
            try:
                answer, sources, duration = chat(history)
            except Exception as error:
                answer, sources = f"Erreur LLM : {type(error).__name__}", []

        for appel in sources:
            outil = appel.get("outil")
            resultat = appel.get("resultat")
            args = appel.get("arguments") or {}

            if outil == "modifier_graphique" and isinstance(resultat, dict) and resultat.get("ok"):
                appliquer_commande(resultat["commande"])
            elif outil in ("get_resolved_tickets_by_period_tool", "get_resolved_tickets_by_period"):
                if isinstance(resultat, dict) and isinstance(resultat.get("plage_appliquee"), dict):
                    appliquer_commande(resultat["plage_appliquee"])
                elif args:
                    appliquer_commande(args)

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()