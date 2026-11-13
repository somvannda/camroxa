import { createHash, randomUUID } from "node:crypto";

/**
 * Suno Studio document codec.
 *
 * Converts the platform project document (seconds, 0–100 mixer values, flat
 * `lanes` list) into Suno's Studio `state` (beats, 0–1 amplitudes, per-track
 * `clips`) and back.
 *
 * The schema is derived from real documents captured on 2026-11-13
 * (`docs/studio/SUNO_STUDIO_STATE_SCHEMA.md`), not guessed:
 *
 *   state = {
 *     timing: { type: "manual"|"follow-track", bps, bpsAutomation, lockBPS?, fallbackBPS?, trackId? },
 *     timeSignatureChanges: [{ startBeats, subdivisionsPerBar, beatsPerSubdivision }],
 *     amplitude, songFadeInBeats, songFadeOutBeats,
 *     loop: { enabled, startBeats, endBeats },
 *     metronome: { enabled, amplitude },
 *     editorPointerModes: { midi, audio },
 *     tracks: [{
 *       id, name, color, type: "audio"|"midi", height, mute, solo, arm, hidden,
 *       amplitude, balance, routingMode, signalChain, eq, faderAutomation,
 *       clips: [{
 *         id, type, name, color?, startBeats, endBeats, readStartBeats,
 *         fadeInBeats, fadeOutBeats, fadeInCurve, fadeOutCurve, mute,
 *         loop: { enabled, startBeats, endBeats },
 *         midi?: { notes: [{ id: number, startBeats, durationBeats, pitch, velocity }],
 *                  controlChanges, pitchBend, channelPressure, sysex },
 *         asset?: { id, type },
 *       }],
 *       takeLanes, takeLanesExpanded, clipCreationIntents,
 *     }],
 *   }
 *
 * Fields we do not generate are preserved from the baseline document, so a Suno
 * key we have not modelled yet survives a save.
 */

export interface LocalMidiNote {
  id?: string;
  pitch: number;
  start: number;
  length: number;
  velocity: number;
}

export interface LocalClip {
  id: string;
  title?: string;
  color?: string;
  start?: number;
  duration?: number;
  songId?: string | null;
  sunoId?: string | null;
  sunoAssetId?: string | null;
  midi?: {
    notes?: LocalMidiNote[];
    /** Seconds; -1..1. Mapped to `midi.pitchBend[{beats,value}]`. */
    bend?: Array<{ at: number; value: number }>;
    /** Seconds; 0..1. Mapped to CC 1 (`modWheel`) inside `midi.controlChanges`. */
    mod?: Array<{ at: number; value: number }>;
  };
  /** Alternate takes; only those with a Suno asset can mirror. */
  takes?: Array<{
    id: string;
    title?: string;
    audioUrl?: string | null;
    duration?: number;
    active?: boolean;
    sunoAssetId?: string | null;
  }>;
  [key: string]: unknown;
}

export interface LocalTrack {
  id: string;
  name?: string;
  color?: string;
  volume?: number;
  pan?: number;
  muted?: boolean;
  solo?: boolean;
  hidden?: boolean;
  index?: number;
  clipIds?: string[];
  volumeAutomation?: Array<{ time: number; value: number }>;
  panAutomation?: Array<{ time: number; value: number }>;
  sunoId?: string | null;
  chain?: unknown[];
  [key: string]: unknown;
}

export interface LocalDocument {
  tracks?: LocalTrack[];
  lanes?: LocalClip[];
  /** Ruler section markers: seconds + label, as the editor stores them. */
  markers?: Array<{ id: string; time: number; label?: string; color?: string }>;
  /** Plugin chains keyed by local track id. */
  chains?: Record<string, Array<Record<string, unknown>>>;
  masterChain?: Array<Record<string, unknown>>;
  masterVolume?: number;
  masterMuted?: boolean;
  loopStart?: number;
  loopEnd?: number;
  [key: string]: unknown;
}

export interface CodecInput {
  title: string;
  majorVersion: number;
  bpm: number;
  timeSignature: string;
  data: LocalDocument;
  /** Last document Suno returned; unknown keys are preserved. */
  baseline?: Record<string, unknown> | null;
  /** Suno clip ids we wrote last time, so a local delete propagates. */
  previousLocalClipIds?: string[];
}

export interface CodecResult {
  state: Record<string, unknown>;
  /** Local clip ids that cannot be represented on Suno yet (no Suno asset). */
  skippedClipIds: string[];
}

/** Round a float to 6 decimals so a save does not churn on float noise. */
function round(value: number): number {
  return Number.isFinite(value) ? Math.round(value * 1e6) / 1e6 : 0;
}

export function beatsFromSeconds(seconds: number, bps: number): number {
  return round((Number(seconds) || 0) * bps);
}

export function secondsFromBeats(beats: number, bps: number): number {
  return bps > 0 ? round((Number(beats) || 0) / bps) : 0;
}

/**
 * Deterministic UUID-shaped id for a local id. Suno's ids are UUIDs and we need
 * the same track/clip to keep its identity across saves and pulls.
 */
