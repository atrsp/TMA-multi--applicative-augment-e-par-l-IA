"""Connexion au LLM et boucle d'agent.

La boucle d'agent, en une phrase : on pose la question au LLM en lui montrant les outils ;
tant qu'il demande des outils, on les exécute et on lui renvoie les résultats ; quand il
répond par du texte, c'est la réponse finale. Le nombre de tours est limité.

La clé du LLM vient du fichier .env. Elle n'est jamais écrite dans le code.
"""
import json
import re
import time

from .. import db, lectures
from .outils import SCHEMA_OUTILS, appeler_outil
from .prompt import PROMPT_SYSTEME, contexte_periode

MESSAGE_DESACTIVE = ("Copilote désactivé : aucun LLM n'est configuré (variables AZURE_OPENAI_ENDPOINT "
                     "et AZURE_OPENAI_KEY, ou LLM_BASE_URL et LLM_MODEL, du fichier .env). Le tableau de bord, les récurrences, les "
                     "pics et le rattachement des nouveaux tickets restent disponibles.")
CONSIGNE_FINALE = ("Tu as atteint le nombre maximal d'appels d'outils. Réponds maintenant à la question, "
                   "uniquement avec les résultats d'outils déjà obtenus, sans appeler d'autre outil. "
                   "Si une information manque, dis-le.")
MAX_MESSAGES_HISTORIQUE = 12        # on n'envoie que les derniers échanges
MAX_CARACTERES_MESSAGE = 4000


class LLMIndisponible(Exception):
    """Le LLM n'est pas configuré ou ne répond pas : seul le chat est touché."""


def creer_client(config):
    """Fabrique le client de l'API. Renvoie (client, nom du modèle)."""
    try:
        if config["azure_endpoint"] and config["azure_cle"]:
            from openai import AzureOpenAI
            client = AzureOpenAI(api_key=config["azure_cle"], azure_endpoint=config["azure_endpoint"],
                                 api_version=config["azure_version_api"], timeout=60, max_retries=1)
            return client, config["azure_deploiement"]
        if config["llm_base_url"] and config["llm_modele"]:
            from openai import OpenAI
            cle = config["llm_cle"] or "non-requis"
            en_parametre = {config["llm_parametre_cle"]: cle} if config.get("llm_parametre_cle") else None
            client = OpenAI(api_key=cle, base_url=config["llm_base_url"], default_query=en_parametre,
                            timeout=60, max_retries=1)
            return client, config["llm_modele"]
    except Exception as erreur:
        raise LLMIndisponible(f"Configuration du LLM invalide : {erreur.__class__.__name__}") from erreur
    raise LLMIndisponible(MESSAGE_DESACTIVE)


def demander(client, modele, messages, config, outils=None):
    """Un appel au LLM. Renvoie le message de réponse.

    Les modèles n'acceptent pas tous les mêmes options. Exemple constaté : gpt-6-luna exige
    reasoning_effort="none" pour accepter des outils. On essaie donc plusieurs jeux d'options,
    du plus complet au plus simple, tant que l'API répond « 400 : demande refusée ».
    """
    base = {"tools": outils} if outils else {}
    effort = {"reasoning_effort": config["llm_effort"]} if config.get("llm_effort") else {}
    essais = [{**base, **effort, "temperature": 0.2}, {**base, **effort}, base]
    try:
        for numero, options in enumerate(essais):
            try:
                reponse = client.chat.completions.create(model=modele, messages=messages, **options)
                break
            except Exception as erreur:
                dernier = numero == len(essais) - 1
                if getattr(erreur, "status_code", None) != 400 or dernier:
                    raise
    except Exception as erreur:
        # On ne recopie pas le détail de l'erreur : il peut contenir des informations sensibles.
        code = getattr(erreur, "status_code", "")
        raise LLMIndisponible(f"Le LLM ne répond pas ({erreur.__class__.__name__} {code}). "
                              "Les analyses restent disponibles.".replace("  ", " ")) from erreur
    return reponse.choices[0].message


def nettoyer_historique(historique):
    """Ne garde que les derniers messages « user » / « assistant », tronqués."""
    propres = [{"role": m["role"], "content": str(m.get("content", ""))[:MAX_CARACTERES_MESSAGE]}
               for m in historique if m.get("role") in ("user", "assistant") and m.get("content")]
    return propres[-MAX_MESSAGES_HISTORIQUE:]


def verifier_citations(texte):
    """Sépare les clés de tickets citées dans une réponse : celles qui existent, et les autres.

    On ne regarde que les clés dont le préfixe existe dans la base (ex. TMA-...), pour ne
    pas confondre avec un code d'erreur comme ORA-01555.
    """
    prefixes = db.prefixes_des_cles()
    citees = list(dict.fromkeys(c for c in re.findall(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b", texte)
                                if c.rsplit("-", 1)[0] in prefixes))
    existantes = db.cles_existantes(citees)
    return [c for c in citees if c in existantes], [c for c in citees if c not in existantes]


def repondre(historique, config, client=None, modele=None):
    """Fait répondre le copilote. Renvoie un dictionnaire :

        reponse          le texte final
        outils           le journal des outils appelés (nom + arguments)
        tickets_cites    les clés citées qui existent bien
        cles_inconnues   les clés citées qui n'existent pas (signalées à l'utilisateur)
        plans_crees      les numéros des plans proposés pendant cette réponse
        duree            temps de réponse en secondes

    `client` et `modele` peuvent être fournis par les tests ; sinon ils viennent du .env.
    """
    if client is None:
        client, modele = creer_client(config)
    debut = time.perf_counter()
    systeme = PROMPT_SYSTEME + "\n" + contexte_periode(lectures.meta())
    messages = [{"role": "system", "content": systeme}, *nettoyer_historique(historique)]
    journal, plans_crees, texte = [], [], None

    for _ in range(config["llm_max_tours"]):
        message = demander(client, modele, messages, config, SCHEMA_OUTILS)
        if not message.tool_calls:
            texte = message.content or ""
            break
        messages.append(message.model_dump(exclude_none=True))
        for appel in message.tool_calls:
            try:
                arguments = json.loads(appel.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            resultat = appeler_outil(appel.function.name, arguments)
            journal.append({"outil": appel.function.name, "arguments": arguments,
                            "erreur": resultat.get("erreur") if isinstance(resultat, dict) else None})
            if appel.function.name == "proposer_plan_action" and resultat.get("plan_id"):
                plans_crees.append(resultat["plan_id"])
            # Le résultat de l'outil est renvoyé au LLM comme une DONNÉE (rôle « tool »).
            messages.append({"role": "tool", "tool_call_id": appel.id,
                             "content": json.dumps(resultat, ensure_ascii=False, default=str)})

    if texte is None:
        # Nombre maximal de tours atteint : on demande une réponse finale SANS outil, à partir
        # des résultats déjà obtenus, plutôt que de laisser l'utilisateur sans réponse.
        messages.append({"role": "user", "content": CONSIGNE_FINALE})
        texte = demander(client, modele, messages, config).content
    if not texte:
        texte = "Je n'ai pas réussi à répondre en un nombre raisonnable d'étapes. Reformulez la question."
    cites, inconnues = verifier_citations(texte)
    return {"reponse": texte, "outils": journal, "tickets_cites": cites, "cles_inconnues": inconnues,
            "plans_crees": plans_crees, "duree": round(time.perf_counter() - debut, 1)}
