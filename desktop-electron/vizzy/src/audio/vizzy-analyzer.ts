/**
 * Reference analyser (WebAssembly).
 *
 * The reference computes band values inside `FFT.wasm`; its Emscripten glue was
 * extracted from the captured bundle (webpack module 455) and is served from
 * `public/vendor/vizzy/`. This wraps the call sequence that glue expects:
 *
 *   analyser_init → resize_input → set_* → make_*_lookup → analyse
 *
 * Values come back in the reference's own units (roughly 0…200 for the Trap
 * Motion preset), not normalised to 0…1.
 */

export interface VizzyAnalyserSettings {
  /** Audio-context sample rate used for the window/offset conversion. */
  sampleRate?: number;
  /** Analysis window in samples (audioDuration ms → samples). */
  sampleInCount: number;
  /** Bands returned per frame. */
  sampleOutCount: number;
  minHz: number;
  maxHz: number;
  /** Index into the reference's window-function enum (gaussian = 7). */
  windowIndex: number;
  /** Index into the reference's provider enum (filter bank = 0, goertzel = 1). */
  providerIndex: number;
  outputMultiplier: number;
  /** Window lead, in the reference's units (its `audioOffset`). */
  audioOffset: number;
  /** Reference analyser settings; omitted values keep the historical defaults. */
  smoothingTimeConstant?: number;
  audioReactionAlignment?: number;
  windowParameter?: number;
  windowSkew?: number;
  frequencyScaleIndex?: number;
  hzLinearFactor?: number;
  cqtResolution?: number;
  cqtBandwidth?: number;
  cqtWindowIndex?: number;
  cqtWindowParameter?: number;
  cqtWindowSkew?: number;
  spectrumConstantQ?: boolean;
  downSample?: number;
  perBandWeightingIndex?: number;
  perBandWeightingAmount?: number;
  perBandFrequencyTilt?: number;
}

const GLUE_URL = "/vendor/vizzy/analyser-glue.js";

let factoryPromise: Promise<((options: unknown) => Promise<unknown>) | null> | null = null;

/** Start downloading the reference glue/wasm before the first frame needs it. */
export function preloadVizzyAnalyser(): void {
  void loadFactory();
}

function loadFactory(): Promise<((options: unknown) => Promise<unknown>) | null> {
  if (!factoryPromise) {
    factoryPromise = (async () => {
      const scope = globalThis as { __vizzyAnalyserFactory?: unknown };
      if (typeof scope.__vizzyAnalyserFactory !== "function") {
        // A classic script, not an ES module: Vite serves public files with an
        // `?import` probe that fails for them.
        await new Promise<void>((resolve, reject) => {
          const script = document.createElement("script");
          script.src = GLUE_URL;
          script.onload = () => resolve();
          script.onerror = () => reject(new Error(`failed to load ${GLUE_URL}`));
          document.head.append(script);
        });
      }
      const factory = scope.__vizzyAnalyserFactory;
      return typeof factory === "function"
        ? (factory as (options: unknown) => Promise<unknown>)
        : null;
    })().catch((error) => {
      console.warn("[vizzy] glue import failed:", error);
      return null;
    });
  }
  return factoryPromise;
}

interface AnalyserModule {
  HEAPF32: Float32Array;
  HEAP32: Int32Array;
  HEAPU8: Uint8Array;
  _set_allowed_fft_sizes(): void;
  _analyser_init(sampleInCount: number): number;
  _analyser_close(ctx: number): void;
  _resize_input(
    ctx: number,
    provider: number,
    sampleInCount: number,
    downSample: number,
    sampleRate: number,
    epsilon: number,
  ): void;
  _set_sample_out_count(ctx: number, count: number): void;
  _set_output_multipler(ctx: number, multiplier: number): void;
  _make_window_lookup(ctx: number, parameter: number, skew: number, index: number): void;
  _make_freq_bands_lookup(
    ctx: number,
    minHz: number,
    maxHz: number,
    scale: number,
    linearFactor: number,
  ): void;
  _make_freq_tilt_lookup(ctx: number, tilt: number): void;
  _make_band_weight_lookup(ctx: number, type: number, amount: number): void;
  _make_combined_lookup(ctx: number): void;
  _make_cqt_lookup(
    ctx: number,
    resolution: number,
    spectrumConstantQ: number,
    bandwidth: number,
    windowIndex: number,
    parameter: number,
    skew: number,
  ): void;
  _set_smoothing_time_constant(ctx: number, value: number): void;
  _set_audio_offset(ctx: number, value: number): void;
  _set_audio_reaction_alignment(ctx: number, value: number): void;
  _set_sample_in_count(ctx: number, value: number): void;
  _analyse(ctx: number, ptr: number, sampleInCount: number, sampleRate: number): number;
  /** Reference manager batch: analyse every context against one shared frame. */
  _analyse_multiple(
    contexts: number,
    count: number,
    ptr: number,
    length: number,
    rerender: number,
  ): number;
  /** Output pointer of a context's band values. */
  _get_result(ctx: number): number;
  _init_pool(): void;
  /** Reference `_analyser_reset`: clears a context's smoothing history. */
  _analyser_reset(ctx: number): void;
  _malloc(bytes: number): number;
  _free(ptr: number): void;
}

