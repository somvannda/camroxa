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

import type { ParamDef } from "@/lib/studio-plugins";

export type MasterChainEntry = {
  id?: string;
  type?: string;
  /** 0..1 amounts, interpreted per plugin kind. */
  amount?: number;
  enabled?: boolean;
  /** Limiter controls (S48): lookahead ms, pre-gain dB, attack/release ms, link 0/1. */
  params?: Record<string, number>;
};

export const LIMITER_DEFAULTS = {
  lookahead: 3,
  preGain: 0,
  attack: 1,
  release: 60,
  link: 1,
};

/** Controls captured on the master Limiter card (S48). */
export const LIMITER_PARAMS: ParamDef[] = [
  { key: "lookahead", label: "Lookahead", min: 0, max: 20, default: 3, unit: "ms", tier: "primary" },
  { key: "preGain", label: "Pre Gain", min: -12, max: 24, default: 0, unit: "db", tier: "primary" },
  { key: "attack", label: "Attack", min: 0, max: 50, default: 1, unit: "ms", tier: "primary" },
  { key: "release", label: "Release", min: 5, max: 500, default: 60, unit: "ms", tier: "primary" },
  { key: "link", label: "Link", min: 0, max: 1, default: 1, tier: "primary" },
];

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
      if (isLimiter) {
        const params = entry.params ?? {};
        const preGain = Math.pow(10, (params.preGain ?? 0) / 20);
        const lookahead = Math.min(0.05, Math.max(0, (params.lookahead ?? 3) / 1000));
        const pre = context.createGain();
        pre.gain.value = preGain;
        const delay = context.createDelay(0.06);
        delay.delayTime.value = lookahead;
        comp.attack.value = Math.min(0.05, Math.max(0, (params.attack ?? 1) / 1000));
        comp.release.value = Math.min(0.5, Math.max(0.005, (params.release ?? 60) / 1000));
        // WebAudio compresses both channels together, which is the linked behaviour.
        cursor.connect(pre).connect(delay).connect(comp);
        cursor = comp;
      } else {
        comp.attack.value = 0.003;
        comp.release.value = 0.25;
        cursor.connect(comp);
        cursor = comp;
      }
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
