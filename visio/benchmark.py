"""Source-disjoint evaluation. Never manufactures a dataset or a success rate."""
from __future__ import annotations

import math
from pathlib import Path
import platform
import statistics

from .core import ATTACKS, VisioError, canonical_hash, fail, file_hash, read_json
from .models import manifest
from .runner import analyze


def dataset(path):
    data = read_json(path)
    try:
        assert data["schema_version"] == "1.0" and isinstance(data["clips"], list) and data["clips"]
        assert isinstance(data["claimed_categories"], list) and data["claimed_categories"]
        assert set(data["claimed_categories"]) <= ATTACKS
        seen_ids, groups = set(), {}
        for clip in data["clips"]:
            assert isinstance(clip["id"], str) and clip["id"] and clip["id"] not in seen_ids
            seen_ids.add(clip["id"])
            assert clip["split"] in ("dev", "test")
            assert clip["label"] in ("real", "attack")
            assert clip["authorized"] is True and isinstance(clip["permission"], str) and clip["permission"].strip()
            if clip["label"] == "attack":
                assert clip["attack_kind"] in ATTACKS
            else:
                assert clip["attack_kind"] is None
            for field in ("source_id", "person_id", "sha256"):
                assert isinstance(clip[field], str) and clip[field]
                key = (field, clip[field])
                assert key not in groups or groups[key] == clip["split"], f"split leakage: {field}"
                groups[key] = clip["split"]
            media = (Path(path).resolve().parent / clip["path"]).resolve()
            assert media.is_file() and 0 < media.stat().st_size <= 50 * 1024**2
            assert file_hash(media) == clip["sha256"]
        # Duplicated content within a split also biases sample counts.
        assert len({c["sha256"] for c in data["clips"]}) == len(data["clips"])
    except (AssertionError, KeyError, TypeError, ValueError, OSError) as exc:
        raise VisioError("InvalidDataset", "Corpus vide, non autorisé, empreinte invalide ou partitions contaminées.",
                         "Remplir dataset.example.json ; garder chaque personne/source et ses variantes dans une partition.") from exc
    return data


def fingerprint(data, config, model_manifest):
    return dict(dataset_sha256=canonical_hash(data), config_sha256=canonical_hash(config),
                models_manifest_sha256=canonical_hash(model_manifest))


def freeze(path, config, models_path):
    data = dataset(path)
    if not all(any(c["split"] == split for c in data["clips"]) for split in ("dev", "test")):
        fail("InvalidDataset", "Partitions dev et test nécessaires.", "Compléter le corpus avant gel.")
    return dict(schema_version="1.0", purpose="frozen_evaluation", **fingerprint(data, config, manifest(models_path)))


def rate(k, n):
    if not n:
        return dict(count=k, total=n, rate=None, wilson95=None)
    p, z = k / n, 1.959963984540054
    den = 1 + z*z / n
    center = (p + z*z / (2*n)) / den
    radius = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return dict(count=k, total=n, rate=p, wilson95=[max(0, center-radius), min(1, center+radius)])


def metrics(rows, threats, claims):
    eligible = [r for r in rows if r["label"] == "real" or r["attack_kind"] in threats]
    real = [r for r in eligible if r["label"] == "real"]
    attacks = [r for r in eligible if r["label"] == "attack"]
    matrix = {label: {outcome: sum(r["label"] == label and r["outcome"] == outcome for r in eligible)
                       for outcome in ("no_signal", "verify", "indeterminate", "error")}
              for label in ("real", "attack")}
    categories = {}
    for category in sorted(set(threats) | set(claims)):
        items = [r for r in attacks if r["attack_kind"] == category]
        decided = [r for r in items if r["outcome"] in ("verify", "no_signal")]
        hits = sum(r["outcome"] == "verify" for r in items)
        categories[category] = dict(applicable=category in threats,
                                    independent_sources=len({r["source_id"] for r in items}),
                                    recall_end_to_end=rate(hits, len(items)),
                                    recall_conditional=rate(hits, len(decided)))
    return dict(eligible=len(eligible), not_applicable=len(rows)-len(eligible), matrix=matrix,
                real_independent_sources=len({r["source_id"] for r in real}),
                false_positive_rate=rate(matrix["real"]["verify"], len(real)),
                recall_end_to_end=rate(matrix["attack"]["verify"], len(attacks)),
                abstention={label: rate(matrix[label]["indeterminate"], sum(matrix[label].values()))
                            for label in matrix},
                technical_failure=rate(sum(r["outcome"] == "error" for r in eligible), len(eligible)),
                categories=categories)


