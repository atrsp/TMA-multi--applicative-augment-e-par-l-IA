"""
=====================================================================================
ÉTAPE 2 : RÉCURRENCES, PICS ET GAIN
=====================================================================================
Le clustering dit « ces tickets parlent du même problème ». Ce script transforme
ces groupes en informations utiles à l'équipe RUN :
  1. RÉCURRENCES : quels groupes reviennent régulièrement, et combien d'heures ils coûtent ;
  2. PICS        : quelles semaines un groupe explose anormalement (test de Poisson) ;
  3. GAIN        : combien d'heures par an on économiserait en traitant la cause.

Usage : python3 recurrences.py sbert 30      (méthode, puis min_cluster_size)
        Ajouter "verite" à la fin pour tout recalculer avec les VRAIES familles
        (python3 recurrences.py sbert 30 verite) : c'est la référence « clustering parfait ».
=====================================================================================
"""
import json
import sys

import pandas as pd
from scipy.stats import poisson          # la loi de Poisson, pour tester les pics
from sklearn.cluster import HDBSCAN

from baseline_clustering import DATA, charger, vectoriser

# ----------------------------------------------------------------------------------
# HYPOTHÈSES : toutes au même endroit, pour pouvoir les discuter et les faire varier.
# ----------------------------------------------------------------------------------
TAILLE_MIN = 10        # un groupe récurrent a au moins 10 tickets...
SEMAINES_MIN = 4       # ... répartis sur au moins 4 semaines différentes
ALPHA = 0.01           # p-valeur sous laquelle on déclare un pic (1 chance sur 100 par hasard)
PIC_MIN = 5            # on ignore les « pics » de moins de 5 tickets (trop petits pour agir)
HISTORIQUE = 4         # semaines d'historique avant de commencer à chercher des pics
TAUX_EVITES = {"pessimiste": 0.3, "median": 0.5, "optimiste": 0.8}  # part des tickets évités


def construire_tableau(methode, taille, colonne):
    """Un tableau pandas : une ligne par ticket, avec sa date, son temps passé et son groupe."""
    issues = json.loads((DATA / "tickets.json").read_text(encoding="utf-8"))["issues"]
    cles, textes, vrai = charger()                 # même ordre que issues

    if colonne == "verite":                        # référence : on prend les vraies familles
        groupes = [-1 if f == "AUCUNE" else f for f in vrai]
    else:                                          # cas réel : les groupes trouvés par HDBSCAN
        X = vectoriser(textes, methode)
        groupes = HDBSCAN(min_cluster_size=taille, copy=True).fit_predict(X)

    df = pd.DataFrame({
        "cle": cles,
        "titre": [t["fields"]["summary"] for t in issues],
        "app": [t["fields"]["components"][0]["name"] for t in issues],
        "cree": pd.to_datetime([t["fields"]["created"] for t in issues]),
        "heures": [t["fields"]["timespent"] / 3600 for t in issues],  # Jira stocke des secondes
        "famille": vrai,
        "groupe": groupes,
    })
    # Numéro de semaine : 1 pour la première semaine des données, 2 pour la suivante, etc.
    debut = df["cree"].min().normalize()           # minuit le premier jour
    df["semaine"] = (df["cree"] - debut).dt.days // 7 + 1
    # On ne garde que les semaines COMPLÈTES : une semaine coupée à la fin des données
    # aurait peu de tickets, ce qui fausserait la moyenne et la détection de pics.
    completes = (df["cree"].max() - debut).days // 7
    return df[df["semaine"] <= completes].reset_index(drop=True)


def recurrences(df):
    """Un résumé par groupe : volume, régularité, coût en heures."""
    nb_semaines = df["semaine"].max()
    g = df[df["groupe"] != -1].groupby("groupe")   # on laisse le bruit de côté
    res = pd.DataFrame({
        "tickets": g.size(),
        "semaines_actives": g["semaine"].nunique(),       # dans combien de semaines il apparaît
        "heures_total": g["heures"].sum().round(1),
        "heures_moy": g["heures"].mean().round(2),
        "app": g["app"].agg(lambda s: s.mode()[0]),       # l'application la plus fréquente
        "famille_maj": g["famille"].agg(lambda s: s.mode()[0]),
        "exemple": g["titre"].agg(lambda s: s.mode()[0]),
    })
    res["par_semaine"] = (res["tickets"] / nb_semaines).round(1)
    # Récurrent = assez gros ET étalé dans le temps (un pic isolé n'est pas une récurrence).
    res["recurrent"] = (res["tickets"] >= TAILLE_MIN) & (res["semaines_actives"] >= SEMAINES_MIN)
    return res.sort_values("heures_total", ascending=False)


