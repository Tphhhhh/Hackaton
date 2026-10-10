// Presentation-only adapter. Never feed these values into receiveResult/GenD.
export function createDemoScores() {
  let left = null, right = null, previous = null;
  return {
    sample(timestamp, { facePresent, filteredFacePresent = facePresent, filterApplied }) {
      if (!facePresent && !filteredFacePresent) { left = right = previous = null; return { original: null, filtered: null, simulation: true }; }
      const seconds = timestamp / 1000;
      const low = 8 + 2 * Math.sin(seconds * .8);
      const high = filterApplied ? 93 + 2 * Math.sin(seconds * .65) : low;
      const blend = previous === null ? 1 : 1 - Math.exp(-Math.min(250, timestamp - previous) / 650);
      left = left === null ? low : left + (low - left) * blend;
      right = right === null ? high : right + (high - right) * blend;
      previous = timestamp;
      return { original: facePresent ? Math.round(left) : null, filtered: filteredFacePresent ? Math.round(right) : null, simulation: true };
    },
    reset() { left = right = previous = null; },
  };
}
