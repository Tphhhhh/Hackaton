# Plan de test visio

Proposition du 10 octobre 2026 ; aucun test exécuté. Dépôt Hackaton, recherche démarrée sur main, branche visio constatée au contrôle final.

## Parcours à vérifier après implémentation

- Le collègue lit les exemples JSON sans installer de modèles en moins de cinq minutes ; exemples marqués simulations.
- Une vidéo autorisée traverse validation, décodage, qualité, modèles et résultat versionné. Vérifier la consommation réelle par le module du collègue.
- Qualité insuffisante : nouvelle capture proposée, aucune accusation. Panne technique : erreur explicite, jamais score zéro.
- Annulation/retry : aucune tentative ancienne ne remplace la nouvelle ; nettoyage après chaque sortie, y compris crash et redémarrage.

## Cas techniques

Entrée absente/vide/trop grosse, codec corrompu, durée et résolution trompeuses, orientation, cadence variable, horodatages invalides, absence ou multiplicité de visages, RGB/BGR, crops spécifiques, labels inversés, poids absents ou hash invalide, NaN/Inf, téléchargement indisponible et analyse offline.

Vérifier limites CPU/mémoire/disque et interruption effective sur worker bloqué. Dix soumissions simultanées : une admise, autres refusées sans stocker les captures. Échec de suppression : nouvelles captures refusées jusqu'à résolution vérifiée.

## Agrégation et contrat

Tester manipulation courte, frames inutilisables regroupées, durée variable, détecteurs en désaccord et panne partielle. Tester chaque couple status/conclusion et code CLI ; score absent null, pas zéro. Aucun no_signal si couverture insuffisante d'un détecteur applicable. Vérifier la distinction entre début du média et horloge de capture.

## Évaluation réelle distincte

Unité de test : clip/source indépendante, jamais frame considérée comme candidat indépendant. Développement et test séparés par personne/source et variantes. Figer modèles, seuils, agrégation et prétraitement avant test. Cinquante clips constituent un pilote ; quatre catégories revendiquées demandent au moins 40 attaques indépendantes et 25 authentiques de test, plus développement séparé.

Rapporter effectifs, faux positifs, rappel par attaque avec et sans abstentions, abstention/échecs par classe, couverture, latence p50/p95, temps à froid, pic mémoire et configuration. Les objectifs du plan sont exploratoires, pas des performances déjà obtenues.

## Défis guidés si sélectionnés

Comparer réponse authentique, face swap, replay, défi expiré, mauvaise session, injection vidéo et incapacité à faire le geste. Geste non réalisé, suivi instable et désynchronisation ne sont pas des preuves de fraude. Une vidéo importée ne prouve pas la fraîcheur d'une réponse.

## Critère de livraison

Contrat validé par les deux développeurs, tests techniques passés, benchmark conservant aussi les résultats négatifs et les catégories non évaluées. Aucune ouverture réseau avant contrôle d'accès et séparation de sessions.
