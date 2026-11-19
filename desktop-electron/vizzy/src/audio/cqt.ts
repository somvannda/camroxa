/**
 * Constant-Q filter bank, ported from the reference `FFT.wasm`.
 *
 * This is the pre-wasm path for the reference's `filter bank` provider. It is
 * not an approximation: every formula below was recovered from the shipped
 * module (`_make_window_lookup`, `_make_cqt_lookup`, `_make_freq_bands_lookup`,
 * `_analyse`) and verified against the running wasm band by band. When the
 * module is ready it remains authoritative; this exists so the first frames and
 * the module-less case look the same.
 *
 * The pieces, in the order `_analyse` runs them:
 *
 * 1. `windowTable` is `_make_window_lookup`: the selected window, skew-warped
 *    and normalised so its samples sum to the frame length.
 * 2. The windowed frame is transformed with a real FFT. The module keeps the
 *    half spectrum packed as `[re0, nyquist, re1, im1, ...]` and divides it by
 *    `nfft / 4`; both are reproduced exactly.
 * 3. `buildCqtKernel` is `_make_cqt_lookup`: one windowed, alternating-sign
 *    kernel per band over the band's FFT bins, with the mirrored-bin pairs.
 * 4. `analyse` accumulates the four weighted sums and combines them
 *    (`hypot(hypot(n+p, o-m), hypot(m+o, n-p)) * 0.125`), then applies the
 *    module's combined gain (its output multiplier in dB).
 *
 * The module accumulates in `f32`, so the sums are rounded with `Math.fround`
 * after every step. That is what keeps the fallback within a few 1e-6 of the
 * wasm instead of drifting by 1e-4 at high bands.
 */

import { dftInPlace } from "./fft.ts";
import { scaleForward, scaleInverse } from "./band-scales.ts";

/** `FLT_MAX`, used by the module for the non-constant-Q bandwidth. */
const FLT_MAX = 3.4028234663852886e38;

/**
 * The module's untouched output-multiplier field. It stores the multiplier in
 * dB and starts at 56; a non-positive setting leaves it alone (the reference
 * only calls `_set_output_multipler` for positive values).
 */
const DEFAULT_OUTPUT_MULTIPLIER_DB = 56;

export function outputGain(outputMultiplier: number): number {
  const db = outputMultiplier > 0 ? outputMultiplier : DEFAULT_OUTPUT_MULTIPLIER_DB;
  return 10 ** (db / 20);
}

/**
 * `f_z` from the module: the twelve window functions. Note that the reference's
 * "Kaiser" is a cosh window, not the usual Bessel one; that is what the shipped
 * module evaluates (`f_sa` is cosh).
 */
export function windowValue(position: number, index: number, parameter: number): number {
  const a = position;
  const e = Math.abs(a);
  if (e > 1) return 1;
  switch (index) {
    case 0: {
      // Hann
      const c = Math.cos(a * Math.PI * 0.5);
      return c * c;
    }
    case 1:
      // Raised cosine (the reference rewrites "hamming" to this)
      return Math.cos(a * Math.PI) * 0.46 + 0.54;
    case 2:
      // Power of sine
      return Math.cos(a * Math.PI * 0.5) ** parameter;
    case 3: {
      // Tukey
      if (parameter <= 0 || e <= 1 - parameter) return 1;
      const s = Math.sin(((a > 0 ? 1 - a : a + 1) * Math.PI) / (2 * parameter));
      return s * s;
    }
    case 4:
      // Blackman
      return Math.cos(a * Math.PI) * 0.5 + 0.42 + Math.cos(2 * a * Math.PI) * 0.08;
    case 5:
      // Nuttall
      return (
        Math.cos(2 * a * Math.PI) * 0.144232 +
        Math.cos(a * Math.PI) * 0.487396 +
        0.355768 +
        Math.cos(3 * a * Math.PI) * 0.012604
      );
    case 6: {
      // "Kaiser": the module uses cosh, not the Bessel I0.
      const beta = parameter * parameter;
      return Math.cosh(Math.sqrt(Math.max(0, 1 - a * a)) * beta) / Math.cosh(beta);
    }
    case 7: {
      // Gaussian
      const c = a * parameter;
      return Math.exp(-(c * c));
    }
    case 8:
      // Triangular
      return 1 - e;
    case 9: {
      // Quadratic spline
      const d = a * 1.414214;
      if (e <= 0.5) return 1 - d * d;
      const q = Math.abs(d) - 1.414214;
      return q * q;
    }
    case 10:
      // Welch
      return 1 - a * a;
    default:
      // Rectangular
      return 1;
  }
}

