import tracking from './generated/tracking.js';
import metadata from './generated/metadata.js';
const validators = { tracking, metadata };
export const MAX_SUPPLEMENTAL_BYTES = 2 * 1024 * 1024;
export const MAX_FRAME_AGE_SECONDS = 0.25;

export function parseSupplemental(input, kind, media) {
  try {
    if (!media) return { ok: false, errors: ['Chargez une vidéo avant de recevoir ces données.'] };
    const text = typeof input === 'string' ? input : JSON.stringify(input);
    if (new TextEncoder().encode(text).byteLength > MAX_SUPPLEMENTAL_BYTES) throw new Error('Taille');
    const data = JSON.parse(text);
    const validate = validators[kind];
    if (!validate || !validate(data)) return { ok: false, errors: (validate?.errors || []).slice(0, 6).map(e => `${e.instancePath || '/'} : ${e.message}`) };
    if (data.media_id !== media.id) return { ok: false, errors: ['Ces données ne correspondent pas à la référence de la vidéo chargée.'] };
    if (kind === 'tracking') {
      let previousTime = -1;
      for (const frame of data.frames) {
        if (frame.time_seconds <= previousTime || frame.time_seconds > media.duration_seconds) {
          return { ok: false, errors: ['Les instants doivent être strictement croissants et compris dans la durée de la vidéo.'] };
        }
        previousTime = frame.time_seconds;
        if (new Set(frame.faces.map(f => f.id)).size !== frame.faces.length) return { ok: false, errors: ['Identifiants de visage dupliqués dans une image.'] };
        for (const { box } of frame.faces) {
          if (box.x + box.width > 1 + 1e-9 || box.y + box.height > 1 + 1e-9) return { ok: false, errors: ['Un cadre de visage sort de l’image.'] };
        }
      }
    } else {
      if (new Set(data.checks.map(c => c.id)).size !== data.checks.length) return { ok: false, errors: ['Identifiants de contrôle dupliqués.'] };
      if (['pending', 'failed'].includes(data.status) && data.checks.length) return { ok: false, errors: ['Un état en attente ou en échec ne peut pas contenir de contrôles terminés.'] };
      if (['failed', 'partial'].includes(data.status) && !data.errors.length) return { ok: false, errors: ['Une analyse partielle ou en échec doit indiquer une erreur.'] };
    }
    return { ok: true, data };
  } catch {
    return { ok: false, errors: ['JSON illisible ou trop volumineux (2 Mo maximum).'] };
  }
}

export function frameAt(frames, time) {
  // Never extrapolate into the future or preserve an old face across a sampling gap.
  let low = 0; let high = frames.length - 1; let index = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (frames[mid].time_seconds <= time) { index = mid; low = mid + 1; } else high = mid - 1;
  }
  if (index < 0 || time - frames[index].time_seconds > MAX_FRAME_AGE_SECONDS) return null;
  return frames[index];
}

export function containedRect(width, height, videoWidth, videoHeight) {
  const scale = Math.min(width / videoWidth, height / videoHeight);
  const w = videoWidth * scale; const h = videoHeight * scale;
  return { x: (width - w) / 2, y: (height - h) / 2, width: w, height: h };
}
