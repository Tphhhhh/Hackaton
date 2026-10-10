# Validation du face swap live — 10 octobre 2026

Branche `live`, Linux/WSL, RTX 5060 Laptop GPU (8 Go), Python 3.12,
ONNX Runtime GPU 1.23.2, InSwapper 128 FP16. Source : portrait Brad Pitt
crédité dans `visio-demo/public/filters/ATTRIBUTION.md`.

Le masque WebGL a été supprimé. Le moteur calcule une nouvelle image avec
InSwapper, servie par le serveur loopback ; le suivi conserve MediaPipe.
32 points sont affichés à gauche, aucun à droite par défaut. Chaque vue
propose Aucun / Léger / Complet sans changer l’inférence MediaPipe.

## Contrôles automatisés

- 22 tests Node : contrats, suivi et scores simulés.
- 31 tests Chromium : parcours historiques et webcam, avec vrai MediaPipe.
  Transport InSwapper simulé dans cette suite : erreur/reprise, une requête
  à la fois, réponse tardive après désactivation, arrêt et flux externe.
- 9 tests Python du transport live : validation JPEG avant décodage,
  taille, origine, moteur absent, occupation GPU, erreurs et absence de
  fichiers de capture.
- 7 tests Python d’intégration historique : tous passent.
- Build de production et `git diff --check` : succès.

## Contrôle réel du GPU et du navigateur

Image de test publique `tests/fixtures/grace-hopper.jpg`, placée dans un
cadre 640×480. Ce contrôle n’utilise ni n’enregistre la webcam personnelle.
Le rendu avant/après a été inspecté : le visage est effectivement remplacé,
le reste du cadre est conservé. Aucun restaurateur de visage n’est ajouté.

20 requêtes après préchauffage : médiane **37,35 ms**, p95 **40,77 ms** pour
le décodage JPEG, la détection, le swap et le réencodage côté serveur.

Sur le build servi à `127.0.0.1:8770`, caméra synthétique animée en mémoire,
vrai tracking et vrai endpoint CUDA : **9,7 images transformées/s** sur le
court parcours, **60 ms** d’aller-retour affichés lors de la capture. Aucun
appel externe ni erreur JavaScript observé. Bascule du filtre, absence de
visage et arrêt des pistes validés. Un JPEG uni envoyé au vrai moteur
retourne bien `X-Visio-Swapped: 0`.

La charge simultanée de plusieurs tests Chromium a réduit le débit à
5,8 images/s et porté un aller-retour à 376 ms. Ces mesures sont des contrôles
sur ce poste, pas une garantie pour d’autres caméras, éclairages ou charges.
La webcam physique, les mouvements rapides, profils et occlusions restent
à apprécier en répétition. InSwapper a une résolution faciale native de
128 pixels : il ne remplace pas les cheveux ni la silhouette et ne garantit
pas la finesse d’un rendu vidéo hors ligne.

Les scores de suspicion restent explicitement simulés ; aucune mesure
GenD PE n’a été ajoutée ni validée pour le live.

## Ajout du portrait Sam Altman

Sélecteur Brad Pitt / Sam Altman disponible avant et pendant la capture.
Les embeddings des deux portraits sont calculés au démarrage. Chaque requête
porte un identifiant de portrait autorisé, repris dans la réponse ; changer
la sélection invalide les résultats précédents. Le nom et les crédits suivent
le portrait choisi. En partage externe, le sélecteur et ces crédits sont masqués.

Validation : 14 tests Chromium live et 10 tests Python du transport réussis,
ainsi que le build. Sur le vrai serveur CUDA, passage Brad → Sam → Brad → Sam,
bascule du filtre et arrêt vérifiés avec la caméra de test publique. Rendu Sam
inspecté visuellement dans l’interface ; aucun appel externe ni erreur JavaScript.
Source et licence du nouveau portrait : `public/filters/ATTRIBUTION.md`.
