"""Effort/DeepfakeBench five-point dlib alignment for the offline comparison.

Adapted from SCLBD/DeepfakeBench f188b1c105465e2e5377eb536a95022ae0e4522d,
preprocessing/preprocess.py (CC BY-NC 4.0). Additional quality failures become
abstentions. No image fallback when the face is missing.
"""
import cv2
import numpy as np
from skimage.transform import SimilarityTransform


def align_effort(rgb, landmarks, size=256):
    dst = np.array([[30.2946, 51.6963], [65.5318, 51.5014], [48.0252, 71.7366],
                    [33.5493, 92.3655], [62.7299, 92.2041]], dtype=np.float32)
    dst[:, 0] += 8.0
    dst[:, 0] = dst[:, 0] * size / 112
    dst[:, 1] = dst[:, 1] * size / 112
    margin = size * (1.3 - 1) / 2
    dst[:, 0] += margin
    dst[:, 1] += margin
    dst[:, 0] *= size / (size + 2 * margin)
    dst[:, 1] *= size / (size + 2 * margin)
    transform = SimilarityTransform()
    if not transform.estimate(landmarks.astype(np.float32), dst):
        raise ValueError("Degenerate face alignment")
    face = cv2.warpAffine(rgb, transform.params[:2], (size, size))
    return cv2.resize(face, (size, size))


def extract_face(bgr, detector, predictor):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    faces = detector(rgb, 1)
    if len(faces) != 1:
        return None, "no_face" if not faces else "multiple_faces"
    face = faces[0]
    h, w = bgr.shape[:2]
    left, top = max(0, face.left()), max(0, face.top())
    right, bottom = min(w, face.right()), min(h, face.bottom())
    if min(right - left, bottom - top) < 64:
        return None, "face_too_small"
    exposure = cv2.cvtColor(bgr[top:bottom, left:right], cv2.COLOR_BGR2GRAY).mean()
    if exposure < 25 or exposure > 235:
        return None, "exposure"
    shape = predictor(rgb, face)
    points = np.array([(shape.part(i).x, shape.part(i).y) for i in [37, 44, 30, 49, 55]])
    aligned = cv2.cvtColor(align_effort(rgb, points), cv2.COLOR_RGB2BGR)
    # DeepfakeBench's preprocessing also requires a detectable aligned face.
    if not detector(aligned, 1):
        return None, "aligned_face_missing"
    return aligned, None
