/**
 * Audio analyzers are first-class objects, not a singleton.
 *
 * Observed in the reference: the Analyzers panel explains "Audio analyzers allow
 * you to change how things react to audio. Here you can see your analyzers and
 * which items are using them", and lists e.g. `Default` (used by Audio Impact,
 * Image, Particles) and `Analyzer (1)` (used by `Layer 1 - Spectrum`).
 *
 * A project export stores each analyzer's settings in its values:
 * `sampleProvider` (`goertzel` / `filter bank`), `outputMultiplier` (about 50-62)
 * and `sampleOutCount` (50 / 128 / 150 in the reference's own projects).
 */

/** How the reference derives band values for this analyzer. */
export type SampleProvider = "goertzel" | "filter bank";

/** Providers in the reference's enum order; `indexOf` picks the wasm index. */
export const SAMPLE_PROVIDERS = ["filter bank", "goertzel"] as const;

export function sampleProviderIndex(provider: string): number {
  const index = (SAMPLE_PROVIDERS as readonly string[]).indexOf(provider);
  // The reference falls back to 0 for unknown values.
  return index >= 0 ? index : 0;
}

/** Per-band weighting curves, in the reference enum's order. */
export const PER_BAND_WEIGHTINGS = ["a", "b", "c", "d", "m"] as const;

export function perBandWeightingIndex(weighting: string): number {
  const index = (PER_BAND_WEIGHTINGS as readonly string[]).indexOf(
    String(weighting).toLowerCase(),
  );
  return index >= 0 ? index : 0;
}

/** Window functions the reference's analyser accepts, in its enum order. */
export const WINDOW_FUNCTIONS = [
  "hann",
  "raised cosine",
  "power of sine",
  "tukey",
  "blackman",
  "nuttall",
  "kaiser",
  "gaussian",
  "triangular",
  "quadratic spline",
  "welch",
  "hamming",
] as const;

/**
 * Index the wasm expects. The reference rewrites `hamming` to `raised cosine`
 * before taking the index, so we do the same.
 */
export function windowFunctionIndex(name: string): number {
  const normalised = name === "hamming" ? "raised cosine" : name;
  const index = (WINDOW_FUNCTIONS as readonly string[]).indexOf(normalised);
  return index >= 0 ? index : 0;
}

/** Frequency mappings in the reference's enum order. */
export const FREQUENCY_SCALES = [
  "linear",
  "log",
  "mel",
  "critical bands",
  "ERB",
  "sinh",
  "nth root",
] as const;

export function frequencyScaleIndex(name: string): number {
  const index = (FREQUENCY_SCALES as readonly string[]).indexOf(name);
  return index >= 0 ? index : 0;
}

export interface Analyzer {
  id: string;
  name: string;
  /**
   * Analysis algorithm named by the reference. Recorded and shown so imported
   * projects read faithfully; our renderer still derives bands with its own FFT.
   */
  sampleProvider: SampleProvider;
  /**
   * Output gain, in the reference's units. 50 is the neutral baseline, so a
   * project's common 50.5 is a ~1% lift and its Default 62 is ~24%.
   */
  outputMultiplier: number;
  /** Band values exposed to the items bound to this analyzer. */
  sampleOutCount: number;
  /** Analysis band in Hz, as the reference stores it (`frequencyRange`). */
  frequencyRange: [number, number];
  /** Window function name, as the reference stores it. */
  windowFunction: string;
  /**
   * Smoothing time constant (reference `smoothingTimeConstant`). Presets use
   * 0.3-0.5 to slow the reaction; the wasm applies it per analyser.
   */
  smoothingTimeConstant?: number;
  /** Reaction alignment, proportional to audio duration (-1 is the reference default). */
  audioReactionAlignment?: number;
  /** Adjustable window parameters (Tukey / Kaiser / Gaussian / power-of-sine). */
  windowParameter?: number;
  windowSkew?: number;
  /** Frequency mapping and its linear factor (reference `frequencyScale`). */
  frequencyScale?: string;
  hzLinearFactor?: number;
  /** Constant-Q settings, used when `sampleProvider` is a filter bank. */
  cqtResolution?: number;
  cqtWindowFunction?: string;
  cqtWindowParameter?: number;
  cqtWindowSkew?: number;
  /** Reference `spectrumConstantQ`: constant-Q analysis on the Goertzel path. */
  spectrumConstantQ?: boolean;
  /** Reference `cqtBandwidth`, 2-16. */
  cqtBandwidth?: number;
  /** Per-bin tilt, dB per octave, applied to each FFT bin (goertzel only). */
  perBinFrequencyTilt?: number;
  /** Per-band tilt, dB per octave: negative values make bass react more. */
  perBandFrequencyTilt?: number;
  /** Reference `perBandWeighting`: A / B / C weighting of each band. */
  perBandWeighting?: string;
  /** Strength of the per-band weighting, 0-0.1. */
  perBandWeightingAmount?: number;
  /** Whether the analyser down-samples its input. */
  downSample?: boolean;
  /**
   * Analysis window length in milliseconds. Real projects range 90-400ms, and
   * this is what distinguishes the analyzers behind a multi-layer spectrum.
   */
  audioDuration: number;
  /**
   * Lead of the analysis window, in the reference's own units (`audioOffset`).
   * The reference passes it straight to the analyser, so a project's 65 shifts
   * every layer's window by the same amount.
   */
  audioOffset: number;
  /**
   * Ids of the items this analyzer drives. Ownership lives here, matching the
   * reference's `audioAnalyzers[id].connections`; an item's own `analyzerId` is
   * a display mirror that must be written through {@link assignUser}.
   */
  users: string[];
}

