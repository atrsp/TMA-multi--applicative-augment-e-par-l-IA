# Copilote RUN — AIOps léger centré sur les tickets

L'application lit les tickets Jira d'une équipe de TMA, détecte les **problèmes récurrents**,
chiffre leur **coût**, repère les **pics anormaux** et estime le **gain** à traiter leur cause.
Un **copilote conversationnel** rend ces analyses lisibles et propose des plans d'action, que
l'équipe RUN valide.

Trois règles structurent tout le code :

1. **Le code calcule, le LLM rédige, l'humain valide.** Le LLM n'obtient un chiffre qu'en
   appelant un outil du moteur d'analyse.
2. **Débranchable.** Sans LLM, tout fonctionne sauf le chat, qui l'explique.
3. **Lecture seule.** L'application ne modifie jamais Jira.

## Installation

Python 3.11 ou plus récent. Depuis le dossier `code_version_finalisee/` :

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

Au premier lancement, le modèle d'embeddings (environ 470 Mo) est téléchargé une fois.

## Lancement en une commande

```bash
uvicorn app.main:app
```

Puis ouvrir <http://localhost:8000>. Sans fichier `.env`, l'application démarre en **mode
démonstration** (tickets de `../tma-data/data/tickets.json`), sans identifiant et sans LLM.
La première analyse prend une quinzaine de secondes ; les suivantes moins d'une seconde.

## Tests

```bash
pytest
```

36 tests : moteur (pic du batch en semaine 9, ticket hors sujet classé « nouveau », groupes
recopiés, cache, semaine au choix, petit fichier), API, outils et boucle d'agent (avec un
faux LLM : aucun appel réseau).

## Configuration

Copier `.env.example` en `.env` et le compléter. Ce fichier contient les secrets : il est
ignoré par Git. Redémarrer l'application après toute modification.

### Source des tickets

| `SOURCE` | Ce qui est lu | Variables |
|---|---|---|
| `demo` (défaut) | le jeu synthétique | `DEMO_TICKETS` |
| `fichier` | un fichier JSON (format de l'API Jira) ou CSV | `FICHIER_TICKETS` |
| `jira` | l'API REST Jira Cloud, en GET uniquement | `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_PROJET` |

Le moteur ne sait pas d'où viennent les tickets : chaque source les convertit vers le même
format interne (`app/sources/format.py`). Les données incomplètes sont tolérées :

- **pas de temps passé** : heures à 0, avec un avertissement (coût et gain sous-estimés) ;
- **pas de composant** : le nom du projet, sinon « Non renseigné » ;
- **pas de date** : le ticket est écarté de l'analyse ;
- **CSV** : les colonnes sont reconnues souplement (`identifiant`, `id` ou `key` ;
  `date_creation` ou `created` ; etc. — voir `ALIAS` dans `app/sources/fichier.py`).

La taille minimale d'un groupe s'adapte au volume (5 pour une centaine de tickets, 30 à
partir de 1 440), sauf si elle est fixée dans « Connecteurs et seuils ».

Pour Jira, créer un jeton d'API sur
<https://id.atlassian.com/manage-profile/security/api-tokens>. `JIRA_JQL` permet de
restreindre la lecture (par exemple aux 6 derniers mois).

### LLM du copilote (facultatif)

```
AZURE_OPENAI_ENDPOINT=https://<passerelle>/<projet>/
AZURE_OPENAI_KEY=…
AZURE_OPENAI_DEPLOYMENT=gpt-6-luna
```

Une API compatible OpenAI fonctionne aussi avec `LLM_BASE_URL`, `LLM_API_KEY` et `LLM_MODEL`
(Ollama, ou une passerelle en `…/openai/v1/` ; si celle-ci attend la clé dans l'adresse,
ajouter `LLM_PARAMETRE_CLE=subscription-key`). Cette variante n'est lue que si
`AZURE_OPENAI_ENDPOINT` est vide.
Sans ces variables, le chat est désactivé et le dit ; le reste est inchangé.

## Semaine de référence

L'analyse ne dépend pas de la date du jour. En haut de chaque page, l'équipe choisit :

- la **semaine de référence** : l'analyse est faite comme si l'on était à la fin de cette
  semaine ; les tickets créés après sont ignorés. « Automatique » prend la dernière semaine
  complète. La semaine en cours est sélectionnable, signalée comme partielle ;
- l'**historique** : le nombre de semaines analysées avant la semaine de référence.

Changer l'un ou l'autre relance l'analyse (moins d'une seconde : les embeddings sont en cache).
Exemple sur la démo : en choisissant la semaine S9, le pic du batch nocturne apparaît en alerte.

