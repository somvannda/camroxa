/**
 * Studio built-in plugin registry.
 *
 * Grounded in the reference catalog captured in
 * `docs/studio/SUNO_STUDIO_IMPLEMENTATION_SPEC.md` §48/§50:
 * effect ids, parameter names, knob tiers and mode tabs.
 *
 * This module is data only — no audio wiring. The engine reads it to build
 * parameter UI and to validate persisted chain entries, so the catalog and the
 * stored chain cannot drift apart.
 *
 * Sources: reference catalog cards (§48), plugin dock panels (§50), and the
 * decompiled registry ids (§51). `chorus` came from the bundle but has no
 * captured card, so its parameters are marked unverified — do not present them
 * as reference-exact until a screenshot confirms them.
 */

export type PluginId =
  | "compressor"
  | "convolution"
  | "delay"
  | "distortion"
  | "eq"
  | "gate"
  | "limiter"
  | "reverb"
  | "chorus";

/** Primary knobs render large; secondary (filters, trims) render small. */
export type ParamTier = "primary" | "secondary";

export type ParamDef = {
  key: string;
  label: string;
  min: number;
  max: number;
  default: number;
  unit?: "ms" | "hz" | "db" | "%" | "s" | "ratio" | "";
  tier?: ParamTier;
  /** Beat-synced mode replaces the ms control with note divisions. */
  tempoSynced?: boolean;
};

export type PluginMode = { id: string; label: string };

export type PluginDef = {
  id: PluginId;
  name: string;
  /** Verbatim reference description (truncated at the card edge). */
  description: string;
  params: ParamDef[];
  modes?: PluginMode[];
  /** Reference card showed an impulse-response slot instead of knobs. */
  assetSlot?: { key: string; label: string; emptyLabel: string };
  /** True when the reference parameters are not fully captured. */
  unverified?: boolean;
};

const EQ_BAND_DEFAULT = { freq: 1000, q: 1, gain: 0 };

export const STUDIO_PLUGINS: readonly PluginDef[] = [
  {
    id: "compressor",
    name: "Compressor",
    description: "Classic dynamics compressor: threshold, ratio, and knee set how hard peaks are…",
    params: [
      { key: "threshold", label: "Thresh", min: -60, max: 0, default: -18, unit: "db", tier: "primary" },
      { key: "ratio", label: "Ratio", min: 1, max: 20, default: 4, unit: "ratio", tier: "primary" },
      { key: "knee", label: "Knee", min: 0, max: 40, default: 6, unit: "db", tier: "primary" },
      { key: "attack", label: "Atk", min: 0, max: 200, default: 10, unit: "ms", tier: "primary" },
      { key: "release", label: "Rel", min: 5, max: 1000, default: 120, unit: "ms", tier: "primary" },
      { key: "gain", label: "Gain", min: -12, max: 24, default: 0, unit: "db", tier: "secondary" },
    ],
  },
  {
    id: "convolution",
    name: "Convolution",
    description: "Places the signal in a sampled real space: load an impulse response, then shape it…",
    params: [
      { key: "mix", label: "Mix", min: 0, max: 100, default: 50, unit: "%", tier: "primary" },
      { key: "pre", label: "Pre", min: 0, max: 200, default: 0, unit: "ms", tier: "secondary" },
      { key: "width", label: "Width", min: 0, max: 200, default: 100, unit: "%", tier: "secondary" },
    ],
    assetSlot: { key: "irAssetId", label: "Impulse response", emptyLabel: "No asset loaded" },
  },
  {
    id: "delay",
    name: "Delay",
    description: "Echo with feedback and mix, free-running in milliseconds or synced to the beat…",
    modes: [
      { id: "time", label: "Time" },
      { id: "tempo", label: "Tempo" },
    ],
    params: [
      { key: "time", label: "Time", min: 1, max: 2000, default: 350, unit: "ms", tier: "primary", tempoSynced: true },
      { key: "feedback", label: "Feedback", min: 0, max: 95, default: 35, unit: "%", tier: "primary" },
      { key: "mix", label: "Mix", min: 0, max: 100, default: 25, unit: "%", tier: "primary" },
      { key: "lowCut", label: "Low Cut", min: 20, max: 2000, default: 120, unit: "hz", tier: "secondary" },
      { key: "highCut", label: "High Cut", min: 1000, max: 20000, default: 12000, unit: "hz", tier: "secondary" },
    ],
  },
  {
    id: "distortion",
    name: "Distortion",
    description: "A comprehensive distortion / waveshaper: drive into a pre-tilt tone stage, six…",
    modes: [
      { id: "hard", label: "Hard" },
      { id: "fold", label: "Fold" },
      { id: "align", label: "Align" },
      { id: "sine", label: "Sine" },
      { id: "crush", label: "Crush" },
    ],
    params: [
      { key: "drive", label: "Drive", min: 0, max: 100, default: 30, unit: "%", tier: "primary" },
      { key: "tilt", label: "Tilt", min: -100, max: 100, default: 0, tier: "primary" },
      { key: "bass", label: "Bass", min: -24, max: 24, default: 0, unit: "db", tier: "secondary" },
      { key: "freq", label: "Freq", min: 20, max: 20000, default: 800, unit: "hz", tier: "secondary" },
    ],
  },
  {
    id: "eq",
    name: "EQ",
    description: "Multi-band parametric EQ: per-band frequency, gain, Q and filter type on an…",
    params: [
      { key: "band1.freq", label: "Freq", min: 20, max: 20000, default: EQ_BAND_DEFAULT.freq, unit: "hz", tier: "primary" },
      { key: "band1.q", label: "Q", min: 0.1, max: 18, default: EQ_BAND_DEFAULT.q, tier: "primary" },
      { key: "band1.gain", label: "Gain", min: -24, max: 24, default: EQ_BAND_DEFAULT.gain, unit: "db", tier: "primary" },
    ],
  },
  {
    id: "gate",
    name: "Gate",
    description: "Noise gate: silences the signal below the threshold, with floor, attack, hold, and…",
    params: [
      { key: "threshold", label: "Threshold", min: -80, max: 0, default: -45, unit: "db", tier: "primary" },
      { key: "floor", label: "Floor", min: -80, max: 0, default: -60, unit: "db", tier: "secondary" },
      { key: "attack", label: "Attack", min: 0, max: 50, default: 2, unit: "ms", tier: "secondary" },
      { key: "hold", label: "Hold", min: 0, max: 500, default: 50, unit: "ms", tier: "secondary" },
    ],
  },
  {
    id: "limiter",
    name: "Limiter",
    description: "Brickwall lookahead limiter: drives the signal into a fixed ceiling with lookahead…",
    params: [
      { key: "lookahead", label: "Lookahead", min: 0, max: 20, default: 3, unit: "ms", tier: "primary" },
      { key: "preGain", label: "Pre Gain", min: -12, max: 24, default: 0, unit: "db", tier: "primary" },
      { key: "attack", label: "Attack", min: 0, max: 50, default: 1, unit: "ms", tier: "secondary" },
      { key: "release", label: "Release", min: 5, max: 500, default: 60, unit: "ms", tier: "secondary" },
    ],
  },
  {
    id: "reverb",
    name: "Reverb",
    description: "Algorithmic reverb with time, mix, width, damping, predelay, and low/high cut…",
    params: [
      { key: "time", label: "Decay", min: 0.2, max: 20, default: 2.4, unit: "s", tier: "primary" },
      { key: "mix", label: "Mix", min: 0, max: 100, default: 25, unit: "%", tier: "primary" },
      { key: "width", label: "Width", min: 0, max: 200, default: 100, unit: "%", tier: "secondary" },
      { key: "damping", label: "Damping", min: 0, max: 100, default: 40, unit: "%", tier: "secondary" },
      { key: "predelay", label: "Predelay", min: 0, max: 250, default: 20, unit: "ms", tier: "secondary" },
      { key: "lowCut", label: "Low Cut", min: 20, max: 2000, default: 120, unit: "hz", tier: "secondary" },
      { key: "highCut", label: "High Cut", min: 1000, max: 20000, default: 14000, unit: "hz", tier: "secondary" },
    ],
  },
  {
    id: "chorus",
    name: "Chorus",
    description: "Chorus effect (present in the shipped registry; catalog card not yet captured).",
    // Unverified: id is confirmed by the bundle, parameters are conventional
    // defaults pending a catalog screenshot. Do not claim reference parity.
    unverified: true,
    params: [
      { key: "rate", label: "Rate", min: 0.05, max: 10, default: 0.8, unit: "hz", tier: "primary" },
      { key: "depth", label: "Depth", min: 0, max: 100, default: 40, unit: "%", tier: "primary" },
      { key: "mix", label: "Mix", min: 0, max: 100, default: 30, unit: "%", tier: "primary" },
    ],
  },
] as const;

