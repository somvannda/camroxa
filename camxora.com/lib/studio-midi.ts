/**
 * MIDI model shared by the editor panel, playback and export.
 *
 * Notes are stored on the clip (`clip.midi.notes`) in the same `lanes` array as audio
 * clips, so drag, split, trim and undo keep working. Times are seconds relative to the
 * clip start; pitches are MIDI numbers; velocity is 1–127.
 */

export type MidiNote = {
  id: string;
  pitch: number;
  start: number;
  length: number;
  velocity: number;
};

export type MidiPoint = { at: number; value: number };

export const MIDI_MIN_PITCH = 36; // C2
export const MIDI_MAX_PITCH = 84; // C6
export const MIDI_ROW = 12;
export const MIDI_PITCHES = MIDI_MAX_PITCH - MIDI_MIN_PITCH + 1;

export type MidiChordMode = "off" | "major" | "minor";
export type MidiArpMode = "off" | "up" | "down";
export type MidiInstrument = "triangle" | "sine" | "sawtooth";

export function normalizeMidiInstrument(value: unknown): MidiInstrument {
  return value === "sine" || value === "sawtooth" ? value : "triangle";
}

/**
 * Notes produced by a click in the piano roll, before ids are assigned.
 *
 * `off` is a single note. A chord stacks the root/third/fifth at the same start;
 * an arpeggiator spreads the same pitches by one grid step, up or down. Pitches are
 * clamped to the editor's 36-84 range and notes that would fall past the clip end
 * are dropped rather than clipped into a zero-length note.
 */
export function buildMidiChordNotes({
  pitch,
  chordMode,
  arpMode,
  start,
  step,
  baseLength,
  duration,
}: {
  pitch: number;
  chordMode: MidiChordMode;
  arpMode: MidiArpMode;
  start: number;
  step: number;
  baseLength: number;
  duration: number;
}): Array<{ pitch: number; start: number; length: number }> {
  const intervals = chordMode === "major" ? [0, 4, 7] : chordMode === "minor" ? [0, 3, 7] : [0];
  let pitches = intervals
    .map((interval) => pitch + interval)
    .filter((value) => value >= MIDI_MIN_PITCH && value <= MIDI_MAX_PITCH);
  if (arpMode === "down") pitches = [...pitches].reverse();

  const stride = arpMode === "off" ? 0 : Math.max(0.02, step);
  const notes: Array<{ pitch: number; start: number; length: number }> = [];
  pitches.forEach((value, index) => {
    const noteStart = start + index * stride;
    if (noteStart >= duration - 0.02) return;
    const available = duration - noteStart;
    const length =
      arpMode === "off"
        ? Math.max(0.02, Math.min(available, baseLength))
        : Math.max(0.02, Math.min(available, Math.max(0.02, stride * 0.9)));
    notes.push({
      pitch: value,
      start: Number(noteStart.toFixed(4)),
      length: Number(length.toFixed(4)),
    });
  });
  return notes;
}

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export function midiToFreq(pitch: number): number {
  return 440 * Math.pow(2, (pitch - 69) / 12);
}

export function noteName(pitch: number): string {
  const name = NOTE_NAMES[((pitch % 12) + 12) % 12];
  const octave = Math.floor(pitch / 12) - 1;
  return `${name}${octave}`;
}

export function isBlackKey(pitch: number): boolean {
  return NOTE_NAMES[((pitch % 12) + 12) % 12]?.includes("#") ?? false;
}

/** Coerce whatever the document holds into notes the editor can trust. */
export function sanitizeNotes(input: unknown): MidiNote[] {
  if (!Array.isArray(input)) return [];
  const notes: MidiNote[] = [];
  for (const raw of input) {
    if (!raw || typeof raw !== "object") continue;
    const note = raw as Record<string, unknown>;
    const pitch = Number(note.pitch);
    const start = Number(note.start);
    const length = Number(note.length);
    const velocity = Number(note.velocity);
    if (!Number.isFinite(pitch) || !Number.isFinite(start)) continue;
    notes.push({
      id: typeof note.id === "string" && note.id ? note.id : `note-${notes.length}-${Math.random().toString(36).slice(2, 7)}`,
      pitch: Math.round(Math.min(MIDI_MAX_PITCH, Math.max(MIDI_MIN_PITCH, pitch))),
      start: Math.max(0, start),
      length: Math.max(0.02, Number.isFinite(length) ? length : 0.25),
      velocity: Math.min(127, Math.max(1, Number.isFinite(velocity) ? Math.round(velocity) : 100)),
    });
  }
  return notes;
}

/**
 * Convert Basic Pitch's `{pitch,start,end,velocity}` transcription into editor
 * notes. `velocity` arrives as a 0..1 confidence from the model, so scale it to the
 * editor's 1..127 range. `offset` is the source clip's timeline position.
 */
