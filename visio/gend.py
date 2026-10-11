"""Local GenD CLIP-L/14 inference; no remote Python or implicit downloads.

Architecture follows yermandy/GenD's MIT implementation (THIRD_PARTY.md).
The complete checkpoint already contains the vision backbone, so loading a
second CLIP checkpoint (including its unused text encoder) is unnecessary.
"""
import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from transformers import CLIPImageProcessor, CLIPVisionConfig, CLIPVisionModel
from safetensors.torch import load_file

from .core import fail, read_json
from .vendor.gend_alignment import align_face
from .vendor.gend_retinaface import RetinaFace


class GenDNetwork(nn.Module):
    """Preserve upstream state-dict names and normalized pooler -> 2 logits."""
    def __init__(self, vision_config):
        super().__init__()
        self.feature_extractor = nn.Module()
        self.feature_extractor.vision_model = CLIPVisionModel(vision_config).vision_model
        # Present in the official checkpoint, but unused by its forward pass.
        self.feature_extractor.visual_projection = nn.Linear(
            vision_config.hidden_size, vision_config.projection_dim, bias=False)
        self.model = nn.Module()
        self.model.linear = nn.Linear(vision_config.hidden_size, 2)

    def forward(self, pixels):
        features = self.feature_extractor.vision_model(pixels).pooler_output
        return self.model.linear(F.normalize(features, p=2, dim=1))


def aligned_face(bgr, boxes, landmarks):
    """Upstream alignment, with explicit quality abstention for interviews."""
    if len(boxes) != 1:
        return None, "no_face" if len(boxes) == 0 else "multiple_faces"
    if (landmarks is None or landmarks.shape != (1, 5, 2)
            or not np.isfinite(landmarks).all() or not np.isfinite(boxes).all()):
        return None, "invalid_landmarks"
    h, w = bgr.shape[:2]
    x1, y1, x2, y2 = boxes[0, :4]
    left, top = max(0, int(x1)), max(0, int(y1))
    right, bottom = min(w, int(x2)), min(h, int(y2))
    if min(right - left, bottom - top) < 64:
        return None, "face_too_small"
    gray = cv2.cvtColor(bgr[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    if gray.mean() < 25 or gray.mean() > 235:
        return None, "exposure"
    # Guard degenerate/out-of-frame points before the upstream dynamic-size warp.
    points = landmarks[0]
    if (np.any(points < 0) or np.any(points[:, 0] > w) or np.any(points[:, 1] > h)
            or np.linalg.norm(points[0] - points[1]) < 5):
        return None, "invalid_landmarks"
    face, _ = align_face(bgr, points, target_size=None, scale=1.3)
    return face, None


class GenDDetector:
    def __init__(self, entry, directory, threads):
        if entry.get("labels") != ["real", "fake"] or entry.get("attack_index") != 1:
            fail("InvalidPrediction", "Mapping GenD inattendu.", "Restaurer le manifeste épinglé.")
        if not torch.cuda.is_available():
            fail("ModelUnavailable", "GenD nécessite CUDA dans cet adaptateur.",
                 "Utiliser visio/.venv-gpu et rendre le GPU accessible ; aucun repli CPU implicite.")
        torch.set_num_threads(threads)
        torch.set_float32_matmul_precision("highest")
        torch.cuda.reset_peak_memory_stats()
        config = read_json(directory / "config.json")
        if config.get("backbone") != "openai/clip-vit-large-patch14" or config.get("head") != "LinearNorm":
            fail("ModelUnavailable", "Architecture GenD inattendue.", "Restaurer le checkpoint CLIP-L/14.")
        vision_config = CLIPVisionConfig(**read_json(directory / "clip_config.json")["vision_config"])
        vision_config._attn_implementation = "eager"
        # No random full-size allocation or duplicate CPU copy of the checkpoint.
        with torch.device("meta"):
            self.model = GenDNetwork(vision_config)
        weights = load_file(str(directory / "model.safetensors"), device="cpu")
        self.model.load_state_dict(weights, strict=True, assign=True)
        del weights
        embeddings = self.model.feature_extractor.vision_model.embeddings
        # This non-persistent buffer is absent from safetensors, hence still meta.
        embeddings.position_ids = torch.arange(embeddings.num_positions).expand((1, -1))
        self.model = self.model.eval().requires_grad_(False).to("cuda", dtype=torch.float32)
        self.processor = CLIPImageProcessor.from_pretrained(directory, local_files_only=True)
        self.locator = RetinaFace(str(directory / "det_10g.onnx"), providers=["CPUExecutionProvider"])
        self.locator.prepare(ctx_id=-1, nms_thresh=0.4, input_size=(640, 640), det_thresh=0.1)
        torch.cuda.synchronize()

    def predict_with_quality(self, bgr, detections=None):
        boxes, landmarks = self.locator.detect(bgr) if detections is None else detections
        face, reason = aligned_face(bgr, boxes, landmarks)
        if face is None:
            return None, reason
        pixels = self.processor(images=Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB)),
                                return_tensors="pt")["pixel_values"].to("cuda")
        with torch.inference_mode():
            logits = self.model(pixels)
            if logits.shape != (1, 2) or not torch.isfinite(logits).all():
                fail("InvalidPrediction", "Logits GenD invalides.", "Vérifier poids et prétraitement.")
            score = logits.softmax(-1)[0, 1].item()  # synchronizes CUDA for timing
        return score, None

    def provenance(self):
        return dict(device=torch.cuda.get_device_name(), cuda=torch.version.cuda,
                    precision="float32", attention="eager", batch_size=1,
                    face_locator="InsightFace det_10g.onnx / CPU", face_threshold=0.1,
                    alignment="GenD five landmarks, scale=1.3, target_size=None",
                    processor="CLIPImageProcessor / RGB / 224",
                    peak_cuda_allocated_mib=torch.cuda.max_memory_allocated() / 1024**2,
                    peak_cuda_reserved_mib=torch.cuda.max_memory_reserved() / 1024**2)
