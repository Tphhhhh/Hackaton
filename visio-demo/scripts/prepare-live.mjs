// Fetch only the public model at setup time; runtime requests stay same-origin.
import { mkdir, cp, readFile, writeFile, rename } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const expected = '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff';
const valid = bytes => createHash('sha256').update(bytes).digest('hex') === expected;
const root = new URL('../', import.meta.url);
const assets = new URL('public/live-assets/', root);
await mkdir(assets, { recursive: true });
await cp(new URL('node_modules/@mediapipe/tasks-vision/wasm/', root), new URL('wasm/', assets), { recursive: true });
const model = new URL('face_landmarker.task', assets);
let cached = false;
try { cached = valid(await readFile(model)); } catch {}
if (!cached) {
  const urls = [
    'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
    'https://github.com/sanderdesnaijer/mediapipe-model-mirrors/releases/download/v1/face_landmarker.task',
  ];
  let downloaded = false;
  for (const url of urls) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (!valid(bytes)) throw new Error('Model SHA-256 mismatch');
      const temporary = new URL('face_landmarker.task.tmp', assets);
      await writeFile(temporary, bytes);
      await rename(temporary, model);
      downloaded = true;
      break;
    } catch (error) { console.warn(`Model download: ${error.message}`); }
  }
  if (!downloaded) throw new Error('Cannot prepare webcam model. Check network access, then run npm run prepare:live.');
}
console.log('Local webcam model and WebAssembly assets ready.');
