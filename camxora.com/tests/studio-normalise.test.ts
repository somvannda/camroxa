import { describe, expect, it } from "vitest";

import {
  EXPORT_TARGET_PEAK_DB,
  normaliseChannels,
  normaliseGain,
  peakOf,
} from "@/lib/studio-normalise";

/** Linear amplitude for a dBFS value, so expectations read like an engineer's. */
function amp(db: number): number {
  return Math.pow(10, db / 20);
}

describe("peakOf", () => {
  it("finds the loudest sample across every channel", () => {
    expect(peakOf([new Float32Array([0.1, -0.8]), new Float32Array([0.2, 0.05])])).toBeCloseTo(0.8, 6);
  });

  it("is zero for silence and for empty input", () => {
    expect(peakOf([new Float32Array(4)])).toBe(0);
    expect(peakOf([])).toBe(0);
  });
});

describe("normaliseGain", () => {
  it("boosts a quiet mix to the -1 dBFS target", () => {
    const gain = normaliseGain([new Float32Array([0.25])]);
    expect(gain).toBeCloseTo(amp(EXPORT_TARGET_PEAK_DB) / 0.25, 6);
  });

  it("cuts a mix that is over the target", () => {
    const gain = normaliseGain([new Float32Array([1])]);
    expect(gain).toBeLessThan(1);
    expect(gain).toBeCloseTo(amp(-1), 6);
  });

  it("leaves silence alone instead of amplifying noise to a huge gain", () => {
    expect(normaliseGain([new Float32Array(8)])).toBe(1);
  });

  it("ignores targets that are not a usable attenuation point", () => {
    const samples = [new Float32Array([0.5])];
    expect(normaliseGain(samples, 0)).toBe(1);
    expect(normaliseGain(samples, 3)).toBe(1);
    expect(normaliseGain(samples, Number.NaN)).toBe(1);
  });
});

describe("normaliseChannels", () => {
  it("applies one gain to all channels and leaves the input untouched", () => {
    const left = new Float32Array([0.5, -0.25]);
    const right = new Float32Array([0.125, 0]);
    const result = normaliseChannels([left, right], EXPORT_TARGET_PEAK_DB);

    expect(peakOf(result.channels)).toBeCloseTo(amp(EXPORT_TARGET_PEAK_DB), 5);
    // Same gain on both channels, so the stereo image is preserved.
    expect(result.channels[0][0] / left[0]).toBeCloseTo(result.channels[1][0] / right[0], 6);
    // The caller can still measure the raw render.
    expect(left[0]).toBe(0.5);
  });

  it("clamps to full scale if rounding overshoots", () => {
    const result = normaliseChannels([new Float32Array([0.99999999])], -0.0001);
    expect(Math.max(...result.channels[0])).toBeLessThanOrEqual(1);
  });

  it("returns the same channels when there is nothing to normalise", () => {
    const channels = [new Float32Array(4)];
    expect(normaliseChannels(channels).channels).toBe(channels);
    expect(normaliseChannels(channels).gain).toBe(1);
  });
});
