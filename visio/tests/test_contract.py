import json
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

from visio.core import DEFAULT_CONFIG, ROOT, VisioError, aggregate, conclude, configuration, result


def observations(scores):
    return [dict(time_seconds=i*.5, score=s, reason=None) for i, s in enumerate(scores)]


def test_all_examples_and_state_invariants():
    validator = Draft202012Validator(json.loads((ROOT / "schema.json").read_text()))
    for path in (ROOT / "examples").glob("*.json"):
        value = json.loads(path.read_text())
        validator.validate(value)
        assert value["simulation"] is True
        if value["status"] in ("failed", "cancelled"):
            value["conclusion"] = "no_signal"
            assert not validator.is_valid(value)
    partial = json.loads((ROOT / "examples/partial.json").read_text())
    partial["conclusion"] = "no_signal"
    assert not validator.is_valid(partial)


def test_example_without_site_packages():
    p = subprocess.run([sys.executable, "-S", "-m", "visio", "example", "failed"],
                       capture_output=True, text=True, check=True)
    assert json.loads(p.stdout)["simulation"]


def test_no_scores_and_missing_frames_abstain():
    assert aggregate([], 4, DEFAULT_CONFIG)["score"] is None
    assert aggregate(observations([None]*8), 4, DEFAULT_CONFIG)["conclusion"] == "indeterminate"
    # High average coverage may still conceal a contiguous unobserved interval.
    scores = [.1]*40
    scores[15:22] = [None]*7
    got = aggregate(observations(scores), 20, DEFAULT_CONFIG)
    assert got["coverage"] >= .8
    assert got["conclusion"] == "indeterminate"


def test_fraction_does_not_turn_one_spike_into_a_verdict():
    assert aggregate(observations([.99]+[.1]*7), 4, DEFAULT_CONFIG)["conclusion"] == "no_signal"
    assert aggregate(observations([.9]*8), 4, DEFAULT_CONFIG)["conclusion"] == "verify"


def test_window_requires_persistence_and_missing_frame_breaks_it():
    cfg = DEFAULT_CONFIG | {"aggregation": "window"}
    assert aggregate(observations([.9]*8), 4, cfg)["conclusion"] == "verify"
    assert aggregate(observations([.9,.9,.9,None,.9,.9,.9,.9]), 4, cfg)["conclusion"] == "no_signal"


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 2])
def test_invalid_predictions_never_become_zero(score):
    with pytest.raises(VisioError, match="Score"):
        aggregate(observations([score]), 4, DEFAULT_CONFIG)


def test_detector_failure_and_disagreement():
    good = aggregate(observations([.1]*8), 4, DEFAULT_CONFIG)
    error = aggregate(observations([None]*8), 4, DEFAULT_CONFIG,
                      error=VisioError("ModelUnavailable", "missing", "fetch"))
    value = result(DEFAULT_CONFIG)
    value["detectors"] = {"a": good, "b": error}
    assert conclude(value)["status"] == "partial"
    assert value["conclusion"] == "indeterminate"
    value["detectors"]["a"] = aggregate(observations([.9]*8), 4, DEFAULT_CONFIG)
    assert conclude(value)["conclusion"] == "verify"


@pytest.mark.parametrize("override", [{"threads": True}, {"threshold": float("nan")},
                                      {"sample_fps": 999}, {"min_coverage": .1},
                                      {"detectors": ["dima", "dima"]}, {"unknown": 1}])
def test_invalid_configuration(tmp_path, override):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(override))
    with pytest.raises(VisioError):
        configuration(path)
