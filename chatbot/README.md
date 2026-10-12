# Chatbot TMA

Assistant Streamlit de consultation des tickets analyses. Le code applicatif est regroupe dans `tma_chatbot/` : `app.py`, `llm.py`, `tools.py`, `data_layer.py`, `eval_chatbot.py` et `requirements.txt`.

## Installation

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r tma_chatbot/requirements.txt
Copy-Item .env.example .env
```

Par defaut, `.env.example` configure Ollama en local (`http://localhost:11434/v1`, modele `qwen2.5:7b`). Lancez Ollama et installez ce modele, ou remplacez ces valeurs par celles de votre fournisseur compatible OpenAI. Le fichier `.env` ne doit jamais etre versionne.

## Lancement

```powershell
streamlit run tma_chatbot/app.py
```

Placez le fichier anonymise `tickets.csv` dans `data/`. Les colonnes obligatoires sont `id`, `date_ouverture`, `type`, `famille`, `cause_racine` et `temps_passe_h`. Le mapping configurable et les champs facultatifs sont definis dans `tma_chatbot/data_layer.py`; les autres colonnes du CSV sont conservees pour le detail d'un ticket. Les en-tetes francais avec accents et les CSV separes par des virgules ou des points-virgules sont pris en charge. Sans fichier, les outils utilisent un jeu synthetique reproductible de 250 tickets.

Le backend local expose les analyses deterministes definies dans `tma_chatbot/backends/local.py` : tickets chronophages, familles et causes recurrentes, repartition par type, detail par famille ou ticket, et synthese hebdomadaire. Chaque resultat borne les exemples et les identifiants sources.

## Variables d'environnement

- `LLM_BASE_URL` : URL de base de l'API compatible OpenAI (laisser vide pour l'API OpenAI standard).
- `LLM_API_KEY` : cle fournie par le service LLM.
- `LLM_MODEL` : identifiant du modele expose par le service.
- `TICKETS_CSV_PATH` : chemin du CSV (par defaut `data/tickets.csv`).
- `LLM_MAX_TOOL_ROUNDS` : nombre maximal de tours d'appels d'outils (par defaut `5`).

## Evaluation

```powershell
py tma_chatbot/eval_chatbot.py
```

L'evaluation interroge le LLM configure, mesure le temps et controle le choix des outils et la citation des sources. Elle requiert un LLM demarre et peut engendrer des appels factures.
