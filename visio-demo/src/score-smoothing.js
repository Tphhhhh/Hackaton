// Display-only exponential average: 25% new measurement, 75% history.
// Identical treatment of rises and falls; never clamp a low model prediction.
export function createScoreSmoother() {
  let value = null;
  return {
    sample(score) {
      if (!Number.isFinite(score) || score < 0 || score > 1) {
        value = null;
        return null;
      }
      value = value === null ? score : .25 * score + .75 * value;
      return value;
    },
    reset() { value = null; },
  };
}
