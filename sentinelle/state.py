"""Bind genuine server-side GenD results to an interview, without storing frames."""
import copy
import json
import math
from pathlib import Path
import statistics
import threading
import time
import uuid


class Interviews:
    def __init__(self, clock=time.monotonic, output=Path('out/video_scores.json')):
        self.clock, self.output = clock, Path(output)
        self.lock = threading.RLock()
        self.sessions = {}
        self.tokens = {}

    def open(self, app_id, source='original'):
        if source not in ('original', 'filtered'):
            raise ValueError('Flux vidéo inconnu.')
        with self.lock:
            previous = self.sessions.get(app_id)
            if previous:
                self.tokens.pop(previous['token'], None)
            token = str(uuid.uuid4())
            self.sessions[app_id] = {'token': token, 'source': source, 'samples': [],
                'generation': None, 'frame': -1, 'updated': None, 'model': None,
                'revision': None, 'active': True}
            self.tokens[token] = app_id
            return token

    def close(self, token):
        with self.lock:
            app_id = self.tokens.pop(token, None)
            if app_id:
                self.sessions[app_id]['active'] = False
                self.sessions[app_id]['samples'] = []

    def app(self, token):
        with self.lock:
            return self.tokens.get(token)

    def record(self, token, result, started):
        with self.lock:
            app_id = self.tokens.get(token)
            if not app_id or self.clock() - started >= 3:
                return
            s = self.sessions[app_id]
            if result.get('model') != 'gend_pe' or result.get('simulation') is not False:
                return
            # A Visio reset rotates this ID. Old binding tokens are invalidated by the wrapper.
            generation = result.get('session_id')
            if generation != s['generation']:
                s['samples'] = []
                s['generation'], s['frame'] = generation, -1
            frame = result.get('frame_id', -1)
            if frame <= s['frame']:
                return
            s['frame'] = frame
            if s['updated'] is not None and started - s['updated'] >= 3:
                s['samples'] = []
            value = result.get(s['source'], {}).get('score')
            s.update(updated=started, model=result['model'], revision=result.get('revision'))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                s['samples'] = []
                return
            s['samples'] = [(t, v) for t, v in s['samples'] if started - t <= 10]
            s['samples'] = (s['samples'] + [(started, value)])[-5:]

    def view(self, app_id):
        with self.lock:
            s = self.sessions.get(app_id)
            if not s:
                return {'status': 'not_started', 'score': None, 'samples': 0, 'raw': None}
            fresh = s['active'] and s['updated'] is not None and self.clock() - s['updated'] < 3
            samples = [(t,v) for t,v in s['samples'] if self.clock()-t <= 10] if fresh else []
            status = 'ready' if len(samples) >= 3 else 'collecting' if samples else 'waiting' if s['active'] else 'stopped'
            return {'status': status, 'score': statistics.median(v for _,v in samples) if len(samples)>=3 else None,
                'raw': samples[-1][1] if samples else None, 'samples': len(samples),
                'source': s['source'], 'model': s['model'], 'revision': s['revision'],
                'simulation': False, 'transformed_demo': s['source']=='filtered'}

    def export(self, app_id):
        with self.lock:
            value = self.view(app_id)
            if value['status'] != 'ready' or value['source'] != 'original':
                raise ValueError('Il faut au moins trois mesures récentes du flux original pour conserver un bilan.')
            data = json.loads(self.output.read_text()) if self.output.exists() else {}
            data[app_id] = {'classifier': value['score']}
            self.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.output.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=2, allow_nan=False))
            temporary.replace(self.output)
            record = dict(value, captured_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            provenance = self.output.with_name('video_provenance.json')
            records = json.loads(provenance.read_text()) if provenance.exists() else {}
            records[app_id] = record
            temporary = provenance.with_suffix('.tmp')
            temporary.write_text(json.dumps(records, indent=2, allow_nan=False))
            temporary.replace(provenance)
            return copy.deepcopy(record)
