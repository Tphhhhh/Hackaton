# Intégration frontend + GenD — 10 octobre 2026

L'interface du worktree `feature/visio-demo` a été copiée dans la branche `visio`, puis reliée au moteur. Le worktree de design est conservé sans modification. Les changements d'intégration suivants sont dans le checkout principal.

## Démarrage

```bash
cd /home/theophile/code/perso/Hackaton/visio-demo
npm ci
npm run build
cd ..
visio/.venv-gpu/bin/python -m visio.server --port 8765
```

Ouvrir http://127.0.0.1:8765. Choisir un MP4/WebM de 2–20 s (50 Mio maximum), cliquer **Analyser avec GenD**, puis lire le clip. Aucun accès webcam ou envoi cloud. Le score est présenté sur 100, sans changement du score numérique sous-jacent et sans conversion en probabilité d'authenticité.

## Chaîne implémentée

1. La sélection donne au clip un UUID et garde son File privé dans le navigateur ; aucun transfert avant clic.
2. Au clic, envoi binaire vers le serveur local de même origine. Le serveur refuse les origines externes, les hôtes inattendus, les corps trop gros et les références invalides. Aucun chemin local arbitraire n'est fourni par le client.
3. Le worker supervisé lance GenD sur la RTX. La localisation réelle InsightFace est échantillonnée à 8 fps pour la surimpression ; l'analyse GenD reste à 2 fps, même seuil et même agrégation. Une seule détection de visage est partagée entre les deux usages à chaque instant concerné.
4. Le résultat moteur conserve le schéma 1.0. Les coordonnées normalisées sont retournées dans un objet distinct conforme au handoff. Ni maillage inventé, ni interpolation, ni certification d'identité. IDs propres à chaque observation.
5. Les réponses sont associées au `media_id` de la sélection. Annuler, retirer ou remplacer une vidéo interrompt la requête et demande l'arrêt du worker. Les réponses périmées ne remplacent pas le nouvel extrait.
6. La copie vidéo privée sous `visio/.cache/browser-uploads/` et les temporaires worker sont retirés à la fin d'une requête/annulation/erreur gérée. Un arrêt brutal peut laisser un dossier à retirer après arrêt du serveur. Pas de média dans Git.

Le transport se trouve dans `visio/server.py` et `visio-demo/src/local-engine.js`. Le serveur sert uniquement le build `visio-demo/dist` et écoute sur `127.0.0.1`. Les schémas sont précompilés au build pour conserver une politique CSP sans `unsafe-eval`.

## Vérifications

- **49 tests Python** : résultats, agrégation, médias, modèles, tracking, annulation du sous-processus, refus des origines externes, limite upload, référence média, nettoyage.
- **20 tests unitaires frontend** : contrat moteur, contrats supplémentaires, absence de données, limites et géométrie.
- **19 tests navigateur Chromium** : import/lecture, rendu, visibilité réelle du SVG et des points, changement d'extrait, métadonnées, erreurs, clavier/mobile, requête explicite, liaison des résultats et rejet des réponses obsolètes.
- Build Vite réussi ; validateurs statiques générés à partir des mêmes schémas.
- Rotation à 90° comparée indépendamment à la sortie auto-orientée de FFmpeg sur une fixture vidéo technique.
- Vérification HTTP + GPU dans un vrai navigateur sur les deux clips ci-dessous ; aucune erreur JavaScript/console, annulation réelle et nettoyage vérifiés. Une vérification supplémentaire rejoue les sorties réellement mesurées sur leurs fichiers d'origine pour vérifier la correction finale du SVG, son bouton de masquage et la lecture.

| Clip de contrôle | Sortie GenD | Score / 100 | Instants de suivi | Points visibles | Temps total avec suivi |
|---|---|---:|---:|---:|---:|
| Authentique, real-01 | aucun indice détecté | 33,51 | 127 | 5 | 37,58 s |
| Deepfake, attack-02 | indice à vérifier | 92,57 | 29 | 5 | 14,46 s |

Ces deux passages vérifient l'intégration, pas la qualité statistique. Le bilan modèle demeure celui du pilote à sept clips : 2/3 deepfakes repérés et 1/4 fausses alertes. Le suivi dense ajoute du calcul ; aucun fonctionnement webcam temps réel n'est revendiqué. Les points apparaissent à la lecture **après** traitement.

Preuves locales ignorées par Git : `visio/reports/frontend-integration/browser-check.json`, `overlay-check.json`, résultats complets `*-bundle.json`, captures `real-01.png`, `deepfake-02.png`, `mobile-empty.png`.

## Correctifs repérés pendant la vérification

- Compilation Ajv dans le navigateur bloquée par la CSP : remplacée par les validateurs statiques générés avant dev/test/build.
- L'attribut HTML `hidden` restait présent sur le SVG malgré l'affectation à `.hidden`. Remplacé par `toggleAttribute`, et test de visibilité des cercles ajouté ; compter uniquement les nœuds SVG ne suffisait pas.
- Limites frontend alignées avec l'intégration : 2–20 s, 50 Mio, MP4/WebM, pour permettre aussi les courts clips DeepfakeTIMIT déjà mesurés.

## Métadonnées : frontière conservée

Aucun background check, extraction de métadonnées ou résultat inventé. Le collègue utilise `window.visioDemo.getContext()` après l'analyse et reprend `media.id` et `analysis.session_id` dans son résultat. `receiveMetadata` ou l'import JSON applique le contrat dans `visio-demo/integration/metadata.schema.json`. Une vraie réponse de ce module reste à tester.

Le handoff actualisé décrit les trois méthodes et le transport dans `visio-demo/integration/README.md`. Les évolutions suivantes de design doivent préserver les ajouts de la branche `visio` (transport, génération des validateurs et correctif SVG).
