/**
 * FFT ladder.
 *
 * The reference application ships three FFT variants (SIMD+threads, threads,
 * sequential) and picks one at runtime from a feature probe, so browsers that
 * cannot do threads still render spectra. This module reproduces that *shape*
 * of decision with its own implementation:
 *
 *   tier 0  wasm-simd  — only if a SIMD kernel has been registered
 *   tier 1  threads    — decimation-in-time split across workers (needs SAB)
 *   tier 2  sequential — plain radix-2 on the calling thread
 *
 * Tiers 1 and 2 are implemented here and fully functional. Tier 0 is a slot:
 * `registerSimdFft` accepts a compiled kernel so a real WASM implementation can
 * be dropped in without touching call sites.
 */

export type FftTier = "wasm-simd" | "threads" | "sequential";

export interface FftCapabilities {
  wasmSimd: boolean;
  wasmThreads: boolean;
  hardwareConcurrency: number;
  simdModuleRegistered: boolean;
  crossOriginIsolated: boolean;
}

export interface FftResult {
  /** Magnitudes normalised to 0..1, length = fftSize / 2. */
  magnitudes: Float32Array;
  tier: FftTier;
  elapsedMs: number;
}

export type SimdFftKernel = (real: Float32Array, imag: Float32Array) => void;

let simdKernel: SimdFftKernel | null = null;

/** Supply a compiled WASM kernel to activate tier 0. */
export function registerSimdFft(kernel: SimdFftKernel): void {
  simdKernel = kernel;
}

/* ------------------------------------------------------------------ */
/* Capability probe                                                    */
/* ------------------------------------------------------------------ */

export function probeCapabilities(): FftCapabilities {
  // Minimal module that exercises i8x16.splat and v128 stores.
  const simdProbe = new Uint8Array([
    0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 10, 9, 1, 7, 0, 65, 0, 253, 15, 26, 11,
  ]);

  let wasmSimd = false;
  try {
    wasmSimd = WebAssembly.validate(simdProbe);
  } catch {
    wasmSimd = false;
  }

  const crossOriginIsolated =
    typeof globalThis.crossOriginIsolated === "boolean" ? globalThis.crossOriginIsolated : false;
  const hasSab = typeof SharedArrayBuffer !== "undefined";
  const hasWorkers = typeof Worker !== "undefined";
  const cores = navigator.hardwareConcurrency ?? 1;

  return {
    wasmSimd,
    wasmThreads: crossOriginIsolated && hasSab && hasWorkers && cores >= 2,
    hardwareConcurrency: cores,
    simdModuleRegistered: simdKernel !== null,
    crossOriginIsolated,
  };
}

export function selectTier(caps: FftCapabilities): { tier: FftTier; reason: string } {
  if (caps.wasmSimd && caps.simdModuleRegistered) {
    return { tier: "wasm-simd", reason: "SIMD probe passed and a kernel is registered" };
  }
  if (caps.wasmThreads) {
    return {
      tier: "threads",
      reason: caps.wasmSimd
        ? "SIMD available but no kernel registered; using threaded tier"
        : "SharedArrayBuffer and workers available",
    };
  }
  if (!caps.crossOriginIsolated) {
    return { tier: "sequential", reason: "not cross-origin isolated, SharedArrayBuffer unavailable" };
  }
  if (caps.hardwareConcurrency < 2) {
    return { tier: "sequential", reason: "single core" };
  }
  return { tier: "sequential", reason: "threaded tier unavailable" };
}

/* ------------------------------------------------------------------ */
/* Radix-2 FFT                                                         */
/* ------------------------------------------------------------------ */

