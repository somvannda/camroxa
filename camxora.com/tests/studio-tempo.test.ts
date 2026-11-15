import { describe, expect, it } from "vitest";

import {
  autoStretchSpeed,
  detectTempo,
  stretchSpeedPercent,
} from "@/lib/studio-tempo";

/** Build a peak envelope with onsets at the given fractions. */
function peaksWithOnsets(fractions: number[], buckets = 1024): number[] {
  const peaks = new Array(buckets).fill(0.02);
  for (const fraction of fractions) {
    const index = Math.round(fraction * (buckets - 1));
    peaks[Math.min(buckets - 1, index)] = 1;
  }
  return peaks;
}

describe("detectTempo", () => {
  it("finds a steady beat from the onset spacing", () => {
    // 120 BPM for 8 s: hits every 0.5 s.
    const fractions = Array.from({ length: 17 }, (_, index) => (index * 0.5) / 8);
    const guess = detectTempo(peaksWithOnsets(fractions), 8);
    expect(guess).not.toBeNull();
    expect(guess?.bpm).toBeGreaterThanOrEqual(118);
    expect(guess?.bpm).toBeLessThanOrEqual(122);
    expect(guess?.confidence).toBeGreaterThan(0.6);
  });

  it("refuses audio without a steady beat", () => {
    const fractions = [0.02, 0.11, 0.39, 0.41, 0.72];
    expect(detectTempo(peaksWithOnsets(fractions), 5)).toBeNull();
  });

  it("refuses silence and missing peaks", () => {
    expect(detectTempo(null, 4)).toBeNull();
    expect(detectTempo(new Array(1024).fill(0), 4)).toBeNull();
  });
});

describe("stretchSpeedPercent", () => {
  it("scales the source tempo onto the project tempo", () => {
    expect(stretchSpeedPercent(120, 174)).toBe(145);
    expect(stretchSpeedPercent(90, 120)).toBe(133);
  });

  it("clamps to the Clip Settings range", () => {
    expect(stretchSpeedPercent(40, 200)).toBe(200);
    expect(stretchSpeedPercent(300, 60)).toBe(50);
  });
});

describe("autoStretchSpeed", () => {
  const fractions = Array.from({ length: 17 }, (_, index) => (index * 0.5) / 8);

  it("stretches only when the setting is on", () => {
    expect(autoStretchSpeed(peaksWithOnsets(fractions), 8, 174, false)).toBeNull();
    expect(autoStretchSpeed(peaksWithOnsets(fractions), 8, 174, true)).toMatchObject({
      speed: 145,
      sourceBpm: 120,
    });
  });

  it("leaves an already-matched clip alone", () => {
    expect(autoStretchSpeed(peaksWithOnsets(fractions), 8, 120, true)).toBeNull();
  });
});
