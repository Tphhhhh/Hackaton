# design.md — Landing page « visio »

> Brief de design pour l'agent qui code la page. Inspiration directe : **vessa.design** (palette froide gris papier / encre quasi noire, un seul accent bleu électrique, petits pixels décoratifs, grotesque sobre, beaucoup d'air). On reprend **l'esthétique**, pas les features : ici c'est **une seule page** qui présente **deux visios côte à côte** — le flux réel et le flux transformé — et l'analyse qui les départage.

---

## 1. Principes

1. **Épuré avant tout.** Fond papier, texte encre, un accent. Pas de dégradé, pas d'ombre portée lourde, pas d'illustration 3D.
2. **Le produit est le visuel.** Le hero, c'est les deux visios. Aucune image décorative qui ne montre pas le produit.
3. **Pixels = signature.** Des petits carrés (4–8 px) servent de ponctuation : coins de cartes, puces, transitions, indicateurs « en direct ». Jamais en fond plein écran chargé.
4. **Copy courte, ton direct, phrases déclaratives.** Comme Vessa : une idée par titre, un paragraphe narratif qui pose le problème, puis la preuve.
5. **Une seule page, une seule action** (CTA principal répété 3 fois : hero, milieu, fin).

---

## 2. Design tokens

### Couleurs

```css
:root {
  /* Base — reprise de Vessa */
  --paper:      #EEF0F3;  /* fond de page (theme-color de vessa.design) */
  --surface:    #F7F8FA;  /* cartes, panneaux */
  --surface-2:  #E4E7EC;  /* états hover, pistes de barres, segmented control */
  --ink:        #101216;  /* texte principal, boutons primaires */
  --ink-2:      #555B66;  /* texte secondaire */
  --ink-3:      #8A909B;  /* légendes, méta */
  --line:       #D8DCE2;  /* bordures 1px */

  /* Accent unique — utilisé avec parcimonie (< 5 % de la surface) */
  --accent:     #1F2DE6;  /* liens, pixels actifs, focus, valeur sélectionnée */
  --accent-ink: #FFFFFF;

  /* Signaux produit (repris de l'app visio) */
  --navy:       #1B3A6B;  /* bouton actif du toggle Original/Transformé */
  --live:       #2F8A5B;  /* point « EN DIRECT », barres validées */
  --warn:       #C2410C;  /* score inquiétant, flux transformé détecté */

  --video-bg:   #1A1C20;  /* fond des cadres vidéo avant chargement */
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper:#0E0F12; --surface:#16181D; --surface-2:#1F2229;
    --ink:#ECEEF2; --ink-2:#A6ACB6; --ink-3:#6E7480; --line:#2A2E36;
    --accent:#5B66FF;
  }
}
:root[data-theme="dark"] { /* mêmes valeurs que ci-dessus */ }
body { background: var(--paper); color: var(--ink); }
```

Règle : **jamais deux couleurs vives côte à côte**. Le vert et l'orange n'apparaissent que dans les composants de score.

### Typographie

