/**
 * Particle presets are plain parameter sets over a `ParticlesNode`, exactly
 * like spectrum presets are parameter sets over a spectrum. Keeping them as
 * data means they can be thumbnailed, saved, imported and diffed.
 *
 * The built-in catalogue lives in `particle-presets.json`; the thumbnails in
 * `public/particles/presets/` are rendered from this same data by
 * `scripts/export-particle-thumbs.mjs`.
 */

import builtinParticleData from "./particle-presets.json";
import type { ParticlesNode } from "./nodes";

export type ParticleFilter = "Linear" | "Nearest";

export interface ParticleParams {
  instances: number;
  sizeRange: [number, number];
  alphaRange: [number, number];
  speedRange: [number, number];
  phaseRange: [number, number];
  phaseAmplitude: [number, number];
  phaseSpeedRange: [number, number];
  timeToLiveRange: [number, number];
  /** Item offset in the reference's world (raw export `position`). */
  /** Optional framing offset; defaults to the node value (-500 on z). */
  offset?: [number, number, number];
  startPos: [number, number, number];
  endPos: [number, number, number];
  directionX: [number, number];
  directionY: [number, number];
  directionZ: [number, number];
  color: string;
  mirror: boolean;
  constantSize: boolean;
  zLimit: number;
  zLimitGrace: number;
  backLimit: number;
  backLimitGrace: number;
  impactMultiplier: number;
  smoothingTimeConstant: number;
  globalAlpha: number;
  incrementWithTime: boolean;
  timeIncrementMultiplier: number;
  enableRandomSize: boolean;
  randomSizeSpeed: number;
  enableRandomAlpha: boolean;
  randomAlphaSpeed: number;
  enableRandomRotation: boolean;
  randomRotationSpeed: number;
  fadeBeginning: boolean;
  fadeEnd: boolean;
  seed: string;
  audioAnalyzer: string;
  particleImage: string;
  magFilter: ParticleFilter;
  minFilter: ParticleFilter;
  premultiplyAlpha: boolean;
}

/**
 * Per-preset audio reaction axis. Each preset names the one thing its audio
 * response moves, so the catalogue reads as seventeen different reactions
 * rather than seventeen copies of "speed up".
 *
 * Grounding: module 1354's vertex shader already exposes the motion term
 * (`speed * orientationStart * diff`), the point size (`uPointSize`), the
 * global alpha (`u_alpha`), the sprite rotation (`vRotation`) and its own
 * `bnoise()`; module 682's Audio Impact supplies the mapping
 * (`sensitivity * hypot(bands) / maxAudioImpact`, smoothed, with the
 * `min === max` guard). See docs/particle-preset-motion.md §"Audio reaction".
 */
export type ParticleReactionTarget =
  | "speed"
  | "size"
  | "alpha"
  | "spin"
  | "spread"
  | "flicker";

/**
 * `amount` is the axis's full-impact excursion:
 * - `speed` / `size` / `spread`: a multiplier delta (0.5 = +50 % at full impact);
 * - `alpha`: how far the quiet value is dimmed (0.5 = half alpha at silence, full at peak);
 * - `spin`: radians added to the sprite rotation;
 * - `flicker`: 0..1 depth of the per-frame alpha flicker.
 */
export interface ParticleReaction {
  target: ParticleReactionTarget;
  amount: number;
  /** 0..1, the same smoother Audio Impact uses (`previous * s + (1 - s) * next`). */
  smoothing: number;
  /** Scales the band magnitude before it is normalised by the project impact. */
  sensitivity: number;
}

export interface ParticlePreset {
  id: string;
  name: string;
  category: string;
  params: ParticleParams;
  /** The preset's own audio-reaction axis. Absent = the shipped node's default. */
  audio?: ParticleReaction;
  thumb?: string;
  /** Built-ins cannot be deleted; saved presets can. */
  builtin?: boolean;
  source?: "builtin" | "user" | "import";
}

/** The node's own defaults, with a fixed seed so previews are reproducible. */
/** The reference item's default world offset (raw export `position`). */
const DEFAULT_PARTICLE_OFFSET: [number, number, number] = [0, 0, -500];

