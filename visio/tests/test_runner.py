import sys

import pytest

from visio import runner
from visio.core import DEFAULT_CONFIG, DEFAULT_MANIFEST, VisioError


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "DEFAULT_CACHE", tmp_path)
    return tmp_path


def test_concurrent_admission_rejected(isolated_state):
    with runner.admission():
        with pytest.raises(VisioError) as exc:
            with runner.admission():
                pass
        assert exc.value.code == "AnalysisBusy"


def test_timeout_terminates_and_removes_job(isolated_state):
    value = runner.analyze("missing.mp4", DEFAULT_CONFIG | {"timeout_seconds": .15},
                           isolated_state, DEFAULT_MANIFEST,
                           worker_command=[sys.executable, "-c", "import sys,time;sys.stdin.read();time.sleep(30)"])
    assert value["status"] == "failed"
    assert value["conclusion"] is None
    assert value["errors"][0]["code"] == "AnalysisTimeout"
    assert not list((isolated_state / "state").glob("job-*"))
    with runner.admission():
        pass


def test_stale_worker_result_rejected(isolated_state):
    script = "import json,sys;sys.stdin.read();print(open('visio/examples/indeterminate.json').read())"
    value = runner.analyze("missing.mp4", DEFAULT_CONFIG, isolated_state, DEFAULT_MANIFEST,
                           worker_command=[sys.executable, "-c", script])
    assert value["status"] == "failed"
    assert value["errors"][0]["code"] == "WorkerFailed"


def test_crash_and_invalid_protocol_never_return_no_signal(isolated_state):
    for code in ["import sys;sys.stdin.read();sys.exit(7)", "import sys;sys.stdin.read();print('{}')"]:
        value = runner.analyze("missing.mp4", DEFAULT_CONFIG, isolated_state, DEFAULT_MANIFEST,
                               worker_command=[sys.executable, "-c", code])
        assert value["status"] == "failed"
        assert value["conclusion"] is None


def test_startup_cleanup_failure_blocks_capture(isolated_state, monkeypatch):
    (isolated_state / "state/job-leftover").mkdir(parents=True)
    def denied(*args):
        raise PermissionError("test")
    monkeypatch.setattr(runner.shutil, "rmtree", denied)
    with pytest.raises(VisioError) as exc:
        with runner.admission():
            pytest.fail("must not admit")
    assert exc.value.code == "CleanupFailed"
