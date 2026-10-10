import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/inter-tight/latin-700.css';
import './style.css';
import { createLiveComparison } from './live-comparison.js';
import { startLiveCamera } from './live-camera.js';
import { createSessionSignals } from './session-signals.js';
import { createAnalysisConsole } from './analysis-console.js';
import { visibleLandmarks } from './landmarks.js';
import { connectLocalEngine } from './local-engine.js';
import { icon, hydrateIcons } from './icons.js';
import { parseSupplemental, frameAt, containedRect, MAX_SUPPLEMENTAL_BYTES } from './supplemental.js';
import { parseResult, conclusionLabel, videoFileError, durationError, MAX_JSON_BYTES } from './contract.js';
import verify from '../reference/examples/verify.json';
import noSignal from '../reference/examples/no_signal.json';
import indeterminate from '../reference/examples/indeterminate.json';
import partial from '../reference/examples/partial.json';
import failed from '../reference/examples/failed.json';
import cancelled from '../reference/examples/cancelled.json';

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
const pct = n => n === null ? 'Non disponible' : `${Math.round(n * 100)} %`;
const number = n => n === null ? 'Non disponible' : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n);
const statuses = { completed: 'Terminée', partial: 'Partielle', failed: 'Échec', cancelled: 'Annulée' };
const detectorStatuses = { ok: 'Disponible', insufficient: 'Données insuffisantes', error: 'Erreur' };
const baselineLimits = ['Scores exploratoires non calibrés : ce ne sont pas des probabilités de fraude.', 'Ces résultats ne prouvent ni l’identité ni la présence en direct.', 'Les intervalles non échantillonnés ne sont pas analysés.'];
let importSequence = 0;
let videoSequence = 0;
let videoUrl = null;
let disposeVideo = () => {};
let media = null;
let selectedFile = null;
let analysis = null;
let analysisMediaId = null;
let tracking = null;
let metadata = null;
let supplementalSequence = { tracking: 0, metadata: 0 };
let lastOverlayKey = '';
let liveFrame = null;
hydrateIcons();
let analysisConsole;
const signals = createSessionSignals({ onMetadata: data => analysisConsole?.metadata(data) });
analysisConsole = createAnalysisConsole();
const comparison = createLiveComparison({ onVideoScore: analysisConsole.video });
if (new URLSearchParams(location.search).get('mode') === 'clip') document.body.classList.remove('compare-mode');


