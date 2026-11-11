import { describe, expect, it } from "vitest";

import {
  DEFAULT_CLIP_AUDIO,
  clipRate,
  dbToGain,
  pitchToRate,
  planClipPlayback,
  quantizeStep,
  sanitizeClipAudio,
  speedToRate,
} from "@/lib/studio-clip-audio";

describe("sanitizeClipAudio", () => {
  it("defaults when the document has nothing", () => {
    expect(sanitizeClipAudio(undefined)).toEqual(DEFAULT_CLIP_AUDIO);
  });

  it("clamps the captured ranges", () => {
    expect(
      sanitizeClipAudio({ gainDb: -80, pitch: 40, speed: 10, loop: 1, reverse: "yes" })
    ).toEqual({ gainDb: -24, loop: true, reverse: true, pitch: 12, speed: 50 });
  });
});

describe("rate and gain math", () => {
  it("turns decibels into gain", () => {
    expect(dbToGain(0)).toBe(1);
    expect(dbToGain(-6)).toBeCloseTo(0.5012, 3);
    expect(dbToGain(12)).toBeCloseTo(3.981, 2);
  });

  it("turns semitones into a rate", () => {
    expect(pitchToRate(0)).toBe(1);
    expect(pitchToRate(12)).toBe(2);
    expect(pitchToRate(-12)).toBe(0.5);
    expect(pitchToRate(7)).toBeCloseTo(1.4983, 3);
  });

  it("turns the speed percent into a rate", () => {
    expect(speedToRate(100)).toBe(1);
    expect(speedToRate(50)).toBe(0.5);
    expect(speedToRate(200)).toBe(2);
  });

  it("multiplies pitch and speed into the clip rate", () => {
    expect(clipRate({ ...DEFAULT_CLIP_AUDIO, pitch: 12, speed: 50 })).toBe(1);
    expect(clipRate({ ...DEFAULT_CLIP_AUDIO, pitch: 0, speed: 150 })).toBe(1.5);
  });
});

describe("planClipPlayback", () => {
  const base = {
    bufferDuration: 8,
    clipDuration: 4,
    intoClip: 0,
    offset: 0,
    rate: 1,
    reverse: false,
    loop: false,
  };

  it("plays the clip's window at its rate", () => {
    expect(planClipPlayback(base)).toEqual({
      bufferStart: 0,
      bufferLength: 4,
      loop: false,
      loopStart: 0,
      loopEnd: 0,
    });
    // Rate 2 consumes twice the buffer for the same timeline length.
    expect(planClipPlayback({ ...base, rate: 2 }).bufferLength).toBe(8);
    // Starting mid-clip advances the buffer position the same way.
    expect(planClipPlayback({ ...base, intoClip: 1 }).bufferStart).toBe(1);
  });

  it("mirrors the window when reversed", () => {
    // 4 s of an 8 s buffer, reversed, starts 4 s from the end of the mirror.
    expect(planClipPlayback({ ...base, reverse: true })).toEqual({
      bufferStart: 4,
      bufferLength: 4,
      loop: false,
      loopStart: 0,
      loopEnd: 0,
    });
  });

  it("loops from the clip offset to the end of the source", () => {
    expect(planClipPlayback({ ...base, loop: true, offset: 2 })).toEqual({
      bufferStart: 2,
      loop: true,
      loopStart: 2,
      loopEnd: 8,
    });
  });

  it("mirrors the loop region when reversed", () => {
    expect(planClipPlayback({ ...base, loop: true, reverse: true, offset: 2 })).toEqual({
      bufferStart: 6,
      loop: true,
      loopStart: 0,
      loopEnd: 6,
    });
  });

  it("never reads past the buffer", () => {
    const plan = planClipPlayback({ ...base, clipDuration: 20 });
    expect(plan.bufferLength).toBe(8);
  });
});

describe("quantizeStep", () => {
  it("maps note values onto a 4/4 bar", () => {
    expect(quantizeStep(2, "1/4", false)).toBe(0.5);
    expect(quantizeStep(2, "1/8", false)).toBe(0.25);
    expect(quantizeStep(2, "1/16", false)).toBe(0.125);
  });

  it("divides by three for triplets", () => {
    expect(quantizeStep(2, "1/8", true)).toBeCloseTo(1 / 6, 5);
  });
});
