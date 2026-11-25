"""Lire la configuration dans le fichier .env.

Tout ce qui est secret (jeton Jira, clé du LLM) ou propre à une installation (adresses,
chemins) vit dans .env, jamais dans le code. Les seuils d'analyse, eux, se règlent dans
la page « Connecteurs et seuils » et sont enregistrés dans SQLite.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent          # le dossier code_version_finalisee


def chemin_absolu(valeur):
    """Un chemin relatif du .env est compris par rapport au dossier du projet."""
    chemin = Path(valeur).expanduser()
    return chemin if chemin.is_absolute() else (RACINE / chemin).resolve()


def racine_azure(adresse):
    """Le client Azure attend la RACINE de la passerelle et ajoute lui-même « /openai/... ».
    Si l'adresse du .env contient déjà ce suffixe (« .../openai/v1/ »), on le retire."""
    position = adresse.find("/openai")
    return adresse[:position] + "/" if position != -1 else adresse


def lire_config():
    """Renvoie la configuration sous forme de dictionnaire."""
    load_dotenv(RACINE / ".env")
    lire = lambda nom, defaut="": os.getenv(nom, defaut).strip()
    return {
        # --- Source des tickets -------------------------------------------------------
        "source": lire("SOURCE", "demo").lower(),                    # demo | jira | fichier
        "demo_tickets": chemin_absolu(lire("DEMO_TICKETS", "../tma-data/data/tickets.json")),
        "fichier_tickets": chemin_absolu(lire("FICHIER_TICKETS", "data/mes_tickets.json")),
        "jira_url": lire("JIRA_URL"),
        "jira_email": lire("JIRA_EMAIL"),
        "jira_token": lire("JIRA_TOKEN"),
        "jira_projet": lire("JIRA_PROJET", "TMA"),
        "jira_jql": lire("JIRA_JQL"),
        "jira_max_tickets": int(lire("JIRA_MAX_TICKETS", "5000")),
        # --- LLM du copilote (facultatif) ---------------------------------------------
        "azure_endpoint": racine_azure(lire("AZURE_OPENAI_ENDPOINT")),
        "azure_cle": lire("AZURE_OPENAI_KEY"),
        "azure_deploiement": lire("AZURE_OPENAI_DEPLOYMENT", "gpt-6-luna"),
        "azure_version_api": lire("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        "llm_base_url": lire("LLM_BASE_URL"),            # autre API compatible OpenAI (ex. Ollama)
        "llm_cle": lire("LLM_API_KEY"),
        "llm_modele": lire("LLM_MODEL"),
        # Certaines passerelles attendent aussi la clé dans un paramètre de l'adresse
        # (ex. « subscription-key »). Laisser vide si ce n'est pas le cas.
        "llm_parametre_cle": lire("LLM_PARAMETRE_CLE"),
        "llm_max_tours": int(lire("LLM_MAX_TOURS", "8")),
        "llm_effort": lire("LLM_REASONING_EFFORT", "none"),
        # --- Divers ---------------------------------------------------------------------
        "dossier_donnees": chemin_absolu(lire("DOSSIER_DONNEES", "data")),
        "identifiants_a_retirer": [p for p in lire("IDENTIFIANTS_A_RETIRER", "CLI,DOS").split(",") if p],
        "modele_embeddings": lire("MODELE_EMBEDDINGS",
                                  "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
    }


def llm_configure(config):
    """Vrai si un LLM est utilisable : Azure OpenAI, ou une API compatible OpenAI."""
    azure = bool(config["azure_endpoint"] and config["azure_cle"])
    compatible = bool(config["llm_base_url"] and config["llm_modele"])
    return azure or compatible
