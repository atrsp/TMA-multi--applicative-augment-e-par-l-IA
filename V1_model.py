import sklearn
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay

#Lecture du CSV
tickets_file_path = 'tickets_jira_fictifs.csv'
tickets_data = pd.read_csv(tickets_file_path)
y = tickets_data["categorie_technique"]

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

res = accuracy_score(val_y, rf_val_predictions)
print(res)


ConfusionMatrixDisplay.from_predictions(
    val_y,
    rf_val_predictions,
    xticks_rotation=45,
    cmap="Blues",
)
plt.title("Matrice de confusion – validation")
plt.tight_layout()
plt.show()