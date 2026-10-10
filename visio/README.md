# Visio — benchmark local sur clips

Module indépendant du **background check / métadonnées**. Il compare trois baselines CPU et **GenD CLIP-L/14 / PE-L sur GPU**, produit un JSON et mesure les faux positifs, le rappel, les abstentions et les erreurs sur un corpus autorisé. Il ne vérifie ni l'identité civile ni une présence en direct. Aucun service AWS. Un serveur HTTP de démonstration optionnel relie l'interface au moteur sur la boucle locale.

## Interface reliée au moteur

La page d'accueil propose maintenant la comparaison webcam avec **InSwapper + scores GenD PE réels**. Installation et validation : [analyse des deux flux en direct](../docs/visio-live-pe.md). Pour lancer cette version complète sur 8765 :

```bash
visio/.venv-gpu/bin/python -m visio.server --port 8765 --live-swap --live-pe
```

L'analyse de fichiers reste disponible via « Sources & simulations » ou `http://127.0.0.1:8765/?mode=clip`. Le serveur sans les options live ci-dessus propose seulement le moteur pour les clips.

Depuis la racine, construire le frontend avec `cd visio-demo && npm ci && npm run build`, puis revenir à la racine et lancer :

```bash
visio/.venv-gpu/bin/python -m visio.server --port 8765
```

Ouvrir http://127.0.0.1:8765. Le bouton **Analyser avec GenD PE** transmet le clip au serveur sur cet ordinateur, lance le worker supervisé et retourne le JSON d'analyse ainsi qu'un JSON de coordonnées séparé. Le serveur utilise `config.gend-pe.json` ; `/api/status` annonce `model: "gend_pe"`. Une seule analyse à la fois ; annulation au retrait/remplacement. Les scores sont affichés sur 100. La localisation tourne à 8 observations/s et GenD PE à 2 analyses/s ; les points sont affichés pendant la lecture **après** traitement, sans accès webcam.

La copie reçue du navigateur est temporaire, sous `.cache/browser-uploads/`, supprimée en fin de traitement/annulation/erreur gérée. Un arrêt forcé peut laisser un dossier à supprimer après arrêt du serveur. La CLI continue à lire directement le fichier original sans copie. Aucun média ou poids n'entre dans Git. Voir [contrats et transport](../visio-demo/integration/README.md) et [validation de l'intégration](../docs/visio-frontend-integration.md).

## GenD sur RTX

GenD se sélectionne explicitement : les valeurs par défaut historiques restent disponibles pour reproduire les premières expériences. **Ne pas combiner automatiquement les anciennes baselines avec GenD** : leurs essais initiaux n'ont pas montré une discrimination utile sur nos clips.

Linux/WSL, Python 3.12, PyTorch 2.8 avec CUDA 12.8. Environnement indépendant du CPU ; prévoir environ 10–15 Gio libres pour dépendances, poids et cache d'installation.

```bash
python3 -m venv visio/.venv-gpu
visio/.venv-gpu/bin/python -m pip install --extra-index-url https://download.pytorch.org/whl/cu128 -r visio/requirements-gpu.lock.txt
visio/.venv-gpu/bin/python -m visio fetch-models --detectors gend_pe
visio/.venv-gpu/bin/python -m visio analyze --config visio/config.gend-pe.json --input visio/local-data/mon-clip.mp4
```

Le GPU doit être accessible au processus WSL ; aucun repli silencieux sur CPU. GenD fonctionne en float32, batch 1. Son localisateur InsightFace tourne sur CPU, avec les poids et l'alignement officiels : cinq points, échelle 1,3. PE utilise ensuite le processeur timm 1.0.20, RGB 224, interpolation bicubique, moyenne/écart-type 0,5 ; CLIP conserve son processeur CLIP. Le checkpoint safetensors est chargé strictement, sans code Python distant ni réseau pendant l'analyse. CUDA nécessite une grande plage d'adresses virtuelles : la limite d'espace virtuel est retirée pour ce worker, mais la surveillance RSS 4 Gio, le délai 60 s, l'admission unique et l'arrêt du processus restent actifs. La mémoire GPU allouée/réservée est mesurée ; ce n'est pas un quota matériel.

