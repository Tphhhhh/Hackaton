# Comparaison live avec GenD PE — 10 octobre 2026

## Fonctionnement

Sur 8765, le navigateur affiche la webcam originale et sa transformation InSwapper. MediaPipe conserve le suivi facial local. Le filtre reste indépendant des analyses GenD PE, qui ciblent une paire par seconde, une seule requête en vol sans accumulation. Les résultats proviennent des images, jamais de l'état activé/désactivé du filtre.

Pour le filtre intégré, les deux entrées sont le JPEG original effectivement envoyé au swap et le JPEG transformé correspondant. GenD PE refait séparément la détection et l'alignement des visages pour chaque image. Les repères graphiques et l'effet miroir de présentation ne sont pas envoyés au détecteur. Filtre désactivé : les mêmes pixels sont analysés deux fois. Pour une fenêtre externe, deux captures récentes sont utilisées ; leur synchronisation parfaite n'est pas garantie.

GenD PE reste chargé dans le serveur Python GPU ; son protocole d'image est celui de `gend_pe.py` (float32, RGB, alignement officiel, timm 1.0.20). Les poids et leur SHA-256 restent épinglés dans `models.json`. Le face swap tourne dans un processus persistant séparé pour conserver ses dépendances InsightFace / ONNX Runtime GPU / NumPy 1.26 indépendantes de celles de GenD. Pas de lecture ni d'appel à l'application sur 8770.

L'API `/api/live/score` reçoit deux JPEG en mémoire, au maximum 1 Mio chacun, avec longueurs et identifiants de session/capture explicites. Elle renvoie un score ou une abstention par image, le modèle, la révision, `simulation:false` et la durée de calcul. Le navigateur refuse les réponses d'une autre capture, efface les scores aux changements de source/filtre/arrêt, et expire chaque mesure trois secondes après sa capture. Les scores ne sont pas injectés dans le contrat d'analyse de clip : ils représentent une image et non une conclusion sur une vidéo complète.

Une absence de visage, une mauvaise exposition, plusieurs visages ou une taille insuffisante peuvent produire une abstention. Les erreurs ne donnent jamais un score zéro. Aucun son, image webcam ou embedding n'est enregistré. Les deux services partagent physiquement le GPU mais conservent leurs processus, fichiers et ports séparés.

Les jauges live affichent une moyenne exponentielle indépendante par vue : 25 % de la nouvelle mesure et 75 % du score lissé précédent, avec le score brut visible sous la jauge. Les hausses et les baisses suivent la même règle. Une première mesure s'affiche directement ; les variations durables apparaissent progressivement sur plusieurs secondes. Une abstention, une expiration ou une erreur efface l'historique concerné ; un changement de filtre/source ou un arrêt remet les deux historiques à zéro. Les résultats bruts du moteur et l'analyse de clips restent inchangés.

## Démarrage reproductible

Installer l'environnement GenD suivant `visio/README.md`, puis l'environnement indépendant du filtre :

```bash
python3 -m venv visio/.cache/live-runtime
visio/.cache/live-runtime/bin/python -m pip install -r visio/requirements-live.lock.txt
visio/.cache/live-runtime/bin/python -m visio.setup_live
cd visio-demo
npm ci
npm run build
cd ..
visio/.venv-gpu/bin/python -m visio.server --port 8765 --live-swap --live-pe
```

Pour cette machine, les dépendances déjà validées du filtre ont été copiées dans un nouvel environnement local, sans modification de l'environnement utilisé par 8770. Les poids live et les fichiers MediaPipe ont également été copiés localement. Les deux moteurs ont ensuite été chargés et exécutés dans cette nouvelle installation.

## Mesures réelles

Contrôle Chromium du build de production à `http://127.0.0.1:8765/`, avec une caméra de test animée en mémoire à partir de la photographie publique `grace-hopper.jpg`. Aucun remplacement de l'API de score ou du filtre pendant ce contrôle : vrai InSwapper CUDA, vrai GenD PE CUDA et vrai MediaPipe.

| Vérification | Résultat |
|---|---|
| Original / visage transformé | 24,44575 / 99,82629 sur 100 |
| Filtre désactivé | 24,44575 / 24,44575 sur 100, égalité exacte |
| Inférence des deux images après premier passage | médiane 599,8 ms sur cinq paires |
| Première paire | 1 631,8 ms |
| Filtre pendant le contrôle | environ 9,63 images/s ; médiane serveur 40,85 ms |
| Absence de visage, arrêt caméra | jauges effacées, pistes fermées |
| Erreurs JavaScript / requêtes externes | aucune |

Ces mesures sur un court parcours et une image publique vérifient l'intégration, pas la précision générale ni la fluidité avec toutes les webcams. Les faux négatifs constatés sur d'autres générateurs restent possibles. Les scores affichés ne sont pas des probabilités d'authenticité.

Preuves locales ignorées par Git : `visio/reports/live-pe/browser-real.json`, `real-pair.png`, `filter-off.png`. Les captures concernent uniquement la fixture publique. Sauvegarde de l'application précédente : `visio/reports/before-live-pe/`.

Validation : 70 tests Python, 20 tests Node et 34 tests navigateur. Deux tests navigateur ont nécessité une reprise ciblée : adaptation du faux moteur de test à l'abstention sur une image sans visage, et reprise d'un test d'import pendant lequel une reconstruction concurrente avait modifié les fichiers servis. Les deux reprises passent. Les tests de délai vérifient l'absence de file d'attente et de résultat périmé après arrêt ; les tests d'expiration vérifient que le filtre peut continuer lorsque les scores deviennent indisponibles.

## Provenance du filtre

Le filtre et son transport visuel proviennent de la branche `live`, commit `25b4035`. Modèles InSwapper / InsightFace à empreintes épinglées dans `visio/live_swap.py`, révision de téléchargement `581e70b61240b7928404c17900437f47cfe94133`. Les restrictions des poids InsightFace restent applicables. Attribution du portrait de référence dans `visio-demo/public/filters/ATTRIBUTION.md`. Le serveur 8770 n'a été ni redémarré ni modifié pour cette intégration.

### Portraits sélectionnables

Le menu « Visage » propose Brad Pitt, Sam Altman, Emmanuel Macron et Nicolas Sarkozy, repris de la branche `live`. Le portrait choisi est transmis au processus InSwapper pour chaque image ; GenD PE analyse les pixels effectivement produits. Un changement de portrait annule les mesures en attente et réinitialise le lissage des deux jauges. Les crédits suivent le portrait sélectionné.
