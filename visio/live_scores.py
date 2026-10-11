"""Resident GenD PE inference on two independently decoded, unmarked images."""
import math
import os
from time import perf_counter

from .core import DEFAULT_CACHE, DEFAULT_MANIFEST
from .live_swap import decode_frame


DOMINANCE = 2.0


def dominant_face(boxes, landmarks):
    """Live calls only: keep the main face when it is clearly the largest.

    A small face in the background (a colleague behind the speaker) otherwise
    makes GenD PE abstain. Comparable faces still abstain as "multiple_faces".
    Clip analysis and benchmarks keep the original all-faces rule.
    """
    if boxes is None or landmarks is None or len(boxes) < 2 or len(landmarks) != len(boxes):
        return boxes, landmarks
    areas = [max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1])) for b in boxes]
    order = sorted(range(len(areas)), key=areas.__getitem__, reverse=True)
    if areas[order[0]] < DOMINANCE * areas[order[1]]:
        return boxes, landmarks
    keep = order[0]
    return boxes[keep:keep + 1], landmarks[keep:keep + 1]


class LivePEScorer:
    def __init__(self):
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        import cv2
        from .gend_pe import GenDPEDetector
        from .models import manifest, verify
        cv2.setNumThreads(2)
        entry = manifest(DEFAULT_MANIFEST)["models"]["gend_pe"]
        directory = verify(DEFAULT_CACHE, "gend_pe", entry)
        self.engine = GenDPEDetector(entry, directory, 2)
        self.info = dict(ready=True, model="gend_pe", revision=entry["revision"],
                         simulation=False, target_interval_ms=1000)

    def score_pair(self, original, filtered):
        # Validate both images before inference; each image gets its own face
        # detection. The filter state and MediaPipe landmarks are never inputs.
        images = [decode_frame(original), decode_frame(filtered)]
        start = perf_counter()
        values = {}
        for name, image in zip(("original", "filtered"), images):
            locator = getattr(self.engine, "locator", None)
            if locator is None:
                score, reason = self.engine.predict_with_quality(image)
            else:
                score, reason = self.engine.predict_with_quality(image, dominant_face(*locator.detect(image)))
            if score is not None and (not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError("Score GenD PE invalide.")
            values[name] = dict(score=score, reason=reason)
        return dict(model="gend_pe", revision=self.info["revision"], simulation=False,
                    **values, inference_ms=round((perf_counter() - start) * 1000, 1))