Le format JSON 1.0 reste identique ; PE utilise `detectors.gend_pe` et `provenance.gend_pe` (GPU, précision, processeur et pic mémoire). CLIP reste reproductible avec `--config visio/config.gend.json` et `fetch-models --detectors gend`. Les scores ne sont pas des probabilités de fraude. Échantillonnage et agrégation restent ceux du POC ; **ces tests ne reproduisent pas le protocole complet du papier**. Les poids InsightFace servant à l'alignement sont limités à la recherche non commerciale : voir [provenance/licences](THIRD_PARTY.md).

Le choix provisoire de PE vient de la [comparaison sur nos sept clips](../docs/visio-model-comparison.md) : trois deepfakes signalés, aucune alerte sur les quatre prises authentiques. Ce petit jeu de développement déjà examiné ne mesure pas la généralisation à de nouvelles vidéos.

Premier [résultat local](../docs/visio-gend-results.md) : **2/3 deepfakes repérés et 1/4 fausses alertes**, sans panne ni abstention. Ce pilote ne suffit pas à valider le modèle. Sur la RTX 5060 Laptop, le pic PyTorch alloué est de 1 186 Mio et le traitement total de 6,52–19,32 s par clip, chargement compris.

## Pour intégrer un résultat sans installer les modèles

Depuis la racine du dépôt, Python 3.12 suffit :

```bash
python3 -m visio example indeterminate
python3 -m visio example partial
```

Sortie : objet conforme à [schema.json](schema.json), avec `simulation: true`. Six [exemples](examples/) couvrent `no_signal`, `verify`, `indeterminate`, `failed`, `cancelled`, `partial`. **Ce sont des simulations**, pas des mesures. Une interface peut directement importer ces JSON.

| Champ | Sens |
|---|---|
| `status` | `completed`, `partial`, `failed`, `cancelled` : état technique |
| `conclusion` | `no_signal`, `verify`, `indeterminate` ; `null` en erreur/annulation |
| `detectors` | Observations et conclusion séparées pour chaque modèle sélectionné |
| `score` | Moyenne descriptive des scores modèle, non calibrée ; jamais une probabilité de fraude du candidat |
| `coverage` | Frames utilisables / frames échantillonnées ; `null` sans échantillon |
| `time_seconds` | Temps depuis la première frame du média, pas heure réelle de capture |
| `freshness` | Toujours `unverified` sur un clip importé |
| `config_sha256` | Empreinte de tous les réglages de l'expérience |

Affichage conseillé : « aucun indice détecté dans le périmètre testé », « indice à vérifier », « analyse insuffisante ». Un score absent est `null`, pas zéro. `partial` peut contenir un indice valide et une panne ; afficher les deux. Aucune décision automatique d'embauche.

## Installer et vérifier les poids

Première cible : **Linux/WSL x86_64, Python 3.12**, accès réseau uniquement pour installation et téléchargement explicite. Réserver environ 3 Gio disque (environnement + poids) et 4 Gio RAM pour le worker. Autres plateformes non vérifiées.

```bash
python3 -m venv visio/.venv
visio/.venv/bin/python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r visio/requirements-cpu.lock.txt
visio/.venv/bin/python -m visio fetch-models
```

Les deux ViT occupent environ 343 Mo chacun. MiniFASNet et le localisateur YuNet sont plus petits. Le manifeste [models.json](models.json) fixe URL, version, taille, licence et SHA-256. Aucun pickle, code distant ou téléchargement implicite pendant l'analyse. Le cache local `visio/.cache/` est ignoré par Git. Un cache déjà présent est revérifié avant chaque chargement.

## Analyser un clip

