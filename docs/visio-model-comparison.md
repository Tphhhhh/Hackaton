# Comparaison locale GenD CLIP, GenD PE et Effort — 10 octobre 2026

## Décision proposée

**GenD PE est le meilleur candidat sur les sept vidéos disponibles.** Il détecte les trois deepfakes et ne signale aucune des quatre vidéos authentiques, contrairement à GenD CLIP et à la copie d'Effort évaluée. Recommander GenD PE pour la prochaine expérimentation, puis vérifier sur de nouvelles vidéos avant de conclure à un gain généralisable.

Ce comparatif est isolé du moteur de démo et du tracking. Il ne remplace pas le modèle de l'application et ne réentraîne aucun réseau.

## Résultats

Scores moyens de manipulation sur 100, **pas des probabilités calibrées** :

| Extrait | Vérité fournie | GenD CLIP | GenD PE | Effort, copie publique* |
| --- | --- | ---: | ---: | ---: |
| Gui | Authentique | 33,51 | 1,31 | 30,86 |
| Ludo | Authentique | 58,56 | 11,23 | 34,95 |
| Rob | Authentique | 5,15 | 0,82 | 20,63 |
| Théophile | Authentique | 12,59 | 0,60 | 49,87 |
| Deepfake 01 | Truqué | 31,18 | 70,65 | 38,75 |
| Deepfake 02 | Truqué | 92,57 | 98,72 | 97,76 |
| Deepfake 03 | Truqué | 96,13 | 99,95 | 98,81 |

La conclusion de notre POC est déterminée par la **part d'images dépassant 0,5**, et non par la seule moyenne affichée : au moins 50 % des images utilisables doivent dépasser ce seuil. C'est pourquoi Effort signale Théophile malgré une moyenne de 49,87/100 : 17 images sur 33 (51,52 %) dépassent 0,5.

| Mesure au niveau vidéo | GenD CLIP | GenD PE | Effort* |
| --- | ---: | ---: | ---: |
| Deepfakes détectés | 2/3 | 3/3 | 2/3 |
| Authentiques signalés à tort | 1/4 (Ludo) | 0/4 | 1/4 (Théophile) |
| Vidéos indéterminées | 0/7 | 0/7 | 0/7 |
| Erreurs techniques | 0/7 | 0/7 | 0/7 |

Les deux GenD s'abstiennent sur une image de Rob où plusieurs visages sont détectés (27/28 images utilisables). Effort accepte les 28 images avec son localisateur différent. Toutes les autres couvertures sont de 100 % des images échantillonnées.

**\* Réserve Effort :** le lien Google Drive des auteurs expire depuis cet environnement, y compris lors d'un essai hors bac à sable. Le fichier testé vient du [miroir public boom2511/effort](https://huggingface.co/boom2511/effort/tree/033bbdbfd5aec5f3266e6c2d356ac2452c79461e), dont la taille et l'empreinte LFS sont vérifiées. **L'égalité de ce fichier avec le checkpoint officiel n'a pas pu être confirmée.** Les résultats décrivent donc cette copie et notre adaptateur vérifié, sans établir une conclusion définitive sur les poids publiés par les auteurs.

## Protocole

- Même corpus `visio/local-data/gend-pilot.json`, sept fichiers dont les empreintes et autorisations sont vérifiées. Quatre prises authentiques confirmées par l'utilisateur et trois DeepfakeTIMIT convertis localement en MP4.
- Identité des fichiers et des horodatages vérifiée entre les trois rapports ; 2 images/s, 40 images maximum. Aucun ajustement sur les résultats et aucun fine-tuning.
- Float32, batch 1, RTX 5060 Laptop, même environnement PyTorch 2.8.0 CUDA 12.8. Un modèle par processus, exécutions GPU successives.
- Mêmes seuils et règles d'agrégation du POC, couverture minimale 80 %, intervalle maximal entre observations 2 s.
- Prétraitements spécifiques respectés : il serait incorrect de donner arbitrairement le même recadrage et la même normalisation aux trois réseaux.
- Les sorties demeurent des indices visuels. La présence actuelle et l'identité ne sont pas évaluées. Aucun score métadonnées n'est intégré ici.

## Temps et mémoire mesurés

Deuxième passage séquentiel, après la fin de toutes les installations/compilations. Les scores et conclusions par image sont **exactement identiques** au premier passage pour les trois modèles. Le corpus représente 77,28 secondes de vidéo au total.

| Mesure locale | GenD CLIP | GenD PE | Effort* |
| --- | ---: | ---: | ---: |
| Chargement initial et vérification des fichiers | 1,79 s | 5,49 s | 2,04 s |
| Traitement des sept vidéos, modèle chargé | 43,18 s | 38,46 s | 43,60 s |
| Traitement de Ludo (19,03 s de vidéo) | 10,69 s | 9,23 s | 12,42 s |
| Pic de mémoire CUDA allouée par PyTorch | 1 186 Mio | 1 228 Mio | 1 183 Mio |

Ces temps incluent le décodage, la localisation/qualité et l'inférence à 2 fps. Ils excluent le tracking dense à 8 fps, le serveur et l'interface. Le chargement n'est fait qu'une fois par modèle dans ce banc d'essai. Les valeurs restent indicatives sur cette machine, avec caches locaux déjà remplis ; il ne s'agit pas d'un test de latence garanti ni d'une démonstration d'analyse live. Le pic PyTorch n'inclut pas toute la mémoire réservée par le pilote CUDA.

## Modèles et prétraitements

### GenD CLIP-L/14