function alertAt(id, messages = []) {
  const box = $(id);
  box.replaceChildren(...messages.map(m => el('p', '', m)));
  box.hidden = messages.length === 0;
}
function clearResult() {
  importSequence++;
  alertAt('json-alert');
  $('json-file').value = '';
  $('json-info').textContent = 'Le résultat peut être consulté sans vidéo.';
  renderEmpty();
}
function renderEmpty() {
  analysis = null; analysisMediaId = null;
  $('clear-result').hidden = true;
  document.querySelectorAll('#examples button').forEach(b => b.setAttribute('aria-pressed', 'false'));
  const empty = el('div', 'empty-state');
  empty.append(el('h3', '', 'Les résultats viendront ici.'), el('p', 'hint', 'Choisissez un extrait puis lancez son analyse avec GenD, ou importez un résultat.'));
  const gauges = el('div', 'empty-gauges');
  gauges.append(gauge('Indices de manipulation', null), gauge('Couverture de l’analyse', null));
  empty.append(gauges, el('p', 'small-note', 'Scores exploratoires, non calibrés. Calcul effectué par le moteur local.'));
  $('result').replaceChildren(empty);
  updateCrosscheck();
}
function gauge(label, value, tone = '') {
  const block = el('div', `gauge ${tone}`);
  const heading = el('div', 'gauge-heading');
  heading.append(el('span', '', label), el('strong', '', value === null ? '—' : `${Math.round(value * 100)} / 100`));
  const rail = el('div', 'gauge-rail');
  if (value !== null) {
    rail.setAttribute('role', 'meter'); rail.setAttribute('aria-label', label);
    rail.setAttribute('aria-valuemin', '0'); rail.setAttribute('aria-valuemax', '100'); rail.setAttribute('aria-valuenow', String(value * 100));
    const fill = el('span', 'gauge-fill'); fill.style.width = `${value * 100}%`; rail.append(fill);
  }
  const ends = el('div', 'gauge-ends'); ends.append(el('span', '', '0'), el('span', '', '100'));
  block.append(heading, rail, ends); return block;
}
function metric(label, value) {
  const block = el('div', 'metric');
  block.append(el('dt', '', label), el('dd', '', value));
  return block;
}
function errorCard(error) {
  const card = el('div', 'error-card');
  if (error === null) { card.append(el('p', '', 'Erreur sans détail dans le JSON.')); return card; }
  card.append(el('strong', '', error.code || 'Erreur sans code'), el('p', '', error.message), el('p', 'error-action', `Action indiquée par le moteur : ${error.action}`), el('p', 'small-note', `Relance possible : ${error.retryable ? 'oui' : 'non'} · Documentation : ${error.docs || 'non fournie'}`));
  return card;
}
function detectorCard(name, data) {
  const card = el('article', 'detector-card');
  const header = el('div', 'detector-header');
  const title = el('div');
  title.append(el('h4', '', name === 'gend_pe' ? 'GenD PE' : name), el('span', 'small-note', `Révision ${data.revision || 'non fournie'} · ${detectorStatuses[data.status]}`));
  header.append(title, el('span', `badge ${data.conclusion}`, conclusionLabel(data.conclusion)));
  const metrics = el('dl', 'detector-metrics');
  metrics.append(metric('Score / 100', data.score === null ? 'Non disponible' : number(data.score * 100)), metric('Couverture', pct(data.coverage)), metric('Part signalée', pct(data.flagged_fraction)), metric('Intervalle max.', `${number(data.longest_gap_seconds)} s`));
  card.append(header, gauge('Indices de manipulation', data.score, data.conclusion), metrics);
  card.append(el('p', 'small-note', 'Score brut fourni par ce détecteur, pas une probabilité de deepfake.'));
  if (data.threats.length) card.append(el('p', 'small-note', `Phénomènes couverts : ${data.threats.join(', ')}`));
  if (data.error) card.append(errorCard(data.error));
  const details = el('details', 'observations');
  details.append(el('summary', '', `Observations échantillonnées (${data.observations.length})`));
  if (!data.observations.length) details.append(el('p', 'hint', 'Aucune observation disponible.'));
  else {
    const table = el('table');
    const thead = el('thead'); const tr = el('tr');
    for (const label of ['Temps', 'Score brut / 1', 'Motif']) { const th = el('th', '', label); th.scope = 'col'; tr.append(th); }
    thead.append(tr);
    const tbody = el('tbody');
    data.observations.forEach(o => { const row = el('tr'); row.append(el('td', '', `${number(o.time_seconds)} s`), el('td', '', number(o.score)), el('td', '', o.reason ?? 'Non renseigné')); tbody.append(row); });
    table.append(thead, tbody); details.append(table);
  }
  card.append(details);
  return card;
}
function renderResult(data, source) {
  analysis = data;
  const root = $('result'); root.replaceChildren(); $('clear-result').hidden = false;
  const head = el('div', 'result-source');
  head.append(el('span', `badge ${data.simulation ? 'simulation' : 'imported'}`, data.simulation ? 'simulation · exemple fictif' : 'résultat importé'), el('span', 'small-note', `État : ${statuses[data.status]}`));
  const conclusion = data.conclusion ?? 'indeterminate';
  const summary = el('div', `conclusion ${conclusion}`);
  summary.append(el('p', 'eyebrow', 'ANALYSE VIDÉO'), el('h3', '', conclusionLabel(conclusion)), el('p', '', data.simulation ? 'Cette simulation ne décrit pas la vidéo sélectionnée.' : 'Résultat fourni par le moteur, à interpréter avec ses limites.'));
  const metrics = el('dl', 'summary-metrics');
  metrics.append(metric('Couverture', pct(data.coverage)), metric('Images échantillonnées', String(data.sampled_frames)), metric('Durée analysée', data.duration_seconds === null ? 'Non disponible' : `${number(data.duration_seconds)} s`));
  root.append(head, summary, metrics, el('p', 'association-note', analysisMediaId && analysisMediaId === media?.id && !data.simulation
    ? 'Résultat associé à cet extrait par l’intégration. La présence en direct n’est pas établie.'
    : 'Le lien entre ce JSON et la vidéo n’est pas vérifié. La présence en direct n’est pas établie.'));
  const sectionTitle = el('div', 'subheading'); sectionTitle.append(el('h3', '', 'Par détecteur'), el('span', 'count', String(Object.keys(data.detectors).length))); root.append(sectionTitle);
  if (!Object.keys(data.detectors).length) root.append(el('p', 'hint', 'Aucun résultat de détecteur disponible.'));
  Object.entries(data.detectors).forEach(([name, detector]) => root.append(detectorCard(name, detector)));
  const errors = el('section', 'result-section'); errors.append(el('h3', '', `Erreurs (${data.errors.length})`));
  data.errors.forEach(error => errors.append(errorCard(error)));
  if (!data.errors.length) errors.append(el('p', 'hint', 'Aucune erreur rapportée dans ce JSON.'));
  root.append(errors);
  const limits = el('section', 'limits result-section'); limits.append(el('h3', '', 'Limites à garder en tête'));
  const list = el('ul'); [...new Set([...baselineLimits, ...data.limitations])].forEach(t => list.append(el('li', '', t))); limits.append(list); root.append(limits);
  const trace = el('details', 'trace'); trace.append(el('summary', '', 'Référence du résultat'));
  trace.append(el('p', 'small-note', `Source : ${source}`), el('p', 'small-note', `Session : ${data.session_id} · Génération : ${data.generation} · Contrat : ${data.schema_version}`));
  root.append(trace);
  updateCrosscheck();
}
// Public integration boundary: accepts an object or JSON string, never a video.
// Every source uses the same schema validation and safe text-only rendering.
function receiveResult(input, source = 'Moteur intégré', binding = {}) {
  importSequence++;
  $('json-file').value = '';
  const parsed = parseResult(input);
  renderEmpty();
  if (!binding || typeof binding !== 'object' || Array.isArray(binding) || (binding.mediaId !== undefined && binding.mediaId !== media?.id)) {
    parsed.ok = false; parsed.errors = ['Ce résultat appartient à une autre vidéo.'];
  }
  if (!parsed.ok) {
    alertAt('json-alert', ['Résultat refusé : contrat JSON invalide.', ...parsed.errors]);
    $('json-info').textContent = 'Aucun résultat chargé.';
    return parsed;
  }
  alertAt('json-alert');
  $('json-info').textContent = source;
  analysisMediaId = binding.mediaId ?? null;
  renderResult(parsed.data, source);
  return { ok: true };
}
window.visioDemo = Object.freeze({
  receiveResult: (input, binding) => receiveResult(input, 'Moteur intégré', binding),
  receiveTracking: input => receiveSupplemental(input, 'tracking'),
  receiveMetadata: input => receiveSupplemental(input, 'metadata'),
  getContext: () => ({ media: media ? { ...media } : null, analysis: analysis ? { session_id: analysis.session_id, generation: analysis.generation, media_id: analysisMediaId } : null }),
  clearResult,
  clearTracking: () => clearSupplemental('tracking'),
  clearMetadata: () => clearSupplemental('metadata'),
});

