
import av
import numpy as np
import pytest

from visio.core import DEFAULT_CONFIG, DEFAULT_MANIFEST, VisioError, file_hash
from visio.models import fas_tensor, manifest, verify
from visio.pipeline import media_path, sampled_frames


def make_clip(path, seconds=2, fps=10):
    with av.open(str(path), "w") as output:
        stream = output.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 160, 120, "yuv420p"
        for i in range(seconds*fps):
            frame = av.VideoFrame.from_ndarray(np.full((120,160,3), 50+i, dtype=np.uint8), format="bgr24")
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)


def test_stream_sampling_uses_pts_and_never_copies_video(tmp_path):
    path = tmp_path / "sample.mp4"
    make_clip(path)
    digest = file_hash(path)
    meta = {}
    frames = list(sampled_frames(path, 2, meta))
    assert [t for t, _ in frames] == [0, .5, 1, 1.5]
    assert meta["decoded_frames"] == 20
    assert meta["duration_seconds"] == pytest.approx(2)
    assert file_hash(path) == digest


def test_empty_and_non_video_inputs(tmp_path):
    path = tmp_path / "empty.mp4"
    path.touch()
    with pytest.raises(VisioError):
        media_path(path)
    path = tmp_path / "playlist.m3u8"
    path.write_text("https://example.invalid/a.ts")
    with pytest.raises(VisioError):
        media_path(path)


def test_minifasnet_color_scale_and_boundary_crop():
    bgr = np.zeros((100,100,3), dtype=np.uint8)
    bgr[:] = [12, 120, 240]
    got = fas_tensor(bgr, [0,0,20,30])
    assert got.shape == (1,3,80,80)
    assert got.dtype == np.float32
    np.testing.assert_equal(got[0,:,0,0], [12,120,240])
    np.testing.assert_equal(got[0,:,-1,-1], [12,120,240])


def test_model_hash_mismatch_and_pinned_label_mapping(tmp_path):
    m = manifest(DEFAULT_MANIFEST)
    assert m["models"]["dima"]["labels"] == ["Real", "Fake"]
    assert m["models"]["prithiv"]["labels"] == ["Realism", "Deepfake"]
    assert m["models"]["minifasnet"]["real_index"] == 1
    assert m["models"]["minifasnet"]["files"][0]["sha256"] == "b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907"
    with pytest.raises(VisioError):
        verify(tmp_path, "dima", m["models"]["dima"])


def test_preprocessing_matches_processor_configuration():
    from PIL import Image
    from transformers import ViTImageProcessor
    from visio.core import DEFAULT_CACHE
    directory = DEFAULT_CACHE / "models/dima"
    if not (directory / "preprocessor_config.json").exists():
        pytest.skip("optional pinned processor configuration not fetched")
    processor = ViTImageProcessor.from_pretrained(directory, local_files_only=True)
    image = Image.fromarray(np.full((250,300,3), [0,127,255], dtype=np.uint8))
    tensor = processor(images=image, return_tensors="np")["pixel_values"]
    assert tensor.shape == (1,3,224,224)
    expected = (np.array([0,127,255])/255 - np.array(processor.image_mean))/np.array(processor.image_std)
    np.testing.assert_allclose(tensor[0,:,100,100], expected, atol=1e-6)


def test_complete_pipeline_uses_same_result_contract(tmp_path, monkeypatch):
    from visio import pipeline
    from visio.core import canonical_hash
    from jsonschema import validate
    import json
    path = tmp_path / "video.mp4"
    make_clip(path)
    class Locator:
        def __init__(self, directory):
            pass
        def locate(self, bgr):
            return [20,20,80,80], None
    class FakeDetector:
        def __init__(self, entry, directory, threads):
            pass
        def predict(self, bgr, bbox):
            assert bgr.shape == (120,160,3)
            return .9
    monkeypatch.setattr(pipeline, "verify", lambda *a: tmp_path)
    monkeypatch.setattr(pipeline, "FaceLocator", Locator)
    monkeypatch.setattr(pipeline, "Detector", FakeDetector)
    value = pipeline.run(dict(config=DEFAULT_CONFIG,input=str(path),manifest=str(DEFAULT_MANIFEST),
                              cache=str(tmp_path),session_id="test",generation=1))
    assert value["conclusion"] == "verify"
    assert value["sampled_frames"] == 4
    assert value["coverage"] == 1
    validate(value, json.loads((DEFAULT_MANIFEST.parent / "schema.json").read_text()))
