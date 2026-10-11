# Indicateurs vidéo complémentaires

Branche `feature/visio-signal-layers`, basée sur `dfdd251` (`visio`). Cinq observations locales sont affichées dans la console, sous Analyse vidéo, pour la source sélectionnée. Ce sont des heuristiques expérimentales : aucun poids GenD PE, score vidéo, score global ou règle de métadonnées n'est changé. Aucun réentraînement ni modèle supplémentaire téléchargé.

## Mesures

| Indicateur | Calcul | Limites |
| --- | --- | --- |
| Rythme et répétitions | Différences entre miniatures 8 × 6 ; gel sur environ 4 s et recherche d'une séquence mobile de six images répétée après au moins 1,5 s, sur 10 s maximum | Une scène immobile, une panne réseau ou des mouvements répétitifs peuvent déclencher l'observation. Ne détecte pas une longue boucle. La cadence affichée est celle de l'analyse, pas celle du capteur. |
| Clignements et mouvements | Rapports d'ouverture des yeux, fermeture puis réouverture entre 50 et 600 ms ; déplacement du centre du visage normalisé par sa largeur | Seuils non personnalisés ; lunettes, pose et faible cadence peuvent masquer les clignements. Aucun nombre de clignements ou immobilité n'entraîne de pénalité. |
| Netteté visage / fond | Rapport de variance du Laplacien sur l'intérieur de la boîte du visage et l'extérieur avec marge, à résolution réduite | Texture du fond et flou portrait influencent le résultat. Pas de score de fraude ; inconnu si texture ou surface insuffisante. |
| Cohérence voix / bouche | Amplitude micro toutes les 50 ms et ouverture de la bouche aux horodatages de capture ; corrélation sur décalages de −800 à +800 ms par pas de 100 ms | Comparaison d'activité sonore, pas de reconnaissance de parole ou de phonèmes. Au moins 35 paires sur 4,5 s et 5 images/s ; silence, activité constante et correspondance faible restent indéterminés. Bruit, autres locuteurs et latence de capture peuvent produire des alertes. |
| Stabilité des contours | Échantillons sur 36 points de l'ovale facial, compensés en position/taille par les repères et centrés en luminosité ; comparaison sur les transitions à faible mouvement, rotation et variation d'éclairage | Le suivi, la compression, les expressions et la pose peuvent créer des variations. Ce n'est pas une segmentation du raccord de face swap. |

Seuils initiaux de démonstration dans `visio-demo/src/video-signals.js`. Ils doivent être évalués sur un corpus indépendant avant toute fusion avec un score de risque. Les tests synthétiques vérifient le calcul et les états ; ils ne démontrent pas une meilleure détection de deepfakes.

## Sources et durée de vie

- Le worker MediaPipe original transmet de petites mesures calculées sur les pixels avant superposition des points. Les images sont réduites à 160 pixels de large pour ces calculs.
- Le face swap est mesuré avec une **seconde instance du même MediaPipe sur les pixels transformés**, plafonnée à 10 images/s, une image en vol, aucune file. Les repères originaux utilisés pour l'affichage du filtre ne sont jamais utilisés pour ces mesures. Cette instance ajoute un coût CPU, à mesurer sur la machine de démonstration.
- Le flux externe réutilise son propre suivi. La cohérence voix/bouche y reste « Audio non associé », car le microphone local ne désigne pas automatiquement le son du partage externe.
- Le filtre intégré conserve l'horodatage de la capture originale pour associer les mesures au son correspondant. Le temps du traitement GPU n'est pas interprété comme un retard labial.
- Historique vidéo : au plus 10 s et 220 petites mesures par source. Audio : au plus 12 s et 250 amplitudes, sans conservation de signal sonore brut. Rafraîchissement de la console au plus toutes les 400 ms par source. Pas de nouvelles requêtes réseau pour les indicateurs.
- Un trou de plus de 700 ms casse l'historique temporel. Les résultats expirent après 2 s depuis la capture. Un visage manquant rend ses mesures inconnues. Absence d'audio récent, silence et cadence trop faible restent inconnus.
- Arrêt caméra, changement de source/portrait, onglet masqué ou fermeture effacent les historiques concernés. Les résultats de workers remplacés sont ignorés. Le micro reste optionnel, utilise la capture existante, n'est jamais diffusé ni enregistré et s'arrête avec la caméra.

## Essais

Tests unitaires : gel, séquences répétées, fermeture/réouverture des yeux, limites de mouvement/luminosité, séparation des sources, trous temporels, reset, silence, décalage audio synthétique, micro absent et audio périmé.

Tests Chromium : MediaPipe réel sur image de fixture ; transport GenD/face swap simulé uniquement par le serveur de tests. Vérification d'un flux transformé vide indépendant du visage original, des cinq états, de l'arrêt, du micro silencieux et de l'affichage desktop/mobile. Les tests de calcul de la console et de pénalité métadonnées restent inchangés.

Validation du 11 octobre 2026 : build Vite réussi, 35 tests unitaires JavaScript, 10 tests Python d'intégration et 47 tests Chromium (38 parcours existants + 9 parcours de la console) réussis. Chromium local 1243 utilisé via `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. Captures desktop/mobile inspectées, sans débordement ni erreur JavaScript dans le parcours ajouté. Aucun essai de précision sur corpus indépendant ni benchmark de charge avec le GPU de production dans cette validation.
