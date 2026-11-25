# Tutoriel du Copilote RUN — texte de la narration

Ce document reprend, scène par scène, le commentaire de la vidéo `tutoriel_copilote_run.mp4`.

## 1. Ouverture

Bienvenue dans le guide du Copilote RUN. Cette application lit vos tickets Jira, en lecture seule. Elle repère les problèmes qui reviennent, chiffre ce qu'ils coûtent, signale les semaines anormales, et vous aide à décider quoi traiter en premier. Retenez une règle : le code calcule, le copilote rédige, et c'est vous qui validez.

## 2. 1 · Tableau de bord — Les quatre indicateurs résument la période analysée

Voici le tableau de bord. En haut, quatre indicateurs. La part des tickets qui relèvent d'un problème connu. Les heures que ces problèmes ont consommées. Le gain annuel estimé si l'on traitait leurs causes. Et le nombre de plans d'action qui attendent votre décision.

## 3. 1 · Tableau de bord — Le menu de gauche donne accès à toutes les pages

À gauche, le menu. La partie pilotage sert à comprendre : problèmes récurrents, pics, gain. La partie opérations sert à agir : copilote, nouveaux tickets, plans d'action et synthèses. Les pastilles colorées indiquent ce qui demande votre attention.

## 4. 2 · Semaine de référence — Choisissez la semaine et la profondeur d'historique

Point très important : l'analyse ne dépend pas de la date du jour. En haut à droite, vous choisissez la semaine de référence. L'application analyse alors comme si l'on était à la fin de cette semaine. Vous pouvez donc revenir sur une semaine passée, ou regarder la semaine en cours. Le second menu règle le nombre de semaines d'historique prises en compte.

## 5. 2 · Semaine de référence — En semaine 9, une alerte de pic apparaît

Sélectionnons la semaine 9. L'analyse se relance en quelques secondes, et un bandeau orange apparaît : un pic anormal sur le batch nocturne, quarante tickets alors qu'on en attendait une quinzaine. C'est le premier endroit à regarder quand vous ouvrez l'application.

## 6. 3 · Problèmes coûteux — Le tableau classe les problèmes par heures consommées

Juste en dessous, les problèmes récurrents les plus coûteux, classés par heures consommées. Pour chacun : le nombre de tickets, la tendance semaine par semaine, le gain annuel possible, et l'état de son plan d'action. Cliquez sur une ligne pour ouvrir la fiche du problème.

## 7. 4 · Fiche d'un problème — Nom précis, description détaillée, solution habituelle

Voici la fiche du batch nocturne. Le nom se veut précis. Si ce nom ne suffit pas, lisez la description détaillée juste en dessous. Vous trouvez aussi les formulations réellement utilisées dans les tickets, les mots caractéristiques, et la solution le plus souvent appliquée, avec le nombre de tickets où elle apparaît.

## 8. 4 · Fiche d'un problème — Volume, coût, gain et semaines de pic

Plus bas, les chiffres du problème : volume, heures consommées, gain estimé et pics détectés. Le graphique montre les tickets semaine par semaine ; la barre foncée est la semaine anormale. À droite, vous pouvez proposer vous-même un plan d'action, sans passer par le copilote.

## 9. 4 · Fiche d'un problème — Tous les tickets du problème, cliquables

En bas de la fiche, la liste des tickets du problème. Chaque clé est cliquable et ouvre le détail du ticket : description, temps passé et résolution. Vous pouvez ainsi toujours vérifier sur quoi repose un chiffre.

## 10. 5 · Groupes à vérifier — Ces groupes ne sont pas comptés comme récurrences

Dans la page Problèmes récurrents, regardez aussi la section du bas : les groupes à vérifier. Ce sont soit un même texte recopié à l'identique, soit des tickets trop différents pour former un seul problème. L'application ne les compte ni dans les récurrences ni dans le gain. À vous de trancher : doublons, gabarit de saisie, ou vrai besoin répété.

## 11. 6 · Pics et alertes — Chaque pic est expliqué : observé, attendu, tickets concernés

