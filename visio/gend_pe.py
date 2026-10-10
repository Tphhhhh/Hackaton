"""Pinned GenD PE-L adapter, matching the upstream timm/LinearNorm path.

The full safetensors checkpoint contains the backbone. No pretrained backbone
download, remote Python, comparison-only dependencies, or CPU fallback.
"""
import cv2
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from safetensors.torch import load_file

from .core import fail, read_json
from .gend import aligned_face
from .vendor.gend_retinaface import RetinaFace


class PENetwork(nn.Module):
    def __init__(self):
        super().__init__()
        import timm
        if timm.__version__ != "1.0.20":
            fail("ModelUnavailable", "Version timm incompatible avec GenD PE.",
                 "Installer visio/requirements-gpu.lock.txt.")
        self.feature_extractor = nn.Module()
        backbone = timm.create_model("vit_pe_core_large_patch14_336", pretrained=False,
                                     dynamic_img_size=True)
        self.data_config = timm.data.resolve_model_data_config(backbone)
        self.data_config["input_size"] = (3, 224, 224)
        self.preprocess = timm.data.create_transform(**self.data_config, is_training=False)
        backbone.head = nn.Identity()
        self.feature_extractor.backbone = backbone
        self.model = nn.Module()
        self.model.linear = nn.Linear(backbone.num_features, 2)

    def forward(self, pixels):
        features = self.feature_extractor.backbone(pixels)
        return self.model.linear(F.normalize(features, p=2, dim=1))


class GenDPEDetector:
    def __init__(self, entry, directory, threads):
        if entry.get("labels") != ["real", "fake"] or entry.get("attack_index") != 1:
            fail("InvalidPrediction", "Mapping GenD PE inattendu.", "Restaurer le manifeste épinglé.")
        if not torch.cuda.is_available():
            fail("ModelUnavailable", "GenD PE nécessite CUDA dans cet adaptateur.",
                 "Utiliser visio/.venv-gpu et rendre le GPU accessible ; aucun repli CPU implicite.")
        torch.set_num_threads(threads)
        torch.set_float32_matmul_precision("highest")
        torch.cuda.reset_peak_memory_stats()
        config = read_json(directory / "config.json")
        if config.get("backbone") != "vit_pe_core_large_patch14_336" or config.get("head") != "LinearNorm":
            fail("ModelUnavailable", "Architecture GenD PE inattendue.", "Restaurer le checkpoint PE-L.")
        # timm initializes non-persistent RoPE buffers on CPU; meta construction
        # is not supported by this pinned backbone. assign avoids a second copy.
        self.model = PENetwork()
        weights = load_file(str(directory / "model.safetensors"), device="cpu")
        self.model.load_state_dict(weights, strict=True, assign=True)
        self.loaded_keys = len(weights)
        del weights
        self.model = self.model.eval().requires_grad_(False).to("cuda", dtype=torch.float32)
        self.locator = RetinaFace(str(directory / "det_10g.onnx"), providers=["CPUExecutionProvider"])
        self.locator.prepare(ctx_id=-1, nms_thresh=0.4, input_size=(640, 640), det_thresh=0.1)
        torch.cuda.synchronize()

    def predict_with_quality(self, bgr, detections=None):
        boxes, landmarks = self.locator.detect(bgr) if detections is None else detections
        face, reason = aligned_face(bgr, boxes, landmarks)
        if face is None:
            return None, reason
        rgb = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB))
        pixels = self.model.preprocess(rgb).unsqueeze(0).to("cuda")
        with torch.inference_mode():
            logits = self.model(pixels)
            if logits.shape != (1, 2) or not torch.isfinite(logits).all():
                fail("InvalidPrediction", "Logits GenD PE invalides.", "Vérifier poids et prétraitement.")
            score = logits.softmax(-1)[0, 1].item()
        return score, None

    def provenance(self):
        return dict(device=torch.cuda.get_device_name(), cuda=torch.version.cuda,
                    precision="float32", batch_size=1, timm="1.0.20",
                    backbone="vit_pe_core_large_patch14_336", strict_loaded_keys=self.loaded_keys,
                    face_locator="InsightFace det_10g.onnx / CPU", face_threshold=0.1,
                    alignment="GenD five landmarks, scale=1.3, target_size=None",
                    processor=self.model.data_config,
                    peak_cuda_allocated_mib=torch.cuda.max_memory_allocated() / 1024**2,
                    peak_cuda_reserved_mib=torch.cuda.max_memory_reserved() / 1024**2)
