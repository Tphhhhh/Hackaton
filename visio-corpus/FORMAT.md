# Contrat et admission

Fichiers lus sans modification :

- `/home/theophile/code/perso/Hackaton/visio/benchmark.py`
- `/home/theophile/code/perso/Hackaton/visio/dataset.example.json`
- `/home/theophile/code/perso/Hackaton/visio/core.py` (valeurs de `ATTACKS`)

Leurs empreintes initiales et de vérification figurent dans STATUS.json. Le moteur peut évoluer ailleurs :
revérifier ces empreintes avant intégration.

## Format benchmark 1.0

Racine : `schema_version: "1.0"`, `claimed_categories` non vide et `clips` non vide.
Chaque clip contient `id`, `path`, `split` (`dev`/`test`), `label` (`real`/`attack`),
`attack_kind` (null pour real), `authorized: true`, `permission` non vide,
`source_id`, `person_id`, `sha256`. Chemins relatifs au manifeste ; fichiers existants,
non vides, au plus 50 × 1024² octets ; hash exact et aucun contenu dupliqué même dans un split.
Personne, source et hash ne doivent pas traverser les partitions. Le gel exige les deux splits.

Le manifeste vide livré n’est PAS accepté par ce contrat. `claimed_categories: []` signifie
qu’aucune couverture n’est actuellement revendiquée. Le build les déduit uniquement des attaques
admises et exige leur présence, ainsi que des vrais, dans chaque partition. Pour choisir moins
de catégories, constituer explicitement un registre cohérent avant build ; aucun tri silencieux.

## Fiche d’admission

`clip.template.json` ne représente aucun clip. Tous ses champs null sont à documenter.
Chaque fiche complète d’intake conserve les champs benchmark, plus :

- `person_ids` : toutes les personnes impliquées (cible, donneur, pilote, visage secondaire).
  `person_id` est la personne cible principale et doit figurer dans cette liste.
- `source_ids` : toutes les racines de provenance, y compris médias de donneur/pilotage,
  originaux avant coupe, recodage, replay ou manipulation. `source_id` est la racine principale.
- `provenance` : fournisseur, page/source exacte, identifiant d’origine, date d’acquisition,
  transformations (`none` si aucune), domaine et support selon la table ci-dessous.
  Pour une capture propre, `source_url` peut être un URI local stable (`local:capture/ID`)
  renvoyant au journal privé ; ne pas inventer une URL publique.
- `review` : `label_verified`, `permission_verified`, `lineage_verified`, `media_verified`,
  tous true après revue réelle, `reviewer` pseudonyme et `reviewed_on` (AAAA-MM-JJ).
- `evidence` : pour `label`, `permission`, `lineage`, `media`, chemin local et SHA-256 d’une
  pièce lisible non vide dans `private/`. Ex. ligne d’annotation éditeur avec référence,
  accord et licence applicables, table de correspondance, journal de lecture complète/ffprobe.
  Conserver les documents complets en privé ; les hashes ne prouvent pas leur véracité.

Le script ne devine rien à partir du nom du fichier, d’une prédiction ou d’une image.
Il vérifie les déclarations et les pièces ; un humain doit en vérifier le sens et visionner
le clip complet. Une preuve de label doit établir le type d’attaque, pas seulement « fake ».
Ne jamais marquer une autorisation vraie à partir d’une case vide ou de ce gabarit.

| label / attack_kind | domain | presentation_medium | Sens opérationnel |
|---|---|---|---|
| real / null | bona_fide | live_person | Capture directe, origine attestée |
| attack / photo | physical_presentation | paper | Photo imprimée refilmée |
| attack / screen | physical_presentation | display | Écran refilmé, contenu fixe ou animé |
| attack / face_swap | digital_manipulation | none | Identité faciale substituée dans le fichier |
| attack / reenactment | digital_manipulation | none | Expression/mouvement piloté numériquement |
| attack / digital_replay | digital_injection | virtual_camera | Rejeu attesté dans un flux numérique, sans écran refilmé |

Un MP4 authentique n’est pas un digital_replay du seul fait qu’on le lit. L’injection exige
un journal de session. Les octets identiques ne peuvent pas porter deux labels dans ce corpus.
Un deepfake ensuite refilmé est une attaque composée : conserver sa filiation, mais l’exclure
de ce manifeste à label unique tant qu’une convention dédiée n’a pas été décidée.
Compression, flou ou faible éclairage ne transforment pas à eux seuls real en attack.

## Partitions sans fuite

Choisir les personnes avant de produire les variantes. Affecter manuellement les composantes
connexes du graphe personnes ↔ médias sources à dev OU test : tous les donneurs et pilotes
relient leurs clips, même s’ils ne sont pas visibles dans le résultat. Les listes complètes
`person_ids`/`source_ids` permettent au validateur de refuser une composante transversale.
Ne jamais splitter par fichier, frame, codec ou variante.

Utiliser des identifiants pseudonymes stables et une table d’alias globale, en privé, pour
une même personne présente dans plusieurs jeux. Les identifiants éditeur de vidéo ne sont
pas des identifiants de personne. L’identité inconnue reste hors corpus : pas de faux identifiant
unique par fichier. Un nouveau lien entre dev et test oblige à retirer les clips concernés et
à refaire le gel, jamais à ignorer le lien. Le script refuse les conflits au lieu de réaffecter
silencieusement les partitions. Conserver les décisions de partition dans les fiches et Git.

Le registre admission et le manifeste doivent être revus ensemble. `verify` recalcule le
manifeste depuis intake, compare le résultat entier et vérifie les octets ; une preuve ou une
vidéo modifiée invalide le contrôle. Le gel du benchmark reste une étape distincte.
