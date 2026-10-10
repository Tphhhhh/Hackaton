# Module metadata : cross-check des candidatures

Partie « métadonnées » du projet (la détection de deepfakes vidéo est un module séparé).

## Problème

Des fraudeurs, dont des réseaux étatiques, se font embaucher à distance sous de fausses
identités, puis volent des données ou détournent des salaires. Un même opérateur peut
porter une douzaine d'identités. Ce module aide un analyste (ESN, portage, plateforme de
freelances) à repérer ces dossiers à partir d'incohérences factuelles et de candidatures
qui se ressemblent trop.

## Architecture

```
candidates.json ─► checks.py      contrôles de cohérence (10 règles explicables)
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
| C5_FORWARDER | Matériel envoyé chez un transitaire connu | 25 | |
| C6_ADDRESS_CHANGE | Adresse de livraison changée < 30 j après l'embauche | 10 | |
| C7_LOGIN_COUNTRIES | Connexions hors du pays déclaré | 20 | T1078 |
| C8_NIGHT_HOURS | Activité la nuit dans le fuseau déclaré | 15 | |
| C9_CRYPTO | Salaire demandé en cryptomonnaie | 20 | |
| C10_DISPOSABLE_EMAIL | Email sur domaine jetable | 10 | |
| S1_PERSONA_NETWORK | Lié à d'autres candidatures (identifiants ou CV) | 30 | T1585 |

Score ≥ 25 : dossier à vérifier ; ≥ 50 : risque élevé. Le score priorise la revue, il ne
décide jamais.

## Installation et utilisation

Python 3.10+, aucune dépendance pour le mode local.

```bash
python -m metadata.data.generate                 # 50 dossiers synthétiques, dont 20 frauduleux
python -m metadata.run                           # rapport dans out/report.md
python -m metadata.evaluate                      # détection, faux positifs, réseaux, temps
python -m metadata.decide C017 --decision verify --analyst "Ludovic" --note "Appel vidéo demandé"
python -m metadata.audit verify                  # intégrité du journal d'audit
```

Bedrock (optionnel) : `pip install -r requirements.txt`, copier `.env.example` en `.env`,
renseigner les clés et mettre `USE_BEDROCK=1`. Les embeddings Titan remplacent alors la
similarité locale et un LLM rédige l'explication. Le `.env` n'est jamais commité.

## Conformité et éthique

- **Données** : uniquement synthétiques (RGPD).
- **Aucun signal d'origine, de nationalité, de langue ou d'accent.** Les pays de connexion
  ne comptent que s'ils contredisent le lieu déclaré par le candidat. Les noms sont tirés
  au hasard indépendamment du statut fraude.
- **AI Act** : outil de filtrage de candidatures, donc à haut risque (annexe III, point 4).
  Supervision humaine (decide.py), explication de chaque score, journal d'audit inviolable,
  information du candidat (article 50) à prévoir dans le parcours de candidature.
- Le LLM ne reçoit que les signaux factuels, pas l'identité du candidat.

## Limites connues

- **Résultats circulaires sur le jeu de développement** : le générateur et les détecteurs
  ont été écrits par la même équipe, d'où des scores parfaits (100 % de détection, 0 faux
  positif, 3/3 réseaux sur plusieurs graines). Ils ne prouvent rien. Le jeu d'évaluation doit
  être produit à l'aveugle par un coéquipier qui ne voit pas ce code.
- Les poids sont fixés à la main, pas appris.
- La similarité locale (n-grammes de caractères) repère les copier-coller, pas les
  reformulations ; les embeddings Bedrock sont prévus pour ça.
- La liste de transitaires est fictive ; en production elle vient de l'équipe conformité.
- Comparaison de toutes les paires en O(n²) : suffisant pour quelques milliers de dossiers.
