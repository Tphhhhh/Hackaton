import { test, expect } from '@playwright/test';

async function camera(page, { denied = false, delayed = false } = {}) {
  // Stub only the neural HTTP transport. MediaPipe tracking below is real.
  // Actual GPU image quality and latency are checked separately against Python.
  await page.route('**/api/live/status', route => route.fulfill({ json: { ready: true, model: 'test transport' } }));
  await page.route('**/api/live/swap', route => route.fulfill({
    contentType: 'image/jpeg', path: new URL('./fixtures/grace-hopper.jpg', import.meta.url).pathname,
    headers: { 'X-Visio-Swapped': '1', 'X-Visio-Inference-Ms': '42' },
  }));
  await page.addInitScript(({ denied, delayed }) => {
    window.testStreams = [];
    navigator.mediaDevices.getUserMedia = async constraints => {
      window.testConstraints = constraints;
      if (denied) throw new DOMException('Denied', 'NotAllowedError');
      if (delayed) await new Promise(resolve => { window.releaseCamera = resolve; });
      const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 480;
      const ctx = canvas.getContext('2d');
      const image = new Image(); image.src = '/tests/fixtures/grace-hopper.jpg';
      await image.decode();
      window.testBlank = false;
      const paint = () => { ctx.fillStyle = '#333'; ctx.fillRect(0, 0, 640, 480); if (!window.testBlank) ctx.drawImage(image, 130, 0, 380, 480); };
      paint();
      const timer = setInterval(paint, 40);
      const stream = canvas.captureStream(25);
      const track = stream.getVideoTracks()[0]; const stop = track.stop.bind(track);
      track.stop = () => { clearInterval(timer); stop(); };
      window.testStreams.push(stream);
      return stream;
    };
  }, { denied, delayed });
}

