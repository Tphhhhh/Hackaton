# Corpus d’évaluation vidéo

État au 10 octobre 2026 : **0 clip acquis, 0 label de clip vérifié, aucune évaluation exécutable**.
Les sources consultées exigent un accord, une inscription, ou ne permettent pas de confirmer
l’autorisation de notre usage. Aucune vidéo téléchargée, aucune demande d’accès envoyée,
aucune condition acceptée pour le compte de l’équipe. Ne pas présenter ce dossier comme un corpus validé.

- [SOURCES.md](SOURCES.md) : sources primaires, droits constatés, accès et attaques.
- [CAPTURE.md](CAPTURE.md) : protocole pour enregistrer nos propres clips autorisés.
- [FORMAT.md](FORMAT.md) : contrat du moteur, preuves et règles de partition.
- `intake.json` : registre de clips à renseigner ; actuellement vide.
- `clip.template.json` : fiche non autorisée, sans label ni empreinte inventés.
- `manifest.json` : structure du benchmark, vide et volontairement refusée par celui-ci.
- `corpus.py` : contrôle local et construction du manifeste après admission des clips.

## Remplir le corpus

1. Suivre CAPTURE.md, ou obtenir les droits et métadonnées de la source choisie.
2. Placer les vidéos dans `media/` et les preuves dans `private/` sous ce dossier.
   Les deux sont ignorés par Git, comme tous les fichiers non explicitement autorisés.
3. Copier la structure de `clip.template.json` dans la liste `clips` de `intake.json`.
   Renseigner les preuves réelles, toutes les personnes/sources et la partition choisie.
4. Calculer l’empreinte du fichier reçu avec `sha256sum visio-corpus/media/nom.mp4`
   et la reporter dans `sha256`. Toute transformation crée une nouvelle fiche et une nouvelle empreinte.
5. Depuis la racine de ce worktree :

```sh
python3 visio-corpus/corpus.py audit
python3 visio-corpus/corpus.py build
python3 visio-corpus/corpus.py verify
python3 -B -m unittest discover -s visio-corpus -p 'test_*.py' -v
```

`audit` accepte un registre vide pour en rapporter l’état ; ce n’est pas une validation
benchmark. `build` et `verify` exigent dev ET test, des vrais et chaque attaque revendiquée
dans les deux partitions. Ils échouent tant que le corpus est vide. Aucun téléchargement automatique.
Le script vérifie les pièces locales et leurs empreintes, mais ne remplace pas la revue humaine
des droits, labels et correspondances d’identité. Les fixtures des tests sont des octets artificiels,
jamais des données d’évaluation, et ne sont pas exportées dans le manifeste.

## Limites connues

Le nouveau worktree part de `origin/main` (`c943958`, dépôt initial vide).
Le moteur a été lu à l’emplacement demandé, sans être copié ni modifié par cette tâche.
Des changements externes ont été observés entre deux lectures ; le contrat a été revérifié.
Les empreintes initiales/finales et les 11 tests réussis figurent dans STATUS.json.
Le manifeste généré doit rester dans ce dossier pour que ses chemins relatifs fonctionnent.
Après intégration avec la branche du moteur, régler seulement sur dev puis utiliser sa procédure
`freeze` avant test. Ne pas interpréter l’audit local comme un gel du modèle/configuration.

Pour démarrer, 4 volontaires et 12 clips permettent un essai technique (voir CAPTURE.md),
pas une conclusion statistique. Le benchmark demande au moins 25 sources réelles et 10 sources
par attaque applicable pour ses objectifs PoC ; ces seuils ne garantissent pas l’indépendance
statistique entre clips d’une même personne. Documenter aussi les corpus d’entraînement des
modèles : la séparation dev/test locale n’exclut pas une contamination de préentraînement.
