import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const clip = new URL('./fixtures/simulation-12s.mp4', import.meta.url).pathname;
const realShape = JSON.parse(readFileSync(new URL('../reference/examples/no_signal.json', import.meta.url)));
async function loadClip(page) {
  await page.locator('#video-file').setInputFiles(clip);
  await expect(page.locator('#video-info')).toContainText('Prête à lire');
  return page.evaluate(() => window.visioDemo.getContext().media);
}
// Artificial data solely to test geometry/transport. Never offered as a demo example.
const trackingPayload = id => ({ schema_version: '1.0', media_id: id, source: 'TEST ONLY — synthetic geometry', simulation: false, coordinate_space: 'normalized', frames: [
  { time_seconds: 0, faces: [{ id: 'test-face', box: { x: .2, y: .1, width: .5, height: .7 }, landmarks: [{ x: .35, y: .3 }, { x: .6, y: .3 }, { x: .45, y: .5 }] }] },
  { time_seconds: .5, faces: [] },
  { time_seconds: 2, faces: [{ id: 'test-face', box: { x: .1, y: .2, width: .4, height: .6 }, landmarks: [{ x: .2, y: .4 }] }] },
] });
const metadataPayload = (id, session = realShape.session_id) => ({ schema_version: '1.0', media_id: id, session_id: session, source: 'TEST ONLY — metadata adapter', simulation: false, status: 'completed', checks: [{ id: 'format', label: 'Format du fichier', status: 'mismatch', video_value: 'MP4', metadata_value: 'WebM', detail: 'Écart déclaré par le module de test.' }], errors: [], limitations: ['Ne démontre pas l’identité.'] });
async function seek(page, seconds) {
  await page.locator('video').evaluate(async (video, time) => {
    if (video.currentTime === time) return;
    await new Promise(resolve => { video.addEventListener('seeked', resolve, { once: true }); video.currentTime = time; });
  }, seconds);
}
test.beforeEach(async ({ page }) => { await page.goto('/'); });

test('commandes de conférence : lecture, pause, son et retour au début', async ({ page }) => {
  await expect(page.locator('#play-video')).toBeDisabled();
  expect(await page.evaluate(data => window.visioDemo.receiveResult(data, null), realShape)).toHaveProperty('ok', false);
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
  await loadClip(page);
  await page.locator('#play-video').click();
  await expect.poll(() => page.locator('video').evaluate(v => v.currentTime)).toBeGreaterThan(0);
  await page.locator('#play-video').click();
  expect(await page.locator('video').evaluate(v => v.paused)).toBe(true);
  await page.locator('#mute-video').click();
  expect(await page.locator('video').evaluate(v => v.muted)).toBe(false);
  await page.locator('#restart-video').click();
  await expect.poll(() => page.locator('video').evaluate(v => v.currentTime)).toBeLessThan(.05);
  await page.locator('#clear-video').click();
  await expect(page.locator('#stage-empty')).toBeVisible();
  await expect(page.locator('#play-video')).toBeDisabled();
});

