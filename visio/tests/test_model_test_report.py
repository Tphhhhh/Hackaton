"""Presentation counts must include failed and abstained samples."""
import pytest

from visio.model_test_report import summarize


def report_fixture():
    config = {"detectors": ["gend_pe"]}
    matrix = {"real": {"verify": 2, "no_signal": 20, "indeterminate": 2, "error": 1},
              "attack": {"verify": 19, "no_signal": 3, "indeterminate": 1, "error": 2}}
    samples = []
    for label, outcomes in matrix.items():
        for outcome, count in outcomes.items():
            for _ in range(count):
                det = dict(status="ok", conclusion=outcome, score=.4, coverage=1, flagged_fraction=.3)
                samples.append(dict(clip_id=str(len(samples)), label=label, result=dict(
                    simulation=False, config=config, duration_seconds=4, timing={"total_seconds": 8},
                    errors=[], detectors={} if outcome == "error" else {"gend_pe": det})))
    return dict(kind="visio_benchmark", split="test", config=config, samples=samples,
                metrics={"gend_pe": {"matrix": matrix}}, config_sha256="c",
                dataset_sha256="d", models_manifest_sha256="m")


def test_failure_and_abstention_are_not_removed_from_denominator():
    summary = summarize(report_fixture())
    assert summary["correct_end_to_end"]["rate"] == 39 / 50
    assert summary["correct_conditional"]["rate"] == 39 / 44
    assert summary["detected_deepfakes"]["rate"] == 19 / 25
    assert summary["false_positives"]["rate"] == 2 / 25
    assert summary["precision"]["rate"] == 19 / 21
    assert summary["abstentions"]["count"] == 3
    assert summary["technical_errors"]["count"] == 3


def test_refuses_simulated_or_inconsistent_results():
    report = report_fixture()
    report["samples"][0]["result"]["simulation"] = True
    with pytest.raises(ValueError, match="Simulated"):
        summarize(report)
    report = report_fixture()
    report["metrics"]["gend_pe"]["matrix"]["real"]["verify"] = 3
    with pytest.raises(ValueError, match="match benchmark"):
        summarize(report)


def test_refuses_unbalanced_corpus():
    report = report_fixture()
    report["samples"][0]["label"] = "attack"
    with pytest.raises(ValueError, match="25 unique"):
        summarize(report)
