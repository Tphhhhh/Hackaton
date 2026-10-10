# Réalisation visio — 10 octobre 2026

Le plan « benchmark sur clips d’abord » a été approuvé. Le module local `visio/` fournit trois adaptateurs CPU, un superviseur de processus, un contrat JSON et six simulations, ainsi que les commandes analyze, benchmark et freeze. Le background check est indépendant.

## Vérifications effectuées

- 34 tests Python réussis : contrats, prétraitements, agrégation, admission, timeout, protocole worker, partitions et gel du benchmark.
- Trois modèles téléchargés explicitement, empreintes contrôlées, chargement et inférence CPU exécutés. Environnement Python 3.12 isolé ; dépendances figées ; pip check réussi.
- Sur un tenseur uniforme, deux appels par modèle : environ 0,20 s par inférence pour chaque ViT et 0,01 s pour MiniFASNet, avec deux threads. Ceci vérifie uniquement le fonctionnement technique, sans mesure de précision ni garantie de temps réel.
- Parcours réel sur une vidéo technique unie de quatre secondes : huit frames, couverture 0 %, conclusion indeterminate, aucun score inventé. Dernier passage : 5,57 s au total, chargement 4,65 s, pic RSS worker 491 Mio. Aucune personne dans cette fixture.

## Limites et suite

Aucune vidéo authentique ou manipulée d’évaluation disponible : aucun taux de détection, faux positifs ou modèle gagnant établi. Les paramètres sont exploratoires. La collecte autorisée, la calibration sur développement puis le test gelé restent à effectuer. Le moteur traite des clips ; il ne prouve pas la présence en direct.

Le watchdog RSS est une surveillance locale, pas une isolation noyau pour un service exposé. Interface et corpus sont dans leurs worktrees séparés. Aucun commit ni push effectué par cette session.

Démarrage et commandes : [README](../visio/README.md). Plan historique et validation : [plan](visio-plan.md).
