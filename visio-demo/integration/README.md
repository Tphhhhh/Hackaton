# Handoff frontend — Visio conférence

Ce dossier définit deux **contrats d’adaptation proposés par le frontend**, indépendants du contrat moteur `../reference/schema.json`. L’intégration locale les adopte sans modifier le contrat moteur. `src/local-engine.js` transmet explicitement le clip au serveur Python sur le même ordinateur, puis appelle ces méthodes. Aucun accès webcam ou extracteur de métadonnées n’est implémenté ici.

## Cycle d’un extrait

1. L’utilisateur choisit une vidéo préenregistrée de 2–20 s. Le lecteur valide la durée et dispose de dimensions décodées non nulles.
2. `window.visioDemo.getContext()` retourne :

```js
{
  media: { id, name, duration_seconds, width, height }, // null sans vidéo valide
  analysis: { session_id, generation, media_id }      // null sans résultat
}
```

`media.id` est un UUID **éphémère**, renouvelé à chaque sélection, même pour le même fichier. Ce n’est ni une empreinte du fichier ni une identité. Copier la référence dans les réponses associées à cette sélection. Le nom seul ne doit pas servir à associer les données.

L’événement `window` `visio:mediachange` émet `{ detail: { media } }` quand la vidéo devient prête, ou `{ detail: { media: null } }` lors du retrait/remplacement. Aucun objet File ni octet vidéo n’est exposé dans cet événement. Le File reste privé dans le frontend ; le bouton Analyser le transmet par POST au serveur local.

```js
window.addEventListener('visio:mediachange', ({ detail }) => {
  // Annuler les travaux de l’ancienne sélection si detail.media est null.
  // Conserver detail.media.id avec le travail externe correspondant.
});
```

Le remplacement efface analyse, coordonnées et métadonnées, invalide les lectures de fichiers en cours, et révoque l’ancienne URL blob. Les réponses avec un ancien `media_id` sont refusées. Les méthodes `receive*` ne font pas de requête ; le listener du transport local envoie une annulation au remplacement.

## Résultat visio existant

```js
const context = window.visioDemo.getContext();
window.visioDemo.receiveResult(engineResult, { mediaId: context.media.id });
```

Le JSON respecte **exactement** `../reference/schema.json` (y compris `cause` dans les erreurs). Ne pas y ajouter les coordonnées ou les métadonnées. Le second argument est séparé du JSON moteur. Sans `{ mediaId }`, le résultat peut être lu, mais son association à la vidéo reste indéterminée. Ne déclarer l’association que si l’adaptateur sait que le moteur a analysé l’extrait correspondant ; elle n’est pas vérifiée cryptographiquement par le frontend.

Retour commun des trois méthodes `receive*` : `{ ok: true }` ou `{ ok: false, errors: string[] }`. Elles acceptent un objet JSON sérialisable ou une chaîne JSON, valident et copient les données. Une entrée invalide efface le précédent résultat de sa catégorie pour éviter de présenter une donnée périmée.

## Coordonnées réelles du visage

Schéma machine : [tracking.schema.json](tracking.schema.json).

```ts
type Tracking = {
  schema_version: '1.0';
  media_id: string;            // référence de la sélection courante
  source: string;              // nom/version du détecteur de visage réellement utilisé
  simulation: false;          // le suivi de démonstration fictif est refusé
  coordinate_space: 'normalized';
  frames: Array<{
    time_seconds: number;     // temps absolu depuis le début du clip, pas l’horloge système
    faces: Array<{
      id: string;             // unique dans l’image ; stabilité temporelle souhaitée
      box: { x: number; y: number; width: number; height: number };
      landmarks: Array<{ x: number; y: number; name?: string }>;
    }>;
  }>;
};
window.visioDemo.receiveTracking(trackingResult);
```

- Fournir les **sorties réelles** du modèle de localisation. Le JSON d’analyse ne les contient pas : le moteur exporte un JSON séparé, validé avec `visio/tracking.schema.json`, identique à ce schéma.
- Coordonnées normalisées entre 0 et 1, origine en haut à gauche de l’image décodée orientée, non miroir. Boîte `x,y` = coin supérieur gauche, `width,height` > 0. La boîte doit rester dans l’image. Si le moteur produit des pixels, diviser par les dimensions de l’image **analysée**, puis inverser tout recadrage, redimensionnement, letterboxing ou miroir appliqué avant inférence pour revenir à l’image décodée du lecteur.
- Transmettre uniquement les points réellement produits. Cinq points reçus = cinq points dessinés ; aucune extrapolation en maillage facial. Un tableau de points vide peut accompagner une boîte réelle.
- Instants strictement croissants, dans la durée de la vidéo. À une position donnée, le frontend choisit la dernière observation passée, pendant **250 ms maximum**. Il n’utilise jamais d’observation future ni d’interpolation entre deux visages. L’adaptateur GenD fournit 8 observations/s et maintient l’analyse GenD à 2 images/s ; les lacunes de suivi restent visibles.
- `faces: []` signifie « aucun visage détecté à cet instant ». L’absence d’échantillon récent signifie « pas de coordonnées à cet instant ». Ces situations sont distinguées.
- Le SVG se place dans la zone de l’image avec `object-fit: contain`, y compris avec les bandes noires. Il suit les callbacks des images vidéo quand disponibles, les déplacements du curseur, le redimensionnement et le plein écran. L’option « suivi » masque uniquement la surimpression.
- Limites : JSON 2 Mo, 1 200 instants, 10 visages par instant, 1 024 points par visage. JSON de suivi importable dans « Sources & simulations » ; sa référence doit déjà correspondre à `getContext().media.id`.

