"""Interface Streamlit : lancer avec `streamlit run tma_chatbot/app.py`."""

import streamlit as st

from llm import MODEL, chat

st.set_page_config(page_title="Assistant TMA augmenté")

# --- Masque le bouton Deploy et le widget de statut, mais laisse les 3 petits points (menu) ---
st.markdown(
    """
    <style>
    /* Cible spécifiquement le bouton Deploy */
    .stDeployButton {
        display: none !important;
    }
    /* Cible le widget de statut / chargement en haut à droite */
    [data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Assistant TMA augmenté")

# --- Gestion de la variable pour stocker la question à poser ---
# On utilise session_state pour mémoriser si l'utilisateur a cliqué sur un bouton d'exemple
if "question_a_poser" not in st.session_state:
    st.session_state.question_a_poser = None

with st.sidebar:
    st.subheader("Exemples de questions")
    
    # Liste de tes exemples de questions
    exemples = [
        "Quels sont les 3 tickets les plus chronophages ?",
        "Quels sont les incidents les plus fréquents sur les trois derniers mois ?",
        "Quelles sont les causes racines les plus fréquentes ?",
        "Fais-moi la synthèse de la semaine.",
        "Que contient la famille `export_pdf_timeout` ?"
    ]
    
    # Création d'un bouton pour chaque question
    for q in exemples:
        if st.button(q, use_container_width=True):
            st.session_state.question_a_poser = q

    st.markdown("---")
    st.caption(f"Modèle : {MODEL}")
    if st.button("Nouvelle conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.question_a_poser = None
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []


def afficher(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("duree"):
            st.caption(f"Durée : {message['duree']:.1f} s")
        if message.get("sources"):
            with st.expander("Données utilisées"):
                for source in message["sources"]:
                    st.markdown(f"**{source['outil']}**  `{source['arguments']}`")
                    st.json(source["resultat"], expanded=False)


for message in st.session_state.messages:
    afficher(message)

# Récupération de la question (soit via le champ de saisie classique, soit via le clic sur un bouton de la sidebar)
user_input = st.chat_input("Posez votre question sur les tickets")

# Si l'utilisateur a cliqué sur un bouton d'exemple, on force la question
if st.session_state.question_a_poser:
    question = st.session_state.question_a_poser
    st.session_state.question_a_poser = None # On réinitialise pour éviter de la reposer en boucle
else:
    question = user_input

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    afficher(st.session_state.messages[-1])
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages
    ]

    loading_message = st.empty()
    loading_message.text("Analyse en cours...")
    try:
        answer, sources, duration = chat(history)
    except Exception as error:
        answer = (
            f"Impossible de joindre le LLM ({type(error).__name__}). "
            "Vérifiez qu'il est lancé."
        )
        sources, duration = [], 0.0
    loading_message.empty()

    assistant_message = {
        "role": "assistant",
        "content": answer,
        "sources": sources,
        "duree": duration,
    }
    st.session_state.messages.append(assistant_message)
    afficher(assistant_message)
    
    # Force le rechargement propre pour afficher la réponse immédiatement
    st.rerun()