# Contrôle interface Visio — 10 octobre 2026

URL : http://127.0.0.1:4183/ · branche feature/visio-demo · Vite · une page.

## ISSUE-001 — Un résultat réel en erreur est refusé

Sévérité : moyenne ; catégorie fonctionnelle. Reproduit deux fois.

1. Importer un résultat réel sans erreur : affichage correct.
2. Importer `actual-failure.json`, produit par le moteur pour un fichier absent.
3. Le validateur affiche `/errors/0 → cause : must NOT have additional properties`.

Attendu : afficher l’état failed et l’erreur InvalidMedia. Observé : résultat refusé, écran vide. Les fixtures figées passent mais le contrat courant du moteur a évolué.

Preuves : [avant](screenshots/actual-result.png), [refus](screenshots/actual-failure.png). Aucun correctif appliqué lors de cette revue.

## Vérifications terminées

- 12 tests de contrat et 9 parcours Chromium passent ; compilation Vite réussie. Tests navigateur et build rejoués dans une copie temporaire identique de l’interface pour préserver le worktree.
- Six simulations, import JSON invalide, concurrence de lecture, vidéo locale 10/12/20 s, durée refusée 9/21 s, nettoyage des URL, clavier et mobile couverts par les parcours.
- Résultat réel du moteur sans visage importé : trois détecteurs indéterminés, scores absents affichés comme indisponibles ; correct.
- Échec réel du moteur rejeté deux fois à cause du champ cause : ISSUE-001 reste ouvert malgré les tests des fixtures figées.
- Aucune erreur console observée sur les deux imports réels. Captures bureau et mobile inspectées ; pas de défaut de mise en page constaté sur ces vues.
- Limites d’intégration futures : prévisualisation 10–20 s / 100 Mio / MP4-WebM-Ogg, moteur 2–20 s / 50 Mio / MP4-MOV-MKV-WebM-AVI. Les parcours restent indépendants actuellement.

## Score provisoire

97/100 sur le périmètre testé : console 100 (poids 15), visuel 100 (10), fonctionnel 92 (20), accessibilité 100 (15, clavier seulement). Autres catégories non notées. Une anomalie moyenne, zéro haute/critique constatée. Ce score ne vaut pas validation complète d’accessibilité ou de sécurité.

## Corpus

11 tests du préparateur réussis. Un manifeste construit depuis quatre fixtures artificielles est accepté par le lecteur actuel du moteur. Le manifeste livré contient zéro clip et est refusé pour benchmark, comme attendu. Aucun téléchargement ou performance de détection confirmé. Sources et protocole préparés ; acquisition à effectuer.

## Apprentissage durable

Les exemples de contrat copiés dans un worktree peuvent diverger pendant le développement parallèle. Des tests verts sur ces copies ne démontrent pas la compatibilité avec les sorties actuelles du moteur, notamment ses erreurs. Les deux imports réels ont mis en évidence cette différence.

Aucun fichier de l’interface ou du corpus modifié lors du contrôle. Aucun message envoyé aux autres sessions.

## Recontrôle après correction de l’interface

ISSUE-001 résolu : schémas moteur/interface identiques, 14 tests de contrat réussis. Import du même fichier actual-failure.json dans Chromium : état Échec, détail InvalidMedia et action affichés, aucune alerte de validation ni erreur console. [Preuve après correction](screenshots/failure-fixed.png). Le score et baseline précédents décrivent le contrôle initial ; aucune nouvelle revue exhaustive effectuée.
