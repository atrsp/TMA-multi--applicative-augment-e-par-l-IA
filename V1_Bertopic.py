# %% Imports et données
import pandas as pd
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
import matplotlib.pyplot as plt
import os
import openai
from dotenv import load_dotenv
import numpy as np
from umap import UMAP

#Lecture du CSV

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)
tickets_file_path = 'tickets_jira_fictifs.csv'
tickets_data = pd.read_csv(tickets_file_path)


# %% Chargement de la Data

y = tickets_data["categorie_technique"]
features = ['titre', 'description']

X_DataFrame = tickets_data[features]

X_Serie = X_DataFrame["titre"].fillna("") + " " + X_DataFrame["description"].fillna("")

X_list = X_Serie.tolist()


# %% Chargement et modèle

nltk.download("stopwords", quiet = True)
mots_vides = stopwords.words("french") + ["démo", "plusieurs"]
vectorizer = CountVectorizer(stop_words=mots_vides)

umap_model = UMAP(n_neighbors=25, n_components=5, min_dist=0.0, metric="cosine", random_state=42)

embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
model = BERTopic(embedding_model=embedding_model, vectorizer_model=vectorizer, umap_model=umap_model, min_topic_size=10)

embeddings = embedding_model.encode(X_list, show_progress_bar=False)
topics, _ = model.fit_transform(X_list, embeddings)

topics_final = model.reduce_outliers(X_list, topics, strategy="embeddings", embeddings=embeddings)
model.update_topics(X_list, topics=topics_final, vectorizer_model=vectorizer)


# %% Exploration

info = model.get_topic_info()
print(info)


# %% Evaluation

ARI = adjusted_rand_score(y, topics)
NMI = normalized_mutual_info_score(y, topics)

print(f"ARI : {ARI:.2f}")
print(f"NMI : {NMI:.2f}")

print(f"ARI après reduce_outliers : {adjusted_rand_score(y, topics_final):.2f}")
print(f"NMI après reduce_outliers : {normalized_mutual_info_score(y, topics_final):.2f}")

#Sans le bruit
topics_tab = np.array(topics)
mask = (topics_tab != -1)

ARI_Sans_Bruit = adjusted_rand_score(y[mask], topics_tab[mask])
NMI_Sans_Bruit = normalized_mutual_info_score(y[mask], topics_tab[mask])

print(f"ARI_Sans_Bruit : {ARI_Sans_Bruit:.2f}")
print(f"NMI_Sans_Bruit : {NMI_Sans_Bruit:.2f}")
print(f"Proportion de bruit = {(topics_tab == -1).mean():.0%}")

# %% Matrice de confusion

matrice = pd.crosstab(y, topics, colnames=["Groupe"])
print(matrice)

# %% Affichage Resultat
model.visualize_barchart().show()
model.visualize_topics().show()


# %% Noms des groupes par le LLM

load_dotenv()
client = openai.OpenAI(
    api_key=os.getenv("subscription_key"),
    base_url=os.getenv("endpoint"),
     default_headers={"api-key": os.getenv("subscription_key")},
)

prompt = """Voici des tickets d'incidents informatiques d'une banque :
[DOCUMENTS]
Mots-clés du groupe : [KEYWORDS]
Donne un nom court (5 mots maximum, en français) qui décrit le problème commun à ces tickets.
Réponds uniquement par le nom."""

noms = {}
actions = {}
for topic in model.get_topic_info()["Topic"]:
    if topic == -1:
        continue
    mots_cles = ", ".join(mot for mot, _ in model.get_topic(topic)[:10])
    exemples = "\n".join("- " + doc for doc in model.get_representative_docs(topic))

    message = f"""Voici des tickets d'incidents informatiques d'une banque :
{exemples}
Mots-clés du groupe : {mots_cles}
Réponds sur une seule ligne, au format exact :
nom court du problème (5 mots maximum) | action corrective concrète (15 mots maximum)"""

    reponse = client.chat.completions.create(
        model=os.getenv("deployment_name"),
        messages=[{"role": "user", "content": message}],
    )
    texte = reponse.choices[0].message.content.strip()
    nom, _, action = texte.partition("|")
    noms[topic] = nom.strip()
    actions[topic] = action.strip()

model.set_topic_labels(noms)
print(model.get_topic_info()[["Topic", "Count", "CustomName", "Representation"]])

# %% Export pour le tableau de bord
from pathlib import Path

DOSSIER = Path("chatbot/data")
PART_EVITABLE = 0.5  # hypothèse : la moitié des tickets d'un groupe serait évitée par l'action

resultats = tickets_data[["identifiant", "date_creation", "titre", "domaine_metier", "application", "categorie_technique"]].copy()
resultats["date_creation"] = pd.to_datetime(resultats["date_creation"], utc=True)
resultats["groupe"] = topics_final
resultats["nom_groupe"] = resultats["groupe"].map(noms).fillna("À examiner")
resultats.to_csv(DOSSIER / "clusters_tickets.csv", index=False)

fin = resultats["date_creation"].max()
recent = resultats[resultats["date_creation"] > fin - pd.Timedelta(days=30)]
avant = resultats[(resultats["date_creation"] <= fin - pd.Timedelta(days=30)) & (resultats["date_creation"] > fin - pd.Timedelta(days=60))]
nb_mois = (fin - resultats["date_creation"].min()).days / 30

def evolution(groupe):
    n_recent = (recent["groupe"] == groupe).sum()
    n_avant = (avant["groupe"] == groupe).sum()
    if n_avant == 0:
        return "▲ nouveau" if n_recent > 0 else "▶ stable"
    variation = (n_recent - n_avant) / n_avant * 100
    if variation > 10:
        return f"▲ +{variation:.0f} %"
    if variation < -10:
        return f"▼ {variation:.0f} %"
    return "▶ stable"

lignes = []
for groupe, nom in noms.items():
    nb = (resultats["groupe"] == groupe).sum()
    gain = round(nb / nb_mois * PART_EVITABLE)
    lignes.append({
        "Problème récurrent": nom,
        "Tickets": nb,
        "Évolution": evolution(groupe),
        "Action suggérée": actions[groupe],
        "Gain estimé": f"≈ {gain} tickets/mois",
    })

groupes = pd.DataFrame(lignes).sort_values("Tickets", ascending=False)
groupes.to_csv(DOSSIER / "clusters_groupes.csv", index=False)
print(groupes)
