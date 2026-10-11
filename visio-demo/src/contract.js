import validate from './generated/result.js';

export const MAX_JSON_BYTES = 1024 * 1024;
export const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
export const conclusions = Object.freeze({
  verify: 'indice à vérifier',
  no_signal: 'aucun indice détecté',
  indeterminate: 'analyse insuffisante',
});
export function conclusionLabel(value) {
  return Object.hasOwn(conclusions, value) ? conclusions[value] : conclusions.indeterminate;
}
export function parseResult(input) {
  try {
    const text = typeof input === 'string' ? input : JSON.stringify(input);
    if (typeof text !== 'string') return { ok: false, errors: ['Résultat JSON absent.'] };
    if (new TextEncoder().encode(text).byteLength > MAX_JSON_BYTES) {
      return { ok: false, errors: ['Le JSON dépasse la limite de 1 Mo.'] };
    }
    const data = JSON.parse(text);
    if (!validate(data)) {
      const errors = validate.errors.filter(e => e.keyword !== 'if');
      return { ok: false, errors: errors.slice(0, 8).map(e => {
        const field = e.params.missingProperty ?? e.params.additionalProperty;
        return `${e.instancePath || '/'}${field ? ` → ${field}` : ''} : ${e.message}`;
      }).concat(errors.length > 8 ? [`… ${errors.length - 8} autre(s) erreur(s).`] : []) };
    }
    return { ok: true, data };
  } catch {
    return { ok: false, errors: ['JSON illisible ou structure trop complexe. Sélectionnez un fichier JSON valide.'] };
  }
}
export function videoFileError(file) {
  if (!file.size) return 'Ce fichier vidéo est vide.';
  if (file.size > MAX_VIDEO_BYTES) return 'La vidéo dépasse la limite de 50 Mo.';
  if (!/\.(mp4|webm)$/i.test(file.name) || (file.type && !['video/mp4', 'video/webm'].includes(file.type))) {
    return 'Format non pris en charge. Choisissez une vidéo MP4 ou WebM.';
  }
  return null;
}
export function durationError(duration) {
  return Number.isFinite(duration) && duration >= 2 && duration <= 20
    ? null : 'La vidéo doit durer de 2 à 20 secondes incluses.';
}