Le champ `simulation: false` est déclaratif : le navigateur ne certifie pas la provenance du moteur. Aucun jeu de coordonnées fictives n’est exposé dans la démo ; seule la suite de tests fabrique des formes pour vérifier la géométrie.

## Métadonnées et rapprochement

Schéma machine : [metadata.schema.json](metadata.schema.json).

```ts
type MetadataResult = {
  schema_version: '1.0';
  media_id: string;
  session_id: string;          // session de l’analyse visio correspondante
  source: string;              // module/version ayant produit les contrôles
  simulation: boolean;
  status: 'pending' | 'completed' | 'partial' | 'failed';
  checks: Array<{
    id: string;               // unique
    label: string;
    status: 'consistent' | 'mismatch' | 'indeterminate';
    video_value: string | null;
    metadata_value: string | null;
    detail: string;
  }>;
  errors: string[];
  limitations: string[];
};
window.visioDemo.receiveMetadata(metadataResult);
```

Le module externe choisit les champs réellement disponibles et **effectue les comparaisons**. L’interface affiche ses résultats : « cohérence déclarée », « écart à vérifier » ou « analyse insuffisante ». Les colonnes de valeurs permettent à l’utilisateur de les examiner. Aucun score global fusionné ni décision automatique n’est calculé.

Les états `pending` et `failed` exigent `checks: []`. Les états `partial` et `failed` exigent au moins une erreur. Les valeurs absentes s’affichent « non disponible ». Limites : 100 contrôles, JSON 2 Mo ; détails des tailles de chaînes dans le schéma.

Le bloc « Rapprochement des sources » n’indique des contrôles associés que si :

- les deux résultats sont présents et ne sont pas des simulations ;
- le résultat visio a été explicitement associé au `mediaId` courant ;
- les métadonnées portent le même `media_id` et le même `session_id` ;
- leurs états permettent une lecture (`completed` ou `partial`).

Sinon il indique attente, simulation, absence d’association, sessions différentes ou analyse insuffisante. Une association est une déclaration du producteur, pas une validation d’identité, de présence en direct ou de l’authenticité des sources.

## Effacement et validation à l’intégration

```js
window.visioDemo.clearResult();
window.visioDemo.clearTracking();
window.visioDemo.clearMetadata();
```

Le panneau métadonnées reste vide avant réception. Les six simulations existantes ne remplissent que les résultats visio ; elles ne créent ni points faciaux ni métadonnées. Le parcours vidéo et les points sont testés avec GenD ; une vraie réponse du module métadonnées reste à vérifier quand ce module sera disponible. Les tests locaux valident la frontière frontend et le rendu, pas la qualité des modèles.


## Transport local implémenté

- `GET /api/status` : disponibilité du serveur local et cadences configurées.
- `POST /api/analyze/{media_id}?suffix=.mp4` : corps binaire, `Content-Type: application/octet-stream`, `X-Visio-Request: 1`, 50 Mio maximum. La réponse contient `{ media_id, result, tracking }` ; `result` respecte le contrat moteur inchangé, `tracking` respecte le contrat ci-dessus ou vaut `null` si indisponible.
- `DELETE /api/analyze/{media_id}` : demande l'annulation du worker ; une réponse arrivée après retrait/remplacement ne peut pas être appliquée.

Même origine requise ; pas de CORS, de chemins de fichiers fournis par le navigateur ou de téléchargement distant. L'association utilise l'UUID de sélection et les octets réellement reçus. Les IDs de visages sont propres à chaque observation : aucun suivi d'identité entre deux personnes n'est revendiqué.

Le collègue chargé des métadonnées doit reprendre `getContext().media.id` et, une fois GenD terminé, `getContext().analysis.session_id`. Il peut injecter son objet avec `receiveMetadata` ou le fournir en JSON pour import. Les colonnes de rapprochement restent vides sans cette réponse ; aucune donnée de remplacement n'est produite.