/** Iterative Cooley-Tukey, in place. Length must be a power of two. */
export function fftInPlace(real: Float32Array, imag: Float32Array): void {
  const n = real.length;
  if (n <= 1) return;
  if ((n & (n - 1)) !== 0) throw new Error(`FFT size must be a power of two, got ${n}`);

  for (let i = 1, j = 0; i < n; i += 1) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      const tr = real[i];
      real[i] = real[j];
      real[j] = tr;
      const ti = imag[i];
      imag[i] = imag[j];
      imag[j] = ti;
    }
  }

  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len;
    const wRe = Math.cos(ang);
    const wIm = Math.sin(ang);
    const half = len >> 1;
    for (let i = 0; i < n; i += len) {
      let curRe = 1;
      let curIm = 0;
      for (let k = 0; k < half; k += 1) {
        const aRe = real[i + k];
        const aIm = imag[i + k];
        const bRe = real[i + k + half] * curRe - imag[i + k + half] * curIm;
        const bIm = real[i + k + half] * curIm + imag[i + k + half] * curRe;

        real[i + k] = aRe + bRe;
        imag[i + k] = aIm + bIm;
        real[i + k + half] = aRe - bRe;
        imag[i + k + half] = aIm - bIm;

        const nextRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = nextRe;
      }
    }
  }
}

interface BluesteinPlan {
  m: number;
  chirpRe: Float64Array;
  chirpIm: Float64Array;
  /** FFT of the chirp kernel; read-only once built. */
  bRe: Float64Array;
  bIm: Float64Array;
  /** Working transform buffer. */
  aRe: Float64Array;
  aIm: Float64Array;
  scratchRe: Float32Array;
  scratchIm: Float32Array;
}

/** Chirp plans are pure functions of the length; keep the hot path allocation-free. */
const BLUESTEIN_PLANS = new Map<number, BluesteinPlan>();
const BLUESTEIN_PLAN_LIMIT = 8;

function bluesteinPlan(n: number): BluesteinPlan {
  const cached = BLUESTEIN_PLANS.get(n);
  if (cached) return cached;
  // Bluestein: X[k] = w[k] * sum_n (x[n] * w[n]) * conj(w[k-n]) with
  // w[j] = exp(-i*pi*j^2/n), evaluated as a cyclic convolution of size m.
  let m = 1;
  while (m < 2 * n - 1) m <<= 1;
  const chirpRe = new Float64Array(n);
  const chirpIm = new Float64Array(n);
  for (let k = 0; k < n; k += 1) {
    // Reduce k^2 modulo 2n so the angle stays accurate for large k.
    const j = (k * k) % (2 * n);
    const angle = (Math.PI * j) / n;
    chirpRe[k] = Math.cos(angle);
    chirpIm[k] = -Math.sin(angle);
  }
  const plan: BluesteinPlan = {
    m,
    chirpRe,
    chirpIm,
    bRe: new Float64Array(m),
    bIm: new Float64Array(m),
    aRe: new Float64Array(m),
    aIm: new Float64Array(m),
    scratchRe: new Float32Array(m),
    scratchIm: new Float32Array(m),
  };
  plan.bRe[0] = chirpRe[0];
  plan.bIm[0] = -chirpIm[0];
  for (let k = 1; k < n; k += 1) {
    plan.bRe[k] = chirpRe[k];
    plan.bIm[k] = -chirpIm[k];
    plan.bRe[m - k] = chirpRe[k];
    plan.bIm[m - k] = -chirpIm[k];
  }
  if (BLUESTEIN_PLANS.size >= BLUESTEIN_PLAN_LIMIT) {
    const oldest = BLUESTEIN_PLANS.keys().next().value;
    if (oldest !== undefined) BLUESTEIN_PLANS.delete(oldest);
  }
  // The kernel's transform is input-independent: keep the transformed chirp.
  for (let i = 0; i < m; i += 1) {
    plan.scratchRe[i] = plan.bRe[i];
    plan.scratchIm[i] = plan.bIm[i];
  }
  fftInPlace(plan.scratchRe, plan.scratchIm);
  for (let i = 0; i < m; i += 1) {
    plan.bRe[i] = plan.scratchRe[i];
    plan.bIm[i] = plan.scratchIm[i];
  }
  BLUESTEIN_PLANS.set(n, plan);
  return plan;
}

