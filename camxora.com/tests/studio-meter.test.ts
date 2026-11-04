import { describe, expect, it } from "vitest";

import { analyse, formatMeter, toDb } from "@/lib/studio-meter";

function sine(amplitude: number, freq = 1000, seconds = 1, rate = 44100): Float32Array {
  const samples = new Float32Array(Math.round(seconds * rate));
  for (let i = 0; i < samples.length; i++) {
    samples[i] = amplitude * Math.sin((2 * Math.PI * freq * i) / rate);
  }
  return samples;
}

describe("toDb", () => {
  it("maps unity to 0 dB and silence to the floor", () => {
    expect(toDb(1)).toBeCloseTo(0, 6);
    expect(toDb(0)).toBe(-60);
  });

  it("maps known ratios", () => {
    expect(toDb(0.5)).toBeCloseTo(-6.02, 2);
    expect(toDb(0.25)).toBeCloseTo(-12.04, 2);
  });
});

describe("analyse", () => {
  it("reads peak and RMS of a full-scale sine", () => {
    const reading = analyse(sine(1));
    expect(reading.peak).toBeCloseTo(1, 2);
    expect(reading.rms).toBeCloseTo(Math.SQRT1_2, 2);
    expect(reading.peakDb).toBeCloseTo(0, 1);
    expect(reading.rmsDb).toBeCloseTo(-3.01, 1);
  });

  it("reads a half-amplitude sine as -6 dBFS peak and -9 dBFS RMS", () => {
    const reading = analyse(sine(0.5));
    expect(reading.peakDb).toBeCloseTo(-6.02, 1);
    expect(reading.rmsDb).toBeCloseTo(-9.03, 1);
  });

  it("keeps the 4x inter-sample estimate at or above sample peak", () => {
    const reading = analyse(sine(0.5));
    expect(reading.truePeak4x).toBeGreaterThanOrEqual(reading.peak);
    // Interpolation cannot invent more than the local maximum for a smooth sine.
    expect(reading.truePeak4x).toBeLessThan(reading.peak * 1.05);
  });

  it("reports silence as the floor", () => {
    const reading = analyse(new Float32Array(128));
    expect(reading.peak).toBe(0);
    expect(reading.peakDb).toBe(-60);
  });
});

describe("formatMeter", () => {
  it("formats a reading and handles idle", () => {
    expect(formatMeter(null)).toBe("—");
    expect(formatMeter(analyse(sine(0.5)))).toMatch(/-6\.\d dB pk/);
    expect(formatMeter(analyse(new Float32Array(16)))).toBe("-inf dB pk");
  });
});