def quantiles(numbers):
    if not numbers:
        return {"p50": None, "p95": None}
    numbers = sorted(numbers)
    return {"p50": statistics.median(numbers), "p95": numbers[max(0, math.ceil(len(numbers)*0.95)-1)]}


def benchmark(path, config, models_path, cache, split="dev", lock_path=None):
    data = dataset(path)
    models = manifest(models_path)
    hashes = fingerprint(data, config, models)
    if split == "test":
        lock = read_json(lock_path) if lock_path else {}
        if lock.get("purpose") != "frozen_evaluation" or any(lock.get(k) != v for k, v in hashes.items()):
            fail("InvalidDataset", "Configuration/test non gelé ou modifié après gel.",
                 "Régler sur dev puis exécuter freeze ; utiliser ce verrou pour test.")
    clips = [c for c in data["clips"] if c["split"] == split]
    if not clips:
        fail("InvalidDataset", "Partition vide.", "Ajouter des clips autorisés.")
    samples, rows = [], {k: [] for k in config["detectors"]}
    for clip in clips:
        media = Path(path).resolve().parent / clip["path"]
        value = analyze(media, config, cache, models_path)
        # Intentionally no path, person ID or raw image in the exported report.
        samples.append(dict(clip_id=clip["id"], label=clip["label"], attack_kind=clip["attack_kind"], result=value))
        for key in rows:
            det = value["detectors"].get(key)
            outcome = "error" if det is None or det["status"] == "error" else det["conclusion"]
            rows[key].append(dict(label=clip["label"], attack_kind=clip["attack_kind"],
                                  source_id=clip["source_id"], outcome=outcome))
        if any(e["code"] in ("CleanupFailed", "AnalysisBusy") for e in value["errors"]):
            fail(value["errors"][0]["code"], "Benchmark interrompu pour préserver l'état local.",
                 "Résoudre le problème avant reprise ; aucun rapport partiel présenté comme complet.")
    summary = {key: metrics(rows[key], models["models"][key]["threats"], data["claimed_categories"]) for key in rows}
    return dict(schema_version="1.0", kind="visio_benchmark", split=split,
                qualification="exploratory_only", calibration="unvalidated_thresholds",
                acceptance=acceptance(summary, data["claimed_categories"], split),
                config=config, **hashes, samples=samples, metrics=summary,
                latency_seconds=quantiles([s["result"]["timing"]["total_seconds"] for s in samples]),
                platform=dict(system=platform.system(), machine=platform.machine(), python=platform.python_version()),
                limitations=["Petit corpus : pas de garantie de production.",
                             "Intervalles Wilson descriptifs ; variantes corrélées ne sont pas des sources indépendantes.",
                             "Chargement des modèles inclus dans le temps total de chaque clip."])


def acceptance(summary, claims, split):
    checks = {}
    for key, m in summary.items():
        applicable = [c for c in claims if m["categories"][c]["applicable"]]
        sufficient = m["real_independent_sources"] >= 25 and bool(applicable) and all(
            m["categories"][c]["independent_sources"] >= 10 for c in applicable)
        passes = (sufficient and m["false_positive_rate"]["rate"] <= 0.04
                  and all(m["categories"][c]["recall_end_to_end"]["rate"] >= 0.8 for c in applicable)
                  and all(x["rate"] is not None and x["rate"] <= 0.2 for x in m["abstention"].values())
                  and m["technical_failure"]["count"] == 0)
        checks[key] = "not_evaluated_on_test" if split != "test" else "inconclusive" if not sufficient else "meets_poc_targets" if passes else "below_poc_targets"
    return checks
