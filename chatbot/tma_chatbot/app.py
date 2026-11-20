# """Interface Streamlit : lancer avec `streamlit run tma_chatbot/app.py`."""

# import streamlit as st

# from llm import MODEL, chat

# st.set_page_config(page_title="Assistant TMA augmenté")

# # --- Masque le bouton Deploy et le widget de statut, mais laisse les 3 petits points (menu) ---
# st.markdown(
#     """
#     <style>
#     /* Cible spécifiquement le bouton Deploy */
#     .stDeployButton {
#         display: none !important;
#     }
#     /* Cible le widget de statut / chargement en haut à droite */
#     [data-testid="stStatusWidget"] {
#         display: none !important;
#         visibility: hidden !important;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# st.title("Assistant TMA augmenté")

# # --- Gestion de la variable pour stocker la question à poser ---
# # On utilise session_state pour mémoriser si l'utilisateur a cliqué sur un bouton d'exemple
# if "question_a_poser" not in st.session_state:
#     st.session_state.question_a_poser = None

# with st.sidebar:
#     st.subheader("Questions Classiques")
    
#     # Liste de tes exemples de questions
#     exemples = [
#         "Quels sont les 3 tickets les plus chronophages ?",
#         "Quels sont les incidents les plus fréquents sur les trois derniers mois ?",
#         "Quelles sont les causes racines les plus fréquentes ?",
#         "Fais-moi la synthèse de la semaine.",
#         "Que contient la famille `export_pdf_timeout` ?"
#     ]
    
#     # Création d'un bouton pour chaque question
#     for q in exemples:
#         if st.button(q, use_container_width=True):
#             st.session_state.question_a_poser = q

#     st.markdown("---")
#     st.caption(f"Modèle : {MODEL}")
#     if st.button("Nouvelle conversation", use_container_width=True):
#         st.session_state.messages = []
#         st.session_state.question_a_poser = None
#         st.rerun()

# if "messages" not in st.session_state:
#     st.session_state.messages = []


# def afficher(message: dict) -> None:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])
#         if message.get("duree"):
#             st.caption(f"Durée : {message['duree']:.1f} s")
#         if message.get("sources"):
#             with st.expander("Données utilisées"):
#                 for source in message["sources"]:
#                     st.markdown(f"**{source['outil']}**  `{source['arguments']}`")
#                     st.json(source["resultat"], expanded=False)


# for message in st.session_state.messages:
#     afficher(message)

# # Récupération de la question (soit via le champ de saisie classique, soit via le clic sur un bouton de la sidebar)
# user_input = st.chat_input("Posez votre question sur les tickets")

# # Si l'utilisateur a cliqué sur un bouton d'exemple, on force la question
# if st.session_state.question_a_poser:
#     question = st.session_state.question_a_poser
#     st.session_state.question_a_poser = None # On réinitialise pour éviter de la reposer en boucle
# else:
#     question = user_input

# if question:
#     st.session_state.messages.append({"role": "user", "content": question})
#     afficher(st.session_state.messages[-1])
#     history = [
#         {"role": message["role"], "content": message["content"]}
#         for message in st.session_state.messages
#     ]

#     loading_message = st.empty()
#     loading_message.text("Analyse en cours...")
#     try:
#         answer, sources, duration = chat(history)
#     except Exception as error:
#         answer = (
#             f"Impossible de joindre le LLM ({type(error).__name__}). "
#             "Vérifiez qu'il est lancé."
#         )
#         sources, duration = [], 0.0
#     loading_message.empty()

#     assistant_message = {
#         "role": "assistant",
#         "content": answer,
#         "sources": sources,
#         "duree": duration,
#     }
#     st.session_state.messages.append(assistant_message)
#     afficher(assistant_message)
    
#     # Force le rechargement propre pour afficher la réponse immédiatement
#     st.rerun()



"""Interface Streamlit TMA Insight : Tableau de bord fixe sur une seule page avec assistant."""

from pathlib import Path

import streamlit as st
import pandas as pd
from llm import MODEL, chat
from data_layer import load_tickets, calculer_kpis_tma  # <--- On importe la fonction

import plotly.express as px
from data_layer import get_resolved_tickets_by_period
from data_layer import get_operational_alerts


