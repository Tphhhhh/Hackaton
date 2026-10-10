import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDemoScores } from '../src/demo-scores.js';

test('demo scores are labeled, absent without a face, and never a model result', () => {
  const scores = createDemoScores();
  assert.deepEqual(scores.sample(0, { facePresent: false, filterApplied: true }), { original: null, filtered: null, simulation: true });
  const visible = scores.sample(1000, { facePresent: true, filterApplied: true });
  assert.equal(visible.simulation, true); assert.ok(visible.original < 15); assert.ok(visible.filtered > 85);
  assert.equal(scores.sample(1100, { facePresent: true, filteredFacePresent: false, filterApplied: true }).filtered, null);
  scores.reset();
  assert.deepEqual(scores.sample(2000, { facePresent: false, filterApplied: false }), { original: null, filtered: null, simulation: true });
});

test('disabling the filter settles back to the original scenario smoothly', () => {
  const scores = createDemoScores();
  const before = scores.sample(1000, { facePresent: true, filterApplied: true });
  const next = scores.sample(1050, { facePresent: true, filterApplied: false });
  assert.ok(next.filtered < before.filtered && next.filtered > 70);
  let last;
  for (let t = 1100; t < 7000; t += 50) last = scores.sample(t, { facePresent: true, filterApplied: false });
  assert.ok(Math.abs(last.original - last.filtered) <= 1);
});
