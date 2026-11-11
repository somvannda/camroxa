import { describe, expect, it } from "vitest";

import { detectOnsets } from "@/lib/studio-peaks";
import {
  DEFAULT_WARP,
  generateWarpMarkers,
  moveWarpMarker,
  quantiseWarpMarkers,
  sanitizeWarp,
} from "@/lib/studio-warp";

const bar = { secondsPerBar: 2, beatsPerBar: 4 };

function envelope(pattern: number[]): number[] {
  return pattern.flatMap((level) => Array.from({ length: 8 }, () => level));
}

describe("detectOnsets", () => {
  it("finds the rise out of silence", () => {
    // 8 quiet buckets, then loud: the rise lands on bucket 8 of 16.
    const peaks = envelope([0.02, 0.9]);
    expect(detectOnsets(peaks)).toEqual([0, 0.5333333333333333]);
  });

  it("ignores wobble inside a loud section", () => {
    const peaks = envelope([0.9, 0.6, 0.9, 0.6]);
    expect(detectOnsets(peaks)).toEqual([0]);
  });

  it("returns nothing without peaks", () => {
    expect(detectOnsets(null)).toEqual([]);
    expect(detectOnsets([0, 0, 0])).toEqual([]);
  });
});

describe("generateWarpMarkers", () => {
  it("places On Beat markers on every beat", () => {
    const markers = generateWarpMarkers({ mode: "beat", duration: 4, ...bar });
    expect(markers.map((marker) => marker.time)).toEqual([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]);
    // Source positions follow the clip offset so they still point into the file.
    const shifted = generateWarpMarkers({ mode: "beat", duration: 4, offset: 2, ...bar });
    expect(shifted[3]).toMatchObject({ time: 1.5, source: 3.5 });
  });

  it("places Start and End at the clip bounds", () => {
    const markers = generateWarpMarkers({ mode: "start-end", duration: 8, ...bar });
    expect(markers.map((marker) => marker.time)).toEqual([0, 8]);
  });

  it("places Transients on the detected onsets", () => {
    const markers = generateWarpMarkers({
      mode: "transients",
      duration: 8,
      peaks: envelope([0.02, 0.9, 0.05, 0.8]),
      ...bar,
    });
    expect(markers[0].time).toBe(0);
    expect(markers.length).toBeGreaterThanOrEqual(3);
    expect(markers[2].time).toBeGreaterThan(markers[1].time);
  });

  it("falls back to Start and End when no audio could be decoded", () => {
    const markers = generateWarpMarkers({ mode: "transients", duration: 8, peaks: null, ...bar });
    expect(markers.map((marker) => marker.time)).toEqual([0, 8]);
  });

  it("treats a flat envelope as nothing to analyse", () => {
    const markers = generateWarpMarkers({
      mode: "transients",
      duration: 8,
      peaks: Array.from({ length: 64 }, () => 0.03),
      ...bar,
    });
    expect(markers.map((marker) => marker.time)).toEqual([0, 8]);
  });
});

describe("quantiseWarpMarkers", () => {
  it("snaps to the grid and collapses duplicates", () => {
    const markers = [
      { id: "a", time: 0.04, source: 0 },
      { id: "b", time: 0.52, source: 1 },
      { id: "c", time: 0.54, source: 2 },
      { id: "d", time: 1.3, source: 3 },
    ];
    const quantised = quantiseWarpMarkers(markers, 2, 4);
    expect(quantised.map((marker) => marker.time)).toEqual([0, 0.5, 1.5]);
    // The source position is a property of the audio, so quantising leaves it alone.
    expect(quantised[1].source).toBe(1);
  });
});

describe("moveWarpMarker", () => {
  it("clamps to the clip and keeps the list ordered", () => {
    const markers = [
      { id: "a", time: 0, source: 0 },
      { id: "b", time: 1, source: 1 },
      { id: "c", time: 2, source: 2 },
    ];
    const moved = moveWarpMarker(markers, "c", 0.5, 4);
    expect(moved.map((marker) => marker.id)).toEqual(["a", "c", "b"]);
    expect(moveWarpMarker(markers, "a", -3, 4).find((m) => m.id === "a")?.time).toBe(0);
    expect(moveWarpMarker(markers, "a", 40, 4).find((m) => m.id === "a")?.time).toBe(4);
  });
});

describe("sanitizeWarp", () => {
  it("defaults when the document has no warp state", () => {
    expect(sanitizeWarp(undefined)).toEqual(DEFAULT_WARP);
  });

  it("clamps, sorts and drops junk markers", () => {
    const state = sanitizeWarp({
      on: true,
      mode: "nope",
      formant: 140,
      markers: [
        { id: "b", time: 2, source: 2 },
        { id: "a", time: 1, source: 1 },
        { id: "bad", time: "x" },
        null,
      ],
    });
    expect(state).toMatchObject({ on: true, mode: "transients", formant: 100 });
    expect(state.markers.map((marker) => marker.id)).toEqual(["a", "b"]);
  });
});