const BY_ID = new Map<string, PluginDef>(STUDIO_PLUGINS.map((plugin) => [plugin.id, plugin]));

export function getPlugin(id: string): PluginDef | undefined {
  return BY_ID.get(id);
}

export function isPluginId(value: string): value is PluginId {
  return BY_ID.has(value);
}

/** Default parameter map for a plugin, used when adding it to a chain. */
export function defaultParams(id: PluginId): Record<string, number> {
  const plugin = BY_ID.get(id);
  if (!plugin) return {};
  return Object.fromEntries(plugin.params.map((param) => [param.key, param.default]));
}

/** Default mode for a plugin that has mode tabs. */
export function defaultMode(id: PluginId): string | undefined {
  return BY_ID.get(id)?.modes?.[0]?.id;
}

export type PluginChainEntry = {
  /** Stable id for the chain slot (a plugin can appear twice). */
  entryId: string;
  pluginId: PluginId;
  presetId?: string | null;
  presetName: string;
  /** "Custom" in the reference means the preset has unsaved changes. */
  dirty?: boolean;
  mode?: string;
  params: Record<string, number>;
  assetId?: string | null;
  bypassed?: boolean;
  /** Reference: each plugin header has a popout control. */
  poppedOut?: boolean;
};

/** Build a chain entry with reference defaults. */
export function createChainEntry(
  pluginId: PluginId,
  entryId: string,
  presetName = "Default"
): PluginChainEntry {
  return {
    entryId,
    pluginId,
    presetId: null,
    presetName,
    dirty: false,
    mode: defaultMode(pluginId),
    params: defaultParams(pluginId),
    assetId: null,
    bypassed: false,
    poppedOut: false,
  };
}

/**
 * Clamp a parameter to its declared range. Unknown keys are dropped so a stale
 * project document cannot smuggle arbitrary state into the audio graph.
 */
export function sanitizeParams(
  pluginId: PluginId,
  input: Record<string, unknown> | null | undefined
): Record<string, number> {
  const plugin = BY_ID.get(pluginId);
  const out: Record<string, number> = {};
  if (!plugin) return out;
  for (const param of plugin.params) {
    const raw = input?.[param.key];
    const value = typeof raw === "number" && Number.isFinite(raw) ? raw : param.default;
    out[param.key] = Math.min(param.max, Math.max(param.min, value));
  }
  return out;
}
