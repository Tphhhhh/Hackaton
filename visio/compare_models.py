"""Isolated exploratory comparison; does not change the live app or its models.

Extra packages live in .cache/comparison-deps, not the application's environment.
Run one model per process to isolate GPU memory and model loading measurements.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".cache/comparison-deps"))
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", OMP_NUM_THREADS="2")

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from safetensors.torch import load_file
from transformers import CLIPVisionConfig, CLIPVisionModel

from .benchmark import dataset, metrics
from .core import DEFAULT_CACHE, DEFAULT_MANIFEST, aggregate, canonical_hash, configuration, file_hash
from .gend import GenDDetector, aligned_face
from .models import manifest, verify
from .pipeline import sampled_frames
from .vendor.gend_retinaface import RetinaFace

ASSETS = ROOT / ".cache/comparison-models"
REFERENCE = ROOT / ".cache/comparison-reference"
PE_SHA = "e2367f8db3a6b76f8d5cc5857f1ed0ea0993b33c9e1f428d3b06e5ca95de2213"


def checked(path, expected):
    if file_hash(path) != expected:
        raise ValueError(f"Checksum mismatch: {path.name}")
    return path


class PENetwork(nn.Module):
    def __init__(self):
        super().__init__()
        import timm
        if timm.__version__ != "1.0.20":
            raise ValueError("Use the pinned upstream timm 1.0.20")
        self.feature_extractor = nn.Module()
        backbone = timm.create_model("vit_pe_core_large_patch14_336", pretrained=False, dynamic_img_size=True)
        self.data_config = timm.data.resolve_model_data_config(backbone)
        self.data_config["input_size"] = (3, 224, 224)
        self.preprocess = timm.data.create_transform(**self.data_config, is_training=False)
        backbone.head = nn.Identity()
        self.feature_extractor.backbone = backbone
        self.model = nn.Module()
        self.model.linear = nn.Linear(backbone.num_features, 2)

    def forward(self, pixels):
        return self.model.linear(F.normalize(self.feature_extractor.backbone(pixels), p=2, dim=1))


class PEDetector:
    def __init__(self):
        weights = checked(ASSETS / "gend-pe.safetensors", PE_SHA)
        self.model = PENetwork()
        state = load_file(str(weights))
        self.model.load_state_dict(state, strict=True, assign=True)
        self.keys = len(state)
        del state
        self.model.eval().requires_grad_(False).to("cuda")
        directory = verify(DEFAULT_CACHE, "gend", manifest(DEFAULT_MANIFEST)["models"]["gend"])
        self.locator = RetinaFace(str(directory / "det_10g.onnx"), providers=["CPUExecutionProvider"])
        self.locator.prepare(ctx_id=-1, input_size=(640, 640), nms_thresh=.4, det_thresh=.1)

    def predict_with_quality(self, bgr):
        boxes, points = self.locator.detect(bgr)
        face, reason = aligned_face(bgr, boxes, points)
        if face is None:
            return None, reason
        pixels = self.model.preprocess(Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB))).unsqueeze(0).to("cuda")
        with torch.inference_mode():
            return self.model(pixels).softmax(-1)[0, 1].item(), None

    def provenance(self):
        return dict(weights_sha256=PE_SHA, revision="4fd5a38cf071af2640d314110826ed5cd25cab88",
                    strict_loaded_keys=self.keys, processor=self.model.data_config,
                    alignment="GenD official five landmarks, scale 1.3, dynamic size",
                    source="https://huggingface.co/yermandy/GenD_PE_L", license="GenD MIT; PE backbone license must also be checked before redistribution; InsightFace research only")


def merge_effort_state(state):
    """Fold published SVD residuals into dense weights without recomputing SVD."""
    state = {k.removeprefix("module."): v for k, v in state.items()}
    output = {}
    used = set()
    for key, value in state.items():
        if key.endswith(".weight_main"):
            prefix = key.removesuffix("weight_main")
            names = [prefix + suffix for suffix in ("U_residual", "S_residual", "V_residual")]
            if any(name in state for name in names):
                if not all(name in state for name in names):
                    raise ValueError("Incomplete Effort residual")
                u, s, v = (state[name] for name in names)
                value = value + u @ torch.diag(s) @ v
                used.update(names)
            output[prefix + "weight"] = value
            used.add(key)
    for key, value in state.items():
        if key not in used:
            output[key] = value
    return output


class EffortNetwork(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.backbone = CLIPVisionModel(config).vision_model
        self.head = nn.Linear(config.hidden_size, 2)

    def forward(self, pixels):
        return self.head(self.backbone(pixels).pooler_output)


class EffortDetector:
    def __init__(self):
        import dlib
        from torchvision import transforms
        from .comparison_effort_face import extract_face
        self.extract_face = extract_face
        self.face_detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor(str(checked(ASSETS / "shape_predictor_81_face_landmarks.dat",
            "8cae4375589dd915d9a0a881101bed1bbb4e9887e35e63b024388f1ca25ff869")))
        provenance = json.loads((ASSETS / "effort-ffpp.pth.provenance.json").read_text())
        weights = checked(ASSETS / "effort-ffpp.pth", provenance["sha256"])
        # No arbitrary pickle objects or remote model Python.
        raw = torch.load(weights, map_location="cpu", weights_only=True, mmap=True)
        state = raw.get("state_dict", raw)
        if not isinstance(state, dict) or not all(isinstance(v, torch.Tensor) for v in state.values()):
            raise ValueError("Expected tensor-only Effort state_dict")
        self.keys = len(state)
        state = merge_effort_state(state)
        cfg = CLIPVisionConfig(**json.loads((DEFAULT_CACHE / "models/gend/clip_config.json").read_text())["vision_config"])
        cfg._attn_implementation = "eager"
        with torch.device("meta"):
            self.model = EffortNetwork(cfg)
        self.model.load_state_dict(state, strict=True, assign=True)
        self.model.backbone.embeddings.position_ids = torch.arange(257).expand((1, -1))
        self.model.eval().requires_grad_(False).to("cuda")
        self.preprocess = transforms.Compose([transforms.ToTensor(), transforms.Normalize(
            [.48145466, .4578275, .40821073], [.26862954, .26130258, .27577711])])
        self.weights_provenance = provenance

    def predict_with_quality(self, bgr):
        face, reason = self.extract_face(bgr, self.face_detector, self.predictor)
        if face is None:
            return None, reason
        # Official benchmark path: aligned 256 crop, RGB, cubic resize to 224.
        rgb = cv2.resize(cv2.cvtColor(face, cv2.COLOR_BGR2RGB), (224, 224), interpolation=cv2.INTER_CUBIC)
        pixels = self.preprocess(Image.fromarray(rgb)).unsqueeze(0).to("cuda")
        with torch.inference_mode():
            return self.model(pixels).softmax(-1)[0, 1].item(), None

    def provenance(self):
        return dict(weights=self.weights_provenance, strict_loaded_source_keys=self.keys,
                    preprocessing="DeepfakeBench 256px dlib-81 alignment, scale 1.3; RGB cubic resize to 224; CLIP normalization",
                    precision="float32; SVD residual matrices folded into dense weights on CPU",
                    license="Effort CC-BY-NC-4.0; landmark model has separate upstream terms")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["gend-clip", "gend-pe", "effort"], required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "local-data/gend-pilot.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/model-comparison-20261010")
    args = parser.parse_args()
    data = dataset(args.dataset)
    args.output.mkdir(parents=True, exist_ok=True)
    config = configuration(detectors=["gend"])
    protocol = dict(kind="exploratory_same_clips_same_times", dataset_sha256=canonical_hash(data),
                    config=config, sample_fps=2, threshold=.5, flag_fraction=.5,
                    precision="float32", batch_size=1, tracking=False,
                    models=["gend-clip", "gend-pe", "effort"],
                    limitations=["Seven previously inspected development clips; no held-out validation.",
                                 "Model-specific published preprocessing; differing face coverage is reported.",
                                 "No tuning of thresholds on these results. Timing excludes dense tracking."])
    protocol_path = args.output / "protocol.json"
    if protocol_path.exists():
        if json.loads(protocol_path.read_text()) != protocol:
            raise ValueError("Protocol changed; use a new output directory")
    else:
        protocol_path.write_text(json.dumps(protocol, indent=2))
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no implicit CPU fallback")
    cv2.setNumThreads(2)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    if args.model == "gend-clip":
        entry = manifest(DEFAULT_MANIFEST)["models"]["gend"]
        engine = GenDDetector(entry, verify(DEFAULT_CACHE, "gend", entry), 2)
    else:
        engine = PEDetector() if args.model == "gend-pe" else EffortDetector()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    report = dict(model=args.model, protocol_sha256=canonical_hash(protocol),
                  source_sha256={p.name: file_hash(p) for p in [Path(__file__), ROOT / "gend.py", ROOT / "pipeline.py"]},
                  gpu=torch.cuda.get_device_name(), torch=torch.__version__,
                  model_load_seconds=load_seconds, provenance=engine.provenance(), clips=[])
    summary_rows = []
    for clip in data["clips"]:
        started = time.perf_counter()
        metadata, observations = {}, []
        for stamp, bgr in sampled_frames((args.dataset.parent / clip["path"]).resolve(), 2, metadata):
            score, reason = engine.predict_with_quality(bgr)
            if score is not None and not np.isfinite(score):
                raise ValueError("Nonfinite score")
            observations.append(dict(time_seconds=round(stamp, 6), score=score, reason=reason))
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        result = aggregate(observations, metadata["duration_seconds"], config)
        row = dict(id=clip["id"], label=clip["label"], sha256=clip["sha256"], duration_seconds=metadata["duration_seconds"],
                   processing_seconds=elapsed, samples=len(observations), result=result)
        report["clips"].append(row)
        summary_rows.append(dict(label=clip["label"], attack_kind=clip["attack_kind"], source_id=clip["source_id"], outcome=result["conclusion"]))
        report["metrics"] = metrics(summary_rows, ["face_swap", "reenactment"], ["face_swap"])
        report["peak_cuda_allocated_mib"] = torch.cuda.max_memory_allocated() / 1024**2
        report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        report["completed"] = len(report["clips"]) == len(data["clips"])
        (args.output / f"{args.model}.json").write_text(json.dumps(report, indent=2, allow_nan=False))
        print(json.dumps(dict(model=args.model, clip=clip["id"], score=result["score"],
                              conclusion=result["conclusion"], coverage=result["coverage"], seconds=elapsed)), flush=True)


if __name__ == "__main__":
    main()
