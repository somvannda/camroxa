/**
 * Conversion between the reference's `scaleMultiplier` and ours.
 *
 * The reference draws the spectrum's ring at `curRad = 120` px of its own render
 * canvas and scales the whole item by `scaleMultiplier`. Its 1280x720 snapshot
 * shows a 178 px ring, so the reference's factor there is 2.225:
 *
 *   178 px / (120 px * 720/1080) = 2.225
 *
 * Our spectrum is drawn in a calibrated plane, where that same 178 px ring needs
 * a scaleMultiplier of 102 (percent). So one reference factor equals
 * `OUR_SCALE_AT_SNAPSHOT / REFERENCE_SCALE_AT_SNAPSHOT` of ours.
 *
 * Keeping this as an explicit conversion means the reference's own numbers -
 * including an audio-impact automation's `minValue`/`maxValue` - can be imported
 * unchanged instead of being rewritten by hand.
 */
export const REFERENCE_SCALE_AT_SNAPSHOT = 2.225;
export const OUR_SCALE_AT_SNAPSHOT = 103;

export function scaleMultiplierFromReference(value: number): number {
  return (value * OUR_SCALE_AT_SNAPSHOT) / REFERENCE_SCALE_AT_SNAPSHOT;
}

export function scaleMultiplierToReference(value: number): number {
  return (value * REFERENCE_SCALE_AT_SNAPSHOT) / OUR_SCALE_AT_SNAPSHOT;
}
