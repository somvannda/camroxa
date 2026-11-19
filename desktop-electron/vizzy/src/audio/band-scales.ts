/**
 * Frequency placements for the pre-wasm analyser fallback.
 *
 * The reference computes band edges inside `FFT.wasm` (`make_freq_bands_lookup`,
 * decompiled from `public/vendor/vizzy/FFT.wasm`). Bands are placed in
 * transform space: the min/max Hz are mapped through the selected scale, the
 * band centres run from the low to the high endpoint inclusive, and each band's
 * edges are half a step beyond its centre.
 *
 * The transforms below are the wasm's exact formulas; the fallback only exists
 * until the reference module loads, but it should place bands identically.
 */

export type BandScale =
  | "linear"
  | "log"
  | "mel"
  | "critical bands"
  | "ERB"
  | "sinh"
  | "nth root"
  | string;

const sinhFactor = (hzLinearFactor: number): number => 10 ** (4 * hzLinearFactor);

/** Hz → transform space. */
export function scaleForward(hz: number, scale: BandScale, hzLinearFactor = 0.5): number {
  const frequency = Math.max(1e-6, hz);
  switch (scale) {
    case "log":
      return Math.log(frequency);
    case "mel":
      return Math.log(1 + frequency / 700);
    case "critical bands":
      return (26.81 * frequency) / (frequency + 1960) - 0.53;
    case "ERB":
      return Math.log(1 + 0.00437 * frequency);
    case "sinh":
      return Math.asinh(frequency / sinhFactor(hzLinearFactor));
    case "nth root":
      return frequency ** (1 / (11 - 10 * hzLinearFactor));
    default:
      return frequency;
  }
}

/** Transform space → Hz. */
export function scaleInverse(value: number, scale: BandScale, hzLinearFactor = 0.5): number {
  switch (scale) {
    case "log":
      return Math.exp(value);
    case "mel":
      return (Math.exp(value) - 1) * 700;
    case "critical bands": {
      const denominator = 26.81 / (value + 0.53) - 1;
      return denominator > 1e-9 ? 1960 / denominator : 0;
    }
    case "ERB":
      return (Math.exp(value) - 1) * 228.832952;
    case "sinh":
      return Math.sinh(value) * sinhFactor(hzLinearFactor);
    case "nth root":
      return Math.max(0, value) ** (11 - 10 * hzLinearFactor);
    default:
      return value;
  }
}

/**
 * Frequency at position `t` between `minHz` and `maxHz` for a scale.
 * `t` may lie slightly outside 0..1: the reference's outer bands use edges half
 * a step beyond the endpoint centres.
 */
export function frequencyAtFraction(
  t: number,
  minHz: number,
  maxHz: number,
  scale: BandScale,
  hzLinearFactor = 0.5,
): number {
  const position = Number.isFinite(t) ? t : 0;
  const min = Math.max(1, Math.min(minHz, maxHz));
  const max = Math.max(min + 1e-6, Math.max(minHz, maxHz));
  const low = scaleForward(min, scale, hzLinearFactor);
  const high = scaleForward(max, scale, hzLinearFactor);
  return scaleInverse(low + position * (high - low), scale, hzLinearFactor);
}
