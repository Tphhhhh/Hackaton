# Module metadata : cross-check des candidatures

Partie « métadonnées » du projet (la détection de deepfakes vidéo est un module séparé).

## Problème

Des fraudeurs, dont des réseaux étatiques, se font embaucher à distance sous de fausses
identités, puis volent des données ou détournent des salaires. Un même opérateur peut
porter une douzaine d'identités. La cible : **toute entreprise qui recrute à distance**, en
particulier des profils tech ou des postes qui donnent accès à des données sensibles
(production, données clients, paiements). Ce module aide les équipes RH et sécurité à repérer
ces dossiers à partir d'incohérences factuelles et de candidatures qui se ressemblent trop.

## Architecture

```
candidates.json ─► checks.py      contrôles de cohérence (18 règles explicables)
                ─► similarity.py  identifiants recyclés + CV quasi identiques ─► réseaux (graphe)
                ─► scoring.py     score 0-100, niveau, signaux
                ─► explain.py     résumé + questions de vérification (Bedrock ou gabarit)
                ─► run.py         report.json / report.md + audit.jsonl
humain          ─► decide.py      décision tracée dans le journal d'audit
                   audit.py       journal chaîné par hash, vérifiable
                   evaluate.py    métriques pour la fiche de défense
```

| Code | Contrôle | Poids | ATT&CK |
| --- | --- | --- | --- |
| C1_TIMELINE | Postes simultanés > 6 mois, dates impossibles | 20 | |
| C2_SENIORITY | Ancienneté annoncée ≠ expériences listées | 10 | |
| C3_YOUNG_PROFILE | Profil pro créé < 6 mois avant la candidature | 15 | T1585.001 |
| C4_CAMERA | Caméra refusée en entretien | 15 | T1656 |
| C5_FORWARDER | Matériel envoyé chez un transitaire connu (25), ou à une adresse d'entrepôt / réexpédition (« cargo », « freight », « Lager », « entrepôt »…) (20) | 20-25 | |
| C6_ADDRESS_CHANGE | Matériel à livrer ailleurs qu'à la résidence, < 30 j après l'embauche | 10 | |
| C7_LOGIN_COUNTRIES | Connexions hors du pays déclaré | 20 | T1078 |
| C8_NIGHT_HOURS | Activité la nuit dans le fuseau déclaré | 15 | |
| C9_CRYPTO | Salaire demandé en cryptomonnaie | 20 | |
| C10_DISPOSABLE_EMAIL | Email sur domaine jetable | 10 | |
| C11_PAYEE | Compte de paie au nom d'une autre personne | 20 | |
| C12_PHONE_INVALID | Téléphone mal formé pour son indicatif, chiffres répétés ou plage réservée aux films | 10 | T1585 |
| C13_PHONE_VOIP | Numéro virtuel (VoIP nomade, numéro de renvoi : UK 056/070, DE 032, ES 51…) | 10 | T1585 |
| C14_PHONE_COUNTRY | Indicatif différent du pays de **résidence** déclaré | 5 | |
| C15_EMAIL_RANDOM | Email d'apparence générée (série de chiffres, lettres imprononçables) | 10 | |
| C16_EMAIL_NAME | Email sans le prénom ni le nom (10 s'il contient un mot type « dev », « crypto ») | 5-10 | |
| C17_PROFILE_NAME | URL LinkedIn sans rapport avec le nom (10 avec un mot type « senior-dev-expert ») | 5-10 | T1585.001 |
| C18_SHIPPING_COUNTRY | Ordinateur à livrer dans un autre pays que la résidence déclarée | 20 | |
| X2_CONTACT_COMBINATION | Anomalies sur 2 coordonnées différentes (email, téléphone, profil) : +10, sur 3 : +15 | 10-15 | T1585 |
| S1_PERSONA_NETWORK | Lié à d'autres candidatures : identifiant partagé (téléphone, IBAN, email, profil, bénéficiaire du salaire) ou parcours identique (30) ; seulement un CV très proche (15) | 15-30 | T1585 |

Score ≥ 25 : dossier à vérifier ; ≥ 50 : risque élevé. Le score priorise la revue, il ne
décide jamais.

**Coordonnées (C12 à C17).** Le téléphone est lu avec un plan de numérotation par pays
(`reference/phone_plans.json` : longueur attendue, tranches VoIP, plages réservées aux fictions).
Il est comparé au pays de **résidence** que le candidat déclare, jamais à une origine supposée :
comparer à une origine reviendrait à traiter différemment les candidats selon leur nationalité
(discrimination interdite, et pratique à haut risque au sens de l'AI Act). Un expatrié garde
souvent son ancien numéro, donc ce signal pèse 5 et ne compte qu'en combinaison. Aucun pays
n'est plus suspect qu'un autre : un +41 et un +86 pèsent pareil. En production, un service de
vérification d'opérateur (type de ligne mobile, fixe ou VoIP) remplacerait le tableau. L'email est
comparé au nom déclaré (avec translittérations « Müller » = « mueller », diminutifs, initiales) ;
les pseudos GitHub ne sont pas contrôlés, ils sont libres par nature. Le pays de l'IBAN n'est pas
un signal : le règlement SEPA interdit de refuser un IBAN d'un autre pays de la zone.

## Installation et utilisation

Python 3.10+, aucune dépendance pour le mode local.

```bash
python -m metadata.data.generate                 # 50 dossiers synthétiques, dont 20 frauduleux
python -m metadata.run                           # rapport dans out/report.md
python -m metadata.evaluate                      # détection, faux positifs, réseaux, temps
python -m metadata.decide C017 --decision verify --analyst "Ludovic" --note "Appel vidéo demandé"
python -m metadata.audit verify                  # intégrité du journal d'audit

pip install streamlit
streamlit run metadata/app.py                    # interface de démo dans le navigateur
```

Bedrock (optionnel) : `pip install -r requirements.txt`, copier `.env.example` en `.env`,
renseigner les clés et mettre `USE_BEDROCK=1`. Les embeddings Titan remplacent alors la
similarité locale et un LLM rédige l'explication. Le `.env` n'est jamais commité.

## Signaux de l'entretien et module vidéo

Pendant l'entretien, six contrôles s'ajoutent (champ `interview_session` du dossier) :

| Code | Contrôle | Poids | Cas légitime à ne pas punir |
| --- | --- | --- | --- |
| I1_VIRTUAL_DEVICE | Caméra ou micro virtuel (OBS, ManyCam, XSplit, VB-Audio, Voicemod…), ou caméra changée en cours d'appel | 10 | Flou d'arrière-plan (NVIDIA Broadcast, logiciel Logitech) : non signalé |
| I2_TIMEZONE | Fuseau de l'ordinateur à 2 h ou plus du fuseau déclaré | 10 | Expatrié, ordinateur mal réglé (écart d'une heure toléré) |
| I3_VIRTUAL_MACHINE | Moteur graphique logiciel ou de machine virtuelle (SwiftShader, llvmpipe, VMware…) | 15 | PC d'entreprise virtualisé |
| I4_INTERVIEW_IP | IP hors du pays déclaré, IP d'hébergeur, IP changée pendant l'appel | 10 à 25 | VPN d'entreprise |
| I5_LATENCY | Temps de réponse médian > 150 ms pour un candidat en Europe | 15 | 4G faible, Wi-Fi saturé |
| I6_VIDEO_SETTINGS | Résolution ou cadence modifiée 3 fois ou plus | 5 | Changement de réseau |
| X1_COMBINATION | Bonus quand 2 signaux d'entretien concordent (+15), ou 3 et plus (+25) | 15-25 | |

Un signal isolé pèse peu ; c'est la combinaison qui fait monter le score. **La langue du
système n'est volontairement pas utilisée** : c'est un indicateur indirect d'origine.

**Scores vidéo** (module de Théophile) : `video_scores.json` à côté des dossiers, un objet par
candidat avec des scores de 0 à 1 (`challenges`, `lipsync`, `temporal`, `lighting`,
`classifier`). Voir `video.py`. Les défis pèsent le plus (jusqu'à 35), le classifieur générique
reste un signal faible (5). Le générateur écrit des scores **simulés** en attendant les vrais.

## Mode en direct

```bash
python -m metadata.live.server
```

- `http://localhost:8000/apply` : offre d'emploi fictive (« Fjordlane »). Comme une vraie
  candidature, elle ne demande ni adresse ni coordonnées bancaires. Le candidat dépose son CV :
  le PDF est lu dans le navigateur (pdf.js, embarqué dans `live/vendor/`), `cv_parser.py` en
  extrait les champs (règles, ou Claude Haiku via Bedrock si `USE_BEDROCK=1`) et le formulaire
  se pré-remplit ; le candidat vérifie et corrige. Puis taux journalier, disponibilité, et les
  métadonnées techniques annoncées. Chaque dépôt est analysé avec les dossiers existants. Le
  bouton « Démo » dépose un des deux CV de `live/demo_cvs/` (Camille, honnête ; Daniel, qui
  recycle le téléphone d'un réseau connu). `python -m metadata.live.make_demo_cvs` les régénère.
- `http://localhost:8000/onboarding?app=ID` : une fois le candidat recruté (lien dans le panneau
  recruteur). Adresse de résidence, livraison de l'ordinateur, compte bancaire pour la paie.
  C'est là qu'apparaissent les signaux les plus forts (transitaire, salaire versé à un tiers) :
  le score du dossier est recalculé et monte dans le panneau recruteur.
- `http://localhost:8000/` : page candidat. Écran de consentement (ce qui est mesuré, ce qui ne
  l'est jamais), puis une mesure toutes les 5 secondes.
- `http://localhost:8000/recruiter` : console « Sentinelle » des équipes RH et sécurité. Pour
  chaque candidature et chaque entretien : score, signaux en clair, réseau détecté, questions à
  poser, décision humaine signée dans le journal d'audit.

Démo : déposer le CV de Daniel, puis remplir son onboarding (65 après la candidature, 100 après l'onboarding). Lancer l'entretien, puis activer un VPN ou choisir une caméra virtuelle (OBS) dans la
liste : l'alerte apparaît en quelques secondes. Si le réseau du lieu bloque le VPN, le menu
« Mode démo » de la page candidat simule ces changements (marqués « simulation »).

Limites du prototype : la page doit tourner en `localhost` (le navigateur n'autorise la caméra
qu'en local ou en HTTPS). L'IP publique, son pays et le temps de réponse sont obtenus depuis le
navigateur via des services publics (ipify, ipapi.co, Cloudflare) ; en production, ce serait
fait côté serveur avec une base GeoLite2, sans tiers.

## Conformité et éthique

- **Données** : uniquement synthétiques (RGPD).
- **Aucun signal d'origine, de nationalité, de langue ou d'accent.** Les pays (connexion,
  indicatif du téléphone, livraison) ne comptent que s'ils contredisent le lieu de **résidence**
  déclaré par le candidat, et tous les pays pèsent pareil. Les noms sont tirés
  au hasard indépendamment du statut fraude.
- **AI Act** : outil de filtrage de candidatures, donc à haut risque (annexe III, point 4).
  Supervision humaine (decide.py), explication de chaque score, journal d'audit inviolable,
  information du candidat (article 50) à prévoir dans le parcours de candidature.
- Le LLM ne reçoit que les signaux factuels, pas l'identité du candidat.

## Évaluation sur un jeu indépendant

Aucune base publique de candidats frauduleux n'existe (les jeux Kaggle portent sur les fausses
**offres** d'emploi). On a donc écrit un jeu à part, `data/blind/` (voir son README) : 2 × 160
dossiers, 44 fraudes chacun, profils de fraude tirés des alertes FBI / DOJ, et beaucoup de cas
honnêtes piégeux (expatriés, déménagements, VPN d'entreprise, emails pseudonymes, noms à
umlaut, bootcamps aux CV identiques…). Règle : on règle sur **dev**, on mesure **test une seule
fois**.

```bash
python -m metadata.data.blind.generate_blind --seed 2026
python -m metadata.run --data metadata/data/blind/test/candidates.json --out out/blind_test
python -m metadata.evaluate --report out/blind_test/report.json --labels metadata/data/blind/test/labels.json
```

| Jeu | Version | Fraudes détectées | Fausses alertes | Précision | Réseaux |
| --- | --- | --- | --- | --- | --- |
| dev | avant (11 règles) | 61 % (27/44) | 5,2 % (6/116) | 0,82 | 2/3 |
| dev | après | 86 % (38/44) | 0 % (0/116) | 1,00 | 3/3 |
| **test** (mesuré une fois) | avant | 61 % (27/44) | 5,2 % (6/116) | 0,82 | 2/3 |
| **test** (mesuré une fois) | **après** | **86 % (38/44)** | **0 % (0/116)** | **1,00** | **3/3** |

Sur test, toutes les fermes d'ordinateurs (8/8), mules de paie (7/7), opérateurs à distance (6/6)
et membres de réseaux (11/11) sont signalés. Les 6 fraudes manquées sont les cas « subtils » à un
seul signal faible (un numéro VoIP, une caméra refusée, un email bizarre) : les signaler ferait
exploser les fausses alertes, c'est voulu. Le jeu historique (`data/synthetic`) passe de 10 % à
3 % de fausses alertes, détection inchangée (90 %).

## Limites connues

- **Jeu « indépendant » mais pas aveugle** : il a été écrit par la même équipe que le détecteur,
  après la conception des règles, et dev et test sortent du même générateur. Les chiffres de test
  sont donc **optimistes**. Il faut encore un jeu écrit par quelqu'un qui n'a jamais vu le code.
- **Réseaux reformulés** : la similarité locale (n-grammes) ne relie pas des CV paraphrasés ; on
  les relie par le parcours (mêmes employeurs, mêmes dates). Un réseau qui change aussi les dates
  passerait : c'est le cas que les embeddings Bedrock doivent couvrir (à mesurer).
- Les poids sont fixés à la main, pas appris.
- Les listes de référence (transitaires, plages VoIP, domaines jetables) sont des échantillons ; en
  production : liste conformité, API de vérification d'opérateur, liste open source tenue à jour.
- Comparaison de toutes les paires en O(n²) : suffisant pour quelques milliers de dossiers.
