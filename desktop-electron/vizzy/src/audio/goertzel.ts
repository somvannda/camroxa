/**
 * Goertzel band bank, ported from the reference `FFT.wasm` (`f_fb`).
 *
 * The reference's `goertzel` provider evaluates one sliding Goertzel per band
 * over the windowed frame. Unlike the constant-Q path it ignores the CQT
 * kernels entirely: each band is a single frequency at the centre placed by
 * `make_freq_bands_lookup`, with the standard recurrence
 *
 *     s0 = x[i] + 2cos(w)·s1 − s2
 *
 * where `w = 2π·centre/rate`, and the magnitude
 * `sqrt(s1² + s2² − s1·2cos(w)·s2) / n`. The module keeps the coefficient in
 * float32 and the recurrence in float32; so does this port.
 */

import { cqtBandCentres, outputGain, windowTable, type CqtSettings } from "./cqt.ts";

export class GoertzelAnalyser {
  private readonly table: Float32Array;
  private readonly source: Float32Array;
  private readonly coefficients: Float32Array;
  private readonly result: Float32Array;
  private readonly gain: number;
  /** Band centres in Hz, in the analyzer's own layout. */
  readonly centres: Float32Array;
  /** Requested input length (what `analyse` consumes). */
  readonly sampleInCount: number;
  readonly sampleOutCount: number;
  private readonly fftSize: number;
  private readonly downSample: boolean;
  private readonly offsetSamples: number;
  private readonly alignment: number;

  constructor(settings: CqtSettings) {
    const requested = settings.sampleInCount;
    const downSample = (settings.downSample ?? 0) !== 0;
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
    this.offsetSamples = Math.round((-(settings.audioOffset ?? 0) / 1000) * settings.sampleRate);
    this.alignment = settings.audioReactionAlignment ?? -1;
    this.gain = outputGain(settings.outputMultiplier);

    const minHz = Math.max(2, Math.min(settings.minHz, settings.maxHz));
    const maxHz = Math.max(minHz, Math.min(settings.maxHz, 20000));
    this.centres = cqtBandCentres(
      settings.sampleOutCount,
      minHz,
      maxHz,
      settings.frequencyScale,
      settings.hzLinearFactor,
    );
    this.coefficients = new Float32Array(settings.sampleOutCount);
    for (let band = 0; band < settings.sampleOutCount; band += 1) {
      // `f_fb` stores `2·cos(2π·centre/rate)` as a float32.
      this.coefficients[band] = Math.fround(
        2 * Math.cos((2 * Math.PI * this.centres[band]) / rate),
      );
    }

    this.table = windowTable(
      fftSize,
      settings.windowIndex,
      settings.windowParameter,
      settings.windowSkew,
    );
    this.source = new Float32Array(fftSize);
    this.result = new Float32Array(settings.sampleOutCount);
  }

  analyse(buffer: Float32Array): Float32Array {
    const n = this.fftSize;
    const source = this.source;
    const table = this.table;
    const start = Math.round(
      (buffer.length - this.sampleInCount) / 2 -
        (this.alignment * this.sampleInCount) / 2 -
        this.offsetSamples -
        (this.downSample ? this.sampleInCount / 2 : 0),
    );
    const at = (index: number): number =>
      index >= 0 && index < buffer.length ? buffer[index] : 0;
    if (this.downSample) {
      for (let i = 0; i < n; i += 1) {
        source[i] = Math.fround((at(start + i * 2) + at(start + i * 2 + 1)) * 0.5);
      }
    } else {
      for (let i = 0; i < n; i += 1) source[i] = at(start + i);
    }
    for (let i = 0; i < n; i += 1) source[i] = Math.fround(source[i] * table[i]);

    const out = this.result;
    for (let band = 0; band < this.sampleOutCount; band += 1) {
      const coefficient = this.coefficients[band];
      let s1 = 0;
      let s2 = 0;
      for (let i = 0; i < n; i += 1) {
        const s0 = Math.fround(
          Math.fround(source[i] + Math.fround(coefficient * s1)) - s2,
        );
        s2 = s1;
        s1 = s0;
      }
      const power = s1 * s1 + s2 * s2 - s1 * coefficient * s2;
      out[band] = Math.fround((Math.sqrt(Math.max(0, power)) / n) * this.gain);
    }
    return out;
  }
}
