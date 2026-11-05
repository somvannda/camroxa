/**
 * Metronome click scheduling (reference H-09: "Click track").
 *
 * Pure maths so the timing can be tested without WebAudio: beat zero is time zero, the
 * period is 60/bpm, and every fourth beat is an accent (4/4 for now — the project's time
 * signature is carried separately and only 4/4 is wired).
 */

export type Click = {
  /** Song time in seconds. */
  time: number;
  /** First beat of a bar. */
  accent: boolean;
};

/** Beats audible in the half-open window [from, to). */
export function clicksBetween(from: number, to: number, bpm: number, beatsPerBar = 4): Click[] {
  if (!(bpm > 0) || !(to > from)) return [];
  const period = 60 / bpm;
  const first = Math.ceil(from / period);
  const last = Math.ceil(to / period) - 1;
  const bar = Math.max(1, Math.round(beatsPerBar));
  const clicks: Click[] = [];
  for (let beat = first; beat <= last; beat++) {
    clicks.push({ time: beat * period, accent: beat % bar === 0 });
  }
  return clicks;
}

/** 1-based beat within the bar for a playhead position, or 0 before the first beat. */
export function beatAt(time: number, bpm: number, beatsPerBar = 4): number {
  if (!(bpm > 0) || time < 0) return 0;
  const bar = Math.max(1, Math.round(beatsPerBar));
  return (Math.floor((time * bpm) / 60) % bar) + 1;
}