Adaptateur existant inchangé. Révision des poids `891ce014a0308386c4d7d25b3dcf436a22db5504`. Alignement InsightFace cinq points, échelle 1,3, taille dynamique ; processeur CLIP RGB 224, normalisation CLIP. Les scores du premier benchmark sont reproduits exactement.

### GenD PE-L

[Poids officiels](https://huggingface.co/yermandy/GenD_PE_L), révision `4fd5a38cf071af2640d314110826ed5cd25cab88`, SHA-256 `e2367f8db3a6b76f8d5cc5857f1ed0ea0993b33c9e1f428d3b06e5ca95de2213`.

Architecture `vit_pe_core_large_patch14_336`, `timm==1.0.20`, taille dynamique ; entrée forcée à 224 conformément à GenD. Même alignement que GenD CLIP, mais normalisation **moyenne 0,5 / écart-type 0,5**, resize bicubique et crop central. Sortie de l'encodeur normalisée L2 puis tête linéaire. Chargement strict des 310 clés du checkpoint complet, sans téléchargement d'un second backbone.

Parité contrôlée avec le code officiel de GenD chargé séparément : sur une image de Ludo et une image de deepfake 01, **écart maximal des tenseurs et des logits = 0**. L'initialisation du backbone préentraîné est désactivée dans la référence pour éviter un téléchargement redondant ; tous les poids finaux proviennent du checkpoint GenD, chargé strictement.

DINOv3 n'a pas été évalué : sa configuration et son processeur de base renvoient HTTP 401 sans autorisation Hugging Face. GenD PE permet une comparaison avec une deuxième variante officielle sans contourner cet accès.

### Effort CLIP-L/14, entraîné sur FF++ selon le nom du fichier miroir

[Code officiel Effort](https://github.com/YZY-stack/Effort-AIGI-Detection/tree/96f5dea2b534d400cfd7003f053c7e93c8e16461), [prétraitement DeepfakeBench](https://github.com/SCLBD/DeepfakeBench/tree/f188b1c105465e2e5377eb536a95022ae0e4522d).

Copie des poids : 1 213 769 519 octets, SHA-256 `8d86711f098d16b49c048962fc3e16a906380f7bb17b8a0e89bd545b926943ee`. Chargement `torch.load(weights_only=True, mmap=True)` ; aucun objet Python arbitraire du checkpoint n'est exécuté. Préfixe `module.` retiré et résidus SVD fusionnés dans les matrices linéaires, puis chargement strict. La tête Effort utilise le pooler CLIP **sans normalisation L2**.

Prétraitement du benchmark : dlib frontal + prédicteur 81 points, points 37/44/30/49/55, transformation de similarité, échelle 1,3, crop 256, RGB, resize cubique vers 224, normalisation CLIP. Les garde-fous de taille/exposition et d'un seul visage entraînent une abstention, jamais un score fabriqué. Ce chemin correspond au benchmark ; le script de démonstration Effort propose aussi un crop direct 224, non utilisé ici.

Parité contrôlée sur les images de Ludo et deepfake 01 : recadrage identique au code officiel ; logits identiques au réseau officiel avec modules SVD non fusionnés. **Écarts maximaux = 0** sur ces contrôles. Cela vérifie l'adaptation du code, sans authentifier le fichier miroir contre Google Drive.

## Limites et suite

Les sept clips ont déjà été examinés pendant le développement. Les authenticités et les deepfakes viennent de sources et conditions de compression différentes. **Zéro erreur sur ces sept clips n'est pas une estimation fiable de la performance future.** Ce n'est pas un ensemble de test indépendant ni une reproduction des benchmarks publiés.

Suite recommandée : évaluer GenD PE sur de nouveaux authentiques et deepfakes, avec plusieurs personnes et générateurs et des conditions de capture comparables. Conserver les désaccords et faux positifs dans le rapport. La meilleure moyenne entre plusieurs détecteurs ou le seuil optimal ne doivent pas être choisis sur ces sept exemples puis présentés comme validés.

## Fichiers et reproduction

- `visio/compare_models.py` : banc d'essai isolé, sans import dans le serveur.
- `visio/comparison_effort_face.py` : adaptation attribuée du prétraitement Effort ; licence complète dans `visio/licenses/DeepfakeBench-CC-BY-NC-4.0.txt`.
- `visio/tests/test_comparison.py` : fusion SVD, résidu incomplet, tête sans L2, alignement de référence.
- `visio/reports/model-comparison-20261010/` (ignoré par Git) : protocole, rapports par modèle, parités avec les références, copies des sources/empreintes, dépendances et deuxième mesure des temps.
- Poids et dépendances supplémentaires dans `.cache/comparison-models` et `.cache/comparison-deps`. Aucune modification des paquets de `.venv-gpu`, aucun envoi des vidéos vers un service externe.

Les **53 tests Python passent** au stade de cette comparaison isolée. Les trois adaptateurs ont été exécutés sur le GPU avec les mêmes sept clips. L'intégration demandée ensuite branche PE sur le serveur local : voir [validation de GenD PE dans l'interface](visio-gend-pe-integration.md).

Une fois les poids et dépendances locales présents, depuis la racine du dépôt :

```bash
visio/.venv-gpu/bin/python -m visio.compare_models --model gend-pe
visio/.venv-gpu/bin/python -m visio.compare_models --model gend-clip
visio/.venv-gpu/bin/python -m visio.compare_models --model effort
```

Les empreintes/provenances des téléchargements sont conservées avec chaque fichier local. Les poids GenD et le localisateur InsightFace ont leurs conditions propres ; Effort et le code DeepfakeBench sont distribués pour des usages non commerciaux. Cette comparaison reste une expérimentation locale.
