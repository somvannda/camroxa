import {
  SequentialFft,
  SimdFft,
  ThreadedFft,
  probeCapabilities,
  selectTier,
  type FftCapabilities,
  type FftTier,
} from "./fft";

/**
 * A source of time-domain samples addressed by *project time*, not wall clock.
 *
 * Time addressing is what makes preview scrubbing and offline export agree:
 * sampling the same second always yields the same window, so a rendered frame is
 * reproducible and a scrub to 3.42s shows exactly what an export would encode.
 */
export interface SpectrumSource {
  fill(out: Float32Array, timeSeconds: number): void;
  /**
   * Per-channel variant for stereo consumers. `timeSeconds` is a window start,
   * matching `fill`. Omitted by synthetic sources.
   */
  fillChannel?(out: Float32Array, timeSeconds: number, channel: number): void;
  readonly label: string;
  /** Sample rate the windows are expressed in; the reference uses the audio context rate. */
  readonly sampleRate?: number;
}

/** Deterministic synthetic signal — same amplitude at the same time, always. */
export class SyntheticSource implements SpectrumSource {
  readonly label = "synthetic";
  readonly sampleRate = 48000;

  fill(out: Float32Array, timeSeconds: number): void {
    const rate = 48000;
    for (let i = 0; i < out.length; i += 1) {
      const t = timeSeconds + i / rate;
      const env = 0.55 + 0.45 * Math.sin(t * 0.7);
      out[i] =
        env * 0.35 * Math.sin(2 * Math.PI * 110 * t) +
        0.22 * Math.sin(2 * Math.PI * 220 * t + 0.4) +
        0.16 * Math.sin(2 * Math.PI * 440 * t * (1 + 0.002 * Math.sin(t))) +
        0.1 * Math.sin(2 * Math.PI * 1320 * t) +
        0.05 * (Math.random() * 2 - 1);
    }
  }
}

/** Plays a decoded AudioBuffer by absolute time. Used for preview and export. */
export class BufferSource implements SpectrumSource {
  readonly label: string;
  private readonly channels: Float32Array[];
  private readonly length: number;

  constructor(private readonly buffer: AudioBuffer, name: string) {
    this.label = name;
    this.channels = [];
    for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
      this.channels.push(buffer.getChannelData(channel));
    }
    if (this.channels.length === 0) this.channels.push(new Float32Array(1));
    this.length = this.channels[0].length;
  }

  get duration(): number {
    return this.buffer.duration;
  }

  get sampleRate(): number {
    return this.buffer.sampleRate;
  }

  fill(out: Float32Array, timeSeconds: number): void {
    this.fillChannel(out, timeSeconds, 0);
  }

  fillChannel(out: Float32Array, timeSeconds: number, channel: number): void {
    const data = this.channels[Math.min(Math.max(0, channel), this.channels.length - 1)];
    const start = Math.floor(timeSeconds * this.buffer.sampleRate);
    for (let i = 0; i < out.length; i += 1) {
      const index = start + i;
      out[i] = index >= 0 && index < this.length ? data[index] : 0;
    }
  }
}

/** Realtime window from a live AnalyserNode, for monitoring while playing. */
export class ElementSource implements SpectrumSource {
  readonly label = "audio element";
  constructor(private readonly analyser: AnalyserNode) {}

  get sampleRate(): number {
    return this.analyser.context.sampleRate;
  }

  fill(out: Float32Array): void {
    this.analyser.getFloatTimeDomainData(out as Float32Array<ArrayBuffer>);
  }
}

/** Reference attenuator curve (`l` in the Audio module). */
function attenuationFor(bassBoost: number, additionalGainDb: number): number {
  const t = additionalGainDb - 3;
  if (bassBoost <= 0) return 1;
  const i = 20 * Math.log10(bassBoost) - t;
  return 10 ** (-i / 20);
}

