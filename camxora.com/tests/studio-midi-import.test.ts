import { describe, expect, it } from "vitest";

import { buildMidiFile } from "@/lib/studio-midi-file";
import { parseMidiFile } from "@/lib/studio-midi-import";

describe("MIDI import", () => {
  it("round-trips the exported note, tempo and timing", () => {
    const bytes = buildMidiFile(
      [
        {
          id: "clip",
          midi: {
            notes: [
              { id: "a", pitch: 60, start: 0, length: 1, velocity: 100 },
              { id: "b", pitch: 67, start: 1.5, length: 0.5, velocity: 80 },
            ],
          },
        },
      ],
      { bpm: 100 }
    );

    const parsed = parseMidiFile(bytes);
    expect(parsed.bpm).toBe(100);
    expect(parsed.timeSignature).toEqual([4, 4]);
    expect(parsed.notes).toHaveLength(2);
    expect(parsed.notes[0]).toMatchObject({ pitch: 60, velocity: 100 });
    expect(parsed.notes[0].start).toBeCloseTo(0, 2);
    expect(parsed.notes[0].length).toBeCloseTo(1, 2);
    expect(parsed.notes[1]).toMatchObject({ pitch: 67, velocity: 80 });
    expect(parsed.notes[1].start).toBeCloseTo(1.5, 2);
    expect(parsed.notes[1].length).toBeCloseTo(0.5, 2);
  });

  it("rejects a file without a MIDI header", () => {
    expect(() => parseMidiFile(new Uint8Array([1, 2, 3, 4]))).toThrow(
      /not a Standard MIDI File/i
    );
  });

  it("rejects SMPTE time division", () => {
    const header = new Uint8Array([
      0x4d, 0x54, 0x68, 0x64, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x01, 0xe8, 0x28,
    ]);
    expect(() => parseMidiFile(header)).toThrow(/SMPTE/i);
  });
});