## Architecture

```
Tickets ──► [1. Moteur d'analyse]            ──► [2. Copilote]              ──► Équipe RUN
            calcul exact, SANS LLM                LLM + agent à outils           décide et valide
```

```
app/
├── main.py            routes de l'API et pages statiques
├── config.py          lecture du .env
├── db.py              SQLite : tickets, analyse, plans, réglages
├── service.py         orchestre source → moteur → base (en arrière-plan)
├── lectures.py        mise en forme des résultats, partagée par l'API et les outils
├── sources/           jira.py · fichier.py (démo, JSON, CSV) · format.py
├── moteur/            nettoyage · semaines · vecteurs · groupes · etiquettes ·
│                      recurrences · nouveau_ticket · synthese · pipeline
└── copilote/          prompt · outils · llm (boucle d'agent) · nommage
static/                index.html · style.css · js/ (un fichier par page)
tests/                 test_moteur.py · test_copilote.py
data/                  tma.sqlite + cache des embeddings (créés au lancement)
```

### Le moteur, étape par étape (`app/moteur/pipeline.py`)

1. **Nettoyer** : entités HTML décodées, identifiants `CLI-…` / `DOS-…` retirés (les codes
   d'erreur comme `ORA-01555` sont gardés).
2. **Choisir la période** : semaine de référence et historique.
3. **Vectoriser** : SBERT `paraphrase-multilingual-MiniLM-L12-v2`. Le cache associe
   l'empreinte de chaque texte à son vecteur : seuls les textes nouveaux sont calculés.
4. **Regrouper** : HDBSCAN. Un groupe est marqué **« à vérifier »**, et exclu des
   récurrences, des pics et du gain, dans deux cas : au moins 90 % de ses tickets portent
   le même texte (texte recopié), ou ses tickets ressemblent trop peu à son centre
   (cohésion sous 0,75 : groupe hétérogène).
5. **Décrire** : mots-clés c-TF-IDF, titres représentatifs, solution la plus fréquente.
6. **Récurrences, pics, gain** : test de Poisson sur la médiane du passé ; gain = heures par
   semaine × 52 × part évitée, en trois scénarios.
7. **Nouveau ticket** : ressemblance (cosinus) avec le centre de chaque groupe, seuil 0,6.

### Nom et description des problèmes

- **Sans LLM** : le nom est le titre de ticket le plus représentatif ; la description est
  assemblée par le moteur (application, formulations, mots-clés, solution).
- **Avec LLM** : il rédige un nom précis et une description de 2 à 4 phrases, à partir des
  seuls éléments tirés des tickets. Sa réponse est **vérifiée par le code** : tout code ou
  nombre qu'elle contient doit figurer dans ces éléments, sinon elle est refusée et le nom
  du moteur est gardé. Les noms acceptés sont mis en cache.

La fiche d'un problème affiche toujours la description, les formulations, les mots-clés et
la solution habituelle, pour que l'opérateur puisse vérifier.

### Le copilote (`app/copilote/`)

Boucle d'agent bornée (8 tours, puis une réponse finale sans outil) avec 8 outils : `top_recurrences`, `pics`, `gain_estime`,
`detail_probleme`, `tickets_similaires`, `detail_ticket`, `synthese_hebdo`,
`proposer_plan_action`.

- Chaque réponse affiche les outils appelés. Les clés de tickets citées sont vérifiées en
  base ; une clé inconnue est signalée à l'écran.
- `proposer_plan_action` écrit dans SQLite, au statut « proposé ». Le gain et le nombre de
  tickets du plan sont recalculés par le moteur ; les clés qui n'appartiennent pas au
  problème sont refusées.
- Seul l'humain valide, modifie ou rejette un plan (`PATCH /api/plans/{id}`) : aucun outil
  n'appelle cette route.

### API

| Route | Rôle |
|---|---|
| `GET /api/etat` | source, LLM, semaine de référence, analyse en cours |
| `POST /api/analyse` | relancer l'analyse |
| `GET`, `PUT /api/reglages` | seuils |
| `GET /api/tableau-de-bord` | indicateurs, alerte, problèmes, série hebdomadaire |
| `GET /api/problemes`, `/api/problemes/{id}` | liste et fiche détaillée |
| `GET /api/pics`, `/api/gain` | pics, gain par scénario |
| `POST /api/nouveau-ticket` | rattacher un texte collé |
| `GET /api/nouveaux-tickets`, `/api/tickets/{cle}` | derniers tickets, détail |
| `GET /api/synthese`, `/api/synthese.md` | synthèse hebdomadaire et export |
| `GET`, `POST /api/plans`, `PATCH /api/plans/{id}` | plans d'action |
| `POST /api/copilote` | question au copilote |

La documentation interactive est sur <http://localhost:8000/docs>.

## Sécurité

- Aucun secret dans le code ; `.env` est dans `.gitignore` ; la page de réglages n'affiche
  ni ne modifie de secret.
- Le texte des tickets est une donnée, jamais une instruction : c'est écrit dans le prompt
  système, les résultats d'outils reviennent au LLM avec le rôle `tool`, et l'agent n'a
  aucun outil d'écriture dans Jira (un test le vérifie).
- Seuls des extraits sont envoyés au LLM (titres, résumés de 300 caractères au plus).
- Tout texte venant des tickets ou du LLM est échappé avant affichage.

## Limites connues

- **LLM : un seul modèle essayé.** Le copilote et le nommage ont été vérifiés avec
  `gpt-6-luna` sur la passerelle Azure. Ce modèle exige `LLM_REASONING_EFFORT=none` pour
  accepter des outils ; un autre modèle peut demander d'autres options.
- **Jira non testé en conditions réelles.** Le client suit l'API `/rest/api/3/search/jql`
  et la conversion est testée sur un ticket simulé, mais aucun Jira réel n'était disponible.
- **Jeu de démonstration facile.** Ses tickets réutilisent peu de formulations : le
  regroupement (ARI 0,89) sera moins net sur de vrais tickets.
- **Numéros de problème instables.** Ils sont réattribués à chaque analyse (1 = le plus
  coûteux). Les plans restent rattachés à leur problème grâce aux tickets qu'ils citent.
- **Solution habituelle.** C'est le dernier commentaire le plus fréquent du groupe. Sur de
  vrais tickets aux commentaires tous différents, elle sera peu représentative.
- **Pics en semaine partielle.** Le test reste valable mais sous-estime le volume final.
- **Vérification des noms du LLM.** Elle contrôle les codes et les nombres, pas le sens des
  phrases : une reformulation trompeuse sans chiffre passerait.
- **Un seul utilisateur.** Pas d'authentification ni de gestion de droits ; la conversation
  du chat n'est pas enregistrée.
- **Graphiques.** Chart.js est chargé depuis Internet (cdnjs) ; hors ligne, les graphiques
  sont remplacés par un message, le reste fonctionne.
- **Changement de source.** Il passe par `.env` et un redémarrage.
