import sklearn
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier

#Lecture du CSV
tickets_file_path = '../Users/skanderamor/Desktop/IMT/2A/Commande entreprise/TMA-multi--applicative-augment-e-par-l-IA/tickets_jira_fictifs.csv'
tickets_data = pd.read_csv(tickets_file_path)
y = tickets_data["categorie_predite"]

features = ['titre', 'description']

X = tickets_data[features]
train_X, val_X, train_y, val_y = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

train_text_X = train_X["titre"].fillna("") + " " + train_X["description"].fillna("")

val_text_X = val_X["titre"].fillna("") + " " + val_X["description"].fillna("")


tfidf = TfidfVectorizer()
train_X_tfidf = tfidf.fit_transform(train_text_X)
val_X_tfidf = tfidf.transform(val_text_X)



rf_model = RandomForestClassifier(random_state=42)
rf_model.fit(train_X_tfidf, train_y)
rf_val_predictions = rf_model.predict(val_X_tfidf)