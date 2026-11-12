/**
 * Standard MIDI File import.
 *
 * The editor exports format-0 SMFs; this reads them back (and the broader format-0/1
 * files DAWs produce) without pulling a MIDI library into the client bundle. It
 * supports PPQ timing, running status, tempo changes, time signatures and the note
 * on/off pairs the editor cares about; SMPTE-timed files are rejected with a clear
 * error instead of being mis-timed.
 *
 * Pure so the byte walk can be unit-tested against `buildMidiFile`.
 */

export type ImportedMidiNote = {
  pitch: number;
  start: number;
  length: number;
  velocity: number;
};

export type ImportedMidi = {
  bpm: number;
  timeSignature: [number, number];
  name: string;
  notes: ImportedMidiNote[];
};

type RawNote = {
  pitch: number;
  start: number;
  length: number;
  velocity: number;
};

const DEFAULT_TEMPO = 500_000; // 120 BPM

function readVariable(bytes: Uint8Array, offset: { value: number }): number {
  let value = 0;
  for (let index = 0; index < 4; index += 1) {
    const byte = bytes[offset.value++];
    if (byte === undefined) throw new Error("Truncated MIDI variable-length value.");
    value = (value << 7) | (byte & 0x7f);
    if ((byte & 0x80) === 0) return value;
  }
  return value;
}

function readText(bytes: Uint8Array, start: number, length: number): string {
  return new TextDecoder().decode(bytes.subarray(start, start + length)).trim();
}

export function parseMidiFile(input: ArrayBuffer | Uint8Array): ImportedMidi {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  const offset = { value: 0 };

  if (readText(bytes, 0, 4) !== "MThd") {
    throw new Error("This is not a Standard MIDI File.");
  }
  offset.value = 4;
  const headerLength =
    ((bytes[4] << 24) | (bytes[5] << 16) | (bytes[6] << 8) | bytes[7]) >>> 0;
  const format = (bytes[8] << 8) | bytes[9];
  const trackCount = (bytes[10] << 8) | bytes[11];
  const division = (bytes[12] << 8) | bytes[13];
  if (division & 0x8000) {
    throw new Error("SMPTE-timed MIDI files are not supported.");
  }
  const ppq = division || 480;
  offset.value = 8 + headerLength;
  if (format > 1) {
    throw new Error("Only MIDI formats 0 and 1 are supported.");
  }

  const tempos: Array<{ tick: number; microseconds: number }> = [
    { tick: 0, microseconds: DEFAULT_TEMPO },
  ];
  let timeSignature: [number, number] = [4, 4];
  let name = "";
  const raw: RawNote[] = [];

  for (let track = 0; track < trackCount && offset.value < bytes.length; track += 1) {
    const chunkType = readText(bytes, offset.value, 4);
    offset.value += 4;
    const chunkLength =
      ((bytes[offset.value] << 24) |
        (bytes[offset.value + 1] << 16) |
        (bytes[offset.value + 2] << 8) |
        bytes[offset.value + 3]) >>>
      0;
    offset.value += 4;
    if (chunkType !== "MTrk") {
      offset.value += chunkLength;
      continue;
    }
    const end = offset.value + chunkLength;
    let tick = 0;
    let runningStatus = 0;
    let lastTick = 0;
    const open = new Map<string, Array<{ pitch: number; start: number; velocity: number }>>();

    while (offset.value < end) {
      tick += readVariable(bytes, offset);
      lastTick = tick;
      let status = bytes[offset.value];
      if (status === undefined) break;
      if (status < 0x80) {
        status = runningStatus;
      } else {
        offset.value += 1;
        if (status < 0xf0) runningStatus = status;
      }
      if (!status) throw new Error("MIDI event is missing a status byte.");

      if (status === 0xff) {
        const type = bytes[offset.value++];
        const length = readVariable(bytes, offset);
        const start = offset.value;
        offset.value += length;
        if (type === 0x51 && length === 3) {
          const microseconds =
            (bytes[start] << 16) | (bytes[start + 1] << 8) | bytes[start + 2];
          if (microseconds > 0) tempos.push({ tick, microseconds });
        } else if (type === 0x58 && length >= 2) {
          timeSignature = [bytes[start], 2 ** bytes[start + 1]];
        } else if (type === 0x03 && !name && length > 0) {
          name = readText(bytes, start, length);
        } else if (type === 0x2f) {
          break;
        }
        continue;
      }

      if (status === 0xf0 || status === 0xf7) {
        const length = readVariable(bytes, offset);
        offset.value += length;
        continue;
      }

      const kind = status & 0xf0;
      const channel = status & 0x0f;
      if (kind === 0x90 || kind === 0x80) {
        const pitch = bytes[offset.value++];
        const velocity = bytes[offset.value++];
        const key = `${channel}:${pitch}`;
        if (kind === 0x90 && velocity > 0) {
          const stack = open.get(key) ?? [];
          stack.push({ pitch, start: tick, velocity });
          open.set(key, stack);
        } else {
          const stack = open.get(key);
          const started = stack?.pop();
          if (started) {
            raw.push({
              pitch: started.pitch,
              start: started.start,
              length: Math.max(1, tick - started.start),
              velocity: started.velocity,
            });
          }
        }
      } else if (kind === 0xc0 || kind === 0xd0) {
        offset.value += 1;
      } else {
        offset.value += 2;
      }
    }

    // A note still held at the track end is closed there rather than dropped.
    for (const stack of open.values()) {
      for (const started of stack) {
        raw.push({
          pitch: started.pitch,
          start: started.start,
          length: Math.max(1, lastTick - started.start),
          velocity: started.velocity,
        });
      }
    }
    offset.value = end;
  }

  tempos.sort((a, b) => a.tick - b.tick);
  const secondsAt = (tick: number): number => {
    let seconds = 0;
    let lastTick = 0;
    let current = DEFAULT_TEMPO;
    for (const tempo of tempos) {
      if (tempo.tick >= tick) break;
      seconds += ((tempo.tick - lastTick) * current) / 1_000_000 / ppq;
      lastTick = tempo.tick;
      current = tempo.microseconds;
    }
    seconds += ((tick - lastTick) * current) / 1_000_000 / ppq;
    return seconds;
  };

  const bpm = Math.round(60_000_000 / tempos[tempos.length - 1].microseconds);
  const notes = raw
    .map((note) => {
      const start = secondsAt(note.start);
      const end = secondsAt(note.start + note.length);
      return {
        pitch: Math.max(0, Math.min(127, Math.round(note.pitch))),
        start: Number(start.toFixed(4)),
        length: Number((end - start).toFixed(4)),
        velocity: Math.max(1, Math.min(127, Math.round(note.velocity))),
      };
    })
    .filter((note) => note.length > 0.005)
    .sort((a, b) => a.start - b.start || a.pitch - b.pitch);

  return { bpm, timeSignature, name, notes };
}