export const DEFAULT_PARTICLE_PARAMS: ParticleParams = {
  instances: 1000,
  sizeRange: [0.2, 0.6],
  alphaRange: [0, 1],
  speedRange: [1, 2],
  phaseRange: [5, 15],
  phaseAmplitude: [-10, 10],
  phaseSpeedRange: [1, 5],
  timeToLiveRange: [10, 12],
  offset: [...DEFAULT_PARTICLE_OFFSET],
  startPos: [-45, -75, -500],
  endPos: [250, 75, 500],
  directionX: [0, 5],
  directionY: [-3, 3],
  directionZ: [50, 100],
  color: "#ffffff",
  mirror: true,
  constantSize: false,
  zLimit: 5,
  zLimitGrace: 10,
  backLimit: 500,
  backLimitGrace: 10,
  impactMultiplier: 3,
  smoothingTimeConstant: 0.2,
  globalAlpha: 1,
  incrementWithTime: true,
  timeIncrementMultiplier: 0.3,
  enableRandomSize: false,
  randomSizeSpeed: 2,
  enableRandomAlpha: true,
  randomAlphaSpeed: 2,
  enableRandomRotation: false,
  randomRotationSpeed: 2,
  fadeBeginning: true,
  fadeEnd: true,
  seed: "20261114",
  audioAnalyzer: "analyzer_default",
  particleImage: "/media/particles/circle_05_alpha.webp",
  magFilter: "Linear",
  minFilter: "Linear",
  premultiplyAlpha: false,
};

/** The reference's default sprite; a preset must never leave the preview empty. */
export const DEFAULT_PARTICLE_IMAGE = "/media/particles/circle_05_alpha.webp";

const STORAGE_KEY = "studio.particle-presets.v1";

/** Built-in designs, verbatim from the JSON payload. */
export const BUILTIN_PARTICLE_PRESETS: ParticlePreset[] = (
  Array.isArray(builtinParticleData) ? (builtinParticleData as ParticlePreset[]) : []
).map((entry) => ({
  ...entry,
  builtin: true,
  source: entry.source ?? "builtin",
  params: { ...DEFAULT_PARTICLE_PARAMS, ...entry.params },
}));

export function loadUserParticlePresets(): ParticlePreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ParticlePreset[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((preset) => preset && typeof preset.id === "string" && preset.params)
      .map((preset) => ({
        ...preset,
        builtin: false,
        source: preset.source ?? "user",
        params: { ...DEFAULT_PARTICLE_PARAMS, ...preset.params },
      }));
  } catch {
    return [];
  }
}

function persist(presets: ParticlePreset[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    /* storage may be unavailable; presets stay in memory */
  }
}

function capture(params: ParticleParams): ParticleParams {
  return {
    ...params,
    sizeRange: [...params.sizeRange],
    alphaRange: [...params.alphaRange],
    speedRange: [...params.speedRange],
    phaseRange: [...params.phaseRange],
    phaseAmplitude: [...params.phaseAmplitude],
    phaseSpeedRange: [...params.phaseSpeedRange],
    timeToLiveRange: [...params.timeToLiveRange],
    offset: [...(params.offset ?? DEFAULT_PARTICLE_OFFSET)],
    startPos: [...params.startPos],
    endPos: [...params.endPos],
    directionX: [...params.directionX],
    directionY: [...params.directionY],
    directionZ: [...params.directionZ],
  };
}

