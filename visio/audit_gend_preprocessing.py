"""Offline diagnostic against reviewed, hash-pinned upstream GenD source.

Run with the GPU environment, from the repository root:
  python -m visio.audit_gend_preprocessing --reference /tmp/visio-gend-reference

Does not modify the detector, thresholds, source media, or application results.
Artifacts include private video stills and stay in ignored visio/reports/.
"""
import argparse
import ast
import hashlib
import heapq
import io
import json
import os
from pathlib import Path
import types

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", OMP_NUM_THREADS="2")

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import torch
from transformers import CLIPImageProcessor

from .core import DEFAULT_CACHE, DEFAULT_MANIFEST, file_hash
from .gend import GenDDetector, aligned_face
from .models import manifest, verify
from .pipeline import sampled_frames
from .vendor.gend_retinaface import RetinaFace


REVISION = "387a42266dd385fbe8f7626c5d3aa03eea3bfaab"
SOURCES = {
    "detector.py": "c7cbdf2dc37ffd5612f3a6b5583027e8eaa42e5eb261eae447bf92b1919eb7b7",
    "src_retinaface.py": "5a9f6232c672b0869c42b7798442ec5405cfaea8fc673635d818382a922fd567",
    "src_hf_modeling_gend.py": "4b76b83df8d0f5c59082e97ececeb67735eb79a1fa0fc09d9299710179b75ad0",
}


def definitions(path, names, namespace):
    """Execute only explicitly reviewed definitions, never imports/entrypoints."""
    tree = ast.parse(path.read_text())
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert {n.name for n in selected} == set(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def digest(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def max_diff(a, b):
    return float(np.max(np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))))


def reference_frames(path):
    """Upstream RGB decode -> BGR, via the same PyAV backend as imageio.

    This independently checks RGB/BGR decoding, not imageio's indexing API.
    The two audited clips have zero rotation; rotation is separately unit-tested.
    """
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        first = None
        for index, frame in enumerate(container.decode(stream)):
            stamp = float(frame.pts * frame.time_base)
            first = stamp if first is None else first
            assert frame.rotation == 0, "Audit reference currently expects unrotated clips"
            rgb = frame.to_ndarray(format="rgb24")
            yield index, round(stamp - first, 6), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


class CaptureProcessor:
    def __init__(self, processor):
        self.processor = processor
        self.pixels = None

    def __call__(self, *args, **kwargs):
        output = self.processor(*args, **kwargs)
        self.pixels = output["pixel_values"].clone()
        return output