/**
 * In-place DFT for any length. Powers of two use the radix-2 transform; other
 * sizes use Bluestein's chirp-z algorithm, because the reference analyser
 * accepts mixed-radix sizes (real analysis windows such as 4800 samples are not
 * powers of two).
 */
export function dftInPlace(real: Float32Array, imag: Float32Array): void {
  const n = real.length;
  if (n <= 1) return;
  if ((n & (n - 1)) === 0) {
    fftInPlace(real, imag);
    return;
  }

  const plan = bluesteinPlan(n);
  const { m, chirpRe, chirpIm, bRe, bIm, aRe, aIm, scratchRe, scratchIm } = plan;
  aRe.fill(0);
  aIm.fill(0);
  for (let k = 0; k < n; k += 1) {
    aRe[k] = real[k] * chirpRe[k] - imag[k] * chirpIm[k];
    aIm[k] = real[k] * chirpIm[k] + imag[k] * chirpRe[k];
  }

  const run = (re: Float64Array, im: Float64Array, inverse: boolean): void => {
    for (let i = 0; i < m; i += 1) {
      scratchRe[i] = re[i];
      scratchIm[i] = inverse ? -im[i] : im[i];
    }
    fftInPlace(scratchRe, scratchIm);
    for (let i = 0; i < m; i += 1) {
      re[i] = scratchRe[i];
      im[i] = inverse ? -scratchIm[i] : scratchIm[i];
    }
  };

  run(aRe, aIm, false);
  for (let i = 0; i < m; i += 1) {
    const re = aRe[i] * bRe[i] - aIm[i] * bIm[i];
    const im = aRe[i] * bIm[i] + aIm[i] * bRe[i];
    aRe[i] = re;
    aIm[i] = im;
  }
  run(aRe, aIm, true);
  const scale = 1 / m;
  for (let k = 0; k < n; k += 1) {
    const re = aRe[k] * scale;
    const im = aIm[k] * scale;
    real[k] = re * chirpRe[k] - im * chirpIm[k];
    imag[k] = re * chirpIm[k] + im * chirpRe[k];
  }
}

export function magnitudesOf(real: Float32Array, imag: Float32Array, out: Float32Array): void {
  const n = real.length;
  const half = n >> 1;
  const norm = 2 / n;
  for (let i = 0; i < half; i += 1) {
    out[i] = Math.sqrt(real[i] * real[i] + imag[i] * imag[i]) * norm;
  }
}

/* ------------------------------------------------------------------ */
/* Tier: sequential                                                    */
/* ------------------------------------------------------------------ */

export class SequentialFft {
  readonly tier: FftTier = "sequential";

  transform(samples: Float32Array, fftSize: number): FftResult {
    const started = performance.now();
    const n = fftSize;
    const real = new Float32Array(n);
    const imag = new Float32Array(n);
    const count = Math.min(samples.length, n);
    for (let i = 0; i < count; i += 1) {
      real[i] = samples[i] * (0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1))));
    }

    fftInPlace(real, imag);

    const magnitudes = new Float32Array(n >> 1);
    magnitudesOf(real, imag, magnitudes);
    return { magnitudes, tier: this.tier, elapsedMs: performance.now() - started };
  }
}

/* ------------------------------------------------------------------ */
/* Tier: threads                                                       */
/* ------------------------------------------------------------------ */

/**
 * Decimation in time across workers:
 *
 *   even = FFT(x[0], x[2], x[4], ...)
 *   odd  = FFT(x[1], x[3], x[5], ...)
 *   X[k]            = even[k] + W^k * odd[k]
 *   X[k + N/2]      = even[k] - W^k * odd[k]
 *
 * Each half is transformed in its own worker over a SharedArrayBuffer, then the
 * main thread does the O(N) combine.
 */
export class ThreadedFft {
  readonly tier: FftTier = "threads";
  private workers: Worker[] = [];
  private ready: Promise<void> | null = null;