/**
 * The module's window skew: a Möbius warp of the window position. Positive
 * skew pulls the window towards earlier samples.
 */
function skewPosition(position: number, skew: number): number {
  if (skew === 0) return position;
  const w = skew * skew * 10;
  const x = w + 1;
  if (skew > 0) {
    const s = position * 0.5 - 0.5;
    return 2 * ((x * s) / (1 - w * s)) + 1;
  }
  const s = position * 0.5 + 0.5;
  return 2 * ((x * s) / (1 + w * s)) - 1;
}

/**
 * `_make_window_lookup`: the window sampled over `[-1, 1]` and normalised so
 * the samples sum to the frame length. Positions are computed in double and the
 * stored table is `f32`, like the module.
 */
export function windowTable(
  length: number,
  index: number,
  parameter: number,
  skew: number,
): Float32Array {
  const table = new Float32Array(length);
  let sum = 0;
  for (let i = 0; i < length; i += 1) {
    const position = length > 1 ? (2 * i) / (length - 1) - 1 : 0;
    const value = windowValue(skewPosition(position, skew), index, parameter);
    table[i] = value;
    sum += value;
  }
  const normalise = sum !== 0 ? length / sum : 0;
  for (let i = 0; i < length; i += 1) table[i] = Math.fround(table[i] * normalise);
  return table;
}

/**
 * Band centres from `_make_freq_bands_lookup`: the endpoints are mapped through
 * the selected scale and the centres run from low to high inclusively.
 */
export function cqtBandCentres(
  count: number,
  minHz: number,
  maxHz: number,
  frequencyScale: string,
  hzLinearFactor: number,
): Float32Array {
  const centres = new Float32Array(count);
  const low = scaleForward(minHz, frequencyScale, hzLinearFactor);
  const high = scaleForward(maxHz, frequencyScale, hzLinearFactor);
  const span = high - low;
  for (let band = 0; band < count; band += 1) {
    const position = count > 1 ? band / (count - 1) : 0;
    centres[band] = scaleInverse(low + span * position, frequencyScale, hzLinearFactor);
  }
  return centres;
}

export interface CqtSettings {
  sampleRate: number;
  /** Transform size, already clamped to the module's 128..32768 range. */
  sampleInCount: number;
  sampleOutCount: number;
  minHz: number;
  maxHz: number;
  frequencyScale: string;
  hzLinearFactor: number;
  windowIndex: number;
  windowParameter: number;
  windowSkew: number;
  cqtResolution: number;
  cqtBandwidth: number;
  cqtWindowIndex: number;
  cqtWindowParameter: number;
  cqtWindowSkew: number;
  spectrumConstantQ: boolean;
  outputMultiplier: number;
  /** Reference `downSample`: average input pairs and halve the rate. */
  downSample?: number;
  /** Reference `audioOffset` in milliseconds (positive = later window). */
  audioOffset?: number;
  /** Reference `audioReactionAlignment`; the module's default is -1. */
  audioReactionAlignment?: number;
}

/** The band centre used by `_make_cqt_lookup`, clamped like `_resize_input`. */
function clampRange(settings: CqtSettings): { minHz: number; maxHz: number } {
  const minHz = Math.max(2, Math.min(settings.minHz, settings.maxHz));
  const maxHz = Math.max(minHz, Math.min(settings.maxHz, 20000));
  return { minHz, maxHz };
}

