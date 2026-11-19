/**
 * Per-analyzer band values.
 *
 * The reference configures each analyzer with its own analysis window
 * (`audioDuration`, 90-400ms in real projects) and output count. That is the
 * only thing distinguishing the eight colour analyzers in a multi-layer
 * spectrum, so each analyzer needs its own band series rather than one shared
 * one — otherwise identically-shaped layers draw identically and only the
 * topmost colour is visible.
 *
 * When the reference wasm analyser is ready its values are resampled into the
 * shared 256 slots ({@link fromValues}). Before it loads, both sample providers
 * run ported engines that reproduce the module's maths: the constant-Q filter
 * bank ({@link CqtAnalyser}) and the Goertzel bank ({@link GoertzelAnalyser}).
 */

import { BAND_WEIGHTS } from "./band-weights.ts";
import { CqtAnalyser, type CqtSettings } from "./cqt.ts";
import { GoertzelAnalyser } from "./goertzel.ts";

/** Settings for the pre-wasm band engines. */
export interface FallbackEngineSettings {
  id: string;
  /** Which ported engine to run, matching the analyzer's `sampleProvider`. */
  provider: "filter bank" | "goertzel";
  cqt: CqtSettings;
  /**
   * Reference `smoothingTimeConstant`. The module smooths every analysis call
   * with `out = s·prev + (1−s)·new`, so this is a per-frame blend, not a time
   * constant.
   */
  smoothingTimeConstant?: number;
  perBandFrequencyTilt?: number;
  perBandWeightingIndex?: number;
  perBandWeightingAmount?: number;
}

/**
 * Weighting in dB at amount 0.1, interpolated over the baked log-frequency grid.
 * The reference wasm scales the curve linearly with the amount.
 */
function weightingDb(index: number, hz: number): number {
  const frequencies = BAND_WEIGHTS.frequencies;
  const curve = BAND_WEIGHTS.curves[Math.min(4, Math.max(0, index))];
  if (hz <= frequencies[0]) return curve[0];
  if (hz >= frequencies[frequencies.length - 1]) return curve[curve.length - 1];
  const x = Math.log(hz);
  let low = 0;
  let high = frequencies.length - 1;
  while (high - low > 1) {
    const mid = (low + high) >> 1;
    if (Math.log(frequencies[mid]) <= x) low = mid;
    else high = mid;
  }
  const x0 = Math.log(frequencies[low]);
  const x1 = Math.log(frequencies[high]);
  const t = x1 === x0 ? 0 : (x - x0) / (x1 - x0);
  return curve[low] + (curve[high] - curve[low]) * t;
}

/** Band slots every analyzer array is written into; the shader indexes 0..255. */
export const ANALYZER_SLOTS = 256;

/** Reference analyzer values are roughly 0..200; our shader wants 0..1. */
export const REFERENCE_VALUE_SCALE = 200;

/**
 * Reference per-band gain: `perBandFrequencyTilt` in dB per octave around
 * 1 kHz and the measured weighting curve scaled by its amount.
 */
export function referenceGain(
  centre: number,
  settings: {
    perBandFrequencyTilt?: number;
    perBandWeightingIndex?: number;
    perBandWeightingAmount?: number;
  },
): number {
  let gain = 1;
  const tilt = settings.perBandFrequencyTilt ?? 0;
  if (tilt !== 0) gain *= 10 ** ((tilt / 20) * Math.log2(centre / 1000));
  const amount = settings.perBandWeightingAmount ?? 0;
  if (amount !== 0) {
    gain *= 10 ** ((weightingDb(settings.perBandWeightingIndex ?? 0, centre) / 20) * (amount / 0.1));
  }
  return gain;
}

/** Both ported engines expose the same analysis surface. */
interface BandEngine {
  readonly centres: Float32Array;
  readonly sampleOutCount: number;
  analyse(samples: Float32Array): Float32Array;
}

interface EngineEntry {
  signature: string;
  engine: BandEngine;
  bands: Float32Array;
  /** Resampled band values in the reference's units, before `/200`. */
  target: Float32Array;
  /** Smoothed band values in the reference's units. */
  smoothed: Float32Array;
}

export class AnalyzerBank {
  private readonly state = new Map<string, Float32Array>();
  private readonly engines = new Map<string, EngineEntry>();
  /** Per-analyzer series at the configured `sampleOutCount`, 0..1. */
  private readonly native = new Map<string, Float32Array>();

