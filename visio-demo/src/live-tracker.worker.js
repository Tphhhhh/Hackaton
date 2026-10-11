import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import { measurePixels } from './video-signals.js';

let tracker;
const sample = new OffscreenCanvas(160, 120);
const pixels = sample.getContext('2d', { willReadFrequently: true });
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
      const files = await FilesetResolver.forVisionTasks(`${data.baseUrl}wasm`, true);
      tracker = await FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: `${data.baseUrl}face_landmarker.task`, delegate: 'CPU' },
        runningMode: 'VIDEO', numFaces: 1,
        minFaceDetectionConfidence: 0.5, minFacePresenceConfidence: 0.5, minTrackingConfidence: 0.5,
      });
      self.postMessage({ type: 'ready' });
    } else if (data.type === 'frame') {
      try {
        const start = performance.now();
        const result = tracker.detectForVideo(data.bitmap, data.timestamp);
        const clamp = n => Math.max(0, Math.min(1, n));
        const faces = result.faceLandmarks.map((points, index) => {
          const landmarks = points.map(({ x, y }) => ({ x: clamp(x), y: clamp(y) }));
          const xs = landmarks.map(p => p.x), ys = landmarks.map(p => p.y);
          const x = Math.min(...xs), y = Math.min(...ys);
          return { id: `live-${index}`, landmarks, box: { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y } };
        });
        // Sample unmarked pixels. Failure of an optional measurement must not stop tracking.
        let metrics = null;
        try {
          sample.height = Math.max(24, Math.round(160 * data.bitmap.height / data.bitmap.width));
          pixels.drawImage(data.bitmap, 0, 0, sample.width, sample.height);
          metrics = measurePixels(pixels.getImageData(0, 0, sample.width, sample.height).data,
            sample.width, sample.height, faces.length === 1 ? faces[0] : null);
        } catch { /* Missing measurements remain unknown in the console. */ }
        self.postMessage({ type: 'result', faces, metrics, bitmap: data.bitmap, timestamp: data.timestamp, inferenceMs: performance.now() - start }, [data.bitmap]);
      } finally { data.bitmap.close(); }
    }
  } catch (error) { self.postMessage({ type: 'error', message: error.message }); }
};
