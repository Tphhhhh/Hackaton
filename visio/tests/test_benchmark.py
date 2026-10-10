import json

import pytest

from visio.benchmark import acceptance, benchmark, dataset, freeze, metrics, rate
from visio.core import DEFAULT_CONFIG, DEFAULT_MANIFEST, VisioError, file_hash


def corpus(tmp_path):
    clips = []
    for i, split in enumerate(("dev", "test")):
        media = tmp_path / f"{i}.mp4"
        media.write_bytes(f"test-only-not-a-video-{i}".encode())
        clips.append(dict(id=str(i), path=media.name, sha256=file_hash(media), split=split,
                          source_id=f"source-{i}", person_id=f"person-{i}", authorized=True,
                          permission="fixture only", label="real", attack_kind=None))
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dict(schema_version="1.0", claimed_categories=["face_swap"], clips=clips)))
    return path


@pytest.mark.parametrize("field", ["person_id", "source_id", "sha256"])
def test_split_leakage_is_rejected(tmp_path, field):
    path = corpus(tmp_path)
    data = json.loads(path.read_text())
    data["clips"][1][field] = data["clips"][0][field]
    path.write_text(json.dumps(data))
    with pytest.raises(VisioError):
        dataset(path)


def test_empty_or_unauthorized_dataset_is_rejected(tmp_path):
    with pytest.raises(VisioError):
        dataset(DEFAULT_MANIFEST.parent / "dataset.example.json")
    path = corpus(tmp_path)
    data = json.loads(path.read_text())
    data["clips"][0]["authorized"] = False
    path.write_text(json.dumps(data))
    with pytest.raises(VisioError):
        dataset(path)


def test_frozen_test_rejects_changed_threshold_before_analysis(tmp_path):
    path = corpus(tmp_path)
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps(freeze(path, DEFAULT_CONFIG, DEFAULT_MANIFEST)))
    with pytest.raises(VisioError, match="gelé"):
        benchmark(path, DEFAULT_CONFIG | {"threshold": .7}, DEFAULT_MANIFEST,
                  tmp_path, "test", lock)


def test_abstention_and_technical_errors_stay_in_recall_denominator():
    rows = [dict(label="attack", attack_kind="face_swap", outcome=outcome, source_id=str(i))
            for i, outcome in enumerate(["verify", "no_signal", "indeterminate", "error"])]
    rows += [dict(label="real", attack_kind=None, outcome="verify", source_id="r")]
    m = metrics(rows, ["face_swap"], ["face_swap", "photo"])
    c = m["categories"]["face_swap"]
    assert c["recall_end_to_end"]["rate"] == .25
    assert c["recall_conditional"]["rate"] == .5
    assert not m["categories"]["photo"]["applicable"]
    assert m["false_positive_rate"]["rate"] == 1
    assert acceptance({"dima": m}, ["face_swap"], "test")["dima"] == "inconclusive"


def test_model_not_credited_for_unrelated_attack():
    rows = [dict(label="attack", attack_kind="digital_replay", outcome="verify", source_id="a")]
    m = metrics(rows, ["photo", "screen"], ["digital_replay"])
    assert m["eligible"] == 0
    assert m["recall_end_to_end"]["rate"] is None
    assert m["not_applicable"] == 1
    assert rate(0, 0)["wilson95"] is None
    assert rate(0, 25)["wilson95"][1] > .1
