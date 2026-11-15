/**
 * Tempo detection and auto-stretch for added audio (Content → Auto-stretch added audio).
 *
 * The reference copy: "On: audio that you add from your library or through file uploads is
 * stretched to the project tempo when it has a steady beat. Clips without a steady beat
 * keep their original timing. Off: added audio always keeps its original timing and does
 * not set the project tempo. Generated clips are not affected."
 *
 * Detection runs on the same peak envelope the waveform uses: onsets are found, consecutive
 * intervals vote for a tempo, and the vote has to be consistent before anything is
 * stretched. A generated song never goes through here.
 */

import { detectOnsets } from "@/lib/studio-peaks";

export type TempoGuess = {
  bpm: number;
  /** 0–1: share of intervals that agree with the winning tempo. */
  confidence: number;
  beats: number;
};

/** Intervals outside this range are not a plausible beat at the project's scale. */
const MIN_BPM = 50;
const MAX_BPM = 210;

/**
 * Estimate the tempo of a clip from its peak envelope and duration.
 *
 * Returns `null` when there are too few onsets or the intervals disagree, which is the
 * honest answer for a pad, a one-shot or a spoken take — those keep their timing.
 */
export function detectTempo(
  peaks: number[] | null | undefined,
  durationSeconds: number
): TempoGuess | null {
  if (!peaks || !(durationSeconds > 0)) return null;
  const onsets = detectOnsets(peaks, { threshold: 0.16, minGap: 2 });
  if (onsets.length < 4) return null;

  const times = onsets.map((fraction) => fraction * durationSeconds);
  const intervals: number[] = [];
  for (let index = 1; index < times.length; index += 1) {
    const gap = times[index] - times[index - 1];
    if (gap > 0) intervals.push(gap);
  }
  if (intervals.length < 3) return null;

  const sorted = [...intervals].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  if (!(median > 0)) return null;

  // Fold two-beat gaps back onto the beat when half the interval is in range.
  const candidates = new Map<number, number>();
  for (const gap of intervals) {
    for (const factor of [1, 2, 4]) {
      const beat = gap / factor;
      const bpm = 60 / beat;
      if (bpm < MIN_BPM || bpm > MAX_BPM) continue;
      const rounded = Math.round(bpm);
      candidates.set(rounded, (candidates.get(rounded) ?? 0) + 1 / factor);
    }
  }
  if (candidates.size === 0) return null;

  const [bpm, votes] = [...candidates.entries()].sort((a, b) => b[1] - a[1])[0];
  const agreeing = intervals.filter((gap) => {
    const ratio = gap / (60 / bpm);
    return Math.abs(ratio - Math.round(ratio)) < 0.12;
  }).length;
  const confidence = agreeing / intervals.length;
  if (confidence < 0.6) return null;

  return { bpm, confidence, beats: intervals.length + 1 };
}

/**
 * Speed (percent, the Clip Settings scale) that makes `sourceBpm` play at `projectBpm`.
 * Values outside the control's 50–200 range are clamped rather than silently dropped.
 */
export function stretchSpeedPercent(sourceBpm: number, projectBpm: number): number {
  if (!(sourceBpm > 0) || !(projectBpm > 0)) return 100;
  return Math.max(50, Math.min(200, Math.round((projectBpm / sourceBpm) * 100)));
}

/**
 * The stretch an added upload should receive, or `null` to keep its timing.
 * `enabled` is the Content setting; callers pass `settingsRef.current.autoStretch`.
 */
export function autoStretchSpeed(
  peaks: number[] | null | undefined,
  durationSeconds: number,
  projectBpm: number,
  enabled: boolean
): { speed: number; sourceBpm: number; confidence: number } | null {
  if (!enabled) return null;
  const guess = detectTempo(peaks, durationSeconds);
  if (!guess) return null;
  const speed = stretchSpeedPercent(guess.bpm, projectBpm);
  // A 1–2% nudge is inaudible but rewrites the clip; keep the original timing instead.
  if (Math.abs(speed - 100) < 3) return null;
  return { speed, sourceBpm: guess.bpm, confidence: guess.confidence };
}
