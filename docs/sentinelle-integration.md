# Intégration sur une page — 11 octobre 2026

La page `/` sur 8765 remplace le parcours CV/recruteur/onboarding. Deux vidéos, quatre portraits, suivi facial et lissage GenD PE conservés. Le bandeau d’introduction est supprimé. Les règles techniques occupent un panneau latéral, placé sous les vidéos sur écran étroit ; les coordonnées et vérifications supplémentaires sont repliées.

## Architecture

`sentinelle.server.Server` réutilise `visio.server.DemoServer` pour les images, le filtre et les scores. Il ajoute uniquement `POST /api/session/analyze`, une fonction sans stockage appelant `metadata/session.py`. Les protections d’origine et l’en-tête `X-Visio-Request: 1` s’appliquent. JSON limité à 16 Kio, types et nombres bornés. Les anciennes routes d’interface redirigent vers `/` ; les anciens endpoints ne sont plus enregistrés.

`visio-demo/src/session-signals.js` reçoit le flux caméra original par un callback explicite. Aucun deuxième accès caméra. Une mesure toutes les 2,5 s ; les requêtes précédentes sont annulées et les réponses d’une ancienne génération ignorées. Arrêt caméra, changement vers un clip et fermeture de page interrompent les observations. Les seules valeurs transmises au serveur local sont celles nécessaires aux règles ; compteurs de frappe et mouvement, cadence d’affichage et volume restent dans le navigateur.

Le microphone n’est jamais connecté à une sortie audio, enregistré ou envoyé. Son accès est optionnel et ses pistes sont arrêtées en fin de session, y compris si la permission est accordée après l’arrêt. Le capteur mobile est facultatif, sans déduction d’émulation à partir de l’absence de mouvement. Les contacts restent dans les champs HTML sans stockage navigateur ou serveur.

## Règles sélectionnées

| Code | Mesure | Limite |
| --- | --- | --- |
| I1 | Nom des pistes caméra et micro effectivement utilisées | Noms modifiables, usages légitimes de périphériques virtuels ; micro non mesuré tant qu’inactif |
| L1 | Identifiant de piste/périphérique remplacé dans la session | Redémarrer la session remet le compteur à zéro ; pas de preuve d’injection |
| I3 | Chaîne du moteur WebGL | Peut correspondre à un rendu logiciel sans VM |
| I4 | IP publique, changement, nom d’organisation | Heuristique de nom d’hébergeur héritée, pas de classification VPN fiable ; opérateur inconnu reste inconnu |
| I5 | Médiane de trois temps HTTP vers Cloudflare | Comprend DNS/TLS/HTTP ; ne mesure pas la latence de l’appel ni une distance |
| I2 | Écart UTC avec le fuseau explicitement déclaré | ZoneInfo calcule le décalage actuel et l’heure d’été ; non renseigné ≠ suspect |
| I6 | Au moins trois changements de résolution/cadence déclarée par la piste | Adaptation normale possible ; cadence arrondie au dixième pour éviter le bruit numérique |
| X1 | Bonus original : 2 codes +15, 3 ou plus +25 | Conserve la règle du module ; ne garantit pas de réduire les faux positifs |
| C4 | Refus renseigné manuellement, +5 | Permission bloquée ≠ intention de refuser |
| C10/C15 | Domaine jetable et forme d’email | Référentiel limité et heuristique ; aucune analyse de nom/origine |
| C12/C13 | Format international et plages VoIP connues | Référentiel limité ; pas de vérification de possession ou d’opérateur en temps réel |

La console affiche le score global et deux familles : analyse vidéo puis métadonnées, chacune avec cinq segments et un détail repliable. Le score vidéo de confiance vaut `100 − indices GenD PE lissés`. Le score global vaut `max(0, score vidéo de confiance − points métadonnées)`. Une absence d’alerte n’apporte aucun bonus. Ce sont des indices exploratoires, pas des probabilités d’humanité. Le sélecteur Original / Transformé ne change que la source vidéo ; les métadonnées restent communes. Le niveau de chaque groupe est `floor(confiance / 20)` de 0 à 5 : 4–5 vert, 3 ambre, 0–2 rouge. Une source absente est grise et empêche le calcul global. Les métadonnées expirent après 8 s sans réponse ; la vidéo garde son expiration de 3 s. Les règles et leurs poids ne sont pas modifiés.

## Indicateurs vidéo complémentaires

La console présente maintenant cinq observations par source, indépendantes des scores : rythme/répétitions, activité faciale, netteté, cohérence voix/bouche et stabilité des contours. Le micro optionnel alimente aussi une comparaison locale son/bouche. Les mesures du face swap utilisent son propre suivi facial. Voir [les méthodes, limites et durées de vie](visio-signal-layers.md).

## Nouvelles observations

- `navigator.webdriver` / `Headless` : indicateurs d’automatisation, non preuve de fraude. Pas d’identification fiable de Puppeteer/Playwright à partir du navigateur seul.
- `requestVideoFrameCallback` : cadence de présentation et dispersion des intervalles sur au plus 90 images. Ce n’est pas l’horloge du capteur ; le rendu, l’écran et la charge CPU/GPU l’influencent.
- `getCapabilities` : présence de réglages exposition, focus, balance des blancs. Leur absence peut venir du navigateur ou du matériel.
- Interactions : événements de confiance, compteurs de mouvements/frappes/collages et dispersion des intervalles, sans texte ni coordonnées enregistrées. Aucun score d’automatisation.
- Microphone : amplitude instantanée en dBFS et réglage de réduction du bruit. Pas de détecteur de voix synthétique, d’hésitations ou de latence vocale automatique.
- Défis : consigne et chronomètre, confirmation de l’observateur. Réaction et interruption restent des mesures manuelles, sans classification humain/bot.
- Mouvement mobile : norme de l’accélération, au plus 100 échantillons. Immobilité ou capteur indisponible n’entraînent aucun signal.
- IP WebRTC : explicitement indisponible, car la démo n’établit pas d’appel WebRTC. Aucun serveur STUN tiers sollicité.

Références des API : [cadence vidéo](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), [capacités des pistes](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/getCapabilities), [webdriver](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/webdriver).

## Réseau et isolation

Désactivé par défaut. L’activation contacte ipify (IP), ipapi.co (organisation) et Cloudflare (temps HTTP), sans vidéo ni cookies. Rafraîchissement toutes les 30 s environ, timeout par requête, arrêt/annulation lors de la désactivation. Une erreur produit une mesure partielle ou indisponible, jamais « pas de VPN ». Une réponse arrivée après annulation ne restaure pas les informations.

La CSP autorise seulement ces trois domaines en plus de la même origine. Pas d’iframe ; aucun CV, dossier ou télémétrie persisté. Les données sont déclarées par le client et peuvent être falsifiées : ce serveur de démonstration ne fournit pas d’attestation matérielle. Une extension utilisée seulement côté recruteur ne pourrait pas récupérer les périphériques de l’interlocuteur distant.