- **Titres + texte : Switzer** (grotesque neutre, gratuite sur Fontshare — c'est la police mise en avant dans la démo Vessa). Fallback : `Inter, system-ui, sans-serif`.
- **Labels, méta, chiffres : une mono** — `Geist Mono` ou `JetBrains Mono` (police à chasse fixe, chaque caractère a la même largeur → rendu « technique », aligne les chiffres).
- Vérifier la police exacte de vessa.design via l'inspecteur du navigateur si on veut un clone strict.

| Rôle | Police | Taille (desktop / mobile) | Poids | Interlignage | Tracking |
|---|---|---|---|---|---|
| Display (H1) | Switzer | 64 / 40 px | 500 | 1.02 | -0.03em |
| H2 | Switzer | 40 / 28 px | 500 | 1.1 | -0.02em |
| H3 | Switzer | 20 / 18 px | 600 | 1.3 | -0.01em |
| Body L (manifeste) | Switzer | 22 / 18 px | 400 | 1.45 | 0 |
| Body | Switzer | 16 px | 400 | 1.55 | 0 |
| Label / eyebrow | Mono | 12 px | 500 | 1 | 0.06em, MAJUSCULES |
| Méta / chiffres | Mono | 13 px | 400 | 1.4 | 0 |

Utiliser `font-variant-numeric: tabular-nums` (chiffres de même largeur) sur tous les scores.

### Espacement, rayons, bordures

- Grille de base **4 px**. Échelle : 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
- Espacement vertical entre sections : **128 px desktop / 80 px mobile**.
- Conteneur : `max-width: 1200px`, gouttière latérale **16 px mobile / 32 px desktop**.
- Rayons : **12 px** cartes, **10 px** boutons, **6 px** badges, **2 px** pixels (quasi carrés).
- Bordures : `1px solid var(--line)`. Pas d'ombre, sauf `0 1px 0 rgba(16,18,22,.04)` sur les cartes surélevées.

---

## 3. Le motif pixel (signature visuelle)

Petits carrés pleins, alignés sur la grille de 4 px. Implémentation en `<span>` ou SVG, jamais en image.

| Usage | Spécification |
|---|---|
| **Indicateur live** | 1 carré 6×6 `--live`, clignote (opacité 1 → 0.3, 1.2 s, `steps(2)`) |
| **Eyebrow de section** | 3 carrés 4×4 en ligne (`--ink`, `--ink-3`, `--accent`) avant le label mono |
| **Coins de cadres vidéo** | « crochets » en pixels : 3 carrés 4×4 en L à chaque coin, `--accent` sur le flux analysé |
| **Barres de score** | segments de 4×4 px au lieu de barres pleines (style jauge pixel) |
| **Séparateur de section** | ligne de carrés 2×2 espacés de 8 px, `--line` |
| **Transition hero → section suivante** | bande de « dither » (tramage : motif en damier qui se raréfie) de 32 px de haut, de `--surface` vers `--paper` |
| **Curseur / hover CTA** | au survol du bouton primaire, 4 pixels `--accent` apparaissent en escalier à droite (stagger 40 ms) |

Densité max : **un motif pixel visible par écran**. Si on en voit trois, on en enlève deux.

---

## 4. Composants

### Bouton primaire
Fond `--ink`, texte `--paper`, 16 px / 500, padding 14×22, rayon 10. Hover : fond `#000` + pixels accent (cf. §3). Focus : outline 2 px `--accent`, offset 2.
Astuce Vessa : le libellé est doublé dans le DOM pour un effet de **roll** vertical au survol (le texte glisse vers le haut, la copie arrive du bas, 220 ms).

### Bouton secondaire
Fond transparent, bordure 1 px `--line`, texte `--ink`. Hover : fond `--surface-2`.

### Lien
Texte `--ink`, soulignement 1 px `--line` → `--accent` au survol.

### Badge (sur vidéo)
Fond `rgba(247,248,250,.92)`, texte mono 12 px majuscules, rayon 6, padding 6×10. Variantes : `● EN DIRECT` (pixel vert), `VISAGE TRANSFORMÉ`, `SUIVI EN DIRECT`.

### Cadre visio (composant clé)
```
┌ 01 · VOUS, EN DIRECT ─────────── Webcam · en direct ┐   ← header mono 12px, --ink-2 / --ink-3
│ ┌───────────────────────────────────────────────┐  │
│ │ [● EN DIRECT]                  [SUIVI EN DIRECT]│  │   ← badges
│ │                                                 │  │
│ │              vidéo 16:10, rayon 12              │  │
│ │                                                 │  │
│ └───────────────────────────────────────────────┘  │
│ Webcam en direct · aucun enregistrement            │   ← méta 13px --ink-2
└────────────────────────────────────────────────────┘
```
- Carte `--surface`, bordure `--line`, padding 12, rayon 12.
- Le cadre **actuellement analysé** a les coins pixel `--accent` et une bordure `--accent` à 40 % d'opacité.
- Sur la landing, les vidéos sont des **boucles MP4 muettes pré-enregistrées** (autoplay, muted, loop, playsinline, poster JPG), pas une vraie webcam.

### Toggle segmenté (Original / Transformé)
Piste `--surface-2`, rayon 10, padding 4. Segment actif : fond `--navy`, texte blanc, transition de glissement 240 ms.

### Jauge de confiance
Grand chiffre Switzer 56 px tabular + `/ 100` en `--ink-3`. Dessous : jauge pixel (25 segments 8×8, gap 4). Légendes mono aux extrémités : `0 · Inquiétant` / `100 · Rassurant`. Couleur des segments remplis : `--warn` si < 40, `--ink` entre 40 et 70, `--live` si > 70.

### Carte de signal (bento)
Carte `--surface`, padding 24, rayon 12. Haut : label mono + score `n / 5` aligné à droite. Milieu : 5 barres segmentées. Bas : phrase d'état en `--ink-2`.

---

## 5. Structure de la page (section par section)

Navigation par ancres, une seule page. Ordre calqué sur le rythme Vessa : promesse → preuve visuelle → manifeste → fonctionnement → détails → CTA → FAQ → CTA final.

### 0. Nav (sticky, 64 px)
- Gauche : wordmark **visio** (Switzer 500, 24 px, tracking -0.03em) + 1 pixel `--accent` 6×6 collé en exposant après le « o ».
- Centre : `Comparaison` · `Analyse` · `Signaux` · `FAQ` (16 px, `--ink-2`, hover `--ink`).
- Droite : lien `Connexion` + bouton primaire compact `Essayer en direct`.
- Au scroll : fond `--paper` à 85 % + `backdrop-filter: blur(12px)` + bordure basse `--line`.

### 1. Hero
- Eyebrow pixel + `ANALYSE VIDÉO EN DIRECT`
- **H1** : « Deux visios. Une seule est vraie. »
- Sous-titre (Body L, max 560 px) : « visio compare votre flux réel et sa version transformée, image par image, et vous dit lequel croire. En direct, sans rien enregistrer. »
- CTA primaire `Essayer en direct` + secondaire `Voir la démo · 1:30`
- Preuve sociale mono sous le CTA : `● 1 200+ sessions analysées` (chiffre à remplacer par le vrai)
- **Visuel : les deux cadres visio côte à côte** (grille 2 colonnes, gap 24), légèrement débordants sous le pli. Le cadre 01 = flux réel, le cadre 02 = flux transformé. Entre les deux, sur desktop, un petit sélecteur flottant `Original | Transformé` qui bascule le cadre mis en avant (coins pixel accent).
- Mobile : les deux cadres s'empilent, toggle au-dessus.

### 2. Bande de détails (équivalent des onglets Vessa « Intro / Logo / Color… »)
- Rangée de 5 onglets mono : `Suivi du visage` · `Transformation` · `Confiance` · `Analyse vidéo` · `Métadonnées`.
- Chaque onglet change une capture plein-largeur (rayon 12, bordure `--line`) avec fondu 200 ms. Onglet actif : texte `--ink` + pixel accent avant.

### 3. Manifeste (narratif, pas de titre)
Body L, colonne de 680 px centrée, 3–4 paragraphes courts, ton Vessa. Exemple :
> Une visio, c'est devenu la preuve qu'on parle à quelqu'un de réel. On voit un visage, on entend une voix, on fait confiance.
> Sauf qu'un visage se remplace maintenant en temps réel, sur une carte graphique grand public, sans que l'image ne saute.
> Les outils de détection rendent un verdict après coup, dans un rapport que personne ne lit pendant l'appel.
> visio regarde pendant.

Dernière phrase en `--ink`, les précédentes en `--ink-2`.

### 4. Comment ça marche (`#analyse`)
- H2 : « Trois couches, un seul score. »
- 3 étapes en colonnes, numérotées en mono `01 / 02 / 03` + pixel :
  1. **Capturer** — « Le flux arrive tel quel. On suit 32 points du visage en direct. »
  2. **Comparer** — « Le flux original et le flux transformé passent dans le même modèle. »
  3. **Trancher** — « Un score de 0 à 100, et les signaux qui l'expliquent. »
- Sous les étapes : maquette animée de la colonne « Analyse de session » (jauge qui se remplit, barres qui s'allument une par une, 80 ms de décalage).

### 5. Signaux (`#signaux`) — grille bento
- H2 : « Chaque verdict montre son raisonnement. »
- Grille 3 colonnes (2 lignes), cartes de tailles variées :
  - **Confiance** (grande, 2 colonnes) — jauge pixel animée.
  - **Analyse vidéo** — 5 barres, « Cohérence des contours, clignements, éclairage ».
  - **Métadonnées** — `5 / 5`, « 4 contrôles · aucune pénalité ».
  - **Suivi du visage** — mini-capture avec la grille de points.
  - **Aucun enregistrement** — icône cadenas pixel, « Le flux est analysé puis oublié. »
  - **Partage de flux externe** — « Analysez une visio Zoom, Meet ou Teams en partageant l'onglet. » (à valider selon la feature réelle)

### 6. Comparaison (`#comparaison`) — équivalent « Two live brands »
- H2 : « Même personne. Même lumière. Pas le même score. »
- Deux grandes cartes vidéo côte à côte (boucles 8 s), chacune avec en légende mono son score final : `Original · 92 / 100` (pixel vert) et `Transformé · 18 / 100` (pixel orange).
- Hover : la vidéo passe en lecture ralentie 0.5×.

### 7. CTA intermédiaire
Bloc centré, fond `--surface`, bordure `--line`, rayon 12, padding 64.
- H2 : « Testez-le sur votre propre visage. »
- Sous-texte : « Webcam en direct, rien n'est enregistré, deux minutes. »
- Bouton primaire.

### 8. FAQ (`#faq`)
- H2 : « Ce qu'on nous demande avant d'essayer. »
- Accordéon : chaque question en Switzer 18 px 500, séparateur 1 px `--line`, icône `+` en pixels (2 barres de carrés 2×2) qui pivote en `×`. Réponse Body `--ink-2`, max 680 px.
- 5–6 questions : enregistrement des données, fiabilité du score, appareils compatibles, usage en entreprise, différence avec les détecteurs existants, prix.

### 9. CTA final
- H2 (taille display) : « Faites confiance à ce que vous voyez. »
- Bouton primaire.
- Ligne mono `--ink-3` en dessous.

### 10. Footer
- Fond `--paper`, bordure haute `--line`, padding 64/32.
- Gauche : wordmark + baseline en `--ink-2` : « L'analyse vidéo qui regarde pendant l'appel. »
- Colonnes de liens mono 13 px : Produit · Ressources · Légal.
- Bas : `© 2026 visio` + séparateur de pixels.

---

## 6. Motion

- Courbe par défaut : `cubic-bezier(.2,.7,.1,1)` (démarre vite, freine en douceur). Durées : 160 ms (hover), 240 ms (toggle, onglets), 480 ms (apparition de section).
- **Apparition au scroll** : `opacity 0 → 1` + `translateY(12px → 0)`, une seule fois, déclenchée à 20 % de visibilité. Enfants décalés de 60 ms.
- **Pixels** : animations en `steps()` (saccadées volontairement, effet rétro), jamais en easing fluide.
- **Jauge** : les segments s'allument un par un (20 ms chacun), le chiffre compte de 0 à la valeur finale.
- Respecter `prefers-reduced-motion: reduce` → tout passe en fondu simple, pas de clignotement.

---

## 7. Responsive

- Breakpoints : 640, 960, 1200 px.
- < 960 px : les deux visios s'empilent ; bento passe en 1 colonne ; nav centrale cachée derrière un bouton menu (icône 3 barres de pixels).
- Aucune barre de défilement horizontale. Cibles tactiles ≥ 44 px.

---

## 8. Accessibilité

- Contraste AA minimum : `--ink-2` sur `--paper` OK, `--ink-3` réservé aux textes ≥ 13 px non essentiels.
- Vidéos : `aria-label` descriptif, bouton pause visible sur chaque boucle.
- Scores : jamais transmis par la couleur seule (toujours chiffre + libellé « Inquiétant / Rassurant »).
- Focus visible partout (outline accent).

---

## 9. Contenu & assets à fournir

- 2 boucles vidéo (MP4 H.264 + WebM, 8 s, ≤ 2 Mo chacune, 1280×800) + posters JPG.
- Captures de l'interface pour la bande d'onglets (section 2).
- Visage transformé : utiliser un **visage généré ou d'une personne qui a donné son accord** — pas une célébrité (droit à l'image).
- Chiffres réels de preuve sociale.

---

## 10. À ne pas faire

- Pas de dégradé violet, pas de glassmorphism (effet verre dépoli) hors nav, pas d'emoji.
- Pas plus d'un accent coloré par écran.
- Pas de stock photos, pas d'illustrations de « hacker à capuche ».
- Pas de textes en majuscules hors labels mono.
- Pas d'ombres portées marquées : la profondeur vient des bordures et du contraste papier/surface.
