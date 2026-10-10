// One request in flight; intermediate frames are dropped, never queued or saved.
export function createNeuralFilter({ onReady, onResult, onError }) {
  let generation = 0, ready = false, request = null, lastSent = -Infinity;
  const cancel = () => { generation++; request?.abort(); request = null; };
  const stop = () => { cancel(); ready = false; };
  async function start() {
    stop();
    const token = generation;
    request = new AbortController();
    try {
      const response = await fetch('/api/live/status', { signal: AbortSignal.any([request.signal, AbortSignal.timeout(8000)]) });
      if (!response.ok || !response.headers.get('Content-Type')?.includes('application/json')) throw new Error('Face swap indisponible. Lancez le serveur local avec --live-swap.');
      const status = await response.json();
      if (token !== generation) return;
      if (!status.ready) throw new Error(status.error);
      ready = true; lastSent = -Infinity; onReady(status);
    } catch (error) {
      if (token === generation) onError(error.message || 'Face swap indisponible. Lancez le serveur local avec --live-swap.');
    } finally { if (token === generation) request = null; }
  }
  async function submit(frame) {
    if (!ready || request || performance.now() - lastSent < 40 || document.hidden) return;
    const token = generation, controller = new AbortController();
    request = controller; lastSent = performance.now();
    const started = lastSent;
    try {
      const scale = Math.min(1, 640 / Math.max(frame.bitmap.width, frame.bitmap.height));
      const canvas = new OffscreenCanvas(Math.round(frame.bitmap.width * scale), Math.round(frame.bitmap.height * scale));
      canvas.getContext('2d').drawImage(frame.bitmap, 0, 0, canvas.width, canvas.height);
      const jpeg = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.92 });
      if (token !== generation) return;
      const response = await fetch('/api/live/swap', {
        method: 'POST', headers: { 'Content-Type': 'image/jpeg', 'X-Visio-Request': '1' }, body: jpeg,
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
      });
      if (response.status === 409) return; // Busy GPU: skip this frame, do not accumulate work.
      if (!response.ok) throw new Error((await response.json()).error || 'Le face swap est indisponible.');
      const bitmap = await createImageBitmap(await response.blob());
      if (token !== generation) { bitmap.close(); return; }
      onResult({ bitmap, frame, receivedAt: performance.now(), applied: response.headers.get('X-Visio-Swapped') === '1',
        inferenceMs: Number(response.headers.get('X-Visio-Inference-Ms')), latencyMs: performance.now() - started });
    } catch (error) {
      if (token === generation) { ready = false; onError(error.name === 'TimeoutError' ? 'Le face swap ne répond plus. Réessayez.' : error.message || 'Connexion au face swap interrompue.'); }
    } finally { if (token === generation) request = null; }
  }
  return { start, submit, cancel, stop };
}
