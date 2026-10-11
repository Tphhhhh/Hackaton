# Vérification du prétraitement GenD — 10 octobre 2026

## Conclusion

Aucun écart de prétraitement trouvé sur les 38 images analysées de Ludo et les 10 images analysées de deepfake 01. Les pixels décodés, les détections, les recadrages et les tenseurs d'entrée sont identiques à la référence contrôlée. Les scores précédents sont reproduits exactement.

Cela écarte, sur ces deux fichiers et ces instants, une inversion RGB/BGR, un mauvais alignement, une normalisation différente ou une modification des images analysées due au tracking. Cela ne prouve pas la fiabilité générale de GenD.

La sélection temporelle reste une différence réelle avec le protocole officiel. Une expérience diagnostique à 32 images change le résultat de Ludo, mais ne résout pas le faux négatif de deepfake 01. Aucun seuil, modèle, traitement de production ou résultat de l'application n'a été modifié.

## Références et méthode

- Code [GenD officiel](https://github.com/yermandy/GenD/tree/387a42266dd385fbe8f7626c5d3aa03eea3bfaab), commit `387a42266dd385fbe8f7626c5d3aa03eea3bfaab`. Les trois fichiers de référence ont été téléchargés à nouveau depuis ce commit et comparés octet par octet aux copies précédemment relues.
- Checkpoint CLIP-L/14, révision `891ce014a0308386c4d7d25b3dcf436a22db5504`. Les empreintes des poids et configurations sont vérifiées par le manifeste avant l'audit.
- Égalité des arbres syntaxiques de toutes les fonctions/classes du localisateur RetinaFace utilisé en production avec l'original. Les différences de fichier sont la suppression du téléchargement et du programme de démonstration, plus la notice locale.
- Exécution de la fonction `align_face` extraite du code officiel vérifié, dans un espace séparé. Échelle 1,3, taille dynamique, interpolation linéaire, cinq points.
- Décodage de référence PyAV en RGB puis conversion BGR, comme le chemin couleur de `imageio`/PyAV dans le code officiel. L'API d'indexation `imageio` elle-même n'a pas été exécutée. Comparaison avec les frames BGR réellement retournées par notre pipeline, aux mêmes horodatages.
- Détection de référence avec une seconde instance du localisateur, mêmes poids et paramètres : CPU, 640 × 640, seuil 0,1, NMS 0,4.
- Capture du tenseur renvoyé par le processeur pendant l'appel réel à `GenDDetector.predict_with_quality`.
- Référence image : recadrage officiel, sauvegarde PNG sans perte, lecture PIL RGB, méthode officielle `CLIPEncoder.preprocess`, processeur CLIP chargé séparément depuis la configuration épinglée.
- Les tenseurs de référence sont ensuite évalués par **le même réseau chargé** : cette partie vérifie le prétraitement, pas une seconde implémentation indépendante du réseau complet. La parité d'architecture antérieure est conservée dans `visio/reports/gend-pilot-20261010/reference-parity-cpu.json` (deux tenseurs synthétiques, poids strictement chargés, logits identiques).

## Résultats aux instants de production

| Contrôle | Ludo (38 images) | Deepfake 01 (10 images) |
| --- | --- | --- |
| Écart maximal des pixels décodés | 0 | 0 |
| Écart maximal boîtes et points | 0 | 0 |
| Écart maximal des pixels alignés | 0 | 0 |
| Écart maximal du tenseur normalisé | 0 | 0 |
| Écart maximal du score avec l'entrée de référence | 0 | 0 |
| Écart maximal avec chaque score du premier benchmark | 0 | 0 |
| Instants d'analyse avec/sans tracking | Identiques | Identiques |
| Bord ajouté hors image par l'alignement | 0 % | 0 % |
| Taille du recadrage avant entrée CLIP 224 × 224 | 297–355 px | 245–255 px |
| Score moyen /100 | 58,56 | 31,18 |
| Part des images au-dessus du seuil 0,5 | 60,53 % | 20 % |

Inspection visuelle des planches : visage correctement ciblé, points sur les yeux, le nez et la bouche, orientation et couleurs cohérentes. Les planches incluent les scores minimal/maximal, le début, le milieu et la fin des observations. Aucun masque de points n'est dessiné dans l'entrée du modèle : les annotations sont ajoutées seulement sur la copie de présentation de l'image source.

Ludo présente des scores allant de 6,05 à 96,62/100 malgré un recadrage conforme. La différence n'est pas expliquée par un bogue RGB/BGR ou des bords noirs dans cette comparaison. Sa cause visuelle précise reste non établie ; aucune attribution à l'éclairage ou à la compression n'est démontrée ici.

## Expérience sur la sélection temporelle

Comparaison prédéfinie : premiers 32 indices de la fonction officielle `max_spread_permutation_pq`, en démarrant au milieu de la vidéo, comme `mode=at_least, n=32`. Chaque image retenue contient un visage utilisable, donc aucun remplacement pour rejet de qualité n'est nécessaire sur ces clips. Même modèle, alignement, processeur et seuils. Cette expérience n'est pas une reproduction de tous les benchmarks publiés.

| Vidéo | Production 2 fps : moyenne /100 | Sélection officielle 32 : moyenne /100 | Part signalée avec 32 images |
| --- | --- | --- | --- |
| Ludo, authentique | 58,56 | 48,21 | 43,75 % (14/32) |
| Deepfake 01, truqué | 31,18 | 32,40 | 25 % (8/32) |

Avec notre règle locale (au moins la moitié des images au-dessus de 0,5), Ludo ne serait plus signalé sur cette sélection ; deepfake 01 resterait manqué. Cela montre une sensibilité à l'échantillonnage, sans valider un changement de protocole pour toutes les vidéos. Il faut évaluer tout protocole proposé sur les autres clips et un ensemble inédit avant de le retenir.

## Artifacts locaux et reproduction

Les images privées et sorties détaillées restent dans le répertoire ignoré par Git `visio/reports/preprocessing-audit-20261010/` :

- `audit.json` : scores par image, horodatages, comparaisons, empreintes, sélection de 32 images.
- `ludo-crops.png` et `deepfake-01-crops.png` : source annotée / recadrage / entrée exacte du modèle dénormalisée pour affichage.
- Trois copies vérifiées du code public de référence, sans exécution de leurs imports, téléchargements ou programmes principaux par l'audit.

Depuis la racine du dépôt, avec accès au GPU local :

```bash
visio/.venv-gpu/bin/python -m visio.audit_gend_preprocessing \
  --reference visio/reports/preprocessing-audit-20261010 \
  --output visio/reports/preprocessing-audit-repeat
```

Les 21 tests ciblés GenD, média et intégration passent, dont la comparaison d'orientation 90° avec FFmpeg. Les deux vidéos auditées n'ont pas de rotation. L'audit n'établit pas l'équivalence sur tous les codecs/espaces colorimétriques, ne mesure pas l'effet de la conversion AVI → MP4 et ne valide pas les performances sur des vidéos inédites.

Statut : vérification terminée, avec réserves sur la qualité de détection et la stabilité temporelle. Aucun correctif de prétraitement justifié par les observations. Suite recommandée : comparaison de détecteurs et de protocoles sur un corpus plus large, sans ajustement au seul cas Ludo.
