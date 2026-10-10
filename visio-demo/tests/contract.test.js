import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { parseResult, conclusionLabel, durationError, videoFileError, MAX_JSON_BYTES, MAX_VIDEO_BYTES } from '../src/contract.js';
const example = name => JSON.parse(readFileSync(new URL(`../reference/examples/${name}.json`, import.meta.url)));
for (const file of readdirSync(new URL('../reference/examples/', import.meta.url))) {
  test(`contrat : ${file}`, () => {
    const data = JSON.parse(readFileSync(new URL(`../reference/examples/${file}`, import.meta.url)));
    assert.equal(data.simulation, true);
    assert.equal(parseResult(data).ok, true);
  });
}
test('rejette les entrées invalides, vides, primitives et trop grosses', () => {
  for (const value of ['', '{', 'null', '[]', 'true', '{}', undefined, 'x'.repeat(MAX_JSON_BYTES + 1)]) {
    assert.equal(parseResult(value).ok, false);
  }
  const circular = {}; circular.self = circular;
  assert.equal(parseResult(circular).ok, false);
});
test('rejette versions, valeurs et propriétés non conformes', () => {
  const mutations = [
    d => delete d.session_id,
    d => d.schema_version = '2.0',
    d => d.coverage = 1.01,
    d => d.coverage = '1',
    d => d.duration_seconds = 21,
    d => d.sampled_frames = 41,
    d => d.config_sha256 = 'invalid',
    d => d.extra = true,
    d => d.detectors.dima.score = -1,
    d => d.detectors.dima.observations[0].time_seconds = 99,
    d => d.detectors.dima.observations[0].extra = 'invalid',
    d => d.detectors.dima.status = 'error',
    d => d.detectors.dima.status = 'insufficient',
    d => d.simulation = 'true',
  ];
  for (const mutate of mutations) { const data = example('verify'); mutate(data); assert.equal(parseResult(data).ok, false); }
});
test('applique les contraintes conditionnelles des états', () => {
  for (const name of ['failed', 'cancelled']) {
    const data = example(name); data.conclusion = 'no_signal'; assert.equal(parseResult(data).ok, false);
    data.conclusion = null; data.errors = []; assert.equal(parseResult(data).ok, false);
  }
  const partial = example('partial'); partial.conclusion = 'no_signal'; assert.equal(parseResult(partial).ok, false);
  partial.conclusion = 'indeterminate'; partial.errors = []; assert.equal(parseResult(partial).ok, false);
  const completed = example('verify'); completed.conclusion = null; assert.equal(parseResult(completed).ok, false);
});
test('respecte les champs nullables et refuse les erreurs globales null', () => {
  const failed = example('failed');
  assert.equal(parseResult(failed).ok, true);
  failed.errors = [null];
  assert.equal(parseResult(failed).ok, false);
  assert.equal(conclusionLabel(failed.conclusion), 'analyse insuffisante');
  assert.equal(conclusionLabel('__proto__'), 'analyse insuffisante');
});
test('ne modifie pas les données du moteur', () => {
  const data = example('verify'); const result = parseResult(data);
  result.data.detectors.dima.score = 0;
  assert.equal(data.detectors.dima.score, .9);
});
test('contrôle les limites vidéo et les formats sans lire le contenu', () => {
  for (const duration of [2, 4, 10, 12, 20]) assert.equal(durationError(duration), null);
  for (const duration of [0, 1.999, 20.001, NaN, Infinity]) assert.ok(durationError(duration));
  assert.equal(videoFileError({ name: 'clip.mp4', type: 'video/mp4', size: 100 }), null);
  assert.equal(videoFileError({ name: 'clip.WEBM', type: '', size: MAX_VIDEO_BYTES }), null);
  for (const file of [
    { name: 'clip.mp4', type: 'video/mp4', size: 0 },
    { name: 'clip.mp4', type: 'video/mp4', size: MAX_VIDEO_BYTES + 1 },
    { name: 'clip.txt', type: 'video/mp4', size: 100 },
    { name: 'clip.mp4', type: 'text/plain', size: 100 },
  ]) assert.ok(videoFileError(file));
});

// Captured engine output from ISSUE-001; deliberately separate from simulations.
test('importe une erreur réelle InvalidMedia du moteur avec cause', () => {
  const raw = readFileSync(new URL('./fixtures/actual-failure.json', import.meta.url), 'utf8');
  const result = parseResult(raw);
  assert.equal(result.ok, true, JSON.stringify(result.errors));
  assert.equal(result.data.simulation, false);
  assert.equal(result.data.status, 'failed');
  assert.equal(result.data.errors[0].code, 'InvalidMedia');
  assert.equal(result.data.errors[0].cause, null);
  assert.equal(conclusionLabel(result.data.conclusion), 'analyse insuffisante');
});

test('valide cause sur les erreurs globales et celles des détecteurs', () => {
  for (const errorAt of [data => data.errors[0], data => data.detectors.minifasnet.error]) {
    for (const cause of [null, 'FileNotFoundError: missing clip']) {
      const data = example('partial'); errorAt(data).cause = cause;
      assert.equal(parseResult(data).ok, true);
    }
    for (const cause of [42, false, {}]) {
      const data = example('partial'); errorAt(data).cause = cause;
      assert.equal(parseResult(data).ok, false);
    }
    const missing = example('partial'); delete errorAt(missing).cause;
    assert.equal(parseResult(missing).ok, false);
    const unknown = example('partial'); errorAt(unknown).unexpected = true;
    assert.equal(parseResult(unknown).ok, false);
  }
});