test('coordonnées reçues : rendu exact, bandes noires, redimensionnement et synchronisation', async ({ page }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  const media = await loadClip(page);
  expect(await page.evaluate(data => window.visioDemo.receiveTracking(data), trackingPayload(media.id))).toEqual({ ok: true });
  await expect(page.locator('#face-overlay circle')).toHaveCount(3);
  await expect(page.locator('#face-overlay')).toBeVisible();
  await expect(page.locator('#face-overlay circle').first()).toBeVisible();
  const verifyGeometry = async () => {
    const coordinates = await page.evaluate(() => {
      const stage = document.querySelector('#video-stage').getBoundingClientRect();
      const side = Math.min(stage.width, stage.height); // Test clip is square.
      const rect = document.querySelector('.face-box'); const point = document.querySelector('.landmark');
      return { x: Number(rect.getAttribute('x')), y: Number(rect.getAttribute('y')), width: Number(rect.getAttribute('width')), cx: Number(point.getAttribute('cx')), expectedX: (stage.width - side) / 2 + .2 * side, expectedY: (stage.height - side) / 2 + .1 * side, expectedWidth: .5 * side, expectedCx: (stage.width - side) / 2 + .35 * side };
    });
    expect(coordinates.x).toBeCloseTo(coordinates.expectedX, 1);
    expect(coordinates.y).toBeCloseTo(coordinates.expectedY, 1);
    expect(coordinates.width).toBeCloseTo(coordinates.expectedWidth, 1);
    expect(coordinates.cx).toBeCloseTo(coordinates.expectedCx, 1);
  };
  await verifyGeometry();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => {
    const width = Number(document.querySelector('#face-overlay').getAttribute('viewBox').split(' ')[2]);
    const bounds = document.querySelector('#video-stage').getBoundingClientRect();
    return Math.abs(width - bounds.width) < 1 && bounds.right <= innerWidth;
  })).toBe(true);
  await verifyGeometry();
  await page.locator('#toggle-tracking').click();
  await expect(page.locator('#face-overlay')).toBeHidden();
  await page.locator('#toggle-tracking').click();
  await expect(page.locator('#face-overlay circle')).toHaveCount(3);
  await expect(page.locator('#face-overlay')).toBeVisible();
  await expect(page.locator('#face-overlay circle').first()).toBeVisible();
  await seek(page, .5);
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
  await expect(page.locator('#tracking-status')).toContainText('Aucun visage détecté');
  await seek(page, 1);
  await expect(page.locator('#tracking-status')).toHaveText('Pas de coordonnées à cet instant');
  await seek(page, 2);
  await expect(page.locator('#face-overlay circle')).toHaveCount(1);
  await seek(page, 3);
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('import de coordonnées, erreurs de fichier et remplacement de vidéo', async ({ page }) => {
  const media = await loadClip(page);
  await page.locator('#open-sources').click();
  await page.locator('#tracking-file').setInputFiles({ name: 'tracking.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(trackingPayload(media.id))) });
  await expect(page.locator('#sources-dialog')).not.toBeVisible();
  await expect(page.locator('#face-overlay circle')).toHaveCount(3);
  await expect(page.locator('#face-overlay')).toBeVisible();
  await expect(page.locator('#face-overlay circle').first()).toBeVisible();
  const replacement = await loadClip(page);
  expect(replacement.id).not.toBe(media.id);
  await expect(page.locator('#face-overlay circle')).toHaveCount(0);
  const response = await page.evaluate(data => window.visioDemo.receiveTracking(data), trackingPayload(media.id));
  expect(response.ok).toBe(false);
  await page.locator('#open-sources').click();
  await expect(page.locator('#tracking-alert')).toContainText('référence');
  await page.locator('#tracking-file').setInputFiles({ name: 'tracking.json', mimeType: 'application/json', buffer: Buffer.from('{broken') });
  await expect(page.locator('#tracking-alert')).toContainText('JSON illisible');
});

test('métadonnées : attente, import, texte sûr et rapprochement explicite', async ({ page }) => {
  await page.locator('#tab-metadata').click();
  await expect(page.locator('#metadata-result')).toContainText('En attente d’intégration');
  await expect(page.locator('.metadata-check')).toHaveCount(0);
  const media = await loadClip(page);
  const data = metadataPayload(media.id);
  data.checks[0].detail = '<img src=x onerror="window.injected=true">';
  await page.locator('#metadata-file').setInputFiles({ name: 'metadata.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) });
  await expect(page.locator('.metadata-check')).toContainText('Écart à vérifier');
  await expect(page.locator('.metadata-check')).toContainText('MP4');
  await expect(page.locator('.metadata-check')).toContainText('WebM');
  await expect(page.locator('#metadata-result img')).toHaveCount(0);
  await expect(page.locator('#crosscheck-status')).toContainText('En attente');
  const result = { ...realShape, simulation: false };
  await page.evaluate(data => window.visioDemo.receiveResult(data), result);
  await expect(page.locator('#crosscheck-status')).toContainText('non associé');
  await page.evaluate(({ result, id }) => window.visioDemo.receiveResult(result, { mediaId: id }), { result, id: media.id });
  await expect(page.locator('#crosscheck-status')).toContainText('Même extrait et session déclarés');
  await page.evaluate(data => window.visioDemo.receiveMetadata(data), metadataPayload(media.id, 'different-session'));
  await expect(page.locator('#crosscheck-status')).toContainText('Sessions différentes');
  await page.evaluate(data => window.visioDemo.receiveMetadata({ ...data, simulation: true }), metadataPayload(media.id));
  await expect(page.locator('#crosscheck-status')).toContainText('Simulation');
  await page.locator('#clear-video').click();
  await expect(page.locator('.metadata-check')).toHaveCount(0);
  await expect(page.locator('#crosscheck-status')).toContainText('En attente');
});

test('réponses annexes retardées annulées au changement de vidéo', async ({ page }) => {
  const media = await loadClip(page);
  await page.evaluate(() => { const read = File.prototype.text; File.prototype.text = async function () { await new Promise(r => setTimeout(r, 600)); return read.call(this); }; });
  await page.locator('#metadata-file').setInputFiles({ name: 'metadata.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(metadataPayload(media.id))) });
  await loadClip(page);
  await page.waitForTimeout(750);
  await page.locator('#tab-metadata').click();
  await expect(page.locator('.metadata-check')).toHaveCount(0);
  await expect(page.locator('#metadata-alert')).toBeHidden();
});

test('onglets au clavier, dialogue fermé avec Échap et aperçu métadonnées', async ({ page }) => {
  await page.locator('#tab-visio').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#tab-metadata')).toBeFocused();
  await expect(page.locator('#panel-metadata')).toBeVisible();
  await page.locator('#open-sources').click();
  await expect(page.locator('#sources-dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#sources-dialog')).toBeHidden();
  await expect(page.locator('#open-sources')).toBeFocused();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: 'test-results/visio-metadata.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
