import { createNeuralFilter } from './neural-filter.js';
import { visibleLandmarks } from './landmarks.js';
import { createLiveScores } from './live-scores.js';
import { createScoreSmoother } from './score-smoothing.js';
import { startLiveCamera } from './live-camera.js';

export function createLiveComparison({ onVideoScore = () => {} } = {}) {
  const $ = id => document.getElementById(id);
  const output = $('filtered-canvas'), context = output.getContext('2d');
  const smoothers = { original: createScoreSmoother(), filtered: createScoreSmoother() };
  const reasons = { no_face: 'Aucun visage détecté', multiple_faces: 'Plusieurs visages · mesure indisponible',
    face_too_small: 'Rapprochez-vous de la caméra', exposure: 'Éclairage insuffisant ou excessif',
    invalid_landmarks: 'Visage non exploitable' };
  const scores = createLiveScores({
    onScores(data) {
      for (const key of ['original', 'filtered']) {
        const value = data?.[key];
        const smoothed = smoothers[key].sample(value?.score ?? null);
        setScore(`${key}-score`, smoothed);
        $(`${key}-score-note`).textContent = !value ? 'En attente d’une mesure'
          : value.score === null ? (reasons[value.reason] || 'Image non exploitable')
            : `Score lissé · brut : ${(value.score * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} / 100`;
        onVideoScore(key, smoothed, $(`${key}-score-note`).textContent);
      }
    },
    onStatus(message) { $('live-score-status').textContent = message; },
  });
  const portraits = {
    'brad-pitt': { label: 'Brad Pitt', author: '© Glenn Francis / PacificProDigital.com',
      source: 'https://commons.wikimedia.org/wiki/File:Brad_Pitt_2019_by_Glenn_Francis.jpg',
      license: 'CC BY-SA 4.0', licenseUrl: 'https://creativecommons.org/licenses/by-sa/4.0/' },
    'sam-altman': { label: 'Sam Altman', author: '© Steve Jennings / Getty Images pour TechCrunch · recadrage James Tamim',
      source: 'https://commons.wikimedia.org/wiki/File:Sam_Altman_CropEdit_James_Tamim.jpg',
      license: 'CC BY 2.0', licenseUrl: 'https://creativecommons.org/licenses/by/2.0/' },
    'emmanuel-macron': { label: 'Emmanuel Macron', author: 'Office of Vice President Kamala Harris · Wikimedia Commons',
      source: 'https://commons.wikimedia.org/wiki/File:Emmanuel_Macron.jpg',
      license: 'Domaine public (États-Unis)', licenseUrl: 'https://commons.wikimedia.org/wiki/File:Emmanuel_Macron.jpg#Licensing' },
    'nicolas-sarkozy': { label: 'Nicolas Sarkozy', author: '© Thierry Dauwe / European People’s Party · recadrage Off2riorob / Ellicrum',
      source: 'https://commons.wikimedia.org/wiki/File:Nicolas_Sarkozy_2010.jpg',
      license: 'CC BY 2.0', licenseUrl: 'https://creativecommons.org/licenses/by/2.0/' },
  };
  const portrait = () => portraits[$('filter-portrait').value];
  const updatePortrait = () => {
    const selected = portrait();
    $('filtered-name').textContent = `02 · ${external ? 'Flux externe' : selected.label}`;
    $('portrait-control').hidden = !!external; $('filter-credit').hidden = !!external;
    $('portrait-author').textContent = selected.author;
    $('portrait-source').href = selected.source;
    $('portrait-license').textContent = selected.license; $('portrait-license').href = selected.licenseUrl;
  };
  let original = null, latest = null, swapped = null, ready = false, failure = null;
  let external = null, externalFrame = null, stopExternal = () => {};
  const enabled = () => $('toggle-filter').getAttribute('aria-pressed') === 'true';
  const releaseSwap = () => { neural.cancel(); swapped?.bitmap.close(); swapped = null; };
  const neural = createNeuralFilter({
    onReady() { ready = true; failure = null; $('toggle-filter').disabled = false; paint(); },
    onResult(result) {
      if (!original || external || !enabled() || !latest?.frame.faces.length || result.portraitId !== $('filter-portrait').value) { result.bitmap.close(); return; }
      swapped?.bitmap.close(); swapped = result;
      if (result.applied) scores.submit(result.originalJpeg, result.filteredJpeg, result.frame.timestamp);
      else scores.reset();
      paint();
    },
    onError(message) {
      ready = false; failure = message; releaseSwap(); resetScores();
      $('toggle-filter').disabled = false; $('toggle-filter').textContent = 'Réessayer le face swap'; paint();
    },
  });
  const disconnect = () => {
    resetScores();
    external = null; stopExternal(); stopExternal = () => {};
    externalFrame?.bitmap?.close(); externalFrame = null;
    $('connect-external').hidden = false; $('disconnect-external').hidden = true; $('toggle-filter').hidden = false;
    $('filter-source-label').textContent = 'Face swap neuronal · GPU'; updatePortrait();
    paint();
  };
  const setScore = (id, value) => {
    $(id).textContent = value === null ? '—' : `${(value * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} / 100`;
    $(`${id}-rail`).style.width = `${value === null ? 0 : value * 100}%`;
    $(`${id}-rail`).style.backgroundColor = value === null ? '#adb5bd' : value >= .5 ? '#c97718' : '#258665';
  };
  const resetScores = () => { scores.reset(); };
  const clear = () => {
    scores.stop(); neural.stop(); releaseSwap(); latest?.bitmap.close(); latest = null;
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
        : !swapped ? 'Traitement de la première image…' : !applied ? 'Visage non détecté par le face swap' : `Face swap ${portrait().label} actif · ${Math.round(swapped.latencyMs)} ms · GPU`);
    if (external && rightBitmap && (frame.faces.length || face)) {
      scores.submit(bitmap, rightBitmap, Math.min(frame.timestamp, right.frame.timestamp));
    } else if (!external && !enabled() && frame.faces.length) {
      scores.submit(bitmap, bitmap, frame.timestamp);
    }
    if (!frame.faces.length && !face) resetScores();
  }
  $('toggle-filter').addEventListener('click', () => {
    resetScores();
    if (failure) {
      failure = null; ready = false;
      $('toggle-filter').setAttribute('aria-pressed', 'true'); neural.start();
    } else {
      $('toggle-filter').setAttribute('aria-pressed', String(!enabled())); releaseSwap();
    }
    $('toggle-filter').textContent = enabled() ? 'Désactiver le filtre' : 'Activer le filtre'; paint();
  });
  $('filter-portrait').addEventListener('change', () => {
    neural.selectPortrait($('filter-portrait').value);
    swapped?.bitmap.close(); swapped = null; resetScores();
    updatePortrait(); paint();
  });
  $('filtered-landmarks').addEventListener('change', paint);
  $('disconnect-external').addEventListener('click', disconnect);
  $('connect-external').addEventListener('click', () => {
    if (!original) return;
    disconnect();
    // Let an initial status check finish while the external source connects.
    if (ready) releaseSwap();
    const token = {}; external = token; updatePortrait();
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
    prepare() { neural.start(); scores.start(); },
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
