"""Récurrences, pics et gain : ce que les groupes veulent dire pour l'équipe RUN.

  1. RÉCURRENCE : un groupe qui revient sur plusieurs semaines, et ce qu'il coûte en heures ;
  2. PIC        : une semaine où un groupe explose anormalement (test de Poisson) ;
  3. GAIN       : les heures économisées par an si l'on traite la cause.

Toutes les fonctions sont de simples calculs : mêmes entrées, mêmes sorties, aucun LLM.
"""
from collections import Counter

from scipy.stats import poisson


def serie_hebdomadaire(numeros_semaine, premiere, derniere):
    """Nombre de tickets par semaine, de `premiere` à `derniere` incluses (0 si aucun).

    numeros_semaine : le numéro de semaine de chaque ticket du groupe.
    Renvoie une liste : serie[0] = semaine `premiere`, serie[1] = la suivante, etc.
    """
    compte = Counter(numeros_semaine)
    return [compte.get(s, 0) for s in range(premiere, derniere + 1)]


def resume_du_groupe(tickets, serie):
    """Volume, régularité et coût d'un groupe.

    tickets : les tickets du groupe (dictionnaires avec « heures », « application », « type »).
    serie   : sa série hebdomadaire (voir serie_hebdomadaire).
    """
    heures = [t["heures"] for t in tickets]
    return {
        "tickets": len(tickets),
        "semaines_actives": sum(1 for n in serie if n > 0),    # dans combien de semaines il apparaît
        "heures_total": round(sum(heures), 1),
        "heures_moy": round(sum(heures) / len(heures), 2) if heures else 0.0,
        "application": valeur_la_plus_frequente(t["application"] for t in tickets),
        "type": valeur_la_plus_frequente(t["type"] for t in tickets),
    }


def valeur_la_plus_frequente(valeurs):
    """La valeur qui revient le plus souvent dans une liste (chaîne vide si la liste est vide)."""
    compte = Counter(v for v in valeurs if v)
    return compte.most_common(1)[0][0] if compte else ""


def est_recurrent(semaines_actives, semaines_min, nb_semaines):
    """Récurrent = étalé dans le temps. Un groupe concentré sur une seule semaine est un
    incident ponctuel, pas une récurrence.

    Si l'on analyse moins de semaines que le seuil (ex. 2 semaines de données), on abaisse
    le seuil au nombre de semaines disponibles, sinon rien ne pourrait être récurrent.
    """
    return semaines_actives >= max(1, min(semaines_min, nb_semaines))


def detecter_pics(serie, premiere, alpha, pic_min, historique):
    """Pour chaque semaine : ce nombre de tickets est-il anormal vu le PASSÉ du groupe ?

    serie      : série hebdomadaire du groupe ; serie[0] correspond à la semaine `premiere`
    alpha      : p-valeur sous laquelle on déclare un pic (0,01 = 1 chance sur 100 par hasard)
    pic_min    : on ignore les « pics » de moins de `pic_min` tickets (trop petits pour agir)
    historique : nombre de semaines de passé exigées avant de chercher des pics

    Principe : si rien d'anormal ne se passe, le nombre de tickets d'une semaine suit une loi
    de Poisson dont la moyenne est le niveau habituel. On estime ce niveau par la MÉDIANE du
    passé (robuste à un ancien pic), puis on calcule la probabilité d'observer autant de
    tickets ou plus. Si elle est minuscule, c'est un pic.
    """
    alertes = []
    for i in range(historique, len(serie)):
        passe = sorted(serie[:i])                      # UNIQUEMENT le passé : pas de triche
        attendu = max(mediane(passe), 0.5)             # 0,5 au minimum pour éviter une moyenne nulle
        observe = serie[i]
        p = float(poisson.sf(observe - 1, attendu))    # P(X >= observe) si rien d'anormal
        if p < alpha and observe >= pic_min:
            alertes.append({"semaine": premiere + i, "observe": observe,
                            "attendu": attendu, "p_valeur": p})
    return alertes


def mediane(valeurs_triees):
    """Médiane d'une liste déjà triée (la valeur du milieu)."""
    n = len(valeurs_triees)
    if n == 0:
        return 0.0
    milieu = n // 2
    if n % 2 == 1:
        return float(valeurs_triees[milieu])
    return (valeurs_triees[milieu - 1] + valeurs_triees[milieu]) / 2


def gain_annuel(heures_total, nb_semaines, taux):
    """Heures économisées par an, pour chaque scénario.

    Formule : (heures consommées / nombre de semaines analysées) x 52 semaines x part évitée.
    taux : dictionnaire {"pessimiste": 0.3, "median": 0.5, "optimiste": 0.8}.
    """
    par_semaine = heures_total / max(nb_semaines, 1)
    return {nom: round(par_semaine * 52 * part) for nom, part in taux.items()}