export class VizzyAnalyser {
  private scratchPtr = 0;
  private scratchLength = 0;

  private constructor(
    private readonly module: AnalyserModule,
    private readonly ctx: number,
    private readonly sampleInCount: number,
    private readonly sampleOutCount: number,
    private readonly sampleRate: number,
  ) {}

  static async create(settings: VizzyAnalyserSettings): Promise<VizzyAnalyser | null> {
    // Standalone convenience for tests and scripts: one module, one context.
    // The renderer uses {@link AnalyserManager}, like the reference manager.
    const factory = await loadFactory();
    if (!factory) return null;
    try {
      const module = (await factory({
        locateFile: (file: string) => `/vendor/vizzy/${file}`,
      })) as AnalyserModule;
      module._set_allowed_fft_sizes();
      const init = initAnalyserContext(module, settings);
      if (!init) return null;
      return new VizzyAnalyser(module, init.ctx, init.sampleInCount, settings.sampleOutCount, init.sampleRate);
    } catch (error) {
      console.warn("[vizzy] analyser init failed:", error);
      return null;
    }
  }

  close(): void {
    try {
      if (this.scratchPtr !== 0) this.module._free(this.scratchPtr);
      this.scratchPtr = 0;
      this.scratchLength = 0;
      this.module._analyser_close?.(this.ctx);
    } catch {
      /* the wasm context may already be gone */
    }
  }

  get windowSamples(): number {
    return this.sampleInCount;
  }

  /** Band values in the reference's units. */
  analyse(buffer: Float32Array, sampleRate = this.sampleRate): Float32Array {
    // The reference manager hands every analyser the same centred buffer
    // (`getDataFrame(time, 2 << 16)`) and passes its length to `_analyse`; the
    // module then selects the analyser's own window inside it.
    const length = Math.max(1, buffer.length);
    if (this.scratchLength < length) {
      if (this.scratchPtr !== 0) this.module._free(this.scratchPtr);
      this.scratchPtr = this.module._malloc(4 * length);
      this.scratchLength = length;
    }
    this.module.HEAPF32.set(buffer, this.scratchPtr >> 2);
    const resultPtr = this.module._analyse(this.ctx, this.scratchPtr, length, sampleRate);
    return new Float32Array(this.module.HEAPU8.buffer, resultPtr, this.sampleOutCount).slice();
  }
}

/**
 * The reference's analyser manager init sequence (module 308's
 * `AudioAnalyzer.init`). Shared by the standalone analyser and the manager so
 * both run the exact same order of `_make_*` calls.
 */
function initAnalyserContext(
  module: AnalyserModule,
  settings: VizzyAnalyserSettings,
): { ctx: number; sampleInCount: number; sampleRate: number } | null {
  // The reference rounds the analysis window up to a multiple of four samples
  // and clamps it to the module's transform range.
  const raw = Math.max(1, Math.round(settings.sampleInCount));
  const n = Math.max(128, Math.min(32768, raw + (raw % 4)));
  const sampleRate = settings.sampleRate ?? 48000;
  const provider = settings.providerIndex;
  const downSample = settings.downSample ?? 0;
  const minHz = Math.max(2, Math.min(settings.minHz, settings.maxHz));
  const maxHz = Math.max(minHz, Math.min(settings.maxHz, 20000));
  const tilt = settings.perBandFrequencyTilt ?? 0;
  const weighting = settings.perBandWeightingIndex ?? 0;
  const weightingAmount = settings.perBandWeightingAmount ?? 0;
  const ctx = module._analyser_init(n);
  const cqt = (): void =>
    module._make_cqt_lookup(
      ctx,
      settings.cqtResolution ?? 7,
      // The reference passes the inverse of `spectrumConstantQ`.
      settings.spectrumConstantQ ? 0 : 1,
      settings.cqtBandwidth ?? 8,
      settings.cqtWindowIndex ?? 5,
      settings.cqtWindowParameter ?? 1,
      settings.cqtWindowSkew ?? 0,
    );
  const windowLookup = (): void =>
    module._make_window_lookup(
      ctx,
      settings.windowParameter ?? 1,
      settings.windowSkew ?? 0,
      settings.windowIndex,
    );
  // The reference's init order matters: `_make_combined_lookup` bakes the
  // band-weight table into the per-bin gain table, and skipping the weight
  // lookup leaves that table corrupt at the top of the frequency range
  // (a 0.5 sine at 100 Hz read ~50,000 instead of ~84).
  module._resize_input(ctx, provider, n, downSample, sampleRate, 0.1);
  windowLookup();
  module._set_sample_out_count(ctx, settings.sampleOutCount);
  module._make_freq_bands_lookup(
    ctx,
    minHz,
    maxHz,
    settings.frequencyScaleIndex ?? 0,
    settings.hzLinearFactor ?? 0.5,
  );
  module._make_band_weight_lookup(ctx, weighting, weightingAmount);
  module._make_freq_tilt_lookup(ctx, tilt);
  module._make_combined_lookup(ctx);
  cqt();
  if (settings.outputMultiplier > 0) {
    module._set_output_multipler(ctx, settings.outputMultiplier);
  }
  windowLookup();
  module._make_freq_tilt_lookup(ctx, tilt);
  module._make_combined_lookup(ctx);
  cqt();
  module._make_band_weight_lookup(ctx, weighting, weightingAmount);
  module._make_combined_lookup(ctx);
  module._set_smoothing_time_constant(ctx, settings.smoothingTimeConstant ?? 0);
  module._set_audio_reaction_alignment(ctx, settings.audioReactionAlignment ?? -1);
  // The reference stores the offset in samples, with the opposite sign.
  const offset = settings.audioOffset;
  if (offset > -1000 && offset < 1000) {
    module._set_audio_offset(ctx, Math.round((-offset / 1000) * sampleRate));
  }
  module._set_sample_in_count(ctx, n);
  module._resize_input(ctx, provider, n, downSample, sampleRate, 0.1);
  windowLookup();
  module._set_smoothing_time_constant(ctx, settings.smoothingTimeConstant ?? 0);
  return { ctx, sampleInCount: n, sampleRate };
}

