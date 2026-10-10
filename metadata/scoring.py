"""Agrège les signaux d'un dossier et son appartenance à un réseau en un score de risque.

Le score sert à prioriser la revue humaine, jamais à décider : un dossier "élevé"
part en vérification, il n'est pas rejeté automatiquement (AI Act, supervision humaine).
"""
from __future__ import annotations

from .checks import Signal

NETWORK_WEIGHT = 30
HIGH, MEDIUM = 50, 25


def score(signals: list[Signal], network: list[str] | None, link_reasons: list[str]) -> dict:
    total = sum(s.weight for s in signals)
    all_signals = [s.to_dict() for s in signals]
    if network:
        total += NETWORK_WEIGHT
        all_signals.append(Signal(
            "S1_PERSONA_NETWORK", NETWORK_WEIGHT,
            f"Fait partie d'un groupe de {len(network)} candidatures liées ({', '.join(network)}) : "
            + "; ".join(sorted(set(link_reasons))) + ".",
            "T1585",
        ).to_dict())
    total = min(total, 100)
    level = "élevé" if total >= HIGH else "moyen" if total >= MEDIUM else "faible"
    return {"score": total, "level": level, "flagged": total >= MEDIUM, "signals": all_signals}
