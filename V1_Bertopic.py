# %% Imports et données
import pandas as pd
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic


#Lecture du CSV
tickets_file_path = 'tickets_jira_fictifs.csv'
tickets_data = pd.read_csv(tickets_file_path)


# %% Chargement de la Data


features = ['titre', 'description']

X_DataFrame = tickets_data[features]

X_Serie = X_DataFrame["titre"].fillna("") + " " + X_DataFrame["description"].fillna("")

X_list = X_Serie.tolist()



# %% Chargement et modèle


embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
model = BERTopic(embedding_model=embedding_model)

topics, _ = model.fit_transform(X_list)


# %% Exploration

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)


info = model.get_topic_info()
print(info)

# %%
