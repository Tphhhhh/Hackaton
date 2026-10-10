# Sources et décisions d’acquisition

Vérification : 2026-10-10, sources primaires consultées en ligne. Ces notes résument les
conditions observées, sans attribuer une licence absente ni certifier les droits de chaque clip.
L’usage commercial/non commercial du projet n’étant pas établi, une permission limitée à la
recherche non commerciale reste conditionnelle. Aucun média acquis ; aucun SHA-256 de vidéo
ne peut donc être fourni à ce stade. Les SHA-256 seront calculés sur les octets effectivement reçus.

## 1. Google/Jigsaw DeepFakeDetection (DFD) — priorité numérique sous accord

- [Annonce Google](https://research.google/blog/contributing-data-to-deepfake-detection-research/),
  [accès et format officiels](https://github.com/ondyari/FaceForensics/blob/master/dataset/README.md).
- Originaux d’acteurs et variantes DeepFakes : candidats `real` / `face_swap`, domaine numérique.
  Le nom des fichiers encode acteur cible, acteur source, scène et expérience. Conserver les deux acteurs.
- [Conditions FaceForensics](https://kaldir.vc.in.tum.de/faceforensics_tos.pdf) : recherche et
  enseignement non commerciaux, accord préalable ; collègues également soumis aux conditions.
  La licence MIT du code ne s’applique pas aux vidéos. Pas d’autorisation générale de redistribution.
- Accès par formulaire approuvé puis script fourni. **Non téléchargé : approbation absente**.
  Après autorisation, viser seulement quelques originaux et variantes, vérifier les identités et limiter le volume.
- Citation : Dufour et al., *DeepFakes Detection Dataset by Google & JigSaw*, 2019.

## 2. FaceForensics++ — face swap et réanimation sous accord

- [Éditeur](https://github.com/ondyari/FaceForensics),
  [conditions](https://kaldir.vc.in.tum.de/faceforensics_tos.pdf).
- Originaux YouTube, Deepfakes/FaceSwap (`face_swap`), Face2Face (`reenactment`).
  NeuralTextures : confirmer la méthode exacte avant mapping ; jamais le classer `screen`.
- Mêmes conditions non commerciales et accès approuvé que DFD. **Non téléchargé**.
  Les exemples visibles ne constituent pas une exemption aux conditions du corpus.
- Risque de fuite : plusieurs séquences d’une vidéo YouTube, donneur/cible, compressions et
  même personne dans plusieurs vidéos. Un numéro de séquence n’est pas un identifiant de personne.
  Refuser les clips dont cette correspondance ne peut pas être établie.
- Citation : Rössler et al., *FaceForensics++*, ICCV 2019.

## 3. DFDC — acteurs consentants, accès non anonyme

- [Meta : corpus et prérequis d’accès](https://ai.meta.com/datasets/dfdc/),
  [portail lié par Meta](https://dfdc.ai/),
  [publication](https://arxiv.org/abs/2006.07397).
- Originaux et modifications faciales numériques ; ne pas convertir le seul label `FAKE`
  en `face_swap` sans preuve de méthode pour le clip.
- Meta indique des acteurs rémunérés ayant accepté l’usage et la manipulation de leur image.
  Cela ne constitue pas notre licence : texte contractuel du portail non vérifié ici.
  **Licence de réutilisation non établie ; non téléchargé**.
- La page exige compte AWS, IAM, clés et inscription avec numéro de compte. Aucun compte créé.
  Ne pas contourner cet accès via un miroir Kaggle/Hugging Face.
- Avant admission : métadonnées original/variante et inventaire complet des identités,
  avec mapping global entre les lots. Citation : Dolhansky et al., DFDC, 2020.

## 4. DeeperForensics-1.0 — intérêt sous double provenance

- [Projet](https://github.com/EndlessSora/DeeperForensics-1.0),
  [documentation et demande](https://github.com/EndlessSora/DeeperForensics-1.0/blob/master/dataset/README.md),
  [Terms of Use](https://github.com/EndlessSora/DeeperForensics-1.0/blob/master/dataset/Terms_of_Use.pdf).
- Recherche non commerciale annoncée ; formulaire à faire approuver. PDF contractuel non
  extrait dans cette session : vérifier intégralement avant acquisition. **Non téléchargé**.
- DF-VAE réalise des échanges faciaux numériques. Les acteurs sources sont annoncés consentants,
  mais les cibles viennent de FaceForensics++ et nécessitent son accès séparé.
  Les vidéos d’acteurs servant à la génération ne sont pas les témoins réels du protocole publié.
- Grouper acteurs donneurs, personnes cibles, sources FF++ et toutes les perturbations.
  Ne pas déduire `reenactment` du seul nom de dossier `reenact_postprocess`.
- Citation : Jiang et al., *DeeperForensics-1.0*, CVPR 2020.

## 5. Replay-Attack (Idiap) — présentation physique

- [Description officielle](https://www.idiap.ch/en/dataset/replay-attack),
  [instructions d’installation Idiap](https://www.idiap.ch/software/bob/docs/bob/docs/v5.0.0/bob.pad.face/doc/installation.html).
- Accès réels, impressions papier, photos/vidéos sur téléphone et tablette refilmées.
  Papier → `photo` ; écran refilmé, même avec image fixe → `screen`. Ce mapping local suit
  le support de présentation ; les groupes « photo » natifs ne sont pas directement équivalents.
- Le guide Idiap demande un accord de licence avant téléchargement. Le bouton actuel vers
  Zenodo n’a pas pu être résolu ; licence actuelle complète et accès libre **non confirmés**.
  Non téléchargé. Le chapeau de la page évoque de l’audio, incohérent avec son descriptif facial :
  vérifier le paquet et les métadonnées avant admission.
- La page annonce une séparation des clients train/devel/test. Conserver devel → dev,
  test → test ; exclure enroll de cette évaluation.
- Citation : Chingovska, Anjos, Marcel, BIOSIG 2012.

## 6. OULU-NPU — présentation physique sur mobiles

- [Description et accès](https://sites.google.com/site/oulunpudatabase/),
  [EULA liée](https://drive.google.com/file/d/1MQ9lAcAsXKpKnmvP96wFhQYq-QPGrZVx/view).
- Vidéos réelles, imprimés et écrans rejoués/refilmés : `real`, `photo`, `screen`.
  Les partitions officielles séparent les sujets ; conserver cette séparation et les variantes par appareil/session.
- EULA à signer par un permanent d’institut, envoi depuis une adresse institutionnelle,
  puis lien transmis après traitement. Le lecteur Drive n’a pas exposé le texte intégral.
  **Conditions détaillées non vérifiées, accès soumis à accord, non téléchargé**.
- Citation : Boulkenafet et al., *OULU-NPU*, FG 2017, DOI 10.1109/FG.2017.77.

## Alternative examinée : Celeb-DF

[Source officielle](https://github.com/yuezunli/celeb-deepfakeforensics) : originaux Internet
et synthèses, lien fourni après formulaire accepté, conditions dans ce formulaire.
La déclaration de confidentialité précise que les originaux n’appartiennent pas aux auteurs.
Conditions complètes et autorisation de notre usage non établies ; pas de téléchargement.
Les noms de célébrités ou l’apparence d’une vidéo ne suffisent pas à établir ses labels ou ses droits.

## Décision pour notre évaluation

La capture propre décrite dans CAPTURE.md est la voie immédiatement préparée, après consentement.
DFD est le candidat externe prioritaire pour les échanges faciaux ; FaceForensics++ pour la
réanimation ; Replay-Attack/OULU-NPU pour les attaques physiques, sous réserve de leurs accords.
Pas de substitution entre ces domaines pour remplir artificiellement une catégorie manquante.
Pour tout futur petit lot libre ET autorisé : maximum initial 12 clips, 200 Mio cumulés,
50 Mio par clip ; URL exacte/version/date, attribution, preuve de licence et labels, puis hash.
Arrêter si une condition est ambiguë ou si seul un lot massif est proposé.