def pics(df):
    """Pour chaque groupe et chaque semaine : ce nombre de tickets est-il anormal vu le passé ?"""
    nb_semaines = df["semaine"].max()
    alertes = []
    for groupe, sous in df[df["groupe"] != -1].groupby("groupe"):
        # Série hebdomadaire : nombre de tickets par semaine, 0 si aucun.
        serie = sous["semaine"].value_counts().reindex(range(1, nb_semaines + 1), fill_value=0)
        for s in range(HISTORIQUE + 1, nb_semaines + 1):
            passe = serie.loc[1:s - 1]                 # UNIQUEMENT le passé : pas de triche
            attendu = max(passe.median(), 0.5)         # médiane : robuste à un ancien pic
            observe = int(serie.loc[s])
            p = poisson.sf(observe - 1, attendu)       # P(X >= observe) si rien d'anormal
            if p < ALPHA and observe >= PIC_MIN:
                alertes.append({"groupe": groupe, "semaine": s, "observe": observe,
                                "attendu": attendu, "p_valeur": float(f"{p:.1e}")})
    return pd.DataFrame(alertes, columns=["groupe", "semaine", "observe", "attendu", "p_valeur"])


def gain(rec, nb_semaines):
    """Heures économisées par an si l'on traite la cause d'un groupe récurrent."""
    rec = rec[rec["recurrent"]].copy()
    par_semaine_h = rec["heures_total"] / nb_semaines
    for nom, taux in TAUX_EVITES.items():
        rec[f"gain_an_{nom}"] = (par_semaine_h * 52 * taux).round(0)
    return rec


def main():
    methode = sys.argv[1] if len(sys.argv) > 1 else "tfidf"
    taille = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    colonne = "verite" if "verite" in sys.argv else "groupe"

    df = construire_tableau(methode, taille, colonne)
    nb_semaines = df["semaine"].max()

    rec = recurrences(df)
    part = df["groupe"].isin(rec.index[rec["recurrent"]]).mean()
    print(f"\n=== RÉCURRENCES ({len(df)} tickets, {nb_semaines} semaines) ===")
    print(f"{part:.0%} des tickets appartiennent à un groupe récurrent")
    print(rec.drop(columns="exemple").to_string())

    alertes = pics(df)
    print("\n=== PICS DÉTECTÉS ===")
    print(alertes.to_string(index=False) if len(alertes) else "aucun pic")

    gains = gain(rec, nb_semaines)
    print("\n=== GAIN ANNUEL ESTIMÉ (heures/an) ===")
    print(gains[["exemple", "heures_total", "gain_an_pessimiste",
                 "gain_an_median", "gain_an_optimiste"]].to_string())

    # Export au format « résultats » (contrat ② avec l'équipe chatbot / MCP).
    sortie = []
    for groupe, ligne in gains.iterrows():
        sortie.append({
            "groupe": str(groupe),
            "exemple": ligne["exemple"],
            "application": ligne["app"],
            "tickets": int(ligne["tickets"]),
            "semaines_actives": int(ligne["semaines_actives"]),
            "heures_total": float(ligne["heures_total"]),
            "gain_annuel_h": {n: float(ligne[f"gain_an_{n}"]) for n in TAUX_EVITES},
            "pics": alertes[alertes["groupe"] == groupe][["semaine", "observe", "attendu"]]
                    .to_dict("records"),
            "tickets_exemples": df[df["groupe"] == groupe]["cle"].head(5).tolist(),
        })
    suffixe = "verite" if colonne == "verite" else f"{methode}_{taille}"
    fichier = DATA.parent / "analysis" / f"recurrences_{suffixe}.json"
    fichier.write_text(json.dumps(sortie, ensure_ascii=False, indent=2, default=int),
                       encoding="utf-8")
    print(f"\nRésultats enregistrés dans {fichier.name}")


if __name__ == "__main__":
    main()
