# Capture de clips propres et autorisés

## Avant la séance

Désigner un responsable, un stockage privé, les personnes pouvant accéder aux fichiers,
une date de suppression et un contact de retrait. Préparer une fiche signée par volontaire
adulte et par la personne qui filme, indiquant l’usage exact « évaluation interne de détection
vidéo », la durée de conservation et le périmètre de partage. Pas de publication ni d’envoi
à un service tiers inclus par défaut. Garder les noms, signatures et correspondances en `private/`.

Recueillir séparément le choix pour : capture authentique, impression/refilmage, écran/refilmage,
injection virtuelle, échange facial, réanimation. Autoriser une catégorie ne vaut pas autorisation
pour les autres. Pour échange/réanimation, les personnes cible ET donneur/pilote doivent accepter.
Une fiche vide n’est pas un accord. En cas de retrait, supprimer tous les dérivés et invalider
les manifestes/gels concernés. Aucun consentement n’a été recueilli par ce dossier.

## Petit pilote : 4 personnes, 12 clips

Avant toute capture, attribuer deux personnes à dev et deux autres à test, par tirage documenté.
Ce sont des quotas prévus, pas des identités ni des labels déjà vérifiés. Chaque personne fournit :

1. Un clip réel de 8–12 secondes : visage visible, parole neutre, clignements et léger mouvement
   de tête naturels ; appareil fixe, 720p, 25/30 fps, MP4 H.264, moins de 50 Mio.
2. Un clip d’une photo imprimée, filmée avec la même caméra et un cadrage comparable.
3. Un clip de sa vidéo affichée sur un écran, filmé avec la même caméra.

Utiliser seulement la photo/vidéo de la personne autorisée ; une image fixe sur écran reste `screen`.
Garder la source photo et la vidéo originale privées et liées par les identifiants de provenance.
Le son peut être désactivé à la capture pour tous les clips si inutile. Ne pas ajouter de filigrane,
carton « fake » ou décor réservé aux attaques. Faire varier éclairage/appareil dans les deux classes
lors de l’extension du corpus ; documenter résolution, durée, fps, caméra, support, distance,
éclairage, compression et éventuels filtres automatiques. Désactiver les filtres de beauté.

## Extension numérique séparée

Seulement après accord spécifique : produire un petit nombre de face swaps/réanimations avec
un outil local autorisé, en conservant version, paramètres, commande, sources, journaux et hashes.
Échanges uniquement entre personnes de la même partition. Vérifier le résultat complet et la
méthode réellement employée avant label ; une génération ratée ou inchangée est exclue.
Un clip de réanimation n’est pas un écran filmé.

Pour `digital_replay`, enregistrer une séance d’injection de notre vidéo dans une caméra virtuelle
locale avec journal explicitant le flux d’entrée et le flux enregistré. Ne pas modifier le moteur
ou une application existante pour ce pilote. L’analyse du seul fichier peut être incapable de
distinguer ce rejeu d’un vrai : rapporter cette limite. Ne pas recoder uniquement pour contourner
le rejet des doublons ; utiliser une capture de session distincte et documentée, ou exclure le doublon.

## Admission après capture

Un opérateur consigne le scénario et les sources. Un second lecteur, si disponible, vérifie
le fichier entier, le label, les accords et la filiation avant toute prédiction du modèle.
En cas de désaccord ou d’identité inconnue : quarantaine, pas de label supposé.
Les preuves doivent être réelles : journal daté, références des accords, inventaire de filiation,
rapport de décodage/visionnage. Calculer les SHA-256 des vidéos et de chaque pièce ; compléter
une fiche par fichier dans intake.json. Nommer par ID opaque, sans nom civil.

Toutes les coupes et recompressions restent dans la partition de l’original. Conserver le hash
de l’original dans les preuves et celui du fichier évalué dans `sha256`. Contrôler avec `audit`,
puis `build` et `verify`. Faire les réglages sur dev, geler corpus/config/modèles via le benchmark,
puis ouvrir test une fois. Les erreurs techniques et abstentions doivent rester dans les résultats.
