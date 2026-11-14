import { describe, expect, it } from "vitest";

import { chromaFromBuffer, estimateKey, noteName } from "@/lib/studio-key";

/** Chroma for a C major triad (C, E, G), with the tonic strongest. */
const C_MAJOR_CHROMA = [
  1, 0.05, 0.1, 0.05, 0.75, 0.1, 0.05, 0.65, 0.05, 0.1, 0.05, 0.1,
];

describe("estimateKey", () => {
  it("names the tonic and mode of a triadic chroma", () => {
    expect(estimateKey(C_MAJOR_CHROMA)).toMatchObject({ tonic: "C", mode: "major" });
  });

  it("transposes with the chroma", () => {
    // Move the tonic from C (0) to A (9): the same energy, nine semitones up.
    const rotated = new Array(12).fill(0);
    C_MAJOR_CHROMA.forEach((value, index) => {
      rotated[(index + 9) % 12] = value;
    });
    expect(estimateKey(rotated)).toMatchObject({ tonic: "A", mode: "major" });
  });

  it("refuses silence and unusable vectors", () => {
    expect(estimateKey(new Array(12).fill(0))).toBeNull();
    expect(estimateKey([1])).toBeNull();
    expect(estimateKey(null as unknown as number[])).toBeNull();
  });

  it("refuses a flat chroma where no key dominates", () => {
    expect(estimateKey(new Array(12).fill(1))).toBeNull();
  });
});

describe("noteName", () => {
  it("wraps both directions", () => {
    expect(noteName(0)).toBe("C");
    expect(noteName(9)).toBe("A");
    expect(noteName(12)).toBe("C");
    expect(noteName(-1)).toBe("B");
  });
});

describe("chromaFromBuffer", () => {
  it("puts energy in the played pitch class", () => {
    // 220 Hz = A3 (MIDI 57) → pitch class 9.
    const sampleRate = 8000;
    const length = sampleRate;
    const samples = new Float32Array(length);
    for (let index = 0; index < length; index += 1) {
      samples[index] = Math.sin((2 * Math.PI * 220 * index) / sampleRate);
    }
    const buffer = {
      sampleRate,
      length,
      numberOfChannels: 1,
      getChannelData: () => samples,
    } as unknown as AudioBuffer;
    const chroma = chromaFromBuffer(buffer);
    const peak = chroma.indexOf(Math.max(...chroma));
    expect(peak).toBe(9);
  });
});
