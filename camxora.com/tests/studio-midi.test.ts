import { describe, expect, it } from "vitest";

import {
  buildMidiChordNotes,
  midiNotesFromTranscription,
  midiToFreq,
  normalizeMidiInstrument,
  noteName,
  quantizeNotes,
  playablePitch,
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

  it("keeps the reference's disabled flag, and only when it is true", () => {
    const notes = sanitizeNotes([
      { id: "a", pitch: 60, start: 0, length: 0.5, velocity: 100, disabled: true },
      { id: "b", pitch: 62, start: 0.5, length: 0.5, velocity: 100, disabled: false },
      { id: "c", pitch: 64, start: 1, length: 0.5, velocity: 100 },
    ]);
    expect(notes.map((note) => note.disabled)).toEqual([true, undefined, undefined]);
  });

  it("quantises starts to the step", () => {
    const notes: MidiNote[] = [
      { id: "a", pitch: 60, start: 0.31, length: 0.4, velocity: 100 },
      { id: "b", pitch: 62, start: 0.61, length: 0.4, velocity: 100 },
    ];
    expect(quantizeNotes(notes, 0.5).map((note) => note.start)).toEqual([0.5, 0.5]);
  });

  it("maps the playable keyboard row to pitches and clamps the range", () => {
    expect(playablePitch("a", 4)).toBe(60); // C4
    expect(playablePitch("w", 4)).toBe(61);
    expect(playablePitch("k", 4)).toBe(72);
    expect(playablePitch(";", 4)).toBe(76);
    expect(playablePitch("x", 4)).toBeNull();
    expect(playablePitch("a", 0)).toBe(36); // clamped at C2
    expect(playablePitch(";", 8)).toBe(84); // clamped at C6
  });

  it("builds single notes, chords and arpeggios", () => {
    const base = { start: 1, step: 0.25, baseLength: 0.5, duration: 4 };

    expect(
      buildMidiChordNotes({ ...base, pitch: 60, chordMode: "off", arpMode: "off" }).map(
        (note) => [note.pitch, note.start, note.length]
      )
    ).toEqual([[60, 1, 0.5]]);

    expect(
      buildMidiChordNotes({ ...base, pitch: 60, chordMode: "major", arpMode: "off" }).map(
        (note) => note.pitch
      )
    ).toEqual([60, 64, 67]);

    expect(
      buildMidiChordNotes({ ...base, pitch: 60, chordMode: "minor", arpMode: "off" }).map(
        (note) => note.pitch
      )
    ).toEqual([60, 63, 67]);

    expect(
      buildMidiChordNotes({ ...base, pitch: 60, chordMode: "major", arpMode: "up" }).map(
        (note) => [note.pitch, note.start]
      )
    ).toEqual([
      [60, 1],
      [64, 1.25],
      [67, 1.5],
    ]);

    expect(
      buildMidiChordNotes({ ...base, pitch: 60, chordMode: "major", arpMode: "down" }).map(
        (note) => [note.pitch, note.start]
      )
    ).toEqual([
      [67, 1],
      [64, 1.25],
      [60, 1.5],
    ]);
  });

  it("clamps chord pitches and drops notes past the clip end", () => {
    const top = buildMidiChordNotes({
      pitch: 84,
      chordMode: "major",
      arpMode: "off",
      start: 0,
      step: 0.25,
      baseLength: 0.5,
      duration: 4,
    });
    expect(top.map((note) => note.pitch)).toEqual([84]);

    const late = buildMidiChordNotes({
      pitch: 60,
      chordMode: "major",
      arpMode: "up",
      start: 3.8,
      step: 0.25,
      baseLength: 0.5,
      duration: 4,
    });
    expect(late.map((note) => note.pitch)).toEqual([60]);
  });

  it("converts a Basic Pitch transcription into editor notes", () => {
    const notes = midiNotesFromTranscription([
      {
        name: "Instrument",
        notes: [
          { pitch: 60, start: 0, end: 1, velocity: 0.8 },
          { pitch: 200, start: 2, end: 2.5, velocity: 100 },
          { pitch: "x", start: 0, end: 1, velocity: 1 },
        ],
      },
    ]);
    expect(notes).toHaveLength(2);
    expect(notes[0]).toMatchObject({ pitch: 60, start: 0, length: 1, velocity: 102 });
    expect(notes[1]).toMatchObject({ pitch: 84, start: 2, length: 0.5, velocity: 100 });
  });

  it("normalises the MIDI synth instrument", () => {
    expect(normalizeMidiInstrument("sine")).toBe("sine");
    expect(normalizeMidiInstrument("sawtooth")).toBe("sawtooth");
    expect(normalizeMidiInstrument("triangle")).toBe("triangle");
    expect(normalizeMidiInstrument("square")).toBe("triangle");
    expect(normalizeMidiInstrument(undefined)).toBe("triangle");
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
