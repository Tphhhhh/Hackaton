import {test,expect} from '../../visio-demo/node_modules/@playwright/test/index.mjs';
async function camera(page){
 await page.route('**/fixture-face.jpg',r=>r.fulfill({contentType:'image/jpeg',path:new URL('../../visio-demo/tests/fixtures/grace-hopper.jpg',import.meta.url).pathname}));
 await page.addInitScript(()=>{
  window.cameraCalls=0;
  navigator.mediaDevices.getUserMedia=async()=>{
   window.cameraCalls++;const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;
   const img=new Image();img.src='/fixture-face.jpg';await img.decode();const c=canvas.getContext('2d');
   const paint=()=>{c.fillStyle='#333';c.fillRect(0,0,640,480);c.drawImage(img,130,0,380,480);};paint();
   const timer=setInterval(paint,40);const stream=canvas.captureStream(25);window.testStream=stream;
   const track=stream.getVideoTracks()[0],stop=track.stop.bind(track);track.stop=()=>{clearInterval(timer);stop();};return stream;
  };
 });
}

test('single page, local observations, both scores and clean stop',async({page})=>{
 await camera(page);const errors=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().startsWith('http')&&!r.url().startsWith('http://127.0.0.1:8891'))external.push(r.url());});
 await page.goto('/');await expect(page.locator('.page-heading')).toHaveCount(0);
 await expect(page.locator('#session-panel')).toBeVisible();await expect(page.locator('#signals-count')).toHaveText('—');
 expect(await page.evaluate(()=>window.cameraCalls)).toBe(0);
 await page.locator('#start-camera').click();await expect(page.locator('#original-score')).toHaveText('20 / 100',{timeout:30000});
 await expect(page.locator('#filtered-score')).toHaveText('80 / 100');
 await expect(page.locator('#signals-state')).toContainText('Mesures actualisées');
 await expect(page.locator('#signals-rows')).toContainText('Changement de caméra');
 await expect(page.locator('#signals-observations')).toContainText('outil de test');
 await expect(page.locator('#signals-observations')).toContainText('i/s',{timeout:15000});
 await page.locator('#filter-portrait').selectOption('sam-altman');
 await expect(page.locator('#filtered-score')).toHaveText('80 / 100',{timeout:15000});
 expect(await page.evaluate(()=>window.cameraCalls)).toBe(1);
 await page.screenshot({path:'test-results/signals-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/signals-mobile.png',fullPage:true});
 await page.locator('#stop-camera').click();await expect(page.locator('#signals-count')).toHaveText('—');
 await expect(page.locator('#signals-rows')).toBeEmpty();await expect(page.locator('#original-score')).toHaveText('—');
 expect(await page.evaluate(()=>window.testStream.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 expect(errors).toEqual([]);expect(external).toEqual([]);
});
test('denied camera is unavailable, not a reported refusal',async({page})=>{
 await page.addInitScript(()=>{navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Denied','NotAllowedError');};});
 await page.goto('/');await page.locator('#start-camera').click();
 await expect(page.locator('#signals-state')).toContainText('refusé');
 await expect(page.locator('#signals-count')).toHaveText('—');
 await expect(page.locator('#signals-refused')).not.toBeChecked();
});
test('late results cannot restore a stopped session',async({page})=>{
 await camera(page);let release;const waiting=new Promise(resolve=>release=resolve);let held=false;
 await page.route('**/api/session/analyze',async route=>{held=true;await waiting;try{await route.continue();}catch{}});
 await page.goto('/');await page.locator('#start-camera').click();await expect.poll(()=>held).toBe(true);
 await page.locator('#stop-camera').click();release();
 await expect(page.locator('#signals-state')).toContainText('Session arrêtée');await expect(page.locator('#signals-rows')).toBeEmpty();
});
test('optional microphone stops with the camera, including a late permission',async({page})=>{
 await camera(page);await page.goto('/');await page.locator('#start-camera').click();
 await expect(page.locator('#signals-state')).toContainText('Mesures actualisées');
 await page.evaluate(()=>{
  const original=navigator.mediaDevices.getUserMedia;
  navigator.mediaDevices.getUserMedia=async constraints=>{
   if(!constraints.audio)return original(constraints);
   const context=new AudioContext();const destination=context.createMediaStreamDestination();
   window.audioStream=destination.stream;window.audioContextForTest=context;
   if(window.delayAudio)await new Promise(resolve=>window.allowAudio=resolve);
   return destination.stream;
  };
 });
 await page.locator('#layers-microphone').click();await expect(page.locator('#signals-mic')).toHaveText('Arrêter le microphone');
 await expect(page.locator('#signals-observations')).toContainText('dBFS');
 await page.locator('#stop-camera').click();
 expect(await page.evaluate(()=>window.audioStream.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 await page.evaluate(()=>window.audioContextForTest.close());
 await page.locator('#start-camera').click();await expect(page.locator('#layers-microphone')).toBeEnabled();
 await page.evaluate(()=>window.delayAudio=true);await page.locator('#layers-microphone').click();
 await expect.poll(()=>page.evaluate(()=>typeof window.allowAudio)).toBe('function');
 await page.locator('#stop-camera').click();await page.evaluate(()=>window.allowAudio());
 await expect.poll(()=>page.evaluate(()=>window.audioStream.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 await page.evaluate(()=>window.audioContextForTest.close());
 await expect(page.locator('#signals-count')).toHaveText('—');
});
test('console fits desktop and mobile widths; metadata stays out of the interface',async({page})=>{
 await page.goto('/');
 await expect(page.locator('#console-overall-score')).toHaveText('En attente');
 await expect(page.locator('.score-unit')).toBeHidden();
 await expect(page.locator('#console-meta-state')).toBeHidden();
 await expect(page.getByText('Étudier les métadonnées',{exact:true})).toBeHidden();
 await expect(page.locator('#console-overall-gauge i')).toHaveCount(25);
 expect(await page.locator('#console-overall-score').evaluate(el=>parseFloat(getComputedStyle(el).fontSize))).toBeLessThanOrEqual(16);
 await page.evaluate(()=>{const score=document.getElementById('console-overall-score');score.textContent='100';score.dataset.tone='positive';});
 await expect(page.locator('.score-unit')).toBeVisible();
 for(const width of [1440,1250,1024,390]){
  await page.setViewportSize({width,height:900});
  await expect(page.locator('#console-video-bars i')).toHaveCount(5);
  expect(await page.evaluate(()=>{
   const score=document.getElementById('console-overall-score').getBoundingClientRect();
   const panel=document.getElementById('session-panel').getBoundingClientRect();
   return score.right<=panel.right&&document.documentElement.scrollWidth<=innerWidth;
  })).toBe(true);
 }
});
test('global index is the video confidence alone; metadata points never change it',async({page})=>{
 await camera(page);let points=0;
 await page.route('**/api/session/analyze',async route=>{
  const response=await route.fetch();const data=await response.json();
  await route.fulfill({json:{...data,points,measured_count:4}});
 });
 await page.goto('/');
 await expect(page.locator('#console-overall-score')).toHaveText('En attente');
 await expect(page.locator('#console-video-bars')).toHaveAttribute('data-tone','unknown');
 await page.locator('#start-camera').click();
 await expect(page.locator('#console-overall-score')).toHaveText('80',{timeout:30000});
 await expect(page.locator('#console-video-bars-value')).toHaveText('4 / 5');
 await expect(page.locator('#console-overall-state')).toHaveText('Flux original · GenD PE');
 points=40;
 await expect(page.locator('#signals-state')).toContainText('Mesures actualisées',{timeout:10000});
 await page.waitForTimeout(3000);
 await expect(page.locator('#console-overall-score')).toHaveText('80');
 await page.locator('#console-source-filtered').click();
 await expect(page.locator('#console-overall-score')).toHaveText('20');
 await expect(page.locator('#console-video-bars')).toHaveAttribute('data-tone','warning');
 await expect(page.locator('#console-overall-state')).toHaveText('Flux transformé · GenD PE');
 await page.route('**/api/live/score',route=>route.fulfill({status:503,json:{error:'test video outage'}}));
 await expect(page.locator('#console-overall-score')).toHaveText('En attente',{timeout:10000});
 await expect(page.locator('#console-video-bars')).toHaveAttribute('data-tone','unknown');
 await page.locator('#stop-camera').click();
 await expect(page.locator('#console-overall-score')).toHaveText('En attente');
});

test('five live layers use each source independently and expire on stop', async ({page}) => {
 await camera(page);
 // Return a genuinely blank transformed image. Original landmarks must not leak into its indicators.
 const blank = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
 await page.route('**/api/live/swap', route => route.fulfill({body:blank,contentType:'image/png',headers:{
  'X-Visio-Portrait':route.request().headers()['x-visio-portrait'],'X-Visio-Swapped':'1','X-Visio-Inference-Ms':'1',
 }}));
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 const panel=page.locator('#video-signal-layers');
 await expect(panel.locator('.signal-layer')).toHaveCount(5);
 await expect(panel.locator('[data-state=unknown]')).toHaveCount(5);
 await expect(page.locator('#layers-microphone')).toBeDisabled();
 await page.locator('#start-camera').click();
 await expect(panel.locator('[data-signal=rhythm] strong')).toHaveText('Image presque figée',{timeout:30000});
 await expect(panel.locator('[data-signal=activity]')).toHaveAttribute('data-state','observed');
 await expect(panel.locator('[data-signal=lips] strong')).toHaveText('Microphone désactivé');
 await expect(page.locator('#console-video-score')).toContainText('80');
 await page.locator('#console-source-filtered').click();
 await expect(panel).toHaveAttribute('data-source','filtered');
 await expect(panel.locator('[data-signal=activity] strong')).toHaveText('Visage non exploitable',{timeout:30000});
 await expect(panel.locator('[data-signal=lips] strong')).toHaveText('Visage non exploitable');
 await page.locator('#console-source-original').click();
 await expect(panel.locator('[data-signal=activity]')).toHaveAttribute('data-state','observed');
 await page.screenshot({path:'test-results/layers-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/layers-mobile.png',fullPage:true});
 await page.locator('#stop-camera').click();
 await expect(panel.locator('[data-state=unknown]')).toHaveCount(5);
 await expect(page.locator('#layers-microphone')).toBeDisabled();
 await page.locator('#console-source-filtered').click();
 await expect(panel.locator('[data-state=unknown]')).toHaveCount(5);
 expect(errors).toEqual([]);
});

test('voice-mouth button samples local audio, stays unknown in silence and releases tracks', async ({page}) => {
 await camera(page);await page.goto('/');await page.locator('#start-camera').click();
 await expect(page.locator('#layers-microphone')).toBeEnabled();
 await page.evaluate(()=>{
  const original=navigator.mediaDevices.getUserMedia;
  navigator.mediaDevices.getUserMedia=async constraints=>{
   if(!constraints.audio)return original(constraints);
   const context=new AudioContext();const destination=context.createMediaStreamDestination();
   window.layerAudioContext=context;window.layerAudioStream=destination.stream;
   return destination.stream;
  };
 });
 await page.locator('#layers-microphone').click();
 await expect(page.locator('#layers-microphone')).toHaveText('Arrêter le microphone');
 const lips=page.locator('#video-signal-layers [data-signal=lips]');
 await expect(lips.locator('strong')).toHaveText('Silence ou son trop faible',{timeout:30000});
 await expect(lips).toHaveAttribute('data-state','unknown');
 await page.locator('#layers-microphone').click();
 await expect(lips.locator('strong')).toHaveText('Microphone désactivé');
 expect(await page.evaluate(()=>window.layerAudioStream.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 await page.evaluate(()=>window.layerAudioContext.close());
 await page.locator('#stop-camera').click();
});

test('legacy candidate pages redirect to the single page',async({page})=>{
 await page.goto('/recruiter');await expect(page).toHaveURL('/');
});
