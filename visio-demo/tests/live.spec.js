import { test, expect } from '@playwright/test';

async function camera(page, { denied = false, delayed = false } = {}) {
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
  await expect(page.locator('#face-overlay circle')).toHaveCount(478);
  await expect(page.locator('#timeline')).toBeHidden();
  await expect(page.locator('#analyze-local')).toBeDisabled();
  expect(await page.evaluate(() => window.testConstraints.audio)).toBe(false);
  const transforms = await page.evaluate(() => ['video', '#face-overlay'].map(s => getComputedStyle(document.querySelector(s)).transform));
  expect(transforms).toEqual(['matrix(-1, 0, 0, 1, 0, 0)', 'matrix(-1, 0, 0, 1, 0, 0)']);
  await page.screenshot({ path: 'test-results/live-desktop.png', fullPage: true });
  await page.locator('#toggle-tracking').click();
  await expect(page.locator('#face-overlay')).toBeHidden();
  await page.locator('#toggle-tracking').click();
  await expect(page.locator('#face-overlay circle')).toHaveCount(478);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/live-mobile.png', fullPage: true });
  await page.evaluate(() => { window.testBlank = true; });
  await expect(page.locator('#live-points')).toHaveText('0');
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
  await page.locator('#stop-camera').click();
  await expect(page.locator('#stage-empty')).toBeVisible();
  expect(await page.evaluate(() => window.testStreams[0].getTracks().every(t => t.readyState === 'ended'))).toBe(true);
  expect(writes).toEqual([]); expect(external).toEqual([]); expect(errors).toEqual([]);
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
