# Webcam en direct — branche `live`

Depuis `visio-demo`, lancer `npm ci` puis `npm run dev` et ouvrir l’adresse
locale affichée. Cliquer sur **Activer la caméra** et autoriser la webcam.
Le visage est suivi automatiquement (478 points), en vue miroir. **Arrêter la
caméra** libère le flux ; quitter la page le libère également. Le bouton de
suivi masque ou affiche les points. Le microphone n’est jamais demandé.

Le suivi fonctionne sans serveur Python. Les images ne sont ni enregistrées,
ni envoyées à un serveur : `getUserMedia` alimente directement la vidéo, et un
worker MediaPipe traite une seule image en mémoire à la fois, à au plus 20 Hz.
Le débit réel dépend du matériel. Une seule personne est suivie. Le suivi
facial ne produit pas de score GenD et ne vérifie pas l’identité.

Utiliser `localhost`, `127.0.0.1` ou HTTPS (condition d’accès caméra des
navigateurs). Chrome/Edge récents sont les cibles testées. La caméra physique
et les autres navigateurs nécessitent une validation sur l’appareil cible.

Au premier `npm run dev` ou `npm run build`, `prepare:live` copie le runtime
WebAssembly et télécharge le modèle public Face Landmarker v1. Source Google :
https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
Un miroir GitHub versionné sert de repli si Google est inaccessible :
https://github.com/sanderdesnaijer/mediapipe-model-mirrors/releases/tag/v1
Le SHA-256 attendu est vérifié pour les deux sources et le cache local :
`64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`.
MediaPipe Tasks Vision 1.1.0 et le modèle sont distribués sous Apache-2.0.
Les fichiers générés restent dans `public/live-assets/` (ignorés par Git),
puis dans `dist/`. À l’utilisation, toutes les ressources sont servies par
l’application ; aucun CDN n’est contacté.
Documentation du modèle : https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/web_js

Vérification : `npm test`, `npm run test:e2e` et `npm run build`.
Les tests live utilisent une caméra en mémoire avec un portrait public et le
vrai modèle : détection, absence de visage, vue miroir, mobile, arrêt/reprise,
refus de permission, permission tardive, déconnexion et retour à un extrait.

Le mode extrait reste accessible depuis **Ou choisir un extrait vidéo** ou
**Sources & simulations**. Les instructions ci-dessous concernent ce mode.

---

# Visio · démonstration locale

Interface de visioconférence locale, en français, avec vidéo préenregistrée et branchement local de GenD. Grande tuile vidéo, commandes de lecture, jauges par détecteur et onglets Visio / Métadonnées. Le moteur Python reste dans `visio/` ; le module de métadonnées reste indépendant.

## Démo complète avec GenD (branche `visio`)

Depuis la racine du dépôt :

```sh
cd visio-demo
npm ci
npm run build
cd ..
visio/.venv-gpu/bin/python -m visio.server --port 8765
```

Ouvrir **http://127.0.0.1:8765**, choisir un MP4/WebM de 2–20 s, puis cliquer **Analyser avec GenD**. L'environnement GPU et les poids doivent déjà être installés suivant `../visio/README.md`. Le serveur écoute uniquement sur la boucle locale. Il ne fait aucun appel cloud et aucun port n'est ouvert sur le réseau local.

Le clic envoie les octets du fichier sélectionné au serveur sur le même ordinateur. Une copie privée sous `visio/.cache/browser-uploads/` est supprimée à la fin du traitement, de l'annulation ou d'une erreur gérée. Un arrêt forcé de la machine peut laisser un dossier temporaire : le retirer après avoir arrêté le serveur. Aucun média ne doit être commité. Une seule analyse est admise ; le worker GPU est limité à 60 s et 4 Gio RSS.

Le score est affiché sur **100**, sans modifier la valeur du moteur ni la présenter comme une probabilité d'authenticité. La détection faciale produit jusqu'à huit observations par seconde ; GenD conserve deux analyses par seconde. Les cinq points réellement détectés sont dessinés pendant la lecture du clip après traitement. Ce n'est pas une webcam en direct et aucune interpolation ne fabrique des points. Retirer ou remplacer un clip demande l'annulation et empêche toute réponse obsolète de s'afficher.

