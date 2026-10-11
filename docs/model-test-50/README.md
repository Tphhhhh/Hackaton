# Test du modèle sur 50 vidéos — 11 octobre 2026

Branche : `feature/model-test-50-videos`. Expérience isolée : aucun changement du
modèle, des seuils, du serveur ou de l'interface. Les vidéos et les archives restent
dans `visio/local-data/model-test-50/`, ignoré par Git.

## Livrables

- **Résultat mesuré : 48/50 décisions correctes (96 %), 25/25 deepfakes détectés,
  2/25 fausses alertes (8 %), aucune abstention ou erreur technique.**
- `results.md` : résultats et formulation pour une diapositive.
- `results.csv` : les 50 décisions, scores, couvertures et temps, ouvrable dans Excel.
- `summary.json` : compteurs, ratios, intervalles descriptifs et empreintes.
- `benchmark.json` : résultats bruts de l'outil existant, y compris les observations par image.
- `evaluation.lock.json` : empreintes figées avant inférence.
- `selection.json` et `provenance.json` : sélection, sources, conversions et empreintes des médias.
- `test-inventory.json` : inventaire des 50 clips ; ses chemins se résolvent depuis
  `visio/local-data/model-test-50/`, et non depuis ce dossier de documentation.
- `config.json`, `model-manifest.json`, `code-provenance.json` et `verification.json` :
  réglages, modèles, empreintes du code et vérifications de l'expérience.

Les 50 clips représentent 229,68 secondes de vidéo, avec des durées de 3,72 à
6,32 secondes. Les deux erreurs concernent `timit-real-07` et `timit-real-22`.
Les chiffres sont calculés automatiquement par `visio.model_test_report` ;
le rapport final contient en complément une explication des deux fausses alertes.

## Sélection fixée avant les scores

Le corpus associe 25 vidéos authentiques de VidTIMIT à 25 versions truquées
DeepfakeTIMIT `higher_quality`. Une seule phrase (`sa1`) par personne, soit
25 sources vidéo distinctes et 13 paires d'identités (26 identités impliquées).
Les identités `fadg0`, `fram1`, `faks0`, `fedw0`, `fcft0`, `fdrd1`, déjà examinées
dans le pilote, sont exclues des deux côtés des échanges de visage.

Les 25 personnes sont tirées parmi les 26 restantes, avec la graine `20261011`
sur une liste triée. Aucun remplacement en fonction des prédictions. Les sept
anciens clips du pilote restent dans la partition de développement et sont
exclus du calcul des statistiques des 50 nouveaux clips.

Les classes partagent la phrase, le contexte de capture, la résolution et le
réencodage final : séquence complète, 512×384, 25 fps, H264 CRF18, sans audio.
L'historique de compression diffère : JPEG pour VidTIMIT, vidéo déjà compressée
pour DeepfakeTIMIT. Le script vérifie que chaque conversion conserve le nombre
d'images de sa propre source ; certaines paires ont des durées légèrement
différentes dans les données originales. Les métadonnées conservent ces écarts.

## Reproduire

Depuis la racine du dépôt, avec FFmpeg/ffprobe et Python 3.12 disponibles :

```bash
# Environ 2 Gio d'archives publiques. Téléchargements séquentiels.
python3 -m visio.prepare_model_test_50 \
  --pilot /chemin/vers/visio/local-data/gend-pilot.json

# Utiliser l'environnement GPU et le cache de modèles déjà installés.
PYTHON=/chemin/vers/visio/.venv-gpu/bin/python
MODEL_CACHE=/chemin/vers/visio/.cache

"$PYTHON" -m visio freeze \
  --config visio/config.gend-pe.json \
  --dataset visio/local-data/model-test-50/dataset.json \
  --output visio/reports/model-test-50/evaluation.lock.json

"$PYTHON" -m visio benchmark \
  --config visio/config.gend-pe.json --cache "$MODEL_CACHE" \
  --dataset visio/local-data/model-test-50/dataset.json --split test \
  --evaluation-lock visio/reports/model-test-50/evaluation.lock.json \
  --output visio/reports/model-test-50/benchmark.json

python3 -m visio.model_test_report \
  --report visio/reports/model-test-50/benchmark.json \
  --output visio/reports/model-test-50/export
```

Les sorties existantes ne sont pas écrasées. Pour une autre expérience, utiliser
un nouveau dossier. Le manifeste local inclut des chemins absolus vers les anciens
clips de développement : déplacer ces fichiers change l'empreinte du manifeste,
et impose un nouveau gel avant toute nouvelle inférence. Les clips de test ont des
chemins relatifs. Aucun téléchargement de poids n'a lieu pendant l'inférence.

Le rapport utilise exactement les conclusions du moteur : `verify` (alerte),
`no_signal` (aucun indice), `indeterminate` (abstention) et erreur technique.
Le dénominateur principal reste 50, même en cas d'abstention ou d'erreur. Les scores
ne sont pas des probabilités calibrées. Le test ne mesure ni la présence réelle
en direct ni les signaux du module métadonnées.

## Sources et droits

- [DeepfakeTIMIT, dépôt de l'éditeur](https://zenodo.org/records/4068245).
  P. Korshunov, S. Marcel, *DeepFakes: a New Threat to Face Recognition?
  Assessment and Detection*, 2018. [Article](https://arxiv.org/abs/1812.08685).
- [VidTIMIT, dépôt de l'auteur](https://zenodo.org/records/158963) et
  [documentation de l'auteur](https://conradsanderson.id.au/vidtimit/).
  C. Sanderson, B. C. Lovell, *Multi-Region Probabilistic Histograms for Robust
  and Scalable Identity Inference*, LNCS 5558, pp. 199–208, 2009.

Les deux fiches Zenodo déclarent CC BY-NC-ND 4.0. Usage local de recherche non
commerciale ; les fichiers convertis ne sont pas redistribués. Les fiches sources
et la notice de l'auteur sont conservées avec les archives locales. Les sommes MD5
publiées sont vérifiées sur les archives complètes ; des SHA-256 sont calculés pour
la traçabilité de chaque archive et des vidéos produites.

Ces vidéos et identités sont nouvelles pour ce test local, mais proviennent d'un
domaine déjà utilisé pour choisir GenD PE. Ce corpus ancien et restreint ne permet
pas de conclure à la performance sur les générateurs récents. Les échanges
réciproques et l'appariement introduisent des dépendances entre observations.

## Vérifications du code

```bash
"$PYTHON" -m pytest visio/tests/test_benchmark.py \
  visio/tests/test_gend.py visio/tests/test_model_test_report.py -q
```

Les tests de calcul vérifient notamment que les erreurs et abstentions restent
dans le dénominateur, et que les exports refusent les simulations et les comptes
incohérents. Ils ne constituent pas une mesure de la qualité du détecteur.
