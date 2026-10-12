"""Boucle de conversation avec une API compatible OpenAI (Ollama, vLLM...)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from tools import TOOLS_SCHEMA, call_tool

MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
MAX_ITERATIONS = int(os.getenv("LLM_MAX_TOOL_ROUNDS", "5"))
client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("LLM_API_KEY", "ollama"),
)

SYSTEM_PROMPT = """Tu es l'assistant d'une equipe RUN de TMA. Tu aides a explorer des
tickets deja analyses et regroupes en familles.

Regles :
- Pour toute question chiffree, de classement ou de tendance, appelle un outil. Ne calcule
  et n'invente aucun chiffre : les calculs sont faits par les outils.
- Justifie tes reponses avec les identifiants fournis dans `tickets_sources`, la periode et
  le nombre de tickets analyses lorsque ces informations sont disponibles.
- Si un outil ne renvoie rien, contient `avertissement`, ou ne couvre pas la question,
  indique clairement que tu ne disposes pas d'informations suffisantes. Ne devine pas.
- Reponds en francais, de facon concise. N'invente aucun ticket ni aucune cause.
- N'utilise pas d'emojis dans tes reponses.
- Tes reponses sont des propositions : aucune action n'est executee, la decision revient
  a l'humain.
"""


def chat(history: list[dict]) -> tuple[str, list[dict], float]:
    """Retourne la reponse finale, le journal des outils et la duree en secondes."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    calls_log = []
    started_at = time.perf_counter()

    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            temperature=0.2,
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content or "", calls_log, time.perf_counter() - started_at

        messages.append(message.model_dump(exclude_none=True))
        for tool_call in message.tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = call_tool(tool_call.function.name, arguments)
            except Exception as error:
                arguments = {}
                result = {"erreur": f"{type(error).__name__}: {error}"}
            calls_log.append({
                "outil": tool_call.function.name,
                "arguments": arguments,
                "resultat": result,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return (
        "Je n'ai pas reussi a repondre en un nombre raisonnable d'etapes.",
        calls_log,
        time.perf_counter() - started_at,
    )