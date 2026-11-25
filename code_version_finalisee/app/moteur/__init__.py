"""Moteur d'analyse : calcul exact, SANS LLM.

Chaque fichier a une seule responsabilité :
    nettoyage.py       nettoyer le texte des tickets
    semaines.py        découper le temps en semaines (du lundi au dimanche)
    vecteurs.py        transformer les textes en vecteurs (SBERT) + cache disque
    groupes.py         regrouper les tickets qui se ressemblent (HDBSCAN)
    etiquettes.py      mots-clés, titres représentatifs, description d'un groupe
    recurrences.py     récurrences, pics (test de Poisson), gain annuel
    nouveau_ticket.py  rattacher un nouveau ticket à un problème connu
    synthese.py        synthèse hebdomadaire en Markdown
    pipeline.py        enchaîner toutes les étapes
"""
