# Visio · GenD PE + signaux de session

Une seule page : webcam originale, version transformée, console avec score global, analyse vidéo lissée et métadonnées. Aucun CV, parcours candidat ou inscription à compléter.

## Lancer

Avec les environnements GPU déjà installés, depuis la racine :

```sh
visio/.venv-gpu/bin/python -m sentinelle.server --port 8765
```

Ouvrir **http://127.0.0.1:8765/**, puis activer la caméra. Un seul serveur doit utiliser ce port. La démo indépendante sur **8770** ne doit pas être arrêtée.

La même caméra alimente le suivi, les filtres, GenD PE et les observations techniques. La console calcule un indice de confiance global : **max(0, 100 − indices GenD PE lissés − points d’alerte métadonnées)**. Aucune alerte appareil n’ajoute de points. Les composantes sont affichées avec cinq segments, verts pour un indice de confiance élevé et rouges pour un indice faible, sans interprétation probabiliste. Le choix Original / Transformé sélectionne la vidéo évaluée ; les métadonnées sont communes. Une composante absente empêche le calcul global. Les métadonnées décrivent **cet appareil**, commun aux deux vues, et non l’ordinateur d’un interlocuteur distant. Ce POC n’établit pas d’appel Zoom/Meet/WebRTC.

## Panneau de session

- **Règles conservées** : I1, L1, I3, I4, I5, I2, I6, X1 ; C4 faible (5 points), C10/C15 et C12/C13 facultatifs. X1 conserve +15 pour deux signaux parmi I1/I2/I3/I4/I5, +25 pour trois ou plus.
- **Réseau facultatif** : contacte ipify, ipapi.co et Cloudflare après activation explicite. Mesure l’IP publique, ses changements, l’organisation et le temps HTTP vers Cloudflare. Le nom d’opérateur donne seulement un indice d’hébergement ; ce n’est pas une détection fiable de VPN ni une localisation de l’interlocuteur. Aucun pays n’est pénalisé.
- **Observations sans score** : indicateurs d’automatisation exposés, cadence d’affichage, réglages caméra exposés, compteurs d’interactions sans contenu. Le microphone et les capteurs de mouvement nécessitent une action séparée ; seule une mesure locale de volume/réglages et de mouvement est effectuée.
- **Défis guidés** : tête, main, code lu, temps de réponse, interruption. Chronomètre et confirmation **manuelle**, sans vérification automatique de la réponse ou du geste.
- Les informations absentes apparaissent **non mesurées**. Refuser une permission ne déclenche pas automatiquement C4. Arrêter la caméra efface les mesures et interrompt le microphone, les capteurs et les requêtes réseau. Les coordonnées facultatives restent dans les champs de la page jusqu’à leur effacement ou son rechargement.

Aucun enregistrement audio/vidéo ni dossier n’est créé. L’API technique est sans état et ne conserve pas les mesures. Les vidéos sont analysées en mémoire ; les clips importés utilisent le mécanisme temporaire existant de Visio. Les fichiers historiques du module `metadata/` restent des sources de référence et ne sont pas exposés par ce serveur. Les anciennes pages candidat redirigent vers `/` et leurs API ne sont plus disponibles.

## Installation et interface

Voir [visio/README.md](visio/README.md) pour GenD PE et [docs/visio-live-pe.md](docs/visio-live-pe.md) pour le filtre. Les poids et environnements ne sont pas versionnés. Construire l’interface :

```sh
cd visio-demo
npm ci
npm run build
```

Pour travailler sans GPU : `visio/.venv-gpu/bin/python -m sentinelle.server --port 8765 --no-models`. Aucun score vidéo n’est simulé dans ce mode. Les dépendances historiques Bedrock/Streamlit de `requirements.txt` ne sont pas nécessaires au serveur intégré.

## Vérifier

```sh
visio/.venv-gpu/bin/python -m pytest sentinelle/tests/test_integration.py -q
cd visio-demo && npm test
```

Tests navigateur depuis la racine :

```sh
node visio-demo/node_modules/@playwright/test/cli.js test -c sentinelle/playwright.config.mjs
```

Le serveur de test utilise le port 8891 et des scores fixes explicitement réservés aux tests ; il ne mesure pas la qualité du modèle. La démo sur 8765 utilise les véritables modèles installés. Les détails et limites sont dans [docs/sentinelle-integration.md](docs/sentinelle-integration.md).