/** Reads every persisted particle parameter off a node. */
export function readParticleParams(node: ParticlesNode): ParticleParams {
  return capture({
    instances: node.instances,
    sizeRange: [node.sizeRange[0], node.sizeRange[1]],
    alphaRange: [node.alphaRange[0], node.alphaRange[1]],
    speedRange: [node.speedRange[0], node.speedRange[1]],
    phaseRange: [node.phaseRange[0], node.phaseRange[1]],
    phaseAmplitude: [node.phaseAmplitude[0], node.phaseAmplitude[1]],
    phaseSpeedRange: [node.phaseSpeedRange[0], node.phaseSpeedRange[1]],
    timeToLiveRange: [node.timeToLiveRange[0], node.timeToLiveRange[1]],
    offset: [node.particleOffset.x, node.particleOffset.y, node.particleOffset.z],
    startPos: [node.startPos.x, node.startPos.y, node.startPos.z],
    endPos: [node.endPos.x, node.endPos.y, node.endPos.z],
    directionX: [node.directionX[0], node.directionX[1]],
    directionY: [node.directionY[0], node.directionY[1]],
    directionZ: [node.directionZ[0], node.directionZ[1]],
    color: node.color,
    mirror: node.mirror,
    constantSize: node.constantSize,
    zLimit: node.zLimit,
    zLimitGrace: node.zLimitGrace,
    backLimit: node.backLimit,
    backLimitGrace: node.backLimitGrace,
    impactMultiplier: node.impactMultiplier,
    smoothingTimeConstant: node.smoothingTimeConstant,
    globalAlpha: node.globalAlpha,
    incrementWithTime: node.incrementWithTime,
    timeIncrementMultiplier: node.timeIncrementMultiplier,
    enableRandomSize: node.enableRandomSize,
    randomSizeSpeed: node.randomSizeSpeed,
    enableRandomAlpha: node.enableRandomAlpha,
    randomAlphaSpeed: node.randomAlphaSpeed,
    enableRandomRotation: node.enableRandomRotation,
    randomRotationSpeed: node.randomRotationSpeed,
    fadeBeginning: node.fadeBeginning,
    fadeEnd: node.fadeEnd,
    seed: node.seed,
    audioAnalyzer: node.audioAnalyzer,
    particleImage: node.particleImage,
    magFilter: node.magFilter === "Nearest" ? "Nearest" : "Linear",
    minFilter: node.minFilter === "Nearest" ? "Nearest" : "Linear",
    premultiplyAlpha: node.premultiplyAlpha,
  });
}

/**
 * Writes every preset parameter onto the node. `rebuild()` re-seeds the
 * geometry from the preset's own seed, then re-applies the uniforms, so the
 * change is visible on the next frame rather than at the end of the current
 * particle lifetime. An empty image falls back to the reference sprite.
 */
export function applyParticlePreset(node: ParticlesNode, preset: ParticlePreset): void {
  const params = { ...DEFAULT_PARTICLE_PARAMS, ...preset.params };
  node.instances = Math.max(10, Math.min(10000, Math.round(params.instances)));
  node.sizeRange = [...params.sizeRange];
  node.alphaRange = [...params.alphaRange];
  node.speedRange = [...params.speedRange];
  node.phaseRange = [...params.phaseRange];
  node.phaseAmplitude = [...params.phaseAmplitude];
  node.phaseSpeedRange = [...params.phaseSpeedRange];
  node.timeToLiveRange = [...params.timeToLiveRange];
  const offset: [number, number, number] = params.offset ?? DEFAULT_PARTICLE_OFFSET;
  node.particleOffset.set(offset[0], offset[1], offset[2]);
  node.startPos.set(params.startPos[0], params.startPos[1], params.startPos[2]);
  node.endPos.set(params.endPos[0], params.endPos[1], params.endPos[2]);
  node.directionX = [...params.directionX];
  node.directionY = [...params.directionY];
  node.directionZ = [...params.directionZ];
  node.color = params.color;
  node.mirror = params.mirror;
  node.constantSize = params.constantSize;
  node.zLimit = params.zLimit;
  node.zLimitGrace = params.zLimitGrace;
  node.backLimit = params.backLimit;
  node.backLimitGrace = params.backLimitGrace;
  node.impactMultiplier = params.impactMultiplier;
  node.smoothingTimeConstant = params.smoothingTimeConstant;
  node.globalAlpha = params.globalAlpha;
  node.incrementWithTime = params.incrementWithTime;
  node.timeIncrementMultiplier = params.timeIncrementMultiplier;
  node.enableRandomSize = params.enableRandomSize;
  node.randomSizeSpeed = params.randomSizeSpeed;
  node.enableRandomAlpha = params.enableRandomAlpha;
  node.randomAlphaSpeed = params.randomAlphaSpeed;
  node.enableRandomRotation = params.enableRandomRotation;
  node.randomRotationSpeed = params.randomRotationSpeed;
  node.fadeBeginning = params.fadeBeginning;
  node.fadeEnd = params.fadeEnd;
  node.seed = params.seed || DEFAULT_PARTICLE_PARAMS.seed;
  node.audioAnalyzer = params.audioAnalyzer || DEFAULT_PARTICLE_PARAMS.audioAnalyzer;
  node.particleImage = params.particleImage || DEFAULT_PARTICLE_IMAGE;
  node.magFilter = params.magFilter === "Nearest" ? "Nearest" : "Linear";
  node.minFilter = params.minFilter === "Nearest" ? "Nearest" : "Linear";
  node.premultiplyAlpha = params.premultiplyAlpha;
  // Each preset owns its reaction axis; Default (no descriptor) keeps module
  // 1354's plain band-average speed push.
  node.setReaction(preset.audio ?? null);
  if (preset.id === "default") {
    // The restore preset must also put the material back on module 1354's
    // constructor uniforms. The reference only pushes zLimit/backLimit into the
    // shader when `setValue` sees a *changed* value, so the shipped node keeps
    // the material defaults (50/10/1000/10) even though its fields read
    // 5/10/500/10; clear any override a project or inspector edit left behind.
    node.limitOverrides.zLimit = false;
    node.limitOverrides.zLimitGrace = false;
    node.limitOverrides.backLimit = false;
    node.limitOverrides.backLimitGrace = false;
  }
  // The node's object mapping feeds automation reads; keep it in sync.
  node.writeNumber("particles.instances", node.instances);
  node.writeNumber("particles.impact", node.impactMultiplier);
  node.writeNumber("particles.globalAlpha", node.globalAlpha);
  node.writeNumber("particles.sizeMin", node.sizeRange[0]);
  node.writeNumber("particles.sizeMax", node.sizeRange[1]);
  node.writeNumber("particles.speed", node.timeIncrementMultiplier);
  node.rebuild();
  void node.loadTexture();
}