/**
 * Kernels for every output band, plus the packed real-FFT layout the module
 * reads. `offsets[i]` is the float index of the band's direct bin, `mirror[i]`
 * the mirrored bin; either can be `nfft` or more, meaning the module reads past
 * the packed spectrum (zeros) and the analysis must do the same.
 */
export class CqtAnalyser {
  private readonly table: Float32Array;
  private readonly source: Float32Array;
  private readonly real: Float32Array;
  private readonly imag: Float32Array;
  private readonly gains: number[];
  private readonly counts: Int32Array;
  private readonly weights: Float32Array[];
  private readonly direct: Int32Array[];
  private readonly mirror: Int32Array[];
  private readonly result: Float32Array;
  /** Band centres in Hz, in the analyzer's own layout. */
  readonly centres: Float32Array;
  /** Requested input length (what `analyse` consumes). */
  readonly sampleInCount: number;
  /** Transform size after the optional input decimation. */
  private readonly fftSize: number;
  private readonly downSample: boolean;
  /** Samples the module subtracts from the window position (`a[32]`). */
  private readonly offsetSamples: number;
  /** Reference `audioReactionAlignment` (`a[33]`). */
  private readonly alignment: number;
  readonly sampleOutCount: number;

  constructor(settings: CqtSettings) {
    const requested = settings.sampleInCount;
    const downSample = (settings.downSample ?? 0) !== 0;
    // `_resize_input`: the rate and frame halve, and the halved frame is rounded
    // up to an even length.
    let fftSize = requested;
    if (downSample) {
      const half = Math.floor(requested / 2);
      fftSize = half + (half % 2);
    }
    const rate = downSample ? settings.sampleRate / 2 : settings.sampleRate;
    this.downSample = downSample;
    this.fftSize = fftSize;
    this.sampleInCount = requested;
    this.sampleOutCount = settings.sampleOutCount;
    // `setAudioOffset` converts milliseconds at the audio context's rate.
    this.offsetSamples = Math.round((-(settings.audioOffset ?? 0) / 1000) * settings.sampleRate);
    this.alignment = settings.audioReactionAlignment ?? -1;

    this.table = windowTable(
      fftSize,
      settings.windowIndex,
      settings.windowParameter,
      settings.windowSkew,
    );
    this.source = new Float32Array(fftSize);
    this.real = new Float32Array(fftSize);
    this.imag = new Float32Array(fftSize);
    this.result = new Float32Array(settings.sampleOutCount);

    const { minHz, maxHz } = clampRange(settings);
    const centres = cqtBandCentres(
      settings.sampleOutCount,
      minHz,
      maxHz,
      settings.frequencyScale,
      settings.hzLinearFactor,
    );
    this.centres = centres;

    const binsPerHz = fftSize / rate;
    const maxHalfWidth = fftSize / rate;
    const bandwidth = settings.cqtBandwidth * binsPerHz;
    const resolution = settings.cqtResolution;

    const counts = new Int32Array(settings.sampleOutCount);
    const weights: Float32Array[] = [];
    const direct: Int32Array[] = [];
    const mirror: Int32Array[] = [];
    const gains: number[] = [];

    for (let band = 0; band < settings.sampleOutCount; band += 1) {
      const centre = centres[band];
      const position = centre * binsPerHz;
      // `ca` is the kernel's full width in bins. The decompiled expression
      // prints as `z / y * min(...)`, but the module divides by the min term.
      const limit = settings.spectrumConstantQ
        ? 2 * resolution / centre
        : FLT_MAX;
      const halfWidth = bandwidth / Math.min(limit, maxHalfWidth) / 2;
      const start = Math.ceil(position - halfWidth);
      const end = Math.floor(position + halfWidth);
      const count = end - start + 1;
      counts[band] = Math.max(0, count);
      const bandWeights = new Float32Array(Math.max(0, count));
      const bandDirect = new Int32Array(Math.max(0, count));
      const bandMirror = new Int32Array(Math.max(0, count));
      for (let i = 0; i < count; i += 1) {
        const bin = start + i;
        const q = (2 * (bin - position)) / (halfWidth * 2);
        const weight = windowValue(
          skewPosition(q, settings.cqtWindowSkew),
          settings.cqtWindowIndex,
          settings.cqtWindowParameter,
        );
        bandWeights[i] = Math.fround((bin & 1) === 1 ? -weight : weight);
        bandDirect[i] = Math.min(fftSize - 1, Math.max(0, bin)) * 2;
        bandMirror[i] = Math.min(fftSize - 1, Math.max(0, fftSize - bin)) * 2;
      }
      weights.push(bandWeights);
      direct.push(bandDirect);
      mirror.push(bandMirror);
      gains.push(outputGain(settings.outputMultiplier));
    }

    this.counts = counts;
    this.weights = weights;
    this.direct = direct;
    this.mirror = mirror;
    this.gains = gains;
  }