```bash
visio/.venv/bin/python -m visio analyze --input visio/local-data/mon-clip.mp4
# Pour une mesure isolée d'un modèle :
visio/.venv/bin/python -m visio analyze --input visio/local-data/mon-clip.mp4 --detectors dima
```

Clips locaux de **2–20 s**, idéalement 10–20 s ; mp4/mov/mkv/webm/avi ; 50 Mio maximum ; une piste vidéo ; 1080p maximum, <=60 fps. Aucun appel réseau pendant l'analyse. Le fichier original reste chez vous et n'est jamais supprimé ni recopié par le moteur. Aucune frame, crop ou embedding n'est enregistré. Seuls les résultats numériques et versions peuvent être exportés.

Prétraitements : YuNet localise un seul visage suffisamment grand/exposé ; les ViT classifient la frame RGB entière conformément à leur usage image ; MiniFASNet reçoit un crop de contexte BGR de facteur 2,7, en float32 non normalisé sur [0,255]. Le remplacement de RetinaFace par YuNet pour les rectangles MiniFASNet doit être validé sur le corpus : l'adaptateur n'hérite pas des performances du dépôt d'origine.

Les paramètres dans [config.example.json](config.example.json) sont **exploratoires et non calibrés**. `--config chemin.json` remplace les valeurs par défaut ; `--detectors ...` prime sur le fichier. Le manifeste/cache peuvent être choisis par `--manifest`/`--cache`. L'analyse est toujours offline ; aucune option ne télécharge silencieusement.

Deux agrégations pour la phase développement : `fraction` (part des frames au-dessus du seuil), `window` (persistance continue sur une durée). Les observations brutes restent disponibles. Une couverture <80 %, un intervalle sans observation >2 s ou une panne rend le détecteur indéterminé. Un seul indice valide peut produire `verify` ; tous les détecteurs sélectionnés doivent être exploitables et sans signal pour `no_signal`. Aucun score moyen entre modèles. Une manipulation entre deux échantillons peut être manquée.

## Préparer le corpus et lancer le benchmark

**Aucune vidéo authentique/truquée fournie au départ.** Le fichier [dataset.example.json](dataset.example.json) est volontairement vide et le benchmark le refuse : aucun chiffre fictif. L'agent chargé du corpus peut préparer un manifeste séparé, sans modifier le moteur.

Créer un JSON du format suivant, avec chemins relatifs au manifeste :

```json
{
  "schema_version": "1.0",
  "claimed_categories": ["face_swap"],
  "clips": [
    {
      "id": "clip-001",
      "path": "clips/clip-001.mp4",
      "sha256": "REMPLACER_PAR_EMPREINTE_REELLE",
      "source_id": "source-001",
      "person_id": "personne-001",
      "split": "dev",
      "label": "real",
      "attack_kind": null,
      "authorized": true,
      "permission": "REMPLACER_PAR_LA_PREUVE_D_AUTORISATION"
    }
  ]
}
```

`label` vaut `real` ou `attack`. `attack_kind` vaut `photo`, `screen`, `face_swap`, `reenactment` ou `digital_replay` pour une attaque. Photos/écrans sont **filmés physiquement** ; digital_replay est une injection/relecture numérique. Les modèles actuels ne revendiquent pas la détection de cette dernière.

Utiliser des identifiants opaques, jamais noms/email. Chaque personne et source (avec toutes ses variantes) reste dans **une seule partition** `dev` ou `test`. Le code refuse les doublons de contenu et les fuites entre partitions. La déclaration d'autorisation est une attestation du préparateur, pas une vérification juridique automatique. Calculer les empreintes : `sha256sum chemin/video.mp4`.

```bash
visio/.venv/bin/python -m visio benchmark --dataset visio/local-data/dataset.json --split dev --output visio/reports/dev-001.json
# Après réglage sur dev, figer corpus, modèles et configuration :
visio/.venv/bin/python -m visio freeze --dataset visio/local-data/dataset.json --output visio/reports/evaluation.lock.json
visio/.venv/bin/python -m visio benchmark --dataset visio/local-data/dataset.json --split test --evaluation-lock visio/reports/evaluation.lock.json --output visio/reports/test-001.json
```