const examples = [ ['verify', 'Indice à vérifier', verify], ['no_signal', 'Aucun indice', noSignal], ['indeterminate', 'Insuffisante', indeterminate], ['partial', 'Partielle', partial], ['failed', 'Échec', failed], ['cancelled', 'Annulée', cancelled] ];
for (const [id, label, value] of examples) {
  const button = el('button', 'example-button', label); button.dataset.example = id; button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-label', `Simulation : ${label}`);
  button.addEventListener('click', () => { enterClipWorkspace(); const outcome = receiveResult({ ...value, simulation: true }, `Simulation · ${label}`); if (outcome.ok) button.setAttribute('aria-pressed', 'true'); $('sources-dialog').close(); selectTab('visio'); });
  $('examples').append(button);
}
$('clear-result').addEventListener('click', clearResult);
$('json-file').addEventListener('change', async (event) => {
  const file = event.target.files[0]; if (!file) return;
  const sequence = ++importSequence;
  renderEmpty(); alertAt('json-alert'); $('json-info').textContent = 'Lecture du JSON…';
  const fail = message => { if (sequence !== importSequence) return; alertAt('json-alert', [message]); $('json-info').textContent = 'Aucun résultat chargé.'; event.target.value = ''; };
  if (!/\.json$/i.test(file.name)) return fail('Choisissez un fichier portant l’extension .json.');
  if (!file.size) return fail('Ce fichier JSON est vide.');
  if (file.size > MAX_JSON_BYTES) return fail('Le JSON dépasse la limite de 1 Mo.');
  try { const text = await file.text(); if (sequence === importSequence) receiveResult(text, `Fichier · ${file.name}`); }
  catch { fail('Impossible de lire ce fichier JSON.'); }
});

