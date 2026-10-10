"""GenD label, preprocessing, architecture, and abstention regression checks."""
import hashlib
import numpy as np
import pytest
import torch
from transformers import CLIPVisionConfig

from visio.core import DEFAULT_CONFIG, DEFAULT_MANIFEST, VisioError, configuration
from visio.gend import GenDDetector, GenDNetwork, aligned_face
from visio.gend_pe import GenDPEDetector
from visio.models import manifest
from visio.vendor.gend_alignment import align_face


@pytest.mark.parametrize("key,adapter", [("gend", GenDDetector), ("gend_pe", GenDPEDetector)])
def test_gend_is_opt_in_and_rejects_cpu_fallback(tmp_path, monkeypatch, key, adapter):
    assert configuration(detectors=[key])["detectors"] == [key]
    assert key not in DEFAULT_CONFIG["detectors"]
    entry = manifest(DEFAULT_MANIFEST)["models"][key]
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(VisioError, match="CUDA"):
        adapter(entry, tmp_path, 1)


def test_official_alignment_golden_pixels():
    # Golden generated from upstream detector.py at 387a42266dd385fbe8f7626c5d3aa03eea3bfaab.
    img = np.arange(200*240*3, dtype=np.uint32).reshape(200,240,3).astype(np.uint8)
    points = np.array([[80,70],[140,75],[110,103],[85,133],[134,135]], dtype=np.float32)
    face, _ = align_face(img, points, target_size=None, scale=1.3)
    assert face.shape == (232,232,3)
    assert hashlib.sha256(face.tobytes()).hexdigest() == "148df4548fd19b55e221fcb33e8ad23c615693d61e5760d32fa33b8e53f76e78"
    guarded, reason = aligned_face(img, np.array([[60,40,160,160,.9]]), points[None])
    assert reason is None
    np.testing.assert_equal(guarded, face)


@pytest.mark.parametrize("boxes,points,reason", [
    (np.empty((0,5)), None, "no_face"),
    (np.zeros((2,5)), None, "multiple_faces"),
    (np.array([[0,0,30,30,.9]]), np.ones((1,5,2)), "face_too_small"),
    (np.array([[0,0,100,100,.9]]), np.full((1,5,2),np.nan), "invalid_landmarks"),
])
def test_quality_never_becomes_fake_score(boxes, points, reason):
    face, actual = aligned_face(np.full((150,150,3),127,dtype=np.uint8),boxes,points)
    assert face is None and actual == reason


def test_network_uses_normalized_pooler_and_not_clip_projection():
    config = CLIPVisionConfig(hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                              num_attention_heads=4, image_size=28, patch_size=14, projection_dim=16)
    model = GenDNetwork(config).eval()
    pixels = torch.rand(2,3,28,28)
    with torch.inference_mode():
        features = model.feature_extractor.vision_model(pixels).pooler_output
        expected = model.model.linear(torch.nn.functional.normalize(features,p=2,dim=1))
        actual = model(pixels)
        model.feature_extractor.visual_projection.weight.fill_(float("nan"))
        torch.testing.assert_close(model(pixels), expected)
    torch.testing.assert_close(actual, expected)
    assert actual.shape == (2,2)


@pytest.mark.parametrize("key", ["gend", "gend_pe"])
def test_gend_pipeline_abstains_with_no_faces(tmp_path, monkeypatch, key):
    from visio import pipeline, gend, gend_pe
    from visio.tests.test_media_models import make_clip
    path = tmp_path / "clip.mp4"
    make_clip(path)
    class NoFaceDetector:
        def __init__(self, *args): pass
        def predict_with_quality(self, bgr): return None, "no_face"
        def provenance(self): return {"device": "test"}
    monkeypatch.setattr(pipeline, "verify", lambda *args: tmp_path)
    monkeypatch.setattr(gend if key == "gend" else gend_pe,
                        "GenDDetector" if key == "gend" else "GenDPEDetector", NoFaceDetector)
    value = pipeline.run(dict(config=configuration(detectors=[key]), input=str(path),
                              manifest=str(DEFAULT_MANIFEST),cache=str(tmp_path),session_id="test",generation=1))
    assert value["conclusion"] == "indeterminate"
    assert value["coverage"] == 0
    assert value["detectors"][key]["score"] is None
    assert value["quality_reasons"] == {key + ":no_face": 4}


def test_pe_pipeline_reuses_dense_landmarks_and_preserves_sparse_scores(tmp_path, monkeypatch):
    import json
    from visio import pipeline, gend_pe
    from visio.tests.test_media_models import make_clip
    path = tmp_path / "clip.mp4"
    make_clip(path)
    calls = []
    boxes = np.array([[10, 10, 100, 100, .9]])
    points = np.array([[[30, 30], [70, 30], [50, 50], [35, 70], [65, 70]]])
    detections = (boxes, points)
    class Locator:
        def detect(self, bgr):
            calls.append("locate")
            return detections
    class PE:
        def __init__(self, *args): self.locator = Locator()
        def predict_with_quality(self, bgr, detected):
            assert detected is detections
            calls.append("predict")
            return .75, None
        def provenance(self): return {"device": "test"}
    def verified(cache, key, entry):
        assert key == "gend_pe"  # No unrelated CPU locator or CLIP checkpoint.
        return tmp_path
    monkeypatch.setattr(pipeline, "verify", verified)
    monkeypatch.setattr(gend_pe, "GenDPEDetector", PE)
    tracking_path = tmp_path / "tracking.json"
    value = pipeline.run(dict(config=configuration(detectors=["gend_pe"]), input=str(path),
        manifest=str(DEFAULT_MANIFEST), cache=str(tmp_path), session_id="test", generation=1,
        tracking_file=str(tracking_path), media_id="clip-test"))
    assert value["status"] == "completed"
    assert value["detectors"]["gend_pe"]["score"] == .75
    assert value["conclusion"] == "verify"
    assert calls.count("locate") == 16 and calls.count("predict") == 4
    assert len(json.loads(tracking_path.read_text())["frames"]) == 16
    assert "gend_pe" in value["provenance"] and "gend" not in value["provenance"]
