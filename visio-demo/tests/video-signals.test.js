import test from 'node:test';
import assert from 'node:assert/strict';
import { createSignalHistory, lipCoherence, measurePixels } from '../src/video-signals.js';
const face = (extra = {}) => ({ eyes: .3, mouth: .04, x: .5, y: .5, size: .4, roll: 0,
  ring: Array(36).fill(0), brightness: 100, sharpness: { face: 40, background: 10 }, ...extra });
const metrics = (i, extra = {}) => ({ thumb: Array(48).fill(i), face: face(extra) });

test('no frames and missing faces remain unknown; rhythm does not require a face', () => {
  const history = createSignalHistory();
  assert.ok(Object.values(history.result()).every(r => r.state === 'unknown'));
  for (let i = 0; i < 50; i++) history.push(i * 100, { thumb: Array(48).fill(30), face: null });
  const result = history.result();
  assert.equal(result.rhythm.value, 'Image presque figée');
  for (const key of ['activity', 'lips', 'sharpness', 'edges']) assert.equal(result[key].state, 'unknown');
});

test('only a moving repeated sequence triggers the loop indicator', () => {
  const history = createSignalHistory();
  for (let i = 0; i < 60; i++) history.push(i * 100, metrics((i % 20) * 8));
  assert.equal(history.result().rhythm.value, 'Séquence répétée possible');
  const other = createSignalHistory();
  for (let i = 0; i < 60; i++) other.push(i * 100, metrics(i * 3));
  assert.equal(other.result().rhythm.value, 'Images renouvelées');
});

test('blink closure needs reopening within a plausible interval; immobility is not flagged', () => {
  const history = createSignalHistory();
  for (let i = 0; i < 60; i++) history.push(i * 100, metrics(i, { eyes: i === 20 || i === 21 ? .1 : .3 }));
  assert.equal(history.result().activity.value, '1 clignement observé');
  assert.equal(history.result().activity.state, 'observed');
  assert.equal(history.result().sharpness.value, 'Rapport 4.0×');
});

test('gaps, duplicate timestamps, reset and separate source histories cannot reuse old evidence', () => {
  const a = createSignalHistory(), b = createSignalHistory();
  for (let i = 0; i < 50; i++) a.push(i * 100, metrics(10));
  assert.equal(a.result().rhythm.state, 'flag');
  assert.equal(b.result().rhythm.state, 'unknown');
  assert.equal(a.push(4900, metrics(200)), false);
  a.push(7000, metrics(200));
  assert.equal(a.result().rhythm.state, 'unknown');
  a.reset(); assert.equal(a.result().sharpness.state, 'unknown');
});

test('contour fluctuations are gated by head movement and brightness', () => {
  const still = createSignalHistory(), moving = createSignalHistory(), lighting = createSignalHistory();
  for (let i = 0; i < 50; i++) {
    const ring = Array(36).fill(i % 2 ? 30 : -30);
    still.push(i * 100, metrics(i, { ring }));
    moving.push(i * 100, metrics(i, { ring, x: i % 2 ? .4 : .6 }));
    lighting.push(i * 100, metrics(i, { ring, brightness: i % 2 ? 100 : 150 }));
  }
  assert.equal(still.result().edges.state, 'flag');
  assert.equal(moving.result().edges.state, 'unknown');
  assert.equal(lighting.result().edges.state, 'unknown');
});

function audiovisual(delay = 0, silent = false, fixedMouth = false) {
  // Nonperiodic envelopes avoid ambiguous correlations at multiples of one period.
  const wave = t => .03 + .02 * Math.sin(t / 317) + .007 * Math.cos(t / 173);
  const frames = [], audio = [];
  for (let t = 0; t <= 9000; t += 50) {
    audio.push({ time: t, rms: silent ? 0 : wave(t - delay) });
    if (t % 100 === 0) frames.push({ time: t, metrics: metrics(0, { mouth: fixedMouth ? .04 : wave(t) * 5 }) });
  }
  return { frames, audio };
}
test('audio disabled, external source, silence and too few samples never reassure', () => {
  const { frames, audio } = audiovisual();
  assert.equal(lipCoherence(frames, audio, false).state, 'unknown');
  assert.equal(lipCoherence(frames, audio, true, false).value, 'Audio non associé');
  assert.equal(lipCoherence(frames.slice(0, 10), audio, true).state, 'unknown');
  const silent = audiovisual(0, true);
  assert.equal(lipCoherence(silent.frames, silent.audio, true).value, 'Silence ou son trop faible');
});
test('aligned, delayed and motionless audio/video examples are distinguished using capture timestamps', () => {
  let data = audiovisual();
  assert.equal(lipCoherence(data.frames, data.audio, true).value, 'Activités concordantes');
  data = audiovisual(500);
  const delayed = lipCoherence(data.frames, data.audio, true);
  assert.equal(delayed.value, 'Décalage possible'); assert.match(delayed.detail, /500 ms/);
  data = audiovisual(0, false, true);
  assert.equal(lipCoherence(data.frames, data.audio, true).value, 'Son sans mouvement visible');
  assert.equal(lipCoherence(data.frames, data.audio.map(a => ({ ...a, time: a.time + 20000 })), true).state, 'unknown');
});
test('pixel measurements handle flat images, small faces and actual texture without inventing a face', () => {
  const pixels = new Uint8ClampedArray(160 * 120 * 4).fill(100);
  const noFace = measurePixels(pixels, 160, 120, null);
  assert.equal(noFace.thumb.length, 48); assert.equal(noFace.face, null);
  const landmarks = Array.from({ length: 478 }, () => ({ x: .5, y: .5 }));
  assert.equal(measurePixels(pixels, 160, 120, { landmarks, box: { x: .4, y: .4, width: .05, height: .05 } }).face, null);
  const full = measurePixels(pixels, 160, 120, { landmarks, box: { x: .25, y: .2, width: .5, height: .6 } });
  assert.deepEqual(full.face.sharpness, { face: 0, background: 0 });
  assert.ok(full.face.ring.every(v => v === 0));
});
test('a stopped audio stream cannot keep a previous result alive while video continues', () => {
 const {frames,audio}=audiovisual();
 assert.equal(lipCoherence(frames,audio.filter(a=>a.time<8000),true).value,'Audio indisponible');
});