function selectTab(name) {
  for (const tab of ['visio', 'metadata']) {
    $(`tab-${tab}`).setAttribute('aria-selected', String(tab === name));
    $(`tab-${tab}`).tabIndex = tab === name ? 0 : -1;
    $(`panel-${tab}`).hidden = tab !== name;
  }
}
for (const name of ['visio', 'metadata']) {
  $(`tab-${name}`).addEventListener('click', () => selectTab(name));
  $(`tab-${name}`).addEventListener('keydown', event => {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault(); const next = event.key === 'Home' ? 'visio' : event.key === 'End' ? 'metadata' : name === 'visio' ? 'metadata' : 'visio';
      selectTab(next); $(`tab-${next}`).focus();
    }
  });
}
$('open-sources').addEventListener('click', () => $('sources-dialog').showModal());
$('close-sources').addEventListener('click', () => $('sources-dialog').close());
for (const id of ['choose-video', 'stage-replace', 'source-video']) $(id).addEventListener('click', () => { $('sources-dialog').close(); $('video-file').click(); });
function enterClipWorkspace() {
  if (media?.kind === 'live') clearVideo();
  document.body.classList.remove('compare-mode');
}
for (const id of ['import-result', 'source-result']) $(id).addEventListener('click', () => { enterClipWorkspace(); $('sources-dialog').close(); selectTab('visio'); $('json-file').click(); });
for (const id of ['import-metadata', 'source-metadata']) $(id).addEventListener('click', () => { enterClipWorkspace(); $('sources-dialog').close(); selectTab('metadata'); $('metadata-file').click(); });
$('source-tracking').addEventListener('click', () => $('tracking-file').click());

