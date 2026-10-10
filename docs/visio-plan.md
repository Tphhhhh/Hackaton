<!-- /autoplan restore point: "/tmp/hackaton-visio-autoplan/restore.md" -->
## Implementation plan
# Visio : recherche et plan avant implémentation

Date : 10 octobre 2026. Statut actuel : plan approuvé par l’utilisateur (« Valider le plan : benchmark sur clips d’abord »), moteur local et benchmark implémentés, évaluation sur corpus en attente de vidéos. Voir [état de réalisation](visio-implementation.md). Les revues ci-dessous sont conservées comme historique préalable à cette approbation ; leurs mentions « aucun modèle exécuté » décrivent cette étape passée. Les précisions finales du bloc eng complètent les propositions initiales (notamment corpus et codes de sortie).

## Demande et contraintes

Deux développeurs se partagent le projet. L'utilisateur prévoit une branche `visio` pour analyser la vidéo d'entretien et déterminer si la personne est réellement présente ; son collègue développe une autre fonctionnalité. Rechercher d'abord les modèles Hugging Face, puis proposer une architecture et des tests avant de coder. Le dépôt était vide sur main à l’ouverture de la recherche, commit c943958 ; le contrôle final constate la branche visio, créée en dehors de cette étude. Le périmètre de cette étude est le moteur d'analyse et son contrat d'intégration, pas la réalisation de l'interface montrée en référence.

Les captures fournies listent AWS : Bedrock, Rekognition, SageMaker, EC2 inférieur à 6xlarge sans GPU, Lambda, ECS, stockage et autres services. Ressources optionnelles uniquement ; aucun appel cloud, déploiement ou dépense pour cette étude. La disponibilité de Rekognition Face Liveness dans le compte et la région reste à vérifier si cette option est choisie. L'accès à SageMaker ne garantit pas un quota GPU.

## Objectif et limites

L'objectif utilisateur reste vérifier une présence humaine pendant un entretien. Les moyens proposés séparent : (1) qualité et présence d'un visage ; (2) attaques physiques photo/écran ; (3) altérations numériques du visage. Un vrai humain peut porter un face swap ; une vidéo authentique peut être rejouée. Aucun résultat passif ne certifie l'identité civile ou l'absence de fraude. Proposer au final la formulation « indices de manipulation / vérification nécessaire / analyse insuffisante », à valider avec l'utilisateur.

L'image de référence n'autorise pas à ajouter les émotions, le regard, l'accent, les clics, le presse-papiers ou un score de personnalité. La voix clonée, la synchronisation labiale et la comparaison biométrique d'identité sont des capacités distinctes, à discuter séparément.

## Recherche vérifiée et shortlist

Recommandation provisoire : deux détecteurs complémentaires évalués séparément, pas un score moyen. MiniFASNet pour photo/écran ; un classificateur de manipulations du visage pour les frames. Le choix final dépend d'un benchmark après approbation, pas des chiffres des model cards.

