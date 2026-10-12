import sklearn
import pandas as pd
from sklearn.model_selection import train_test_split


tickets_file_path = '../Users/skanderamor/Desktop/IMT/2A/Commande entreprise/TMA-multi--applicative-augment-e-par-l-IA/tickets_jira_fictifs.csv'
tickets_data = pd.read_csv(tickets_file_path)
y = tickets_data["categorie_predite"]

features = ['titre', 'description']

X = tickets_data[features]
train_X, val_X, train_y, val_y = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

