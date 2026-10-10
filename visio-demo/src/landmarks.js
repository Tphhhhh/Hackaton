// Select only the overlay; MediaPipe still computes all 478 landmarks.
const LIGHT = [10, 67, 109, 338, 297, 152, 172, 397, 234, 454, 33, 133, 159, 145, 362, 263, 386, 374, 70, 105, 107, 336, 334, 300, 1, 4, 98, 327, 61, 291, 13, 14];
export function visibleLandmarks(points, mode) {
  if (mode === 'none') return [];
  if (mode === 'full' || points.length < 468) return points;
  return LIGHT.map(index => points[index]).filter(Boolean);
}
