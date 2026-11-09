"""Petit client pour l'API locale d'Ollama."""
import json
import os

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODELE = os.getenv("OLLAMA_MODELE", "llama3.2")


def demander_json(prompt, seed=0, temperature=0.9):
    """Envoie un prompt à Ollama et renvoie sa réponse sous forme de dictionnaire Python."""
    reponse = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODELE,
            "prompt": prompt,
            "stream": False,      # on attend la réponse complète
            "format": "json",     # on oblige le modèle à répondre en JSON
            "options": {"temperature": temperature, "seed": seed},
        },
        timeout=120,
    )
    reponse.raise_for_status()                   # erreur claire si Ollama ne répond pas
    return json.loads(reponse.json()["response"])
