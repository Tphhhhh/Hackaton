import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
const example = name => JSON.parse(readFileSync(new URL(`../reference/examples/${name}.json`, import.meta.url)));
const upload = (page, value, name = 'result.json') => page.locator('#json-file').setInputFiles({ name, mimeType: 'application/json', buffer: Buffer.from(typeof value === 'string' ? value : JSON.stringify(value)) });
const fixture = seconds => new URL(`./fixtures/simulation-${seconds}s.mp4`, import.meta.url).pathname;
test.beforeEach(async ({ page }) => { await page.goto('/'); });
async function chooseExample(page, id) {
  await page.locator('#open-sources').click();
  await page.locator(`[data-example="${id}"]`).click();
}


test('six simulations, détecteurs, observations, erreurs et effacement', async ({ page }) => {
  await expect(page.getByText('Les résultats viendront ici.')).toBeVisible();
  const states = [ ['verify', 'indice à vérifier', 'Terminée'], ['no_signal', 'aucun indice détecté', 'Terminée'], ['indeterminate', 'analyse insuffisante', 'Terminée'], ['partial', 'analyse insuffisante', 'Partielle'], ['failed', 'analyse insuffisante', 'Échec'], ['cancelled', 'analyse insuffisante', 'Annulée'] ];
  for (const [id, label, status] of states) {
    await chooseExample(page, id);
    await expect(page.locator('.conclusion h3')).toHaveText(label);
    await expect(page.locator('.result-source')).toContainText('simulation');
    await expect(page.locator('.result-source')).toContainText(status);
    await expect(page.locator('.limits')).toContainText('Scores exploratoires');
  }
  await chooseExample(page, 'partial');
  await expect(page.locator('.detector-card')).toHaveCount(2);
  await expect(page.locator('.error-card').first()).toContainText('ModelUnavailable');
  await expect(page.locator('.detector-card').last()).toContainText('Non disponible');
  await page.locator('.observations summary').first().click();
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await page.locator('#clear-result').click();
  await expect(page.locator('.conclusion')).toHaveCount(0);
  await expect(page.locator('#examples [aria-pressed="true"]')).toHaveCount(0);
});

test('import réel et point d’intégration suivent la même validation', async ({ page }) => {
  const data = example('verify'); data.simulation = false;
  await upload(page, data);
  await expect(page.locator('.result-source')).toContainText('résultat importé');
  await expect(page.locator('.conclusion h3')).toHaveText('indice à vérifier');
  await expect(page.locator('.association-note')).toBeVisible();
  const received = await page.evaluate(data => window.visioDemo.receiveResult(data), example('failed'));
  expect(received.ok).toBe(true);
  await expect(page.locator('.conclusion h3')).toHaveText('analyse insuffisante');
  expect(await page.evaluate(() => window.visioDemo.receiveResult({ invalid: true }))).toHaveProperty('ok', false);
  await expect(page.locator('#json-alert')).toContainText('contrat JSON invalide');
  await expect(page.locator('.conclusion')).toHaveCount(0);
});

test('fichiers JSON invalides : extension, vide, syntaxe, taille, contrat', async ({ page }) => {
  for (const [value, name, message] of [
    [example('verify'), 'result.txt', 'extension .json'],
    ['', 'empty.json', 'vide'],
    ['{broken', 'bad.json', 'JSON illisible'],
    ['x'.repeat(1024 * 1024 + 1), 'large.json', '1 Mo'],
    [{ ...example('verify'), coverage: 7 }, 'invalid.json', '/coverage'],
    [{ ...example('verify'), schema_version: '99' }, 'future.json', '/schema_version'],
  ]) {
    await chooseExample(page, 'verify');
    await upload(page, value, name);
    await expect(page.locator('#json-alert')).toContainText(message);
    await expect(page.locator('.conclusion')).toHaveCount(0);
  }
  await upload(page, example('no_signal'));
  await expect(page.locator('#json-alert')).toBeHidden();
  await expect(page.locator('.conclusion h3')).toHaveText('aucun indice détecté');
});

test('contenu importé rendu en texte et erreurs globales null refusées', async ({ page }) => {
  const data = example('verify');
  data.limitations = ['<img src=x onerror="window.injected=true">'];
  data.detectors['<script>alert(1)</script>'] = data.detectors.dima;
  await upload(page, data);
  await expect(page.locator('.limits')).toContainText('<img src=x');
  await expect(page.locator('#result img, #result script')).toHaveCount(0);
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  const failure = example('failed'); failure.errors = [null];
  await upload(page, failure);
  await expect(page.locator('#json-alert')).toContainText('/errors/0');
  await expect(page.locator('.conclusion')).toHaveCount(0);
});

