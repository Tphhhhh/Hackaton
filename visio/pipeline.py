"""Streaming local-file pipeline. Runs only inside the supervised worker."""
from __future__ import annotations

import importlib.metadata
import json
import math
from pathlib import Path
import resource
import time

from .core import VisioError, aggregate, conclude, fail, canonical_hash, result
from .models import Detector, FaceLocator, manifest, verify


def media_path(path):
    path = Path(path)
    if (path.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm", ".avi")
            or not path.is_file() or not 0 < path.stat().st_size <= 50 * 1024**2):
        fail("InvalidMedia", "Vidéo locale absente, vide, trop grosse ou format refusé.",
             "Utiliser mp4/mov/mkv/webm/avi de 2–20 s, au plus 50 Mio.")
    return path.resolve()


def sampled_frames(path, fps, metadata, max_samples=40):
    import av
    import numpy as np
    # No playlist/remote protocols. Path is a file object, not a decoder URL.
    with path.open("rb") as source, av.open(source, options={"protocol_whitelist": "file,pipe"}) as container:
        if len(container.streams.video) != 1:
            fail("InvalidMedia", "Nombre de pistes vidéo incorrect.", "Fournir une seule piste vidéo.")
        stream = container.streams.video[0]
        stream.thread_type = "SLICE"
        stream.codec_context.thread_count = 1
        width, height = stream.width, stream.height
        if (min(width, height) <= 0 or max(width, height) > 1920 or min(width, height) > 1080
                or (stream.average_rate and float(stream.average_rate) > 60.01)):
            fail("InvalidMedia", "Résolution ou cadence hors limites.", "Exporter en 1080p maximum et <=60 fps.")
        first = previous = None
        next_sample = 0.0
        count = sampled = 0
        last_step = 0.0
        duration_hint = float(stream.duration * stream.time_base) if stream.duration is not None else None
        if duration_hint is not None and not 0 < duration_hint <= 20.05:
            fail("InvalidMedia", "Durée déclarée hors limites.", "Utiliser un clip de 2–20 s.")
        for frame in container.decode(stream):
            count += 1
            if count > 1200 or frame.width * frame.height > 1920 * 1080:
                fail("InvalidMedia", "Budget de décodage dépassé.", "Réencoder dans les limites documentées.")
            if frame.pts is None or frame.time_base is None:
                fail("InvalidMedia", "Horodatages absents.", "Réencoder le clip avec horodatages valides.")
            stamp = float(frame.pts * frame.time_base)
            first = stamp if first is None else first
            t = stamp - first
            if not math.isfinite(t) or t < 0 or t >= 20.05 or (previous is not None and t <= previous):
                fail("InvalidMedia", "Horodatages incohérents ou durée excessive.", "Réencoder la vidéo.")
            last_step = t - previous if previous is not None else 0.0
            previous = t
            if t + 1e-6 < next_sample or sampled >= max_samples:
                continue
            bgr = frame.to_ndarray(format="bgr24")
            rotation = frame.rotation
            if rotation % 90:
                fail("InvalidMedia", "Rotation arbitraire non prise en charge.", "Normaliser l'orientation.")
            if rotation:
                bgr = np.ascontiguousarray(np.rot90(bgr, round(rotation / 90)))
            sampled += 1
            next_sample = (math.floor(t * fps + 1e-6) + 1) / fps
            yield t, bgr
        if previous is None:
            fail("DecodeFailed", "Aucune frame décodable.", "Vérifier le codec ou fournir un autre clip.")
        # Trust neither the header alone nor a possibly long last inter-frame gap.
        tail = min(last_step, 1 / float(stream.average_rate or fps))
        duration = max(previous + tail, duration_hint or 0)
        if duration < 2 or duration > 20.05:
            fail("InvalidMedia", "Clip trop court ou trop long.", "Utiliser 2–20 s, idéalement 10–20 s.")
        if duration_hint and duration_hint - (previous + tail) > 1 / fps:
            fail("DecodeFailed", "Fin de vidéo manquante.", "Fournir un fichier complet.")
        metadata.update(duration_seconds=duration, decoded_frames=count,
                        source_width=width, source_height=height)