export interface AnalyserHandle {
  readonly ctx: number;
  readonly sampleInCount: number;
  readonly sampleRate: number;
}

/**
 * Reference analyser manager (`AudioAnalyzerManager`): one wasm module, one
 * context per analyzer, and `_analyse_multiple` over the shared frame. The
 * renderer uses this instead of one module per analyzer, matching the bundled
 * app and uploading the 131 072-sample frame once per frame.
 */
export class AnalyserManager {
  private readonly contexts = new Set<number>();
  private ctxPtr = 0;
  private ctxCapacity = 0;
  private framePtr = 0;
  private frameCapacity = 0;

  private constructor(private readonly module: AnalyserModule) {}

  static async create(): Promise<AnalyserManager | null> {
    const factory = await loadFactory();
    if (!factory) return null;
    try {
      const module = (await factory({
        locateFile: (file: string) => `/vendor/vizzy/${file}`,
      })) as AnalyserModule;
      module._set_allowed_fft_sizes();
      module._init_pool();
      return new AnalyserManager(module);
    } catch (error) {
      console.warn("[vizzy] analyser manager failed:", error);
      return null;
    }
  }

  open(settings: VizzyAnalyserSettings): AnalyserHandle | null {
    try {
      const init = initAnalyserContext(this.module, settings);
      if (!init) return null;
      this.contexts.add(init.ctx);
      return init;
    } catch (error) {
      console.warn("[vizzy] analyser context failed:", error);
      return null;
    }
  }

  /** Upload one shared frame and return its wasm pointer. */
  private uploadFrame(frame: Float32Array): number {
    const length = Math.max(1, frame.length);
    if (this.frameCapacity < length) {
      if (this.framePtr !== 0) this.module._free(this.framePtr);
      this.framePtr = this.module._malloc(4 * length);
      this.frameCapacity = length;
    }
    this.module.HEAPF32.set(frame, this.framePtr >> 2);
    return length;
  }

  /** One upload and one call for every open context (`_analyse_multiple`). */
  analyse(frame: Float32Array, sampleRate: number): void {
    const count = this.contexts.size;
    if (count === 0) return;
    void sampleRate;
    if (this.ctxCapacity < count) {
      if (this.ctxPtr !== 0) this.module._free(this.ctxPtr);
      this.ctxPtr = this.module._malloc(4 * count);
      this.ctxCapacity = count;
    }
    const length = this.uploadFrame(frame);
    const words = this.ctxPtr >> 2;
    let index = 0;
    for (const ctx of this.contexts) {
      this.module.HEAP32[words + index] = ctx;
      index += 1;
    }
    this.module._analyse_multiple(this.ctxPtr, count, this.framePtr, length, 1);
  }

  /**
   * The same analysis for a single context (`_analyse`). The reference's audio
   * impact scan only needs one analyser; running `_analyse_multiple` charged it
   * for every open context (13 in a template), which is where the multi-second
   * first-load stall came from.
   */
  analyseOne(handle: AnalyserHandle, frame: Float32Array, sampleRate: number): void {
    const length = this.uploadFrame(frame);
    this.module._analyse(handle.ctx, this.framePtr, length, sampleRate);
  }

  /** Band values in the reference's units (`_get_result`). */
  result(handle: AnalyserHandle, sampleOutCount: number): Float32Array {
    const ptr = this.module._get_result(handle.ctx);
    return new Float32Array(this.module.HEAPU8.buffer, ptr, sampleOutCount).slice();
  }

  /** Reference `resetAnalysers`: forget every context's smoothing history. */
  reset(): void {
    for (const ctx of this.contexts) {
      try {
        this.module._analyser_reset?.(ctx);
      } catch {
        /* context already gone */
      }
    }
  }

  close(handle: AnalyserHandle): void {
    try {
      this.module._analyser_close?.(handle.ctx);
    } catch {
      /* already gone */
    }
    this.contexts.delete(handle.ctx);
  }
}
