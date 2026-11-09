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

export const MIDI_MIN_PITCH = 36; // C2
export const MIDI_MAX_PITCH = 84; // C6
export const MIDI_ROW = 12;
export const MIDI_PITCHES = MIDI_MAX_PITCH - MIDI_MIN_PITCH + 1;

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
  rate = 1
): OscillatorNode {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "triangle";
  oscillator.frequency.value = midiToFreq(note.pitch);
  const peak = Math.max(0.01, Math.min(1, note.velocity / 127)) * 0.22;
  const length = Math.max(0.03, note.length / Math.max(0.1, rate));
  gain.gain.setValueAtTime(0, when);
  gain.gain.linearRampToValueAtTime(peak, when + 0.008);
  gain.gain.setValueAtTime(peak, when + length * 0.7);
  gain.gain.linearRampToValueAtTime(0, when + length);
  oscillator.connect(gain);
  gain.connect(destination);
  oscillator.start(when);
  oscillator.stop(when + length + 0.02);
  return oscillator;
}