// A real face model on a deterministic in-memory camera; no fake landmarks.
test('live model tracks a face, clears it when absent, mirrors, and releases camera', async ({ page }) => {
  await camera(page);
  const writes = [], external = [], errors = [];
  page.on('request', req => { if (req.method() !== 'GET') writes.push(req.url()); if (!req.url().startsWith('http://127.0.0.1:5179')) external.push(req.url()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#start-camera')).toBeVisible();
  expect(await page.evaluate(() => window.testStreams.length)).toBe(0);
  await page.locator('#start-camera').click();
  await expect(page.locator('#live-points')).toHaveText('478', { timeout: 30000 });
  await expect(page.locator('#face-overlay circle')).toHaveCount(32);
  await expect(page.locator('#timeline')).toBeHidden();
  await expect(page.locator('#analyze-local')).toBeDisabled();
  expect(await page.evaluate(() => window.testConstraints.audio)).toBe(false);
  const transforms = await page.evaluate(() => ['video', '#face-overlay'].map(s => getComputedStyle(document.querySelector(s)).transform));
  expect(transforms).toEqual(['matrix(-1, 0, 0, 1, 0, 0)', 'matrix(-1, 0, 0, 1, 0, 0)']);
  await page.screenshot({ path: 'test-results/live-desktop.png', fullPage: true });
  await page.locator('#original-landmarks').selectOption('none');
  await expect(page.locator('#face-overlay')).toBeHidden();
  await page.locator('#original-landmarks').selectOption('full');
  await expect(page.locator('#face-overlay circle')).toHaveCount(478);
  await page.locator('#original-landmarks').selectOption('light');
  await expect(page.locator('#face-overlay circle')).toHaveCount(32);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/live-mobile.png', fullPage: true });
  await page.evaluate(() => { window.testBlank = true; });
  await expect(page.locator('#live-points')).toHaveText('0');
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
  await page.locator('#stop-camera').click();
  await expect(page.locator('#stage-empty')).toBeVisible();
  expect(await page.evaluate(() => window.testStreams[0].getTracks().every(t => t.readyState === 'ended'))).toBe(true);
  expect(writes.every(url => url.endsWith('/api/live/swap'))).toBe(true); expect(external).toEqual([]); expect(errors).toEqual([]);
  // Restart uses a fresh stream and a fresh model timestamp sequence.
  await page.locator('#start-camera').click();
  await expect(page.locator('#live-points')).toHaveText('478', { timeout: 30000 });
  await page.locator('#stop-camera').click();
  expect(await page.evaluate(() => window.testStreams.every(s => s.getTracks().every(t => t.readyState === 'ended')))).toBe(true);
});

test('denied permission is actionable and can be retried', async ({ page }) => {
  await camera(page, { denied: true }); await page.goto('/');
  await page.locator('#start-camera').click();
  await expect(page.locator('#video-alert')).toContainText('Accès à la caméra refusé');
  await expect(page.locator('#start-camera')).toBeEnabled();
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
});

test('stop while permission is pending closes a late stream', async ({ page }) => {
  await camera(page, { delayed: true }); await page.goto('/');
  await page.locator('#start-camera').click();
  await page.locator('#stop-camera').click();
  await page.evaluate(() => window.releaseCamera());
  await expect.poll(() => page.evaluate(() => window.testStreams[0]?.getTracks().every(t => t.readyState === 'ended'))).toBe(true);
  await expect(page.locator('#stage-empty')).toBeVisible();
  await expect(page.locator('video')).toHaveCount(0);
});

test('switching to a clip releases webcam and restores file controls', async ({ page }) => {
  await camera(page); await page.goto('/'); await page.locator('#start-camera').click();
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1);
  await page.locator('#video-file').setInputFiles(new URL('./fixtures/simulation-12s.mp4', import.meta.url).pathname);
  await expect(page.locator('#video-info')).toContainText('Prête à lire');
  expect(await page.evaluate(() => window.testStreams[0].getTracks()[0].readyState)).toBe('ended');
  await expect(page.locator('#play-video')).toBeVisible(); await expect(page.locator('#play-video')).toBeEnabled();
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
});

test('disconnect stops tracking and offers a fresh start', async ({ page }) => {
  await camera(page); await page.goto('/'); await page.locator('#start-camera').click();
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1);
  await page.evaluate(() => window.testStreams[0].getVideoTracks()[0].dispatchEvent(new Event('ended')));
  await expect(page.locator('#video-alert')).toContainText('déconnectée');
  await expect(page.locator('#start-camera')).toBeEnabled();
  await expect(page.locator('video')).toHaveCount(0);
});

test('model failure closes camera and clears the live state', async ({ page }) => {
  await camera(page);
  await page.route('**/live-assets/face_landmarker.task', route => route.abort());
  await page.goto('/'); await page.locator('#start-camera').click();
  await expect(page.locator('#video-alert')).toContainText('suivi facial est indisponible', { timeout: 30000 });
  expect(await page.evaluate(() => window.testStreams[0].getTracks()[0].readyState)).toBe('ended');
  await expect(page.locator('#start-camera')).toBeEnabled();
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
});

test('comparison changes actual pixels, scores are simulated, and toggling restores the original', async ({ page }) => {
  await camera(page); await page.goto('/'); await page.locator('#start-camera').click();
  await expect(page.locator('#filter-status')).toContainText('Face swap Brad Pitt actif', { timeout: 30000 });
  await expect(page.locator('#demo-banner')).toContainText('SCORES SIMULÉS');
  await expect(page.locator('#filtered-canvas')).toHaveAttribute('data-filter-applied', 'true');
  // Compare the two canvases at the same JS turn. A color tweak or static poster
  // cannot pass the round trip to byte-identical source pixels when disabled.
  const difference = () => page.evaluate(() => {
    const left = document.querySelector('#live-original'), right = document.querySelector('#filtered-canvas');
    const a = left.getContext('2d').getImageData(0, 0, left.width, left.height).data;
    const scaled = document.createElement('canvas'); scaled.width = left.width; scaled.height = left.height;
    scaled.getContext('2d').drawImage(right, 0, 0, left.width, left.height);
    const b = scaled.getContext('2d').getImageData(0, 0, left.width, left.height).data;
    let count = 0; for (let i = 0; i < a.length; i += 4) if (Math.abs(a[i] - b[i]) > 5) count++;
    return count;
  });
  expect(await difference()).toBeGreaterThan(2000);
  expect(Number((await page.locator('#original-score').textContent()).replace(/\D/g, ''))).toBeLessThan(15);
  await expect.poll(async () => Number((await page.locator('#filtered-score').textContent()).replace(/\D/g, ''))).toBeGreaterThan(85);
  await expect(page.locator('#filtered-canvas')).toHaveAttribute('data-point-count', '0');
  await page.locator('#filtered-landmarks').selectOption('light');
  await expect(page.locator('#filtered-canvas')).toHaveAttribute('data-point-count', '32');
  await page.locator('#filtered-landmarks').selectOption('none');
  await page.locator('#toggle-filter').click();
  await expect(page.locator('#filtered-canvas')).toHaveAttribute('data-filter-applied', 'false');
  await expect.poll(difference).toBe(0);
  await expect.poll(async () => Number((await page.locator('#filtered-score').textContent()).replace(/\D/g, ''))).toBeLessThan(15);
  await page.locator('#toggle-filter').click();
  await expect(page.locator('#filtered-canvas')).toHaveAttribute('data-filter-applied', 'true');
  await page.evaluate(() => { window.testBlank = true; });
  await expect(page.locator('#original-score')).toHaveText('—'); await expect(page.locator('#filtered-score')).toHaveText('—');
  await page.locator('#stop-camera').click(); await expect(page.locator('#filtered-canvas')).toBeHidden();
});

test('external window has its own detection and stopping releases both streams', async ({ page }) => {
  await camera(page);
  await page.addInitScript(() => {
    navigator.mediaDevices.getDisplayMedia = async constraints => {
      window.displayConstraints = constraints;
      const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 480;
      const context = canvas.getContext('2d'); context.fillStyle = '#55aa88';
      context.fillRect(0, 0, 640, 480);
      const stream = canvas.captureStream(20); window.testExternal = stream;
      const timer = setInterval(() => context.fillRect(0, 0, 640, 480), 50);
      const track = stream.getVideoTracks()[0], stop = track.stop.bind(track);
      track.stop = () => { clearInterval(timer); stop(); }; return stream;
    };
  });
  await page.goto('/'); await page.locator('#start-camera').click();
  await expect(page.locator('#live-points')).toHaveText('478', { timeout: 30000 });
  await page.locator('#connect-external').click();
  await expect(page.locator('#filter-status')).toContainText('Flux externe', { timeout: 30000 });
  await expect(page.locator('#filtered-tracking')).toHaveText('Aucun visage détecté');
  await expect(page.locator('#live-points')).toHaveText('478');
  await expect(page.locator('#filtered-score')).toHaveText('—');
  expect(await page.evaluate(() => window.displayConstraints.audio)).toBe(false);
  await page.locator('#disconnect-external').click();
  expect(await page.evaluate(() => window.testExternal.getTracks()[0].readyState)).toBe('ended');
  await expect(page.locator('#filter-status')).toContainText('Face swap Brad Pitt actif');
  await page.locator('#connect-external').click();
  await expect.poll(() => page.evaluate(() => window.testExternal.getTracks()[0].readyState)).toBe('live');
  await page.locator('#stop-camera').click();
  expect(await page.evaluate(() => [...window.testStreams[0].getTracks(), ...window.testExternal.getTracks()].every(t => t.readyState === 'ended'))).toBe(true);
});

test('unavailable neural engine leaves webcam usable without a fabricated high score', async ({ page }) => {
  await camera(page); await page.route('**/api/live/status', route => route.fulfill({ json: { ready: false, error: 'Moteur indisponible' } }));
  await page.goto('/'); await page.locator('#start-camera').click();
  await expect(page.locator('#live-points')).toHaveText('478', { timeout: 30000 });
  await expect(page.locator('#filter-status')).toContainText('indisponible');
  await expect(page.locator('#filtered-score')).toHaveText('—');
  await expect(page.locator('#connect-external')).toBeEnabled();
});

test('opening an existing result from the demo returns to the analysis workspace', async ({ page }) => {
  await page.goto('/'); await page.locator('#open-sources').click(); await page.locator('[data-example="verify"]').click();
  await expect(page.locator('.conclusion')).toBeVisible();
  await expect(page.locator('#filtered-panel')).toBeHidden();
});

test('delayed swap has no queue and cannot reappear after disabling or stopping', async ({ page }) => {
  await camera(page);
  let release, calls = 0;
  const held = new Promise(resolve => { release = resolve; });
  await page.route('**/api/live/swap', async route => {
    calls++; await held;
    await route.fulfill({ contentType: 'image/jpeg', path: new URL('./fixtures/grace-hopper.jpg', import.meta.url).pathname,
      headers: { 'X-Visio-Swapped': '1', 'X-Visio-Inference-Ms': '800' } }).catch(() => {});
  });
  await page.goto('/'); await page.locator('#start-camera').click();
  await expect.poll(() => calls).toBe(1);
  // Many camera frames arrive while this single request is held.
  await page.waitForTimeout(650); expect(calls).toBe(1);
  await page.locator('#toggle-filter').click(); release();
  await expect(page.locator('#filter-status')).toContainText('Filtre désactivé');
  await expect(page.locator('#filtered-canvas')).toHaveAttribute('data-filter-applied', 'false');
  await page.locator('#stop-camera').click();
  await expect(page.locator('#filtered-canvas')).toBeHidden();
  await expect(page.locator('#filtered-score')).toHaveText('—');
  expect(calls).toBe(1);
});

test('inference failure can retry without restarting the webcam', async ({ page }) => {
  await camera(page);
  let failing = true;
  await page.route('**/api/live/swap', route => failing
    ? route.fulfill({ status: 500, json: { error: 'Face swap interrompu.' } })
    : route.fulfill({ contentType: 'image/jpeg', path: new URL('./fixtures/grace-hopper.jpg', import.meta.url).pathname,
      headers: { 'X-Visio-Swapped': '1', 'X-Visio-Inference-Ms': '40' } }));
  await page.goto('/'); await page.locator('#start-camera').click();
  await expect(page.locator('#filter-status')).toContainText('interrompu');
  await expect(page.locator('#filtered-score')).toHaveText('—');
  failing = false; await page.getByRole('button', { name: 'Réessayer le face swap' }).click();
  await expect(page.locator('#filter-status')).toContainText('Face swap Brad Pitt actif');
  expect(await page.evaluate(() => window.testStreams.length)).toBe(1);
});
