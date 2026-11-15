import { describe, expect, it } from "vitest";

import {
  deleteTimeRange,
  duplicateTimeRange,
  normaliseRange,
  rangeLength,
  splitClipAtTimes,
  type TimeClip,
  type TimeEdit,
} from "@/lib/studio-time";

function clip(id: string, start: number, duration: number, extra: Record<string, unknown> = {}) {
  return { id, start, duration, ...extra } as TimeClip;
}

function edit(tracks: Record<string, string[]>, lanes: ReturnType<typeof clip>[]): TimeEdit {
  return {
    lanes,
    tracks: Object.entries(tracks).map(([id, clipIds]) => ({ id, clipIds })),
  };
}

function byId(result: TimeEdit, id: string) {
  const found = result.lanes.find((item) => item.id === id);
  if (!found) throw new Error(`missing clip ${id} in ${result.lanes.map((item) => item.id)}`);
  return found;
}

describe("normaliseRange", () => {
  it("orders the drag and clamps to zero", () => {
    expect(normaliseRange(8, 4)).toEqual({ start: 4, end: 8 });
    expect(normaliseRange(-2, 3)).toEqual({ start: 0, end: 3 });
  });

  it("drops an empty selection", () => {
    expect(normaliseRange(4, 4)).toBeNull();
    expect(normaliseRange(4, 4.00001)).toBeNull();
  });

  it("measures a range", () => {
    expect(rangeLength({ start: 2, end: 6.5 })).toBe(4.5);
  });
});

describe("deleteTimeRange", () => {
  it("removes a clip inside the range and ripples later clips left", () => {
    const before = edit(
      { t1: ["a", "b", "c"] },
      [clip("a", 0, 2), clip("b", 2, 2), clip("c", 6, 2)]
    );
    const after = deleteTimeRange(before, { start: 2, end: 4 });

    expect(after.lanes.map((item) => item.id)).toEqual(["a", "c"]);
    expect(byId(after, "c").start).toBe(4);
    expect(after.tracks[0].clipIds).toEqual(["a", "c"]);
  });

  it("keeps the head and tail of a clip that spans the range", () => {
    const before = edit({ t1: ["a"] }, [clip("a", 0, 8, { offset: 1, fadeIn: 2 })]);
    const after = deleteTimeRange(before, { start: 3, end: 5 });

    const head = byId(after, "a");
    const tail = after.lanes.find((item) => item.id !== "a");
    expect(head.start).toBe(0);
    expect(head.duration).toBe(3);
    expect(head.fadeIn).toBe(2);
    expect(tail?.start).toBe(3);
    expect(tail?.duration).toBe(3);
    // The tail resumes 5 s into the source, then ripples back to the gap start.
    expect(tail?.offset).toBe(1 + 5);
    expect(after.tracks[0].clipIds).toEqual([head.id, tail?.id]);
  });

  it("only edits the tracks it was given", () => {
    const before = edit(
      { t1: ["a"], t2: ["b"] },
      [clip("a", 0, 4), clip("b", 0, 4)]
    );
    const after = deleteTimeRange(before, { start: 0, end: 2 }, ["t2"]);

    expect(byId(after, "a").duration).toBe(4);
    // The scoped track keeps the part of its clip that is after the range.
    const trimmed = byId(after, "b");
    expect(trimmed).toMatchObject({ start: 0, duration: 2, offset: 2 });
    expect(after.tracks[0].clipIds).toEqual(["a"]);
    expect(after.tracks[1].clipIds).toEqual(["b"]);
  });

  it("does nothing for an empty range", () => {
    const before = edit({ t1: ["a"] }, [clip("a", 0, 4)]);
    expect(deleteTimeRange(before, { start: 2, end: 2 })).toBe(before);
  });

  it("rebases MIDI notes onto the surviving tail", () => {
    const notes = [
      { id: "n1", pitch: 60, start: 0, length: 1, velocity: 100 },
      { id: "n2", pitch: 62, start: 4, length: 2, velocity: 100 },
    ];
    const before = edit({ t1: ["m"] }, [clip("m", 0, 8, { midi: { notes } })]);
    const after = deleteTimeRange(before, { start: 3, end: 5 });
    const tail = after.lanes.find((item) => item.id !== "m");

    expect(tail?.midi?.notes).toEqual([
      // The note starts inside the deleted block, so it is clipped to the tail's head.
      { id: "n2", pitch: 62, start: 0, length: 1, velocity: 100 },
    ]);
  });
});

