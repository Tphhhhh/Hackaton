"""Adapt actual detector pixels to the frontend's separate tracking contract."""
import math


def frame_result(stamp, shape, detections):
    height, width = shape[:2]
    boxes, landmarks = detections
    faces = []
    for index, box in enumerate(boxes[:10]):
        coords = [float(n) for n in box[:4]]
        if not all(math.isfinite(n) for n in coords):
            continue
        x1, y1, x2, y2 = coords
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        points = []
        if landmarks is not None:
            for point in landmarks[index]:
                x, y = map(float, point)
                # Never invent or clamp a landmark outside the decoded image.
                if math.isfinite(x) and math.isfinite(y) and 0 <= x <= width and 0 <= y <= height:
                    points.append(dict(x=x / width, y=y / height))
        faces.append(dict(id=f"observation-{stamp:.6f}-{index}",
                          box=dict(x=x1/width, y=y1/height, width=(x2-x1)/width, height=(y2-y1)/height),
                          landmarks=points))
    return dict(time_seconds=round(stamp, 6), faces=faces)
