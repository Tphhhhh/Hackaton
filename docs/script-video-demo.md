# Script vidéo de démo · Sentinelle

10 octobre 2026 · Ludovic · vidéo de 2 à 3 minutes pour le jury Secure Horizons

## Avant d'enregistrer

Compter 10 minutes de préparation. Tout se passe sur ton PC, sans Internet sauf pour `git pull`.

- [ ] Double-cliquer sur `lancer-demo.bat` : il récupère la dernière version, vide les candidatures d'essai et ouvre l'offre (`localhost:8000/apply`) et la console RH (`localhost:8000/recruiter`). Laisser la fenêtre noire ouverte.
- [ ] Déposer la candidature de Camille **hors caméra** : sur l'offre, bouton **Démo** en bas à gauche, « Déposer le CV de Camille Laurent », **Vérifier mes informations**, **Continuer** jusqu'à **Envoyer ma candidature**. Elle apparaît à 0 dans la console.
- [ ] Recharger l'offre pour repartir d'un formulaire vide, et la remonter en haut de page.
- [ ] Une seule fenêtre de navigateur en plein écran (F11), zoom 100 %, deux onglets : l'offre puis la console RH. Fermer le reste et activer « Ne pas déranger » dans Windows.
- [ ] Enregistreur prêt en 1080p : OBS Studio, ou la Xbox Game Bar de Windows (Win + Alt + R). Tester le micro 10 secondes dans une pièce calme.
- [ ] Ouvrir une invite de commandes dans le dossier du projet pour le plan 6. Vérifier qu'aucune clé AWS ni fichier `.env` n'est visible à l'écran ou dans l'historique.
- [ ] Ouvrir le pitch sur la slide de couverture (plan 1) et garder la slide Résultats sous la main (plan 7).
- [ ] Optionnel : un vrai VPN et OBS Virtual Camera lancés avant l'entretien. Sinon le mode démo de la page d'entretien les simule, et la console l'affiche honnêtement avec un badge « Simulation ».

## Le script, plan par plan

Sept plans, 2 min 30 au total. La voix off se lit calmement : environ 2,5 mots par seconde. Les chiffres à l'écran sont ceux obtenus en répétition (65, 80, 100).

| Temps | À l'écran | Voix off |
| --- | --- | --- |
| **1** · 0:00 – 0:15 | Slide de couverture du pitch, puis la slide « Pourquoi ce problème ». | « En 2025, la justice américaine a perquisitionné 29 fermes d'ordinateurs : plus de 100 entreprises avaient embauché à distance de faux informaticiens nord-coréens. Sentinelle repère ces faux candidats avant qu'ils reçoivent l'ordinateur. » |
| **2** · 0:15 – 0:35 | Offre Fjordlane. Bouton **Démo**, « Déposer le CV de Daniel Kovac ». Le formulaire se remplit (28 champs). **Vérifier mes informations**, **Continuer**, **Envoyer ma candidature**. | « Daniel postule à un poste d'ingénieur qui touche aux données de paiement. Il dépose son CV : le formulaire se remplit tout seul. Seuls le CV et les années d'expérience sont obligatoires. » |
| **3** · 0:35 – 0:55 | Onglet console RH. Daniel à 65 avec l'encadré « Réseau détecté », Camille à 0 en dessous. Pointer la souris sur les signaux. | « Côté RH, Daniel est déjà à 65 sur 100. Son CV et son téléphone se retrouvent dans trois autres candidatures : c'est un réseau de faux profils. Son LinkedIn a six semaines pour neuf ans d'expérience, son email est jetable. Camille, une vraie candidate, reste à zéro. » |
| **4** · 0:55 – 1:25 | Onglet de Daniel : **Passer mon entretien vidéo**, cocher l'accord, **Rejoindre l'entretien**. Ouvrir « Mode démo · simuler un fraudeur », cliquer **VPN lointain** puis **Caméra virtuelle**. Basculer sur la console, section « Entretiens en direct » : 80. | « Pendant l'entretien vidéo, Sentinelle mesure la connexion toutes les cinq secondes. Ici, Daniel passe par un serveur à Singapour et une caméra virtuelle, simulés pour la vidéo. En quelques secondes, l'entretien monte à 80 : IP d'hébergeur, 262 millisecondes de délai pour quelqu'un qui dit vivre à Amsterdam, et la caméra OBS. » |
| **5** · 1:25 – 1:55 | Console : sur le dossier de Daniel, **Envoyer le lien d'onboarding**. Page d'onboarding : bouton **Démo**, « Remplir : fraudeur », **Valider mes informations**. Retour console, recharger : Daniel à 100. | « Imaginons que personne n'ait regardé et que Daniel soit embauché. À l'onboarding, il fait livrer son ordinateur chez un transitaire à Hambourg, alors qu'il dit habiter Amsterdam, et verser son salaire à une société tierce. C'est exactement le schéma des fermes d'ordinateurs. Score : 100. » |
| **6** · 1:55 – 2:15 | Ouvrir « Questions à poser au candidat ». Taper un nom, cliquer **Escalader**. Puis l'invite de commandes : `python -m metadata.audit verify` affiche « Journal intact. » | « Sentinelle ne décide jamais. Elle propose des questions de vérification, et c'est le recruteur qui choisit d'escalader à la sécurité. Sa décision entre dans un journal chaîné : toute retouche se verrait. » |
| **7** · 2:15 – 2:30 | Slide « Résultats » du pitch, puis retour à la couverture. | « Sur 160 dossiers jamais utilisés pour le réglage, Sentinelle détecte 86 % des fraudes sans une seule fausse alerte. Aucun critère d'origine, et une personne décide toujours. Sentinelle. » |

**Option deepfake.** Si le module de Théophile est prêt, insérer 10 secondes après le plan 4 pour montrer sa détection, et raccourcir le plan 3 d'autant (couper la phrase sur Camille).

## Plan B

On peut enregistrer plan par plan et recoller au montage : une erreur ne force jamais à tout refaire.

- **Une phrase ratée** : se taire 2 secondes et reprendre la phrase depuis le début ; on coupe au montage.
- **Le CV ne se remplit pas** : recharger l'offre et repasser par le bouton Démo. Le menu Démo permet aussi de télécharger les PDF de Camille et Daniel pour les déposer à la main.
- **La console reste vide** : vérifier que la fenêtre noire de `lancer-demo.bat` est toujours ouverte. La relancer efface les candidatures : redéposer Camille hors caméra.
- **La page d'entretien refuse la caméra** : autoriser la caméra dans la barre d'adresse du navigateur et recharger. Si ça bloque encore, passer au plan 5 et dire l'entretien en voix off sur la capture de la slide Démo.
- **Le score affiché n'est pas celui du script** : lire le chiffre à l'écran, jamais celui du script. Le jury regarde l'écran.

## Après l'enregistrement

- [ ] **Durée** : viser 2 min 30, jamais plus de 3 minutes (règle du hackathon). Couper les temps de chargement et les clics inutiles.
- [ ] **Montage** : Clipchamp, déjà installé sur Windows et gratuit. Un zoom sur le score aux plans 3, 4 et 5 aide le jury à suivre.
- [ ] **Sous-titres** : les générer automatiquement dans Clipchamp, puis les relire. Beaucoup de jurys regardent sans le son.
- [ ] **Relecture sécurité** : uniquement des identités fictives à l'écran, aucune clé AWS, aucun `.env`, aucun onglet personnel.
- [ ] **Export** : MP4 en 1080p, nommé `sentinelle-demo.mp4`, déposé là où l'organisation le demande. Vérifier son heure limite : le code, lui, gèle dimanche à 12:00.
