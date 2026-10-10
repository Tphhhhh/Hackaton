import { createSignalHistory, unavailableSignals } from './video-signals.js';

// Bounded histories only. No recording, upload or score fusion.
export function createSignalLayers({ onResults }) {
  const histories = { original: createSignalHistory(), filtered: createSignalHistory() };
  const expires = {}, updated = { original: -Infinity, filtered: -Infinity };
  let audio = [], audioEnabled = false, comparable = true;
  let worker = null, ready = false, busy = false, epoch = 0, lastSubmitted = -Infinity, watchdog, retryAfter = 0;
  const publish = key => onResults(key, histories[key].result(audio, audioEnabled, key === 'original' || comparable));
  function stopWorker() {
    epoch++; worker?.terminate(); worker = null; ready = busy = false; lastSubmitted = -Infinity;
    clearTimeout(watchdog);
  }
  function reset(key) {
    const keys = key ? [key] : ['original', 'filtered'];
    if (keys.includes('filtered')) { stopWorker(); comparable = true; retryAfter = 0; }
    for (const k of keys) {
      clearTimeout(expires[k]); histories[k].reset(); updated[k] = -Infinity;
      onResults(k, unavailableSignals());
    }
    if (!key) audio = [];
  }
  function accept(key, frame) {
    if (document.hidden || performance.now() - frame.timestamp > 1800) return;
    if (!histories[key].push(frame.timestamp, frame.metrics)) return;
    clearTimeout(expires[key]);
    expires[key] = setTimeout(() => {
      histories[key].reset(); updated[key] = -Infinity;
      onResults(key, unavailableSignals('Mesures expirées · en attente de nouvelles images.'));
    }, Math.max(1, 2000 - (performance.now() - frame.timestamp)));
    if (frame.timestamp - updated[key] >= 400) { updated[key] = frame.timestamp; publish(key); }
  }
  function startWorker() {
    const own = epoch;
    worker = new Worker(new URL('./live-tracker.worker.js', import.meta.url), { type: 'module' });
    const fail = () => {
      if (own !== epoch) return;
      stopWorker(); histories.filtered.reset(); clearTimeout(expires.filtered);
      retryAfter = performance.now() + 5000;
      onResults('filtered', unavailableSignals('Suivi du flux transformé indisponible.'));
    };
    worker.onerror = fail;
    worker.onmessage = ({ data }) => {
      if (own !== epoch) { data.bitmap?.close(); return; }
      clearTimeout(watchdog);
      if (data.type === 'ready') ready = true;
      else if (data.type === 'result') { busy = false; accept('filtered', data); data.bitmap?.close(); }
      else if (data.type === 'error') fail();
    };
    watchdog = setTimeout(fail, 20000);
    worker.postMessage({ type: 'init', baseUrl: new URL(`${import.meta.env.BASE_URL}live-assets/`, location.href).href });
  }
  async function frame(key, value, { retrack = false, audioComparable = true } = {}) {
    if (key === 'filtered') comparable = audioComparable;
    if (!retrack) { accept(key, value); return; }
    if (document.hidden || !value.bitmap || performance.now() - value.timestamp > 1800) return;
    if (!worker && performance.now() < retryAfter) return;
    if (!worker) startWorker();
    if (!ready || busy || value.timestamp - lastSubmitted < 100) return;
    busy = true; lastSubmitted = value.timestamp;
    const own = epoch;
    try {
      // Clone now: the renderer owns and may close the source on its next frame.
      const bitmap = await createImageBitmap(value.bitmap);
      if (own !== epoch) { bitmap.close(); return; }
      watchdog = setTimeout(() => {
        reset('filtered'); onResults('filtered', unavailableSignals('Suivi trop lent · nouvelle tentative.'));
      }, 5000);
      worker.postMessage({ type: 'frame', bitmap, timestamp: value.timestamp }, [bitmap]);
    } catch {
      if (own === epoch) { reset('filtered'); onResults('filtered', unavailableSignals('Image transformée non exploitable.')); }
    }
  }
  function microphone(enabled) {
    if (audioEnabled === enabled) return;
    audioEnabled = enabled; audio = [];
    for (const key of ['original', 'filtered']) publish(key);
  }
  document.addEventListener('visibilitychange', () => { if (document.hidden) reset(); });
  window.addEventListener('pagehide', () => { reset(); audioEnabled = false; });
  return {
    frame, reset, microphone,
    audio(time, rms) {
      if (!audioEnabled || document.hidden || !Number.isFinite(rms)) return;
      audio.push({ time, rms }); audio = audio.filter(a => time - a.time <= 12000).slice(-250);
    },
  };
}