describe("duplicateTimeRange", () => {
  it("copies the range after itself and pushes later clips right", () => {
    const before = edit(
      { t1: ["a", "b"] },
      [clip("a", 0, 2), clip("b", 2, 1)]
    );
    const after = duplicateTimeRange(before, { start: 0, end: 2 });
    const copy = after.lanes.find((item) => item.id.startsWith("a~d"));

    expect(byId(after, "a").start).toBe(0);
    expect(copy?.start).toBe(2);
    expect(copy?.duration).toBe(2);
    expect(byId(after, "b").start).toBe(4);
    expect(after.tracks[0].clipIds).toHaveLength(3);
  });

  it("slices a clip that starts before and ends after the range", () => {
    const before = edit({ t1: ["a"] }, [clip("a", 1, 8, { offset: 0 })]);
    const after = duplicateTimeRange(before, { start: 3, end: 5 });
    const ids = after.lanes.map((item) => item.id).sort();

    expect(ids).toHaveLength(4);
    const head = byId(after, "a");
    const mid = after.lanes.find((item) => item.id.endsWith("~m"));
    const copy = after.lanes.find((item) => item.id.endsWith("~d"));
    const tail = after.lanes.find((item) => item.id.endsWith("~r"));

    expect(head).toMatchObject({ start: 1, duration: 2 });
    expect(mid).toMatchObject({ start: 3, duration: 2, offset: 2 });
    expect(copy).toMatchObject({ start: 5, duration: 2, offset: 2 });
    expect(tail).toMatchObject({ start: 7, duration: 4, offset: 4 });
  });

  it("only duplicates on the tracks it was given", () => {
    const before = edit(
      { t1: ["a"], t2: ["b"] },
      [clip("a", 0, 2), clip("b", 0, 2)]
    );
    const after = duplicateTimeRange(before, { start: 0, end: 2 }, ["t2"]);

    expect(after.lanes).toHaveLength(3);
    expect(after.tracks[0].clipIds).toEqual(["a"]);
    expect(after.tracks[1].clipIds).toHaveLength(2);
  });

  it("keeps every id unique across repeated edits", () => {
    const before = edit({ t1: ["a"] }, [clip("a", 0, 4)]);
    const once = duplicateTimeRange(before, { start: 0, end: 2 });
    const twice = duplicateTimeRange(once, { start: 0, end: 2 });
    const ids = twice.lanes.map((item) => item.id);

    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("splitClipAtTimes", () => {
  it("cuts at each time, keeps the head's id and advances the offset", () => {
    const segments = splitClipAtTimes(clip("a", 2, 4, { offset: 1 }), [3, 5]);

    expect(segments.map((item) => item.id)).toEqual(["a", "a-split", "a-split-2"]);
    expect(segments.map((item) => [item.start, item.duration])).toEqual([
      [2, 1],
      [3, 2],
      [5, 1],
    ]);
    expect(segments.map((item) => item.offset)).toEqual([1, 2, 4]);
  });

  it("keeps the fades on the outer segments only", () => {
    const segments = splitClipAtTimes(clip("a", 0, 4, { fadeIn: 0.5, fadeOut: 0.25 }), [2]);

    expect(segments).toHaveLength(2);
    expect(segments[0].fadeIn).toBe(0.5);
    expect(segments[0].fadeOut).toBeUndefined();
    expect(segments[1].fadeIn).toBeUndefined();
    expect(segments[1].fadeOut).toBe(0.25);
  });

  it("ignores cuts at or outside the clip and de-duplicates repeats", () => {
    const untouched = splitClipAtTimes(clip("a", 2, 4), [2, 6, 1, 9]);
    expect(untouched).toHaveLength(1);
    expect(untouched[0].id).toBe("a");

    const once = splitClipAtTimes(clip("a", 2, 4), [3, 3.0000001, 3]);
    expect(once).toHaveLength(2);
  });
});
