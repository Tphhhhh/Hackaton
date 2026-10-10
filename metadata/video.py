"""Point d'entrée des scores du module vidéo (détection de deepfake, Théophile).

Le module vidéo écrit un fichier JSON, un objet par candidat, avec des scores de 0
(naturel) à 1 (très suspect). Toutes les clés sont optionnelles :

{
  "C003": {
    "challenges": 0.85,   # artefacts pendant les défis (main devant le visage, profil) : signal le plus fort
    "lipsync": 0.70,      # faible corrélation son / ouverture de la bouche
    "temporal": 0.40,     # micro-sauts ou stabilité anormale des points du visage
    "lighting": 0.20,     # éclairage du visage incohérent avec la main et le fond
    "classifier": 0.30    # classifieur deepfake générique : signal faible, jamais un verdict
  }
}

Un score sous 0,5 ne produit aucun signal. Au-dessus, le poids est proportionnel au score.
"""
from __future__ import annotations

import json
from pathlib import Path

from .checks import Signal

# (code, poids maximal, phrase de preuve)
VIDEO_SIGNALS = {
    "challenges": ("V1_CHALLENGE_ARTEFACTS", 35, "Artefacts du visage pendant les défis (occlusion par la main, profil)"),
    "lipsync": ("V2_LIPSYNC", 20, "Synchronisation labiale faible ou décalée"),
    "temporal": ("V3_TEMPORAL", 15, "Mouvements des points du visage incohérents d'une image à l'autre"),
    "lighting": ("V4_LIGHTING", 10, "Éclairage du visage incohérent avec la main et le fond"),
    "classifier": ("V5_CLASSIFIER", 5, "Classifieur deepfake générique positif (signal faible)"),
}
THRESHOLD = 0.5


def load_video_scores(path: str | Path | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def video_signals(scores: dict | None) -> list[Signal]:
    out = []
    for key, value in (scores or {}).items():
        if key not in VIDEO_SIGNALS or value < THRESHOLD:
            continue
        code, max_weight, label = VIDEO_SIGNALS[key]
        out.append(Signal(code, round(max_weight * value), f"{label} : score {value:.2f}.", "T1656"))
    return out
