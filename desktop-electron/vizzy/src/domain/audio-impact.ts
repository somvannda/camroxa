import type { AudioImpactSettings } from "./types";
import { REFERENCE_VALUE_SCALE } from "../audio/analyzer-bank";

/**
 * The reference's audio-impact automation, ported from its `AudioImpact` class.
 *
 * Recovered behaviour (`updateAutomation`):
 *
 *   let data = bands for the bound analyser (dropped below `floorValue`)
 *   const maxAudioImpact = project-wide maximum impact
 *   if (maxAudioImpact <= 0) return minValue
 *   let magnitude = hypot(...data)
 *   if (ceilingValue > 0) magnitude = min(magnitude, ceilingValue)
 *   let value = min + (max - min) * (sensitivity * magnitude / maxAudioImpact)
 *   if deltaSmoothing: falling values decay by deltaDecay, and rises smaller
 *     than deltaThreshold also decay by deltaDecay
 *   if (previous === min) previous = value
 *   else value = previous * smoothing + (1 - smoothing) * value
 *   value = clamp(value, min, max)
 *   previous = value
 *   // `isCumulative` accumulates instead of replacing
 *
 * The reference converts the analyser's raw magnitudes; ours are normalised by
 * the same factor the particle port already uses (`normalised * 200`), so the
 * project's own `audioImpact.max` (1254.4 for the Trap Motion export) stays the
 * correct normaliser.
 */
/**
 * Raw-band conversion. The analyser hands back bands divided by
 * `REFERENCE_VALUE_SCALE` (the shader normalisation); the reference's own band
 * series and its `maxAudioImpact` are on the 0..200 scale, so multiplying the
 * native series back up is what makes `sensitivity * magnitude / maxImpact`
 * mean the same thing in both. (The older note here claimed 800; the analyser
 * has normalised by 200 since the shader slots became 0..1.)
 */
const BAND_SCALE = REFERENCE_VALUE_SCALE;

interface ImpactState {
  previous: number;
  cumulative: number;
}

export class AudioImpactEngine {
  private readonly states = new Map<string, ImpactState>();

  /** Forget running values, e.g. when playback restarts or a project is loaded. */
  reset(): void {
    this.states.clear();
  }

  /**
   * One frame of an audio-impact automation.
   *
   * @param id        Automation id, so each row keeps its own smoother state.
   * @param settings  The automation's own impact settings.
   * @param bands     Normalised band magnitudes, or null before audio is ready.
   * @param maxImpact The project's maximum impact (`audioImpact.max`).
   */
  sample(
    id: string,
    settings: AudioImpactSettings,
    bands: Float32Array | null | undefined,
    maxImpact: number,
  ): number | null {
    if (!bands || bands.length === 0) return null;
    // Shipped `updateAutomation` guards the whole mapping with `minValue !==
    // maxValue` (`if (d !== f && ...)`), so a degenerate row emits no updates
    // at all and the driven controller keeps its authored value. Returning
    // null here rather than `min` is what keeps a flat range inert.
    if (settings.min === settings.max) return null;
    if (!(maxImpact > 0)) {
      this.states.set(id, { cumulative: 0, previous: settings.min });
      return settings.min;
    }

    let magnitude: number;
    const floor = Math.max(0, settings.floor);
    if (floor > 0) {
      let sum = 0;
      let count = 0;
      for (const band of bands) {
        if (band * BAND_SCALE < floor) continue;
        const scaled = band * BAND_SCALE;
        sum += scaled * scaled;
        count += 1;
      }
      magnitude = count > 0 ? Math.sqrt(sum) : 0;
    } else {
      let sum = 0;
      for (const band of bands) {
        const scaled = band * BAND_SCALE;
        sum += scaled * scaled;
      }
      magnitude = Math.sqrt(sum);
    }

    if (settings.ceiling > 0) magnitude = Math.min(magnitude, settings.ceiling);

    const state = this.states.get(id) ?? { cumulative: 0, previous: settings.min };

    const t = clamp01((settings.sensitivity * magnitude) / maxImpact);
    let value = settings.min + (settings.max - settings.min) * t;
    if (settings.color) {
      state.previous = value;
      this.states.set(id, state);
      return value;
    }

    // Shipped AudioImpact.updateAutomation: delta smoothing operates on the
    // mapped value and is skipped for colour variants.
    if (settings.deltaSmoothing) {
      const decay = settings.deltaDecay ?? 0.01;
      const threshold = settings.deltaThreshold ?? 0;
      const delta = value - state.previous;
      if (delta < 0) {
        value =
          state.previous - decay <= settings.min ? settings.min : state.previous - decay;
      } else if (delta < threshold) {
        value = value - decay <= settings.min ? settings.min : value - decay;
      }
    }

    const smoothing = clamp01(settings.smoothing);
    // The reference branches on the direction of the range, initialising the
    // smoother from that end so the first frame does not ease in from zero.
    if (settings.min < settings.max) {
      if (state.previous === settings.min) state.previous = value;
      else value = state.previous * smoothing + (1 - smoothing) * value;
      value = Math.max(settings.min, Math.min(value, settings.max));
    } else {
      if (state.previous === settings.max) state.previous = value;
      else value = state.previous * smoothing + (1 - smoothing) * value;
      value = Math.min(settings.min, Math.max(value, settings.max));
    }

    // Cumulative accumulates the smoothed value and keeps `previous` at the
    // pre-cumulative value, exactly like the reference.
    let output = value;
    if (settings.cumulative) {
      state.cumulative += value;
      output = state.cumulative;
    }

    state.previous = value;
    this.states.set(id, state);
    return output;
  }
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}
