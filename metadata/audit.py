"""Journal d'audit chaîné par hash (piste d'audit inviolable, au sens de l'AI Act).

Chaque entrée contient le hash de la précédente : modifier ou supprimer une ligne
casse la chaîne, ce que `python -m metadata.audit verify` détecte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG = Path("out/audit.jsonl")
GENESIS = "0" * 64


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _last_hash(log: Path) -> str:
    if not log.exists():
        return GENESIS
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])["hash"] if lines else GENESIS


def append(event: str, payload: dict, actor: str, log: Path = DEFAULT_LOG) -> dict:
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event,
             "actor": actor, "payload": payload, "prev": _last_hash(log)}
    entry["hash"] = _hash(entry)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify(log: Path = DEFAULT_LOG) -> tuple[bool, str]:
    prev = GENESIS
    for n, line in enumerate(log.read_text(encoding="utf-8").splitlines(), start=1):
        entry = json.loads(line)
        if entry["prev"] != prev or entry["hash"] != _hash(entry):
            return False, f"Chaîne rompue à la ligne {n}."
        prev = entry["hash"]
    return True, "Journal intact."


def main():
    p = argparse.ArgumentParser(description="Vérifie l'intégrité du journal d'audit.")
    p.add_argument("command", choices=["verify"])
    p.add_argument("--log", default=str(DEFAULT_LOG))
    args = p.parse_args()
    ok, msg = verify(Path(args.log))
    print(msg)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