st.markdown("""
    <style>
    /* Réduit l'espace vide sous les graphiques Plotly et les conteneurs */
    .stPlotlyChart {
        margin-bottom: -15px !important;
    }
    div[data-testid="stVerticalBlock"] > div {
        margin-bottom: -5px !important;
    }
    </style>
""", unsafe_allow_html=True)



# 1. Configuration de la page en mode "wide"
st.set_page_config(page_title="TMA Insight", layout="wide")

# 2. CSS global pour bloquer le scroll de la page et descendre le titre de l'assistant
st.markdown(
    """
    <style>
    .stDeployButton { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; visibility: hidden !important; }
    
    /* Supprime le scroll global de la page et fixe la hauteur à 100% de l'écran */
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        height: 100vh !important;
    }
    
    /* Ajustement des marges globales */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
    }

    /* Décale la colonne de droite (Assistant) vers le bas d'environ 1 cm pour éviter la coupe en haut */
    div[data-testid="column"]:nth-of-type(2) {
        margin-top: 500px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

OPTIONS_PERIODE = ["1 semaine", "2 semaines", "1 mois", "Tout"]

# =====================================================================
# METTRE LA PARTIE 3 EN COMMENTAIRE SI ON VEUT SUPPRIMER LA BARRE DE NAVIGATION
# =====================================================================

# 3. Barre latérale de navigation
with st.sidebar:
    st.markdown("### 📊 TMA Insight")
    page = st.radio(
        "Navigation",
        ["Vue d'ensemble", "Problèmes récurrents", "Tendances et pics", "Actions correctives", "Tickets"]
    )
    st.markdown("---")
    st.caption("Projet 29 • IMT Atlantique")

# 4. Organisation principale en deux colonnes (Tableau de bord / Assistant)
col_dashboard, col_chatbot = st.columns([3, 1], gap="medium")

# =====================================================================
# COLONNE GAUCHE : TABLEAU DE BORD FIXE (Sans dépassement)
# =====================================================================
with col_dashboard:
    st.title("Vue d'ensemble du RUN")
    st.caption("Du 27 juillet au 15 octobre 2026 • 6 applications • 315 tickets analysés")

    # --- Ligne de métriques (KPIs) ---

    # 1. Chargement des données
    df = load_tickets()

    # 2. Calcul des KPI
    kpis = calculer_kpis_tma(df)

    # 3. Affichage dans le tableau de bord Streamlit
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Tickets Reçus (30j)", 
            value=kpis.get("recus", {}).get("valeur", 0), 
            delta=f"{kpis.get('recus', {}).get('evolution', 0)}% vs N-1"
        )

    with col2:
        st.metric(
            label="Tickets Résolus (30j)", 
            value=kpis.get("resolus", {}).get("valeur", 0), 
            delta=f"{kpis.get('resolus', {}).get('evolution', 0)}% vs N-1"
        )

    with col3:
        st.metric(
            label="Temps Moyen (MTTR)", 
            value=f"{kpis.get('mttr', {}).get('valeur', 0)}h", 
            delta=f"{kpis.get('mttr', {}).get('evolution', 0)}% vs N-1"
        )

    with col4:
        st.metric(
            label="Charge Consommée", 
            value=f"{kpis.get('charge', {}).get('valeur', 0)}h", 
            delta=f"{kpis.get('charge', {}).get('evolution', 0)}% vs N-1"
        )

    st.markdown("---")

    # --- Section centrale : Graphique et Bloc Alertes avec scroll interne ---
    col_graphe, col_alertes = st.columns([2, 1])
    
    with col_graphe:

        if "chart_range" not in st.session_state:
            st.session_state["chart_range"] = {"mode": "relative", "periode": "2 semaines", "date_debut": None, "date_fin": None}

        def _on_periode_change():
            st.session_state["chart_periode"] = st.session_state["chart_periode_widget"]
            st.session_state["chart_range"] = {
                "mode": "relative",
                "periode": st.session_state["chart_periode_widget"],
                "date_debut": None,
                "date_fin": None,
            }

        periode_choisie = st.segmented_control(
            "Période de résolution",
            options=OPTIONS_PERIODE,
            key="chart_periode_widget",
            on_change=_on_periode_change,
            label_visibility="collapsed",
        ) or st.session_state.get("chart_periode", "2 semaines")

        chart_range = st.session_state["chart_range"]

        if chart_range.get("mode") == "custom":
            d1 = chart_range.get("date_debut")
            d2 = chart_range.get("date_fin")
            df_graph = get_resolved_tickets_by_period(df, date_debut=d1, date_fin=d2)
            titre_graph = f"Tickets résolus par jour ({d1 or '...'} → {d2 or '...'})"
        else:
            df_graph = get_resolved_tickets_by_period(df, periode=periode_choisie)
            titre_graph = f"Tickets résolus par jour ({periode_choisie})"

        if not df_graph.empty:
            fig = px.bar(
                df_graph,
                x="date_str",
                y="nombre",
                title=f"Tickets résolus par jour ({periode_choisie})",
                labels={"date_str": "Date", "nombre": "Tickets résolus"},
                text="nombre",
            )

            max_val = df_graph["nombre"].max() if not df_graph.empty else 0
            fig.update_traces(textposition="outside", marker_color="#2b5c8f")
            fig.update_layout(
                xaxis_title="",
                yaxis_title="",
                margin=dict(l=10, r=10, t=30, b=10),
                height=250,
                xaxis=dict(tickangle=-30),
                yaxis=dict(range=[0, max(1, max_val * 1.25)]),
            )

            st.plotly_chart(fig, width="stretch")
        else:
            st.info(f"Aucune donnée de résolution disponible sur la période « {periode_choisie} ».")
            
            # # Affichage dans Streamlit
            # st.plotly_chart(fig, use_container_width=True)

        with col_alertes:
            st.subheader("🚨 Alertes et Points Opérationnels")

            # Récupération des alertes depuis les données
            alerts_list = get_operational_alerts(df)

            if alerts_list:
                # Conteneur scrollable avec CSS personnalisé
                scrollable_container = st.container(height=150)  # Hauteur fixe en pixels avec scroll automatique
                
                with scrollable_container:
                    for alert in alerts_list:
                        niveau = alert.get("niveau")
                        titre = alert.get("titre")
                        msg = alert.get("message")
                        
                        # Affichage selon le niveau d'alerte Streamlit
                        if niveau == "error":
                            st.error(f"**{titre}** : {msg}", icon="🚨")
                        elif niveau == "warning":
                            st.warning(f"**{titre}** : {msg}", icon="⚠️")
                        else:
                            st.info(f"**{titre}** : {msg}", icon="ℹ️")
            else:
                st.success("Aucune alerte critique en cours sur le périmètre actuel.", icon="✅")

    st.markdown("---")

    # --- Section basse : Problèmes récurrents avec scroll interne fixe ---
    chemin_groupes = Path(__file__).resolve().parent.parent / "data" / "clusters_groupes.csv"
    if chemin_groupes.exists():
        df_problemes = pd.read_csv(chemin_groupes)
    else:
        st.info("Lancez V1_Bertopic.py pour générer les problèmes récurrents.")
        df_problemes = pd.DataFrame()

    # --- Conteneur à hauteur fixe avec scroll interne pour les problèmes ---
    with st.container(height=160):
        st.dataframe(df_problemes, use_container_width=True, hide_index=True)

# =====================================================================
# COLONNE DROITE : ASSISTANT RUN (Chatbot d'aide intégré)
# =====================================================================
with col_chatbot:
    # Petit espace vertical pour descendre l'en-tête d'environ 1 cm
    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
    
    st.subheader("Assistant RUN")
    st.caption("chatbot d'aide")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": ""
            }
        ]

    # Conteneur de chat avec hauteur fixe pour préserver la mise en page unique
    chat_container = st.container(height=520)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar=None if message["role"] == "user" else "🤖"):
                st.markdown(message["content"])

    # Zone de saisie fixée en bas de la colonne de droite
    user_input = st.chat_input("Poser une question sur les tickets...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        with st.spinner("Analyse..."):
            try:
                answer, sources, duration = chat(history)
            except Exception as error:
                answer = f"Erreur LLM : {type(error).__name__}"
        
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()