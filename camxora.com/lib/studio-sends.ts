/**
 * Per-track FX sends (post-fader-ish sends into two shared buses).
 *
 * The reference UI has no sends; this is a requested addition from the completion pass.
 * A send is a level 0–100 into a shared Delay or Reverb bus, so several tracks share one
 * effect instead of each carrying its own copy.
 */

export type TrackSends = { delay: number; reverb: number };

export const DEFAULT_SENDS: TrackSends = { delay: 0, reverb: 0 };

function clamp(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(0, Math.min(100, value))
    : 0;
}

export function sanitizeSends(input: unknown): TrackSends {
  if (!input || typeof input !== "object") return { ...DEFAULT_SENDS };
  const source = input as Record<string, unknown>;
  return { delay: clamp(source.delay), reverb: clamp(source.reverb) };
}

export function sendsActive(sends: TrackSends): boolean {
  return sends.delay > 0 || sends.reverb > 0;
}

/** Delay bus settings: a dotted-eighth-ish echo, fully wet (the send carries the mix). */
export const DELAY_BUS_PARAMS = { time: 375, feedback: 0.35, mix: 100 };
/** Reverb bus settings: a medium room, fully wet. */
export const REVERB_BUS_PARAMS = {
  time: 2.4,
  mix: 100,
  width: 100,
  damping: 45,
  predelay: 20,
  lowCut: 150,
  highCut: 9000,
};