export class AudioBus {
  readonly context: AudioContext;
  readonly analyser: AnalyserNode;
  readonly gain: GainNode;
  /**
   * Reference live chain: the dry source plus a low-passed branch whose gain is
   * `bassBoostAmount`, summed at the master gain. The low-pass branch alone must
   * never be the only path: its default gain is 0, so a series-only chain is
   * silent until bass boost is raised.
   */
  readonly bass: BiquadFilterNode;
  readonly bassGain: GainNode;
  readonly compressor: DynamicsCompressorNode;

  private volume = 1;
  private muted = false;
  private bassBoost = 0;
  private attenuator = false;
  private additionalGainDb = 0;
  private compressorEnabled = false;
  private playbackRate = 1;

  constructor() {
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.context = new Ctor();
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.smoothingTimeConstant = 0;
    this.gain = this.context.createGain();
    this.gain.connect(this.context.destination);

    this.bass = this.context.createBiquadFilter();
    this.bass.type = "lowpass";
    this.bass.frequency.value = 60;
    this.bassGain = this.context.createGain();
    this.bassGain.gain.value = 0;
    this.compressor = this.context.createDynamicsCompressor();
    // Reference limiter settings.
    this.compressor.threshold.value = -4;
    this.compressor.knee.value = 0;
    this.compressor.ratio.value = 20;
    this.compressor.attack.value = 0.001;
    this.compressor.release.value = 1;
    this.bass.connect(this.bassGain);
    this.bassGain.connect(this.gain);
  }

  /** Mirrors the reference's Audio object settings. */
  configure(settings: {
    volume?: number;
    muted?: boolean;
    bassBoost?: number;
    frequency?: number;
    playbackRate?: number;
    attenuator?: boolean;
    additionalGainDb?: number;
    compressor?: boolean;
  }): void {
    if (settings.volume !== undefined) this.volume = Math.max(0, Math.min(1, settings.volume));
    if (settings.muted !== undefined) this.muted = settings.muted;
    if (settings.bassBoost !== undefined) {
      this.bassBoost = settings.bassBoost;
      this.bassGain.gain.value = settings.bassBoost;
    }
    if (settings.frequency !== undefined) this.bass.frequency.value = settings.frequency;
    if (settings.playbackRate !== undefined) {
      this.playbackRate = settings.playbackRate;
      if (this.player) this.player.playbackRate.value = settings.playbackRate;
    }
    if (settings.attenuator !== undefined) this.attenuator = settings.attenuator;
    if (settings.additionalGainDb !== undefined) this.additionalGainDb = settings.additionalGainDb;
    if (settings.compressor !== undefined) this.setCompressor(settings.compressor);
    this.applyGain();
  }

  private applyGain(): void {
    // Reference attenuator curve (`Audio` module): bass boost is compensated
    // against the extra gain, and zero boost means no attenuation.
    const attenuation = this.attenuator ? attenuationFor(this.bassBoost, this.additionalGainDb) : 1;
    this.gain.gain.value = (this.muted ? 0 : this.volume) * attenuation;
  }

  private setCompressor(enabled: boolean): void {
    if (enabled === this.compressorEnabled) return;
    this.compressorEnabled = enabled;
    // The limiter sits after the master gain, not in the bass branch.
    this.gain.disconnect();
    if (enabled) {
      this.gain.connect(this.compressor);
      this.compressor.connect(this.context.destination);
    } else {
      this.compressor.disconnect();
      this.gain.connect(this.context.destination);
    }
  }

  async decode(file: File): Promise<AudioBuffer> {
    const bytes = await file.arrayBuffer();
    return this.context.decodeAudioData(bytes.slice(0));
  }

  async resume(): Promise<void> {
    if (this.context.state === "suspended") await this.context.resume();
  }

