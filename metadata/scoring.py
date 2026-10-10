"""Agrège les signaux d'un dossier et son appartenance à un réseau en un score de risque.

Le score sert à prioriser la revue humaine, jamais à décider : un dossier "élevé"
part en vérification, il n'est pas rejeté automatiquement (AI Act, supervision humaine).
"""
from __future__ import annotations

from .checks import Signal
from .similarity import is_strong

NETWORK_WEIGHT = 30          # identifiant partagé ou parcours identique
TEXT_ONLY_WEIGHT = 15        # seulement un CV très proche (modèle de bootcamp, CV rédigé par IA…)
HIGH, MEDIUM = 50, 25


def score(signals: list[Signal], network: list[str] | None, link_reasons: list[str], self_id: str = "") -> dict:
    total = sum(s.weight for s in signals)
    all_signals = [s.to_dict() for s in signals]
    if network:
        others = [i for i in network if i != self_id] or network
        weight = NETWORK_WEIGHT if any(is_strong(r) for r in link_reasons) else TEXT_ONLY_WEIGHT
        total += weight
        all_signals.append(Signal(
            "S1_PERSONA_NETWORK", weight,
            f"Lié à {len(others)} autre{'s' if len(others) > 1 else ''} dossier{'s' if len(others) > 1 else ''} "
            f"({', '.join(others)}) : " + ", ".join(sorted(set(link_reasons))) + ".",
            "T1585",
        ).to_dict())
    total = min(total, 100)
    level = "élevé" if total >= HIGH else "moyen" if total >= MEDIUM else "faible"
    return {"score": total, "level": level, "flagged": total >= MEDIUM, "signals": all_signals}
