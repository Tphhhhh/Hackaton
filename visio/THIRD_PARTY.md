# Provenance des modèles et prétraitements

Les poids sont téléchargés explicitement, jamais ajoutés au dépôt. Les SHA-256 et révisions exactes sont dans `models.json`. Les licences ci-dessous sont celles annoncées par les sources ; conserver ces notices lors d'une distribution de poids ou de code dérivé.

- **dima806/deepfake_vs_real_image_detection** : https://huggingface.co/dima806/deepfake_vs_real_image_detection, Apache-2.0 annoncé. ViT image, labels Real/Fake, input RGB par ViTImageProcessor. Données anciennes signalées par l'auteur ; ne pas généraliser ses scores à une webcam actuelle.
- **prithivMLmods/Deep-Fake-Detector-v2-Model** : https://huggingface.co/prithivMLmods/Deep-Fake-Detector-v2-Model, Apache-2.0 annoncé. ViT image, labels Realism/Deepfake. Sensibilité aux conditions et à la compression ; pas un modèle temporel vidéo.
- **MiniFASNetV2, port yakhyo** : https://github.com/yakhyo/face-anti-spoofing, révision `aea85c1fa14e4d52a7910af75d59ef51e62a2267`, Apache-2.0. Origine : https://github.com/minivision-ai/Silent-Face-Anti-Spoofing. L'implémentation `fas_tensor` adapte le prétraitement de `onnx_inference.py` : contexte 2,7, BGR, valeurs 0–255, entrée NCHW 80×80 ; réel à l'index 1. Les poids ONNX viennent de la release `weights`, dont l'empreinte publiée est vérifiée. Modification locale : YuNet localise les visages à la place de RetinaFace, avec effet à évaluer sur les prédictions.
- **YuNet (OpenCV Zoo)** : https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet ; modèle `face_detection_yunet_2023mar.onnx`, MIT. Sert uniquement à localiser le visage et à déclencher une abstention si l'image n'est pas exploitable.

Les adaptateurs ViT utilisent les configurations de processeur publiées et les poids safetensors. Aucun `trust_remote_code`, notebook ou pickle. Le code de prétraitement GenD est relu puis intégré au dépôt ; aucun code Python distant ne s’exécute au chargement des poids.


## GenD PE-L (modèle de l'interface)

- [Checkpoint officiel PE-L](https://huggingface.co/yermandy/GenD_PE_L), révision `4fd5a38cf071af2640d314110826ed5cd25cab88`, safetensors, 1 264 456 640 octets ; SHA-256 `e2367f8db3a6b76f8d5cc5857f1ed0ea0993b33c9e1f428d3b06e5ca95de2213`.
- Architecture et transformation issues du code GenD MIT à la même révision source que CLIP ci-dessous : backbone `vit_pe_core_large_patch14_336`, `timm==1.0.20`, normalisation L2 puis tête linéaire à deux classes ; transformation d'évaluation RGB 224 avec moyenne/écart-type 0,5. Tous les poids sont chargés strictement depuis le checkpoint complet ; `pretrained=False`, aucun code distant exécuté.
- Réutilise le même alignement et les mêmes poids InsightFace que CLIP. Les conditions propres au backbone Perception Encoder restent à vérifier avant redistribution ou commercialisation ; la licence MIT du code GenD ne suffit pas à couvrir tous les composants.
- L'adaptateur de production `gend_pe.py` est autonome vis-à-vis des dépendances et poids de comparaison Effort. Sources et vérification de parité décrites dans [la comparaison](../docs/visio-model-comparison.md).

## GenD CLIP-L/14 (ajout GPU)

- [Dépôt officiel GenD](https://github.com/yermandy/GenD), code MIT, copyright (c) 2025 Andy. Révision `387a42266dd385fbe8f7626c5d3aa03eea3bfaab`. Notice conservée dans `licenses/GenD-MIT.txt`.
- [Poids GenD](https://huggingface.co/yermandy/GenD_CLIP_L_14), révision `891ce014a0308386c4d7d25b3dcf436a22db5504`, safetensors, 1 215 928 160 octets. SHA-256 `d76f0bdfd74a29fe1b1c1b84a80ac92486993e426878e8c7a3944281fbb96833`.
- `gend.py` adapte `src/hf/modeling_gend.py` : CLIP vision pooler, normalisation L2, tête linéaire 2 classes. La projection visuelle est chargée mais inutilisée, comme en amont. `app/run.py` confirme que softmax index 1 = fake. Chargement strict de toutes les clés ; aucun téléchargement du second backbone CLIP/text encoder, déjà inutile au checkpoint complet.
- Configuration CLIP et processeur : [openai/clip-vit-large-patch14](https://huggingface.co/openai/clip-vit-large-patch14), révision `32bd64288804d66eefd0ccbe215aa642df71cc41`. RGB, resize bicubique, crop central 224, moyennes et écarts-types du processeur épinglé.
- `vendor/gend_alignment.py` reprend la fonction `align_face` officielle ; `vendor/gend_retinaface.py` reprend le localisateur officiel, en retirant téléchargement shell, détection CUDA et programme de démo. CPU ONNX explicite ; seuil visage 0,1, NMS 0,4, entrée 640×640, alignement cinq points échelle 1,3 et taille dynamique.
- `det_10g.onnx` est le poids InsightFace indiqué par GenD, téléchargé depuis le même miroir HF à révision fixe. SHA-256 `5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91`. **Les poids InsightFace sont réservés à la recherche non commerciale**, malgré la licence MIT du code : [conditions amont](https://github.com/deepinsight/insightface#license). Cette dépendance est adaptée à cette évaluation de recherche, mais devra être remplacée ou licenciée avant un usage commercial.

Différences assumées avec le benchmark publié : 2 fps chronologiques (maximum 40), abstention si plusieurs visages ou qualité insuffisante, agrégation locale fraction ≥0,5 des frames au-dessus de 0,5. Le papier utilise son propre protocole d’échantillonnage et d’agrégation. Le prétraitement image est repris, pas la revendication de performance du papier. Float32, attention eager, batch 1 ; aucune optimisation mixte susceptible de masquer la comparaison initiale.