function clearSupplemental(kind) {
  supplementalSequence[kind]++;
  if (kind === 'tracking') { tracking = null; lastOverlayKey = ''; drawTracking(); }
  else { metadata = null; renderMetadata(); }
  alertAt(`${kind}-alert`);
  $(`${kind}-file`).value = '';
}
function receiveSupplemental(input, kind) {
  clearSupplemental(kind);
  const parsed = parseSupplemental(input, kind, media);
  if (!parsed.ok) {
    alertAt(`${kind}-alert`, parsed.errors);
    if (kind === 'tracking') $('tracking-status').textContent = 'Coordonnées refusées · consulter les sources';
    return parsed;
  }
  if (kind === 'tracking') { tracking = parsed.data; drawTracking(); }
  else { metadata = parsed.data; renderMetadata(); }
  return { ok: true };
}
for (const kind of ['tracking', 'metadata']) {
  $(`${kind}-file`).addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    clearSupplemental(kind); const sequence = supplementalSequence[kind];
    const fail = message => { if (sequence === supplementalSequence[kind]) alertAt(`${kind}-alert`, [message]); };
    if (!/\.json$/i.test(file.name) || !file.size || file.size > MAX_SUPPLEMENTAL_BYTES) return fail('Choisissez un JSON non vide de 2 Mo maximum.');
    try {
      const text = await file.text(); if (sequence !== supplementalSequence[kind]) return;
      const outcome = receiveSupplemental(text, kind);
      if (outcome.ok && kind === 'tracking') $('sources-dialog').close();
    } catch { fail('Impossible de lire ce fichier JSON.'); }
  });
}
function renderMetadata() {
  const root = $('metadata-result'); root.replaceChildren();
  if (!metadata) {
    const empty = el('div', 'metadata-empty');
    empty.append(el('span', 'badge neutral', 'En attente d’intégration'), el('h3', '', 'Les informations du fichier.'), el('p', 'hint', 'Retrouvez ici les vérifications transmises par le module métadonnées.'));
    const slots = el('div', 'metadata-slots');
    for (const label of ['Source & provenance', 'Informations du fichier', 'Cohérence avec la visio']) { const row = el('div'); row.append(el('span', '', label), el('span', '', 'En attente')); slots.append(row); }
    empty.append(slots, el('p', 'small-note', 'Aucune métadonnée extraite ici. Le module externe fournit les contrôles et leurs résultats.')); root.append(empty);
  } else {
    const header = el('div', 'result-source');
    header.append(el('span', `badge ${metadata.simulation ? 'simulation' : 'imported'}`, metadata.simulation ? 'simulation · métadonnées fictives' : 'résultat importé'), el('span', 'small-note', ({ pending: 'En attente', completed: 'Terminée', partial: 'Partielle', failed: 'Échec' })[metadata.status]));
    root.append(header, el('h3', '', 'Contrôles de métadonnées'), el('p', 'small-note', `Source : ${metadata.source}`));
    const labels = { consistent: 'Cohérence déclarée', mismatch: 'Écart à vérifier', indeterminate: 'Analyse insuffisante' };
    for (const check of metadata.checks) {
      const card = el('article', 'metadata-check'); const head = el('div', 'section-heading');
      head.append(el('h4', '', check.label), el('span', `badge ${check.status}`, labels[check.status]));
      const values = el('dl', 'metadata-values'); values.append(metric('Référence visio', check.video_value ?? 'Non disponible'), metric('Métadonnées', check.metadata_value ?? 'Non disponible'));
      card.append(head, values, el('p', 'hint', check.detail)); root.append(card);
    }
    if (!metadata.checks.length) root.append(el('p', 'hint', 'Aucun contrôle disponible.'));
    metadata.errors.forEach(error => root.append(el('p', 'error-card', error)));
    const limits = el('div', 'limits'); limits.append(el('h3', '', 'Limites du module'));
    const list = el('ul'); metadata.limitations.forEach(text => list.append(el('li', '', text)));
    if (!metadata.limitations.length) list.append(el('li', '', 'Aucune limite fournie par le module.')); limits.append(list); root.append(limits);
    const clear = el('button', 'text-button', 'Effacer les métadonnées'); clear.addEventListener('click', () => clearSupplemental('metadata')); root.append(clear);
  }
  $('metadata-dot').classList.toggle('received', !!metadata);
  updateCrosscheck();
}
function updateCrosscheck() {
  $('video-source-dot').classList.toggle('received', !!analysis);
  $('meta-source-dot').classList.toggle('received', !!metadata);
  let message = 'En attente des deux sources pour le même extrait.';
  if (analysis?.simulation || metadata?.simulation) message = 'Simulation : aucun rapprochement avec la vidéo réelle.';
  else if (analysis && metadata) {
    if (analysisMediaId !== media?.id) message = 'Résultat visio non associé à cet extrait par l’intégration.';
    else if (analysis.session_id !== metadata.session_id) message = 'Sessions différentes : rapprochement indisponible.';
    else if (['failed', 'cancelled'].includes(analysis.status) || ['pending', 'failed'].includes(metadata.status)) message = 'Sources associées, mais analyse insuffisante ou en attente.';
    else message = 'Même extrait et session déclarés · contrôles disponibles dans les deux onglets.';
  }
  $('crosscheck-status').textContent = message;
}
function drawTracking(time) {
  const live = media?.kind === 'live';
  const video = $('video-stage').querySelector('video');
  const overlay = $('face-overlay');
  const mode = live ? $('original-landmarks').value : 'full';
  const enabled = live ? mode !== 'none' : $('toggle-tracking').getAttribute('aria-pressed') === 'true';
  const frame = live ? liveFrame : tracking && video && !video.seeking ? frameAt(tracking.frames, time ?? video.currentTime) : null;
  let status = !enabled ? 'Affichage des coordonnées masqué' : live ? (!frame ? 'Démarrage du suivi…' : !frame.faces.length ? 'Aucun visage détecté' : 'Visage suivi en direct') : !tracking ? 'En attente de coordonnées du moteur' : !frame ? 'Pas de coordonnées à cet instant' : !frame.faces.length ? 'Aucun visage détecté à cet instant' : `${frame.faces.length} visage(s) · ${tracking.source}`;
  if ($('tracking-status').textContent !== status) $('tracking-status').textContent = status;
  $('overlay-chip').textContent = live ? (!enabled ? 'Suivi masqué' : !frame ? 'Suivi en préparation' : frame.faces.length ? 'Suivi en direct' : 'Aucun visage détecté') : !tracking ? 'Coordonnées en attente' : !enabled ? 'Suivi masqué' : !frame ? 'Instant non couvert' : !frame.faces.length ? 'Aucun visage détecté' : 'Coordonnées du moteur';
  const count = enabled && frame ? frame.faces.reduce((n, face) => n + visibleLandmarks(face.landmarks, mode).length, 0) : null;
  $('tracking-count').textContent = count === null ? '— point' : `${count} point(s)`;
  if (!enabled || !frame || !video || !media) { overlay.replaceChildren(); overlay.toggleAttribute('hidden', true); lastOverlayKey = ''; return; }
  const { width, height } = $('video-stage').getBoundingClientRect();
  if (!width || !height) return;
  const key = `${frame.time_seconds}/${width}/${height}`;
  if (key === lastOverlayKey) return;
  lastOverlayKey = key; overlay.replaceChildren(); overlay.toggleAttribute('hidden', false);
  overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
  const rect = containedRect(width, height, video.videoWidth, video.videoHeight);
  const svg = (tag, attributes) => { const node = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value); return node; };
  for (const face of frame.faces) {
    const group = svg('g', { 'data-face-id': face.id });
    group.append(svg('rect', { x: rect.x + face.box.x * rect.width, y: rect.y + face.box.y * rect.height, width: face.box.width * rect.width, height: face.box.height * rect.height, rx: 6, class: 'face-box' }));
    for (const point of visibleLandmarks(face.landmarks, mode)) group.append(svg('circle', { cx: rect.x + point.x * rect.width, cy: rect.y + point.y * rect.height, r: live ? 1.2 : 3, class: 'landmark' }));
    overlay.append(group);
  }
}
$('toggle-tracking').addEventListener('click', () => {
  $('toggle-tracking').setAttribute('aria-pressed', String($('toggle-tracking').getAttribute('aria-pressed') !== 'true'));
  lastOverlayKey = ''; drawTracking();
});
$('original-landmarks').addEventListener('change', () => { lastOverlayKey = ''; drawTracking(); });
new ResizeObserver(() => { lastOverlayKey = ''; drawTracking(); }).observe($('stage-shell'));
const clock = seconds => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
function setControl(id, name, label) { $(id).innerHTML = icon(name); $(id).setAttribute('aria-label', label); $(id).title = label; }
function updatePlayback() {
  if (media?.kind === 'live') { $('session-state').textContent = 'Caméra en direct'; return; }
  const video = $('video-stage').querySelector('video');
  const time = media && video ? video.currentTime : 0;
  $('current-time').textContent = clock(time); $('timeline').value = time;
  setControl('play-video', video && !video.paused ? 'pause' : 'play', video && !video.paused ? 'Mettre en pause' : 'Lire la vidéo');
  setControl('mute-video', video && !video.muted ? 'volume' : 'volume-off', video && !video.muted ? 'Couper le son' : 'Activer le son');
  $('session-state').textContent = !media ? 'Extrait en attente' : video?.ended ? 'Lecture terminée' : video?.paused ? 'Prête à lire' : 'Lecture en cours';
}
$('play-video').addEventListener('click', async () => { const video = $('video-stage').querySelector('video'); if (!video || !media) return; try { if (video.paused) await video.play(); else video.pause(); } catch { alertAt('video-alert', ['La lecture n’a pas pu démarrer. Essayez un autre fichier.']); } });
$('mute-video').addEventListener('click', () => { const video = $('video-stage').querySelector('video'); if (video) { video.muted = !video.muted; updatePlayback(); } });
$('restart-video').addEventListener('click', () => { const video = $('video-stage').querySelector('video'); if (video) video.currentTime = 0; });
$('timeline').addEventListener('input', () => { const video = $('video-stage').querySelector('video'); if (video && media) video.currentTime = Number($('timeline').value); });
$('fullscreen-video').addEventListener('click', async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await $('stage-shell').requestFullscreen(); } catch { alertAt('video-alert', ['Le plein écran n’est pas disponible dans ce navigateur.']); } });
function clearVideo() {
  videoSequence++;
  liveFrame = null;
  signals.stop();
  comparison.clear();
  setLiveMode(false);
  disposeVideo(); disposeVideo = () => {};
  if (videoUrl) { URL.revokeObjectURL(videoUrl); videoUrl = null; }
  media = null; selectedFile = null;
  $('video-stage').replaceChildren(); $('video-stage').hidden = true;
  $('stage-empty').hidden = false;
  for (const id of ['stage-top', 'stage-name', 'stage-replace', 'clear-video']) $(id).hidden = true;
  for (const id of ['play-video', 'mute-video', 'restart-video', 'fullscreen-video', 'timeline']) $(id).disabled = true;
  $('video-info').textContent = ''; $('video-file').value = ''; alertAt('video-alert');
  $('total-time').textContent = '00:00'; $('stage-filename').textContent = '';
  $('media-reference').textContent = 'Chargez une vidéo pour obtenir sa référence d’intégration.';
  clearSupplemental('tracking'); clearSupplemental('metadata'); clearResult(); updatePlayback();
  window.dispatchEvent(new CustomEvent('visio:mediachange', { detail: { media: null } }));
}
$('clear-video').addEventListener('click', clearVideo);
$('video-file').addEventListener('change', event => {
  const file = event.target.files[0]; if (!file) return;
  clearVideo();
  document.body.classList.remove('compare-mode');
  const error = videoFileError(file); if (error) return alertAt('video-alert', [error]);
  const sequence = videoSequence;
  const video = el('video'); video.preload = 'metadata'; video.playsInline = true; video.muted = true;
  video.setAttribute('aria-label', 'Prévisualisation de la vidéo locale');
  videoUrl = URL.createObjectURL(file);
  const fail = message => { if (sequence !== videoSequence) return; clearVideo(); signals.unavailable(message); alertAt('video-alert', [message]); };
  const timer = setTimeout(() => fail('Impossible de lire la durée de cette vidéo. Essayez un autre fichier.'), 10000);
  let frameCallback = null; let animationFrame = null;
  const renderFrame = (_now, details) => {
    if (sequence !== videoSequence) return;
    drawTracking(details?.mediaTime); updatePlayback();
    if (video.requestVideoFrameCallback) frameCallback = video.requestVideoFrameCallback(renderFrame);
    else if (!video.paused) animationFrame = requestAnimationFrame(renderFrame);
  };
  disposeVideo = () => {
    clearTimeout(timer); if (frameCallback !== null) video.cancelVideoFrameCallback(frameCallback); if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    for (const event of ['loadedmetadata', 'error', 'play', 'pause', 'ended', 'seeking', 'seeked', 'timeupdate']) video[`on${event}`] = null;
    video.pause(); video.removeAttribute('src'); video.load();
  };
  video.onloadedmetadata = () => {
    if (sequence !== videoSequence) return;
    clearTimeout(timer);
    const error = durationError(video.duration); if (error) return fail(error);
    if (!video.videoWidth || !video.videoHeight) return fail('Ce fichier ne contient pas d’image vidéo décodable.');
    media = { id: crypto.randomUUID(), name: file.name, duration_seconds: video.duration, width: video.videoWidth, height: video.videoHeight };
    selectedFile = file;
    $('source-label').textContent = 'Vidéo préenregistrée';
    $('video-stage').hidden = false; $('stage-empty').hidden = true;
    for (const id of ['stage-top', 'stage-name', 'stage-replace']) $(id).hidden = false;
    for (const id of ['play-video', 'mute-video', 'restart-video', 'fullscreen-video', 'timeline']) $(id).disabled = false;
    $('video-info').textContent = `${file.name} · ${number(video.duration)} s · Prête à lire`;
    $('stage-filename').textContent = file.name; $('total-time').textContent = clock(video.duration); $('timeline').max = video.duration;
    $('media-reference').textContent = `Référence de cet extrait : ${media.id}`;
    renderFrame();
    window.dispatchEvent(new CustomEvent('visio:mediachange', { detail: { media: { ...media } } }));
  };
  video.onplay = () => { updatePlayback(); if (!video.requestVideoFrameCallback) { cancelAnimationFrame(animationFrame); animationFrame = requestAnimationFrame(renderFrame); } };
  for (const event of ['pause', 'ended', 'seeking', 'seeked', 'timeupdate']) video[`on${event}`] = () => { drawTracking(); updatePlayback(); };
  video.onerror = () => fail('Vidéo illisible ou codec non pris en charge par ce navigateur. Essayez un autre fichier.');
  $('video-info').textContent = 'Vérification de la durée…'; $('clear-video').hidden = false;
  $('video-stage').append(video); video.src = videoUrl;
});

