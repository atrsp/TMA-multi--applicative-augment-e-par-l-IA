"""Découper le temps en semaines.

Une semaine va du lundi 00h00 au dimanche 23h59. Elle est identifiée par la date de son
lundi (« 2026-07-27 ») : cet identifiant ne dépend pas des tickets chargés.

Pour l'affichage, on donne aussi un numéro court (S1, S2...) : S1 est la semaine du plus
ancien ticket connu.

L'équipe RUN choisit librement la « semaine de référence » : l'analyse est alors faite
comme si l'on était à la fin de cette semaine (les tickets créés après sont ignorés).
"""
from datetime import date, datetime, timedelta


def lire_date(valeur):
    """Transforme une date écrite en texte en objet datetime (heure locale, sans fuseau).

    Accepte les formats de Jira (« 2026-06-01T08:53:00.000+0200 »), ISO (« ...Z ») et les
    dates simples (« 2026-06-01 », « 01/06/2026 »). Renvoie None si la valeur est illisible.
    """
    if isinstance(valeur, datetime):
        return valeur.replace(tzinfo=None)
    texte = str(valeur or "").strip()
    if not texte:
        return None
    try:
        # fromisoformat comprend la plupart des écritures ISO, fuseau compris.
        return datetime.fromisoformat(texte).replace(tzinfo=None)
    except ValueError:
        pass
    for forme in ("%Y-%m-%dT%H:%M:%S.%f%z", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texte, forme).replace(tzinfo=None)
        except ValueError:
            continue
    return None


def lundi_de(jour):
    """Le lundi de la semaine qui contient ce jour (accepte une date ou un datetime)."""
    if isinstance(jour, datetime):
        jour = jour.date()
    return jour - timedelta(days=jour.weekday())     # weekday() : lundi = 0 ... dimanche = 6


def numero_de(lundi, lundi_origine):
    """Numéro court d'une semaine : 1 pour la semaine d'origine, 2 pour la suivante..."""
    return (lundi - lundi_origine).days // 7 + 1


def lundi_du_numero(numero, lundi_origine):
    """L'inverse de numero_de : retrouve le lundi à partir du numéro court."""
    return lundi_origine + timedelta(weeks=numero - 1)


def calendrier(dates, fin_des_donnees, inclure_aujourdhui=False):
    """Liste de toutes les semaines que l'utilisateur peut choisir comme référence.

    dates              : dates de création de tous les tickets connus
    fin_des_donnees    : instant jusqu'où les données sont à jour (dernier ticket, ou
                         heure de la dernière synchronisation Jira)
    inclure_aujourdhui : vrai pour une source « vivante » (Jira) : la semaine en cours est
                         proposée même si elle n'a encore aucun ticket.

    Renvoie une liste de dictionnaires {numero, lundi, complete}, de la plus ancienne à
    la plus récente. « complete » est faux pour une semaine pas encore terminée.
    """
    if not dates:
        return []
    origine = lundi_de(min(dates))
    dernier = lundi_de(max(dates))
    if inclure_aujourdhui:
        dernier = max(dernier, lundi_de(date.today()))
    semaines = []
    lundi = origine
    while lundi <= dernier:
        fin = datetime.combine(lundi + timedelta(days=7), datetime.min.time())
        semaines.append({"numero": numero_de(lundi, origine),
                         "lundi": lundi.isoformat(),
                         "complete": fin <= fin_des_donnees})
        lundi += timedelta(weeks=1)
    return semaines


def semaine_par_defaut(semaines):
    """La semaine de référence choisie automatiquement : la dernière semaine COMPLÈTE.

    Une semaine entamée a peu de tickets ; la prendre par défaut ferait croire à une
    baisse. L'utilisateur peut tout de même la sélectionner à la main.
    """
    completes = [s for s in semaines if s["complete"]]
    return (completes or semaines)[-1] if semaines else None


def libelle(lundi_iso):
    """Texte lisible pour une semaine : « 27/07 au 02/08/2026 »."""
    lundi = date.fromisoformat(lundi_iso)
    dimanche = lundi + timedelta(days=6)
    return f"{lundi:%d/%m} au {dimanche:%d/%m/%Y}"
