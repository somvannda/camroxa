import { describe, expect, it } from "vitest";

import { barBeatAt, parseBeatsPerBar, secondsPerBar } from "@/lib/studio-signature";

describe("parseBeatsPerBar", () => {
  it("reads the numerator", () => {
    expect(parseBeatsPerBar("4/4")).toBe(4);
    expect(parseBeatsPerBar("3/4")).toBe(3);
    expect(parseBeatsPerBar("6/8")).toBe(6);
    expect(parseBeatsPerBar(" 2 / 4 ")).toBe(2);
  });

  it("falls back to four for anything unparseable", () => {
    expect(parseBeatsPerBar("")).toBe(4);
    expect(parseBeatsPerBar(null)).toBe(4);
    expect(parseBeatsPerBar("common")).toBe(4);
    expect(parseBeatsPerBar("0/4")).toBe(4);
    expect(parseBeatsPerBar("99/4")).toBe(16);
  });
});

describe("secondsPerBar", () => {
  it("is four beats at 4/4 and three at 3/4", () => {
    expect(secondsPerBar(120, "4/4")).toBe(2);
    expect(secondsPerBar(120, "3/4")).toBe(1.5);
    expect(secondsPerBar(60, "6/8")).toBe(6);
  });

  it("guards a nonsense tempo", () => {
    expect(secondsPerBar(0, "4/4")).toBe(2);
    expect(secondsPerBar(Number.NaN, "4/4")).toBe(2);
  });
});

describe("barBeatAt", () => {
  it("counts bars in the project's meter", () => {
    // 120 BPM: a beat is 0.5 s; 4/4 bars are 2 s, 3/4 bars are 1.5 s.
    expect(barBeatAt(0, 120, "4/4")).toEqual({ bar: 1, beat: 1 });
    expect(barBeatAt(2, 120, "4/4")).toEqual({ bar: 2, beat: 1 });
    expect(barBeatAt(4.5, 120, "3/4")).toEqual({ bar: 4, beat: 1 });
    expect(barBeatAt(4.4, 120, "3/4")).toEqual({ bar: 3, beat: 3 });
  });

  it("never reports positions before zero", () => {
    expect(barBeatAt(-3, 120, "4/4")).toEqual({ bar: 1, beat: 1 });
  });
});
