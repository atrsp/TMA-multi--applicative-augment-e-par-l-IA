# %% Imports et données
import pandas as pd
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
import matplotlib.pyplot as plt


#Lecture du CSV
tickets_file_path = 'tickets_jira_fictifs.csv'
tickets_data = pd.read_csv(tickets_file_path)


# %% Chargement de la Data

y = tickets_data["categorie_technique"]
features = ['titre', 'description']

X_DataFrame = tickets_data[features]

X_Serie = X_DataFrame["titre"].fillna("") + " " + X_DataFrame["description"].fillna("")

X_list = X_Serie.tolist()



# %% Chargement et modèle

nltk.download("stopwords")
mots_vides = stopwords.words("french") + ["démo", "plusieurs"]
vectorizer = CountVectorizer(stop_words=mots_vides)

embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
model = BERTopic(embedding_model=embedding_model, vectorizer_model=vectorizer)

topics, _ = model.fit_transform(X_list)


# %% Exploration

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)


info = model.get_topic_info()
print(info)

# %% Accuracy

ARI = adjusted_rand_score(y, topics)
NMI = normalized_mutual_info_score(y, topics)

print(f"ARI : {ARI:.2f}")
print(NMI)

# %% Matrice de confusion

matrice = pd.crosstab(y, topics)
plt.show()

# %% Affichage Resultat
model.visualize_barchart().show()
model.visualize_topics().show()

# %% Noms des groupes par le LLM
import os
import openai
from dotenv import load_dotenv
from bertopic.representation import OpenAI

load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

prompt = """Voici des tickets d'incidents informatiques d'une banque :
[DOCUMENTS]
Mots-clés du groupe : [KEYWORDS]
Donne un nom court (5 mots maximum, en français) qui décrit le problème commun à ces tickets.
Réponds uniquement par le nom."""

nommeur = OpenAI(client, model="NOM_DU_MODELE", prompt=prompt, chat=True, nr_docs=4, delay_in_seconds=1)

model.update_topics(X_list, vectorizer_model=vectorizer, representation_model={"LLM": nommeur})
print(model.get_topic_info()[["Topic", "Count", "Representation", "LLM"]])