export const DEFAULT_SAMPLE_OUT_COUNT = 64;
export const DEFAULT_OUTPUT_MULTIPLIER = 50;
export const DEFAULT_AUDIO_DURATION = 200;

export function createAnalyzer(
  id: string,
  name: string,
  options: Partial<
    Pick<
      Analyzer,
      | "sampleProvider"
      | "outputMultiplier"
      | "sampleOutCount"
      | "audioDuration"
      | "audioOffset"
      | "frequencyRange"
      | "windowFunction"
      | "smoothingTimeConstant"
      | "audioReactionAlignment"
      | "windowParameter"
      | "windowSkew"
      | "frequencyScale"
      | "hzLinearFactor"
      | "cqtResolution"
      | "cqtWindowFunction"
      | "cqtWindowParameter"
      | "cqtWindowSkew"
      | "downSample"
      | "spectrumConstantQ"
      | "cqtBandwidth"
      | "perBinFrequencyTilt"
      | "perBandFrequencyTilt"
      | "perBandWeighting"
      | "perBandWeightingAmount"
    >
  > = {},
): Analyzer {
  return {
    id,
    name,
    sampleProvider: options.sampleProvider ?? "goertzel",
    outputMultiplier: options.outputMultiplier ?? DEFAULT_OUTPUT_MULTIPLIER,
    sampleOutCount: options.sampleOutCount ?? DEFAULT_SAMPLE_OUT_COUNT,
    audioDuration: options.audioDuration ?? DEFAULT_AUDIO_DURATION,
    audioOffset: options.audioOffset ?? 0,
    frequencyRange: options.frequencyRange ?? [20, 130],
    windowFunction: options.windowFunction ?? "hann",
    smoothingTimeConstant: options.smoothingTimeConstant ?? 0,
    audioReactionAlignment: options.audioReactionAlignment ?? -1,
    windowParameter: options.windowParameter ?? 1,
    windowSkew: options.windowSkew ?? 0,
    frequencyScale: options.frequencyScale ?? "linear",
    hzLinearFactor: options.hzLinearFactor ?? 0.5,
    cqtResolution: options.cqtResolution ?? 7,
    cqtWindowFunction: options.cqtWindowFunction ?? "hann",
    cqtWindowParameter: options.cqtWindowParameter ?? 1,
    cqtWindowSkew: options.cqtWindowSkew ?? 0,
    spectrumConstantQ: options.spectrumConstantQ ?? false,
    cqtBandwidth: options.cqtBandwidth ?? 8,
    perBinFrequencyTilt: options.perBinFrequencyTilt ?? 0,
    perBandFrequencyTilt: options.perBandFrequencyTilt ?? 0,
    perBandWeighting: (options.perBandWeighting ?? "a").toLowerCase(),
    perBandWeightingAmount: options.perBandWeightingAmount ?? 0,
    downSample: options.downSample ?? true,
    users: [],
  };
}

/** Gain implied by `outputMultiplier`, with 50 as the neutral baseline. */
/**
 * The reference analyser applies `outputMultiplier` itself, as a dB gain with
 * 50 as the neutral baseline (`10^((m - 50)/20)` — verified against the wasm:
 * 0 -> 0.4, 25 -> 7.1, 50 -> 126.5, 100 -> 39998 for the same 0.8 sine), so the
 * renderer must not apply it a second time. Values that come from our fallback
 * FFT are an approximation only used before the wasm finishes loading.
 */
export function analyzerGain(_analyzer: Analyzer): number {
  return 1;
}

export function analyzerById(analyzers: readonly Analyzer[], id: string | null): Analyzer | null {
  if (!id) return null;
  return analyzers.find((analyzer) => analyzer.id === id) ?? null;
}

/** The analyzer that owns `itemId`, or null when it is not bound to one. */
export function analyzerOf(analyzers: readonly Analyzer[], itemId: string): Analyzer | null {
  return analyzers.find((analyzer) => analyzer.users.includes(itemId)) ?? null;
}

/**
 * Bind `itemId` to `analyzerId`, or detach it when null. The item is removed
 * from every analyzer first, so it can never be owned by two at once.
 *
 * Returns the analyzer that ended up owning the item.
 */
export function assignUser(
  analyzers: Analyzer[],
  itemId: string,
  analyzerId: string | null,
): Analyzer | null {
  for (const analyzer of analyzers) {
    const at = analyzer.users.indexOf(itemId);
    if (at >= 0) analyzer.users.splice(at, 1);
  }
  const target = analyzerById(analyzers, analyzerId);
  if (target && !target.users.includes(itemId)) target.users.push(itemId);
  return target;
}

export function detachUser(analyzers: Analyzer[], itemId: string): void {
  assignUser(analyzers, itemId, null);
}

/** Copy of every analyzer's user list, for the undo journal. */
export function snapshotOwnership(analyzers: readonly Analyzer[]): Record<string, string[]> {
  return Object.fromEntries(analyzers.map((analyzer) => [analyzer.id, [...analyzer.users]]));
}

export function restoreOwnership(
  analyzers: readonly Analyzer[],
  snapshot: Record<string, string[]>,
): void {
  for (const analyzer of analyzers) {
    analyzer.users = [...(snapshot[analyzer.id] ?? [])];
  }
}
