# GenD PE dans l'interface locale — 10 octobre 2026

Le serveur `python -m visio.server --port 8765` sélectionne désormais `visio/config.gend-pe.json`. Le bouton affiche **Analyser avec GenD PE** et les résultats exposent `detectors.gend_pe`, révision `4fd5a38cf071af2640d314110826ed5cd25cab88`. La CLI CLIP reste disponible avec `config.gend.json`.

## Intégration

Adaptateur `visio/gend_pe.py` : architecture timm 1.0.20, checkpoint safetensors complet vérifié par taille et SHA-256, chargement strict des 310 clés, float32, CUDA, batch 1. Aucun téléchargement implicite ni import du banc de comparaison. Les poids PE déjà téléchargés ont été revérifiés et installés dans le cache de production. `models.json` permet de les récupérer explicitement sur une autre installation.

Le localisateur et l'alignement restent identiques au banc d'essai. La localisation à 8 fps alimente le contrat de coordonnées existant ; seules les images prévues à 2 fps sont classifiées. Pas de modification des contrats JSON ni du module métadonnées. Les points sont disponibles après traitement, puis synchronisés avec la lecture ; ceci n'implémente pas l'analyse live.

## Essais réels depuis Chromium

Sur `http://127.0.0.1:8765/`, RTX 5060 Laptop, fichiers sélectionnés avec le champ d'import puis bouton d'analyse :

| Extrait | Score PE / 100 | Conclusion | Images classifiées | Images de localisation | Temps complet |
|---|---:|---|---:|---:|---:|
| Ludo authentique | 11,23 | aucun indice détecté | 38 | 152 | 52,47 s |
| deepfake 01 | 70,65 | indice à vérifier | 10 | 38 | 17,40 s |

Les scores complets correspondent exactement à ceux de la comparaison isolée. Cinq points effectivement visibles après déplacement de la lecture à une seconde pour chaque clip. Annulation d'une troisième analyse puis retrait du clip : aucun résultat ni point résiduel. Aucune erreur JavaScript ; vue mobile sans débordement horizontal.

Le premier chargement a pris 21,81 s ; l'analyse et la localisation de Ludo 28,82 s. Pic RSS du worker 2 064 Mio et pic CUDA alloué 1 228 Mio. Les limites existantes (60 s et 4 Gio RSS) restent actives ; ces durées ne constituent pas une garantie sous charge. Le tracking CPU dense représente une part importante du temps total.

Preuves locales ignorées par Git : `visio/reports/gend-pe-integration/` contient les deux bundles JSON complets, captures et `browser-check.json`.

Validation automatique : **57 tests Python, 20 tests unitaires frontend, 20 tests navigateur réussis**, build Vite réussi. Les nouveaux contrôles couvrent le routage PE, l'abstention, l'absence de repli CPU, la réutilisation des localisations à 8 fps pour conserver l'analyse à 2 fps, le statut serveur et l'affichage des résultats PE.

Ces scores sont des indices non calibrés, pas des probabilités. Les deux vidéos ont déjà servi au développement ; cet essai vérifie l'intégration, pas la généralisation du modèle. Les conditions des poids sont détaillées dans `visio/THIRD_PARTY.md`.