export function allParticlePresets(): ParticlePreset[] {
  return [...BUILTIN_PARTICLE_PRESETS, ...loadUserParticlePresets()];
}

export function saveUserParticlePreset(
  name: string,
  params: ParticleParams,
  thumb?: string,
  audio?: ParticleReaction,
): ParticlePreset[] {
  const presets = loadUserParticlePresets();
  const entry: ParticlePreset = {
    id: `user-particle-${Date.now().toString(36)}`,
    name: name || `Particle preset ${presets.length + 1}`,
    category: "Custom",
    params: capture({ ...DEFAULT_PARTICLE_PARAMS, ...params }),
    source: "user",
  };
  if (audio) entry.audio = { ...audio };
  if (thumb) entry.thumb = thumb;
  const next = [...presets, entry];
  persist(next);
  return next;
}

export function deleteUserParticlePreset(id: string): ParticlePreset[] {
  const next = loadUserParticlePresets().filter((preset) => preset.id !== id);
  persist(next);
  return next;
}

export function updateUserParticlePreset(
  id: string,
  patch: Partial<ParticlePreset>,
): ParticlePreset[] {
  const next = loadUserParticlePresets().map((preset) =>
    preset.id === id
      ? {
          ...preset,
          ...patch,
          params: patch.params
            ? capture({ ...preset.params, ...patch.params })
            : preset.params,
        }
      : preset,
  );
  persist(next);
  return next;
}

/** Accepts either an array of presets or a single preset object. */
export function parseParticlePresetFile(text: string): ParticlePreset[] {
  const parsed = JSON.parse(text) as ParticlePreset | ParticlePreset[];
  const list = Array.isArray(parsed) ? parsed : [parsed];
  return list
    .filter((preset) => preset && typeof preset.name === "string" && preset.params)
    .map((preset) => ({
      id: `import-particle-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      name: preset.name,
      category: preset.category ?? "Imported",
      params: capture({ ...DEFAULT_PARTICLE_PARAMS, ...preset.params }),
      ...(preset.audio ? { audio: { ...preset.audio } } : {}),
      source: "import" as const,
    }));
}

export function exportParticlePresets(presets: ParticlePreset[]): string {
  return JSON.stringify(
    presets.map(({ name, category, params, audio }) => ({
      name,
      category,
      params,
      ...(audio ? { audio } : {}),
    })),
    null,
    2,
  );
}