| Candidat | Rôle et éléments vérifiés | Réserve / décision proposée |
|---|---|---|
| [MiniFASNet / Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing), [port ONNX yakhyo](https://github.com/yakhyo/face-anti-spoofing) | Anti-spoofing passif, environ 0,43 M paramètres, Apache-2.0 annoncé. Port avec modèles V1SE et V2, recadrages différents. | Premier candidat CPU contre photo/écran. Pas une défense démontrée contre injection numérique. Le miroir HF `yakhyo/face-anti-spoofing` renvoie HTTP 401 à la consultation anonyme : ne pas le proposer comme téléchargement vérifié ; utiliser la provenance GitHub et contrôler les poids. |
| [dima806/deepfake_vs_real_image_detection](https://huggingface.co/dima806/deepfake_vs_real_image_detection) | ViT de classification d'images, 85,8 M paramètres, safetensors et Apache-2.0. Révision observée `29e4cf9efc543845610045f6ba7e88e5cf9d9301`. | Baseline facile à tester. L'auteur avertit que les données anciennes généralisent mal aux nouveaux faux. Ne pas réduire arbitrairement le seuil pour obtenir une démo convaincante. |
| [prithivMLmods/Deep-Fake-Detector-v2-Model](https://huggingface.co/prithivMLmods/Deep-Fake-Detector-v2-Model) | Autre ViT, 85,8 M paramètres, safetensors, Apache-2.0, révision `3a99ae26f52c7ac7c3a53103b6cf3a8b617f7093`. | Challenger simple. La fiche annonce classification d'images et sensibilité à la compression ; ne pas le présenter comme détecteur temporel vidéo. Même famille que dima : pas d'ensemble supposé indépendant. |
| [morhadi/deepfake-detection](https://huggingface.co/morhadi/deepfake-detection), [code des auteurs](https://github.com/yermandy/deepfake-detection) | Modèle lié à un travail CLIP ViT-L/14 sur visages partiellement manipulés, évaluations inter-datasets publiées ; licence MIT affichée sur HF. Révision `521c54a774618af4e3a0f9a506fa3288f220b970`. | Candidat recherche mieux aligné avec face swaps, mais coût CPU et provenance exacte du miroir à contrôler. Formats ckpt/torchscript, pas de safetensors listé ; inspecter le chargement avant toute exécution. |
| [umm-maybe/AI-image-detector](https://huggingface.co/umm-maybe/AI-image-detector) | La fiche vise les images artistiques générées et dit explicitement ne pas être un détecteur de deepfake photo. | Écarté pour la visio ; popularité sans adéquation à l'usage. |

[MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker) peut fournir des repères du visage et sa pose. C'est une brique de localisation/qualité, pas un détecteur de fraude.

[AWS Rekognition Face Liveness](https://docs.aws.amazon.com/rekognition/latest/dg/face-liveness.html) propose une capture selfie guidée avec session dédiée et score probabiliste. Option si la présence active est prioritaire, sous réserve de disponibilité, consentement et coût. Ce n'est pas une API qui certifie chaque frame d'un entretien Zoom existant. Bedrock n'est pas nécessaire pour classifier les pixels ; une explication déterministe suffit au POC.

## Proposition de réalisation après validation

1. Définir un petit corpus de vidéos autorisées et un manifeste indiquant provenance, personne/source, type d'attaque et transformations. Geler un jeu de test distinct avant de régler les seuils.
2. Préparer un outil d'évaluation CPU reproductible. Comparer dima et prithiv sur les mêmes clips, puis le candidat CLIP si les deux échouent et si le coût reste acceptable. Tester MiniFASNet sur des attaques photo et écran réellement filmées.
3. Créer un module Python isolé sous `visio/`, sans toucher au module dossiers du collègue. Utiliser des poids et versions épinglés, un traitement local par défaut et aucun entraînement initial.
4. Pour une première démonstration, accepter un clip court (10 à 20 secondes) et partager le même moteur avec une future capture navigateur. Échantillonner au maximum deux frames par seconde, avec plafonds explicites et un seul traitement actif. Ce choix clip d'abord reste une proposition de séquencement à approuver, pas une réduction imposée du besoin visio.
5. Détecter/localiser le visage, contrôler la qualité, appliquer le prétraitement exact de chaque modèle, produire des résultats par détecteur et agréger temporellement selon une règle évaluée. Plusieurs visages ou frames inutilisables produisent un résultat indéterminé.
6. Exposer un contrat JSON versionné avec identifiant de session opaque, état technique, horodatages, couverture analysable, résultats par détecteur, score brut non calibré, raisons, versions et limites. Aucun booléen `is_human`, aucune décision d'embauche. Prévoir une API mince si le collègue en a besoin, sans choisir sa stack à sa place.
7. Retourner trois issues interprétables : aucun indice détecté dans le périmètre testé, à vérifier, indéterminé. Le premier n'est pas un certificat. Une erreur de modèle ne devient jamais un zéro de risque.
8. Mesurer latence CPU à froid/à chaud, RAM et délai total par clip, puis décider si un retour pendant l'entretien est réaliste. Objectif provisoire : clip 20 s traité en moins de 20 s sur le CPU cible, à mesurer ; aucune promesse temps réel préalable.

## Évaluation et conditions d'acceptation proposées

Le corpus des 50 dossiers synthétiques du projet global ne valide pas la vidéo. Prévoir un corpus vidéo indépendant, idéalement au moins 50 clips dont 25 authentiques et 25 attaques réparties entre photo, écran/replay, face swap et reenactment selon les médias autorisés disponibles. Séparer personnes, vidéo d'origine et toutes ses variantes entre développement et test ; jamais séparer seulement les frames. Une catégorie sans exemples reste non évaluée et explicitement non revendiquée.

Rapporter matrice de confusion, rappel par attaque, faux positifs sur clips authentiques, abstention, couverture et latence p50/p95. Avec 25 authentiques, une fausse alerte représente 4 % ; ce petit échantillon est une évaluation de POC, pas une garantie industrielle. Décider les seuils uniquement sur développement, puis figer modèles, prétraitements et seuils pour le test.

Scénarios : éclairage faible, lunettes, contre-jour, visage absent, visages multiples, compression, faible résolution, faible fréquence, photo filmée, écran filmé, vidéo rejouée et injection numérique. Ne pas inférer une fraude depuis un mouvement ou une différence physiologique. Inclure un état non évaluable et une vérification humaine de secours.

Si aucun modèle ne sépare suffisamment les vrais clips et les manipulations, conclure au résultat négatif du benchmark. Ne pas modifier les labels, masquer les faux positifs ou présenter un détecteur photo/écran comme couverture des deepfakes. Choisir ensuite entre approfondir le détecteur vidéo ou une capture active guidée.

## Protection et intégration

Limiter la taille, durée, résolution et temps de décodage des médias non fiables. Aucune URL arbitraire distante ; fichiers locaux ou upload borné. Ne pas exécuter de code de modèle distant (`trust_remote_code=False` lorsque applicable). Préférer safetensors ou ONNX vérifiés, ne jamais charger des poids pickle inconnus sans contrôle.

Ne conserver par défaut ni vidéo brute, ni visage, ni embedding biométrique ; nettoyage des fichiers temporaires après succès, erreur et annulation. Journaliser des identifiants opaques et des timings, pas les pixels. Toute démonstration utilise des médias consentis/autorisés. Proposer une alternative humaine si la capture n'est pas possible.

Livrables futurs : manifeste modèle/licence/révision, adaptateurs, pipeline commun, contrat de résultat, commande benchmark, documentation de lancement et rapport d'évaluation. Le collègue peut intégrer un exemple JSON sans installer les poids. La sélection finale de modèle, l'entrée live ou clip et l'éventuel check AWS sont les décisions à valider avant code.

## Hors périmètre proposé

Entraîner un nouveau détecteur, brancher Zoom/Teams, surveiller le poste du candidat, détecter ses émotions, authentifier son identité civile, reconnaître sa voix, agréger automatiquement un risque d'embauche, déployer AWS et construire toute l'interface. Ces extensions restent distinctes du moteur vidéo demandé.

<!-- autoplan-accepted:ceo -->
- Avant de choisir un modèle, inventorier les médias autorisés, leurs sources indépendantes, le CPU cible et les menaces ; comparer passif, interaction guidée locale/humaine et service actif sans activer AWS.
- Exiger des résultats séparés par détecteur avec couverture, horodatages, versions, raisons d'abstention et action humaine ; aucune absence d'indice ne vaut preuve de présence live ou d'identité.
- Fournir un exemple JSON autonome pour le collègue et un manifeste modèle comprenant provenance, licence, révision et hash ; vérifier prétraitement et mapping des labels avant chaque benchmark.
- Geler les seuils sur développement, séparer personnes et sources entre jeux, rapporter effectifs, faux positifs, rappel par attaque, abstention et latence. Un corpus de 50 dossiers synthétiques n'est pas un benchmark vidéo.
- Proposer comme critères exploratoires avant test final : faux positifs au plus 1/25 authentiques, rappel au moins 80 % par catégorie revendiquée avec au moins 10 sources indépendantes, abstention au plus 20 %, au moins 80 % de frames utilisables ; résultat marqué non concluant si effectifs insuffisants. Ces cibles de POC ne constituent pas une garantie de production.
- Fixer pour le premier benchmark un plafond de 2 h de préparation par modèle, 4 Gio de RAM pour le worker et une cible de 20 s maximum par clip de 20 s à chaud sur le CPU documenté ; les dépassements restent des résultats de faisabilité visibles, pas une autorisation de masquer une capacité manquante.
- Prévoir erreurs nommées, admission bornée, invalidation des résultats après annulation/retry, nettoyage vérifié et tests des ordres concurrents ; si le nettoyage échoue, refuser de nouvelles captures jusqu'à résolution.
- Limiter initialement l'exécution au poste local. Toute ouverture réseau doit ajouter contrôle d'accès, séparation de session et transport sécurisé avant usage partagé.
<!-- /autoplan-accepted:ceo -->

<!-- autoplan-accepted:dx -->
- Publier d'abord sous visio/ un schéma JSON et cinq fixtures (succès, abstention, erreur, annulation, partiel) marquées simulation ; le collègue les lit sans dépendance ML. README fournit commandes et sorties attendues ; cible <5 min mesurée lors de son premier essai, distincte du temps de téléchargement.
- Contrat v1 : schema_version string, session_id opaque, generation entier, status completed|partial|failed|cancelled, conclusion no_signal|verify|indeterminate|null. Horodatages en secondes depuis début média ; coverage = frames utilisables / frames échantillonnées, null si dénominateur nul. Un score absent est null, jamais zéro par défaut ; chaque détecteur a statut et menace évaluée propres. Les modèles/configurations et limites accompagnent le résultat.
- Interface future : python -m visio analyze --input chemin --manifest chemin ; python -m visio benchmark --dataset manifeste --output rapport. stdout contient seulement JSON, diagnostics sur stderr ; --help sans ML. Sortie 0 = analyse achevée, y compris indéterminée analytique ; 2 = entrée invalide ; 3 = panne technique. Pas de téléchargement implicite à l'analyse.
- Donner chaque erreur sous forme code/message/cause/action/retryable/docs. Ne réessayer qu'après correction indiquée ; une panne de nettoyage bloque jusqu'au contrôle réussi du répertoire temporaire appartenant au worker. Les erreurs par détecteur ne deviennent jamais un score nul.
- Configuration : CLI > fichier config > defaults documentés ; chemins cache/manifeste, détecteurs, threads CPU, budgets et mode offline configurables sous limites obligatoires. Empreinte de configuration effective dans le rapport ; seuil ou prétraitement modifié = nouvelle expérience, aucun réglage sur test final.
- README du module relie démarrage, contrat, erreurs, benchmark et ajout d'adaptateur. Version majeure du schéma pour rupture, note de migration et fixtures mises à jour ensemble. Première cible Linux/WSL CPU ; autre OS testé selon environnement réel du collègue, pas de compatibilité prétendue.
<!-- /autoplan-accepted:dx -->

## Complément utilisateur : défis et mesures MediaPipe

La capture ajoutée suggère occlusion main/visage, rotation de tête, synchronisation labiale, instabilité temporelle et éclairage. Elle est traitée comme piste de recherche, pas comme preuve que ces mesures distinguent une fraude. [GOTCHA](https://arxiv.org/abs/2210.06186) étudie bien des défis en visio ; ses résultats ne valident pas notre implémentation ni tous les générateurs actuels. [MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker) expose repères, suivi et lissage : la stabilité de sa propre estimation n'est pas une mesure indépendante d'authenticité.

Comparer un protocole guidé à la baseline passive avant de choisir la démonstration : consigne imprévisible liée à une session, réponse dans une fenêtre mesurée, récupération après occlusion, qualité observée et recours humain. La présence de repères derrière une main ne prouve pas une incrustation ; repères absents, sauts et faible stabilité peuvent venir du suivi. Ne pas interpréter un échec de geste comme fraude, proposer une alternative accessible. La corrélation énergie audio/ouverture de bouche est une expérience de synchronisation, pas un classificateur de voix générée : silence, phonèmes, latence et capture la perturbent. Audio et éclairage restent des options hors première implémentation à valider. Ne pas reprendre les formulations « signal le plus fort » ou « probablement générée » sans évaluation.

Le plafond 2 images/s concerne seulement la baseline de classification passive ; il serait inadéquat pour des micro-variations temporelles. Si le protocole guidé est retenu, conserver les horodatages et une cadence suffisante mesurée pour ce test, sans promettre de preuve universelle de présence. Aucun défi n'est implémenté dans cette recherche.


<!-- autoplan-accepted:eng -->
- Pour le test final, séparer le développement du pilote de 50 clips ; exiger 25 authentiques de test et au moins 10 sources indépendantes par catégorie revendiquée (donc >=65 clips de test pour quatre catégories). Effectifs moindres = exploration non concluante, sans réduire silencieusement les revendications. Rapporter abstention/échecs par classe et rappel bout en bout incluant abstentions au dénominateur, ainsi que résultats conditionnels.
- Fixer avant test une agrégation par détecteur : candidats fraction de frames au-dessus de seuil et persistance par fenêtre de 2 s ; choix et paramètres sur développement seulement. Conserver observations/horodatages/longest_gap ; couverture minimale 80 % par détecteur, maximum gap non observé 2 s proposé pour clip passif. Alerte valide => verify ; sinon tout détecteur applicable prêt et couverture suffisante => no_signal ; sinon indeterminate. Aucun mélange des scores ; aucune conclusion entre échantillons. Burst plus court que cadence reste une limite déclarée.
- Appliquer la table d'états terminale : completed analytique code 0, partial technique code 3 avec verify ou indeterminate, failed code 2/3 avec conclusion null, cancelled code 130 avec conclusion null. Superviseur seul propriétaire de session/generation, publication après nettoyage et contrôle courant ; erreur nettoyage prime, résultats périmés rejetés. Tester toutes combinaisons, ordre concurrent et crash/restart.
- Worker local séparément terminable, limites d'entrée et de décodage contrôlées en continu : 50 Mio, 20 s, 1080p, <=60 fps, <=1200 frames décodées, <=40 échantillons passifs, temp <=100 Mio, deadline dure 60 s. Admission immédiate d'une tâche sans file ; terminer/récolter processus et purger uniquement leur espace privé. Démontrer une limite mémoire effective avant entrée externe ; cible mémoire groupe 4 Gio, cible chaude 20 s, sans confondre RSS et espace virtuel. Crash/timeout/OOM/disque plein/métadonnées trompeuses doivent être testés.
- Conformité avant accuracy : références prétraitement et tolérances par adaptateur, RGB/crop/resize/labels, orientation, PTS variables, sortie NaN/Inf, zéro frame et plusieurs visages. Manifeste et rapport figent hash modèles/données, runtime, décodeur et config ; jeux de données séparés par personne/source et toutes variantes.
- Si défi guidé choisi ultérieurement, définir générateur de défi, durée de validité, horloge de référence et liaison challenge/session/capture. Uploads => freshness=unverified ; tester replay, expiration, mismatch et injection. Aucun score de landmark, de lip-sync ou de défi réussi ne devient automatiquement une preuve d'identité ou d'absence de deepfake.
<!-- /autoplan-accepted:eng -->
## Review record

### Phase 0 : contexte et exécution

GitHub, base main, c943958 ; aucun fichier applicatif suivi, aucune dépendance, aucun stash ni autre branche locale. Aucun AGENTS.md, TODOS.md, DESIGN.md ou ancien design pertinent trouvé. UI scope : non, recherche et moteur seulement ; DX scope : oui, deux occurrences API (hash d'entrée 93d3dbcd287028087ed3617a6a58326a7b7c29e673adc9def12722242baf0f2a). La capture d'interface est une inspiration, pas une demande de surveillance ou de développement frontend.

Autoplan session 1-1791644914-4377197c. Ranges CEO chargés 1–600 (portion tronquée relue 300–450), 601–900, 901–1200, 1201–1500, 1501–1800, 1801–2233, plus critères review-sections du checkout source. Aucun code applicatif écrit. Les scripts de routing et office-hours ne sont pas ajoutés au projet : cela sortirait de la recherche demandée et de la base minimale souhaitée. Audit temporaire sous /tmp/hackaton-visio-autoplan ; livrables durables sous docs. Les journaux globaux gstack ont signalé un système de fichiers en lecture seule ; aucune couverture fictive enregistrée.

### Phase 1 : stratégie et périmètre

Mode SELECTIVE EXPANSION selon autoplan. La recherche répond au besoin exprimé, mais le choix d'un modèle ne résout pas encore le sens de « vrai humain ». Nous maintenons cet objectif utilisateur et soumettons au choix final le niveau de preuve attendu : signal passif ou contrôle actif ; aucun changement de promesse n'est considéré approuvé.

#### 0A : prémisses

- Modèles réutilisables : confirmé par fiches et fichiers disponibles ; aucune exécution ni validation locale réalisée.
- Présence du visage égale présence en direct : faux en présence d'un replay. Garder cette limite comme question de produit à valider.
- Face spoofing et deepfake sont équivalents : faux ; les menaces et corpus diffèrent.
- Score élevé signifie identité vérifiée : non établi. Aucun document d'identité de référence n'est fourni et ce travail n'en demande pas.
- CPU suffisant : hypothèse mesurable, pas une conclusion ; AWS sans GPU est une contrainte transmise, pas un matériel benchmarké.
- Données disponibles : non vérifié ; l'inventaire doit précéder toute sélection définitive.

#### 0B : What already exists

| Sous-problème | Existant constaté | Réutilisation |
|---|---|---|
| Collaboration | Dépôt GitHub vide, main initialisée | Branche visio prévue par utilisateur ; contrat séparé pour collègue |
| Pipeline, API, tests | Aucun code dans le dépôt | Aucune architecture héritée, aucun module à reconstruire |
| Localisation visage | MediaPipe documenté | Candidat de prétraitement, sans score de fraude |
| Anti-présentation | MiniFASNet et port ONNX publiés | Adapter le prétraitement original |
| Manipulation numérique | Poids HF shortlistés | Évaluer avant sélection, sans entraînement |
| Présence active | Rekognition documenté | Alternative optionnelle, accès non testé |

#### 0C : Dream state

```text
ACTUEL : dépôt vide + besoin de confiance en entretien
  -> CE PLAN : preuves de faisabilité, menace couverte, résultat explicable
  -> IDÉAL 12 MOIS : capture liée à la session, validation indépendante,
     faible friction, mesure de dérive et recours humain documenté
```
Dream state delta : ce plan apporte une décision instrumentée sur la faisabilité du moteur. Il ne livre ni identité certifiée, ni protection totale des recrutements, ni défense démontrée contre l'injection de flux.

#### 0C-bis : alternatives examinées

| Approche | Effort estimé humain / assisté | Avantages | Limites et risque | Position |
|---|---|---|---|---|
| A. Analyse passive clip + modèles HF | 1–2 j / 3–6 h hors données | Locale, reproductible, s'intègre au travail du collègue | Présence live non prouvée ; généralisation incertaine | Base recommandée pour la recherche demandée |
| B. Interaction guidée locale + vérification humaine | 1–2 j / 3–6 h | Réponse à une consigne fraîche, contrôle compréhensible | Accessible seulement avec alternatives ; contournable par deepfake live | Alternative à tester si présence actuelle prioritaire |
| C. Session Rekognition Face Liveness | 1–2 j / 2–5 h après accès | Capture guidée existante, pas de GPU à gérer | Réseau, quota, coût, accès et consentement ; nouvelle étape candidat | Option AWS, aucun appel maintenant |

Complétude : alternatives de nature différente, aucun score arbitraire. Un modèle passif peut servir la recherche mais ne remplace pas le besoin de présence live. Une vérification humaine guidée sert aussi de référence de comparaison, sans prétendre être infaillible.

#### 0D : expansion sélective

Minimum cohérent : inventaire de données, adaptateurs de modèles, pipeline borné, résultat versionné, benchmark et documentation. Vision élargie : un protocole de vérification d'entretien, dont chaque signal a une portée et une action. Pas de plateforme multi-agents ni d'infrastructure supplémentaire justifiée.

Cinq améliorations voisines proposées et retenues au plan : exemple JSON intégrable sans poids, raison explicite d'abstention, horodatage des observations, manifeste de modèle, rapport reproductible avec chiffres bruts. Chacune complète une obligation existante dans moins de cinq fichiers et moins d'un jour assisté. Capture active, voix, connecteur Zoom et surveillance du poste restent des extensions non auto-approuvées.

#### 0E : décisions avant exécution

| Moment humain (ordre de grandeur) | Décision nécessaire | Résolution proposée |
|---|---|---|
| Heure 1 | Médias autorisés et CPU cible | Inventaire et spécifications avant dépendances |
| Heures 2–3 | Prétraitement, faux positifs, abstention | Révisions figées, développement indépendant, critères chiffrés provisoires |
| Heures 4–5 | Connexion avec collègue | Exemple JSON et code d'état commun, aucun besoin de sa stack |
| Heure 6+ | Échec du modèle ou lenteur | Conserver le résultat négatif et proposer capture active, sans seuil opportuniste |

Temps assisté estimé pour ces étapes : 2–4 h hors acquisition des données ; aucune garantie sur les téléchargements ou l'évaluation.

#### Revue indépendante CEO

Codex natif : six observations, dont trois High (promesse à clarifier, comparaison active trop tardive, critères d'arrêt qualitatifs) et trois Medium (recours humain, disponibilité corpus, valeur au-delà du modèle). INPUT natif correspond exactement au snapshot ceo 93d3dbcd287028087ed3617a6a58326a7b7c29e673adc9def12722242baf0f2a.

Claude Code : unavailable, résultat d'exécution `Failed to authenticate: OAuth session expired and could not be refreshed`. Aucune recommandation externe produite ; modèle inconnu, usage 0. Réparation possible par `claude auth login`, hors tâche.

| Dimension CEO | Codex natif | Claude Code | Consensus |
|---|---|---|---|
| Prémisses | Présence et identité à séparer | indisponible | N/A |
| Bon problème | Oui, promesse à valider | indisponible | N/A |
| Périmètre | Cohérent, preuve passive limitée | indisponible | N/A |
| Alternatives | Comparer actif dès le début | indisponible | N/A |
| Marché | Valeur dans le protocole intégré | indisponible | N/A |
| Trajectoire 6 mois | Dépend de corpus et dérive | indisponible | N/A |

#### Section 1 : architecture

Deux détecteurs ont des prétraitements et des menaces différents ; un score moyen masquerait leurs désaccords. Retenir un moteur partagé et deux adaptateurs simples, avec résultats séparés ; l'entrée clip n'impose pas une future stack live. À 10× la charge, le CPU sature ; à 100×, l'admission doit refuser explicitement plutôt qu'accumuler des vidéos.

```text
clip autorisé -> validation/décodage -> visage + qualité
                                      |              |
                                 MiniFASNet     classifieur HF
                                      +------ résultats séparés
                                                -> JSON versionné -> collègue
```

#### Section 2 : Error & Rescue Registry

Les erreurs doivent avoir des noms avant de brancher les modèles. Les codes ci-dessous sont des erreurs applicatives proposées, avec adaptation des exceptions du décodeur/runtime choisi. Aucun appel LLM n'est prévu : JSON halluciné/refus LLM ne sont donc pas des chemins de ce moteur.

| Chemin | Erreur proposée / cause | Rescue | Résultat visible | Test |
|---|---|---|---|---|
| Validation | InvalidMedia : absent/vide/type/durée/taille | Rejeter sans inference | Capture à refaire, raison | nil, 0 octet, limites |
| Décodage | DecodeFailed : corrompu/codec | Arrêt + nettoyage | indéterminé | fichier tronqué |
| Ressource | AnalysisTimeout : budget dépassé | Tuer tâche bornée + nettoyer | indéterminé/timeout | worker bloqué |
| Modèle | ModelUnavailable : poids absents/hash invalide | Refuser readiness | indisponible, pas score 0 | fichier manquant |
| Prédiction | InvalidPrediction : NaN/labels/taille | Invalider détecteur | résultat partiel/indéterminé | sorties invalides |
| Qualité | InsufficientEvidence : 0/multi-visages | Abstention | guidage de recapture | visage absent/multiple |
| Session | AnalysisCancelled : arrêt/retry | Invalider génération + nettoyage | annulé | arrêt concurrent |
| Charge | AnalysisBusy : tâche active | Pas de file illimitée | réessayer | deux requêtes |
| Suppression | CleanupFailed : fichier inaccessible | Bloquer nouvelles captures + alerter | erreur technique | refus unlink |

#### Section 3 : sécurité

Le risque concret est l'entrée média malformée et le téléchargement de poids exécutables, pas une injection de prompt puisque aucun LLM n'est appelé. Le décodeur doit être isolé et borné, les modèles vérifiés et les fichiers temporaires privés. Le POC doit rester local ; tout accès réseau du collègue nécessite une authentification et une séparation des sessions avant ouverture, sans URL arbitraire fournie par le candidat.

| Menace | Vraisemblance / impact | Mitigation proposée |
|---|---|---|
| Média épuisant CPU/RAM | moyenne / élevée | limites avant et pendant décodage |
| Poids non fiables | moyenne / élevée | révision, hash, format sûr, revue chargeur |
| Fuite de visage/logs | moyenne / élevée | pas de pixels dans logs, nettoyage vérifié |
| Confusion de session | moyenne / élevée | ID et génération, résultat lié à sa capture |
| Faux négatif injection | élevée / élevée | limite affichée ; aucune certification live |

#### Section 4 : flux et concurrence

Les entrées nil et vides doivent s'arrêter avant modèle ; les erreurs du runtime doivent garder leur cause sans recevoir un score rassurant. Un résultat tardif ne doit pas remplacer celui d'une nouvelle tentative. Une génération monotone par session et un contrôle avant publication couvrent cet ordre, à tester dans les deux sens.

```text
absent/vide -> InvalidMedia -> aucune inference
valide -> decode -> qualité -> modèles -> résultat -> nettoyage
             |          |          |
          corrompu   insuffisant  indisponible -> indéterminé -> nettoyage

Temps   analyse A        annulation/retry B       état partagé
 t1     generation=1                              courant=1
 t2     attend modèle    invalide 1, crée 2        courant=2
 t3     finit tard       attend résultat 2        résultat 1 rejeté
 inverse : A publie avant B ; B invalide ensuite 1 avant toute lecture fraîche
```
États : ready -> running -> completed|failed|cancelled -> cleaned. Toute publication après cancelled est interdite ; timeout ne publie jamais completed. Doubles soumissions refusées, reprise après arrêt explicite, résultat partiel conservé comme partiel, panne et retry testés.

#### Section 5 : qualité du code

Aucun fichier applicatif ne peut être inspecté dans le dépôt vide : les chemins visio proposés sont futurs, pas existants. Une classe commune de plugins serait prématurée pour deux runtimes ; des fonctions et objets de configuration explicites suffisent. La capture et le benchmark doivent appeler le même pipeline pour éviter des résultats incompatibles entre démo et évaluation.

#### Section 6 : tests

Il n'existe aucun test exécuté ; les engagements ici sont futurs. Le test décisif est une vidéo authentique dégradée et un replay numérique que le système ne peut certifier : ils doivent rester distincts d'une fraude avérée. Le test hostile combine média corrompu, dépassement de budget et erreur de nettoyage ; les erreurs doivent rester visibles sans fuite de données.

```text
entrée absente/vide/limite -> tests validation
clip -> decode -> crop -> modèles -> JSON -> intégration fixture autorisée
erreurs nommées -> injection déterministe -> résultat indéterminé
annulation + fin -> test concurrence contrôlée -> aucun résultat obsolète
modèles réels -> corpus scellé par source -> métriques et abstention
```
Pas d'évaluation de prompt nécessaire. Les mocks vérifient le contrat, jamais la qualité du modèle. Les benchmarks réels mesurent séparément faux positifs, rappel et abstention.

#### Section 7 : performance

Décodage, inférence et premier chargement sont les trois chemins lents ; aucune latence p99 n'est connue avant mesure. Traiter des frames successives évite de charger toutes les vidéos en RAM et une concurrence bornée protège le CPU. Pas de base de données, de N+1 ou de pool réseau dans le moteur local ; mise en cache des poids en mémoire seulement, jamais de résultats entre candidats.

#### Section 8 : observabilité

Compter clips reçus, frames analysables, échecs par code, latence de chaque étape et volume d'abstentions. L'identifiant de run et la révision modèle permettent de reproduire une évaluation sans conserver des visages dans les journaux. Un rapport local suffit au POC ; seuil de saturation et panne readiness doivent avoir une action décrite, sans ajouter CloudWatch tant que rien n'est déployé.

#### Section 9 : livraison

Ordre proposé : corpus -> modèle figé -> benchmark -> contrat -> moteur -> intégration locale -> revue avant réseau. Aucun déploiement AWS n'est requis par cette étude et aucune migration de base n'existe. Le retour arrière restaure la révision du moteur et son manifeste ; un modèle absent désactive la capacité et ne simule pas un succès.

```text
poids vérifiés -> smoke test -> benchmark gelé -> activation locale
                                    échec -> conserver désactivé
régression -> désactiver capacité -> restaurer modèle+config -> smoke test
```

#### Section 10 : trajectoire

Les adaptateurs et le contrat versionné rendent le choix du modèle réversible (4/5), mais un corpus pauvre peut créer une fausse confiance coûteuse. La dette à suivre est la collecte de données représentatives et la dérive après évolution des générateurs. Les références de modèle et les décisions de seuil doivent être documentées pour que le collègue puisse remplacer un modèle sans dépendre de l'auteur.

#### Section 11 : design

Non exécutée : pas de frontend ni de nouvelle interface dans ce plan de recherche/moteur. Les états du contrat et le recours humain sont néanmoins spécifiés pour ne pas imposer au collègue un résultat ambigu.

#### Failure Modes Registry

| Codepath | Mode de panne | Rescue prévu | Test prévu | Visible | Journal |
|---|---|---|---|---|---|
| decode | média invalide | oui | oui | raison recapture | code |
| quality | aucune preuve exploitable | oui | oui | indéterminé | couverture |
| model | absent / NaN | oui | oui | indisponible | version + code |
| aggregation | une frame extrême domine | règle gelée | oui | limite + couverture | paramètres |
| session | résultat obsolète | génération | oui | annulé | ID opaque |
| temporary files | suppression échoue | fail closed capacité | oui | erreur technique | code |
| evaluation | fuite train/test | partition source/personne | oui | benchmark invalide | manifeste |
| meaning | replay déclaré vivant | non certifiable passivement | oui | limite explicite | mode analyse |

Aucun chemin silencieux accepté. Gap produit maintenu ouvert : preuve de présence live non couverte par la proposition passive seule.

#### NOT in scope

1. Identité civile : aucune référence vérifiée.
2. Surveillance comportementale/émotionnelle : hors demande et non probante.
3. Voix et lip-sync : autres modèles et corpus.
4. Connecteurs Zoom/Teams : intégration distincte.
5. Entraînement : données/ressources non établies.
6. Cloud : option, pas prérequis.
7. Frontend complet : propriété à répartir avec collègue.

#### Completion Summary CEO

| Élément | Résultat |
|---|---|
| Mode / audit | SELECTIVE EXPANSION ; dépôt sans application |
| Step 0 | 6 prémisses, 3 alternatives, 5 améliorations adjacentes |
| Arch / erreurs | 2 limites de conception ; 9 erreurs nommées |
| Sécurité / flux | 5 menaces ; 6 cas de session/qualité |
| Qualité / tests | pipeline partagé ; diagramme et tests comportementaux |
| Perf / observabilité | 3 chemins à mesurer ; diagnostic sans pixels |
| Livraison / futur | local d'abord, rollback ; réversibilité 4/5 |
| Design | hors scope interface |
| Hors scope / existant / delta | 7 items et cartes écrites |
| Registres | 9 erreurs, 8 failure modes ; gap présence live explicite |
| Extensions | 5 proposées, 5 retenues au plan |
| Diagrams | architecture, flux, concurrence, états, livraison et rollback |
| Voix | natif 6 constats ; externe indisponible OAuth ; consensus N/A |
| Lake score | N/A : aucun raccourci de garantie accepté |
| Ouvert | promesse, clip/live, modèle retenu après benchmark |

<!-- AUTONOMOUS DECISION LOG -->
### Decision Audit Trail

| # | Phase | Décision | Classification | Principe | Raison | Alternative |
|---|---|---|---|---|---|---|
| 1 | intake | Recherche avant code, branche laissée à utilisateur | mécanique | P6 | demande explicite | scaffolding immédiat |
| 2 | intake | Aucune activation AWS | mécanique | P3 | ressources optionnelles | cloud par défaut |
| 3 | CEO | Distinguer présence, spoof, deepfake, identité | challenge au gate | P5 | garanties différentes | booléen humain |
| 4 | CEO | Comparer actif/passif avant sélection | mécanique | P1 | bon problème avant modèle | actif seulement en échec |
| 5 | CEO | Clip d'abord proposé, live conservé comme objectif | goût | P3 | benchmark reproductible | streaming immédiat |
| 6 | CEO | Résultats distincts par détecteur | mécanique | P5 | menaces différentes | moyenne des scores |
| 7 | CEO | Exemple JSON sans poids | mécanique | P4 | autonomie collègue | deux installations lourdes |
| 8 | CEO | Raison d'abstention | mécanique | P1 | pas de faux signal rassurant | score nul |
| 9 | CEO | Horodatages et couverture | mécanique | P1 | observations vérifiables | score global seul |
| 10 | CEO | Manifeste révision/licence/hash | mécanique | P4 | reproductibilité | latest implicite |
| 11 | CEO | Rapport brut et règles gelées | mécanique | P1 | pas de sélection opportuniste | réglage sur test |
| 12 | CEO | Budget/critères POC provisoires | goût | P5 | condition d'arrêt vérifiable | seuil vague |
| 13 | CEO | CPU + moteur partagé | mécanique | P3 | limites AWS et DRY | GPU implicite |
| 14 | CEO | Pas de routing ni onboarding commit | mécanique | P3 | repo simple/recherche | fichiers hors objectif |

<!-- autoplan-accepted:ceo -->
- Avant de choisir un modèle, inventorier les médias autorisés, leurs sources indépendantes, le CPU cible et les menaces ; comparer passif, interaction guidée locale/humaine et service actif sans activer AWS.
- Exiger des résultats séparés par détecteur avec couverture, horodatages, versions, raisons d'abstention et action humaine ; aucune absence d'indice ne vaut preuve de présence live ou d'identité.
- Fournir un exemple JSON autonome pour le collègue et un manifeste modèle comprenant provenance, licence, révision et hash ; vérifier prétraitement et mapping des labels avant chaque benchmark.
- Geler les seuils sur développement, séparer personnes et sources entre jeux, rapporter effectifs, faux positifs, rappel par attaque, abstention et latence. Un corpus de 50 dossiers synthétiques n'est pas un benchmark vidéo.
- Proposer comme critères exploratoires avant test final : faux positifs au plus 1/25 authentiques, rappel au moins 80 % par catégorie revendiquée avec au moins 10 sources indépendantes, abstention au plus 20 %, au moins 80 % de frames utilisables ; résultat marqué non concluant si effectifs insuffisants. Ces cibles de POC ne constituent pas une garantie de production.
- Fixer pour le premier benchmark un plafond de 2 h de préparation par modèle, 4 Gio de RAM pour le worker et une cible de 20 s maximum par clip de 20 s à chaud sur le CPU documenté ; les dépassements restent des résultats de faisabilité visibles, pas une autorisation de masquer une capacité manquante.
- Prévoir erreurs nommées, admission bornée, invalidation des résultats après annulation/retry, nettoyage vérifié et tests des ordres concurrents ; si le nettoyage échoue, refuser de nouvelles captures jusqu'à résolution.
- Limiter initialement l'exécution au poste local. Toute ouverture réseau doit ajouter contrôle d'accès, séparation de session et transport sécurisé avant usage partagé.
<!-- /autoplan-accepted:ceo -->


### Phase 2 : design

Ignorée : aucun frontend demandé dans cette étude.

### Phase 2.5 : expérience du collègue développeur

Méthodologie DX chargée jusqu'à la ligne 2102, critères des huit passes relus dans review-sections ; référence Hall of Fame consultée. Mode DX POLISH, produit : bibliothèque/CLI Python et contrat JSON local. Dépôt initial vide : aucun README, programme, exemple ou message d'erreur existant à tester. Les scores ci-dessous mesurent uniquement la précision du plan, pas un logiciel opérationnel.

**Persona.** Le collègue qui développe l'autre fonctionnalité veut brancher un résultat sans devenir spécialiste de vision. Tolérance cible : moins de cinq minutes pour afficher une fixture, installation de modèles séparée. Sa stack reste inconnue ; JSON est le point commun proposé.

**Developer Perspective.** « Je récupère le dépôt pour développer ma fonctionnalité en parallèle. Aujourd'hui je trouve un commit initial et ce plan, mais aucun README exécutable. Je ne peux donc pas encore lancer une commande ou vérifier que mon intégration fonctionne. Je comprends que l'analyse vidéo peut échouer sans que le candidat soit frauduleux, mais je dois connaître les champs exacts pour rendre ces situations. Si je dois télécharger plusieurs modèles avant de travailler, je deviens dépendant de leur installation et de la machine de mon collègue. Je voudrais commencer avec un fichier JSON représentatif, sans GPU et sans compte AWS. Ensuite je voudrais recevoir les mêmes champs du vrai moteur. Une valeur absente ne doit pas ressembler à un zéro ; je veux savoir si je dois afficher un résultat, demander une nouvelle capture ou signaler une panne. Quand le schéma change, une version explicite m'éviterait de chercher une erreur dans mon propre code. Pour contribuer, j'ai surtout besoin d'une commande de test légère et du nom des fichiers dont je suis responsable. » Cette perspective est inférée du travail à deux, pas issue d'un test utilisateur.

**Comparaison de démarrage.** Transformers : pipeline et processeur documentés, téléchargement de poids nécessaire ; ONNX Runtime : installation et session d'inférence explicites, prétraitement à fournir ; Rekognition Liveness : compte, permissions, session et capture dédiée. Références : https://huggingface.co/docs/transformers/main_classes/pipelines ; https://onnxruntime.ai/docs/get-started/with-python.html ; https://docs.aws.amazon.com/rekognition/latest/dg/face-liveness.html . Aucun temps de démarrage mesuré pour ces outils ; ne pas inventer un classement chronométré. Notre cible sans poids est <5 min, temps réel d'installation/inférence à mesurer séparément.

| Étape | Action / friction actuelle | Résolution dans le plan |
|---|---|---|
| Découvrir | dépôt sans README | README court du module |
| Évaluer | pas de sortie observable | fixtures honnêtement marquées exemples |
| Installer | runtime non choisi | Python versionné + lock CPU après smoke test |
| Premier résultat | aucun programme | lire fixture sans dépendance ML |
| Intégrer | noms de champs indéfinis | schéma et cinq cas versionnés |
| Déboguer | aucun code d'erreur stable | problème, cause, action, retry |
| Mettre à jour | modèle pourrait changer silencieusement | manifeste + config + version schéma |
| Monter en charge | CPU partagé | un worker, refus busy explicite |
| Migrer | risque couplage modèle/frontend | même contrat, remplacer adaptateur |

**Simulation de première visite, pas test exécuté.** T+0 : ouvrir le dépôt ; T+30 s : chercher README absent ; T+1 min : lire le plan ; T+2 min : contrat encore en prose ; T+3 min : besoin d'exemple exécutable. Tous ces manques sont couverts par les livrables ci-dessous.

**Revue indépendante.** INPUT dx 2de8d23d7fdbeaf1bcc6ce4bae45a02d7bd429d84d5b89b4ae93f3a3611d1770 vérifié. Cinq constats : contrat et récupération High ; démarrage, docs et paramétrage Medium. Claude Code indisponible : `Failed to authenticate: OAuth session expired and could not be refreshed` ; aucun modèle externe ni consensus confirmé.

| Dimension consensus | Natif | Externe | Consensus |
|---|---|---|---|
| Premier résultat | parcours à concrétiser | indisponible | N/A |
| Nommage | schéma requis | indisponible | N/A |
| Erreurs | récupération requise | indisponible | N/A |
| Docs | structure requise | indisponible | N/A |
| Upgrade | manifeste utile | indisponible | N/A |
| Environnement | installation séparée | indisponible | N/A |

| Passe | Avant → après /10 | Correction et condition pour 10 |
|---|---|---|
| 1 Démarrage | 3 → 8 | exemple sans poids en trois étapes ; 10 exige essai chronométré collègue |
| 2 API/CLI | 4 → 8 | schéma, unités et commandes proposés ; 10 exige validation consommateur |
| 3 Erreurs | 5 → 8 | récupération par code ; 10 exige injections de pannes |
| 4 Documentation | 4 → 8 | README vers contrat, benchmark, dépannage ; 10 exige parcours copié réussi |
| 5 Upgrade | 4 → 8 | version majeure pour rupture, manifeste figé ; 10 exige test migration |
| 6 Environnement | 5 → 7 | CPU Linux/WSL, lock après compatibilité ; 10 exige plateforme collègue testée |
| 7 Communauté | 5 → 8 | deux responsables, branches et revue commune ; écosystème public hors scope |
| 8 Mesure DX | 3 → 8 | mesurer installation, fixture et réel séparément ; 10 exige données réelles |

Moyenne indicative de spécification : 4,1 → 7,9/10. Aucun score d'expérience réelle. Les principes de découverte, exemples, erreurs, defaults et configuration sont couverts au plan ; leur efficacité reste à vérifier.

Trois chemins d'erreur détaillés : modèle absent → ModelUnavailable, demander téléchargement vérifié explicite puis retry ; vidéo corrompue → DecodeFailed, demander un nouveau fichier lisible ; nettoyage refusé → CleanupFailed, fermer worker, vérifier/supprimer seulement son répertoire temporaire puis relancer le contrôle. Avant : aucun message existant. Après proposé : objet {code, message, cause, action, retryable, docs}, chemin documentaire relatif sans données personnelles. Aucun retry infini.

Checklist future : [ ] fixture <5 min ; [ ] installation CPU reproductible ; [ ] cinq fixtures conformes ; [ ] --help et codes de sortie ; [ ] erreurs documentées ; [ ] configuration effective ; [ ] contrat compatible consommateur ; [ ] benchmark réel distinct ; [ ] essai du collègue. Site de docs, playground, SDK multilangage, télémétrie externe et communauté publique exclus : disproportionnés pour deux développeurs.

<!-- autoplan-accepted:dx -->
- Publier d'abord sous visio/ un schéma JSON et cinq fixtures (succès, abstention, erreur, annulation, partiel) marquées simulation ; le collègue les lit sans dépendance ML. README fournit commandes et sorties attendues ; cible <5 min mesurée lors de son premier essai, distincte du temps de téléchargement.
- Contrat v1 : schema_version string, session_id opaque, generation entier, status completed|partial|failed|cancelled, conclusion no_signal|verify|indeterminate|null. Horodatages en secondes depuis début média ; coverage = frames utilisables / frames échantillonnées, null si dénominateur nul. Un score absent est null, jamais zéro par défaut ; chaque détecteur a statut et menace évaluée propres. Les modèles/configurations et limites accompagnent le résultat.
- Interface future : python -m visio analyze --input chemin --manifest chemin ; python -m visio benchmark --dataset manifeste --output rapport. stdout contient seulement JSON, diagnostics sur stderr ; --help sans ML. Sortie 0 = analyse achevée, y compris indéterminée analytique ; 2 = entrée invalide ; 3 = panne technique. Pas de téléchargement implicite à l'analyse.
- Donner chaque erreur sous forme code/message/cause/action/retryable/docs. Ne réessayer qu'après correction indiquée ; une panne de nettoyage bloque jusqu'au contrôle réussi du répertoire temporaire appartenant au worker. Les erreurs par détecteur ne deviennent jamais un score nul.
- Configuration : CLI > fichier config > defaults documentés ; chemins cache/manifeste, détecteurs, threads CPU, budgets et mode offline configurables sous limites obligatoires. Empreinte de configuration effective dans le rapport ; seuil ou prétraitement modifié = nouvelle expérience, aucun réglage sur test final.
- README du module relie démarrage, contrat, erreurs, benchmark et ajout d'adaptateur. Version majeure du schéma pour rupture, note de migration et fixtures mises à jour ensemble. Première cible Linux/WSL CPU ; autre OS testé selon environnement réel du collègue, pas de compatibilité prétendue.
<!-- /autoplan-accepted:dx -->

### Phase 3 : ingénierie

Méthodologie lue jusqu'à 1790, critères Architecture/Qualité/Tests/Performance relus dans review-sections. Scope : plan actuel, intégrant la capture MediaPipe. Aucun code applicatif suivi ni framework de tests existant ; aucun bug d'une application existante ni test passé ne peut être revendiqué. FULL_REVIEW, aucune réduction du besoin utilisateur. Les fichiers futurs sont indicatifs. Le minimum cohérent reste un module et ses tests, pas un service par détecteur. Distribution initiale par clone du dépôt privé ; publication de package/container hors scope.

**Natif :** INPUT eng c82cfcbd1cfb5e82afcdae95ffa618a8724c00567017bbdc5ceb64e8caafecb8 vérifié. Six constats : High agrégation, corpus insuffisant et limites non appliquées ; Medium états du contrat, fraîcheur des défis, conformité des adaptateurs. **Externe :** indisponible, `Failed to authenticate: OAuth session expired and could not be refreshed`, session 333b7bf7-7828-4dc4-8885-47e9ab9b521d, usage nul, modèle inconnu.

| Dimension consensus | Natif | Externe | Consensus |
|---|---|---|---|
| Architecture | frontières bonnes, agrégation à préciser | indisponible | N/A |
| Tests | corpus et conformité manquants | indisponible | N/A |
| Performance | isolation à concrétiser | indisponible | N/A |
| Sécurité | fraîcheur non prouvée | indisponible | N/A |
| Erreurs | invariants des états manquants | indisponible | N/A |
| Livraison | local raisonnable | indisponible | N/A |

#### 1. Architecture et état

[P1, confiance 8/10, exigence de plan] « agréger temporellement selon une règle évaluée » (proposition étape 5) laisse deux implémentations incompatibles possibles. Définir d'abord règles candidates et table de décision ; ne pas inventer une calibration avant données. [P1, confiance 8/10] « plafonds explicites » (étape 4) ne précise pas le mécanisme qui interrompt un décodeur natif bloqué : isoler le worker. [P2, confiance 8/10] « consigne imprévisible liée à une session » ne définit pas de frontière de confiance : l'upload reste freshness=unverified. Ces constats portent sur la spécification, pas sur du code existant.

```text
CLI / futur appel collègue -> validation + admission immédiate
                              -> superviseur local (session, génération)
                                  -> worker CPU isolé
                                     decode -> qualité -> adaptateurs
                                              -> observations par détecteur
                                  <- résultat borné
                              -> contrôle génération -> nettoyage -> publication JSON
benchmark -------------------^ même pipeline, manifeste de données gelé
```

Utiliser les primitives de processus de la bibliothèque standard, pas une queue distribuée. Références vérifiées : https://docs.python.org/3/library/subprocess.html et https://docs.python.org/3/library/resource.html . Un timeout doit terminer et récolter les processus ; des pipes capturés sans plafond pourraient encore épuiser la mémoire. Sur Linux/WSL, mémoire du groupe worker bornée par cgroup quand disponible ; à défaut un plafond d'espace virtuel par processus testé ne doit pas être annoncé comme limite RSS agrégée. Sans limite effective démontrée, ne pas accepter d'uploads externes. Cette condition est un test de faisabilité, pas une installation implicite d'infrastructure.

#### 2. Qualité et contrat

[P2, confiance 8/10] « status completed|partial|failed|cancelled » n'impose pas les combinaisons légales avec conclusion. La table retenue ci-dessous les définit et garde un score null si absent. Réutiliser un validateur, un prétraitement propre à chaque modèle et un seul pipeline benchmark/démo ; pas de hiérarchie de plugins. Les versions runtime/décodeur/modèle/config sont dans le rapport. Aucun diagramme de code existant à mettre à jour.

| État terminal | Conclusion autorisée | CLI | Action |
|---|---|---|---|
| completed, tous applicables analysables | no_signal ou verify | 0 | résultat limité au périmètre |
| completed, qualité insuffisante | indeterminate | 0 | nouvelle capture / humain |
| partial, détecteur en panne | verify si signal valide ailleurs, sinon indeterminate | 3 | résultat partiel + panne |
| failed | null | 2 entrée invalide, sinon 3 | correction technique |
| cancelled | null | 130 | aucun résultat analytique publié |

Précédence : échec de nettoyage = failed même si calcul terminé ; conserver seulement diagnostic sans pixels. Un superviseur détient session/generation ; il invalide une tentative avant retry et rejette les retours périmés. États internes ready -> running -> finalizing -> terminal ; terminal après nettoyage réussi ou erreur de nettoyage explicite. L'état analytique ne représente jamais une aptitude au recrutement.

#### 3. Tests et évaluation

[P1, confiance 9/10 sur arithmétique] « 25 attaques réparties » et « au moins 10 sources indépendantes » par quatre catégories ne peuvent être satisfaits ensemble. Conserver 50 clips comme pilote exploratoire, sans qualification de toutes les catégories ; pour revendiquer quatre catégories, jeu de test >=25 authentiques +40 attaques indépendantes, plus développement séparé. Une catégorie non disponible reste non évaluée. Une même personne/source et ses transformations appartiennent à une seule partition.

[P2, confiance 8/10] « vérifier prétraitement et mapping des labels » doit avoir des tests de conformité concrets. Les sorties plausibles avec RGB inversé ou mauvais crop peuvent invalider toutes les métriques. La conformité de chaque adaptateur précède le benchmark.

```text
CODE/FLOWS FUTURS                              TESTS REQUIS (tous encore à écrire)
CLI --help / fixture sans ML                   unité : imports légers, JSON stdout
input absent/vide/trop gros/type faux          unité : InvalidMedia, aucun decode
poids absents/hash/labels/config invalides      unité : refus, pas téléchargement
video rotation/VFR/PTS incohérent              intégration : orientation/temps exacts
decode bloqué/corrompu/OOM/disque plein        intégration : arrêt, nettoyage, erreur
visage absent/multiple/qualité faible          unité+clip : abstention, pas accusation
RGB/crop/resize/normalisation/labels           conformité référence par adaptateur
scores NaN/Inf/forme/faible couverture         unité : résultat invalide/indéterminé
pic court/gap long/durée variable/conflit      unité : règle agrégation figée
annulation avant/après résultat + retry        concurrence contrôlée : rien de périmé
10 appels simultanés                           intégration : 1 admis, 9 busy, pas file
succès/erreur/annulation/crash/redémarrage      intégration : fichiers temporaires purgés
pipeline -> JSON -> consommation collègue      E2E local : fixtures et vrai clip autorisé
corpus/personnes/sources/révisions             contrôle manifeste puis évaluation réelle
option défi expiré/rejoué/mauvaise session     seulement si choisi : test capture active
```

Pas de test généré ici : demande de recherche avant code. Aucun LLM/prompt dans le moteur, donc pas d'évaluation LLM. Pour chaque branche, vérifier code d'erreur, absence de score trompeur et nettoyage. Pas de régression de code historique dans le dépôt vide. Plan QA durable : docs/visio-test-plan.md.

Mesures : rappel bout en bout = attaques signalées / toutes attaques éligibles, abstentions comprises au dénominateur ; rappel conditionnel aussi rapporté séparément. Faux positifs = vrais clips signalés / tous vrais clips ; matrice à trois issues et taux d'abstention par classe, afin qu'un système qui s'abstient toujours ne puisse réussir. Échec technique rapporté séparément et inclus dans la couverture totale. Intervalles d'incertitude et effectifs, aucune comparaison opportuniste après gel.

#### 4. Performance

[P2, confiance 8/10] « 4 Gio de RAM » et « 20 s » sont des cibles non mesurées. Mesurer démarrage à froid, inférence chaude et total, plus pic mémoire du groupe de processus ; le temps du téléchargement est séparé. Pas de DB ou N+1. Charger les modèles une fois si le worker persiste, invalider le cache sur hash/config modifié, ne jamais mettre en cache une vidéo de candidat. Première limite proposée : fichier <=50 Mio, durée <=20 s, résolution <=1920×1080, source <=60 fps, <=1200 frames décodées, <=40 frames échantillonnées ; stop si durée réelle/PTS invalides malgré métadonnées. Au plus une frame complète décodée en mémoire à la fois, crops temporaires bornés. Timeout dur de 60 s, cible chaude 20 s. Temp <=100 Mio dans répertoire privé par tentative, pas de file de captures. Le plafond doit être vérifié pendant l'écriture/décodage, pas seulement annoncé.

#### Failure modes : complément final

| Chemin | Échec | Traitement prévu | Test prévu | Visible |
|---|---|---|---|---|
| agrégation | rafale masquée / gap caché | fenêtres et couverture par détecteur | burst/gap | limites + indeterminate |
| corpus | catégories sous-représentées | non concluant, effectifs | manifeste | rapport invalide pour cette revendication |
| worker | hang/OOM/disque | superviseur termine et récolte | intégration | failed |
| contrat | partial vu comme succès | invariants + code 3 | schéma/CLI | panne et résultat partiel |
| adaptateur | labels/couleurs inversés | référence et tolérance | conformité | détecteur non prêt |
| défi optionnel | replay sous nouvel ID | fraîcheur non vérifiée / rejet protocole | replay/expiry | limite explicite |

Aucun échec silencieux prévu ; garanties restent non testées. Gap produit : la présence live n'est pas prouvée par la baseline passive. Hors scope : entraînement, identité civile, voix, interface complète, connecteurs entretiens, réseau public, AWS et publication package. Existant : dépôt vide + modèles tiers documentés, aucun composant maison à réutiliser. Delta idéal : valider une brique de vérification, sans promettre l'authenticité générale d'un candidat.

**Parallélisation.** Lane utilisateur : visio/ contrat -> adaptateurs -> évaluation. Lane collègue : son module, indépendant après accord du contrat et fixtures. L'intégration vient après les deux ; changements de schéma coordonnés pour éviter conflits. Pas de worktree supplémentaire créé dans cette recherche.

**Completion Summary.** Scope maintenu ; architecture 3 constats, contrat/qualité 1, tests 2 familles de lacunes, performance 1 précision complémentaire. Six constats natifs intégrés au plan ; 15 chemins/familles de tests futurs cartographiés, aucun test exécuté. Registres et hors-scope écrits ; externe indisponible ; Lake score N/A ; choix produit, protocole et cibles exploratoires restent à valider.

<!-- autoplan-accepted:eng -->
- Pour le test final, séparer le développement du pilote de 50 clips ; exiger 25 authentiques de test et au moins 10 sources indépendantes par catégorie revendiquée (donc >=65 clips de test pour quatre catégories). Effectifs moindres = exploration non concluante, sans réduire silencieusement les revendications. Rapporter abstention/échecs par classe et rappel bout en bout incluant abstentions au dénominateur, ainsi que résultats conditionnels.
- Fixer avant test une agrégation par détecteur : candidats fraction de frames au-dessus de seuil et persistance par fenêtre de 2 s ; choix et paramètres sur développement seulement. Conserver observations/horodatages/longest_gap ; couverture minimale 80 % par détecteur, maximum gap non observé 2 s proposé pour clip passif. Alerte valide => verify ; sinon tout détecteur applicable prêt et couverture suffisante => no_signal ; sinon indeterminate. Aucun mélange des scores ; aucune conclusion entre échantillons. Burst plus court que cadence reste une limite déclarée.
- Appliquer la table d'états terminale : completed analytique code 0, partial technique code 3 avec verify ou indeterminate, failed code 2/3 avec conclusion null, cancelled code 130 avec conclusion null. Superviseur seul propriétaire de session/generation, publication après nettoyage et contrôle courant ; erreur nettoyage prime, résultats périmés rejetés. Tester toutes combinaisons, ordre concurrent et crash/restart.
- Worker local séparément terminable, limites d'entrée et de décodage contrôlées en continu : 50 Mio, 20 s, 1080p, <=60 fps, <=1200 frames décodées, <=40 échantillons passifs, temp <=100 Mio, deadline dure 60 s. Admission immédiate d'une tâche sans file ; terminer/récolter processus et purger uniquement leur espace privé. Démontrer une limite mémoire effective avant entrée externe ; cible mémoire groupe 4 Gio, cible chaude 20 s, sans confondre RSS et espace virtuel. Crash/timeout/OOM/disque plein/métadonnées trompeuses doivent être testés.
- Conformité avant accuracy : références prétraitement et tolérances par adaptateur, RGB/crop/resize/labels, orientation, PTS variables, sortie NaN/Inf, zéro frame et plusieurs visages. Manifeste et rapport figent hash modèles/données, runtime, décodeur et config ; jeux de données séparés par personne/source et toutes variantes.
- Si défi guidé choisi ultérieurement, définir générateur de défi, durée de validité, horloge de référence et liaison challenge/session/capture. Uploads => freshness=unverified ; tester replay, expiration, mismatch et injection. Aucun score de landmark, de lip-sync ou de défi réussi ne devient automatiquement une preuve d'identité ou d'absence de deepfake.
<!-- /autoplan-accepted:eng -->


### Audit complémentaire des décisions

| # | Phase | Décision | Type / principe | Motif |
|---|---|---|---|---|
| 15 | DX | JSON typé et fixtures sans modèles | mécanique P4 | permettre deux développements indépendants |
| 16 | DX | erreurs et reprise documentées | mécanique P1 | pas de score rassurant lors d'une panne |
| 17 | DX | CLI et docs courtes | mécanique P5 | pas de service supplémentaire |
| 18 | DX | configuration figée et versionnée | mécanique P4 | reproductibilité |
| 19 | DX | parcours chronométré du collègue | mécanique P1 | vérifier l'intégration réelle |
| 20 | info utilisateur | mesures MediaPipe comme hypothèses | mécanique P5 | sources ne démontrent pas un verdict de fraude |
| 21 | Eng | agrégation et décision explicites | mécanique P1 | éviter des résultats ambigus |
| 22 | Eng | corpus test séparé et dénominateurs | mécanique P1 | corriger l'incompatibilité des effectifs |
| 23 | Eng | processus et budgets appliqués | mécanique P1 | erreurs natives bornées |
| 24 | Eng | invariants et codes CLI | mécanique P5 | protéger le consommateur |
| 25 | Eng | fraîcheur non certifiée sur upload | mécanique P5 | ne pas confondre ID et présence actuelle |
| 26 | Eng | tests de conformité des adaptateurs | mécanique P1 | déceler des scores plausibles mais faux |

26 décisions : 23 mécaniques ; 2 choix provisoires (clip d'abord et cibles exploratoires) ; 1 clarification produit (« vrai humain ») à valider. Cette dernière n'est pas un consensus entre deux modèles : aucune couverture externe achevée.

### Thèmes entre phases

Présence versus manipulation : CEO et Eng indépendants. Résultats interprétables et erreurs : DX et Eng. Corpus et critères de sélection : CEO et Eng. Ces convergences sont des revues natives, pas un accord entre fournisseurs externes.

### Implementation Tasks (agrégées)

Les chemins ci-dessous sont futurs. Rien n'est implémenté. Estimations hors collecte/téléchargement, pas des engagements.

- [ ] **C1 (P1) — Inventorier données autorisées et menaces ; fixer dev/test**. Humain : 2–4 h ; assisté : 1–2 h. Source : CEO corpus et objectif humain. Fichiers futurs : visio/data/manifest.json.

- [ ] **C2 (P1) — Comparer les candidats HF et MiniFASNet sur CPU**. Humain : 1 j ; assisté : 3–6 h. Source : CEO faisabilité et alternatives. Fichiers futurs : visio/benchmark.py, visio/models.json.

- [ ] **D1 (P1) — Définir schéma et fixtures consommables sans poids**. Humain : 2 h ; assisté : 30–60 min. Source : DX contrat High. Fichiers futurs : visio/schema.json, visio/examples/.

- [ ] **E1 (P1) — Implémenter pipeline partagé, limites et états**. Humain : 1 j ; assisté : 3–6 h. Source : Eng limites et contrat. Fichiers futurs : visio/pipeline.py, visio/worker.py.

- [ ] **E2 (P1) — Vérifier conformité, agrégation, pannes et corpus gelé**. Humain : 1 j ; assisté : 3–6 h. Source : Eng six constats. Fichiers futurs : visio/tests/, visio/benchmark.py.

- [ ] **D2 (P2) — Écrire le démarrage, les commandes et la récupération**. Humain : 2 h ; assisté : 30–60 min. Source : DX onboarding et erreurs. Fichiers futurs : visio/README.md.

### Limites de cette exécution

Sources et fiches inspectées ; poids non téléchargés, aucun score d'accuracy ni temps d'inférence mesuré. Aucun code, branche, commit, push ou ressource AWS créés par cette étude. Trois revues natives achevées ; trois appels Claude Code ont échoué avant toute analyse (OAuth expiré). Pas de consensus externe. Les snapshots sont sous /tmp ; listes de tâches, restore et plan QA ont été copiés dans ~/.gstack/projects/Hackaton. Le plan et le plan QA sont aussi durables dans le dépôt. Les revues ont démarré sur main ; le contrôle final constate visio sans changement Git de cet assistant. Les formalités de routing/commit d'onboarding sont omises pour respecter la demande de dépôt minimal ; la revue porte sur le plan, pas sur une application livrée.

Apprentissage durable : anti-présentation MiniFASNet et classificateur HF couvrent des menaces différentes ; une mesure de landmarks n'est pas un verdict deepfake. Vérifier les liens de poids réels avant installation, en particulier le miroir HF yakhyo non accessible anonymement lors de cette recherche.

## GSTACK REVIEW REPORT

| Review | Trigger | Runs | Status | Findings |
|---|---|---|---|---|
| CEO | autoplan | 1 | terminé, choix produit ouvert | 6 constats natifs |
| Design | autoplan | 0 | skipped | aucun frontend demandé |
| DX | autoplan | 1 | terminé au niveau plan | 5 constats ; précision indicative 4,1 → 7,9/10 |
| Eng | autoplan | 1 | terminé, conditions avant implémentation | 6 constats natifs, protocole QA écrit |
| Outside | Claude Code | 3 tentatives | unavailable | OAuth expiré, aucune analyse produite |

**OUTSIDE COVERAGE :** CEO/DX/Eng indisponibles ; design skipped ; 0 accord confirmé, consensus N/A.
**VERDICT :** DONE_WITH_CONCERNS : recherche et revues natives achevées, proposition à valider ; aucune qualification de modèle ni autorisation de livraison inférée.

**UNRESOLVED DECISIONS:**
- Démonstration sur clip d'abord, ou prototype guidé en direct prioritaire ; maintien du besoin utilisateur de présence humaine.
- Accepter les cibles exploratoires et la formulation en indices/abstention ; modèle final à choisir après mesures.

## Suite approuvée et réalisation — 10 octobre 2026

L’utilisateur a retenu le benchmark sur clips avant la capture guidée et confirmé ne pas disposer de vidéos. Son collègue travaille exclusivement sur les métadonnées / background check. Le module `visio/` reste indépendant. Trois adaptateurs CPU, un superviseur local, le contrat JSON, six exemples simulés et les commandes de benchmark / gel sont disponibles. Les tests techniques et limites mesurées figurent dans [le compte rendu](visio-implementation.md). Le choix final de modèle, les seuils calibrés et la qualification de détection restent en attente du corpus ; l’approbation du plan ne constitue pas une validation des performances.
