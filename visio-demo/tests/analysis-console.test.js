import test from 'node:test';
import assert from 'node:assert/strict';
import {confidenceScore,confidenceLevel} from '../src/analysis-console.js';

test('metadata can only subtract from video confidence, with a zero floor',()=>{
  assert.equal(confidenceScore(20,0),80);
  assert.equal(confidenceScore(20,15),65);
  assert.equal(confidenceScore(90,30),0);
  assert.equal(confidenceScore(0,0),100);
  assert.equal(confidenceScore(100,0),0);
  assert.equal(confidenceScore(24.4,15),60.599999999999994);
});
test('missing sources are never treated as reassuring zero penalties',()=>{
  for(const value of [null,undefined,NaN,Infinity,-1,101,'20',false]){
    assert.equal(confidenceScore(value,20),null);
    assert.equal(confidenceScore(20,value),null);
    assert.equal(confidenceLevel(value),null);
  }
});
test('five segments have explicit endpoints and a distinct unknown state',()=>{
  assert.deepEqual([0,1,20,21,40,41,60,61,80,81,100].map(confidenceLevel),[0,0,1,1,2,2,3,3,4,4,5]);
});
