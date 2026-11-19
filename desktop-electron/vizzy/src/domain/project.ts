import * as THREE from "three";
import type { AnyNode } from "./nodes";
import type { Automation, AutomationGroup, Easing } from "./types";
import { newId } from "./types";
import { ease } from "./easing";
import type { EffectInstance } from "./effects";
import { createAnalyzer, type Analyzer } from "./analyzers";

export interface MediaAsset {
  id: string;
  name: string;
  kind: "image" | "video";
  url: string;
  width: number;
  height: number;
}

/**
 * Composition layer, as the reference stores it: a container that owns items and
 * its own effect stack. Effects attach to a layer (`effect.connections`), not to
 * the composition as a whole.
 */
export interface CompositionLayer {
  id: string;
  name: string;
  /** Ids of the items inside this layer. */
  nodeIds: string[];
  enabled: boolean;
  /** Keep the layer's rendered frame available to other layers' effects. */
  renderToBuffer: boolean;
  /** Reference layer `audioAnalyzer`; contents without their own binding inherit it. */
  audioAnalyzer?: string | null;
  /** Reference layer camera; absent means "derive from the items' dimension". */
  camera?: {
    type: "Orthographic" | "Perspective";
    fov: number;
    near: number;
    far: number;
  };
  /** Reference Layer transform (position/rotation in reference pixels/degrees). */
  transform?: {
    position: [number, number, number];
    rotation: [number, number, number];
    scale: [number, number, number];
  };
}

export interface Project {
  id: string;
  name: string;
  width: number;
  height: number;
  fps: number;
  /** Musical tempo used for the timeline beat/bar grid. */
  bpm: number;
  /** Named ruler markers. */
  markers: { id: string; time: number; name: string }[];
  duration: number;
  /** Stage clear colour, as a CSS hex string. */
  background: string;
  /** Project menu “Set creator note”. */
  creatorNote: string;
  /** Composition audio monitoring level, 0..100. */
  volume: number;
  /** Reference Audio `muted`: silences preview without losing the level. */
  muted: boolean;
  /** Reference Add-layer colour transform: brighten or darken the palette. */
  spectrumLayerColorMode: "lighten" | "darken";
  /** Strength of the Add-layer colour transform, 0..1. */
  spectrumLayerColorShift: number;
  nodes: AnyNode[];
  /** Composition layers in draw order; items may belong to one. */
  layers: CompositionLayer[];
  automations: Automation[];
  /** Reference automation folders (`automationGroups`). */
  automationGroups: AutomationGroup[];
  /**
   * Maximum audio impact over the whole track, as the reference stores it in
   * `audioImpact.max`. Audio-impact automations normalise their magnitude by it.
   */
  audioImpactMax: number;
  /** Render settings `g1`–`g5`; shader items read them as `u_g1`–`u_g5`. */
  globals: number[];
  /** Reference Audio object processing chain. */
  audioSettings: {
    bassBoost: number;
    frequency: number;
    playbackRate: number;
    attenuator: boolean;
    additionalGainDb: number;
    compressor: boolean;
  };
  assets: MediaAsset[];
  effects: EffectInstance[];
  analyzers: Analyzer[];
}

export function createProject(): Project {
  return {
    id: newId("project"),
    name: "Untitled",
    width: 1920,
    height: 1080,
    fps: 30,
    bpm: 120,
    markers: [],
    duration: 12,
    background: "#000000",
    creatorNote: "",
    volume: 100,
    muted: false,
    spectrumLayerColorMode: "lighten",
    spectrumLayerColorShift: 0.5,
    nodes: [],
    layers: [],
    automations: [],
    automationGroups: [],
    audioImpactMax: 0,
    globals: [0, 0, 0, 0, 0],
    audioSettings: {
      bassBoost: 0,
      frequency: 60,
      playbackRate: 1,
      attenuator: false,
      additionalGainDb: 0,
      compressor: false,
    },
    assets: [],
    effects: [],
    analyzers: [createAnalyzer("analyzer_default", "Default")],
  };
}

/* ------------------------------------------------------------------ */
/* Automation sampling                                                 */
/* ------------------------------------------------------------------ */

export function easing(t: number, mode: Easing): number {
  // Older saves used the coarse four-mode vocabulary; keep them working while
  // imported keyframes use the reference's full easing catalogue.
  if (mode === "hold") return 0;
  if (mode === "ease-in") return t * t;
  if (mode === "ease-out") return 1 - (1 - t) * (1 - t);
  return ease(mode, t);
}

/** Sample an automation track at an absolute project time. */
export function sampleAutomation(automation: Automation, time: number): number | null {
  const keys = automation.keyframes;
  if (keys.length === 0) return null;
  if (keys.length === 1) return keys[0].value;
  if (time <= keys[0].t) return keys[0].value;
  const last = keys[keys.length - 1];
  if (time >= last.t) return last.value;

  for (let i = 0; i < keys.length - 1; i += 1) {
    const a = keys[i];
    const b = keys[i + 1];
    if (time >= a.t && time <= b.t) {
      const span = Math.max(1e-6, b.t - a.t);
      const u = (time - a.t) / span;
      return a.value + (b.value - a.value) * easing(u, a.easing);
    }
  }
  return last.value;
}

/* ------------------------------------------------------------------ */
/* Asset loading                                                       */
/* ------------------------------------------------------------------ */

export class AssetStore {
  private textures = new Map<string, THREE.Texture>();
  private assets = new Map<string, MediaAsset>();

  addImage(name: string, url: string, width: number, height: number): MediaAsset {
    const asset: MediaAsset = { id: newId("asset"), name, kind: "image", url, width, height };
    this.assets.set(asset.id, asset);
    return asset;
  }

  addVideo(name: string, url: string, width = 0, height = 0): MediaAsset {
    const asset: MediaAsset = { id: newId("asset"), name, kind: "video", url, width, height };
    this.assets.set(asset.id, asset);
    return asset;
  }

  /** Re-register a snapshot asset without loading it yet (restore path). */
  register(asset: MediaAsset): void {
    this.assets.set(asset.id, asset);
  }

  /** Drop every record and texture, e.g. before loading another project. */
  clear(): void {
    for (const texture of this.textures.values()) texture.dispose();
    this.textures.clear();
    this.assets.clear();
  }

  async load(asset: MediaAsset): Promise<THREE.Texture> {
    const cached = this.textures.get(asset.id);
    if (cached) return cached;
    const texture = await new THREE.TextureLoader().loadAsync(asset.url);
    // Our image shaders write the sampled value straight to the framebuffer, and
    // the renderer's output stage does not encode for them. Tagging the texture
    // sRGB would decode it to linear and never re-encode, which renders every
    // photo about 2.2x too dark; the reference composites in sRGB throughout, so
    // the raw values are the faithful ones.
    texture.colorSpace = THREE.NoColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = false;
    this.textures.set(asset.id, texture);
    return texture;
  }

  get(assetId: string): THREE.Texture | null {
    return this.textures.get(assetId) ?? null;
  }

  /** Asset record (name + source URL), for thumbnails and previews. */
  record(assetId: string): MediaAsset | null {
    return this.assets.get(assetId) ?? null;
  }

  list(): MediaAsset[] {
    return [...this.assets.values()];
  }
}