export function stableSunoId(localId: string): string {
  const hex = createHash("sha256").update(`camxora:${localId}`).digest("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-5${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

/** `4/4` → Suno's `{subdivisionsPerBar, beatsPerSubdivision}`. */
export function timeSignatureParts(signature: string): {
  subdivisionsPerBar: number;
  beatsPerSubdivision: number;
} {
  const match = /^(\d{1,2})\s*\/\s*(\d{1,2})$/.exec(String(signature ?? "").trim());
  const numerator = match ? Math.max(1, Math.min(32, Number(match[1]))) : 4;
  const denominator = match ? Math.max(1, Math.min(32, Number(match[2]))) : 4;
  return {
    subdivisionsPerBar: numerator,
    beatsPerSubdivision: round(4 / denominator),
  };
}

export function timeSignatureFromState(
  changes: unknown
): string {
  const first = Array.isArray(changes) ? (changes[0] as Record<string, unknown> | undefined) : undefined;
  if (!first) return "4/4";
  const numerator = Number(first.subdivisionsPerBar) || 4;
  const perSubdivision = Number(first.beatsPerSubdivision) || 1;
  const denominator = Math.round(4 / perSubdivision) || 4;
  return `${numerator}/${denominator}`;
}

/** BPM from a Suno timing block (`bps` is beats per second). */
export function bpmFromState(timing: unknown): number {
  const block = (timing ?? {}) as Record<string, unknown>;
  const bps = Number(block.bps ?? block.fallbackBPS);
  if (!Number.isFinite(bps) || bps <= 0) return 120;
  return Math.round(bps * 60);
}

/** Suno's note id is numeric; derive a stable positive int32 from ours. */
export function noteId(value: string | undefined, fallbackIndex: number): number {
  const source = value ?? `note-${fallbackIndex}`;
  const hash = createHash("sha256").update(source).digest();
  const n = hash.readUInt32BE(0) & 0x7fffffff;
  return n === 0 ? fallbackIndex + 1 : n;
}

function midiFromLocal(
  clip: LocalClip,
  bps: number
): Record<string, unknown> | null {
  if (!clip.midi) return null;
  const notes = Array.isArray(clip.midi.notes) ? clip.midi.notes : [];
  const bend = (Array.isArray(clip.midi.bend) ? clip.midi.bend : []).map((point) => ({
    beats: beatsFromSeconds(Number(point.at) || 0, bps),
    value: Math.max(-1, Math.min(1, Number(point.value) || 0)),
  }));
  const mod = (Array.isArray(clip.midi.mod) ? clip.midi.mod : []).map((point) => ({
    beats: beatsFromSeconds(Number(point.at) || 0, bps),
    value: Math.max(0, Math.min(1, Number(point.value) || 0)),
  }));
  return {
    notes: notes.map((note, index) => ({
      id: noteId(note.id, index),
      startBeats: beatsFromSeconds(note.start, bps),
      durationBeats: Math.max(0.01, beatsFromSeconds(note.length, bps)),
      pitch: Math.max(0, Math.min(127, Math.round(Number(note.pitch) || 0))),
      velocity: Math.max(1, Math.min(127, Math.round(Number(note.velocity) || 100))),
    })),
    // Controller entries group their points; pitch bend is a flat point list.
    controlChanges: mod.length
      ? [{ controller: 1, channel: 0, points: mod }]
      : [],
    pitchBend: bend,
    channelPressure: [],
    sysex: [],
  };
}

/** One alternate take as a Suno clip inside a take lane. */
function takeClipFromLocal(
  clip: LocalClip,
  take: NonNullable<LocalClip["takes"]>[number],
  track: LocalTrack,
  bps: number
): Record<string, unknown> | null {
  const assetId = typeof take.sunoAssetId === "string" ? take.sunoAssetId : "";
  if (!assetId) return null;
  const start = Number(clip.start) || 0;
  const duration = Math.max(0, Number(take.duration ?? clip.duration) || 0);
  const startBeats = beatsFromSeconds(start, bps);
  const endBeats = beatsFromSeconds(start + duration, bps);
  return {
    id: stableSunoId(take.id),
    type: "audio",
    name: take.title ?? clip.title ?? "Take",
    color: clip.color ?? track.color,
    startBeats,
    endBeats,
    readStartBeats: 0,
    fadeInBeats: 0,
    fadeOutBeats: 0,
    fadeInCurve: 1,
    fadeOutCurve: 1,
    mute: true,
    loop: { enabled: false, startBeats: 0, endBeats },
    asset: { id: assetId, type: "clip" },
    clipId: assetId,
    amplitude: 1,
    transposition: 0,
    streaming: false,
    reversed: false,
    formantCorrection: 0,
    warp: { enabled: false, markersHash: "", awaitingAnalysis: false },
  };
}

function localClipsForTrack(data: LocalDocument, track: LocalTrack): LocalClip[] {  const lanes = Array.isArray(data.lanes) ? data.lanes : [];
  const ids = new Set(track.clipIds ?? []);
  const byId = lanes.filter((clip) => ids.has(clip.id));
  if (byId.length > 0) return byId;
  // Fallback for documents written before tracks carried clipIds.
  return lanes.filter((clip) => (clip as { trackId?: string }).trackId === track.id);
}

function sunoClipFromLocal(
  clip: LocalClip,
  track: LocalTrack,
  bps: number
): { clip: Record<string, unknown> } | { skip: string } {
  const start = Number(clip.start) || 0;
  const duration = Math.max(0, Number(clip.duration) || 0);
  const startBeats = beatsFromSeconds(start, bps);
  const endBeats = beatsFromSeconds(start + duration, bps);
  const readStartBeats = beatsFromSeconds(Number(clip.offset) || 0, bps);
  const fadeInBeats = Math.max(0, beatsFromSeconds(Number(clip.fadeIn) || 0, bps));
  const midi = midiFromLocal(clip, bps);
  const assetId =
    typeof clip.sunoAssetId === "string" && clip.sunoAssetId ? clip.sunoAssetId : null;
  if (!midi && !assetId) return { skip: clip.id };

  const body: Record<string, unknown> = {
    id: clip.sunoId ?? stableSunoId(clip.id),
    type: midi ? "midi" : "audio",
    name: clip.title ?? "Clip",
    color: clip.color ?? track.color,
    startBeats,
    endBeats,
    readStartBeats,
    fadeInBeats,
    fadeOutBeats: 0,
    fadeInCurve: 1,
    fadeOutCurve: 1,
    mute: false,
    loop: { enabled: false, startBeats: readStartBeats, endBeats },
  };
  if (midi) body.midi = midi;
  if (assetId) {
    // Audio clips reference a Suno-owned clip asset. `type` is always "clip" in
    // every captured project; `clipId` is the source clip, not the timeline id.
    body.asset = { id: assetId, type: "clip" };
    body.clipId = assetId;
    body.amplitude = 1;
    body.transposition = 0;
    body.streaming = false;
    body.reversed = false;
    body.formantCorrection = 0;
    body.warp = { enabled: false, markersHash: "", awaitingAnalysis: false };
  }
  return { clip: body };
}

function automationToBeats(
  points: unknown,
  bps: number
): Array<{ timeBeats: number; value: number }> {
  if (!Array.isArray(points)) return [];
  return points
    .map((point) => {
      const record = (point ?? {}) as Record<string, unknown>;
      return {
        timeBeats: beatsFromSeconds(Number(record.time) || 0, bps),
        value: round(Number(record.value) || 0),
      };
    })
    .sort((a, b) => a.timeBeats - b.timeBeats);
}

/** Sections are a registry keyed by id: {id, name, startBeats, endBeats, color}. */
function sectionsFromMarkers(
  markers: LocalDocument["markers"],
  bps: number,
  contentEndBeats: number
): Record<string, unknown> {
  const list = (Array.isArray(markers) ? markers : [])
    .map((marker) => ({
      id: String(marker.id),
      beats: beatsFromSeconds(Number(marker.time) || 0, bps),
      name: String(marker.label ?? "Section").slice(0, 80) || "Section",
      color: typeof marker.color === "string" ? marker.color : "#7c5cff",
    }))
    .sort((a, b) => a.beats - b.beats);
  const sections: Record<string, unknown> = {};
  list.forEach((marker, index) => {
    const next = list[index + 1];
    const endBeats = next
      ? next.beats
      : Math.max(marker.beats + 1, contentEndBeats);
    sections[marker.id] = {
      id: marker.id,
      name: marker.name,
      startBeats: marker.beats,
      endBeats,
      color: marker.color,
    };
  });
  return sections;
}

function markersFromState(
  sections: unknown,
  bps: number
): Array<{ id: string; time: number; label: string; color?: string }> {
  if (!sections || typeof sections !== "object" || Array.isArray(sections)) return [];
  return Object.entries(sections as Record<string, Record<string, unknown>>)
    .map(([key, section]) => ({
      id: String(section?.id ?? key),
      time: secondsFromBeats(Number(section?.startBeats) || 0, bps),
      label: String(section?.name ?? "Section"),
      color: typeof section?.color === "string" ? section.color : undefined,
    }))
    .sort((a, b) => a.time - b.time);
}

/** Suno plugin catalog entries captured on 2026-11-13 (schema doc §10). */
export interface SunoPluginMapping {
  pluginVersionId: string;
  /** Local numeric param key → Suno numeric param key. */
  params: Record<string, string>;
  /** Per-param multiplier when the two sides use different scales (e.g. 0–100 → 0–1). */
  scales?: Record<string, number>;
  /** Local 0/1 param key → Suno boolean param key. */
  booleans?: Record<string, string>;
  /** Local chain string field → Suno param key (e.g. `mode`). */
  strings?: Record<string, string>;
}

/**
 * Only plugins whose parameters map one-to-one are listed. Distortion and chorus
 * use different parameter sets (and chorus `rate` is a division string on Suno),
 * so they stay local until captured values prove a translation.
 */
export const SUNO_PLUGIN_CATALOG: Record<string, SunoPluginMapping> = {
  compressor: {
    pluginVersionId: "a4838315-d631-4255-946c-c65531bc9cd4",
    params: {
      threshold: "threshold",
      ratio: "ratio",
      knee: "knee",
      attack: "attack",
      release: "release",
      gain: "output",
    },
  },
  convolution: {
    pluginVersionId: "ddcfbfdc-ec10-4a92-8a8b-56245cf48293",
    params: { mix: "mix", gain: "gain", pre: "predelay", width: "width" },
  },
  delay: {
    pluginVersionId: "e2b9270b-5099-4e2b-8ddc-c3a2b2cbe31e",
    params: {
      time: "milliseconds",
      feedback: "feedback",
      mix: "mix",
      lowCut: "lowCut",
      highCut: "highCut",
    },
    // Suno stores delay wet/dry and feedback as 0–1, we store percentages.
    scales: { feedback: 0.01, mix: 0.01 },
  },
  gate: {
    pluginVersionId: "14fb47e6-c951-4a35-bfa6-f14d2396b4d0",
    params: { threshold: "threshold", floor: "floor", attack: "attack", hold: "hold" },
  },
  limiter: {
    pluginVersionId: "bf422c67-c85e-4b6d-9db9-1769c5912941",
    params: {
      lookahead: "lookahead",
      preGain: "preGain",
      attack: "attack",
      release: "release",
    },
  },
  reverb: {
    pluginVersionId: "dec400a6-9dac-4c8a-b553-dd7bd2eb5f29",
    params: {
      time: "time",
      mix: "mix",
      width: "width",
      damping: "damping",
      predelay: "predelay",
      lowCut: "lowCut",
      highCut: "highCut",
    },
  },
  eq: {
    pluginVersionId: "b1a718a1-839f-48d8-9482-ef6f64d490f0",
    params: Object.fromEntries(
      [1, 2, 3, 4].flatMap((band) => [
        [`band${band}.freq`, `freq${band}`],
        [`band${band}.q`, `q${band}`],
        [`band${band}.gain`, `gain${band}`],
      ])
    ),
    booleans: Object.fromEntries(
      [1, 2, 3, 4].map((band) => [`band${band}.on`, `enabled${band}`])
    ),
  },
  distortion: {
    pluginVersionId: "20c5b585-bdd5-45ad-9640-5b1fd68955f6",
    params: { drive: "Input Gain", tilt: "Pre Tilt", freq: "Post Cutoff" },
    // 0–100 % drive → 0–24 dB input gain.
    scales: { drive: 0.24 },
  },
  chorus: {
    pluginVersionId: "537ba288-f700-4c96-b103-c84e2b62fab6",
    params: { depth: "depth", mix: "mix" },
    scales: { depth: 0.01, mix: 0.01 },
  },
};

/** MIDI tracks carry their instrument as a synth plugin instance. */
export const SUNO_SYNTH_PLUGIN_ID = "77cd4e27-c6cc-47ae-981a-7342778e8ff5";

function instrumentWaveform(instrument: unknown): string {
  if (instrument === "sawtooth") return "saw";
  if (instrument === "triangle") return "triangle";
  return "sine";
}

function waveformInstrument(waveform: unknown): string {
  if (waveform === "saw") return "sawtooth";
  if (waveform === "triangle") return "triangle";
  return "sine";
}

const DISTORTION_SHAPES: Record<string, string> = {
  hard: "Hard",
  fold: "Fold",
  align: "Align",
  sine: "Sine",
  crush: "Crush",
};

/** Hz → Suno's division string (`1/4` = one beat). */
function chorusDivision(hz: number, bpm: number): string {
  const cyclesPerBeat = (Math.max(0.01, hz) * 60) / Math.max(1, bpm);
  const raw = 4 * Math.max(0.01, cyclesPerBeat);
  const denominator = Math.max(1, Math.min(32, 2 ** Math.round(Math.log2(raw))));
  return `1/${denominator}`;
}

function chorusHz(division: unknown, bpm: number): number {
  const match = /^1\/(\d+)$/.exec(String(division ?? ""));
  const denominator = match ? Number(match[1]) : 8;
  // A 1/4 division is one beat, so a 1/n division is n/4 beats per cycle.
  const cyclesPerBeat = denominator / 4;
  return round((cyclesPerBeat * bpm) / 60);
}

const SUNO_PLUGIN_BY_VERSION = new Map(
  Object.entries(SUNO_PLUGIN_CATALOG).map(([pluginId, def]) => [def.pluginVersionId, pluginId])
);

/**
 * Map one local chain entry to a Suno plugin instance. Returns null when the
 * plugin has no verified translation (custom plugins, distortion, chorus).
 */
export function chainEntryToSuno(
  entry: Record<string, unknown>,
  fallbackIndex: number,
  bpm = 120
): Record<string, unknown> | null {
  const pluginId = typeof entry.pluginId === "string" ? entry.pluginId : "";
  const def = SUNO_PLUGIN_CATALOG[pluginId];
  if (!def) return null;
  const localParams = (entry.params ?? {}) as Record<string, unknown>;
  const params: Record<string, unknown> = {};
  for (const [local, suno] of Object.entries(def.params)) {
    const raw = Number(localParams[local]);
    if (!Number.isFinite(raw)) continue;
    params[suno] = round(raw * (def.scales?.[local] ?? 1));
  }
  for (const [local, suno] of Object.entries(def.booleans ?? {})) {
    if (localParams[local] !== undefined) params[suno] = Number(localParams[local]) > 0.5;
  }
  for (const [local, suno] of Object.entries(def.strings ?? {})) {
    if (typeof entry[local] === "string") params[suno] = entry[local];
  }
  if (pluginId === "delay") {
    const mode = entry.mode === "tempo" ? "tempo" : "time";
    const milliseconds = Number(localParams.time) || 0;
    params.mode = mode;
    params.milliseconds = milliseconds;
    // Suno keeps both fields; the mode decides which one it plays.
    params.beats = round((milliseconds * bpm) / 60_000);
  }
  if (pluginId === "eq") {
    params.enabled5 = false;
    params.enabled6 = false;
  }
  if (pluginId === "distortion") {
    params.Shape = DISTORTION_SHAPES[String(entry.mode ?? "")] ?? "Soft";
    params.Mix = 1;
    params["Output Gain"] = 0;
    params.Bias = 0;
    params.Crush = 0;
    params["Post Resonance"] = 0.707;
  }
  if (pluginId === "chorus") {
    const hz = Number((entry.params as Record<string, unknown> | undefined)?.rate) || 0.8;
    params["rate (1/16, 1/8, 1/4)"] = chorusDivision(hz, bpm);
  }
  const entryId =
    typeof entry.entryId === "string" && entry.entryId
      ? entry.entryId
      : `plugin-${pluginId}-${fallbackIndex}`;
  return {
    id: stableSunoId(entryId),
    pluginVersionId: def.pluginVersionId,
    ...(typeof entry.presetId === "string" && entry.presetId
      ? { presetId: entry.presetId }
      : {}),
    bypassed: Boolean(entry.bypassed),
    params,
    paramAutomation: {},
  };
}

/** Map a Suno plugin instance back to a local chain entry (verified plugins only). */
export function chainEntryFromSuno(
  entry: Record<string, unknown>,
  fallbackIndex: number,
  bpm = 120
): Record<string, unknown> | null {
  const versionId = typeof entry.pluginVersionId === "string" ? entry.pluginVersionId : "";
  const pluginId = SUNO_PLUGIN_BY_VERSION.get(versionId);
  if (!pluginId) return null;
  const def = SUNO_PLUGIN_CATALOG[pluginId];
  const sunoParams = (entry.params ?? {}) as Record<string, unknown>;
  const params: Record<string, number> = {};
  for (const [local, suno] of Object.entries(def.params)) {
    const value = Number(sunoParams[suno]);
    if (Number.isFinite(value)) {
      const scale = def.scales?.[local] ?? 1;
      params[local] = round(value / scale);
    }
  }
  for (const [local, suno] of Object.entries(def.booleans ?? {})) {
    if (sunoParams[suno] !== undefined) params[local] = sunoParams[suno] ? 1 : 0;
  }
  let mode =
    pluginId === "delay" && typeof sunoParams.mode === "string"
      ? sunoParams.mode === "tempo"
        ? "tempo"
        : "time"
      : undefined;
  if (pluginId === "distortion" && typeof sunoParams.Shape === "string") {
    mode = sunoParams.Shape.toLowerCase();
  }
  if (pluginId === "chorus") {
    params.rate = chorusHz(sunoParams["rate (1/16, 1/8, 1/4)"], bpm);
  }
  return {
    entryId: typeof entry.id === "string" ? `entry-${entry.id.slice(0, 8)}` : `entry-${fallbackIndex}`,
    pluginId,
    presetId: typeof entry.presetId === "string" ? entry.presetId : null,
    presetName: "Custom",
    mode,
    params,
    sunoId: typeof entry.id === "string" ? entry.id : undefined,
  };
}

function buildChain(
  entries: Array<Record<string, unknown>> | undefined,
  bpm = 120,
  fallbackIndexBase = 0
): Record<string, unknown>[] {
  return (Array.isArray(entries) ? entries : [])
    .map((entry, index) => chainEntryToSuno(entry, fallbackIndexBase + index, bpm))
    .filter((entry): entry is Record<string, unknown> => entry !== null);
}

function buildMasterChain(
  entries: Array<Record<string, unknown>> | undefined
): Record<string, unknown>[] {
  const chain: Record<string, unknown>[] = [];
  for (const [index, entry] of (Array.isArray(entries) ? entries : []).entries()) {
    const type = String(entry.type ?? "").toLowerCase();
    const params = (entry.params ?? {}) as Record<string, unknown>;
    const amount = Math.max(0, Math.min(1, Number(entry.amount ?? 0.5)));
    const bypassed = entry.enabled === false;
    if (type.includes("limit")) {
      chain.push({
        id: stableSunoId(`master-limiter-${index}`),
        pluginVersionId: SUNO_PLUGIN_CATALOG.limiter.pluginVersionId,
        bypassed,
        params: {
          lookahead: Number(params.lookahead ?? 3),
          preGain: Number(params.preGain ?? 0),
          attack: Number(params.attack ?? 1),
          release: Number(params.release ?? 60),
        },
        paramAutomation: {},
      });
      continue;
    }
    if (type.includes("eq")) {
      // Our master EQ is one peaking band at 1.2 kHz; ±12 dB around the midpoint.
      chain.push({
        id: stableSunoId(`master-eq-${index}`),
        pluginVersionId: SUNO_PLUGIN_CATALOG.eq.pluginVersionId,
        bypassed,
        params: {
          enabled1: false,
          enabled2: false,
          enabled3: true,
          enabled4: false,
          enabled5: false,
          enabled6: false,
          freq3: 1200,
          q3: 0.9,
          gain3: round((amount - 0.5) * 24),
        },
        paramAutomation: {},
      });
      continue;
    }
    if (type.includes("compress")) {
      // Mirrors buildMasterBus: threshold -24..-12 dB, ratio 2..8, fixed timing.
      chain.push({
        id: stableSunoId(`master-compressor-${index}`),
        pluginVersionId: SUNO_PLUGIN_CATALOG.compressor.pluginVersionId,
        bypassed,
        params: {
          threshold: round(-24 + amount * 12),
          ratio: round(2 + amount * 6),
          attack: 3,
          release: 250,
          knee: 24,
        },
        paramAutomation: {},
      });
    }
  }
  return chain;
}

/**
 * Build the Suno document for one Camxora project.
 *
 * The arrangement is generated from the local document (local-first mirror).
 * Every top-level key we do not generate — selection, layout, panel state,
 * warp registries, plugin instances we do not model — is copied from the
 * baseline so a save never erases Suno state we have not mapped yet.
 */
export function projectDocumentToSunoState(input: CodecInput): CodecResult {
  const bpm = Math.max(20, Math.min(300, Number(input.bpm) || 120));
  const bps = round(bpm / 60);
  const data = input.data ?? {};
  const tracks = Array.isArray(data.tracks) ? data.tracks : [];
  const signature = timeSignatureParts(input.timeSignature);
  const skippedClipIds: string[] = [];
  const previousClipIds = new Set(input.previousLocalClipIds ?? []);

  const sunoTracks = tracks
    .slice()
    .sort((a, b) => (Number(a.index) || 0) - (Number(b.index) || 0))
    .map((track) => {
      const trackId = track.sunoId ?? stableSunoId(track.id);
      const localClips = localClipsForTrack(data, track);
      const localClipSunoIds = new Set(
        localClips.map((clip) => clip.sunoId ?? stableSunoId(clip.id))
      );
      const built = localClips
        .map((clip) => sunoClipFromLocal(clip, track, bps))
        .filter((entry): entry is { clip: Record<string, unknown> } => {
          if ("skip" in entry) {
            skippedClipIds.push(entry.skip);
            return false;
          }
          return true;
        })
        .map((entry) => entry.clip);
      const builtIds = new Set(built.map((clip) => clip.id));
      // Keep clips the baseline owns that we did not rebuild (audio we cannot
      // represent yet, or clips added on Suno). Dropping them would delete real
      // audio from the mirrored project.
      const baselineTrack = Array.isArray(input.baseline?.tracks)
        ? (input.baseline?.tracks as Array<Record<string, unknown>>).find(
            (candidate) => candidate.id === trackId
          )
        : undefined;
      const preserved = Array.isArray(baselineTrack?.clips)
        ? (baselineTrack?.clips as Array<Record<string, unknown>>).filter((clip) => {
            const clipId = String(clip.id ?? "");
            if (builtIds.has(clipId)) return false;
            // We mirrored this clip before and it is gone locally: a delete.
            if (previousClipIds.has(clipId) && !localClipSunoIds.has(clipId)) return false;
            return true;
          })
        : [];
      const clips = [...built, ...preserved];
      const hasMidi = clips.some((clip) => clip.type === "midi");
      const chain = buildChain(
        (data.chains ?? {})[track.id] as Array<Record<string, unknown>> | undefined,
        bpm
      );
      if (hasMidi) {
        // Suno renders MIDI through a synth plugin instance. Keep the baseline
        // instance (and any params the user set on Suno) but apply our waveform.
        const baselineSynth = Array.isArray(baselineTrack?.signalChain)
          ? (baselineTrack?.signalChain as Array<Record<string, unknown>>).find(
              (entry) => entry.pluginVersionId === SUNO_SYNTH_PLUGIN_ID
            )
          : undefined;
        const midiClip = localClips.find((clip) => clip.midi);
        chain.unshift({
          id: baselineSynth?.id ?? stableSunoId(`${track.id}:synth`),
          pluginVersionId: SUNO_SYNTH_PLUGIN_ID,
          bypassed: false,
          params: {
            ...((baselineSynth?.params ?? {}) as Record<string, unknown>),
            oscAEnabled: "on",
            waveform1: instrumentWaveform(midiClip?.instrument),
          },
          paramAutomation: {},
        });
      }
      const takeClips = localClips
        .flatMap((clip) =>
          (Array.isArray(clip.takes) ? clip.takes : []).map((take) => ({ clip, take }))
        )
        .filter(({ take }) => take.active !== true)
        .map(({ clip, take }) => takeClipFromLocal(clip, take, track, bps))
        .filter((clip): clip is Record<string, unknown> => clip !== null);
      const baselineTakeLanes = Array.isArray(baselineTrack?.takeLanes)
        ? (baselineTrack?.takeLanes as Array<Record<string, unknown>>)
        : null;
      // A take lane carries the alternates we can represent; when we cannot
      // (their audio has no Suno asset), keep Suno's lanes untouched.
      const takeLanes =
        takeClips.length > 0
          ? [
              {
                id: stableSunoId(`${track.id}:take-lane`),
                name: "Take lane",
                type: hasMidi ? "midi" : "audio",
                height: 32,
                dismissed: false,
                clips: takeClips,
                clipCreationIntents: [],
              },
            ]
          : baselineTakeLanes ?? [
              {
                id: stableSunoId(`${track.id}:take-lane`),
                name: "Take 1",
                type: hasMidi ? "midi" : "audio",
                height: 32,
                dismissed: true,
                clips: [],
                clipCreationIntents: [],
              },
            ];
      return {
        id: trackId,
        name: track.name ?? "Track",
        color: track.color ?? "#7c5cff",
        type: hasMidi ? "midi" : "audio",
        height: 88,
        mute: Boolean(track.muted),
        solo: Boolean(track.solo),
        arm: false,
        hidden: Boolean(track.hidden),
        amplitude: round(Math.max(0, Math.min(1.2, (Number(track.volume ?? 80) || 0) / 100))),
        balance: round(Math.max(-1, Math.min(1, (Number(track.pan ?? 0) || 0) / 100))),
        routingMode: "stereo",
        signalChain: chain,
        faderAutomation: automationToBeats(track.volumeAutomation, bps),
        clips,
        takeLanes,
        takeLanesExpanded: takeClips.length > 0,
        clipCreationIntents: [],
      };
    });

  const fallbackTracks = Array.isArray((input.baseline ?? {}).tracks)
    ? ((input.baseline ?? {}).tracks as unknown[])
    : null;
  const contentEndBeats = sunoTracks.reduce((max, track) => {
    for (const clip of track.clips as Array<Record<string, unknown>>) {
      const end = Number(clip.endBeats) || 0;
      if (end > max) max = end;
    }
    return max;
  }, 0);  // A local document with no tracks is ambiguous: it can mean "every track was
  // deleted" or "the data never loaded". Never wipe a Suno-only project on the
  // ambiguous case; a real delete still pushes when at least one track remains.
  const nextTracks = sunoTracks.length > 0 || fallbackTracks === null ? sunoTracks : fallbackTracks;

  const state: Record<string, unknown> = {
    ...(input.baseline ?? {}),
    title: String(input.title ?? "").trim().slice(0, 120) || "Untitled Project",
    majorVersion: Math.max(1, Math.min(10, Number(input.majorVersion) || 2)),
    timing: {
      type: "manual",
      bps,
      bpsAutomation: [],
      lockBPS: false,
    },
    timeSignatureChanges: [
      {
        startBeats: 0,
        subdivisionsPerBar: signature.subdivisionsPerBar,
        beatsPerSubdivision: signature.beatsPerSubdivision,
      },
    ],
    amplitude: round(Math.max(0, Math.min(1.2, (Number(data.masterVolume ?? 100) || 0) / 100))),
    songFadeInBeats: 0,
    songFadeOutBeats: 0,
    loop: {
      enabled: Number(data.loopEnd ?? 0) > Number(data.loopStart ?? 0),
      startBeats: beatsFromSeconds(Number(data.loopStart ?? 0) || 0, bps),
      endBeats: beatsFromSeconds(Number(data.loopEnd ?? 0) || 0, bps),
    },
    metronome: { enabled: false, amplitude: 1 },
    editorPointerModes: { midi: "select", audio: "select" },
    sections: sectionsFromMarkers(data.markers, bps, contentEndBeats),
    masterSignalChain: buildMasterChain(data.masterChain),
    tracks: nextTracks,
    selection: {
      trackIds: nextTracks.map((track) => (track as { id?: string }).id ?? ""),
      focusedTrackId: (nextTracks[0] as { id?: string } | undefined)?.id ?? null,
      noteIds: [],
      anchorBeats: 0,
      focusBeats: 0,
      contextBeforeBeats: 32,
      contextAfterBeats: 32,
      focusedArea: "timeline",
      warpMarkerSeconds: {},
    },
  };

  return { state, skippedClipIds };
}

/**
 * Read a Suno document back into local project fields. Used by the pull path and
 * by the round-trip test; only fields with a verified mapping are projected.
 */
export function sunoStateToProjectData(state: Record<string, unknown>): {
  bpm: number;
  timeSignature: string;
  tracks: LocalTrack[];
  lanes: LocalClip[];
  markers: Array<{ id: string; time: number; label: string; color?: string }>;
  chains: Record<string, Array<Record<string, unknown>>>;
  masterChain: Array<Record<string, unknown>>;
} {
  const bpm = bpmFromState(state.timing);
  const bps = round(bpm / 60);
  const signature = timeSignatureFromState(state.timeSignatureChanges);
  const tracks: LocalTrack[] = [];
  const lanes: LocalClip[] = [];
  const chains: Record<string, Array<Record<string, unknown>>> = {};

  const sunoTracks = Array.isArray(state.tracks) ? state.tracks : [];
  sunoTracks.forEach((entry, index) => {
    const track = (entry ?? {}) as Record<string, unknown>;
    const trackId = typeof track.id === "string" ? track.id : `track-${index}`;
    const clips = Array.isArray(track.clips) ? track.clips : [];
    const clipIds: string[] = [];
    const sunoChain = (Array.isArray(track.signalChain) ? track.signalChain : []).map(
      (entry) => (entry ?? {}) as Record<string, unknown>
    );
    const synth = sunoChain.find((entry) => entry.pluginVersionId === SUNO_SYNTH_PLUGIN_ID);
    const instrument = synth
      ? waveformInstrument((synth.params as Record<string, unknown> | undefined)?.waveform1)
      : undefined;
    clips.forEach((raw, clipIndex) => {
      const clip = (raw ?? {}) as Record<string, unknown>;
      const clipId = typeof clip.id === "string" ? clip.id : `${trackId}-clip-${clipIndex}`;
      clipIds.push(clipId);
      const midi = clip.midi as
        | {
            notes?: Array<Record<string, unknown>>;
            pitchBend?: Array<Record<string, unknown>>;
            controlChanges?: Array<Record<string, unknown>>;
          }
        | undefined;
      const bend = (Array.isArray(midi?.pitchBend) ? midi?.pitchBend : []).map((point) => ({
        at: secondsFromBeats(Number(point.beats) || 0, bps),
        value: Number(point.value) || 0,
      }));
      const mod = (Array.isArray(midi?.controlChanges) ? midi?.controlChanges : [])
        .filter((change) => Number(change.controller) === 1)
        .flatMap((change) =>
          (Array.isArray(change.points) ? change.points : []).map(
            (point: Record<string, unknown>) => ({
              at: secondsFromBeats(Number(point.beats) || 0, bps),
              value: Number(point.value) || 0,
            })
          )
        );
      lanes.push({
        id: clipId,
        sunoId: clipId,
        title: typeof clip.name === "string" ? clip.name : "Clip",
        color: typeof clip.color === "string" ? clip.color : undefined,
        start: secondsFromBeats(Number(clip.startBeats) || 0, bps),
        duration: secondsFromBeats(
          (Number(clip.endBeats) || 0) - (Number(clip.startBeats) || 0),
          bps
        ),
        offset: secondsFromBeats(Number(clip.readStartBeats) || 0, bps),
        fadeIn: secondsFromBeats(Number(clip.fadeInBeats) || 0, bps),
        midi: midi
          ? {
              notes: (midi.notes ?? []).map((note) => ({
                id: String(note.id ?? ""),
                pitch: Number(note.pitch) || 0,
                start: secondsFromBeats(Number(note.startBeats) || 0, bps),
                length: secondsFromBeats(Number(note.durationBeats) || 0, bps),
                velocity: Number(note.velocity) || 100,
              })),
              ...(bend.length ? { bend } : {}),
              ...(mod.length ? { mod } : {}),
              ...(instrument ? { instrument } : {}),
            }
          : undefined,
        songId: (clip.asset as { id?: string } | undefined)?.id,
        sunoAssetId: (clip.asset as { id?: string } | undefined)?.id,
      });
    });
    tracks.push({
      id: trackId,
      sunoId: trackId,
      name: typeof track.name === "string" ? track.name : `Track ${index + 1}`,
      color: typeof track.color === "string" ? track.color : undefined,
      index,
      volume: Math.round((Number(track.amplitude) || 0) * 100),
      pan: Math.round((Number(track.balance) || 0) * 100),
      muted: Boolean(track.mute),
      solo: Boolean(track.solo),
      hidden: Boolean(track.hidden),
      clipIds,
    });
    const effectEntries = sunoChain.filter(
      (entry) => entry.pluginVersionId !== SUNO_SYNTH_PLUGIN_ID
    );
    const mappedChain = effectEntries
      .map((entry, chainIndex) => chainEntryFromSuno(entry, chainIndex, bpm))
      .filter((entry): entry is Record<string, unknown> => entry !== null);
    if (mappedChain.length === effectEntries.length) {
      chains[trackId] = mappedChain;
    }
  });

  const masterChain: Array<Record<string, unknown>> = [];
  for (const entry of Array.isArray(state.masterSignalChain) ? state.masterSignalChain : []) {
    const record = (entry ?? {}) as Record<string, unknown>;
    const params = (record.params ?? {}) as Record<string, unknown>;
    const versionId = record.pluginVersionId;
    const enabled = record.bypassed !== true;
    if (
      versionId === SUNO_PLUGIN_CATALOG.limiter.pluginVersionId ||
      (typeof versionId !== "string" && record.id)
    ) {
      masterChain.push({
        id: "master-limiter",
        type: "limiter",
        enabled,
        params: {
          lookahead: Number(params.lookahead) || 3,
          preGain: Number(params.preGain) || 0,
          attack: Number(params.attack) || 1,
          release: Number(params.release) || 60,
        },
      });
      continue;
    }
    if (versionId === SUNO_PLUGIN_CATALOG.eq.pluginVersionId) {
      const gain = Number(params.gain3) || 0;
      masterChain.push({
        id: "master-eq",
        type: "eq",
        enabled,
        amount: Math.max(0, Math.min(1, gain / 24 + 0.5)),
      });
      continue;
    }
    if (versionId === SUNO_PLUGIN_CATALOG.compressor.pluginVersionId) {
      const threshold = Number(params.threshold ?? -18);
      masterChain.push({
        id: "master-compressor",
        type: "compressor",
        enabled,
        amount: Math.max(0, Math.min(1, (threshold + 24) / 12)),
      });
    }
  }

  return {
    bpm,
    timeSignature: signature,
    tracks,
    lanes,
    markers: markersFromState(state.sections, bps),
    chains,
    masterChain,
  };
}

/** Short, readable suffix for ids created from a Suno id. */
function shortId(value: string): string {
  return value.replace(/-/g, "").slice(0, 10);
}

/**
 * Apply a Suno document to a local project ("Load Suno version").
 *
 * This is a merge, not a replace: tracks and clips are matched by the Suno id
 * they were pulled from (or the deterministic id their local id maps to), and
 * anything Suno does not know about — a local upload, a clip that has not been
 * uploaded yet — is kept rather than silently deleted. The caller is told what
 * was kept so the UI can explain the result.
 */
export function mergeSunoProjectIntoLocal(
  local: LocalDocument,
  suno: {
    bpm: number;
    timeSignature: string;
    tracks: LocalTrack[];
    lanes: LocalClip[];
    markers?: Array<{ id: string; time: number; label: string; color?: string }>;
    chains?: Record<string, Array<Record<string, unknown>>>;
    masterChain?: Array<Record<string, unknown>>;
  }
): { data: LocalDocument; keptLocalClips: string[]; droppedTracks: string[] } {
  const localTracks = Array.isArray(local.tracks) ? local.tracks : [];
  const localLanes = Array.isArray(local.lanes) ? local.lanes : [];
  const localTrackBySunoId = new Map<string, LocalTrack>();
  for (const track of localTracks) {
    localTrackBySunoId.set(track.sunoId ?? stableSunoId(track.id), track);
  }
  const localClipBySunoId = new Map<string, LocalClip>();
  for (const clip of localLanes) {
    localClipBySunoId.set(clip.sunoId ?? stableSunoId(clip.id), clip);
  }

  const usedTrackIds = new Set<string>();
  const usedClipIds = new Set<string>();
  const keptLocalClips: string[] = [];

  const tracks: LocalTrack[] = suno.tracks.map((track, index) => {
    const match =
      localTrackBySunoId.get(track.id) ??
      localTracks.find((candidate) => candidate.index === index && !candidate.sunoId);
    const id = match?.id ?? `track-${shortId(track.id)}`;
    usedTrackIds.add(match?.id ?? id);
    const clipIds: string[] = [];
    for (const sunoClip of suno.lanes.filter((clip) => clipIdsOf(track).includes(clip.id))) {
      const clipMatch = localClipBySunoId.get(sunoClip.id);
      const clipId = clipMatch?.id ?? `clip-${shortId(sunoClip.id)}`;
      usedClipIds.add(clipMatch?.id ?? clipId);
      clipIds.push(clipId);
      if (clipMatch) {
        clipMatch.title = sunoClip.title ?? clipMatch.title;
        clipMatch.color = sunoClip.color ?? clipMatch.color;
        clipMatch.start = sunoClip.start;
        clipMatch.duration = sunoClip.duration;
        clipMatch.midi = sunoClip.midi;
        clipMatch.sunoAssetId = sunoClip.sunoAssetId ?? clipMatch.sunoAssetId;
        clipMatch.sunoId = sunoClip.id;
      } else {
        localLanes.push({ ...sunoClip, id: clipId, sunoId: sunoClip.id });
      }
    }
    return {
      ...(match ?? {
        id,
        name: track.name ?? `Track ${index + 1}`,
        color: track.color,
        chain: [],
        index,
      }),
      sunoId: track.id,
      name: track.name ?? match?.name ?? `Track ${index + 1}`,
      color: track.color ?? match?.color,
      volume: track.volume,
      pan: track.pan,
      muted: track.muted,
      solo: track.solo,
      hidden: track.hidden,
      index,
      clipIds,
    };
  });

  // Local-only clips keep their place; drop a track only when it would be empty.
  const droppedTracks: string[] = [];
  const clipTrack = new Map<string, string>();
  for (const track of localTracks) {
    for (const clipId of track.clipIds ?? []) clipTrack.set(clipId, track.id);
  }
  for (const clip of localLanes) {
    if (usedClipIds.has(clip.id)) continue;
    keptLocalClips.push(clip.id);
    const ownerId = clipTrack.get(clip.id);
    const owner = tracks.find((track) => track.id === ownerId);
    if (owner) {
      owner.clipIds = [...new Set([...(owner.clipIds ?? []), clip.id])];
      continue;
    }
    const localOwner = localTracks.find((track) => (track.clipIds ?? []).includes(clip.id));
    if (localOwner && !usedTrackIds.has(localOwner.id)) {
      tracks.push({ ...localOwner, clipIds: [...new Set(localOwner.clipIds ?? [])] });
      usedTrackIds.add(localOwner.id);
    }
  }
  for (const track of localTracks) {
    if (!usedTrackIds.has(track.id) && (track.clipIds ?? []).length === 0) {
      droppedTracks.push(track.id);
    }
  }

  return {
    data: {
      ...local,
      tracks,
      lanes: localLanes,
      markers: suno.markers ?? local.markers,
      // Per-track merge: a Suno chain we could not fully map leaves the local
      // chain in place rather than dropping effects silently.
      chains: { ...(local.chains ?? {}), ...(suno.chains ?? {}) },
      masterChain:
        suno.masterChain && suno.masterChain.length > 0
          ? suno.masterChain
          : local.masterChain,
    },
    keptLocalClips,
    droppedTracks,
  };
}

function clipIdsOf(track: LocalTrack): string[] {
  return (track.clipIds ?? []).filter((id): id is string => typeof id === "string");
}

/** Minimal document for a brand-new Suno project (title/metadata only). */export function emptySunoState(title: string, majorVersion = 2): Record<string, unknown> {
  const id = randomUUID();
  return {
    title,
    majorVersion,
    timing: { type: "manual", bps: 2, bpsAutomation: [], lockBPS: false },
    timeSignatureChanges: [
      { startBeats: 0, subdivisionsPerBar: 4, beatsPerSubdivision: 1 },
    ],
    amplitude: 1,
    songFadeInBeats: 0,
    songFadeOutBeats: 0,
    loop: { enabled: false, startBeats: 0, endBeats: 0 },
    metronome: { enabled: false, amplitude: 1 },
    editorPointerModes: { midi: "select", audio: "select" },
    tracks: [
      {
        id,
        name: "Track 1",
        color: "#7c5cff",
        type: "audio",
        height: 88,
        mute: false,
        solo: false,
        arm: false,
        hidden: false,
        amplitude: 0.8,
        balance: 0,
        routingMode: "stereo",
        signalChain: [],
        faderAutomation: [],
        clips: [],
        takeLanes: [],
        takeLanesExpanded: false,
        clipCreationIntents: [],
      },
    ],
    selection: {
      trackIds: [id],
      focusedTrackId: id,
      noteIds: [],
      anchorBeats: 0,
      focusBeats: 0,
      contextBeforeBeats: 32,
      contextAfterBeats: 32,
      focusedArea: "timeline",
      warpMarkerSeconds: {},
    },
  };
}