  constructor(private readonly workerCount = 2) {}

  private init(): Promise<void> {
    if (this.ready) return this.ready;
    this.ready = (async () => {
      for (let i = 0; i < this.workerCount; i += 1) {
        this.workers.push(new Worker(new URL("./fftWorker.ts", import.meta.url), { type: "module" }));
      }
    })();
    return this.ready;
  }

  private runWorker(worker: Worker, signal: SharedArrayBuffer, n: number, slot: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        worker.removeEventListener("message", onMessage);
        worker.removeEventListener("error", onError);
      };
      const onMessage = (event: MessageEvent) => {
        if (event.data?.slot !== slot) return;
        cleanup();
        resolve();
      };
      const onError = (event: ErrorEvent) => {
        cleanup();
        reject(new Error(event.message || "fft worker failed"));
      };
      worker.addEventListener("message", onMessage);
      worker.addEventListener("error", onError);
      worker.postMessage({ signal, n, slot, ready: new SharedArrayBuffer(4) });
    });
  }

  async transform(samples: Float32Array, fftSize: number): Promise<FftResult> {
    const started = performance.now();
    await this.init();

    const n = fftSize;
    const half = n >> 1;
    const halves: SharedArrayBuffer[] = [];

    for (let parity = 0; parity < 2; parity += 1) {
      const shared = new SharedArrayBuffer(half * 2 * 4);
      const re = new Float32Array(shared, 0, half);
      const im = new Float32Array(shared, half * 4, half);
      for (let i = 0; i < half; i += 1) {
        const src = 2 * i + parity;
        const window = 0.5 * (1 - Math.cos((2 * Math.PI * src) / (n - 1)));
        re[i] = (samples[src] ?? 0) * window;
        im[i] = 0;
      }
      const worker = this.workers[parity % this.workers.length];
      await this.runWorker(worker, shared, half, parity);
      halves.push(shared);
    }

    const eRe = new Float32Array(halves[0], 0, half);
    const eIm = new Float32Array(halves[0], half * 4, half);
    const oRe = new Float32Array(halves[1], 0, half);
    const oIm = new Float32Array(halves[1], half * 4, half);

    const outRe = new Float32Array(n);
    const outIm = new Float32Array(n);
    for (let k = 0; k < half; k += 1) {
      const ang = (-2 * Math.PI * k) / n;
      const wRe = Math.cos(ang);
      const wIm = Math.sin(ang);
      const tRe = oRe[k] * wRe - oIm[k] * wIm;
      const tIm = oRe[k] * wIm + oIm[k] * wRe;
      outRe[k] = eRe[k] + tRe;
      outIm[k] = eIm[k] + tIm;
      outRe[k + half] = eRe[k] - tRe;
      outIm[k + half] = eIm[k] - tIm;
    }

    const magnitudes = new Float32Array(half);
    magnitudesOf(outRe, outIm, magnitudes);
    return { magnitudes, tier: this.tier, elapsedMs: performance.now() - started };
  }

  dispose(): void {
    for (const worker of this.workers) worker.terminate();
    this.workers = [];
    this.ready = null;
  }
}

/* ------------------------------------------------------------------ */
/* Tier: wasm-simd                                                     */
/* ------------------------------------------------------------------ */

export class SimdFft {
  readonly tier: FftTier = "wasm-simd";

  transform(samples: Float32Array, fftSize: number): FftResult {
    if (!simdKernel) throw new Error("no SIMD FFT kernel registered");
    const started = performance.now();
    const n = fftSize;
    const real = new Float32Array(n);
    const imag = new Float32Array(n);
    const count = Math.min(samples.length, n);
    for (let i = 0; i < count; i += 1) {
      real[i] = samples[i] * (0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1))));
    }
    simdKernel(real, imag);
    const magnitudes = new Float32Array(n >> 1);
    magnitudesOf(real, imag, magnitudes);
    return { magnitudes, tier: this.tier, elapsedMs: performance.now() - started };
  }
}
