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

topics, _ = model.fit_transform(X_list)


# %% Exploration

info = model.get_topic_info()
print(info)


# %% Evaluation

ARI = adjusted_rand_score(y, topics)
NMI = normalized_mutual_info_score(y, topics)

print(f"ARI : {ARI:.2f}")
print(f"NMI : {NMI:.2f}")

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
for topic in model.get_topic_info()["Topic"]:
    if topic == -1:
        continue
    mots_cles = ", ".join(mot for mot, _ in model.get_topic(topic)[:10])
    exemples = "\n".join("- " + doc for doc in model.get_representative_docs(topic))

    message = f"""Voici des tickets d'incidents informatiques d'une banque :
{exemples}
Mots-clés du groupe : {mots_cles}
Donne un nom court (5 mots maximum, en français) qui décrit le problème commun à ces tickets.
Réponds uniquement par le nom."""

    reponse = client.chat.completions.create(
        model=os.getenv("deployment_name"),
        messages=[{"role": "user", "content": message}],
    )
    noms[topic] = reponse.choices[0].message.content.strip()

model.set_topic_labels(noms)
print(model.get_topic_info()[["Topic", "Count", "CustomName", "Representation"]])

# %%