export function midiNotesFromTranscription(
  instruments: Array<{ name?: string; notes?: Array<Record<string, unknown>> }> | undefined,
  offset = 0
): MidiNote[] {
  if (!Array.isArray(instruments)) return [];
  const stamp = Date.now().toString(36);
  const notes: MidiNote[] = [];
  instruments.forEach((instrument, instrumentIndex) => {
    for (const raw of instrument.notes ?? []) {
      const pitch = Number(raw.pitch);
      const start = Number(raw.start);
      const end = Number(raw.end);
      const velocity = Number(raw.velocity);
      if (!Number.isFinite(pitch) || !Number.isFinite(start) || !Number.isFinite(end)) continue;
      const length = Math.max(0.02, end - start);
      if (length <= 0.05) continue;
      notes.push({
        id: `midi-${stamp}-${instrumentIndex}-${notes.length}`,
        pitch: Math.round(Math.max(MIDI_MIN_PITCH, Math.min(MIDI_MAX_PITCH, pitch))),
        start: Math.max(0, start + offset),
        length,
        velocity: Math.max(
          1,
          Math.min(127, Math.round(velocity <= 1 ? velocity * 127 : velocity))
        ),
      });
    }
  });
  return notes.sort((a, b) => a.start - b.start || a.pitch - b.pitch);
}

/** Coerce an automation lane (pitch bend -1..1, modulation 0..1). */
export function sanitizePoints(input: unknown, min: number, max: number): MidiPoint[] {
  if (!Array.isArray(input)) return [];
  return input
    .map((raw) => {
      const point = raw as Record<string, unknown>;
      const at = Number(point?.at);
      const value = Number(point?.value);
      if (!Number.isFinite(at) || !Number.isFinite(value)) return null;
      return { at: Math.max(0, at), value: Math.min(max, Math.max(min, value)) };
    })
    .filter((point): point is MidiPoint => point !== null)
    .sort((a, b) => a.at - b.at);
}

/** Value of a lane at a time; holds the nearest point (before, else first). */
export function valueAt(points: MidiPoint[] | undefined, at: number, fallback: number): number {
  if (!points || points.length === 0) return fallback;
  let current = points[0].value;
  for (const point of points) {
    if (point.at > at) break;
    current = point.value;
  }
  return current;
}

export function quantizeNotes(notes: MidiNote[], step: number): MidiNote[] {
  if (!(step > 0)) return notes;
  return notes.map((note) => ({
    ...note,
    start: Math.round(note.start / step) * step,
  }));
}

/** Schedule one synth voice into a destination node. Returns the oscillator for cleanup. */
export function scheduleMidiNote(
  context: BaseAudioContext,
  destination: AudioNode,
  note: MidiNote,
  when: number,
  rate = 1,
  automation?: { bend?: number; mod?: number },
  instrument: MidiInstrument = "triangle",
  wavetable?: { real: Float32Array; imag: Float32Array } | null
): AudioScheduledSourceNode[] {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  if (wavetable) {
    oscillator.setPeriodicWave(context.createPeriodicWave(wavetable.real, wavetable.imag));
  } else {
    oscillator.type = instrument;
  }
  oscillator.frequency.value = midiToFreq(note.pitch);
  // Pitch bend is applied as detune at the note's start (captured lane, simplified).
  oscillator.detune.value = (automation?.bend ?? 0) * 200;
  const peak = Math.max(0.01, Math.min(1, note.velocity / 127)) * 0.22;
  const length = Math.max(0.03, note.length / Math.max(0.1, rate));
  gain.gain.setValueAtTime(0, when);
  gain.gain.linearRampToValueAtTime(peak, when + 0.008);
  gain.gain.setValueAtTime(peak, when + length * 0.7);
  gain.gain.linearRampToValueAtTime(0, when + length);
  oscillator.connect(gain);

  const sources: AudioScheduledSourceNode[] = [oscillator];
  const mod = automation?.mod ?? 0;
  if (mod > 0) {
    // Modulation is tremolo: an LFO on a gain stage, depth from the lane at start.
    const tremolo = context.createGain();
    tremolo.gain.value = 1;
    const lfo = context.createOscillator();
    const depth = context.createGain();
    lfo.frequency.value = 5;
    depth.gain.value = mod * 0.35;
    lfo.connect(depth);
    depth.connect(tremolo.gain);
    gain.connect(tremolo);
    tremolo.connect(destination);
    lfo.start(when);
    lfo.stop(when + length + 0.02);
    sources.push(lfo);
  } else {
    gain.connect(destination);
  }

  oscillator.start(when);
  oscillator.stop(when + length + 0.02);
  return sources;
}