  /**
   * The module's packed half spectrum. `index` is a float index into the packed
   * array; anything at or past `fftSize` reads as zero because the module only
   * writes the first `fftSize` floats (band 0 packs DC and Nyquist into its pair).
   */
  private at(index: number): number {
    const nfft = this.fftSize;
    if (index >= nfft) return 0;
    const bin = index >> 1;
    if ((index & 1) === 0) return this.real[bin];
    return bin === 0 ? this.real[nfft / 2] : this.imag[bin];
  }

  analyse(buffer: Float32Array): Float32Array {
    const nfft = this.fftSize;
    const real = this.real;
    const imag = this.imag;
    const table = this.table;
    const source = this.source;
    // The module selects its window inside the shared buffer:
    // start = (length - nfft)/2 - alignment·nfft/2 - offsetSamples.
    const start = Math.round(
      (buffer.length - this.sampleInCount) / 2 -
        (this.alignment * this.sampleInCount) / 2 -
        this.offsetSamples -
        (this.downSample ? this.sampleInCount / 2 : 0),
    );
    const at = (index: number): number =>
      index >= 0 && index < buffer.length ? buffer[index] : 0;
    if (this.downSample) {
      // `_resize_input` averages each pair of inputs before the transform.
      for (let i = 0; i < nfft; i += 1) {
        source[i] = Math.fround((at(start + i * 2) + at(start + i * 2 + 1)) * 0.5);
      }
    } else {
      for (let i = 0; i < nfft; i += 1) source[i] = at(start + i);
    }
    for (let i = 0; i < nfft; i += 1) {
      real[i] = Math.fround(source[i] * table[i]);
      imag[i] = 0;
    }
    dftInPlace(real, imag);

    const out = this.result;
    const scale = 0.125 * (4 / nfft);
    for (let band = 0; band < this.sampleOutCount; band += 1) {
      const count = this.counts[band];
      const weights = this.weights[band];
      const direct = this.direct[band];
      const mirror = this.mirror[band];
      let p = 0;
      let n = 0;
      let o = 0;
      let m = 0;
      for (let i = 0; i < count; i += 1) {
        const weight = weights[i];
        const d = direct[i];
        const r = mirror[i];
        p = Math.fround(p + Math.fround(weight * this.at(d)));
        o = Math.fround(o + Math.fround(weight * this.at(d + 1)));
        n = Math.fround(n + Math.fround(weight * this.at(r)));
        m = Math.fround(m + Math.fround(weight * this.at(r + 1)));
      }
      const magnitude = Math.hypot(
        Math.hypot(Math.fround(n + p), Math.fround(o - m)),
        Math.hypot(Math.fround(m + o), Math.fround(n - p)),
      );
      out[band] = Math.fround(magnitude * scale * this.gains[band]);
    }
    return out;
  }
}
