# Suites possibles après la recherche visio

Ces tâches sont différées, pas des fonctionnalités approuvées.

## P2 — Choisir et éprouver une capture guidée

**What :** comparer interaction locale/humaine et Rekognition Face Liveness si la présence actuelle est prioritaire.
**Why :** un classificateur passif peut accepter une vraie vidéo rejouée.
**Context :** voir docs/visio-plan.md, notamment GOTCHA et les limites des landmarks. Évaluer fraîcheur, liaison à la session, replay/injection et alternative accessible. AWS reste optionnel, sans activation actuelle.
**Pros / Cons :** rapproche du besoin live ; ajoute capture, protocole et éventuellement dépendance cloud.
**Effort :** humain 1–2 jours / assisté 3–6 heures, hors accès et corpus.
**Depends on :** choix utilisateur du protocole, corpus autorisé, contrat partagé.

## P3 — Étudier audio et éclairage

**What :** évaluer synchronisation audiovisuelle et cohérence d'éclairage comme signaux additionnels.
**Why :** pistes fournies par l'utilisateur, sans qualité de détection démontrée.
**Context :** corrélation bouche/énergie sonore et sauts de landmarks ne suffisent pas à classifier une fraude. Prévoir vrais clips désynchronisés et captures dégradées comme contrôles négatifs.
**Pros / Cons :** observations complémentaires ; faux positifs, collecte et traitements supplémentaires.
**Effort :** à estimer après protocole et données ; pas d'engagement d'implémentation.
**Depends on :** baseline mesurée, décision explicite sur audio et protocole.

## P3 — Connexion entretien et service partagé

**What :** intégrer capture navigateur ou plateforme d'entretien, puis accès partagé si nécessaire.
**Why :** permettre une utilisation pendant l'entretien après faisabilité locale.
**Context :** aucun frontend ou connecteur hérité. Répartir avec le collègue ; auth/session/TLS avant réseau. Une fenêtre d'analyse passive ne certifie pas tout l'entretien.
**Pros / Cons :** démonstration intégrée ; complexité de transport et de confiance de capture.
**Effort :** humain 1–3 jours / assisté 3–8 heures, très dépendant de la stack.
**Depends on :** contrat et benchmark, choix clip/live, stack du collègue.
