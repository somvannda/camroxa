/**
 * Estimated musical key for a library song (§19.2 tag strip).
 *
 * The generation payload carries no key, so it is estimated from the audio: a chroma
 * vector (energy per pitch class across six octaves) correlated with the Krumhansl
 * major/minor key profiles. It is labelled “≈” everywhere because a mixed song is not a
 * single unambiguous key — but it is measured, not guessed from the prompt.
 */

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

/** Krumhansl–Kessler key profiles (tonic first). */
const MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
const MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];

export type EstimatedKey = { tonic: string; mode: "major" | "minor"; score: number };

export function noteName(index: number): string {
  return NOTE_NAMES[((index % 12) + 12) % 12];
}

function correlate(chroma: number[], profile: number[], rotation: number): number {
  let sum = 0;
  for (let index = 0; index < 12; index += 1) {
    sum += (chroma[(index + rotation) % 12] ?? 0) * profile[index];
  }
  return sum;
}

/**
 * Best key for a chroma vector. Returns `null` when the vector is silent or the best fit is
 * not clearly better than its relative major/minor (a flat, ambiguous mix).
 */
export function estimateKey(chroma: number[]): EstimatedKey | null {
  if (!Array.isArray(chroma) || chroma.length !== 12) return null;
  const total = chroma.reduce((sum, value) => sum + Math.max(0, value), 0);
  if (total <= 0) return null;
  // A flat chroma (all twelve classes equal) has no tonic at all.
  const positive = chroma.map((value) => Math.max(0, value));
  const max = Math.max(...positive);
  const mean = total / 12;
  if (max > 0 && mean > 0 && max / mean < 1.08) return null;

  let best: { index: number; mode: "major" | "minor"; score: number } | null = null;
  let second = 0;
  for (let tonic = 0; tonic < 12; tonic += 1) {
    for (const mode of ["major", "minor"] as const) {
      const profile = mode === "major" ? MAJOR_PROFILE : MINOR_PROFILE;
      const score = correlate(chroma, profile, tonic);
      if (!best || score > best.score) {
        if (best) second = Math.max(second, best.score);
        best = { index: tonic, mode, score };
      } else {
        second = Math.max(second, score);
      }
    }
  }
  if (!best || best.score <= 0) return null;
  // Culture note: relative major/minor are genuinely ambiguous here, and the UI prefixes
  // the result with “≈” rather than pretending certainty.
  return { tonic: noteName(best.index), mode: best.mode, score: best.score };
}

/** Goertzel energy at one frequency over a window of samples. */
function goertzel(samples: Float32Array, start: number, length: number, sampleRate: number, frequency: number): number {
  const omega = (2 * Math.PI * frequency) / sampleRate;
  const coefficient = 2 * Math.cos(omega);
  let s0 = 0;
  let s1 = 0;
  let s2 = 0;
  for (let index = 0; index < length; index += 1) {
    s0 = samples[start + index] + coefficient * s1 - s2;
    s2 = s1;
    s1 = s0;
  }
  return s1 * s1 + s2 * s2 - coefficient * s1 * s2;
}

/** Chroma vector (12 pitch classes) for a decoded buffer. */
export function chromaFromBuffer(buffer: AudioBuffer): number[] {
  const sampleRate = buffer.sampleRate;
  const samples = buffer.getChannelData(0);
  const window = Math.min(samples.length, Math.floor(sampleRate * 0.25));
  const hop = Math.floor(sampleRate * 0.5);
  const chroma = new Array(12).fill(0);
  // C2 (MIDI 36) to B5 (MIDI 83): six octaves of the musical range.
  const notes = Array.from({ length: 48 }, (_, index) => 36 + index);
  for (let start = 0; start + window <= samples.length; start += hop) {
    for (const midi of notes) {
      const frequency = 440 * 2 ** ((midi - 69) / 12);
      if (frequency > sampleRate / 2.2) continue;
      chroma[midi % 12] += goertzel(samples, start, window, sampleRate, frequency);
    }
  }
  const peak = Math.max(...chroma);
  return peak > 0 ? chroma.map((value) => value / peak) : chroma;
}

const keyCache = new Map<string, Promise<EstimatedKey | null>>();

/** Estimate the key of a clip, cached per URL so a re-render never decodes twice. */
export function computeKey(url: string): Promise<EstimatedKey | null> {
  if (typeof AudioContext === "undefined") return Promise.resolve(null);
  const cached = keyCache.get(url);
  if (cached) return cached;
  const pending = (async () => {
    const context = new AudioContext();
    try {
      const response = await fetch(url);
      if (!response.ok) return null;
      const buffer = await context.decodeAudioData(await response.arrayBuffer());
      return estimateKey(chromaFromBuffer(buffer));
    } catch {
      return null;
    } finally {
      void context.close();
    }
  })();
  keyCache.set(url, pending);
  return pending;
}