test('une lecture JSON retardée ne remplace pas une simulation plus récente', async ({ page }) => {
  await page.evaluate(() => {
    const original = File.prototype.text;
    File.prototype.text = async function () { await new Promise(resolve => setTimeout(resolve, 500)); return original.call(this); };
  });
  await upload(page, example('verify'));
  await chooseExample(page, 'failed');
  await page.waitForTimeout(650);
  await expect(page.locator('.result-source')).toContainText('Échec');
});

test('vidéos locales 10, 12 et 20 s, lecture, retrait et URL libérées', async ({ page }) => {
  await page.evaluate(() => { window.revoked = []; const original = URL.revokeObjectURL; URL.revokeObjectURL = url => { window.revoked.push(url); original.call(URL, url); }; });
  const requests = [];
  page.on('request', req => requests.push(req));
  for (const seconds of [10, 12, 20]) {
    await page.locator('#video-file').setInputFiles(fixture(seconds));
    await expect(page.locator('#video-info')).toContainText('Prête à lire');
    await expect(page.locator('video')).toBeVisible();
    expect(await page.locator('video').evaluate(v => v.duration)).toBe(seconds);
  }
  await page.locator('video').evaluate(async v => { v.muted = true; await v.play(); });
  await expect.poll(() => page.locator('video').evaluate(v => v.currentTime)).toBeGreaterThan(0);
  await chooseExample(page, 'verify');
  await expect(page.locator('.conclusion')).toContainText('ne décrit pas la vidéo sélectionnée');
  await page.locator('#clear-video').click();
  await expect(page.locator('video')).toHaveCount(0);
  expect(await page.evaluate(() => window.revoked.length)).toBe(3);
  expect(requests.filter(r => (['fetch', 'xhr'].includes(r.resourceType()) && !r.url().endsWith('/api/status')) || r.method() !== 'GET')).toHaveLength(0);
  expect(requests.filter(r => !r.url().startsWith('blob:') && !r.url().startsWith('http://127.0.0.1:5179'))).toHaveLength(0);
});

test('rejette les vidéos hors durée, vides, invalides et mal nommées', async ({ page }) => {
  for (const seconds of [1, 21]) {
    await page.locator('#video-file').setInputFiles(fixture(seconds));
    await expect(page.locator('#video-alert')).toContainText('2 à 20 secondes');
    await expect(page.locator('video')).toHaveCount(0);
  }
  for (const [name, content, message] of [['empty.mp4', '', 'vide'], ['corrupt.mp4', 'not a movie', 'illisible'], ['wrong.txt', 'not a movie', 'Format non pris en charge']]) {
    await page.locator('#video-file').setInputFiles({ name, mimeType: 'video/mp4', buffer: Buffer.from(content) });
    await expect(page.locator('#video-alert')).toContainText(message);
    await expect(page.locator('video')).toHaveCount(0);
  }
  await page.locator('#video-file').setInputFiles(fixture(12));
  await expect(page.locator('#video-alert')).toBeHidden();
  await expect(page.locator('video')).toBeVisible();
});

test('navigation clavier et présentation mobile sans débordement', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#open-sources').click();
  await page.locator('[data-example="partial"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.conclusion h3')).toHaveText('analyse insuffisante');
  await page.locator('.observations summary').first().focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('tbody').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/visio-mobile.png', fullPage: true });
});

test('vue bureau et absence d’erreur JavaScript sur les parcours', async ({ page }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.screenshot({ path: 'test-results/visio-empty.png', fullPage: true });
  for (const id of ['no_signal', 'indeterminate', 'failed', 'cancelled', 'verify', 'partial']) await chooseExample(page, id);
  await page.screenshot({ path: 'test-results/visio-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('importe le fichier réel InvalidMedia signalé par ISSUE-001', async ({ page }) => {
  const path = new URL('./fixtures/actual-failure.json', import.meta.url).pathname;
  const data = JSON.parse(readFileSync(path));
  await page.locator('#json-file').setInputFiles(path);
  await expect(page.locator('#json-alert')).toBeHidden();
  await expect(page.locator('.result-source')).toContainText('résultat importé');
  await expect(page.locator('.result-source')).toContainText('Échec');
  await expect(page.locator('.result-source')).not.toContainText('simulation');
  await expect(page.locator('.conclusion h3')).toHaveText('analyse insuffisante');
  await expect(page.locator('.error-card')).toHaveCount(1);
  await expect(page.locator('.error-card')).toContainText('InvalidMedia');
  await expect(page.locator('.error-card')).toContainText(data.errors[0].message);
  await expect(page.locator('.error-card')).toContainText(data.errors[0].action);
  await expect(page.locator('.detector-card')).toHaveCount(0);
  // The future engine integration must accept the same captured output.
  expect(await page.evaluate(data => window.visioDemo.receiveResult(data), data)).toEqual({ ok: true });
  await expect(page.locator('.error-card')).toContainText('InvalidMedia');
});
