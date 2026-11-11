/**
 * Per-clip audio settings (spec §81): Volume, Loop, Reverse, Pitch, Speed.
 *
 * Shared by playback and export so both hear the same thing. Pitch and Speed both map
 * to `playbackRate` — this engine has no time-stretcher, so pitching also changes
 * speed (recorded in D-032). Reverse mirrors the source inside the clip, and Loop
 * repeats the source from the clip's offset to the end of the file to fill the clip's
 * timeline length.
 *
 * Pure, so the arithmetic is unit-tested; the callers own the Web Audio nodes.
 */

export type ClipAudioSettings = {
  /** Volume trim in dB, −24…+12 (the captured readout is a dB value). */
  gainDb: number;
  loop: boolean;
  reverse: boolean;
  /** Semitones, −12…+12. */
  pitch: number;
  /** Percent, 50…200 where 100 is the recorded speed. */
  speed: number;
};

export const DEFAULT_CLIP_AUDIO: ClipAudioSettings = {
  gainDb: 0,
  loop: false,
  reverse: false,
  pitch: 0,
  speed: 100,
};

export const GAIN_DB_MIN = -24;
export const GAIN_DB_MAX = 12;
export const PITCH_MIN = -12;
export const PITCH_MAX = 12;
export const SPEED_MIN = 50;
export const SPEED_MAX = 200;

function finite(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/** Coerce whatever the document holds into settings the engine can trust. */
export function sanitizeClipAudio(value: unknown): ClipAudioSettings {
  if (!value || typeof value !== "object") return DEFAULT_CLIP_AUDIO;
  const source = value as Record<string, unknown>;
  return {
    gainDb: clamp(finite(source.gainDb, 0), GAIN_DB_MIN, GAIN_DB_MAX),
    loop: Boolean(source.loop),
    reverse: Boolean(source.reverse),
    pitch: clamp(Math.round(finite(source.pitch, 0)), PITCH_MIN, PITCH_MAX),
    speed: clamp(Math.round(finite(source.speed, 100)), SPEED_MIN, SPEED_MAX),
  };
}

export function dbToGain(db: number): number {
  return Math.pow(10, clamp(db, GAIN_DB_MIN, GAIN_DB_MAX) / 20);
}

/** A reversed copy of a decoded buffer, for Reverse playback and export. */
export function reverseBuffer(context: BaseAudioContext, buffer: AudioBuffer): AudioBuffer {
  const next = context.createBuffer(
    buffer.numberOfChannels,
    buffer.length,
    buffer.sampleRate
  );
  for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
    const source = buffer.getChannelData(channel);
    const target = next.getChannelData(channel);
    for (let index = 0; index < source.length; index += 1) {
      target[index] = source[source.length - 1 - index];
    }
  }
  return next;
}

/** Semitones to a playback-rate factor (one octave doubles the rate). */
export function pitchToRate(semitones: number): number {
  return Math.pow(2, clamp(Math.round(semitones), PITCH_MIN, PITCH_MAX) / 12);
}

export function speedToRate(percent: number): number {
  return clamp(percent, SPEED_MIN, SPEED_MAX) / 100;
}

/** The total rate for a clip: pitch and speed both scale the source. */
export function clipRate(settings: ClipAudioSettings): number {
  return pitchToRate(settings.pitch) * speedToRate(settings.speed);
}

export type PlaybackPlanInput = {
  /** Length of the decoded source in seconds. */
  bufferDuration: number;
  /** How long the clip sits on the timeline. */
  clipDuration: number;
  /** Seconds from the clip start where playback begins (0 for a fresh start). */
  intoClip: number;
  /** Source offset already stored on the clip. */
  offset: number;
  /** Total rate (audition speed × pitch × speed). */
  rate: number;
  reverse: boolean;
  loop: boolean;
};

export type PlaybackPlan = {
  /** Seconds into the buffer to start (already mirrored when reversed). */
  bufferStart: number;
  /** Buffer seconds to play; omitted while looping (the stop time cuts it). */
  bufferLength?: number;
  loop: boolean;
  loopStart: number;
  loopEnd: number;
};

/**
 * Where to start in the (possibly reversed) buffer and how much to play.
 *
 * `intoClip` is timeline seconds; the source offset advances at `rate`, so the buffer
 * position is `offset + intoClip` (the same convention the editor already uses for
 * audition speed).
 */
export function planClipPlayback({
  bufferDuration,
  clipDuration,
  intoClip,
  offset,
  rate,
  reverse,
  loop,
}: PlaybackPlanInput): PlaybackPlan {
  const total = Math.max(0.001, bufferDuration);
  const safeRate = Math.max(0.05, rate);
  const remaining = Math.max(0, clipDuration - Math.max(0, intoClip));
  const sourceStart = clamp(offset + Math.max(0, intoClip), 0, total);

  if (loop) {
    const regionStart = clamp(offset, 0, total);
    const regionEnd = total;
    const start = clamp(sourceStart, regionStart, regionEnd);
    if (reverse) {
      // The looped region mirrored into the reversed buffer, entered at its end.
      return {
        bufferStart: total - start,
        loop: true,
        loopStart: 0,
        loopEnd: Math.max(0.001, regionEnd - regionStart),
      };
    }
    return {
      bufferStart: start,
      loop: true,
      loopStart: regionStart,
      loopEnd: regionEnd,
    };
  }

  const length = Math.min(Math.max(0, remaining) * safeRate, total - sourceStart);
  const safeLength = Math.max(0, length);
  if (reverse) {
    return {
      bufferStart: Math.max(0, total - (sourceStart + safeLength)),
      bufferLength: safeLength,
      loop: false,
      loopStart: 0,
      loopEnd: 0,
    };
  }
  return {
    bufferStart: sourceStart,
    bufferLength: safeLength,
    loop: false,
    loopStart: 0,
    loopEnd: 0,
  };
}

/** Quantize grids from the captured panel (spec §81). */
export type QuantizeGrid = "1/2" | "1/4" | "1/8" | "1/16" | "1/32";

export const QUANTIZE_GRIDS: Array<{ value: QuantizeGrid; label: string }> = [
  { value: "1/2", label: "1/2" },
  { value: "1/4", label: "1/4" },
  { value: "1/8", label: "1/8" },
  { value: "1/16", label: "1/16" },
  { value: "1/32", label: "1/32" },
];

/**
 * Seconds between quantize points for a grid label: the label is a note value, so
 * 1/4 is one beat, 1/8 an eighth, and triplets divide the value by three.
 */
export function quantizeStep(
  secondsPerBar: number,
  grid: QuantizeGrid,
  triplets: boolean
): number {
  const denominator = Number(grid.split("/")[1]);
  // A 4/4 bar holds `denominator` notes of that value; `secondsPerBar` already carries
  // the project meter, so the step is simply the bar over the note value.
  const step = secondsPerBar / denominator;
  return triplets ? step * (2 / 3) : step;
}