  /**
   * Reference `onAudioChanged`: render the processing graph offline. The
   * rendered buffer is what the analysers see, so bass boost, attenuator,
   * compressor and playback rate change the visuals, not just the speaker
   * output. The graph sums the dry source with a low-passed branch scaled by
   * `bassBoostAmount`, applies the attenuator curve at the master and inserts
   * the limiter last when enabled.
   */
  async process(
    buffer: AudioBuffer,
    settings: {
      bassBoost: number;
      frequency: number;
      playbackRate: number;
      attenuator: boolean;
      additionalGainDb: number;
      compressor: boolean;
    },
  ): Promise<AudioBuffer> {
    const rate = settings.playbackRate > 0 ? settings.playbackRate : 1;
    const Ctor =
      window.OfflineAudioContext ??
      (window as unknown as { webkitOfflineAudioContext: typeof OfflineAudioContext })
        .webkitOfflineAudioContext;
    const context = new Ctor(
      buffer.numberOfChannels,
      Math.max(1, Math.ceil(buffer.length / rate)),
      buffer.sampleRate,
    );

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.playbackRate.value = Math.round(1000 * (rate + Number.EPSILON)) / 1000;

    const bass = context.createBiquadFilter();
    bass.type = "lowpass";
    bass.frequency.value = settings.frequency;
    const bassGain = context.createGain();
    bassGain.gain.value = settings.bassBoost;

    const master = context.createGain();
    master.gain.value = settings.attenuator
      ? attenuationFor(settings.bassBoost, settings.additionalGainDb)
      : 1;

    const limiter = context.createDynamicsCompressor();
    limiter.threshold.value = -4;
    limiter.knee.value = 0;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.001;
    limiter.release.value = 1;

    source.connect(bass);
    bass.connect(bassGain);
    bassGain.connect(master);
    source.connect(master);
    if (settings.compressor) {
      master.connect(limiter);
      limiter.connect(context.destination);
    } else {
      master.connect(context.destination);
    }
    source.start();

    const rendered = await context.startRendering();
    for (let channel = 0; channel < rendered.numberOfChannels; channel += 1) {
      const data = rendered.getChannelData(channel);
      for (let index = 0; index < data.length; index += 1) {
        data[index] = Math.max(-1, Math.min(1, data[index]));
      }
    }
    return rendered;
  }

  /** Plays a decoded buffer from an offset, for preview transport. */
  private player: AudioBufferSourceNode | null = null;

  play(buffer: AudioBuffer | null, offset: number): void {
    if (!buffer) return;
    this.stop();
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.playbackRate.value = this.playbackRate;
    // Reference graph: the dry source goes straight to the master gain, while a
    // parallel low-pass branch is scaled by `bassBoostAmount`.
    source.connect(this.bass);
    source.connect(this.gain);
    source.start(0, Math.max(0, offset));
    this.player = source;
  }

  stop(): void {
    if (!this.player) return;
    try {
      this.player.stop();
    } catch {
      /* already stopped */
    }
    this.player.disconnect();
    this.player = null;
  }
}

const WAVE_LENGTH = 256;

/**
 * Shared analysis buffer. The reference's analyser manager passes
 * `getDataFrame(time, 2 << 16)` to every analyser, so each one selects its own
 * window inside this centred buffer (that is how `audioOffset` and
 * `audioReactionAlignment` shift the analysis in time).
 */
export const ANALYSIS_BUFFER_SAMPLES = 2 << 16;

/**
 * Owns tier selection, band mapping, peak-hold and waveform output.
 *
 * `tick(time, dt)` is time-addressed and never blocks: the threaded tier resolves
 * asynchronously and the most recent magnitudes are kept, so a slow transform
 * degrades frame freshness rather than stalling the renderer.
 */
export class SpectrumAnalyser {
  readonly fftSize = 2048;
  readonly bandCount = 256;
  readonly waveCount = WAVE_LENGTH;

  readonly capabilities: FftCapabilities;
  tier: FftTier;
  readonly reason: string;
  readonly fallbacks: string[] = [];

  private sequential = new SequentialFft();
  private threaded: ThreadedFft | null;
  private simd: SimdFft | null;
  private source: SpectrumSource = new SyntheticSource();

  private samples = new Float32Array(this.fftSize);
  private bins = new Float32Array(this.fftSize / 2);
  private readonly timeWindows = new Map<number, Float32Array>();
  private readonly analysisFrameBuffer = new Float32Array(ANALYSIS_BUFFER_SAMPLES);
  private bands = new Float32Array(this.bandCount);
  private smoothed = new Float32Array(this.bandCount);
  private peaks = new Float32Array(this.bandCount);
  private wave = new Float32Array(WAVE_LENGTH);
  private busy = false;
  private lastMs = 0;

