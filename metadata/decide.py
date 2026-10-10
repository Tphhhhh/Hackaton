"""Enregistre la décision humaine sur un dossier dans le journal d'audit.

    python -m metadata.decide C017 --decision verify --analyst "Ludovic" --note "Appel vidéo demandé"

La décision appartient à l'analyste ; l'outil ne fait que la tracer.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import audit

DECISIONS = ["clear", "verify", "escalate", "reject"]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("candidate_id")
    p.add_argument("--decision", required=True, choices=DECISIONS)
    p.add_argument("--analyst", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--log", default="out/audit.jsonl")
    args = p.parse_args()
    entry = audit.append("human_decision", {"id": args.candidate_id, "decision": args.decision, "note": args.note},
                         actor=args.analyst, log=Path(args.log))
    print(f"Décision « {args.decision} » enregistrée pour {args.candidate_id} (hash {entry['hash'][:12]}…).")


if __name__ == "__main__":
    main()
