/**
 * Time signatures (H-13): the reference lets the meter be edited, and bar maths follows
 * it. Only the numerator changes the beat count per bar; the denominator is carried for
 * display and for the note-value semantics of the ruler.
 */

export const STUDIO_SIGNATURES = ["2/4", "3/4", "4/4", "6/8"] as const;

/** Beats in a bar for a signature string; falls back to 4 for anything unparseable. */
export function parseBeatsPerBar(signature: string | null | undefined): number {
  const match = /^(\d{1,2})\s*\/\s*(\d{1,2})$/.exec(String(signature ?? "").trim());
  if (!match) return 4;
  const beats = Number(match[1]);
  if (!Number.isFinite(beats) || beats < 1) return 4;
  return Math.min(16, Math.max(1, Math.round(beats)));
}

/** Seconds in one bar at a tempo and signature. */
export function secondsPerBar(bpm: number, signature: string): number {
  const tempo = Number.isFinite(bpm) && bpm > 0 ? bpm : 120;
  return (60 / tempo) * parseBeatsPerBar(signature);
}

/** 1-based bar and beat for a position, in the given meter. */
export function barBeatAt(
  seconds: number,
  bpm: number,
  signature: string
): { bar: number; beat: number } {
  const beatsPerBar = parseBeatsPerBar(signature);
  const beats = Math.max(0, seconds) / (60 / (Number.isFinite(bpm) && bpm > 0 ? bpm : 120));
  return {
    bar: Math.floor(beats / beatsPerBar) + 1,
    beat: Math.floor(beats % beatsPerBar) + 1,
  };
}
