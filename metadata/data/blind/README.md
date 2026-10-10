# Jeu d'évaluation `blind`

Deux lots de 160 candidatures **entièrement synthétiques** (noms, emails, numéros, IBAN
inventés), avec la vérité terrain à part dans `labels.json` :

| Lot | Rôle | Dossiers | Fraudes |
| --- | --- | --- | --- |
| `dev/` | réglage des règles et des poids | 160 (`B-D001`…) | 44 (27,5 %) |
| `test/` | mesure finale, **une seule fois**, sans réglage | 160 (`B-T001`…) | 44 (27,5 %) |

```bash
python -m metadata.data.blind.generate_blind --seed 2026   # régénère les deux lots (déterministe)
```

Étiquettes : `{"is_fraud", "network", "archetype", "notes"}`. `network` vaut `NET-1`… pour les
personas d'un même réseau, `null` sinon. `notes` liste les signaux réellement présents.

## Pourquoi ce jeu

Aucune base publique de candidats frauduleux n'existe : les jeux connus (EMSCAD, Kaggle « Real or
Fake Job Posting ») portent sur les fausses **offres** d'emploi, pas sur les faux candidats. Les
vraies affaires sont confidentielles (et contiendraient des données personnelles).

## Fraudes (44 par lot)

Tirées des schémas décrits par les autorités :

| Type | Nb | Ce qu'on voit |
| --- | --- | --- |
| `laptop_farm` | 8 | ordinateur livré chez un réexpéditeur (souvent dans un autre pays), parfois juste après l'embauche |
| `payroll_mule` | 7 | salaire vers un tiers (société écran, particulier), une plateforme ou en crypto |
| `persona_network` | 11 | 3 réseaux (4 + 4 + 3) : même téléphone sous des écritures différentes, même IBAN / wallet / bénéficiaire, CV reformulés au même parcours ; un réseau ne partage **aucun** identifiant |
| `contact_identity` | 7 | numéro VoIP ou mal formé, email généré, URL LinkedIn sans le nom, profil récent |
| `remote_proxy` | 6 | entretien depuis une IP d'hébergeur lointaine, VM, caméra virtuelle, connexions de l'étranger aux heures d'un autre fuseau |
| `subtle` | 5 | **un seul** signal faible : cas difficiles, qu'un détecteur raisonnable doit manquer |

La plupart des fraudes cumulent 2 à 4 signaux. Quelques-unes (1 à 3 par lot) ne sont pas encore
embauchées : leurs signaux d'onboarding (livraison, paie, connexions) n'existent pas encore. Côté
honnêtes, environ 1 sur 5 n'est pas encore embauché.

## Honnêtes (116 par lot), avec des cas piégeux

Expatrié qui garde son numéro d'origine (8), déménagement juste après l'embauche (6), freelance
aux missions qui se chevauchent (6), reconversion (5), anciens d'un même bootcamp au CV quasi
identique (6), voyage de quelques jours (7), couche-tard (6), email pseudonyme (« vinylcat15@… »)
ou à initiales (7), LinkedIn créé récemment malgré une longue carrière (5), caméra coupée pour
cause de réseau (4), VPN d'entreprise pendant l'entretien (5), flou d'arrière-plan NVIDIA
Broadcast / Logi Capture (4), IBAN d'une néobanque d'un autre pays SEPA (5), titulaire écrit avec
une initiale ou un second prénom (5), noms à umlaut et emails translittérés « mueller » (4), noms
composés (6), et 27 profils standards. Environ 8 % des résidents français ont une ligne fixe de box
en 09.

Les noms sont tirés d'un même réservoir mixte (européen, africain, asiatique, arabe, latino-
américain…), **indépendamment** du statut fraude : l'origine supposée d'un nom ne prédit rien.

## Limites

- Écrit par l'équipe qui a écrit le détecteur, après la conception des règles. Il n'a pas servi au
  réglage du lot `test`, mais dev et test sortent du même générateur : les chiffres sont
  **optimistes**. Un jeu écrit par une personne qui n'a jamais lu le code reste à faire.
- Les adresses de réexpéditeurs et les plages VoIP sont des exemples.

## Sources

- FBI IC3, PSA 2025-01-23, « North Korean IT Workers Conducting Data Extortion » :
  https://www.ic3.gov/psa/2025/psa250123
- FBI IC3, PSA 2025-07-23 : https://www.ic3.gov/PSA/2025/PSA250723-4
- ASIS, « Recruitment red flags » (mai 2025) :
  https://www.asisonline.org/security-management-magazine/latest-news/today-in-security/2025/may/recruitment-red-flags/
- Alerte conjointe États-Unis / Corée du Sud / Japon sur les informaticiens nord-coréens (résumé
  Baker McKenzie) :
  https://sanctionsnews.bakermckenzie.com/multiple-governments-issue-joint-alert-on-north-korean-it-workers/
- Plans de numérotation : Ofcom (UK 056, 070, plages de fiction), Bundesnetzagentur (DE 032),
  CNMC (ES 51), ACM (NL 084/085/087).