  constructor() {
    this.capabilities = probeCapabilities();
    const decision = selectTier(this.capabilities);
    this.tier = decision.tier;
    this.reason = decision.reason;
    this.threaded = this.tier === "threads" ? new ThreadedFft(2) : null;
    this.simd = this.tier === "wasm-simd" ? new SimdFft() : null;
  }

  setSource(source: SpectrumSource): void {
    this.source = source;
    this.smoothed.fill(0);
    this.peaks.fill(0);
  }

  get sourceLabel(): string {
    return this.source.label;
  }

  /** Rate used for sample/time conversion; the reference follows the audio context. */
  get sampleRate(): number {
    return this.source.sampleRate ?? 48000;
  }

  get lastTransformMs(): number {
    return this.lastMs;
  }

  /** Smoothed band values, 0..1, including peak hold. */
  value(): Float32Array {
    return this.smoothed;
  }

  /** Time-domain window of `length` samples ending at `time`. */
  windowFor(length: number, time: number): Float32Array {
    return this.windowForChannel(length, time, 0);
  }

  /** Stereo variant of {@link windowFor}. */
  windowForChannel(length: number, time: number, channel: number): Float32Array {
    return this.windowStartingAt(length, time - length / this.sampleRate, channel);
  }

  /**
   * Time-domain window of `length` samples centered on `time`, matching the
   * reference's `getDataFrame(t, size)` (start = time - size/2).
   */
  windowCenteredFor(length: number, time: number): Float32Array {
    return this.windowStartingAt(length, time - length / (2 * this.sampleRate));
  }

  /**
   * The reference's shared analysis frame: `2 << 16` samples centred on `time`.
   * Analysers pick their own window inside it, which is what makes
   * `audioOffset` and `audioReactionAlignment` meaningful.
   */
  analysisFrame(time: number): Float32Array {
    const start = time - ANALYSIS_BUFFER_SAMPLES / (2 * this.sampleRate);
    this.source.fill(this.analysisFrameBuffer, start);
    return this.analysisFrameBuffer;
  }

  private windowStartingAt(length: number, startSeconds: number, channel = 0): Float32Array {
    const size = Math.max(128, Math.min(32768, Math.round(length)));
    const key = size * 8 + Math.min(7, Math.max(0, channel));
    let buffer = this.timeWindows.get(key);
    if (!buffer || buffer.length !== size) {
      buffer = new Float32Array(size);
      this.timeWindows.set(key, buffer);
    }
    const start = Math.max(0, startSeconds);
    if (this.source.fillChannel) this.source.fillChannel(buffer, start, channel);
    else this.source.fill(buffer, start);
    return buffer;
  }

  /** Downsampled time-domain window, -1..1. */
  waveform(): Float32Array {
    return this.wave;
  }

  tick(time: number, dt: number): void {
    this.source.fill(this.samples, time);
    this.updateWaveform();

    if (this.busy) return;

    if (this.tier === "sequential") {
      const result = this.sequential.transform(this.samples, this.fftSize);
      this.bins.set(result.magnitudes);
      this.lastMs = result.elapsedMs;
      this.mapBands(dt);
      return;
    }

    if (this.tier === "wasm-simd" && this.simd) {
      try {
        const result = this.simd.transform(this.samples, this.fftSize);
        this.bins.set(result.magnitudes);
        this.lastMs = result.elapsedMs;
        this.mapBands(dt);
      } catch (error) {
        this.degrade("wasm-simd", String(error));
      }
      return;
    }

    if (this.threaded) {
      this.busy = true;
      const input = this.samples.slice();
      this.threaded
        .transform(input, this.fftSize)
        .then((result) => {
          this.bins.set(result.magnitudes);
          this.lastMs = result.elapsedMs;
          this.mapBands(dt);
        })
        .catch((error: unknown) => this.degrade("threads", String(error)))
        .finally(() => {
          this.busy = false;
        });
    }
  }

