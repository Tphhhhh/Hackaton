import test from 'node:test';
import assert from 'node:assert/strict';
import { createScoreSmoother } from '../src/score-smoothing.js';

test('an isolated dip is attenuated, a sustained change still converges', () => {
  const smoother = createScoreSmoother();
  assert.equal(smoother.sample(.9), .9);
  assert.ok(Math.abs(smoother.sample(.1) - .7) < 1e-12);
  let last=.7;
  for(let i=0;i<20;i++) {
    const next=smoother.sample(.1);
    assert.ok(next < last && next >= .1);
    last=next;
  }
  assert.ok(last < .103);
});

test('rises and falls are smoothed symmetrically, independently per face', () => {
  const up=createScoreSmoother(),down=createScoreSmoother();
  up.sample(.1);down.sample(.9);
  assert.ok(Math.abs(up.sample(.9) - .3)<1e-12);
  assert.ok(Math.abs(down.sample(.1) - .7)<1e-12);
});

test('missing data, invalid data and source resets cannot retain old scores', () => {
  for(const absent of [null,undefined,NaN,Infinity,-.1,1.1]) {
    const smoother=createScoreSmoother();smoother.sample(.9);
    assert.equal(smoother.sample(absent),null);
    assert.equal(smoother.sample(.1),.1);
  }
  const smoother=createScoreSmoother();smoother.sample(.9);smoother.reset();
  assert.equal(smoother.sample(.1),.1);
});
