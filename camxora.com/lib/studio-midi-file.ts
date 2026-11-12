/**
 * Standard MIDI File export (N-05).
 *
 * The reference offers "Download MIDI" for the selected MIDI clips; the strings are
 * explicit that the unit is the selection, so several clips become one file with their
 * timeline positions preserved. The file is a format-0 SMF with a tempo meta event and
 * one note-on/note-off pair per note, which every DAW reads.
 *
 * Pure so the byte layout is testable: the shell only decodes the document and hands
 * the bytes to the browser.
 */

import type { MidiNote } from "@/lib/studio-midi";

export type MidiExportClip = {
  id: string;
  /** Clip position on the timeline, in seconds. */
  start?: number;
  duration?: number;
  midi?: { notes?: MidiNote[] };
};

export type MidiExportOptions = {
  bpm?: number;
  /** Ticks per quarter note; 480 is the common DAW default. */
  ppq?: number;
  /** MIDI channel 0–15; the editor is single-timbre so channel 1 by default. */
  channel?: number;
};

export const MIDI_PPQ = 480;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, Math.round(value)));
}

/** MIDI variable-length quantity. */
function variableLength(value: number): number[] {
  let remaining = Math.max(0, Math.round(value));
  const bytes = [remaining & 0x7f];
  while ((remaining >>= 7) > 0) {
    bytes.unshift((remaining & 0x7f) | 0x80);
  }
  return bytes;
}

function ascii(value: string): number[] {
  return [...value].map((character) => character.charCodeAt(0));
}

function chunk(type: string, data: number[]): number[] {
  return [
    ...ascii(type),
    (data.length >>> 24) & 0xff,
    (data.length >>> 16) & 0xff,
    (data.length >>> 8) & 0xff,
    data.length & 0xff,
    ...data,
  ];
}

/**
 * Build one SMF file from the given clips. Notes are placed at
 * `clip.start + note.start` so a selection of clips keeps its arrangement.
 */
export function buildMidiFile(
  clips: MidiExportClip[],
  { bpm = 120, ppq = MIDI_PPQ, channel = 0 }: MidiExportOptions = {}
): Uint8Array {
  const tempo = Math.round(60_000_000 / Math.max(20, bpm));
  const ticksPerSecond = (ppq * Math.max(20, bpm)) / 60;

  type Event = { tick: number; order: number; bytes: number[] };
  const events: Event[] = [];
  const noteOn = 0x90 | (channel & 0x0f);
  const noteOff = 0x80 | (channel & 0x0f);

  for (const clip of clips) {
    const clipStart = clip.start ?? 0;
    for (const note of clip.midi?.notes ?? []) {
      const start = Math.max(0, Math.round((clipStart + note.start) * ticksPerSecond));
      const length = Math.max(1, Math.round(note.length * ticksPerSecond));
      events.push({
        tick: start,
        // Note-offs sort before note-ons at the same tick so repeated pitches retrigger.
        order: 1,
        bytes: [noteOn, clamp(note.pitch, 0, 127), clamp(note.velocity, 1, 127)],
      });
      events.push({
        tick: start + length,
        order: 0,
        bytes: [noteOff, clamp(note.pitch, 0, 127), 0x40],
      });
    }
  }

  if (events.length === 0) {
    return new Uint8Array([...chunk("MThd", header(ppq)), ...chunk("MTrk", endOfTrack())]);
  }
  events.sort((a, b) => a.tick - b.tick || a.order - b.order);

  const track: number[] = [
    0x00,
    0xff,
    0x51,
    0x03,
    (tempo >>> 16) & 0xff,
    (tempo >>> 8) & 0xff,
    tempo & 0xff,
  ];
  let last = 0;
  for (const event of events) {
    track.push(...variableLength(event.tick - last), ...event.bytes);
    last = event.tick;
  }
  track.push(0x00, 0xff, 0x2f, 0x00);

  return new Uint8Array([...chunk("MThd", header(ppq)), ...chunk("MTrk", track)]);
}

function header(ppq: number): number[] {
  // Format 0, one track, then the division.
  return [0x00, 0x00, 0x00, 0x01, (ppq >> 8) & 0xff, ppq & 0xff];
}

function endOfTrack(): number[] {
  return [0x00, 0xff, 0x2f, 0x00];
}
