// Exploratory measurements, independent of GenD and of the global score.
// Thresholds are conservative demo defaults, not calibrated deepfake classifiers.
const mean = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0;
const deviation = a => { const center = mean(a); return Math.sqrt(mean(a.map(v => (v - center) ** 2))); };
const difference = (a, b) => mean(a.map((v, i) => Math.abs(v - b[i])));
const row = (state, value, detail) => ({ state, value, detail });
export const SIGNAL_LABELS = {
  rhythm: 'Rythme & répétitions', activity: 'Clignements & mouvements',
  sharpness: 'Netteté visage / fond', lips: 'Cohérence voix / bouche', edges: 'Stabilité des contours',
};
export function unavailableSignals(reason = 'Activez la caméra pour mesurer.') {
  return Object.fromEntries(Object.keys(SIGNAL_LABELS).map(key => [key, row('unknown', 'Non mesuré', reason)]));
}

// Run on a small image inside the tracking worker, before any landmark overlay.
export function measurePixels(rgba, width, height, face) {
  const gray = new Float32Array(width * height);
  for (let i = 0; i < gray.length; i++) gray[i] = .299 * rgba[i * 4] + .587 * rgba[i * 4 + 1] + .114 * rgba[i * 4 + 2];
  const thumb = [];
  for (let y = 0; y < 6; y++) for (let x = 0; x < 8; x++) {
    let total = 0, n = 0;
    for (let yy = Math.floor(y * height / 6); yy < Math.floor((y + 1) * height / 6); yy++)
      for (let xx = Math.floor(x * width / 8); xx < Math.floor((x + 1) * width / 8); xx++) { total += gray[yy * width + xx]; n++; }
    thumb.push(total / n);
  }
  if (!face) return { thumb, face: null };
  const { box, landmarks: p } = face;
  const distance = (a, b) => Math.hypot((p[a].x - p[b].x) * width, (p[a].y - p[b].y) * height);
  if (p.length < 468 || box.width * width < 20 || box.height * height < 24 ||
      box.x < .01 || box.y < .01 || box.x + box.width > .99 || box.y + box.height > .99) return { thumb, face: null };
  const eyes = (distance(159, 145) / Math.max(1, distance(33, 133)) + distance(386, 374) / Math.max(1, distance(362, 263))) / 2;
  const mouth = distance(13, 14) / Math.max(1, distance(61, 291));
  const facial = [], background = [];
  for (let y = 1; y < height - 1; y++) for (let x = 1; x < width - 1; x++) {
    const nx = x / width, ny = y / height, i = y * width + x;
    const lap = 4 * gray[i] - gray[i - 1] - gray[i + 1] - gray[i - width] - gray[i + width];
    if (nx > box.x + box.width * .15 && nx < box.x + box.width * .85 && ny > box.y + box.height * .15 && ny < box.y + box.height * .85) facial.push(lap);
    else if (nx < box.x - .04 || nx > box.x + box.width + .04 || ny < box.y - .04 || ny > box.y + box.height + .04) background.push(lap);
  }
  // Resample around the actual face oval; translation/scale normalized by landmarks.
  const oval = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109];
  const ring = oval.map(index => {
    const x = Math.max(0, Math.min(width - 1, Math.round(p[index].x * width)));
    const y = Math.max(0, Math.min(height - 1, Math.round(p[index].y * height)));
    return gray[y * width + x];
  });
  const brightness = mean(ring);
  return { thumb, face: {
    eyes, mouth, x: box.x + box.width / 2, y: box.y + box.height / 2, size: box.width,
    roll: Math.atan2((p[263].y - p[33].y) * height, (p[263].x - p[33].x) * width),
    ring: ring.map(v => v - brightness), brightness,
    sharpness: facial.length > 50 && background.length > 100
      ? { face: deviation(facial) ** 2, background: deviation(background) ** 2 } : null,
  } };
}