def run(request):
    config = request["config"]
    started = time.perf_counter()
    path = media_path(request["input"])
    data = manifest(request["manifest"])
    value = result(config, session_id=request["session_id"], generation=request["generation"])
    entries = data["models"]
    import cv2
    cv2.setNumThreads(config["threads"])
    locator = None
    if any(key != "gend" for key in config["detectors"]):
        directory = verify(request["cache"], "yunet", entries["yunet"])
        locator = FaceLocator(directory)
    engines, errors, observations = {}, {}, {}
    for key in config["detectors"]:
        observations[key] = []
        try:
            directory = verify(request["cache"], key, entries[key])
            if key == "gend":
                from .gend import GenDDetector
                engines[key] = GenDDetector(entries[key], directory, config["threads"])
            else:
                engines[key] = Detector(entries[key], directory, config["threads"])
        except VisioError as exc:
            errors[key] = exc
        except Exception as exc:
            errors[key] = VisioError("ModelUnavailable", f"Chargement {key} échoué ({type(exc).__name__}).",
                                     "Vérifier les dépendances verrouillées et les empreintes.")
    loaded = time.perf_counter()
    metadata = {}
    usable = sampled = 0
    infer_times = []
    reasons = {}
    tracking = None
    if request.get("tracking_file") and "gend" in engines:
        tracking = dict(schema_version="1.0", media_id=request["media_id"],
                        source="GenD/InsightFace det_10g 5838f7fe; five landmarks; 8 fps",
                        simulation=False, coordinate_space="normalized", frames=[])
    next_analysis = 0.0
    try:
        for stamp, bgr in sampled_frames(path, 8 if tracking is not None else config["sample_fps"],
                                         metadata, 160 if tracking is not None else 40):
            detections = None
            if tracking is not None:
                from .tracking import frame_result
                detections = engines["gend"].locator.detect(bgr)
                tracking["frames"].append(frame_result(stamp, bgr.shape, detections))
                if stamp + 1e-6 < next_analysis:
                    continue
                next_analysis = (math.floor(stamp * config["sample_fps"] + 1e-6) + 1) / config["sample_fps"]
            sampled += 1
            bbox, reason = locator.locate(bgr) if locator else (None, None)
            frame_usable = bbox is not None
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
            for key in config["detectors"]:
                score = None
                detector_reason = reason if key != "gend" else None
                if (bbox is not None or key == "gend") and key not in errors:
                    begin = time.perf_counter()
                    try:
                        if key == "gend":
                            score, detector_reason = (engines[key].predict_with_quality(bgr, detections)
                                                      if detections is not None else engines[key].predict_with_quality(bgr))
                            frame_usable |= score is not None
                            if detector_reason:
                                name = "gend:" + detector_reason
                                reasons[name] = reasons.get(name, 0) + 1
                        else:
                            score = engines[key].predict(bgr, bbox)
                        if score is not None and (not math.isfinite(score) or not 0 <= score <= 1):
                            fail("InvalidPrediction", "Score non fini ou hors intervalle.", "Vérifier les poids et labels.")
                    except Exception as exc:
                        errors[key] = exc if isinstance(exc, VisioError) else VisioError(
                            "InvalidPrediction", f"Inférence {key} échouée ({type(exc).__name__}).",
                            "Vérifier l'adaptateur ; ne pas interpréter comme absence de signal.")
                        score = None
                    infer_times.append(time.perf_counter() - begin)
                observations[key].append(dict(time_seconds=round(stamp, 6), score=score,
                                               reason=detector_reason or (errors[key].code if key in errors else None)))
            usable += frame_usable
    except VisioError:
        raise
    except Exception as exc:
        raise VisioError("DecodeFailed", f"Décodage échoué ({type(exc).__name__}).",
                         "Fournir un autre clip ou réencoder localement.") from exc
    for key in config["detectors"]:
        value["detectors"][key] = aggregate(observations[key], metadata["duration_seconds"],
                                             config, error=errors.get(key))
        value["detectors"][key].update(threats=entries[key]["threats"], revision=entries[key]["revision"])
    value.update(duration_seconds=metadata["duration_seconds"], sampled_frames=sampled,
                 coverage=usable / sampled if sampled else None,
                 quality_reasons=reasons, errors=[e.as_dict() for e in errors.values()])
    value["provenance"] = dict(models_manifest_sha256=canonical_hash(data),
                               versions={n: importlib.metadata.version(n) for n in
                                         ("av", "opencv-python-headless", "torch", "transformers", "onnxruntime")},
                               decoder="PyAV/libavcodec", weights={k: entries[k]["files"] for k in engines})
    if "gend" in engines:
        value["provenance"]["gend"] = engines["gend"].provenance()
        value["limitations"].append("GenD : échantillonnage POC 2 fps et agrégation locale ; pas une reproduction du benchmark publié.")
    value["timing"] = dict(model_load_seconds=loaded - started,
                           processing_seconds=time.perf_counter() - loaded,
                           inference_seconds=sum(infer_times),
                           peak_worker_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    if tracking is not None:
        Path(request["tracking_file"]).write_text(json.dumps(tracking, allow_nan=False))
        value["provenance"]["tracking"] = dict(sample_fps=8, frames=len(tracking["frames"]),
                                               coordinate_space="decoded oriented image", mirrored=False)
    return conclude(value)
