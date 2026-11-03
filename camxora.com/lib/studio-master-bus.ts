/**
 * Master bus (roadmap W4.1).
 *
 * The reference chain is captured in spec §91: the master is a chain target like any
 * track, and it ships with a Limiter. Ours previously went straight from track gains
 * into `destination` with a single hard-coded gain, so nothing on the master was
 * audible.
 *
 * This builds a real node graph:
 *
 *   input -> [ eq -> compressor -> drive ] -> output
 *
 * Only the plugin kinds we can render faithfully with WebAudio are supported here;
 * anything else is skipped rather than approximated.
 */

export type MasterChainEntry = {
  id?: string;
  type?: string;
  /** 0..1 amounts, interpreted per plugin kind. */
  amount?: number;
  enabled?: boolean;
};

const MAX_DRIVE = 4;

export type MasterBus = {
  input: AudioNode;
  output: AudioNode;
  /** How many chain links were actually built (for display and tests). */
  built: number;
};

function makeDriveCurve(amount: number): Float32Array<ArrayBuffer> {
  const samples = 1024;
  const curve = new Float32Array(new ArrayBuffer(samples * 4));
  const k = Math.max(1, amount * MAX_DRIVE);
  for (let i = 0; i < samples; i++) {
    const x = (i * 2) / samples - 1;
    // tanh soft-clip, the shape the reference's Drive control implies.
    curve[i] = Math.tanh(k * x) / Math.tanh(k);
  }
  return curve;
}

/**
 * Build the master chain into a context. Returns the input and output nodes so the
 * caller can wire sources in and `destination` out.
 */
export function buildMasterBus(
  context: BaseAudioContext,
  chain: MasterChainEntry[] = []
): MasterBus {
  const input = context.createGain();
  let cursor: AudioNode = input;
  let built = 0;

  for (const entry of chain) {
    if (entry.enabled === false) continue;
    const kind = (entry.type ?? "").toLowerCase();
    const amount = typeof entry.amount === "number" ? Math.min(1, Math.max(0, entry.amount)) : 0.5;

    if (kind.includes("eq")) {
      const filter = context.createBiquadFilter();
      filter.type = "peaking";
      filter.frequency.value = 1200;
      filter.Q.value = 0.9;
      filter.gain.value = (amount - 0.5) * 24; // ±12 dB around the midpoint
      cursor.connect(filter);
      cursor = filter;
      built += 1;
    } else if (kind.includes("compress") || kind.includes("limit")) {
      const comp = context.createDynamicsCompressor();
      const isLimiter = kind.includes("limit");
      // A limiter needs a hard knee: with the default 30 dB knee the curve is so soft
      // that peaks pass through almost untouched (measured 1.4 -> 1.36 before this).
      comp.knee.value = isLimiter ? 0 : 24;
      comp.threshold.value = isLimiter ? -1 : -24 + amount * 12;
      comp.ratio.value = isLimiter ? 20 : 2 + amount * 6;
      comp.attack.value = isLimiter ? 0.001 : 0.003;
      comp.release.value = 0.25;
      cursor.connect(comp);
      cursor = comp;
      built += 1;
    } else if (kind.includes("drive") || kind.includes("distort")) {
      const shaper = context.createWaveShaper();
      shaper.curve = makeDriveCurve(amount);
      shaper.oversample = "2x";
      cursor.connect(shaper);
      cursor = shaper;
      built += 1;
    }
  }

  const output = context.createGain();
  cursor.connect(output);
  return { input, output, built };
}

// Dev-only handle so the bus can be measured with an OfflineAudioContext without
// reaching into React. Never exposed in a production build.
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
  (window as unknown as { __buildMasterBus?: typeof buildMasterBus }).__buildMasterBus =
    buildMasterBus;
}
