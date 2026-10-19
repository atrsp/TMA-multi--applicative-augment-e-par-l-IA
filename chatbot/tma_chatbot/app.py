"""Interface Streamlit : lancer avec `streamlit run tma_chatbot/app.py`."""

import streamlit as st

from llm import MODEL, chat

st.set_page_config(page_title="Assistant TMA augmenté")

# --- Masque le bouton Deploy et le widget de statut, mais laisse les 3 petits points (menu) ---
st.markdown(
    """
    <style>
    /* Cible spécifiquement le bouton Deploy */
    [data-testid="stDeployButton"] {
        display: none !important;
        visibility: hidden !important;
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

with st.sidebar:
    st.subheader("Exemples de questions")
    st.markdown(
        "- Quels sont les 3 tickets les plus chronophages ?\n"
        "- Quels sont les incidents les plus fréquents sur les trois derniers mois ?\n"
        "- Quelles sont les causes racines les plus fréquentes ?\n"
        "- Fais-moi la synthèse de la semaine.\n"
        "- Que contient la famille `export_pdf_timeout` ?"
    )
    st.caption(f"Modèle : {MODEL}")
    if st.button("Nouvelle conversation"):
        st.session_state.messages = []
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

if question := st.chat_input("Posez votre question sur les tickets"):
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