function setLiveMode(enabled) {
  document.body.classList.toggle('is-live', enabled);
  $('live-summary').hidden = !enabled;
  $('stop-camera').hidden = !enabled;
  $('start-camera').disabled = enabled;
  $('source-camera').disabled = enabled;
  $('source-label').textContent = enabled ? 'Webcam · en direct' : 'Webcam ou extrait vidéo';
  $('source-chip').textContent = enabled ? 'EN DIRECT' : 'LECTURE LOCALE';
  if (!enabled) { $('live-points').textContent = '—'; $('live-latency').textContent = '—'; }
}
function openCamera() {
  $('sources-dialog').close();
  clearVideo();
  const sequence = videoSequence;
  const video = el('video');
  video.autoplay = true; video.playsInline = true; video.muted = true;
  video.setAttribute('aria-label', 'Webcam en direct, vue miroir');
  media = { id: crypto.randomUUID(), kind: 'live', name: 'Webcam en direct', duration_seconds: null, width: 0, height: 0 };
  document.body.classList.add('compare-mode');
  setLiveMode(true);
  const originalCanvas = el('canvas'); originalCanvas.id = 'live-original'; originalCanvas.hidden = true;
  originalCanvas.setAttribute('aria-label', 'Flux webcam original synchronisé');
  $('video-stage').append(video, originalCanvas); comparison.start(originalCanvas); $('video-stage').hidden = false; $('stage-empty').hidden = true;
  for (const id of ['stage-top', 'stage-name']) $(id).hidden = false;
  $('stage-filename').textContent = 'Vous · vue miroir';
  $('fullscreen-video').disabled = false;
  $('media-reference').textContent = `Session webcam : ${media.id}`;
  window.dispatchEvent(new CustomEvent('visio:mediachange', { detail: { media: { ...media } } }));
  disposeVideo = startLiveCamera({ video,
    onStream: stream => { if (sequence === videoSequence) signals.start(stream, video); },
    onReady: data => { if (sequence === videoSequence) comparison.prepare(data); },
    onState: message => { if (sequence === videoSequence) { $('live-status').textContent = message; $('video-info').textContent = message; } },
    onFrame: frame => {
      if (sequence !== videoSequence) { frame.bitmap?.close(); return; }
      comparison.render(frame);
      media.width = video.videoWidth; media.height = video.videoHeight;
      liveFrame = { time_seconds: frame.timestamp / 1000, faces: frame.faces };
      $('live-points').textContent = String(frame.faces.reduce((sum, face) => sum + face.landmarks.length, 0));
      $('live-latency').textContent = `${Math.round(frame.inferenceMs)} ms`;
      $('live-status').textContent = frame.faces.length ? 'Visage détecté · suivi actif' : 'Placez votre visage devant la caméra.';
      $('video-info').textContent = 'Webcam en direct · aucun enregistrement';
      drawTracking(); updatePlayback();
    },
    onError: message => { if (sequence === videoSequence) { clearVideo(); signals.unavailable(message); alertAt('video-alert', [message]); } },
  });
}
$('start-camera').addEventListener('click', openCamera);
$('source-camera').addEventListener('click', openCamera);
$('stop-camera').addEventListener('click', clearVideo);

window.addEventListener('pagehide', clearVideo);
renderEmpty(); renderMetadata(); drawTracking();
connectLocalEngine({ api: window.visioDemo, getFile: () => selectedFile,
  button: $('analyze-local'), cancelButton: $('cancel-local'), status: $('engine-status') });