Si `--config` ou `--detectors` est utilisé, répéter les mêmes options pour dev, freeze et test. Aucun fichier de sortie existant n'est écrasé. Le verrou détecte les changements accidentels ; il ne peut empêcher quelqu'un de consulter le test puis refaire volontairement un verrou. Respecter le protocole de gel.

Le rapport conserve aussi les erreurs et abstentions. Les résultats sont **par modèle et menace applicable** : MiniFASNet photo/écran, ViT face swap/reenactment. Le rappel bout en bout inclut abstentions et pannes au dénominateur ; le rappel conditionnel est fourni en complément. Les ratios sans données sont `null`. Les intervalles Wilson sont descriptifs et ne compensent pas un corpus peu représentatif.

50 clips constituent un pilote. Les cibles du plan demandent >=25 sources authentiques de test et >=10 sources par catégorie revendiquée, plus un développement séparé. Un petit effectif est `inconclusive`, jamais une validation de production. Les latences totales incluent chargement et décodage ; `model_load_seconds` et `inference_seconds` permettent de les distinguer.

## Erreurs

stdout = JSON ; stderr = progression des téléchargements. Code de sortie : 0 analyse terminée (y compris abstention), 2 entrée/config/corpus invalide, 3 panne ou résultat technique partiel, 130 annulation. Le sous-processus est terminé et attendu avant une nouvelle tentative ; aucune tâche en arrière-plan ne publie un résultat ancien.

| Code | Cause / action |
|---|---|
| `InvalidMedia` | Format, durée, taille, résolution ou timestamps invalides ; réencoder dans les limites |
| `DecodeFailed` | Vidéo corrompue/incomplète ; fournir un autre fichier |
| `ModelUnavailable` | Poids absents/hash incorrect ou runtime absent ; installer le lock et relancer `fetch-models` |
| `InvalidPrediction` | Labels, forme ou score invalides ; vérifier adaptateur et manifeste |
| `AnalysisTimeout` / `ResourceLimit` | Budget dépassé ; raccourcir le clip ou sélectionner moins de modèles |
| `AnalysisBusy` | Une analyse locale est active ; attendre sa fin |
| `CleanupFailed` | Accès/suppression des temporaires impossible ; arrêter toute analyse, vérifier `visio/.cache/state/`, corriger permissions et relancer |
| `WorkerFailed` | Processus arrêté ou réponse hors contrat ; vérifier installation/ressources |
| `InvalidDataset` | Corpus vide, non autorisé, altéré, contaminé ou non gelé ; corriger le manifeste |

Le superviseur impose une tâche par checkout et surveille délai/RSS (4 Gio). Le worker a aussi des limites d'espace virtuel (8 Gio), CPU et taille de sortie. Le plafond RSS est un watchdog échantillonné, **pas un sandbox de sécurité ni une limite noyau sur un groupe hostile**. Cette version est réservée à des clips locaux autorisés. Aucun upload externe/service partagé avant isolation durcie et contrôle d'accès. Les temporaires contiennent uniquement JSON/diagnostic et sont nettoyés ; aucune vidéo temporaire à purger.

## Tests et maintenance

```bash
visio/.venv/bin/python -m pytest visio/tests -q
```

Tests sans téléchargement : contrat, erreurs, séparation des données, gel, agrégation, prétraitement, échantillonnage, timeout et admission. Les fixtures vidéo techniques sont fabriquées dans un dossier temporaire ; elles ne mesurent aucune détection de fraude.

Voir [sources/licences](THIRD_PARTY.md), [plan QA](../docs/visio-test-plan.md) et [plan approuvé](../docs/visio-plan.md). Toute modification de poids, prétraitement, seuil ou agrégation crée une nouvelle expérience. Une rupture de schéma demande une nouvelle version majeure et des exemples migrés. Pas de modification automatique des seuils en fonction du résultat de test.