function correlation(a, b) {
  const ma = mean(a), mb = mean(b);
  let ab = 0, aa = 0, bb = 0;
  for (let i = 0; i < a.length; i++) { const x = a[i] - ma, y = b[i] - mb; ab += x * y; aa += x * x; bb += y * y; }
  return aa * bb > 1e-10 ? ab / Math.sqrt(aa * bb) : 0;
}
function nearestAudio(audio, time) {
  // Audio history is bounded to 12 seconds. Never pair a current sample with a delayed frame.
  let best = null, delta = 100;
  for (const sample of audio) { const d = Math.abs(sample.time - time); if (d < delta) { delta = d; best = sample; } }
  return best;
}
export function lipCoherence(frames, audio, enabled, comparable = true) {
  if (!comparable) return row('unknown', 'Audio non associé', 'Le son du micro local ne peut pas être associé automatiquement au flux externe.');
  if (!enabled) return row('unknown', 'Microphone désactivé', 'Activez le microphone pour comparer son activité aux mouvements de bouche.');
  if (!frames.length || !nearestAudio(audio, frames.at(-1).time))
    return row('unknown', 'Audio indisponible', 'Aucun échantillon audio récent associé à cette image.');
  const paired = frames.filter(f => f.metrics.face).map(f => ({ time: f.time, mouth: f.metrics.face.mouth, audio: nearestAudio(audio, f.time)?.rms })).filter(f => Number.isFinite(f.audio));
  if (paired.length < 35 || paired.at(-1).time - paired[0].time < 4500) return row('unknown', 'Observation en cours', 'Il faut au moins 5 secondes de visage et de son synchronisés.');
  const levels = paired.map(f => f.audio), mouths = paired.map(f => f.mouth);
  const active = levels.filter(v => v > .012).length;
  if (active < 10) return row('unknown', 'Silence ou son trop faible', 'Aucune conclusion pendant le silence.');
  if (Math.max(...mouths) - Math.min(...mouths) < .025 && active / levels.length > .45)
    return row('flag', 'Son sans mouvement visible', 'Activité sonore et bouche peu mobile sur cette fenêtre. Bruit ou autre personne possibles.');
  if (deviation(levels) < .004 || deviation(mouths) < .012)
    return row('unknown', 'Activité peu variable', 'Pas assez de variations pour estimer une correspondance.');
  const candidates = [];
  for (let lag = -800; lag <= 800; lag += 100) {
    const pairs = paired.map(f => [f.mouth, nearestAudio(audio, f.time + lag)?.rms]).filter(p => Number.isFinite(p[1]));
    if (pairs.length >= paired.length * .8) candidates.push({ lag, score: correlation(pairs.map(p => p[0]), pairs.map(p => p[1])) });
  }
  const zero = candidates.find(v => v.lag === 0)?.score ?? 0;
  const best = candidates.sort((a, b) => b.score - a.score)[0];
  if (best?.score > .5 && Math.abs(best.lag) >= 300 && best.score - zero > .15)
    return row('flag', 'Décalage possible', `Écart d’activité estimé ≈ ${Math.abs(best.lag)} ms. Mesure grossière ; latence de capture et bruit possibles.`);
  if (zero > .35) return row('observed', 'Activités concordantes', 'Le son et la bouche varient ensemble. Les phonèmes et l’authenticité ne sont pas vérifiés.');
  return row('unknown', 'Correspondance incertaine', 'Le volume seul ne permet pas de conclure. Bruit, autre locuteur ou articulation possibles.');
}

