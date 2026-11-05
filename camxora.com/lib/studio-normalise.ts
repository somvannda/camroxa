/**
 * Export normalisation (roadmap G11).
 *
 * Exported mixes inherited whatever headroom the master chain left them, so two
 * exports of the same project could differ by several dB depending on clip levels.
 * This puts the sample peak at a fixed target instead, which is what makes an export
 * comparable to the next one.
 *
 * Deliberate limits, so nobody over-trusts it:
 * - It is **sample-peak** normalisation, not LUFS. Integrated loudness needs a
 *   BS.1770 meter; `lib/studio-meter.ts` only approximates true peak.
 * - It runs after the master chain, so the chain still shapes the sound; only the
 *   final level moves.
 * - Only the mix and range exports are normalised. Per-track files stay at unity so
 *   their balance survives reimport (normalising each one separately would silently
 *   flatten the arrangement).
 */

/** Peak target used by the export menu: just under full scale, matching the limiter. */
export const EXPORT_TARGET_PEAK_DB = -1;

function dbToLinear(db: number): number {
  return Math.pow(10, db / 20);
}

/** Loudest sample magnitude across every channel (0 for silence). */
export function peakOf(channels: Float32Array[]): number {
  let peak = 0;
  for (const channel of channels) {
    for (let i = 0; i < channel.length; i++) {
      const magnitude = Math.abs(channel[i]);
      if (magnitude > peak) peak = magnitude;
    }
  }
  return peak;
}

/**
 * Linear gain that puts the loudest sample at `targetPeakDb`.
 *
 * Returns 1 for silence, for a non-finite target, or for a target at/above 0 dBFS
 * (nothing sane to aim for). Both boosts and cuts, so an over-hot render is tamed.
 */
export function normaliseGain(
  channels: Float32Array[],
  targetPeakDb: number = EXPORT_TARGET_PEAK_DB
): number {
  if (!Number.isFinite(targetPeakDb) || targetPeakDb >= 0) return 1;
  const peak = peakOf(channels);
  if (peak <= 0 || !Number.isFinite(peak)) return 1;
  return dbToLinear(targetPeakDb) / peak;
}

/**
 * Apply normalisation and return new channel data (the input is left untouched so a
 * caller can still measure the raw render). Samples are hard-clamped to [-1, 1].
 */
export function normaliseChannels(
  channels: Float32Array[],
  targetPeakDb: number = EXPORT_TARGET_PEAK_DB
): { channels: Float32Array[]; gain: number } {
  const gain = normaliseGain(channels, targetPeakDb);
  if (gain === 1) return { channels, gain };
  const scaled = channels.map((channel) => {
    const out = new Float32Array(channel.length);
    for (let i = 0; i < channel.length; i++) {
      out[i] = Math.max(-1, Math.min(1, channel[i] * gain));
    }
    return out;
  });
  return { channels: scaled, gain };
}

// Dev-only handle so the gain maths can be checked against a rendered file.
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
  (
    window as unknown as {
      __studioNormalise?: {
        peakOf: typeof peakOf;
        normaliseGain: typeof normaliseGain;
        normaliseChannels: typeof normaliseChannels;
      };
    }
  ).__studioNormalise = { peakOf, normaliseGain, normaliseChannels };
}
