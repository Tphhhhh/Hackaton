import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const clip = new URL('./fixtures/simulation-12s.mp4', import.meta.url).pathname;
const fixture = JSON.parse(fs.readFileSync(new URL('../reference/examples/no_signal.json', import.meta.url)));
const json = body => ({ contentType: 'application/json', body: JSON.stringify(body) });

test.beforeEach(async ({ page }) => {
  await page.route('**/api/status', route => route.fulfill(json({ backend: 'gend' })));
});

test('explicit click sends selected bytes and binds result and real-coordinate contract', async ({ page }) => {
  let posts = 0;
  await page.route('**/api/analyze/**', async route => {
    posts++;
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataBuffer()).toEqual(fs.readFileSync(clip));
    const mediaId = new URL(route.request().url()).pathname.split('/').at(-1);
    // Synthetic contract data only for this test; never bundled into the demo.
    const tracking = { schema_version:'1.0',media_id:mediaId,source:'test fixture',simulation:false,
      coordinate_space:'normalized',frames:[{time_seconds:0,faces:[]}] };
    await route.fulfill(json({media_id:mediaId,result:{...fixture,simulation:false},tracking}));
  });
  await page.goto('/?mode=clip');
  await page.locator('#video-file').setInputFiles(clip);
  await expect(page.locator('#analyze-local')).toBeEnabled();
  expect(posts).toBe(0);
  await page.locator('#analyze-local').click();
  await expect(page.locator('#engine-status')).toContainText('Analyse terminée');
  expect(posts).toBe(1);
  const context = await page.evaluate(()=>window.visioDemo.getContext());
  expect(context.analysis.media_id).toBe(context.media.id);
  await expect(page.locator('.association-note')).toContainText('associé à cet extrait');
});

test('replacing media cancels the active request and never displays its stale result', async ({ page }) => {
  let started;const admitted=new Promise(resolve=>started=resolve);
  let release;const gate=new Promise(resolve=>release=resolve);
  let deleted=false;
  await page.route('**/api/analyze/**', async route => {
    if(route.request().method()==='DELETE') {deleted=true;return route.fulfill(json({status:'cancelling'}));}
    const mediaId=new URL(route.request().url()).pathname.split('/').at(-1);
    started();await gate;
    await route.fulfill(json({media_id:mediaId,result:{...fixture,simulation:false},tracking:null})).catch(()=>{});
  });
  await page.goto('/?mode=clip');
  await page.locator('#video-file').setInputFiles(clip);
  await page.locator('#analyze-local').click();await admitted;
  await page.locator('#video-file').setInputFiles(clip);
  release();
  await expect.poll(()=>deleted).toBe(true);
  await expect(page.locator('#analyze-local')).toBeEnabled();
  expect((await page.evaluate(()=>window.visioDemo.getContext())).analysis).toBeNull();
  await expect(page.locator('.conclusion')).toHaveCount(0);
});

test('wrong media binding and backend errors remain explicit without stale gauges', async ({ page }) => {
  await page.route('**/api/analyze/**', route=>route.fulfill(json({media_id:'wrong',result:fixture})));
  await page.goto('/?mode=clip');await page.locator('#video-file').setInputFiles(clip);
  await page.locator('#analyze-local').click();
  await expect(page.locator('#engine-status')).toContainText('autre extrait');
  await expect(page.locator('.conclusion')).toHaveCount(0);
  await page.unroute('**/api/analyze/**');
  await page.route('**/api/analyze/**',route=>route.fulfill({status:409,...json({error:'Une analyse se termine encore.'})}));
  await page.locator('#analyze-local').click();
  await expect(page.locator('#engine-status')).toContainText('se termine encore');
  await expect(page.locator('#analyze-local')).toBeEnabled();
});