export function createSignalHistory() {
  let frames = [], closedAt = null, blinks = [];
  function reset() { frames = []; closedAt = null; blinks = []; }
  return {
    reset,
    push(time, metrics) {
      if (!Number.isFinite(time) || !metrics?.thumb?.length) return false;
      const last = frames.at(-1);
      if (last && time <= last.time) return false;
      if (last && time - last.time > 700) reset();
      frames.push({ time, metrics });
      frames = frames.filter(f => time - f.time <= 10000).slice(-220);
      blinks = blinks.filter(t => time - t < 10000);
      const eyes = metrics.face?.eyes;
      if (!Number.isFinite(eyes)) closedAt = null;
      else if (eyes < .16 && closedAt === null) closedAt = time;
      else if (eyes > .22 && closedAt !== null) {
        if (time - closedAt >= 50 && time - closedAt <= 600) blinks.push(time);
        closedAt = null;
      }
      return true;
    },
    result(audio = [], enabled = false, comparable = true) {
      const result = unavailableSignals('Observation en cours.');
      if (!frames.length) return result;
      const last = frames.at(-1), start = frames[0].time, duration = (last.time - start) / 1000;
      const fps = duration ? (frames.length - 1) / duration : 0;
      const recent = frames.filter(f => last.time - f.time <= 4000);
      if (duration >= 3 && frames.length >= 12) {
        const diffs = recent.slice(1).map((f, i) => difference(f.metrics.thumb, recent[i].metrics.thumb));
        const frozen = diffs.length >= 10 && diffs.every(d => d < .65);
        let loop = false;
        // Compare a moving sequence, not a single repeated pose or a frozen image.
        const tail = frames.slice(-6);
        if (!frozen && tail.length === 6 && mean(tail.slice(1).map((f, i) => difference(f.metrics.thumb, tail[i].metrics.thumb))) > 2) {
          for (let i = 0; i < frames.length - 12; i++) {
            const period = tail[0].time - frames[i].time;
            if (period < 1500) continue;
            if (tail.every((f, j) => Math.abs(f.time - frames[i + j].time - period) < 150 && difference(f.metrics.thumb, frames[i + j].metrics.thumb) < 1.5)) { loop = true; break; }
          }
        }
        result.rhythm = row(frozen || loop ? 'flag' : 'observed', frozen ? 'Image presque figée' : loop ? 'Séquence répétée possible' : 'Images renouvelées',
          `${fps.toFixed(1)} images analysées/s sur ${duration.toFixed(1)} s. ${frozen ? 'Immobilité et gel réseau possibles.' : loop ? 'Répétition courte, à confirmer sur une durée plus longue.' : 'Une boucle de plus de 10 s peut passer inaperçue.'}`);
      }
      if (!last.metrics.face) {
        for (const key of ['activity', 'sharpness', 'lips', 'edges']) result[key] = row('unknown', 'Visage non exploitable', 'Un visage entier, assez grand et suivi est nécessaire.');
        return result;
      }
      // Face gaps break temporal measurements, even when whole-frame rhythm continues.
      let segmentStart = recent.length - 1;
      while (segmentStart > 0 && recent[segmentStart - 1].metrics.face) segmentStart--;
      const faces = recent.slice(segmentStart).map(f => f.metrics.face);
      const faceDuration = (last.time - recent[segmentStart].time) / 1000;
      if (faceDuration >= 3 && faces.length >= 12) {
        const movement = mean(faces.slice(1).map((f, i) => Math.hypot(f.x - faces[i].x, f.y - faces[i].y) / Math.max(.1, f.size)));
        result.activity = row('observed', `${blinks.length} clignement${blinks.length > 1 ? 's' : ''} observé${blinks.length > 1 ? 's' : ''}`,
          `Sur ${Math.min(duration, 10).toFixed(0)} s · ${movement < .006 ? 'peu de mouvements' : 'mouvements visibles'}. ${fps < 8 ? 'Cadence basse : des clignements peuvent être manqués. ' : ''}L’immobilité n’est pas une preuve de manipulation.`);
        const residuals = [];
        for (let i = 1; i < faces.length; i++) {
          const a = faces[i - 1], b = faces[i];
          if (Math.hypot(a.x - b.x, a.y - b.y) / b.size < .025 && Math.abs(a.roll - b.roll) < .06 && Math.abs(a.size - b.size) / b.size < .06 && Math.abs(a.brightness - b.brightness) < 12)
            residuals.push(difference(a.ring, b.ring));
        }
        if (residuals.length >= 12) {
          const unstable = residuals.filter(v => v > 18).length / residuals.length > .3;
          result.edges = row(unstable ? 'flag' : 'observed', unstable ? 'Variations de contours' : 'Contours peu variables',
            'Comparaison du contour après compensation de position, taille et luminosité moyenne. Compression, suivi et mouvement peuvent expliquer les variations.');
        } else result.edges = row('unknown', 'Mouvement trop important', 'Il faut quelques secondes de visage relativement stable pour comparer les contours.');
      }
      const sharp = last.metrics.face.sharpness;
      if (sharp && sharp.face > 2 && sharp.background > 2) {
        const ratio = sharp.face / sharp.background;
        result.sharpness = row('observed', `Rapport ${ratio.toFixed(1)}×`,
          `Visage ${ratio > 2 ? 'plus net que le fond' : ratio < .5 ? 'moins net que le fond' : 'de netteté comparable au fond'}. Texture et flou portrait influencent cette mesure ; aucun verdict.`);
      } else result.sharpness = row('unknown', 'Texture insuffisante', 'Le visage ou le fond manque de détails pour comparer la netteté.');
      const gap = frames.findLastIndex(f => !f.metrics.face);
      const lipFrames = frames.slice(gap + 1);
      result.lips = fps >= 5 ? lipCoherence(lipFrames, audio, enabled, comparable)
        : row('unknown', 'Cadence insuffisante', 'Au moins 5 images analysées/s sont nécessaires pour comparer la bouche au son.');
      return result;
    },
  };
}
