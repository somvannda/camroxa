import { describe, expect, it } from "vitest";

import {
  midiToFreq,
  noteName,
  quantizeNotes,
  sanitizeNotes,
  sanitizePoints,
  valueAt,
  type MidiNote,
} from "@/lib/studio-midi";

describe("studio MIDI model", () => {
  it("maps pitch to frequency and names", () => {
    expect(Math.round(midiToFreq(69))).toBe(440);
    expect(noteName(60)).toBe("C4");
    expect(noteName(69)).toBe("A4");
    expect(noteName(61)).toBe("C#4");
  });

  it("sanitises notes from a document", () => {
    const notes = sanitizeNotes([
      { pitch: 200, start: -3, length: 0, velocity: 999 },
      { pitch: "not a number", start: 0 },
      null,
    ]);
    expect(notes).toHaveLength(1);
    expect(notes[0]).toMatchObject({ pitch: 84, start: 0, length: 0.02, velocity: 127 });
    expect(sanitizeNotes("nope")).toEqual([]);
  });

  it("quantises starts to the step", () => {
    const notes: MidiNote[] = [
      { id: "a", pitch: 60, start: 0.31, length: 0.4, velocity: 100 },
      { id: "b", pitch: 62, start: 0.61, length: 0.4, velocity: 100 },
    ];
    expect(quantizeNotes(notes, 0.5).map((note) => note.start)).toEqual([0.5, 0.5]);
  });

  it("sanitises and reads automation lanes", () => {
    const points = sanitizePoints(
      [
        { at: 2, value: 5 },
        { at: 0, value: -9 },
        { at: "x", value: 1 },
      ],
      -1,
      1
    );
    expect(points).toEqual([
      { at: 0, value: -1 },
      { at: 2, value: 1 },
    ]);
    expect(valueAt(points, -5, 0)).toBe(-1);
    expect(valueAt(points, 1, 0)).toBe(-1);
    expect(valueAt(points, 3, 0)).toBe(1);
    expect(valueAt(undefined, 1, 0.5)).toBe(0.5);
  });
});