  /**
   * Slots for an analyzer's own band series while the wasm is loading. Values
   * are in the reference's units (Trap Motion peaks near 200), so they take the
   * same `/200` scaling and resampling as the wasm path. Smoothing matches the
   * module: `out = s·prev + (1−s)·new` once per analysis call.
   */
  bandsFromEngine(
    samples: Float32Array,
    settings: FallbackEngineSettings,
  ): Float32Array {
    const signature = `${settings.provider}|${JSON.stringify(settings.cqt)}`;
    let entry = this.engines.get(settings.id);
    if (!entry || entry.signature !== signature) {
      const engine: BandEngine =
        settings.provider === "goertzel"
          ? new GoertzelAnalyser(settings.cqt)
          : new CqtAnalyser(settings.cqt);
      entry = {
        signature,
        engine,
        bands: new Float32Array(engine.sampleOutCount),
        target: new Float32Array(ANALYZER_SLOTS),
        smoothed: new Float32Array(ANALYZER_SLOTS),
      };
      this.engines.set(settings.id, entry);
    }

    const values = entry.engine.analyse(samples);
    const centres = entry.engine.centres;
    const count = values.length;
    const bands = entry.bands;
    // The wasm bakes the tilt/weighting into the per-band combined lookup, so
    // apply the reference gain per band before resampling into the 256 slots.
    for (let band = 0; band < count; band += 1) {
      bands[band] = values[band] * referenceGain(centres[band], settings);
    }
    const target = entry.target;
    for (let slot = 0; slot < ANALYZER_SLOTS; slot += 1) {
      const position = (slot / (ANALYZER_SLOTS - 1)) * Math.max(0, count - 1);
      const lower = Math.floor(position);
      const fraction = position - lower;
      const a = bands[Math.min(lower, count - 1)];
      const b = bands[Math.min(lower + 1, count - 1)];
      // Keep the reference's units here: the module smooths before the caller
      // clamps to the shader's 0..1 range.
      target[slot] = a + (b - a) * fraction;
    }

    let out = this.state.get(settings.id);
    if (!out || out.length !== ANALYZER_SLOTS) {
      out = new Float32Array(ANALYZER_SLOTS);
      this.state.set(settings.id, out);
    }
    const smoothing = Math.min(1, Math.max(0, settings.smoothingTimeConstant ?? 0));
    const alpha = 1 - smoothing;
    const smoothed = entry.smoothed;
    for (let slot = 0; slot < ANALYZER_SLOTS; slot += 1) {
      smoothed[slot] += (target[slot] - smoothed[slot]) * alpha;
      out[slot] = Math.min(1, Math.max(0, smoothed[slot] / REFERENCE_VALUE_SCALE));
    }
    // The reference hands the spectrum path exactly `sampleOutCount` values;
    // resampling those 256 shader slots back down produced the wrong band
    // count (the path drew 256 radial segments where the reference draws 100).
    this.storeNative(settings.id, bands, smoothing);
    return out;
  }

  /** Native-length (configured) series for path/math consumers, 0..1. */
  nativeValues(id: string): Float32Array | null {
    return this.native.get(id) ?? null;
  }

  private storeNative(id: string, values: Float32Array, smoothing: number): Float32Array {
    let out = this.native.get(id);
    if (!out || out.length !== values.length) {
      out = new Float32Array(values.length);
      this.native.set(id, out);
    }
    const alpha = 1 - Math.min(1, Math.max(0, smoothing));
    for (let index = 0; index < values.length; index += 1) {
      // The reference's `audioAnalyzerData` series is NOT capped at the shader
      // slot range: a loud band on a high-`outputMultiplier` analyzer (smoking-
      // yamada's "Visually soundkeys-like", outputMultiplier 69) reaches ~1.85
      // in normalized units, and its spectrum path draws that peak. Clamping at
      // 1 flattened every loud low band onto the same height, so the mirrored
      // waveform read as a flat-topped rectangle instead of the reference's lens.
      // Only the GPU slot series (`out` above) is 0..1.
      const target = Math.max(0, values[index] / REFERENCE_VALUE_SCALE);
      out[index] += (target - out[index]) * alpha;
    }
    return out;
  }

  reset(): void {
    this.state.clear();
    this.engines.clear();
    this.native.clear();
  }

  /** Drop cached bands for analyzers that no longer exist. */
  retain(ids: ReadonlySet<string>): void {
    for (const id of this.state.keys()) {
      if (!ids.has(id)) this.state.delete(id);
    }
    for (const id of this.engines.keys()) {
      if (!ids.has(id)) this.engines.delete(id);
    }
    for (const id of this.native.keys()) {
      if (!ids.has(id)) this.native.delete(id);
    }
  }

  /**
   * Slots for a reference-analyzer frame. Its values are in the reference's own
   * units (Trap Motion peaks near 200), so they are scaled into the shader's
   * 0..1 range here.
   */
  fromValues(values: Float32Array, id: string): Float32Array {
    let out = this.state.get(id);
    if (!out || out.length !== ANALYZER_SLOTS) {
      out = new Float32Array(ANALYZER_SLOTS);
      this.state.set(id, out);
    }
    const count = values.length;
    for (let slot = 0; slot < ANALYZER_SLOTS; slot += 1) {
      const t = slot / (ANALYZER_SLOTS - 1);
      const position = t * Math.max(0, count - 1);
      const lower = Math.floor(position);
      const fraction = position - lower;
      const a = values[Math.min(lower, count - 1)];
      const b = values[Math.min(lower + 1, count - 1)];
      const raw = a + (b - a) * fraction;
      out[slot] = Math.min(1, Math.max(0, raw / REFERENCE_VALUE_SCALE));
    }
    // The reference wasm already applies `smoothingTimeConstant` internally, so
    // the native series needs no extra blend.
    this.storeNative(id, values, 0);
    return out;
  }
}
