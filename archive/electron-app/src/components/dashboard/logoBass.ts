export function computeLogoBassFromFreq(freq: Uint8Array, sampleRate: number) {
  const ny = Math.max(1, sampleRate) / 2;
  const a = clamp(20 / ny, 0, 1);
  const b = clamp(200 / ny, 0, 1);
  const ia = Math.floor(a * (freq.length - 1));
  const ib = Math.floor(b * (freq.length - 1));
  let sum = 0;
  let n = 0;
  for (let i = ia; i <= ib; i++) {
    sum += freq[i] ?? 0;
    n++;
  }
  const raw = n ? sum / n / 255 : 0;
  return clamp(Math.pow(raw, 0.65), 0, 1);
}

export function computeLogoScale(baseScale: number, logoBass: number, reactBass: number) {
  const s = Math.max(0.05, Math.min(4, baseScale)) * (1 + clamp(logoBass, 0, 1) * clamp(reactBass, 0, 2));
  return clamp(s, 0.05, 4);
}

function clamp(v: number, a: number, b: number) {
  return Math.max(a, Math.min(b, v));
}
