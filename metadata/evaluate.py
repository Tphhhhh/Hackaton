"""Métriques pour la fiche de défense : détection, faux positifs, réseaux retrouvés, temps.

    python -m metadata.evaluate --report out/report.json --labels metadata/data/synthetic/labels.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(report: dict, labels: dict) -> dict:
    res = {r["id"]: r for r in report["results"]}
    tp = sum(1 for cid, l in labels.items() if l["is_fraud"] and res[cid]["flagged"])
    fn = sum(1 for cid, l in labels.items() if l["is_fraud"] and not res[cid]["flagged"])
    fp = sum(1 for cid, l in labels.items() if not l["is_fraud"] and res[cid]["flagged"])
    tn = sum(1 for cid, l in labels.items() if not l["is_fraud"] and not res[cid]["flagged"])

    true_nets: dict[str, set] = {}
    for cid, l in labels.items():
        if l["network"]:
            true_nets.setdefault(l["network"], set()).add(cid)
    found = [set(n) for n in report["networks"]]
    # Un réseau est "retrouvé" si un groupe détecté en contient au moins deux membres et aucun intrus.
    recovered = sum(1 for t in true_nets.values() if any(len(f & t) >= 2 and f <= t for f in found))
    spurious = sum(1 for f in found if not any(f <= t for t in true_nets.values()))

    times = sorted(r["detect_ms"] for r in report["results"])
    return {
        "frauds": tp + fn, "legit": fp + tn,
        "detection_rate": round(tp / (tp + fn), 3) if tp + fn else None,
        "false_positive_rate": round(fp / (fp + tn), 3) if fp + tn else None,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "true_positives": tp, "false_negatives": fn, "false_positives": fp,
        "networks_recovered": f"{recovered}/{len(true_nets)}", "spurious_networks": spurious,
        "median_detect_ms": times[len(times) // 2], "total_seconds": report["total_seconds"],
        "missed": sorted(cid for cid, l in labels.items() if l["is_fraud"] and not res[cid]["flagged"]),
        "false_alarms": sorted(cid for cid, l in labels.items() if not l["is_fraud"] and res[cid]["flagged"]),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--report", default="out/report.json")
    p.add_argument("--labels", default="metadata/data/synthetic/labels.json")
    args = p.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    metrics = evaluate(report, labels)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
