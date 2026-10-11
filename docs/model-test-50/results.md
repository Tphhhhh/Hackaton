# Test GenD PE — 25 deepfakes et 25 vidéos authentiques

**48/50 (96 %) décisions correctes** sur ce corpus figé.
Deepfakes repérés : **25/25 (100 %)**.
Authentiques sans alerte : **23/25 (92 %)**.

## Chiffres pour la présentation

| Mesure | Résultat | Intervalle Wilson 95 % descriptif |
| --- | ---: | ---: |
| Décisions correctes sur les 50 vidéos | 48/50 (96 %) | 86.5–98.9 % |
| Deepfakes détectés | 25/25 (100 %) | 86.7–100.0 % |
| Authentiques sans alerte | 23/25 (92 %) | 75.0–97.8 % |
| Fausses alertes | 2/25 (8 %) | 2.2–25.0 % |
| Deepfakes sans alerte (manqués) | 0/25 (0 %) | 0.0–13.3 % |
| Abstentions | 0/50 (0 %) | 0.0–7.1 % |
| Erreurs techniques | 0/50 (0 %) | 0.0–7.1 % |

| Vérité du corpus | Alerte deepfake | Aucun indice | Abstention | Erreur |
| --- | ---: | ---: | ---: | ---: |
| Deepfake | 25 | 0 | 0 | 0 |
| Authentique | 2 | 23 | 0 | 0 |

Les abstentions et erreurs restent dans le dénominateur de 50. Une sortie
« aucun indice » compte comme une décision correcte uniquement pour les clips
étiquetés authentiques ; elle ne prouve pas l'authenticité d'une vidéo inconnue.
La précision des alertes est 25/27 (93 %). Le taux de décisions correctes
conditionnel aux vidéos ayant reçu une décision est 48/50 (96 %).

## Phrase utilisable sur une diapositive

« Sur un test exploratoire de 50 vidéos (25 authentiques et 25 deepfakes),
GenD PE a détecté 25 deepfakes sur 25,
avec 2 fausse(s) alerte(s) sur 25 authentiques,
0 abstention(s) et 0 erreur(s).
Résultats limités à VidTIMIT/DeepfakeTIMIT, sans garantie sur les deepfakes récents. »

## Protocole et limites

### Les deux erreurs observées

| Clip authentique | Score moyen sur 100 | Images au-dessus du seuil | Couverture | Décision |
| --- | ---: | ---: | ---: | --- |
| `timit-real-07` | 45,10 | 50 % | 100 % | Fausse alerte |
| `timit-real-22` | 90,33 | 100 % | 100 % | Fausse alerte |

Le premier clip déclenche une alerte malgré une moyenne inférieure à 50/100 :
la règle actuelle utilise la **proportion d'images dont le score atteint 0,5**,
avec une alerte à partir de 50 % de ces images. Elle n'utilise pas le score moyen
pour décider. Les vidéos locales sont `clips/real-07.mp4` et `clips/real-22.mp4`
dans le corpus `visio/local-data/model-test-50/`.

Le taux de fausses alertes observé, 8 %, dépasse la cible exploratoire de 4 %
définie avant ce test dans le benchmark existant. Le rapport brut indique donc
`below_poc_targets`, même avec 96 % de décisions correctes au total.

### Conditions de l'expérience

- 25 personnes, une phrase `sa1` par personne et sa version face swap `higher_quality`.
- Sélection déterministe (graine 20261011) avant inférence ; six identités du pilote exclues.
- GenD PE, configuration de l'application inchangée : 2 images/s, seuil 0,5 ;
  alerte si au moins 50 % des images utilisables atteignent ce seuil.
- Couverture minimale 80 %, intervalle maximal sans observation 2 s.
- Corpus/configuration/manifeste des modèles gelés avant le test. Aucun entraînement
  ni réglage de seuil à partir de ces 50 vidéos. Sept anciens clips restent en `dev`
  et ne contribuent à aucun chiffre ci-dessus.
- Même encodage final pour les deux classes : MP4 H264 CRF18, 512×384, 25 fps,
  séquence complète, audio retiré. Les compressions antérieures restent différentes.
- Corpus ancien, une famille de manipulation, conditions contrôlées : pas une mesure
  représentative de tous les deepfakes, ni un benchmark de liveness ou de métadonnées.
- Les vrais/truqués sont appariés et certains échanges d'identité sont réciproques.
  Les 50 clips ne sont pas 50 observations indépendantes. Les intervalles Wilson
  ci-dessus sont descriptifs et ne corrigent pas cette dépendance.
- Le modèle a déjà été choisi sur un pilote comprenant d'autres DeepfakeTIMIT :
  nouvelles identités et nouvelles vidéos, mais **pas un nouveau domaine** de validation.

## Sources et attribution

- [DeepfakeTIMIT — dépôt officiel](https://zenodo.org/records/4068245),
  P. Korshunov et S. Marcel, *DeepFakes: a New Threat to Face Recognition?
  Assessment and Detection*, 2018. [Publication](https://arxiv.org/abs/1812.08685).
- [VidTIMIT — dépôt officiel](https://zenodo.org/records/158963),
  C. Sanderson et B. C. Lovell, *Multi-Region Probabilistic Histograms for Robust
  and Scalable Identity Inference*, LNCS 5558, pp. 199–208, 2009.
- Les métadonnées des deux dépôts indiquent CC BY-NC-ND 4.0. Les vidéos converties
  restent locales et ne sont pas redistribuées dans Git.

## Vérifiabilité

Le détail des 50 décisions est dans [results.csv](results.csv), les ratios et
empreintes dans [summary.json](summary.json), les sorties complètes dans
[benchmark.json](benchmark.json). Voir [README.md](README.md) pour relancer.

- Corpus : `6665e9913df134bb7a8612cbb7dc5a2256f244ea6f2a69903a36ffe94f42baac`
- Configuration : `866ffde74c94a1e307ac24fc44c8b6390ecde2c56296162fd7799489e5a05851`
- Manifeste modèles : `f85e51eaeff834f69f24dcc9290ec21143bd486296c238321f2aca2d69d5f344`
