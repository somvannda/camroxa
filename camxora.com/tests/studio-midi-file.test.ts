import { describe, expect, it } from "vitest";

import { buildMidiFile, MIDI_PPQ } from "@/lib/studio-midi-file";

type Event = { delta: number; status: number; data: number[] };

function readVariable(data: Uint8Array, at: number): { value: number; next: number } {
  let value = 0;
  let index = at;
  for (;;) {
    const byte = data[index++];
    value = (value << 7) | (byte & 0x7f);
    if ((byte & 0x80) === 0) return { value, next: index };
  }
}

function parseTrack(bytes: Uint8Array): { division: number; events: Event[] } {
  const text = (from: number, length: number) =>
    String.fromCharCode(...bytes.subarray(from, from + length));
  expect(text(0, 4)).toBe("MThd");
  const headerLength = new DataView(bytes.buffer).getUint32(4);
  const division = (bytes[12] << 8) | bytes[13];
  const trackAt = 8 + headerLength;
  expect(text(trackAt, 4)).toBe("MTrk");

  const events: Event[] = [];
  let at = trackAt + 8;
  const end = bytes.length;
  while (at < end) {
    const delta = readVariable(bytes, at);
    at = delta.next;
    const status = bytes[at];
    if (status === 0xff) {
      const type = bytes[at + 1];
      const length = readVariable(bytes, at + 2);
      const data = [...bytes.subarray(length.next, length.next + length.value)];
      events.push({ delta: delta.value, status: 0xff00 | type, data });
      at = length.next + length.value;
      continue;
    }
    const count = (status & 0xf0) === 0xc0 || (status & 0xf0) === 0xd0 ? 1 : 2;
    events.push({ delta: delta.value, status, data: [...bytes.subarray(at + 1, at + 1 + count)] });
    at += 1 + count;
  }
  return { division, events };
}

describe("buildMidiFile", () => {
  it("writes a format-0 header at 480 PPQ", () => {
    const bytes = buildMidiFile([]);
    expect(String.fromCharCode(...bytes.subarray(0, 4))).toBe("MThd");
    expect(bytes[7]).toBe(6); // header length
    expect(bytes[8]).toBe(0); // format 0
    expect(bytes[10]).toBe(0); // one track
    expect(bytes[11]).toBe(1);
    expect((bytes[12] << 8) | bytes[13]).toBe(MIDI_PPQ);
  });

  it("writes tempo, note-on/off pairs and an end-of-track", () => {
    const bytes = buildMidiFile(
      [
        {
          id: "midi",
          start: 0,
          duration: 4,
          midi: {
            notes: [
              { id: "n1", pitch: 60, start: 0.5, length: 0.5, velocity: 100 },
              { id: "n2", pitch: 64, start: 1, length: 0.5, velocity: 90 },
            ],
          },
        },
      ],
      { bpm: 120 }
    );
    const { events } = parseTrack(bytes);

    // 500,000 µs per quarter at 120 BPM.
    expect(events[0]).toEqual({
      delta: 0,
      status: 0xff51,
      data: [0x07, 0xa1, 0x20],
    });

    const noteOns = events.filter((event) => event.status === 0x90);
    const noteOffs = events.filter((event) => event.status === 0x80);
    expect(noteOns.map((event) => event.data)).toEqual([
      [60, 100],
      [64, 90],
    ]);
    expect(noteOffs.map((event) => event.data)).toEqual([
      [60, 0x40],
      [64, 0x40],
    ]);

    // 0.5 s at 120 BPM is 480 ticks (960 ticks a second at 480 PPQ).
    expect(noteOns[0].delta).toBe(480);
    expect(noteOffs[0].delta).toBe(480);

    expect(events.at(-1)).toEqual({ delta: 0, status: 0xff2f, data: [] });
  });

  it("keeps a clip's timeline position in the file", () => {
    const bytes = buildMidiFile(
      [
        {
          id: "late",
          start: 2,
          duration: 2,
          midi: { notes: [{ id: "n", pitch: 72, start: 0, length: 1, velocity: 64 }] },
        },
      ],
      { bpm: 120 }
    );
    const { events } = parseTrack(bytes);
    const noteOn = events.find((event) => event.status === 0x90);
    // 2 s at 960 ticks a second.
    expect(noteOn?.delta).toBe(1920);
  });

  it("uses the channel it is given", () => {
    const bytes = buildMidiFile(
      [
        {
          id: "midi",
          start: 0,
          midi: { notes: [{ id: "n", pitch: 60, start: 0, length: 1, velocity: 80 }] },
        },
      ],
      { channel: 3 }
    );
    const { events } = parseTrack(bytes);
    expect(events.some((event) => event.status === 0x93)).toBe(true);
  });
});