Les métadonnées restent vides tant que le module externe ne fournit pas de résultat. Contrats et identifiants : [integration/README.md](integration/README.md).

## Développer uniquement l’interface

Avec Node.js 22.12+ (ou 24+) et npm, depuis ce dossier :

```sh
npm ci
npm run dev
```

Ouvrir l’URL locale annoncée par Vite. Le serveur ne sert que l’interface et ses dépendances. Ce mode Vite ne lance pas le moteur ; les imports JSON restent disponibles. Pour l’analyse réelle, utiliser le serveur Python ci-dessus. Aucun extracteur de métadonnées ou background check n’est inclus ici. La durée nécessaire à la validation est lue par l’élément vidéo HTML natif ; Les dimensions décodées servent uniquement à placer les coordonnées faciales sur l’image. Aucune métadonnée du conteneur n’est extraite.

```sh
npm run build
npm run preview
```

`dist/` contient une application statique autonome, sans CDN ni ressource distante. Servir ce dossier par HTTP, et non en ouvrant `index.html` en `file://`.

## Parcours

1. Choisir une vidéo MP4 ou WebM lisible par le navigateur, de **2 à 20 secondes incluses**, au plus 50 Mo. La prévisualisation utilise une URL `blob:` locale. Les URL sont révoquées au remplacement, au retrait, en cas d’erreur et à la fermeture de la page. La sélection seule n’envoie rien ; le clic Analyser lance le transfert local et GenD.
2. Via le panneau Visio, importer un fichier `.json` non vide, au plus 1 Mo. Validation intégrale du contrat JSON Schema 2020-12 par Ajv, y compris les contraintes conditionnelles. Les erreurs de validation sont affichées avec leur chemin. Un import invalide efface le résultat précédent pour éviter une lecture ambiguë.
3. Lire la conclusion fournie, les résultats de chaque détecteur, les scores bruts non calibrés, la couverture, les observations, les erreurs et les limites. Les erreurs de détecteur restent visibles même si elles ne figurent pas dans la liste globale.
4. Dans « Sources & simulations », essayer les six **simulations** : indice à vérifier, aucun indice détecté, analyse insuffisante, partielle, échec et annulation. Aucun exemple n’est exécuté contre la vidéo.

L’import de résultat visio reste indépendant de la vidéo : le lien n’est pas vérifié. L’adaptateur local déclare une association explicite à l’extrait et une session commune avec les métadonnées ; cette déclaration n’est pas une preuve d’authenticité. Le changement de vidéo efface toutes les données associées. Les exemples fournis contiennent une durée analysée de 4 secondes ; ils sont conservés tels quels, dans la plage de 2–20 secondes des vidéos choisies. La conclusion `null` des états d’échec/annulation s’affiche « analyse insuffisante ».

Les textes importés sont rendus via `textContent`. Les références de documentation des erreurs sont du texte, jamais des liens exécutables. Les réponses asynchrones obsolètes ne remplacent pas une simulation ou un résultat plus récent.

## Contrat de référence

`reference/schema.json` et `reference/examples/*.json` sont des copies figées des fichiers lus dans `/home/theophile/code/perso/Hackaton/visio/`. Le contrat moteur reste inchangé par cette intégration. `reference/snapshot.json` consigne la date et les SHA-256 des copies. Ce contrat en développement pourra évoluer : recopier explicitement une nouvelle référence, puis relancer les tests. Les validateurs sont précompilés depuis les schémas par `npm run validators` (automatique avant dev, test et build), sans compilation dynamique dans le navigateur.

## Points d’intégration

Une fois l’interface chargée, appeler dans le même contexte JavaScript :

```js
const outcome = window.visioDemo.receiveResult(resultObject); // ou une chaîne JSON
// { ok: true } ou { ok: false, errors: string[] }
window.visioDemo.clearResult();
```