La page Pics et alertes détaille chaque semaine anormale. Vous voyez le volume observé, le niveau habituel, la probabilité que ce soit dû au hasard, la solution habituelle, et les tickets de la semaine. Utilisez-la pour décider rapidement s'il faut ouvrir un incident majeur ou prévenir une équipe.

## 12. 7 · Gain estimé — Trois scénarios, pour prioriser et argumenter

La page Gain estimé répond à la question : que gagnerait-on à traiter la cause ? Trois scénarios sont proposés, du plus prudent au plus optimiste. La formule est affichée, et les hypothèses se règlent dans les paramètres. Ce sont des estimations pour prioriser et argumenter, pas des gains acquis.

## 13. 8 · Nouveaux tickets — Collez un ticket : problème connu, solution et tickets similaires

Passons à l'usage quotidien. Dans Nouveaux tickets, collez le titre et la description d'un ticket qui vient d'arriver, puis cliquez sur Analyser. Ici, l'application reconnaît un problème connu. Elle donne la solution habituelle et trois tickets similaires déjà traités. Le technicien gagne du temps dès la prise en charge.

## 14. 8 · Nouveaux tickets — Sous le seuil de ressemblance : nouveau problème

Second exemple : une demande sans rapport avec l'historique. La ressemblance est sous le seuil, l'application répond donc : nouveau problème, à traiter normalement. Elle ne force jamais un rattachement.

## 15. 9 · Copilote — Chaque réponse montre les outils appelés et cite des tickets

Le copilote, maintenant. Posez votre question en français. Au-dessus de chaque réponse, vous voyez les outils qu'il a appelés : c'est la preuve que les chiffres viennent du moteur d'analyse et non de son imagination. Les clés de tickets citées sont cliquables. Si une réponse n'affiche aucun outil, ne vous fiez pas à ses chiffres.

## 16. 9 · Copilote — Un plan proposé attend votre décision

Demandons-lui un plan d'action. Le copilote consulte la fiche du problème, puis enregistre une proposition. Le gain affiché est calculé par le moteur. Le plan n'est pas décidé : trois boutons vous laissent le valider, le modifier ou le rejeter.

## 17. 10 · Plans d'action — Valider, modifier ou rejeter : seul l'humain décide

Tous les plans se retrouvent dans Plans d'action, répartis en trois onglets : à valider, validés, rejetés. Avant de valider, relisez les actions et ouvrez les tickets cités. Le bouton Modifier permet d'ajuster le texte et d'ajouter un commentaire d'équipe. Rien n'est exécuté automatiquement, et rien n'est écrit dans Jira.

## 18. 10 · Plans d'action — Le plan validé reste suivi dans l'onglet Validés

Une fois validé, le plan passe dans l'onglet Validés, et le tableau de bord affiche cet état en face du problème. Vous gardez ainsi la trace de ce qui a été décidé.

## 19. 11 · Synthèse hebdo — Générée par le moteur, exportable en Markdown

En fin de semaine, ouvrez Synthèses hebdo. Choisissez la semaine : l'application rédige le bilan. Volume, alertes, problèmes les plus présents, tickets sans problème connu, et plans en cours. Le bouton Exporter en Markdown télécharge le texte, prêt à être collé dans un compte rendu. Cette synthèse fonctionne même sans intelligence artificielle.

## 20. 12 · Connecteurs et seuils — État des connexions et réglage des seuils

Enfin, Connecteurs et seuils. En haut, l'état de la source des tickets et du modèle de langage. En dessous, les seuils : taille minimale d'un groupe, sensibilité des pics, seuil de nouveauté, hypothèses du gain. Chaque champ rappelle sa valeur par défaut. Ne les changez que si les résultats ne correspondent pas à votre terrain. Si le modèle de langage est indisponible, seul le chat s'arrête : tout le reste continue de fonctionner.

## 21. Routine conseillée

Pour finir, une routine simple. Chaque matin, regardez le bandeau d'alerte, puis passez les nouveaux tickets dans l'outil de rattachement. Chaque lundi, sélectionnez la semaine écoulée et lisez les pics et les problèmes. En point d'équipe, demandez un plan au copilote, puis validez-le ou rejetez-le. Chaque vendredi, exportez la synthèse. Et toujours : ouvrez les tickets cités avant de décider. Bonne utilisation.
