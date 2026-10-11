# GenD CLIP-L/14 — pilote du 10 octobre 2026

Résultat : **2/3 deepfakes détectés, 1/4 faux positifs**, aucune abstention ni erreur technique. Ce résultat ne valide pas une détection fiable : corpus de développement déjà observé, sept vidéos seulement, sources et compressions différentes entre réels et attaques. Seuil 0,5 et fraction 0,5 fixés avant l'inférence, sans ajustement après consultation des résultats.

| Clip | Vérité terrain | Score moyen descriptif | Fraction ≥0,5 | Conclusion | Temps total (s) |
|---|---|---:|---:|---|---:|
| real-01 | real | 0.3351 | 0.219 | no_signal | 19.32 |
| real-02 | real | 0.5856 | 0.605 | verify | 13.48 |
| real-03 | real | 0.0515 | 0.000 | no_signal | 11.28 |
| real-04 | real | 0.1259 | 0.030 | no_signal | 12.36 |
| attack-01 | attack | 0.3118 | 0.200 | no_signal | 6.75 |
| attack-02 | attack | 0.9257 | 1.000 | verify | 6.53 |
| attack-03 | attack | 0.9613 | 1.000 | verify | 6.52 |

`no_signal` ne certifie pas l'authenticité ; `verify` demande une vérification. Les scores sont ceux du modèle, pas une probabilité de fraude. La conclusion utilise la fraction des frames au-dessus du seuil, pas le seul score moyen.

## Comparaison exploratoire sur les mêmes sept médias

| Modèle | Deepfakes repérés | Fausses alertes sur authentiques |
|---|---:|---:|
| Dima ViT CPU | 0/3 | 0/4 |
| Prithiv ViT CPU | 3/3 | 4/4 |
| GenD CLIP-L/14 GPU | 2/3 | 1/4 |

MiniFASNet vise les présentations photo/écran : ces face swaps ne permettent pas d'en mesurer le rappel pertinent. Les poids et configurations antérieurs sont dans les rapports `first-recordings-56673608` et `deepfake-timit-mp4-190072e2`. GenD utilise un prétraitement différent, celui de son dépôt officiel ; il s'agit de comparer des chaînes complètes, pas uniquement des architectures.

## Exécution et vérifications

- RTX 5060 Laptop GPU, 8 151 Mio, PyTorch 2.8.0+cu128 / CUDA 12.8, transformers 4.56.2 ; float32, attention eager, batch 1.
- Pic alloué par PyTorch : **1 185,98 Mio**, pic réservé : **1 212 Mio**. Ce n'est pas la consommation totale de la carte (affichage et autres processus exclus).
- Temps par clip : **6,52–19,32 s**, chargement, vérification des empreintes, décodage et arrêt du worker compris. Nouveau processus pour chaque vidéo ; premières compilations/caches et autres activités locales influencent ces durées. Aucun débit temps réel revendiqué.
- Couverture 100 % des frames échantillonnées pour six clips, 96,4 % pour `real-03` (une frame écartée pour qualité). Cela ne signifie pas que toutes les frames du média sont analysées.
- 42 tests passent dans les environnements CPU et GPU ; `pip check` ne trouve aucune dépendance incohérente dans l'environnement GPU.
- Chargement strict des 394 clés safetensors ; sorties de l'adaptateur exactement égales à celles du code officiel sur deux entrées synthétiques de contrôle CPU (écart maximal des logits : 0). Cela vérifie l'adaptateur, pas la qualité du modèle. Alignement testé sur une référence de pixels.
- Alignement officiel RetinaFace/InsightFace, cinq points, échelle 1,3, taille dynamique ; RGB puis processeur CLIP 224. Ajouts locaux : qualité/abstention, 2 fps, agrégation POC. Pas une reproduction complète du benchmark publié.

## Fichiers et reproduction

`visio/reports/gend-pilot-20261010/benchmark.json` contient toutes les observations et métriques (avec intervalles Wilson très larges). Chaque `real-XX.json` / `attack-XX.json` est importable individuellement par une interface respectant `visio/schema.json`. Le manifeste local `visio/local-data/gend-pilot.json` associe les identifiants aux médias et à leurs empreintes, sans inclure les médias dans Git.

`protocol.json` conserve le protocole fixé avant le test ; `reference-parity-cpu.json` la comparaison au code officiel ; `implementation-hashes.json` les empreintes du code local. Environnement reproductible dans `visio/requirements-gpu.lock.txt`. Poids, licences et versions exactes dans `visio/models.json` et `visio/THIRD_PARTY.md`.

```bash
visio/.venv-gpu/bin/python -m visio benchmark --config visio/config.gend.json --dataset visio/local-data/gend-pilot.json --split dev --output visio/reports/gend-nouvelle-mesure.json
```

Prochaine évaluation utile : nouvelles personnes et manipulations, avec vidéos réelles et truquées issues des mêmes sources et encodages, puis test tenu à l'écart du réglage. Ne pas augmenter le seuil sur ces sept exemples pour faire disparaître une fausse alerte : le deepfake manqué a déjà un score inférieur à plusieurs authentiques.
