// Real GenD PE measurements. One pair in flight, no queue, no filter-state input.
export function createLiveScores({ onScores, onStatus }) {
  let running = false, ready = false, generation = 0, lifecycle = 0, request = null;
  let session = crypto.randomUUID(), sequence = 0, lastSent = -Infinity, expiry;
  const maxAge = 3000;
  const reset = () => {
    generation++; request?.abort(); request = null; clearTimeout(expiry);
    session = crypto.randomUUID(); lastSent = -Infinity;
    onScores(null);
  };
  const stop = () => { lifecycle++; running = ready = false; reset(); onStatus('GenD PE · en attente de la caméra'); };
  async function start() {
    stop(); running = true;
    const token = lifecycle;
    onStatus('Connexion à GenD PE…');
    try {
      const response = await fetch('/api/live/score/status', { signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error('GenD PE live indisponible.');
      const data = await response.json();
      if (token !== lifecycle || !running) return;
      if (!data.ready || data.model !== 'gend_pe' || data.simulation !== false) throw new Error(data.error || 'GenD PE live indisponible.');
      ready = true; onStatus('GenD PE prêt · environ une mesure par seconde');
    } catch (error) {
      if (token === lifecycle && running) onStatus(error.message || 'GenD PE live indisponible.');
    }
  }
  const encode = source => {
    if (source instanceof Blob) return Promise.resolve(source);
    const scale = Math.min(1, 640 / Math.max(source.width, source.height));
    const canvas = new OffscreenCanvas(Math.round(source.width * scale), Math.round(source.height * scale));
    // Copy immediately: camera ImageBitmaps may be closed on the next frame.
    canvas.getContext('2d').drawImage(source, 0, 0, canvas.width, canvas.height);
    return canvas.convertToBlob({ type: 'image/jpeg', quality: .92 });
  };
  const valid = value => value && (value.score === null
    ? typeof value.reason === 'string'
    : Number.isFinite(value.score) && value.score >= 0 && value.score <= 1 && value.reason === null);
  async function submit(original, filtered, capturedAt) {
    const now = performance.now();
    if (!running || !ready || request || document.hidden || now - lastSent < 1000 || now - capturedAt > maxAge) return;
    const token = generation, controller = new AbortController(), id = ++sequence, sid = session;
    request = controller; lastSent = now;
    try {
      const [left, right] = await Promise.all([encode(original), encode(filtered)]);
      if (token !== generation) return;
      const response = await fetch('/api/live/score', {
        method: 'POST', body: new Blob([left, right]),
        headers: { 'Content-Type': 'application/octet-stream', 'X-Visio-Request': '1',
          'X-Visio-Original-Length': String(left.size), 'X-Visio-Session': sid, 'X-Visio-Frame': String(id) },
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]),
      });
      if (token !== generation) return;
      if (response.status === 409) { onStatus('GenD PE occupé · prochaine image attendue'); return; }
      const data = await response.json();
      if (token !== generation) return;
      if (!response.ok) throw new Error(data.error || 'Analyse GenD PE indisponible.');
      if (data.model !== 'gend_pe' || data.simulation !== false || data.session_id !== sid || data.frame_id !== id
          || !valid(data.original) || !valid(data.filtered)) throw new Error('Résultat GenD PE incompatible avec cette capture.');
      const age = performance.now() - capturedAt;
      if (age >= maxAge) throw new Error('Mesure trop ancienne · attente d’une nouvelle image');
      clearTimeout(expiry);
      onScores(data);
      onStatus(`GenD PE · mesure reçue en ${Math.round(age)} ms · actualisation ~1/s`);
      expiry = setTimeout(() => {
        onScores(null); onStatus('Mesure expirée · attente d’une nouvelle image');
      }, maxAge - age);
    } catch (error) {
      if (token === generation && running) {
        clearTimeout(expiry); onScores(null);
        onStatus(error.name === 'TimeoutError' ? 'GenD PE ne répond pas · nouvelle tentative…' : error.message || 'GenD PE indisponible.');
      }
    } finally { if (token === generation) request = null; }
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) reset(); });
  window.addEventListener('pagehide', stop);
  return { start, stop, reset, submit };
}
