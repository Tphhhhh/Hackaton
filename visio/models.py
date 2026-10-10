"""Pinned artifact acquisition is explicit; inference never downloads anything."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
import time
import urllib.request

from .core import VisioError, canonical_hash, fail, file_hash, read_json


def manifest(path):
    value = read_json(path)
    try:
        assert value["schema_version"] == "1.0"
        for key, entry in value["models"].items():
            assert re.fullmatch(r"[a-z][a-z0-9_-]*", key)
            assert entry["kind"] in ("vit", "minifasnet", "face_locator", "gend")
            assert entry["files"] and entry["revision"] and entry["license"]
            names = set()
            for f in entry["files"]:
                assert Path(f["name"]).name == f["name"] and f["name"] not in (".", "..")
                assert f["name"] not in names
                names.add(f["name"])
                assert re.fullmatch(r"[0-9a-f]{64}", f["sha256"])
                assert type(f["size"]) is int and 0 < f["size"] <= 1500 * 1024**2
                assert f["url"].startswith("https://")
    except (AssertionError, KeyError, TypeError, AttributeError) as exc:
        raise VisioError("InvalidConfiguration", "Manifeste modèle invalide.",
                         "Restaurer visio/models.json ou vérifier ses champs.") from exc
    return value


def verify(cache, key, entry):
    directory = Path(cache) / "models" / key
    for f in entry["files"]:
        path = directory / f["name"]
        if not path.is_file() or path.stat().st_size != f["size"] or file_hash(path) != f["sha256"]:
            fail("ModelUnavailable", f"Fichier manquant ou empreinte invalide : {key}/{f['name']}.",
                 "Exécuter explicitement python -m visio fetch-models.")
    return directory


def download(cache, key, entry):
    directory = Path(cache) / "models" / key
    directory.mkdir(parents=True, exist_ok=True)
    for f in entry["files"]:
        dest = directory / f["name"]
        if dest.is_file() and dest.stat().st_size == f["size"] and file_hash(dest) == f["sha256"]:
            continue
        fd, temp = tempfile.mkstemp(prefix=".download-", dir=directory)
        try:
            start = time.monotonic()
            with os.fdopen(fd, "wb") as out, urllib.request.urlopen(f["url"], timeout=30) as response:
                if not response.url.startswith("https://"):
                    raise ValueError("insecure redirect")
                total = 0
                while block := response.read(1024**2):
                    total += len(block)
                    if total > f["size"] or time.monotonic() - start > 600:
                        raise ValueError("download budget exceeded")
                    out.write(block)
            if Path(temp).stat().st_size != f["size"] or file_hash(temp) != f["sha256"]:
                raise ValueError("checksum mismatch")
            os.replace(temp, dest)
        except Exception as exc:
            raise VisioError("ModelUnavailable", f"Téléchargement non validé : {key}/{f['name']}.",
                             "Vérifier le réseau et relancer fetch-models ; aucun fichier partiel accepté.") from exc
        finally:
            Path(temp).unlink(missing_ok=True)
    verify(cache, key, entry)


def fas_tensor(bgr, bbox, scale=2.7):
    """Follow the pinned yakhyo ONNX reference: BGR float32, no /255.

    Context crop clamps at the image edge, then includes both endpoints.
    Reference and Apache-2.0 attribution: THIRD_PARTY.md.
    """
    import cv2
    import numpy as np
    height, width = bgr.shape[:2]
    x, y, w, h = (int(v) for v in bbox)
    if min(w, h) <= 0:
        fail("InvalidPrediction", "Rectangle visage vide.", "Vérifier le localisateur.")
    factor = min((height - 1) / h, (width - 1) / w, scale)
    cx, cy = x + w / 2, y + h / 2
    left, right = max(0, int(cx - w * factor / 2)), min(width - 1, int(cx + w * factor / 2))
    top, bottom = max(0, int(cy - h * factor / 2)), min(height - 1, int(cy + h * factor / 2))
    crop = bgr[top:bottom + 1, left:right + 1]
    return cv2.resize(crop, (80, 80)).astype(np.float32).transpose(2, 0, 1)[None]


class FaceLocator:
    def __init__(self, directory):
        import cv2
        self.cv2 = cv2
        self.model = cv2.FaceDetectorYN.create(str(directory / "face_detection_yunet_2023mar.onnx"),
                                              "", (320, 320), 0.8, 0.3, 5000)

    def locate(self, bgr):
        h, w = bgr.shape[:2]
        # Resize for bounded face localisation cost, retain original-image coordinates.
        ratio = min(1.0, 640 / max(w, h))
        small = self.cv2.resize(bgr, (max(1, round(w * ratio)), max(1, round(h * ratio))))
        self.model.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.model.detect(small)
        if faces is None or len(faces) != 1:
            return None, "no_face" if faces is None or len(faces) == 0 else "multiple_faces"
        x, y, bw, bh = (faces[0, :4] / ratio).tolist()
        left, top = max(0, int(x)), max(0, int(y))
        right, bottom = min(w, int(x + bw)), min(h, int(y + bh))
        if min(right - left, bottom - top) < 64:
            return None, "face_too_small"
        # Quality heuristics are abstention only, never evidence of fraud.
        gray = self.cv2.cvtColor(bgr[top:bottom, left:right], self.cv2.COLOR_BGR2GRAY)
        if gray.mean() < 25 or gray.mean() > 235:
            return None, "exposure"
        return [left, top, right - left, bottom - top], None


class Detector:
    def __init__(self, entry, directory, threads):
        self.entry = entry
        self.directory = directory
        if entry["kind"] == "vit":
            import torch
            from transformers import ViTForImageClassification, ViTImageProcessor
            torch.set_num_threads(threads)
            self.torch = torch
            self.processor = ViTImageProcessor.from_pretrained(directory, local_files_only=True)
            self.model = ViTForImageClassification.from_pretrained(
                directory, local_files_only=True, use_safetensors=True).eval()
            if [self.model.config.id2label[i] for i in range(2)] != entry["labels"]:
                fail("InvalidPrediction", "Mapping des labels inattendu.", "Vérifier modèle et manifeste.")
        elif entry["kind"] == "minifasnet":
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = threads
            options.inter_op_num_threads = 1
            self.model = ort.InferenceSession(str(directory / "model.onnx"), options,
                                              providers=["CPUExecutionProvider"])
            if self.model.get_inputs()[0].shape[-3:] != [3, 80, 80]:
                fail("InvalidPrediction", "Forme ONNX inattendue.", "Vérifier l'export MiniFASNetV2.")
        else:
            fail("InvalidConfiguration", "Type détecteur non pris en charge.", "Vérifier le manifeste.")

    def predict(self, bgr, bbox):
        if self.entry["kind"] == "vit":
            from PIL import Image
            inputs = self.processor(images=Image.fromarray(bgr[:, :, ::-1]), return_tensors="pt")
            with self.torch.inference_mode():
                probs = self.model(**inputs).logits.softmax(-1)
            return float(probs[0, self.entry["attack_index"]])
        import numpy as np
        tensor = fas_tensor(bgr, bbox, self.entry["crop_scale"])
        logits = self.model.run(None, {self.model.get_inputs()[0].name: tensor})[0]
        if logits.shape != (1, 3) or not np.isfinite(logits).all():
            fail("InvalidPrediction", "Sortie ONNX invalide.", "Vérifier l'adaptateur.")
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        return float(1 - probs[0, self.entry["real_index"]])
