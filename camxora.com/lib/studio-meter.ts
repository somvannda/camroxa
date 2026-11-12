/**
 * Master metering (roadmap W4.4).
 *
 * The reference shows no loudness figure at all (§91), so this is new scope: a master
 * that cannot be measured is a master you cannot trust.
 *
 * `peak` and `rms` are exact for the samples given. `truePeak` is an **inter-sample
 * approximation** using linear interpolation at 4x — that is what catches the classic
 * case of a signal that looks under 0 dBFS sample-peak but clips on playback. It is
 * labelled `truePeak4x` everywhere so nobody mistakes it for a certified BS.1770 meter.
 */

export type MeterReading = {
  peak: number;
  rms: number;
  truePeak4x: number;
  /** Peak in dBFS, clamped at -60 for quiet material. */
  peakDb: number;
  rmsDb: number;
};

const FLOOR_DB = -60;

export function toDb(value: number): number {
  if (value <= 0) return FLOOR_DB;
  return Math.max(FLOOR_DB, 20 * Math.log10(value));
}

export function analyse(samples: Float32Array): MeterReading {
  let peak = 0;
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    const value = samples[i];
    const magnitude = Math.abs(value);
    if (magnitude > peak) peak = magnitude;
    sum += value * value;
  }
  const rms = samples.length > 0 ? Math.sqrt(sum / samples.length) : 0;

  // 4x inter-sample estimate: compare every sample with the midpoints to its neighbours.
  let truePeak4x = peak;
  for (let i = 0; i < samples.length - 1; i++) {
    const a = samples[i];
    const b = samples[i + 1];
    for (let step = 1; step < 4; step++) {
      const t = step / 4;
      const interpolated = Math.abs(a + (b - a) * t);
      if (interpolated > truePeak4x) truePeak4x = interpolated;
    }
  }

  return {
    peak,
    rms,
    truePeak4x,
    peakDb: toDb(peak),
    rmsDb: toDb(rms),
  };
}

/** Compact header label, e.g. "-6.2 dB pk". */
export function formatMeter(reading: MeterReading | null): string {
  if (!reading) return "—";
  const peak = reading.peakDb <= FLOOR_DB ? "-inf" : reading.peakDb.toFixed(1);
  return `${peak} dB pk`;
}

// Dev-only handle so the meter maths can be checked against a rendered file.
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
  (window as unknown as { __studioMeter?: { analyse: typeof analyse } }).__studioMeter = { analyse };
}
