import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

let tracker;
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
      const files = await FilesetResolver.forVisionTasks(`${data.baseUrl}wasm`, true);
      tracker = await FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: `${data.baseUrl}face_landmarker.task`, delegate: 'CPU' },
        runningMode: 'IMAGE', numFaces: 1,
        minFaceDetectionConfidence: 0.5, minFacePresenceConfidence: 0.5, minTrackingConfidence: 0.5,
      });
      const ready = { type: 'ready' };
      if (data.filter) {
        let referenceImage;
        try {
          const response = await fetch(new URL('../filters/brad-pitt.jpg', data.baseUrl), { signal: AbortSignal.timeout(8000) });
          if (!response.ok) throw new Error('Portrait indisponible');
          referenceImage = await createImageBitmap(await response.blob());
          const result = tracker.detect(referenceImage);
          if (!result.faceLandmarks.length) throw new Error('Visage du portrait non détecté');
          ready.referencePoints = result.faceLandmarks[0].slice(0, 468);
          ready.triangles = [];
          const edges = FaceLandmarker.FACE_LANDMARKS_TESSELATION;
          for (let i = 0; i < edges.length; i += 3) ready.triangles.push(edges[i].start, edges[i].end, edges[i + 1].end);
          ready.oval = [...new Set(FaceLandmarker.FACE_LANDMARKS_FACE_OVAL.flatMap(edge => [edge.start, edge.end]))];
          ready.referenceImage = referenceImage;
        } catch { referenceImage?.close(); ready.filterError = 'Filtre intégré indisponible. Relancez la caméra ou branchez un flux externe.'; }
      }
      await tracker.setOptions({ runningMode: 'VIDEO' });
      self.postMessage(ready, ready.referenceImage ? [ready.referenceImage] : []);
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
        self.postMessage({ type: 'result', faces, bitmap: data.bitmap, timestamp: data.timestamp, inferenceMs: performance.now() - start }, [data.bitmap]);
      } finally { data.bitmap.close(); }
    }
  } catch (error) { self.postMessage({ type: 'error', message: error.message }); }
};
