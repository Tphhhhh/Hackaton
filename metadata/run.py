"""Pipeline complet : contrôles de cohérence, réseaux de personas, score, explication.

    python -m metadata.run --data metadata/data/synthetic/candidates.json --out out

Écrit out/report.json (lu par evaluate.py) et out/report.md (lisible par l'analyste),
et journalise chaque score dans out/audit.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from . import audit
from .checks import run_checks
from .explain import explain
from .schema import load_candidates
from .scoring import score
from .similarity import find_links, find_networks


def load_dotenv(path: str = ".env") -> None:
    """Charge un .env local sans dépendance (les clés ne sont jamais commitées)."""
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def analyse(candidates: list[dict]) -> dict:
    t0 = time.perf_counter()
    links = find_links(candidates)
    networks = find_networks(candidates, links)
    t_links = time.perf_counter() - t0
    net_of = {cid: net for net in networks for cid in net}

    results = []
    for c in candidates:
        t = time.perf_counter()
        reasons = [r for l in links if c["id"] in (l["a"], l["b"]) for r in l["reasons"]]
        res = score(run_checks(c), net_of.get(c["id"]), reasons)
        res["explanation"] = explain(res)
        res["id"] = c["id"]
        res["detect_ms"] = round((time.perf_counter() - t) * 1000 + t_links * 1000 / len(candidates), 2)
        results.append(res)
    results.sort(key=lambda r: -r["score"])
    return {"results": results, "networks": networks, "links": links,
            "total_seconds": round(time.perf_counter() - t0, 3)}


def to_markdown(report: dict) -> str:
    lines = ["# Rapport de vérification des candidatures", "",
             f"{len(report['results'])} dossiers analysés en {report['total_seconds']} s. "
             f"{sum(r['flagged'] for r in report['results'])} à vérifier, {len(report['networks'])} réseau(x) "
             "de personas présumé(s).", "",
             "> Aide à la décision : chaque dossier signalé doit être revu par un humain.", ""]
    if report["networks"]:
        lines += ["## Réseaux de personas", ""] + [f"- {', '.join(n)}" for n in report["networks"]] + [""]
    lines += ["## Dossiers par risque", "", "| Dossier | Score | Niveau | Signaux |", "| --- | --- | --- | --- |"]
    for r in report["results"]:
        lines.append(f"| {r['id']} | {r['score']} | {r['level']} | {', '.join(s['code'] for s in r['signals']) or '-'} |")
    lines.append("")
    for r in report["results"]:
        if not r["flagged"]:
            continue
        lines += [f"### {r['id']} ({r['score']}/100)", "", r["explanation"]["summary"], "",
                  "Questions de vérification :"] + [f"- {q}" for q in r["explanation"]["questions"]] + [""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default="metadata/data/synthetic/candidates.json")
    p.add_argument("--out", default="out")
    args = p.parse_args()
    load_dotenv()

    report = analyse(load_candidates(args.data))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "report.md").write_text(to_markdown(report), encoding="utf-8")
    log = out / "audit.jsonl"
    for r in report["results"]:
        audit.append("scored", {"id": r["id"], "score": r["score"], "level": r["level"],
                                "signals": [s["code"] for s in r["signals"]]}, actor="system", log=log)
    flagged = sum(r["flagged"] for r in report["results"])
    print(f"{len(report['results'])} dossiers, {flagged} à vérifier, {len(report['networks'])} réseau(x). "
          f"Rapport : {out / 'report.md'}")


if __name__ == "__main__":
    main()