`receiveResult` valide et copie les données, remplace l’affichage et respecte le champ `simulation`. Un résultat rejeté efface l’affichage précédent. L’API ne reçoit jamais de vidéo et ne lance aucune requête. Le second argument facultatif `{ mediaId }` associe explicitement le résultat à l’extrait courant pour le rapprochement des sources. Le transport local est implémenté dans `src/local-engine.js` et `../visio/server.py` ; les méthodes `receive*` seules ne déclenchent aucun transfert. Les résultats importés sont déclaratifs, sans contrôle d’authenticité. L’interface ne déduit pas d’autre conclusion que celle prévue par le contrat.

## Vérifier

```sh
npm test
npx playwright install chromium
npm run test:e2e
npm run build
```

Pour un Chromium déjà installé, on peut définir `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` avec le chemin de son exécutable. Les tests utilisent un serveur local sur le port 5179. Les fixtures `tests/fixtures/simulation-*s.mp4` sont de petites vidéos synthétiques unies et muettes (aucune personne), générées avec ffmpeg ; aucune dépendance ffmpeg n’est requise pour lancer les tests.

Les tests couvrent les six exemples, le contrat et ses états conditionnels, les limites de taille/durée, les imports invalides, l’intégration, les valeurs nulles, le rendu sûr du texte, les courses d’import, la lecture et le retrait d’une vidéo, les URL libérées, l’absence de transfert avant clic et l’association des réponses au bon extrait, la navigation clavier et le mobile. Les captures sont dans `test-results/` (ignoré par Git). Les codecs disponibles dépendent du navigateur ; un format ou codec illisible produit une erreur explicite.

### Régression ISSUE-001 : erreur réelle du moteur

Le contrat synchronisé exige `cause` (chaîne ou `null`) dans chaque objet erreur, global ou par détecteur. Les éléments `null` de la liste globale `errors` sont désormais invalides ; `detectors.*.error` reste nullable. Les propriétés inconnues restent refusées.

`tests/fixtures/actual-failure.json` est une copie exacte de `/tmp/visio-interface-qa/actual-failure.json`, sortie réelle du moteur capturée pendant le contrôle pour une vidéo absente (`InvalidMedia`, `simulation: false`). Elle est indépendante des six exemples de simulation. Son test de validation a reproduit le rejet de `cause` avant synchronisation. Le test navigateur importe ce fichier et vérifie l’état « Échec », la conclusion « analyse insuffisante » et le message/action du moteur, puis vérifie le même JSON par l’API d’intégration. Aucun moteur ni modèle n’est lancé par les tests.

Référence du contrôle : `/home/theophile/code/perso/Hackaton/docs/visio-interface-qa/report.md`. Cette régression complète les tests des exemples : des copies cohérentes entre elles ne suffisent pas à prouver la compatibilité avec les sorties réelles du moteur.

## Interface conférence et intégration à transmettre

- Les boutons en bas pilotent réellement le lecteur : lecture/pause, son, retour au début, plein écran et retrait. Aucun accès webcam/micro n’est demandé.
- Le panneau Visio affiche des jauges **0–1 de scores bruts**, sans pourcentage de certitude ni conclusion sur l’humanité du participant.
- Le suivi n’affiche que les cadres et points reçus via `receiveTracking`. Aucun faux visage, maillage inventé ou calcul ML. L’état initial indique l’attente du moteur.
- L’onglet Métadonnées réserve la place aux vérifications de l’autre module, avec valeurs de référence, résultats, erreurs et limites. Il ne lit aucune métadonnée lui-même.
- Les contrats frontend, méthodes, règles de synchronisation et responsabilités de l’adaptateur sont détaillés dans [integration/README.md](integration/README.md). Ils sont **distincts du contrat moteur existant**, qui reste inchangé.

Les tests additionnels couvrent la géométrie avec bandes noires, les points absents/anciens/futurs, le changement de vidéo, les imports annexes retardés, les associations explicites, la navigation clavier et les commandes du lecteur. Les coordonnées artificielles présentes dans le code des tests servent uniquement à vérifier le rendu ; elles ne sont jamais proposées dans l’interface. Les validations sur de vrais clips sont consignées dans `../docs/visio-frontend-integration.md`.
