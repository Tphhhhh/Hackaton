import test from 'node:test';
import assert from 'node:assert/strict';
import { parseSupplemental, frameAt, containedRect } from '../src/supplemental.js';
const media = { id: 'current-clip', duration_seconds: 12 };
// Synthetic geometry for renderer tests ONLY, never a production/demo example.
const tracking = () => ({ schema_version: '1.0', media_id: media.id, source: 'TEST ONLY', simulation: false, coordinate_space: 'normalized', frames: [
  { time_seconds: 0, faces: [{ id: 'face-1', box: { x: .2, y: .1, width: .5, height: .7 }, landmarks: [{ x: .35, y: .3 }, { x: .6, y: .3 }] }] },
  { time_seconds: .5, faces: [] },
] });
const metadata = () => ({ schema_version: '1.0', media_id: media.id, session_id: 'session-1', source: 'TEST ONLY', simulation: false, status: 'completed', checks: [{ id: 'format', label: 'Format', status: 'consistent', video_value: 'MP4', metadata_value: 'MP4', detail: 'Test' }], errors: [], limitations: ['Test only'] });
test('accepte coordonnées normalisées et refuse toute simulation de suivi', () => {
  assert.equal(parseSupplemental(tracking(), 'tracking', media).ok, true);
  assert.equal(parseSupplemental({ ...tracking(), simulation: true }, 'tracking', media).ok, false);
  assert.equal(parseSupplemental(tracking(), 'tracking', null).ok, false);
  assert.equal(parseSupplemental(tracking(), 'tracking', { ...media, id: 'other' }).ok, false);
});
test('rejette coordonnées impossibles, chronologie incohérente et identifiants dupliqués', () => {
  for (const change of [
    d => d.frames[0].faces[0].landmarks[0].x = 1.1,
    d => d.frames[0].faces[0].box.width = .9,
    d => d.frames[0].faces[0].box.height = 0,
    d => d.frames[0].faces.push(d.frames[0].faces[0]),
    d => d.frames[1].time_seconds = 0,
    d => d.frames[1].time_seconds = 13,
    d => d.coordinate_space = 'pixels',
    d => d.extra = true,
  ]) { const data = tracking(); change(data); assert.equal(parseSupplemental(data, 'tracking', media).ok, false); }
});
test('n’affiche ni données futures ni anciennes, conserve un échantillon sans visage', () => {
  const frames = tracking().frames;
  assert.equal(frameAt(frames, -.1), null);
  assert.equal(frameAt(frames, 0), frames[0]);
  assert.equal(frameAt(frames, .25), frames[0]);
  assert.equal(frameAt(frames, .251), null);
  assert.deepEqual(frameAt(frames, .5).faces, []);
  assert.equal(frameAt(frames, .76), null);
  assert.equal(frameAt([], 1), null);
});
test('place le suivi dans l’image avec bandes latérales ou horizontales', () => {
  assert.deepEqual(containedRect(800, 400, 400, 400), { x: 200, y: 0, width: 400, height: 400 });
  assert.deepEqual(containedRect(400, 800, 400, 400), { x: 0, y: 200, width: 400, height: 400 });
});
test('valide le module métadonnées, les états partiels et la liaison à l’extrait', () => {
  assert.equal(parseSupplemental(metadata(), 'metadata', media).ok, true);
  assert.equal(parseSupplemental(metadata(), 'metadata', { ...media, id: 'wrong' }).ok, false);
  for (const change of [d => d.checks[0].status = 'verified', d => d.status = 'failed', d => d.status = 'partial', d => d.checks.push(d.checks[0]), d => delete d.session_id]) {
    const data = metadata(); change(data); assert.equal(parseSupplemental(data, 'metadata', media).ok, false);
  }
  const partial = metadata(); partial.status = 'partial'; partial.errors = ['Test failure'];
  assert.equal(parseSupplemental(partial, 'metadata', media).ok, true);
});
test('rejette les fichiers annexes invalides, trop gros ou cycliques', () => {
  for (const value of ['{', '', 'null', {}, 'x'.repeat(2 * 1024 * 1024 + 1)]) assert.equal(parseSupplemental(value, 'tracking', media).ok, false);
  const cyclic = {}; cyclic.self = cyclic;
  assert.equal(parseSupplemental(cyclic, 'metadata', media).ok, false);
});
