import { describe, expect, it } from "vitest";

import {
  sanitizeWavetables,
  WAVETABLE_PRESETS,
  wavetableIdFromInstrument,
  wavetableInstrumentId,
  wavetableSamples,
} from "@/lib/studio-wavetable";

describe("sanitizeWavetables", () => {
  it("keeps named tables and clamps partials", () => {
    const tables = sanitizeWavetables([
      { id: "wt-a", name: "Bright", harmonics: [2, -1, 0.5] },
      { id: "wt-a", name: "Duplicate" },
      { nope: true },
    ]);
    expect(tables).toHaveLength(1);
    expect(tables[0].name).toBe("Bright");
    expect(tables[0].harmonics[0]).toBe(1);
    expect(tables[0].harmonics[1]).toBe(0);
    expect(tables[0].harmonics[2]).toBe(0.5);
  });

  it("returns an empty list for junk", () => {
    expect(sanitizeWavetables(null)).toEqual([]);
    expect(sanitizeWavetables("nope")).toEqual([]);
  });
});

describe("wavetable instrument ids", () => {
  it("round-trips", () => {
    expect(wavetableIdFromInstrument(wavetableInstrumentId("wt-1"))).toBe("wt-1");
  });

  it("ignores built-in instruments", () => {
    expect(wavetableIdFromInstrument("triangle")).toBeNull();
    expect(wavetableIdFromInstrument("wavetable:")).toBeNull();
  });
});

describe("wavetableSamples", () => {
  it("draws one normalised cycle", () => {
    const samples = wavetableSamples(WAVETABLE_PRESETS[0].harmonics, 64);
    expect(samples).toHaveLength(64);
    expect(Math.max(...samples.map((value) => Math.abs(value)))).toBeCloseTo(1, 5);
  });

  it("a single partial is a sine", () => {
    const samples = wavetableSamples([1], 4);
    expect(samples[0]).toBeCloseTo(0, 6);
    expect(samples[1]).toBeCloseTo(1, 6);
    expect(samples[2]).toBeCloseTo(0, 6);
    expect(samples[3]).toBeCloseTo(-1, 6);
  });
});
