import { describe, expect, it } from "vitest";

import {
  customWavetables,
  designWavetable,
  findWavetable,
  saveCustomWavetable,
  wavetableCoefficients,
  wavetablePreview,
} from "@/lib/studio-wavetable";

describe("wavetable", () => {
  it("designs, clamps and saves a table", () => {
    const table = designWavetable({
      name: "Bright",
      harmonics: [1, 0.5, 2, -1, 0, 0, 0, 0],
    });
    expect(table.name).toBe("Bright");
    expect(table.harmonics).toEqual([1, 0.5, 1, 0, 0, 0, 0, 0]);

    saveCustomWavetable(table);
    expect(findWavetable(table.id)).toEqual(table);
    expect(customWavetables().some((item) => item.id === table.id)).toBe(true);
  });

  it("builds periodic-wave coefficients with the partials in imag", () => {
    const table = designWavetable({ name: "Test", harmonics: [1, 0.25, 0, 0, 0, 0, 0, 0] });
    const { real, imag } = wavetableCoefficients(table);
    expect(real[0]).toBe(0);
    expect(imag[1]).toBeCloseTo(1);
    expect(imag[2]).toBeCloseTo(0.25);
    expect(imag[3]).toBe(0);
  });

  it("draws a deterministic waveform preview", () => {
    const table = designWavetable({ name: "Test", harmonics: [1, 0.5, 0, 0, 0, 0, 0, 0] });
    const preview = wavetablePreview(table, 64);
    expect(preview).toHaveLength(64);
    expect(wavetablePreview(table, 64)).toEqual(preview);
    expect(preview.some((value) => value !== 0)).toBe(true);
  });
});
