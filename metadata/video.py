"""Optional genuine GenD classifier scores, keyed by candidate ID.

Example: {"A2UG64": {"classifier": 0.8}}. No lipsync, lighting, challenge or
motion detector is implemented. The live UI keeps video and metadata separate.
The batch CLI retains its historical classifier weight (at most five points).
"""
import json
import math
from pathlib import Path
from .checks import Signal


def load_video_scores(path):
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding='utf-8'))


def video_signals(scores):
    value=(scores or {}).get('classifier')
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0.5<=value<=1:
        return []
    return [Signal('V5_CLASSIFIER',round(5*value),f'Indice visuel de manipulation GenD : {value:.2f}, non calibré.', 'T1656')]