  /** Wait until any in-flight preview transform has landed. */
  async whenIdle(): Promise<void> {
    while (this.busy) {
      await new Promise((resolve) => setTimeout(resolve, 1));
    }
  }

  /** Clear smoothing/peak history before a deterministic export run. */
  reset(): void {
    this.bins.fill(0);
    this.bands.fill(0);
    this.smoothed.fill(0);
    this.peaks.fill(0);
    this.wave.fill(0);
  }

  /**
   * Deterministic analysis for export: waits for the actual transform instead of
   * keeping the preview's asynchronous "most recent result" behaviour. Without
   * this, fast frame export always rendered stale bands (no audio reaction).
   */
  async tickForExport(time: number, dt: number): Promise<void> {
    this.source.fill(this.samples, time);
    this.updateWaveform();

    if (this.tier === "sequential") {
      const result = this.sequential.transform(this.samples, this.fftSize);
      this.bins.set(result.magnitudes);
      this.lastMs = result.elapsedMs;
      this.mapBands(dt);
      return;
    }

    if (this.tier === "wasm-simd" && this.simd) {
      try {
        const result = this.simd.transform(this.samples, this.fftSize);
        this.bins.set(result.magnitudes);
        this.lastMs = result.elapsedMs;
        this.mapBands(dt);
        return;
      } catch (error) {
        this.degrade("wasm-simd", String(error));
      }
    }

    if (!this.threaded) return;
    while (this.busy) {
      await new Promise((resolve) => setTimeout(resolve, 1));
    }
    this.busy = true;
    try {
      const result = await this.threaded.transform(this.samples.slice(), this.fftSize);
      this.bins.set(result.magnitudes);
      this.lastMs = result.elapsedMs;
      this.mapBands(dt);
    } catch (error) {
      this.degrade("threads", String(error));
      const result = this.sequential.transform(this.samples, this.fftSize);
      this.bins.set(result.magnitudes);
      this.lastMs = result.elapsedMs;
      this.mapBands(dt);
    } finally {
      this.busy = false;
    }
  }

  private degrade(from: FftTier, why: string): void {
    this.fallbacks.push(`${from} -> sequential: ${why}`);
    this.tier = "sequential";
    this.threaded?.dispose();
    this.threaded = null;
    this.simd = null;
    this.busy = false;
  }

  private updateWaveform(): void {
    const step = this.fftSize / WAVE_LENGTH;
    for (let i = 0; i < WAVE_LENGTH; i += 1) {
      this.wave[i] = this.samples[Math.floor(i * step)] ?? 0;
    }
  }

  /** Log-spaced band mapping with attack/release smoothing and peak hold. */
  private mapBands(dt: number): void {
    const half = this.fftSize / 2;
    const minBin = 1;
    const maxBin = half - 1;
    const ratio = Math.log(maxBin / minBin) / (this.bandCount - 1);
    const safeDt = Math.min(0.2, Math.max(0.001, dt));
    const release = Math.pow(0.02, safeDt);
    const peakDecay = Math.pow(0.35, safeDt);

    for (let band = 0; band < this.bandCount; band += 1) {
      const start = Math.floor(minBin * Math.exp(ratio * band));
      const end = Math.max(start + 1, Math.floor(minBin * Math.exp(ratio * (band + 1))));
      let peak = 0;
      for (let bin = start; bin < Math.min(end, half); bin += 1) {
        if (this.bins[bin] > peak) peak = this.bins[bin];
      }

      // Perceptual curve: keeps quiet content visible without flattening peaks.
      const scaled = Math.min(1, Math.pow(peak, 0.55) * 1.8);
      const attack = 0.72;
      const previous = this.bands[band];
      this.bands[band] = previous + (scaled - previous) * (scaled > previous ? attack : 1 - release);

      const held = Math.max(this.bands[band], this.peaks[band] * peakDecay);
      this.peaks[band] = held;
      this.smoothed[band] = held;
    }
  }
}
