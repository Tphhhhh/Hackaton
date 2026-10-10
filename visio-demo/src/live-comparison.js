import { createFaceFilter } from './face-filter.js';
import { createDemoScores } from './demo-scores.js';
import { startLiveCamera } from './live-camera.js';

export function createLiveComparison() {
  const $ = id => document.getElementById(id);
  const output = $('filtered-canvas'), context = output.getContext('2d');
  const scores = createDemoScores();
  let filter = null, original = null, latest = null, applied = false;
  let failure = null;
  let external = null, externalFrame = null, stopExternal = () => {};
  const disconnect = () => {
    external = null; stopExternal(); stopExternal = () => {};
    externalFrame?.bitmap?.close(); externalFrame = null;
    $('connect-external').hidden = false; $('disconnect-external').hidden = true;
    $('toggle-filter').hidden = false;
    $('filter-source-label').textContent = 'Filtre intégré · masque 2D';
    paint();
  };
  const enabled = () => $('toggle-filter').getAttribute('aria-pressed') === 'true';
  const setScore = (id, value) => {
    $(id).textContent = value === null ? '—' : `${value} %`;
    $(`${id}-rail`).style.width = `${value ?? 0}%`;
  };
  const resetScores = () => { scores.reset(); setScore('original-score', null); setScore('filtered-score', null); };
  const clear = () => {
    latest?.bitmap.close(); latest = null; disconnect(); filter?.close(); filter = null; failure = null; applied = false;
    original = null; context.clearRect(0, 0, output.width, output.height); output.hidden = true;
    $('filtered-placeholder').hidden = false; $('filter-status').textContent = 'En attente de la caméra';
    $('filtered-tracking').textContent = 'Suivi partagé avec le flux original';
    $('toggle-filter').disabled = true; $('connect-external').disabled = true; $('external-alert').hidden = true; resetScores();
  };
  function paint() {
    if (!latest || !original) return;
    const { bitmap, frame } = latest;
    if (original.width !== bitmap.width || original.height !== bitmap.height) { original.width = bitmap.width; original.height = bitmap.height; }
    original.getContext('2d').drawImage(bitmap, 0, 0);
    original.hidden = false;
    const right = external ? externalFrame : latest;
    const rightBitmap = right?.bitmap;
    output.hidden = !rightBitmap; $('filtered-placeholder').hidden = !!rightBitmap;
    if (!rightBitmap) {
      const values = scores.sample(frame.timestamp, { facePresent: !!frame.faces.length, filteredFacePresent: false, filterApplied: false });
      setScore('original-score', values.original); setScore('filtered-score', null); return;
    }
    if (output.width !== rightBitmap.width || output.height !== rightBitmap.height) { output.width = rightBitmap.width; output.height = rightBitmap.height; }
    context.drawImage(rightBitmap, 0, 0);
    const face = right.frame.faces[0]; applied = false;
    if (!external && face && filter && enabled()) {
      try { filter.draw(context, face.landmarks, output.width, output.height); applied = true; }
      catch (error) { failure = error.message; filter.close(); filter = null; $('toggle-filter').disabled = true; }
    }
    const showPoints = $('toggle-tracking').getAttribute('aria-pressed') === 'true';
    if (face && showPoints) {
      context.fillStyle = '#c8ffe5';
      for (const point of face.landmarks) { context.beginPath(); context.arc(point.x * output.width, point.y * output.height, 1.2, 0, Math.PI * 2); context.fill(); }
    }
    $('filter-status').textContent = external ? 'Flux externe · transformation fournie par la fenêtre partagée' : failure || (!face ? 'Placez votre visage face à la caméra' : !filter ? 'Préparation du filtre…' : !enabled() ? 'Filtre désactivé · flux original' : 'Filtre Brad Pitt actif');
    $('filtered-tracking').textContent = face ? `${face.landmarks.length} points · ${external ? 'détectés sur le flux externe' : 'géométrie du visage original'}` : 'Aucun visage détecté';
    $('filtered-canvas').dataset.filterApplied = String(applied);
    output.classList.toggle('external-stream', !!external);
    const values = scores.sample(frame.timestamp, { facePresent: !!frame.faces.length, filteredFacePresent: !!face, filterApplied: external ? true : applied });
    setScore('original-score', values.original);
    setScore('filtered-score', !external && (failure || (enabled() && !filter)) ? null : values.filtered);
  }
  $('toggle-filter').addEventListener('click', () => {
    $('toggle-filter').setAttribute('aria-pressed', String(!enabled()));
    $('toggle-filter').textContent = enabled() ? 'Désactiver le filtre' : 'Activer le filtre';
    paint();
  });
  $('toggle-tracking').addEventListener('click', () => queueMicrotask(paint));
  $('disconnect-external').addEventListener('click', disconnect);
  $('connect-external').addEventListener('click', () => {
    if (!original) return;
    disconnect();
    const token = {}; external = token;
    $('external-alert').hidden = true;
    $('connect-external').hidden = true; $('disconnect-external').hidden = false;
    $('toggle-filter').hidden = true;
    $('filter-source-label').textContent = 'Flux externe · Deep-Live-Cam / OBS';
    const video = document.createElement('video'); video.muted = true; video.playsInline = true;
    stopExternal = startLiveCamera({ video, filter: false,
      acquireMedia: () => {
        if (!navigator.mediaDevices.getDisplayMedia) throw new Error('Le partage de fenêtre nécessite Chrome ou Edge sur ordinateur.');
        return navigator.mediaDevices.getDisplayMedia({ video: { frameRate: { ideal: 20, max: 30 } }, audio: false });
      },
      onState: message => { if (external === token) $('filter-status').textContent = message; },
      onFrame: frame => {
        if (external !== token) { frame.bitmap?.close(); return; }
        externalFrame?.bitmap?.close(); externalFrame = frame.bitmap ? { frame, bitmap: frame.bitmap } : null;
        paint();
      },
      onError: () => {
        if (external !== token) return;
        disconnect(); $('external-alert').textContent = 'Partage arrêté ou indisponible. Le filtre intégré a repris. Vous pouvez partager à nouveau la fenêtre d’aperçu de Deep-Live-Cam.'; $('external-alert').hidden = false;
      },
    });
    paint();
  });
  return {
    start(canvas) { clear(); original = canvas; $('connect-external').disabled = false; $('filter-status').textContent = 'Connexion à la caméra…'; },
    prepare(data) {
      if (data.filterError) { failure = data.filterError; $('filter-status').textContent = failure; return; }
      try {
        filter = createFaceFilter({ image: data.referenceImage, points: data.referencePoints, triangles: data.triangles, oval: data.oval });
        $('toggle-filter').disabled = false;
      } catch (error) { failure = error.message; $('filter-status').textContent = failure; }
    },
    render(frame) {
      if (!frame.bitmap) { latest?.bitmap.close(); latest = null; if (original) original.getContext('2d').clearRect(0, 0, original.width, original.height); context.clearRect(0, 0, output.width, output.height); resetScores(); return; }
      latest?.bitmap.close(); latest = { frame, bitmap: frame.bitmap }; paint();
    },
    clear,
  };
}
