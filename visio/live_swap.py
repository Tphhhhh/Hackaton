"""In-memory neural face swap. No camera access, frame files, or network calls."""
from io import BytesIO
import os
from pathlib import Path
from time import perf_counter

from .core import DEFAULT_CACHE, ROOT, file_hash

MODEL_REVISION = "581e70b61240b7928404c17900437f47cfe94133"
MODELS = {
    "det_10g.onnx": ("buffalo_l/buffalo_l/det_10g.onnx", "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91"),
    "w600k_r50.onnx": ("buffalo_l/buffalo_l/w600k_r50.onnx", "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43"),
    "inswapper_128_fp16.onnx": ("inswapper_128_fp16.onnx", "6d51a9278a1f650cffefc18ba53f38bf2769bf4bbff89267822cf72945f8a38b"),
}
MODEL_DIR = DEFAULT_CACHE / "live-models"
MAX_FRAME_BYTES = 1024 * 1024
MAX_PIXELS = 1280 * 720
PORTRAITS = {"brad-pitt": "Brad Pitt", "sam-altman": "Sam Altman"}


def decode_frame(payload):
    import cv2
    import numpy as np
    from PIL import Image

    # Inspect the JPEG header before allocating decoded pixel buffers.
    if not 0 < len(payload) <= MAX_FRAME_BYTES:
        raise ValueError("Image trop volumineuse.")
    try:
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
            if image.format != "JPEG" or not (16 <= width <= 1280 and 16 <= height <= 1280 and width * height <= MAX_PIXELS):
                raise ValueError("Image JPEG de 1280 × 720 pixels maximum requise.")
        frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Image illisible.")
        return frame
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Image JPEG invalide.") from exc


class LiveSwapper:
    def __init__(self, model_dir=MODEL_DIR):
        os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"
        import cv2
        import onnxruntime as ort
        from insightface.model_zoo.retinaface import RetinaFace
        from insightface.model_zoo.arcface_onnx import ArcFaceONNX
        from insightface.model_zoo.inswapper import INSwapper

        self.cv2 = cv2
        cv2.setNumThreads(2)
        ort.disable_telemetry_events()
        ort.preload_dlls(directory="")  # CUDA/cuDNN installed in this virtualenv.
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.log_severity_level = 3
        providers = [("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"}), "CPUExecutionProvider"]

        def load(name, model_type):
            path = Path(model_dir) / name
            if not path.is_file() or file_hash(path) != MODELS[name][1]:
                raise RuntimeError(f"Modèle absent ou invalide : {name}. Exécuter python -m visio.setup_live.")
            session = ort.InferenceSession(str(path), providers=providers, sess_options=options)
            model = model_type(model_file=str(path), session=session)
            if model.session.get_providers()[0] != "CUDAExecutionProvider":
                raise RuntimeError("CUDA indisponible : le face swap live nécessite le GPU NVIDIA.")
            return model

        self.detector = load("det_10g.onnx", RetinaFace)
        self.detector.prepare(ctx_id=0, input_size=(320, 320), det_thresh=0.5)
        recognizer = load("w600k_r50.onnx", ArcFaceONNX)
        self.swapper = load("inswapper_128_fp16.onnx", INSwapper)
        self.sources = {}
        for portrait_id, label in PORTRAITS.items():
            image = cv2.imread(str(ROOT.parent / "visio-demo/public/filters" / f"{portrait_id}.jpg"))
            if image is None:
                raise RuntimeError(f"Portrait de référence illisible : {label}.")
            scale = min(1, 960 / max(image.shape[:2]))
            image = cv2.resize(image, None, fx=scale, fy=scale)
            source = self.face(image)
            if source is None:
                raise RuntimeError(f"Aucun visage détecté dans le portrait : {label}.")
            recognizer.get(image, source)
            self.sources[portrait_id] = source
            # Warm up CUDA before advertising readiness. No webcam image is involved.
            self.swapper.get(image, source, source, paste_back=True)
        self.info = {"ready": True, "model": "InSwapper 128 FP16", "provider": "CUDA",
                     "default_portrait": "brad-pitt",
                     "portraits": [{"id": key, "label": label} for key, label in PORTRAITS.items()]}

    def face(self, image):
        from insightface.app.common import Face
        boxes, points = self.detector.detect(image, max_num=1)
        if not len(boxes):
            return None
        return Face(bbox=boxes[0, :4], kps=points[0], det_score=boxes[0, 4])

    def process(self, payload, portrait_id="brad-pitt"):
        if portrait_id not in self.sources:
            raise ValueError("Portrait inconnu.")
        start = perf_counter()
        frame = decode_frame(payload)
        face = self.face(frame)
        swapped = self.swapper.get(frame, face, self.sources[portrait_id], paste_back=True) if face is not None else frame
        ok, jpeg = self.cv2.imencode(".jpg", swapped, [self.cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise RuntimeError("Encodage impossible.")
        return jpeg.tobytes(), {"applied": face is not None, "inference_ms": round((perf_counter() - start) * 1000, 1)}
