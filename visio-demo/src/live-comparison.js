import { createNeuralFilter } from './neural-filter.js';
import { visibleLandmarks } from './landmarks.js';
import { createDemoScores } from './demo-scores.js';
import { startLiveCamera } from './live-camera.js';

export function createLiveComparison() {
  const $ = id => document.getElementById(id);
  const output = $('filtered-canvas'), context = output.getContext('2d');
  const scores = createDemoScores();
  let original = null, latest = null, swapped = null, ready = false, failure = null;
  let external = null, externalFrame = null, stopExternal = () => {};
  const enabled = () => $('toggle-filter').getAttribute('aria-pressed') === 'true';
  const releaseSwap = () => { neural.cancel(); swapped?.bitmap.close(); swapped = null; };
  const neural = createNeuralFilter({
    onReady() { ready = true; failure = null; $('toggle-filter').disabled = false; paint(); },
    onResult(result) {
      if (!original || external || !enabled() || !latest?.frame.faces.length) { result.bitmap.close(); return; }
      swapped?.bitmap.close(); swapped = result; paint();
    },
    onError(message) {
      ready = false; failure = message; releaseSwap();
      $('toggle-filter').disabled = false; $('toggle-filter').textContent = 'Réessayer le face swap'; paint();
    },
  });
  const disconnect = () => {
    external = null; stopExternal(); stopExternal = () => {};
    externalFrame?.bitmap?.close(); externalFrame = null;
    $('connect-external').hidden = false; $('disconnect-external').hidden = true; $('toggle-filter').hidden = false;
    $('filter-source-label').textContent = 'Face swap neuronal · GPU';
    paint();
  };
  const setScore = (id, value) => {
    $(id).textContent = value === null ? '—' : `${value} %`;
    $(`${id}-rail`).style.width = `${value ?? 0}%`;
  };
  const resetScores = () => { scores.reset(); setScore('original-score', null); setScore('filtered-score', null); };
  const clear = () => {
    neural.stop(); releaseSwap(); latest?.bitmap.close(); latest = null;
    disconnect(); failure = null; ready = false; original = null;
    context.clearRect(0, 0, output.width, output.height); output.hidden = true;
    output.dataset.filterApplied = 'false'; output.dataset.pointCount = '0';
    $('filtered-placeholder').hidden = false; $('filter-status').textContent = 'En attente de la caméra';
    $('filtered-tracking').textContent = 'Points masqués · visage dégagé';
    $('toggle-filter').disabled = true; $('toggle-filter').textContent = enabled() ? 'Désactiver le filtre' : 'Activer le filtre';
    $('connect-external').disabled = true; $('external-alert').hidden = true; resetScores();
  };
  function paint() {
    if (!latest || !original) return;
    if (swapped && performance.now() - swapped.receivedAt > 2000) { swapped.bitmap.close(); swapped = null; }
    const { bitmap, frame } = latest;
    if (original.width !== bitmap.width || original.height !== bitmap.height) { original.width = bitmap.width; original.height = bitmap.height; }
    original.getContext('2d').drawImage(bitmap, 0, 0); original.hidden = false;
    const right = external ? externalFrame : enabled() && swapped ? swapped : latest;
    const rightBitmap = right?.bitmap;
    output.hidden = !rightBitmap; $('filtered-placeholder').hidden = !!rightBitmap;
    output.classList.toggle('external-stream', !!external);
    let applied = false, face = null;
    if (rightBitmap) {
      if (output.width !== rightBitmap.width || output.height !== rightBitmap.height) { output.width = rightBitmap.width; output.height = rightBitmap.height; }
      context.drawImage(rightBitmap, 0, 0);
      face = right.frame.faces[0];
      applied = !external && enabled() && right === swapped && swapped.applied;
      const points = face ? visibleLandmarks(face.landmarks, $('filtered-landmarks').value) : [];
      context.fillStyle = '#c8ffe5';
      for (const point of points) { context.beginPath(); context.arc(point.x * output.width, point.y * output.height, 1.2, 0, Math.PI * 2); context.fill(); }
      output.dataset.pointCount = String(points.length);
      $('filtered-tracking').textContent = !face ? 'Aucun visage détecté' : !points.length ? 'Points masqués · visage dégagé' : `${points.length} points · ${external ? 'détectés sur le flux externe' : 'repères du visage original'}`;
    }
    output.dataset.filterApplied = String(applied);
    $('filter-status').textContent = external ? (rightBitmap ? 'Flux externe · transformation fournie par la fenêtre partagée' : 'Connexion au flux externe…')
      : failure || (!enabled() ? 'Filtre désactivé · flux original' : !ready ? 'Connexion au face swap neuronal…' : !frame.faces.length ? 'Placez votre visage face à la caméra'
        : !swapped ? 'Traitement de la première image…' : !applied ? 'Visage non détecté par le face swap' : `Face swap Brad Pitt actif · ${Math.round(swapped.latencyMs)} ms · GPU`);
    const values = scores.sample(frame.timestamp, { facePresent: !!frame.faces.length, filteredFacePresent: !!face, filterApplied: external ? true : applied });
    setScore('original-score', values.original);
    setScore('filtered-score', !external && enabled() && !applied ? null : values.filtered);
  }
  $('toggle-filter').addEventListener('click', () => {
    if (failure) {
      failure = null; ready = false;
      $('toggle-filter').setAttribute('aria-pressed', 'true'); neural.start();
    } else {
      $('toggle-filter').setAttribute('aria-pressed', String(!enabled())); releaseSwap();
    }
    $('toggle-filter').textContent = enabled() ? 'Désactiver le filtre' : 'Activer le filtre'; paint();
  });
  $('filtered-landmarks').addEventListener('change', paint);
  $('disconnect-external').addEventListener('click', disconnect);
  $('connect-external').addEventListener('click', () => {
    if (!original) return;
    disconnect();
    // Let an initial status check finish while the external source connects.
    if (ready) releaseSwap();
    const token = {}; external = token;
    $('external-alert').hidden = true; $('connect-external').hidden = true; $('disconnect-external').hidden = false;
    $('toggle-filter').hidden = true; $('filter-source-label').textContent = 'Flux externe · Deep-Live-Cam / OBS';
    const video = document.createElement('video'); video.muted = true; video.playsInline = true;
    stopExternal = startLiveCamera({ video,
      acquireMedia: () => {
        if (!navigator.mediaDevices.getDisplayMedia) throw new Error('Le partage de fenêtre nécessite Chrome ou Edge sur ordinateur.');
        return navigator.mediaDevices.getDisplayMedia({ video: { frameRate: { ideal: 20, max: 30 } }, audio: false });
      },
      onState: message => { if (external === token) $('filter-status').textContent = message; },
      onFrame: frame => {
        if (external !== token) { frame.bitmap?.close(); return; }
        externalFrame?.bitmap?.close(); externalFrame = frame.bitmap ? { frame, bitmap: frame.bitmap } : null; paint();
      },
      onError: () => {
        if (external !== token) return;
        disconnect(); $('external-alert').textContent = 'Partage arrêté ou indisponible. Retour au moteur local. Vous pouvez partager à nouveau une fenêtre.'; $('external-alert').hidden = false;
      },
    });
    paint();
  });
  return {
    start(canvas) { clear(); original = canvas; $('connect-external').disabled = false; $('filter-status').textContent = 'Connexion à la caméra…'; },
    prepare() { neural.start(); },
    render(frame) {
      if (!frame.bitmap) {
        releaseSwap(); latest?.bitmap.close(); latest = null;
        if (original) original.getContext('2d').clearRect(0, 0, original.width, original.height);
        context.clearRect(0, 0, output.width, output.height); output.dataset.filterApplied = 'false';
        $('filter-status').textContent = 'Caméra momentanément interrompue…'; resetScores(); return;
      }
      latest?.bitmap.close(); latest = { frame, bitmap: frame.bitmap };
      if (!frame.faces.length && ready) releaseSwap();
      if (!external && enabled() && frame.faces.length) neural.submit(frame);
      paint();
    },
    clear,
  };
}