def contact_sheet(name, selected, destination):
    width, row_height = 970, 290
    sheet = Image.new("RGB", (width, 46 + row_height * len(selected)), "#131923")
    draw = ImageDraw.Draw(sheet)
    draw.text((14, 12), f"{name} | source + detections / aligned crop / actual 224x224 model input", fill="white")
    for row, (observation, original, crop, tensor) in enumerate(selected):
        y = 46 + row * row_height
        annotated = original.copy()
        for point in observation["landmarks"]:
            cv2.circle(annotated, tuple(np.round(point).astype(int)), 4, (0, 255, 0), -1)
        x1, y1, x2, y2 = np.round(observation["box"][:4]).astype(int)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        source = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
        sheet.paste(ImageOps.contain(source, (448, 240)), (14, y + 24))
        face = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        sheet.paste(ImageOps.contain(face, (224, 224)), (486, y + 24))
        means = np.array([0.48145466, 0.4578275, 0.40821073])
        stds = np.array([0.26862954, 0.26130258, 0.27577711])
        pixels = np.rint(np.clip(tensor[0].permute(1, 2, 0).numpy() * stds + means, 0, 1) * 255).astype(np.uint8)
        sheet.paste(Image.fromarray(pixels), (732, y + 24))
        draw.text((14, y + 4), f"t={observation['time_seconds']:.3f}s   score={observation['score']*100:.2f}/100   crop={crop.shape[1]}px", fill="white")
    sheet.save(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("visio/reports/preprocessing-audit-20261010"))
    args = parser.parse_args()
    for name, expected in SOURCES.items():
        assert file_hash(args.reference / name) == expected, f"Unreviewed reference: {name}"
    args.output.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        (args.output / name).write_bytes((args.reference / name).read_bytes())
    # Source equality of every runtime face-detector definition; only its unused
    # downloader/demo were removed in our vendored module.
    upstream = ast.parse((args.reference / "src_retinaface.py").read_text())
    local = ast.parse(Path("visio/vendor/gend_retinaface.py").read_text())
    upstream_defs = {n.name: ast.dump(n) for n in upstream.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    checked_defs = []
    for node in local.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            assert ast.dump(node) == upstream_defs[node.name], node.name
            checked_defs.append(node.name)
    reference = definitions(args.reference / "detector.py", ["align_face", "max_spread_permutation_pq"],
                            dict(np=np, cv2=cv2, heapq=heapq))
    encoder = definitions(args.reference / "src_hf_modeling_gend.py", ["CLIPEncoder"],
                          dict(torch=torch, nn=torch.nn, Image=Image))["CLIPEncoder"]
    entry = manifest(DEFAULT_MANIFEST)["models"]["gend"]
    directory = verify(DEFAULT_CACHE, "gend", entry)
    cv2.setNumThreads(2)
    engine = GenDDetector(entry, directory, 2)
    reference_processor = CLIPImageProcessor.from_pretrained(directory, local_files_only=True)
    reference_encoder = types.SimpleNamespace(_preprocess=reference_processor)
    recorder = CaptureProcessor(engine.processor)
    engine.processor = recorder
    # Separate instance of the exact upstream detector algorithm.
    ref_locator = RetinaFace(str(directory / "det_10g.onnx"), providers=["CPUExecutionProvider"])
    ref_locator.prepare(ctx_id=-1, nms_thresh=0.4, input_size=(640, 640), det_thresh=0.1)
    output = dict(reference_revision=REVISION, reference_sha256=SOURCES,
                  detector_ast_equal=checked_defs, model_revision=entry["revision"],
                  implementation_sha256={p: file_hash(p) for p in ["visio/gend.py", "visio/pipeline.py", "visio/audit_gend_preprocessing.py"]},
                  reference_decode="PyAV RGB24 -> OpenCV BGR; same backend/color path as upstream imageio; imageio API not executed",
                  processor=reference_processor.to_dict(), clips={})
    for name, filename, previous_name in [
        ("ludo", "visio/local-data/ludo1.mp4", "real-02"),
        ("deepfake-01", "visio/local-data/deepfake-timit/deepfake-01.mp4", "attack-01"),
    ]:
        print(f"Auditing {name}", flush=True)
        path = Path(filename)
        metadata = {}
        current = {round(t, 6): frame for t, frame in sampled_frames(path, 2, metadata)}
        dense_stamps = [round(t, 6) for t, _ in sampled_frames(path, 8, {}, max_samples=160)]
        next_analysis = 0
        dense_analysis = []
        for t in dense_stamps:
            if t + 1e-6 >= next_analysis:
                dense_analysis.append(t)
                next_analysis = (np.floor(t * 2 + 1e-6) + 1) / 2
        assert dense_analysis == list(current), "Tracking changes analysis timestamps"
        previous = json.loads(Path(f"visio/reports/gend-pilot-20261010/{previous_name}.json").read_text())
        old = {o["time_seconds"]: o["score"] for o in previous["detectors"]["gend"]["observations"]}
        rows, previews = [], []
        for index, stamp, ref_bgr in reference_frames(path):
            if stamp not in current:
                continue
            bgr = current[stamp]
            boxes, landmarks = engine.locator.detect(bgr)
            ref_boxes, ref_landmarks = ref_locator.detect(ref_bgr)
            score, reason = engine.predict_with_quality(bgr, (boxes, landmarks))
            assert reason is None and len(ref_boxes) == 1, (name, stamp, reason)
            face, reason = aligned_face(bgr, boxes, landmarks)
            ref_face, ref_mask = reference["align_face"](ref_bgr, ref_landmarks[0], target_size=None,
                                                       scale=1.3, mask=np.full(ref_bgr.shape[:2], 255, np.uint8))
            # Upstream dataset path saves lossless PNG then loads a RGB PIL image.
            success, encoded = cv2.imencode(".png", ref_face)
            assert success
            with Image.open(io.BytesIO(encoded.tobytes())) as pil:
                ref_pixels = encoder.preprocess(reference_encoder, pil.convert("RGB")).unsqueeze(0)
            pixels = recorder.pixels
            with torch.inference_mode():
                ref_score = engine.model(ref_pixels.to("cuda")).softmax(-1)[0, 1].item()
            row = dict(time_seconds=stamp, frame_index=index, score=score, reference_score=ref_score,
                       previous_score=old[stamp], decode_max_abs=max_diff(bgr, ref_bgr),
                       boxes_max_abs=max_diff(boxes, ref_boxes), landmarks_max_abs=max_diff(landmarks, ref_landmarks),
                       aligned_pixels_max_abs=max_diff(face, ref_face), tensor_max_abs=max_diff(pixels.numpy(), ref_pixels.numpy()),
                       score_abs_difference=abs(score-ref_score), previous_abs_difference=abs(score-old[stamp]),
                       tensor_sha256=digest(pixels.numpy()), box=boxes[0].tolist(), landmarks=landmarks[0].tolist(),
                       crop_size=list(face.shape), warp_border_fraction=float(np.mean(ref_mask == 0)))
            rows.append(row)
            previews.append((row, bgr, face, pixels))
        assert len(rows) == len(current) == len(old)
        scores = [r["score"] for r in rows]
        ids = sorted({0, len(rows)//2, len(rows)-1, int(np.argmin(scores)), int(np.argmax(scores))})
        contact_sheet(name, [previews[i] for i in ids], args.output / f"{name}-crops.png")
        clip = dict(input_sha256=file_hash(path), metadata=metadata, observations=rows,
                    samples=len(rows), mean_score=float(np.mean(scores)), flagged_fraction=float(np.mean(np.array(scores) >= .5)),
                    tracking_analysis_timestamps_equal=True,
                    maxima={key: max(r[key] for r in rows) for key in ["decode_max_abs", "boxes_max_abs", "landmarks_max_abs", "aligned_pixels_max_abs", "tensor_max_abs", "score_abs_difference", "previous_abs_difference", "warp_border_fraction"]})
        output["clips"][name] = clip
        print(json.dumps({name: {k: v for k, v in clip.items() if k not in ["observations"]}}), flush=True)
        # Predefined official at_least/n=32 selection: diagnostic, no tuning.
        # These clips have one usable face per sampled frame.
        frame_ids = reference["max_spread_permutation_pq"](metadata["decoded_frames"], start=metadata["decoded_frames"]//2)[:32]
        selected_ids = set(frame_ids)
        alternate = []
        for index, stamp, bgr in reference_frames(path):
            if index in selected_ids:
                score, reason = engine.predict_with_quality(bgr)
                alternate.append(dict(frame_index=index, time_seconds=stamp, score=score, reason=reason))
        valid = [r["score"] for r in alternate if r["score"] is not None]
        clip["official_selection_32_diagnostic"] = dict(
            selection="First 32 max_spread_permutation_pq indices, starting at middle frame; no replacement on quality rejection",
            observations=alternate, usable=len(valid), mean_score=float(np.mean(valid)),
            flagged_fraction=float(np.mean(np.array(valid) >= .5)))
        print(f"{name} alternate32: mean={np.mean(valid):.6f}, usable={len(valid)}", flush=True)
        (args.output / "audit.json").write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(f"Audit written to {args.output}", flush=True)


if __name__ == "__main__":
    main()
