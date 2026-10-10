"""Small, dependency-free result contract and deterministic aggregation."""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE = ROOT / ".cache"
DEFAULT_MANIFEST = ROOT / "models.json"
AVAILABLE_DETECTORS = ("dima", "prithiv", "minifasnet", "gend")
DEFAULT_CONFIG = {
    "detectors": ["dima", "prithiv", "minifasnet"],
    "threads": 2,
    "sample_fps": 2.0,
    "threshold": 0.5,
    "aggregation": "fraction",
    "flag_fraction": 0.5,
    "window_seconds": 2.0,
    "min_coverage": 0.8,
    "max_gap_seconds": 2.0,
    "timeout_seconds": 60.0,
}
ATTACKS = {"photo", "screen", "face_swap", "reenactment", "digital_replay"}


class VisioError(Exception):
    def __init__(self, code, message, action, *, retryable=False, cause=None):
        super().__init__(message)
        self.code, self.message, self.action = code, message, action
        self.retryable = retryable
        self.cause = cause

    def as_dict(self):
        return dict(code=self.code, message=self.message, action=self.action,
                    retryable=self.retryable, cause=self.cause, docs="visio/README.md#erreurs")


def fail(code, message, action):
    raise VisioError(code, message, action)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    try:
        path = Path(path)
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("JSON too large")
        return json.loads(path.read_text(), parse_constant=lambda x: fail(
            "InvalidConfiguration", "JSON non fini.", "Retirer NaN/Infinity."))
    except (OSError, ValueError) as exc:
        raise VisioError("InvalidConfiguration", "JSON absent ou invalide.",
                         "Vérifier le chemin et la syntaxe JSON.") from exc


def configuration(path=None, detectors=None):
    values = read_json(path) if path else {}
    if not isinstance(values, dict) or set(values) - set(DEFAULT_CONFIG):
        fail("InvalidConfiguration", "Options inconnues.", "Consulter config.example.json.")
    config = DEFAULT_CONFIG | values
    if detectors is not None:
        config["detectors"] = detectors
    ds = config["detectors"]
    if (not isinstance(ds, list) or not ds or any(x not in AVAILABLE_DETECTORS for x in ds)
            or len(ds) != len(set(ds))):
        fail("InvalidConfiguration", "Détecteurs invalides.", "Choisir dima, prithiv, minifasnet, gend sans doublon.")
    ranges = {"threads": (1, 4), "sample_fps": (0.5, 2), "threshold": (0.01, 0.99),
              "flag_fraction": (0.01, 1), "window_seconds": (1, 5), "min_coverage": (0.8, 1),
              "max_gap_seconds": (0.5, 2), "timeout_seconds": (1, 60)}
    for key, (low, high) in ranges.items():
        value = config[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            fail("InvalidConfiguration", f"Valeur invalide : {key}.", f"Utiliser [{low}, {high}].")
    if type(config["threads"]) is not int or config["aggregation"] not in ("fraction", "window"):
        fail("InvalidConfiguration", "Threads ou agrégation invalides.", "Threads entier ; fraction ou window.")
    return config


def result(config, *, session_id=None, generation=1):
    return {
        "schema_version": "1.0", "session_id": session_id or str(uuid.uuid4()),
        "generation": generation, "simulation": False, "status": "completed",
        "conclusion": "indeterminate", "freshness": "unverified",
        "coverage": None, "sampled_frames": 0, "duration_seconds": None,
        "detectors": {}, "errors": [], "timing": {}, "provenance": {},
        "config": config, "config_sha256": canonical_hash(config),
        "limitations": ["Scores exploratoires non calibrés ; aucune décision d'embauche.",
                        "Ne prouve ni identité ni présence en direct.",
                        "Les intervalles non échantillonnés ne sont pas analysés."],
    }


def error_result(config, error, status="failed", **kwargs):
    value = result(config, **kwargs)
    value.update(status=status, conclusion=None, errors=[error.as_dict()])
    return value


def aggregate(observations, duration, config, *, error=None):
    """No inference between samples; coverage and longest gap gate every decision."""
    scores = [x["score"] for x in observations if x["score"] is not None]
    if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in scores):
        fail("InvalidPrediction", "Score non fini ou hors intervalle.", "Vérifier l'adaptateur et les poids.")
    good_times = [x["time_seconds"] for x in observations if x["score"] is not None]
    coverage = len(scores) / len(observations) if observations else None
    boundaries = [0.0, *good_times, duration]
    gap = max((b - a for a, b in zip(boundaries, boundaries[1:])), default=duration)
    usable = bool(scores) and coverage >= config["min_coverage"] and gap <= config["max_gap_seconds"]
    fraction = sum(s >= config["threshold"] for s in scores) / len(scores) if scores else None
    flagged = bool(scores) and fraction >= config["flag_fraction"]
    if config["aggregation"] == "window":
        flagged = False
        # Require a complete time window. Missing observations break persistence.
        start = None
        for item in observations:
            if item["score"] is None or item["score"] < config["threshold"]:
                start = None
            else:
                start = item["time_seconds"] if start is None else start
                flagged |= item["time_seconds"] - start >= config["window_seconds"]
    return dict(status="error" if error else "ok" if usable else "insufficient",
                conclusion="indeterminate" if error or not usable else "verify" if flagged else "no_signal",
                coverage=coverage, longest_gap_seconds=gap,
                score=sum(scores) / len(scores) if scores else None,
                flagged_fraction=fraction, observations=observations,
                error=error.as_dict() if error else None)


def conclude(value):
    detectors = list(value["detectors"].values())
    technical = any(x["status"] == "error" for x in detectors)
    value["status"] = "partial" if technical else "completed"
    if any(x["conclusion"] == "verify" for x in detectors):
        value["conclusion"] = "verify"
    elif detectors and all(x["conclusion"] == "no_signal" for x in detectors):
        value["conclusion"] = "no_signal"
    else:
        value["conclusion"] = "indeterminate"
    return value


def exit_code(value):
    if value["status"] == "cancelled":
        return 130
    if value["status"] in ("failed", "partial"):
        return 2 if any(x["code"] in ("InvalidMedia", "InvalidConfiguration", "InvalidDataset")
                        for x in value["errors"]) else 3
    return 0
