import * as THREE from "three";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { createNoise3D } from "simplex-noise";
import {
  SPHERICAL_FRAGMENT_SHADER,
  SPHERICAL_VERTEX_SHADER,
} from "./spherical-shader";
import { DEFAULT_SHADER_ITEM_FRAGMENT } from "./shader-item-default";
import type { ParticleReaction } from "./particle-presets";
import { parseCustomPath, sampleCustomPath, type CustomPathPoint } from "./custom-path";
import type { AnimationItem } from "lottie-web";
import VizzyButterchurn from "./vizzy-butterchurn.js";
import * as butterchurnPresetsModule from "butterchurn-presets";
// Presets used by the reference templates but absent from the npm pack; extracted
// from Vizzy's own vendor chunks so template projects load their named preset.
import referenceButterchurnPresets from "./butterchurn-reference-presets.json";

const butterchurnLib: any = VizzyButterchurn;

const butterchurnPresetsLib: any =
  (butterchurnPresetsModule as any).getPresets
    ? butterchurnPresetsModule
    : (butterchurnPresetsModule as any).default?.getPresets
      ? (butterchurnPresetsModule as any).default
      : (butterchurnPresetsModule as any).default?.default ?? butterchurnPresetsModule;

import seedrandom from "seedrandom";
import {
  ContainerKind,
  NodeKind,
  PropertyKind,
  type Automation,
  type ControllerSetups,
  type Id,
  type PropertyDescriptor,
  newId,
} from "./types";
import type { SpectrumDraw, SpectrumFillStyle, SpectrumParams, SpectrumType } from "./presets";
import { createSpectrumLayer, type SpectrumColorType, type SpectrumLayer } from "./spectrum-layers";
import { REFERENCE_VALUE_SCALE } from "../audio/analyzer-bank";
import {
  SPECTRUM_VERTEX_SHADER,
  buildSpectrumFragment,
} from "./spectrum-shader";
import { SpectrumCanvasRenderer, type PathSettings } from "./spectrum-canvas";
import { spectrumPoints } from "./spectrum-path";
import { PROGRESS_BAR_SHADER } from "./progress-bar-shader";
import { LOGO_SHADER } from "./logo-shader";
import { NOISE_SOURCES } from "./noise-shaders";
import { BLEND_EQUATIONS, BLEND_FACTORS, applyBlending } from "./blending";
import { drawText } from "./text-canvas";
import { SKIA_FONT_TITLES, loadSkiaFont } from "./skia-fonts";
import { BmFontLayout, buildBmFontGeometry, parseBmFont, type BmFont } from "./bmfont-text";
import {
  ANIMATED_TEXT_FRAGMENT_SHADER,
  ANIMATED_TEXT_VERTEX_SHADER,
} from "./animated-text-shader";
import { parseLyrics, type LyricLine } from "./lyrics";
import { LYRICS_FRAGMENT_SHADER, LYRICS_VERTEX_SHADER } from "./lyrics-shader";
import { EASING_OPTIONS, ease } from "./easing";

/** Reference preset order: case-insensitive locale sort of the bundled names. */
function sortPresets(presets: Record<string, unknown>): Record<string, unknown> {
  return Object.keys(presets)
    .sort((a, b) => a.localeCompare(b, "en", { sensitivity: "base" }))
    .reduce<Record<string, unknown>>((sorted, name) => {
      sorted[name] = presets[name];
      return sorted;
    }, {});
}

export interface NodeContext {
  /** Live spectrum magnitudes, 0..1, supplied by the audio layer. */
  spectrum: () => Float32Array;
  /** Downsampled time-domain window, -1..1. */
  waveform: () => Float32Array;
  /** Time-domain window at a specific playhead, sized in samples. */
  waveformWindow?: (samples: number, time: number) => Float32Array;
  /**
   * Stereo windows `[left, right]` for items that feed separate audio channels
   * (the reference Butterchurn passes distinct L/R arrays plus their average).
   */
  waveformWindowChannels?: (samples: number, time: number) => [Float32Array, Float32Array];
  /** Audio-context sample rate; windows and periods are expressed in samples. */
  sampleRate?: () => number;
  /** Resolves a media asset id to a texture, or null while loading. */
  texture: (assetId: Id) => THREE.Texture | null;
  /**
   * Band count configured on an analyzer, or null when the id is unknown.
   * Layers bound to that analyzer sample this many bands instead of the item's.
   */
  analyzerBands?: (analyzerId: string) => number | null;
  /** Gain implied by an analyzer's output multiplier, or null when unknown. */
  analyzerGain?: (analyzerId: string) => number | null;
  /**
   * Band values for one analyzer, already shaped by its window and band count.
   * Falls back to {@link spectrum} when the analyzer is unknown.
   */
  spectrumFor?: (analyzerId: string) => Float32Array | null;
  /**
   * Native-length (`sampleOutCount`) band series for the spectrum path. The
   * reference draws one radial segment per configured band; `spectrumFor`
   * returns the shader's fixed 256 slots instead.
   */
  spectrumBandsFor?: (analyzerId: string) => Float32Array | null;
  /**
   * The project's permanent Default analyzer id. The reference binds a spectrum
   * layer without its own `audioAnalyzer` to this analyzer, so it is the item's
   * fallback series instead of the shared {@link spectrum} one.
   */
  defaultAnalyzerId?: () => string | null;
  /**
   * The project's audio-impact normaliser (`project.audioImpactMax`). Module
   * 682 divides `sensitivity * hypot(bands)` by it before mapping onto the
   * output range; without it (`0`) the mapping stays at its minimum.
   */
  maxAudioImpact?: () => number;
  /**
   * Single-analyser analysis for offline scans (the audio-impact maximum): the
   * same `_analyse` call, without recomputing every other open analyser.
   */
  spectrumScanFor?: (analyzerId: string) => Float32Array | null;
  /** Drawing-buffer size in pixels, for shaders that work in fragment coordinates. */
  resolution?: () => { x: number; y: number };
  /** Composition duration in seconds, used by text variables. */
  projectDuration?: () => number;
  /** Composition name, used by `{{project_name}}`. */
  projectName?: () => string;
  /** Render-settings global variable (`g1`–`g5`), zero-based index. */
  globalVar?: (index: number) => number;
  /** Active audio file name, used by `{{audio_name}}`. */
  audioName?: () => string;
  /** Finished texture of a render-to-buffer layer, for shader items. */
  layerTexture?: (layerId: string) => THREE.Texture | null;
  /**
   * Whether the node's composition layer draws through the 2-unit
   * orthographic camera. Items authored in the reference's 1000-unit stage
   * (Shader Item) map with `2/1000` only on an orthographic layer; a
   * perspective layer projects the same 1000 units through its fov.
   */
  orthographicLayer?: (nodeId: Id) => boolean;
  /** Whether the timeline is currently playing (video playback vs. scrubbing). */
  playing?: () => boolean;
}

/**
 * Base class for everything that appears on the timeline.
 *
 * Two ideas do most of the work:
 *  - `objectMapping` keeps an explicit map of animatable property ids to values
 *    so automation can address them by path without reflection.
 *  - `createControllerSetups()` derives the inspector tree from the node itself,
 *    so a new node type needs no inspector changes.
 */
/** Shared inspector-row options recovered from reference controller `extraInfo`. */
type FieldMeta = { tooltip?: string; constraint?: () => boolean };

export abstract class SceneNode {
  readonly id: Id = newId("node");
  abstract readonly kind: NodeKind;
  abstract readonly typeLabel: string;
  name: string;
  start = 0;
  duration = 10;
  visible = true;
  /** Draw-order/depth value; the timeline row is a separate field. */
  z = 0;
  /** Reference `rowIndex`: clips on the same row share a timeline lane. */
  trackRow = 0;
  /** Solo isolates this object: everything not soloed is hidden while any solo is set. */
  solo = false;
  /** Shy objects stay in the composition; Ctrl+H toggles hiding them. */
  shy = false;
  /** When true the object renders at every time, ignoring its start/duration span. */
  ignoreTimeSpan = false;
  /**
   * Display mirror of the analyzer that drives this item. Ownership lives on
   * `Analyzer.users`; write through the binding helper so the two never drift.
   */
  analyzerId: string | null = null;

  /** Whether this item uses the perspective layer camera. */
  readonly is3D: boolean = false;

  /** Animatable numeric properties, addressable by path. */
  readonly objectMapping = new Map<string, number>();
  /** Meshes this node contributes to the scene. */
  readonly group = new THREE.Group();

  protected ctx: NodeContext;

  constructor(name: string, ctx: NodeContext) {
    this.name = name;
    this.ctx = ctx;
    this.group.name = name;
  }

  /** Subclasses declare their animatable state here. */
  protected abstract initializeObjectMapping(): void;

  /** Subclasses build their meshes here. */
  protected abstract build(): void;

  /** Applies current property values to the meshes. */
  abstract sync(_time: number): void;

  createControllerSetups(): ControllerSetups {
    return { containers: [], controllers: [] };
  }

  /** Numeric read used by automation and by slider defaults. */
  readNumber(path: string): number {
    return this.objectMapping.get(path) ?? 0;
  }

  /** Numeric write used by automation. */
  writeNumber(path: string, value: number): void {
    this.objectMapping.set(path, value);
  }

  /* ------------------------------------------------------------------ */
  /* Editor transform gizmo                                              */
  /* ------------------------------------------------------------------ */

  private gizmoBase: {
    position: THREE.Vector3;
    rotation: THREE.Euler;
    scale: THREE.Vector3;
    mapping: Map<string, number>;
  } | null = null;

  /** Records the state the gizmo starts from, so edits apply as deltas. */
  captureGizmoBase(): void {
    const mapping = new Map<string, number>();
    for (const key of [
      "transform.x",
      "transform.y",
      "transform.z",
      "transform.rotX",
      "transform.rotY",
      "transform.rotZ",
      "transform.scaleX",
      "transform.scaleY",
      "transform.scaleZ",
    ]) {
      if (this.objectMapping.has(key)) mapping.set(key, this.readNumber(key));
    }
    this.gizmoBase = {
      position: this.group.position.clone(),
      rotation: this.group.rotation.clone(),
      scale: this.group.scale.clone(),
      mapping,
    };
  }

  /** Writes the gizmo's delta back into the node's transform mapping. */
  applyGizmoDelta(): void {
    const base = this.gizmoBase;
    if (!base) return;
    const dx = this.group.position.x - base.position.x;
    const dy = this.group.position.y - base.position.y;
    const dz = this.group.position.z - base.position.z;
    const rotX = ((this.group.rotation.x - base.rotation.x) * 180) / Math.PI;
    const rotY = ((this.group.rotation.y - base.rotation.y) * 180) / Math.PI;
    const rotZ = ((this.group.rotation.z - base.rotation.z) * 180) / Math.PI;
    const sx = this.group.scale.x / (base.scale.x || 1);
    const sy = this.group.scale.y / (base.scale.y || 1);
    const sz = this.group.scale.z / (base.scale.z || 1);
    const write = (key: string, value: number): void => {
      if (base.mapping.has(key)) this.objectMapping.set(key, value);
    };
    write("transform.x", (base.mapping.get("transform.x") ?? 0) + dx);
    write("transform.y", (base.mapping.get("transform.y") ?? 0) + dy);
    write("transform.z", (base.mapping.get("transform.z") ?? 0) + dz);
    write("transform.rotX", (base.mapping.get("transform.rotX") ?? 0) + rotX);
    write("transform.rotY", (base.mapping.get("transform.rotY") ?? 0) + rotY);
    write("transform.rotZ", (base.mapping.get("transform.rotZ") ?? 0) + rotZ);
    write("transform.scaleX", (base.mapping.get("transform.scaleX") ?? 100) * sx);
    write("transform.scaleY", (base.mapping.get("transform.scaleY") ?? 100) * sy);
    write("transform.scaleZ", (base.mapping.get("transform.scaleZ") ?? 100) * sz);
  }

  /** Keyframeable property ids for this node. */
  animatablePaths(): string[] {
    return [...this.objectMapping.keys()];
  }

  protected addFolder(id: string, label: string, parentId?: string): void {
    void id;
    void label;
    void parentId;
  }

  protected slider(
    id: string,
    label: string,
    options: FieldMeta & {
      parentId?: string;
      min?: number;
      max?: number;
      step?: number;
      unit?: string;
      get: () => number;
      set: (v: number) => void;
    },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.Slider,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      min: options.min,
      max: options.max,
      step: options.step ?? 0.01,
      unit: options.unit,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: true,
      read: () => options.get(),
      write: (v) => options.set(Number(v)),
    };
  }

  protected toggle(
    id: string,
    label: string,
    options: FieldMeta & { parentId?: string; get: () => boolean; set: (v: boolean) => void },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.Boolean,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(Boolean(v)),
    };
  }

  protected fileField(
    id: string,
    label: string,
    options: { parentId?: string; get: () => string; set: (v: string) => void },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.File,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }

  protected colorField(
    id: string,
    label: string,
    options: FieldMeta & { parentId?: string; get: () => string; set: (v: string) => void },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.Color,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }

  protected text(
    id: string,
    label: string,
    options: FieldMeta & { parentId?: string; get: () => string; set: (v: string) => void },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.Text,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }

  protected choose(
    id: string,
    label: string,
    options: FieldMeta & {
      parentId?: string;
      values: readonly string[];
      get: () => string;
      set: (v: string) => void;
    },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.Select,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      options: options.values,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }

  protected imageGrid(
    id: string,
    label: string,
    options: FieldMeta & {
      parentId?: string;
      values: readonly string[];
      get: () => string;
      set: (v: string) => void;
    },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.ImageGrid,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      options: options.values,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }

  /** The reference's `AUDIO_ANALYZER` control: a select over project analyzers. */
  protected analyzerSelect(
    id: string,
    label: string,
    options: FieldMeta & { parentId?: string; get: () => string; set: (v: string) => void },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.Analyzer,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }

  /** The reference's `CUSTOM_PATH` row editor (serialized path string). */
  protected customPathField(
    id: string,
    label: string,
    options: FieldMeta & { parentId?: string; get: () => string; set: (v: string) => void },
  ): PropertyDescriptor {
    return {
      id,
      label,
      kind: PropertyKind.CustomPath,
      container: ContainerKind.Controller,
      parentId: options.parentId,
      tooltip: options.tooltip,
      constraint: options.constraint,
      animatable: false,
      read: () => options.get(),
      write: (v) => options.set(String(v)),
    };
  }
}

/**
 * A control the reference exposes but we cannot back yet: it renders in the same
 * position, with the same label and control type, and is disabled.
 */
const notImplemented = (controller: PropertyDescriptor): PropertyDescriptor => {
  controller.disabled = true;
  return controller;
};

/**
 * Reference items live in a ~1000-unit world (a 1024 plane fills the frame).
 * Our stage is ~2 units tall, so reference geometry and positions scale by this.
 */
const REFERENCE_SCALE = 1 / 512;

export class LayerNode extends SceneNode {
  readonly kind = NodeKind.Layer;
  readonly typeLabel = "Layer";

  color = "#4cc9f0";
  /** Composition layer id this inspector view represents. */
  compositionLayerId: string | null = null;
  /** Reference layer `audioAnalyzer` controller, shared by the layer's items. */
  audioAnalyzer: string | null = null;
  /** Mirrors the composition layer's render-to-buffer flag when inspected. */
  onRenderToBufferChange: ((value: boolean) => void) | null = null;
  /** Mirrors the composition layer's camera settings when inspected. */
  onCameraChange: (() => void) | null = null;
  cameraType: "Orthographic" | "Perspective" = "Orthographic";
  cameraFov = 45;
  cameraNear = 1;
  cameraFar = 100000;
  private mesh!: THREE.Mesh;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("behaviour.opacity", 100);
    this.objectMapping.set("behaviour.scale", 100);
    this.objectMapping.set("behaviour.rotation", 0);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
    this.objectMapping.set("basics.shy", 0);
    this.objectMapping.set("rendering.cameraType", 0);
    this.objectMapping.set("rendering.fov", 50);
    this.objectMapping.set("rendering.near", 0.1);
    this.objectMapping.set("rendering.far", 1000);
    this.objectMapping.set("rendering.renderToBuffer", 0);
  }

  protected build(): void {
    const geometry = new THREE.PlaneGeometry(3.6, 2.05, 1, 1);
    const material = new THREE.MeshBasicMaterial({
      color: new THREE.Color(this.color),
      transparent: true,
      opacity: this.readNumber("behaviour.opacity") / 100,
    });
    this.mesh = new THREE.Mesh(geometry, material);
    this.group.add(this.mesh);
  }

  sync(_time: number): void {
    const material = this.mesh.material as THREE.MeshBasicMaterial;
    material.color.set(this.color);
    const opacity = this.readNumber("behaviour.opacity") / 100;
    material.opacity = opacity;
    material.visible = this.visible && opacity > 0.001;

    const scale = this.readNumber("behaviour.scale") / 100;
    const sx = (this.readNumber("transform.scaleX") / 100) * scale;
    const sy = (this.readNumber("transform.scaleY") / 100) * scale;
    const sz = (this.readNumber("transform.scaleZ") / 100) * scale;
    this.mesh.scale.set(sx, sy, sz);
    this.mesh.rotation.set(
      THREE.MathUtils.degToRad(this.readNumber("transform.rotX")),
      THREE.MathUtils.degToRad(this.readNumber("transform.rotY")),
      THREE.MathUtils.degToRad(
        this.readNumber("behaviour.rotation") + this.readNumber("transform.rotZ"),
      ),
    );
    this.mesh.position.set(
      this.readNumber("transform.x") / 100,
      this.readNumber("transform.y") / 100,
      this.z + this.readNumber("transform.z") / 100,
    );
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "rendering", label: "Rendering", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
        { id: "basics", label: "Basics", kind: ContainerKind.Folder },
        { id: "effects", label: "Effects", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.choose("rendering.cameraType", "Camera type", {
          parentId: "rendering",
          values: ["Orthographic", "Perspective"],
          get: () => this.cameraType,
          set: (v) => {
            this.cameraType = v === "Perspective" ? "Perspective" : "Orthographic";
            this.onCameraChange?.();
          },
        }),
        this.slider("rendering.fov", "FOV", {
          parentId: "rendering",
          min: 10,
          max: 120,
          step: 1,
          unit: "°",
          get: () => this.cameraFov,
          set: (v) => {
            this.cameraFov = v;
            this.onCameraChange?.();
          },
        }),
        this.slider("rendering.near", "Near plane", {
          parentId: "rendering",
          min: 0.01,
          max: 10,
          step: 0.01,
          get: () => this.cameraNear,
          set: (v) => {
            this.cameraNear = v;
            this.onCameraChange?.();
          },
        }),
        this.slider("rendering.far", "Far plane", {
          parentId: "rendering",
          min: 10,
          max: 100000,
          step: 10,
          get: () => this.cameraFar,
          set: (v) => {
            this.cameraFar = v;
            this.onCameraChange?.();
          },
        }),
        this.toggle("rendering.renderToBuffer", "Render to buffer", {
          parentId: "rendering",
          get: () => this.readNumber("rendering.renderToBuffer") > 0.5,
          set: (v) => {
            this.objectMapping.set("rendering.renderToBuffer", v ? 1 : 0);
            this.onRenderToBufferChange?.(v);
          },
        }),

        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.rotX", "Rotation X", {
          parentId: "transform",
          min: -360,
          max: 360,
          step: 1,
          unit: "°",
          get: () => this.readNumber("transform.rotX"),
          set: (v) => this.objectMapping.set("transform.rotX", v),
        }),
        this.slider("transform.rotY", "Rotation Y", {
          parentId: "transform",
          min: -360,
          max: 360,
          step: 1,
          unit: "°",
          get: () => this.readNumber("transform.rotY"),
          set: (v) => this.objectMapping.set("transform.rotY", v),
        }),
        this.slider("behaviour.rotation", "Rotation Z", {
          parentId: "transform",
          min: -360,
          max: 360,
          step: 1,
          unit: "°",
          get: () => this.readNumber("behaviour.rotation"),
          set: (v) => this.objectMapping.set("behaviour.rotation", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
        this.slider("transform.scaleZ", "Scale Z", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("transform.scaleZ"),
          set: (v) => this.objectMapping.set("transform.scaleZ", v),
        }),

        this.choose("basics.objectType", "Object type", {
          parentId: "basics",
          values: [this.typeLabel],
          get: () => this.typeLabel,
          set: () => void 0,
        }),
        this.text("basics.name", "Name", {
          parentId: "basics",
          get: () => this.name,
          set: (v) => {
            this.name = v;
            this.group.name = v;
          },
        }),
        this.slider("basics.start", "Time", {
          parentId: "basics",
          min: 0,
          max: 120,
          step: 0.01,
          unit: "s",
          get: () => this.start,
          set: (v) => {
            this.start = v;
          },
        }),
        this.toggle("basics.ignoreTimeSpan", "Ignore time span", {
          parentId: "basics",
          get: () => this.ignoreTimeSpan,
          set: (v) => {
            this.ignoreTimeSpan = v;
          },
        }),
        this.slider("basics.trackRow", "Track row", {
          parentId: "basics",
          min: 0,
          max: 8,
          step: 1,
          get: () => this.trackRow,
          set: (v) => {
            this.trackRow = Math.max(0, Math.round(v));
          },
        }),
        this.toggle("basics.shy", "Shy", {
          parentId: "basics",
          get: () => this.shy,
          set: (v) => {
            this.shy = v;
          },
        }),
        this.toggle("basics.enabled", "Enabled", {
          parentId: "basics",
          get: () => this.visible,
          set: (v) => {
            this.visible = v;
          },
        }),

        notImplemented(
          this.choose("effects.choose", "Choose effect", {
            parentId: "effects",
            values: ["Choose effect"],
            get: () => "Choose effect",
            set: () => void 0,
          }),
        ),
      ],
    };
  }
}

/* ------------------------------------------------------------------ */
/* Media — an image texture with mirror / vignette / brightness.       */
/* ------------------------------------------------------------------ */

export class MediaNode extends SceneNode {
  readonly kind = NodeKind.Media;
  readonly typeLabel = "Media";

  assetId: Id | null = null;
  imageUrl: string | null = null;
  /** Reference `useLayerTexture`: render another layer's finished frame. */
  useLayerAsImage = false;
  layerSource = "";
  mirrorType = "None";
  audioAnalyzer = "analyzer_default";
  vignette = 0;
  brightness = 1;
  tint = "#ffffff";
  /** Shipped Media shader inputs: `gl_FragColor = pixel * colorMult + colorAdd`. */
  colorMult = { r: 1, g: 1, b: 1, a: 1 };
  colorAdd = { r: 0, g: 0, b: 0, a: 0 };
  /** Reference `brightnessMultiplier`; only scales the audio vignette amount. */
  brightnessMultiplier = 0.2;
  private urlTexture: THREE.Texture | null = null;
  private urlPending: string | null = null;
  private mesh!: THREE.Mesh;
  private material!: THREE.ShaderMaterial;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("behaviour.opacity", 100);
    this.objectMapping.set("behaviour.scale", 100);
    this.objectMapping.set("effects.vignette", 0);
    this.objectMapping.set("effects.brightnessMultiplier", 0.2);
    this.objectMapping.set("effects.brightness", 1);
    this.objectMapping.set("channel.fitToScreen", 1);
    this.objectMapping.set("channel.useLayerAsImage", 0);
    this.objectMapping.set("basics.autoBackground", 1);
    this.objectMapping.set("basics.autoCoverArt", 0);
    // Reference Transform surface: Position / Rotation / Scale on three axes.
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.material = new THREE.ShaderMaterial({
      transparent: true,
      uniforms: {
        uMap: { value: null },
        uOpacity: { value: 1 },
        uVignette: { value: 0 },
        uBrightness: { value: 1 },
        uColorMult: { value: new THREE.Vector4(1, 1, 1, 1) },
        uColorAdd: { value: new THREE.Vector4(0, 0, 0, 0) },
        uMirror: { value: 0 },
        uHasMap: { value: 0 },
        uTint: { value: new THREE.Color(1, 1, 1) },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform sampler2D uMap;
        uniform float uOpacity;
        uniform float uVignette;
        uniform float uMirror;
        uniform float uHasMap;
        uniform vec4 uColorMult;
        uniform vec4 uColorAdd;
        varying vec2 vUv;

        vec3 fallback(vec2 uv) {
          // Procedural stand-in so the node is visible before a file is loaded.
          vec3 a = vec3(0.10, 0.12, 0.18);
          vec3 b = vec3(0.32, 0.20, 0.46);
          float g = smoothstep(0.0, 1.0, uv.y * 0.7 + uv.x * 0.3);
          return mix(a, b, g);
        }

        // Derive the uv transform for the mirror modes. Measured against the
        // reference with a square ramp and fit-to-screen off (2026-10-27).
        vec2 mirrored(vec2 uv) {
          float x = uv.x;
          float fold = x < 0.5 ? x : 1.0 - x;
          float t = x;
          if (uMirror < 0.5)         t = min(2.0 * x, 2.0 - 2.0 * x); // Whole image
          else if (uMirror < 1.5)    t = fold;                        // Left half
          else if (uMirror < 2.5)    t = x < 0.5 ? 1.0 - x : x;       // Right half
          else if (uMirror < 3.5)    t = 0.25 + fold;                 // Left center
          else if (uMirror < 4.5)    t = 0.75 - fold;                 // Right center
          return vec2(t, uv.y);
        }

        void main() {
          vec2 uv = mirrored(vUv);
          vec4 pixel = uHasMap > 0.5 ? texture2D(uMap, uv) : vec4(fallback(uv), 1.0);
          // Shipped Media shader: vig_amt = vignetteAmt * length(centre - vUv);
          // then the whole vec4 is reduced by it. The vignette is radial, so the
          // centre keeps its brightness and only the edges darken.
          float vig = uVignette * length(vec2(0.5) - vUv);
          if (pixel.a > 0.0) pixel -= vec4(vig);
          vec4 result = pixel * uColorMult + uColorAdd;
          gl_FragColor = vec4(result.rgb, uOpacity * clamp(result.a, 0.0, 1.0));
        }
      `,
    });
    // Reference Media is the 1000-unit plane of the 1000-unit stage height, so
    // a fitted 16:9 texture spans exactly `2 * aspect` by 2 world units (one
    // frame height). A 2.05 plane magnified every render-layer quad 3%.
    const geometry = new THREE.PlaneGeometry(2, 2, 1, 1);
    this.mesh = new THREE.Mesh(geometry, this.material);
    this.group.add(this.mesh);
  }

  setMirrorMode(mode: string): void {
    this.mirrorType = mode;
  }

  sync(_time: number): void {
    let map: THREE.Texture | null = null;
    // An Image item can display another layer's rendered buffer instead of a
    // file; several Cubiq templates composite whole layers this way.
    if (this.useLayerAsImage && this.layerSource) {
      map = this.ctx.layerTexture?.(this.layerSource) ?? null;
    }
    if (!map) map = this.assetId ? this.ctx.texture(this.assetId) : null;

    // Remote link source: load once per URL, then reuse the texture.
    if (!map && this.imageUrl) {
      if (this.urlPending !== this.imageUrl) {
        this.urlPending = this.imageUrl;
        this.urlTexture = null;
        new THREE.TextureLoader().load(
          this.imageUrl,
          (loaded) => {
            loaded.colorSpace = THREE.NoColorSpace;
            this.urlTexture = loaded;
          },
          undefined,
          () => {
            this.urlTexture = null;
          },
        );
      } else if (this.urlTexture) {
        map = this.urlTexture;
      }
    }

    this.material.uniforms.uMap.value = map;
    this.material.uniforms.uHasMap.value = map ? 1 : 0;
    this.material.uniforms.uOpacity.value = (this.readNumber("behaviour.opacity") / 100) * (this.visible ? 1 : 0);
    // Shipped Media.update: the vignette reacts to the analyzer's first 100
    // bands, scaled by "Audio Brightness" - and only when a vignette is set.
    // Without the guard a zero vignette went negative under audio and brightened
    // the frame's corners instead of doing nothing.
    const analyzer = this.analyzerId ?? this.audioAnalyzer;
    const bands = analyzer ? this.ctx.spectrumFor?.(analyzer) ?? null : null;
    let average = 0;
    if (bands && bands.length > 0) {
      const count = Math.min(100, bands.length);
      let sum = 0;
      for (let index = 0; index < count; index += 1) sum += bands[index] * 200;
      average = sum / (6000 * count);
    }
    const vignette = this.readNumber("effects.vignette") / 100;
    this.material.uniforms.uVignette.value =
      vignette > 0 ? vignette - average * this.readNumber("effects.brightnessMultiplier") : 0;
    const mult = this.material.uniforms.uColorMult.value as THREE.Vector4;
    const add = this.material.uniforms.uColorAdd.value as THREE.Vector4;
    mult.set(this.colorMult.r, this.colorMult.g, this.colorMult.b, this.colorMult.a);
    add.set(this.colorAdd.r, this.colorAdd.g, this.colorAdd.b, this.colorAdd.a);
    this.material.uniforms.uMirror.value = Math.max(0, ["Whole image", "Left half", "Right half", "Left center", "Right center", "None"].indexOf(this.mirrorType));
    const scale = this.readNumber("behaviour.scale") / 100;
    const sx = (this.readNumber("transform.scaleX") / 100) * scale;
    const sy = (this.readNumber("transform.scaleY") / 100) * scale;
    const sz = (this.readNumber("transform.scaleZ") / 100) * scale;

    // Shipped Image `setScaling`:
    //   o = fitToScreen ? canvasAspect / imageAspect : 1
    //   mesh.scale = (x * o * imageAspect, y * o, z)
    // The 1000-unit plane is the same stage as the reference camera.
    const image = (map?.image ?? null) as { width?: number; height?: number } | null;
    const texAspect = image?.width && image?.height ? image.width / image.height : 1;
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const frameAspect = resolution.x / Math.max(1, resolution.y);
    const fit =
      this.readNumber("channel.fitToScreen") > 0.5 ? frameAspect / texAspect : 1;

    // Layer and image positions are the reference's 1000-unit stage. The
    // shipped `positionChanged` calls its coordinate helper
    // `f(x, y, true)`, which keeps the position's pixel size independent of
    // orientation: in a landscape frame x is multiplied by the aspect and y is
    // not (portrait is the reverse). Using one factor for both compressed
    // every off-centre item toward the middle (`record-label-004`'s cover sat
    // at x=544 instead of x=221).
    const unit = 2 / 1000;
    const landscape = frameAspect > 1;
    const unitX = unit * (landscape ? frameAspect : 1);
    const unitY = unit * (landscape ? 1 : frameAspect);
    // A render-layer quad reproduces another layer's frame one-to-one, so it
    // keeps the reference's own depth (`transform.z`, normally 0) instead of the
    // paint-order offset `syncNodeOrder` gives every node. In a perspective
    // layer that offset is a real distance change: `music-player-list`'s cards
    // sat 0.32-0.46 units in front of a camera at 2.4 and drew 1.25x too large.
    const baseZ = this.useLayerAsImage ? 0 : this.z;
    this.mesh.position.set(
      this.readNumber("transform.x") * unitX,
      this.readNumber("transform.y") * unitY,
      baseZ + this.readNumber("transform.z") * unit,
    );
    // Coplanar render-layer quads (`music-player-list`'s p1..p5 compositors)
    // must all blend in draw order; writing depth made only the first survive.
    this.material.depthWrite = !this.useLayerAsImage;
    this.mesh.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.mesh.scale.set(sx * fit * texAspect, sy * fit, sz);
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        // Section names and control order mirror the reference's Image inspector.
        { id: "behaviour", label: "Appearance", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
        { id: "effects", label: "Basics", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.fileField("channel.imageFile", "File", {
          parentId: "behaviour",
          get: () => this.assetId ?? "",
          set: (v) => {
            this.assetId = v || null;
          },
        }),
        this.text("channel.imageLink", "Link", {
          parentId: "behaviour",
          get: () => this.imageUrl ?? "",
          set: (v) => {
            this.imageUrl = v.trim() || null;
          },
        }),
        this.fileField("channel.imageUpload", "Upload", {
          parentId: "behaviour",
          get: () => this.assetId ?? "",
          set: (v) => {
            this.assetId = v || null;
          },
        }),
        this.toggle("channel.useLayerAsImage", "Use layer as image", {
          parentId: "behaviour",
          get: () => this.useLayerAsImage,
          set: (v) => {
            this.useLayerAsImage = v;
          },
        }),
        this.choose("effects.mirror", "Mirror", {
          parentId: "behaviour",
          // Reference order and values, measured 2026-10-27.
          values: ["Whole image", "Left half", "Right half", "Left center", "Right center", "None"],
          get: () => this.mirrorType,
          set: (v) => this.setMirrorMode(v),
        }),
        this.slider("effects.vignette", "Vignette", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          unit: "%",
          get: () => this.readNumber("effects.vignette"),
          set: (v) => this.objectMapping.set("effects.vignette", v),
        }),
        // Reference "Audio Brightness": decreases the vignette while the audio
        // is loud, i.e. the background image's audio reaction. Same range and
        // step as the shipped controller (0..100, 0.1) because the value is a
        // multiplier on the analyzer average, not a percentage.
        this.slider("effects.brightnessMultiplier", "Audio Brightness", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          step: 0.1,
          get: () => this.readNumber("effects.brightnessMultiplier"),
          set: (v) => this.objectMapping.set("effects.brightnessMultiplier", v),
        }),
        this.toggle("channel.fitToScreen", "Fit to screen", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.fitToScreen") > 0.5,
          set: (v) => this.objectMapping.set("channel.fitToScreen", v ? 1 : 0),
        }),
        this.colorField("channel.tint", "Color", {
          parentId: "behaviour",
          get: () => this.tint,
          set: (v) => {
            this.tint = v;
            const raw = v.replace(/^#/, "");
            if (/^[0-9a-f]{6}$/i.test(raw)) {
              this.colorMult.r = Number.parseInt(raw.slice(0, 2), 16) / 255;
              this.colorMult.g = Number.parseInt(raw.slice(2, 4), 16) / 255;
              this.colorMult.b = Number.parseInt(raw.slice(4, 6), 16) / 255;
            }
          },
        }),
        // Ours alone: the reference has Use layer as image, Audio analyzer and
        // Fit to screen here instead, and no opacity/scale/brightness controls.
        this.slider("behaviour.opacity", "Opacity", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          unit: "%",
          get: () => this.readNumber("behaviour.opacity"),
          set: (v) => this.objectMapping.set("behaviour.opacity", v),
        }),
        this.slider("behaviour.scale", "Scale", {
          parentId: "behaviour",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("behaviour.scale"),
          set: (v) => this.objectMapping.set("behaviour.scale", v),
        }),
        this.slider("effects.brightness", "Brightness", {
          parentId: "behaviour",
          min: 0,
          max: 3,
          step: 0.01,
          get: () => this.readNumber("effects.brightness"),
          set: (v) => this.objectMapping.set("effects.brightness", v),
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.rotX", "Rotation X", {
          parentId: "transform",
          min: -180,
          max: 180,
          step: 1,
          unit: "°",
          get: () => this.readNumber("transform.rotX"),
          set: (v) => this.objectMapping.set("transform.rotX", v),
        }),
        this.slider("transform.rotY", "Rotation Y", {
          parentId: "transform",
          min: -180,
          max: 180,
          step: 1,
          unit: "°",
          get: () => this.readNumber("transform.rotY"),
          set: (v) => this.objectMapping.set("transform.rotY", v),
        }),
        this.slider("transform.rotZ", "Rotation Z", {
          parentId: "transform",
          min: -180,
          max: 180,
          step: 1,
          unit: "°",
          get: () => this.readNumber("transform.rotZ"),
          set: (v) => this.objectMapping.set("transform.rotZ", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
        this.slider("transform.scaleZ", "Scale Z", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("transform.scaleZ"),
          set: (v) => this.objectMapping.set("transform.scaleZ", v),
        }),
        this.choose("basics.objectType", "Object type", {
          parentId: "effects",
          values: ["Image"],
          get: () => "Image",
          set: () => void 0,
        }),
        this.text("basics.name", "Name", {
          parentId: "effects",
          get: () => this.name,
          set: (v) => {
            this.name = v;
            this.group.name = v;
          },
        }),
        this.slider("basics.start", "Time", {
          parentId: "effects",
          min: 0,
          max: 120,
          step: 0.01,
          unit: "s",
          get: () => this.start,
          set: (v) => {
            this.start = v;
          },
        }),
        this.toggle("basics.ignoreTimeSpan", "Ignore time span", {
          parentId: "effects",
          get: () => this.ignoreTimeSpan,
          set: (v) => {
            this.ignoreTimeSpan = v;
          },
        }),
        this.slider("basics.trackRow", "Track row", {
          parentId: "effects",
          min: 0,
          max: 8,
          step: 1,
          get: () => this.trackRow,
          set: (v) => {
            this.trackRow = Math.max(0, Math.round(v));
          },
        }),
        this.toggle("basics.autoBackground", "Auto Background", {
          parentId: "effects",
          get: () => this.readNumber("basics.autoBackground") > 0.5,
          set: (v) => this.objectMapping.set("basics.autoBackground", v ? 1 : 0),
        }),
        notImplemented(
          this.toggle("basics.autoCoverArt", "Auto Cover Art", {
            parentId: "effects",
            get: () => this.readNumber("basics.autoCoverArt") > 0.5,
            set: (v) => this.objectMapping.set("basics.autoCoverArt", v ? 1 : 0),
          }),
        ),
      ],
    };
  }
}

/* ------------------------------------------------------------------ */
/* Particles - the reference's instanced particle field.               */
/* ------------------------------------------------------------------ */

/**
 * Ported from the reference's Particles item (module 1354). Instances are laid
 * out with `seedrandom(seed + index + salt).double()`, animated in the vertex
 * shader from a per-instance start time and lifetime, and driven by the
 * cumulative audio impact.
 *
 * The reference stores particle coordinates in degrees and converts them with
 * `x * Math.PI / 180`; its item mesh is then scaled by `scale + 34` (35 at the
 * default scale of 1), which is what puts the field hundreds of units away.
 */
const PARTICLE_DEG = Math.PI / 180;

export const PARTICLE_IMAGES = [
  { label: "Particle 1", url: "/media/particles/particle1.webp" },
  { label: "Star", url: "/media/particles/star_particle.webp" },
  { label: "Moon", url: "/media/particles/circle_05_alpha.webp" },
  { label: "Flame", url: "/media/particles/flame_01.webp" },
  { label: "Smoke", url: "/media/particles/smoke_07.webp" },
  { label: "Slash", url: "/media/particles/slash_02.webp" },
  { label: "Square", url: "/media/particles/square.webp" },
  { label: "Circle", url: "/media/particles/circle.webp" },
];

const PARTICLE_VERTEX_SHADER = /* glsl */ `
  precision highp float;
  uniform mat4 modelViewMatrix;
  uniform mat4 projectionMatrix;

  attribute float startTime;
  attribute float timeToLive;
  attribute vec3 position;
  attribute float speed;
  attribute float phaseSpeed;
  attribute float inSize;
  attribute float inAlpha;
  attribute vec4 phase;
  attribute vec4 color;
  attribute vec3 orientationStart;

  uniform float time;
  uniform float realTime;
  uniform float uPointSize;
  uniform float zLimit;
  uniform float zLimitGrace;
  uniform float backLimit;
  uniform float backLimitGrace;

  uniform bool enableRandomSize;
  uniform float randomSizeSpeed;
  uniform bool enableRandomAlpha;
  uniform float randomAlphaSpeed;
  uniform bool enableRandomRotation;
  uniform float randomRotationSpeed;

  uniform bool constantSize;

  // Preset audio reaction (q29). The reference's own formula is the linear
  // speed * orientationStart * diff term; uSpread scales that term for a
  // radial gust, uSpin offsets the sprite rotation the fragment already
  // consumes through rotateUV(uv, vRotation, 0.5), and uFlicker reuses the
  // shader's own bnoise() for an alpha flutter. All three are 1/0/0 when no
  // descriptor is active, which leaves module 1354's math unchanged.
  uniform float uSpin;
  uniform float uSpread;
  uniform float uFlicker;

  varying vec3 vPosition;
  varying vec4 vColor;
  varying float lifePerc;
  varying float vAlpha;
  varying float vRotation;

  float bnoise( in float x ) {
    float i = floor(x);
    float f = fract(x);
    float s = sign(fract(x / 2.0) - 0.5);
    float k = fract(i * .1731);
    return s * f * (f - 1.0) * ((16.0 * k - 4.0) * f * (f - 1.0) - 1.0);
  }

  void main() {
    float diff = mod(startTime + realTime, timeToLive);
    lifePerc = diff / timeToLive;
    vAlpha = inAlpha;

    // The reference's own motion, in its own units.
    vec3 motion = position
      + speed * orientationStart * diff * uSpread
      + speed * vec3(phase.zw, 1.0) * sin(vec3(phase.xy * diff * 4.0 * phaseSpeed, 0.0));

    vPosition = motion;
    vColor = color;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(vPosition, 1.0);

    if (constantSize) {
      gl_PointSize = 30.0 * inSize * uPointSize;
    } else {
      gl_PointSize = 10000.0 * inSize * uPointSize / length(gl_Position);
    }

    float randomSize;
    if (!enableRandomSize) randomSize = 1.0;
    if (enableRandomSize) {
      randomSize = 1.0 + bnoise((gl_Position.x / 3.0 + gl_Position.y / 3.0 + gl_Position.z / 3.0) / (11.0 - randomSizeSpeed));
    }
    gl_PointSize *= randomSize;

    float randomAlpha;
    if (!enableRandomAlpha) randomAlpha = 1.0;
    if (enableRandomAlpha) {
      randomAlpha = 1.0 + bnoise((gl_Position.x / 3.0 + gl_Position.y / 3.0 + gl_Position.z / 3.0) / (11.0 - randomAlphaSpeed));
    }
    vAlpha *= randomAlpha;

    float randomRotation;
    if (!enableRandomRotation) randomRotation = 0.0;
    if (enableRandomRotation) {
      randomRotation = bnoise((gl_Position.x / 3.0 + gl_Position.y / 3.0 + gl_Position.z / 3.0) / (11.0 - randomRotationSpeed));
    }
    vRotation = randomRotation * 3.1415 + uSpin;

    // Alpha flutter for the prescribed flicker axis. bnoise is module 1354's
    // own noise; realTime drives it so a paused playhead holds the pose.
    if (uFlicker > 0.0) {
      float flutter = abs(bnoise(realTime * 18.0 + phase.x * 9.0 + phase.y * 3.0));
      vAlpha *= mix(1.0, 0.35 + 0.65 * flutter, uFlicker);
    }

    if (length(gl_Position) < zLimit + zLimitGrace) {
      vAlpha *= clamp(max(0.0, (length(gl_Position) - zLimit) / zLimitGrace), 0.0, 1.0);
    }
    if (length(gl_Position) > backLimit - backLimitGrace) {
      vAlpha *= clamp(min(1.0, (backLimit - length(gl_Position)) / backLimitGrace), 0.0, 1.0);
    }
  }
`;

const PARTICLE_FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  uniform float time;
  uniform float alpha;
  uniform sampler2D texture;
  uniform bool fadeBeginning;
  uniform bool fadeEnd;
  uniform vec3 uColor;
  uniform float u_alpha;

  varying vec3 vPosition;
  varying vec4 vColor;
  varying float lifePerc;
  varying float vAlpha;
  varying float vRotation;

  vec2 rotateUV(vec2 uv, float rotation, float mid) {
    return vec2(
      cos(rotation) * (uv.x - mid) + sin(rotation) * (mid - uv.y) + mid,
      cos(rotation) * (mid - uv.y) - sin(rotation) * (uv.x - mid) + mid
    );
  }

  void main() {
    vec3 col = vec3(uColor);
    vec2 uv = gl_PointCoord;
    uv = rotateUV(uv, vRotation, 0.5);
    uv = uv * 2.0 - 1.0;
    uv /= 0.5;
    uv = uv * 0.5 + 0.5;

    vec4 pixelColor = texture2D(texture, uv);
    if (uv.x > 1.0 || uv.y > 1.0 || uv.x < 0.0 || uv.y < 0.0) {
      pixelColor *= 0.0;
    }

    pixelColor.rgb *= col;
    pixelColor.a *= u_alpha * vAlpha;
    if (pixelColor.a > 1.0) pixelColor.a = 1.0;

    if (lifePerc < 0.1 && fadeBeginning) {
      pixelColor.a *= (lifePerc * 10.0) * vAlpha;
    } else if (lifePerc > 0.9 && fadeEnd) {
      pixelColor.a *= vAlpha - (1.0 - 10.0 * (1.0 - lifePerc)) * vAlpha;
    }
    gl_FragColor = pixelColor;
  }
`;

export class ParticlesNode extends SceneNode {
  readonly kind = NodeKind.Particles;
  readonly typeLabel = "Particles";
  /** The reference item lives in a 3D layer, so it uses the perspective camera. */
  override readonly is3D = true;

  /** Item offset in the reference's world, applied to the cloud's group. */
  readonly particleOffset = new THREE.Vector3(0, 0, 0);

  /** Item scale; the reference draws the cloud at `scale + 34` per axis. */
  readonly particleScale = new THREE.Vector3(1, 1, 1);

  instances = 1000;
  sizeRange: [number, number] = [0.2, 0.6];
  alphaRange: [number, number] = [0, 1];
  speedRange: [number, number] = [1, 2];
  phaseRange: [number, number] = [5, 15];
  phaseAmplitude: [number, number] = [-10, 10];
  phaseSpeedRange: [number, number] = [1, 5];
  timeToLiveRange: [number, number] = [10, 12];
  startPos = new THREE.Vector3(-45, -75, -500);
  endPos = new THREE.Vector3(250, 75, 500);
  directionX: [number, number] = [0, 5];
  directionY: [number, number] = [-3, 3];
  directionZ: [number, number] = [50, 100];
  color = "#ffffff";
  mirror = true;
  constantSize = false;
  zLimit = 5;
  zLimitGrace = 10;
  backLimit = 500;
  backLimitGrace = 10;
  /**
   * Reference `setValue` only assigns a saved field (and only then calls
   * `onValueChange`, the sole writer of the limit uniforms) when the incoming
   * value differs from the constructor default:
   *
   *   async setValue(t,e){ const i=this.objectMapping.get(t), s=ΓÇª; const a=i[s];
   *     e!==a && (ΓÇª i[s]=Number(e) ΓÇª, this.onValueChange(s,t)) }
   *
   * The material is built with `zLimit 50 / backLimit 1000`, so a project that
   * saves the constructor defaults (5 / 500, e.g. `chill`) never pushes them
   * into the shader. We flip these flags only where the reference would have
   * fired `onValueChange`.
   */
  readonly limitOverrides = {
    zLimit: false,
    zLimitGrace: false,
    backLimit: false,
    backLimitGrace: false,
  };
  impactMultiplier = 3;
  smoothingTimeConstant = 0.2;
  globalAlpha = 1;
  incrementWithTime = true;
  timeIncrementMultiplier = 0.3;
  enableRandomSize = false;
  randomSizeSpeed = 2;
  enableRandomAlpha = true;
  randomAlphaSpeed = 2;
  enableRandomRotation = false;
  randomRotationSpeed = 2;
  fadeBeginning = true;
  fadeEnd = true;
  seed = Math.floor(Math.random() * 1e6).toString();
  audioAnalyzer = "analyzer_default";
  particleImage = "/media/particles/circle_05_alpha.webp";
  magFilter = "Linear";
  minFilter = "Linear";
  premultiplyAlpha = false;

  private material!: THREE.RawShaderMaterial;
  private front: THREE.Points | null = null;
  private back: THREE.Points | null = null;
  private particleTexture: THREE.Texture | null = null;
  private textureUrlPending: string | null = null;
  private cumMult = 0;
  private previous: Float32Array | null = null;

  /**
   * The active preset's reaction axis. `null` keeps module 1354's shipped
   * behaviour: the band average is added to `cumMult`, i.e. audio speeds the
   * whole field up. A descriptor redirects that response onto one axis.
   */
  reaction: ParticleReaction | null = null;
  /** Smoothed 0..1 impact after `reaction.smoothing` (module 682's smoother). */
  private reactionPrev = 0;
  /** `amount * smoothed`, i.e. the axis excursion used this frame. */
  reactionValue = 0;
  /** The target's effective value: a multiplier, radians, or 0..1 flicker. */
  reactionApplied = 1;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("behaviour.opacity", 100);
    this.objectMapping.set("particles.instances", this.instances);
    this.objectMapping.set("particles.impact", this.impactMultiplier);
    this.objectMapping.set("particles.globalAlpha", this.globalAlpha);
    this.objectMapping.set("particles.sizeMin", this.sizeRange[0]);
    this.objectMapping.set("particles.sizeMax", this.sizeRange[1]);
    this.objectMapping.set("particles.speed", this.timeIncrementMultiplier);
  }

  protected build(): void {
    this.material = new THREE.RawShaderMaterial({
      uniforms: {
        fadeBeginning: { value: true },
        fadeEnd: { value: true },
        uColor: { value: new THREE.Color(0xffffff) },
        realTime: { value: 0 },
        u_alpha: { value: 1 },
        texture: { value: null },
        uPointSize: { value: 1 },
        // Reference material defaults (module 1354): 50/10/1000/10. The node
        // properties default to 5/10/500/10 and only reach the shader when a
        // project or the inspector actually changes them.
        zLimit: { value: 50 },
        zLimitGrace: { value: 10 },
        backLimit: { value: 1000 },
        backLimitGrace: { value: 10 },
        constantSize: { value: false },
        enableRandomSize: { value: false },
        randomSizeSpeed: { value: 2 },
        enableRandomAlpha: { value: false },
        randomAlphaSpeed: { value: 2 },
        enableRandomRotation: { value: false },
        randomRotationSpeed: { value: 2 },
        // Preset audio-reaction axes; neutral values keep the shipped shader.
        uSpin: { value: 0 },
        uSpread: { value: 1 },
        uFlicker: { value: 0 },
      },
      vertexShader: PARTICLE_VERTEX_SHADER,
      fragmentShader: PARTICLE_FRAGMENT_SHADER,
      // Recovered verbatim from the reference's material options:
      // transparent: true, premultipliedAlpha: false, blending: NormalBlending.
      transparent: true,
      premultipliedAlpha: false,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });
    this.rebuild();
    void this.loadTexture();
  }

  private rand(salt: string): number {
    return seedrandom(this.seed + salt).double();
  }

  private lerpRange(range: [number, number], salt: string): number {
    return range[0] + this.rand(salt) * (range[1] - range[0]);
  }

  /** Builds one geometry; `flipped` negates x, as the reference's mirror does. */
  private createGeometry(flipped: boolean): THREE.BufferGeometry {
    const count = Math.max(1, Math.round(this.instances));
    const geometry = new THREE.BufferGeometry();
    const position = new Float32Array(count * 3);
    const orientation = new Float32Array(count * 3);
    const phase = new Float32Array(count * 4);
    const colors = new Float32Array(count * 4);
    const startTime = new Float32Array(count);
    const timeToLive = new Float32Array(count);
    const inSize = new Float32Array(count);
    const inAlpha = new Float32Array(count);
    const speed = new Float32Array(count);
    const phaseSpeed = new Float32Array(count);
    const sign = flipped ? -1 : 1;

    for (let index = 0; index < count; index += 1) {
      const salt = (name: string): string => String(index) + name;
      startTime[index] = this.rand(salt("startTimes")) * this.timeToLiveRange[1];
      timeToLive[index] = this.lerpRange(this.timeToLiveRange, salt("timeToLive"));
      inSize[index] = this.lerpRange(this.sizeRange, salt("inSize"));
      inAlpha[index] = this.lerpRange(this.alphaRange, salt("inAlpha"));
      speed[index] = this.lerpRange(this.speedRange, salt("speed"));
      phaseSpeed[index] = this.lerpRange(this.phaseSpeedRange, salt("phaseSpeed"));

      // The reference converts every raw export coordinate with `deg2rad`
      // (`f.z` in module 1354), positions included. The item mesh then scales
      // the cloud by `scale + 34`, which is what places it in the scene.
      const px = this.startPos.x + this.rand(salt("posX")) * (this.endPos.x - this.startPos.x);
      const py = this.startPos.y + this.rand(salt("posY")) * (this.endPos.y - this.startPos.y);
      const pz = this.startPos.z + this.rand(salt("posZ")) * (this.endPos.z - this.startPos.z);
      position.set(
        [px * PARTICLE_DEG * sign, py * PARTICLE_DEG, pz * PARTICLE_DEG],
        index * 3,
      );

      const dx = this.lerpRange(this.directionX, salt("rx"));
      const dy = this.lerpRange(this.directionY, salt("ry"));
      const dz = this.lerpRange(this.directionZ, salt("rz"));
      orientation.set([-dx * PARTICLE_DEG * sign, dy * PARTICLE_DEG, dz * PARTICLE_DEG], index * 3);

      const phaseX = this.lerpRange(this.phaseRange, salt("phaseX"));
      const phaseY = this.lerpRange(this.phaseRange, salt("phaseY"));
      const ampX = this.lerpRange(this.phaseAmplitude, salt("phaseAmpX"));
      const ampY = this.lerpRange(this.phaseAmplitude, salt("phaseAmpY"));
      phase.set(
        [phaseX * PARTICLE_DEG, phaseY * PARTICLE_DEG, ampX * PARTICLE_DEG * sign, ampY * PARTICLE_DEG],
        index * 4,
      );

      colors.set([1, 1, 1, this.rand(salt("colors"))], index * 4);
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
    geometry.setAttribute("orientationStart", new THREE.BufferAttribute(orientation, 3));
    geometry.setAttribute("phase", new THREE.BufferAttribute(phase, 4));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 4));
    geometry.setAttribute("startTime", new THREE.BufferAttribute(startTime, 1));
    geometry.setAttribute("timeToLive", new THREE.BufferAttribute(timeToLive, 1));
    geometry.setAttribute("inSize", new THREE.BufferAttribute(inSize, 1));
    geometry.setAttribute("inAlpha", new THREE.BufferAttribute(inAlpha, 1));
    geometry.setAttribute("speed", new THREE.BufferAttribute(speed, 1));
    geometry.setAttribute("phaseSpeed", new THREE.BufferAttribute(phaseSpeed, 1));
    geometry.computeBoundingSphere();
    return geometry;
  }

  /** Rebuilds both point clouds after a layout-affecting change. */
  rebuild(): void {
    for (const points of [this.front, this.back]) {
      if (!points) continue;
      this.group.remove(points);
      points.geometry.dispose();
    }
    this.front = new THREE.Points(this.createGeometry(false), this.material);
    this.front.frustumCulled = false;
    this.group.add(this.front);

    if (this.mirror) {
      this.back = new THREE.Points(this.createGeometry(true), this.material);
      this.back.frustumCulled = false;
      this.group.add(this.back);
    } else {
      this.back = null;
    }
    this.applyUniforms();
  }

  private applyUniforms(): void {
    const uniforms = this.material.uniforms;
    (uniforms.uColor.value as THREE.Color).set(this.color);
    uniforms.u_alpha.value = this.globalAlpha;
    uniforms.fadeBeginning.value = this.fadeBeginning;
    uniforms.fadeEnd.value = this.fadeEnd;
    uniforms.zLimit.value = this.limitOverrides.zLimit ? this.zLimit : 50;
    uniforms.zLimitGrace.value = this.limitOverrides.zLimitGrace ? this.zLimitGrace : 10;
    uniforms.backLimit.value = this.limitOverrides.backLimit ? this.backLimit : 1000;
    uniforms.backLimitGrace.value = this.limitOverrides.backLimitGrace ? this.backLimitGrace : 10;
    uniforms.constantSize.value = this.constantSize;
    uniforms.enableRandomSize.value = this.enableRandomSize;
    uniforms.randomSizeSpeed.value = this.randomSizeSpeed;
    uniforms.enableRandomAlpha.value = this.enableRandomAlpha;
    uniforms.randomAlphaSpeed.value = this.randomAlphaSpeed;
    uniforms.enableRandomRotation.value = this.enableRandomRotation;
    uniforms.randomRotationSpeed.value = this.randomRotationSpeed;
    uniforms.texture.value = this.particleTexture;
    // Neutral reaction axes until the next sync computes the preset's response.
    uniforms.uSpin.value = 0;
    uniforms.uSpread.value = 1;
    uniforms.uFlicker.value = 0;
  }

  /**
   * Install a preset's reaction axis. Resets both smoothers so switching
   * presets never inherits the previous preset's loudness.
   */
  setReaction(reaction: ParticleReaction | null): void {
    this.reaction = reaction ? { ...reaction } : null;
    this.reactionPrev = 0;
    this.reactionValue = 0;
    this.reactionApplied = reaction ? this.reactionBaseline(reaction) : 1;
    this.previous = null;
    if (!this.material) return;
    const uniforms = this.material.uniforms;
    uniforms.uSpin.value = 0;
    uniforms.uSpread.value = 1;
    uniforms.uFlicker.value = 0;
    uniforms.u_alpha.value = this.globalAlpha;
  }

  /** The target's value with zero impact (a quiet frame). */
  private reactionBaseline(reaction: ParticleReaction): number {
    switch (reaction.target) {
      case "alpha":
        return Math.max(0, 1 - reaction.amount);
      case "spin":
      case "flicker":
        return 0;
      default:
        return 1;
    }
  }

  /**
   * One frame of the preset's reaction, using module 682's mapping:
   *
   *   const max = project audio-impact normaliser
   *   magnitude = hypot(native bands)
   *   t = clamp(sensitivity * magnitude / max, 0, 1)
   *   if (previous === min) previous = t; else t = previous*s + (1-s)*t
   *
   * `amount` is the axis excursion, analogous to Audio Impact's `min..max`
   * (the reference's `minValue === maxValue` guard is `amount <= 0` here).
   */
  private sampleReaction(): number {
    const reaction = this.reaction;
    if (!reaction || !(reaction.amount > 0)) {
      this.reactionPrev = 0;
      return 0;
    }
    const analyzer = this.audioAnalyzer || this.ctx.defaultAnalyzerId?.() || "";
    if (!analyzer) {
      this.reactionPrev = 0;
      return 0;
    }
    let values = this.ctx.spectrumBandsFor?.(analyzer) ?? null;
    let resample = 1;
    if (!values || values.length === 0) {
      const slots = this.ctx.spectrumFor?.(analyzer) ?? null;
      if (!slots || slots.length === 0) {
        this.reactionPrev = 0;
        return 0;
      }
      // `spectrumFor` repeats the native series into 256 shader slots; undo the
      // repeat so hypot() matches module 682's native-band magnitude.
      const native = this.ctx.analyzerBands?.(analyzer) ?? slots.length;
      resample = Math.sqrt(Math.max(1, Math.min(native, slots.length)) / slots.length);
      values = slots;
    }
    const maxImpact = this.ctx.maxAudioImpact?.() ?? 0;
    if (!(maxImpact > 0)) {
      this.reactionPrev = 0;
      return 0;
    }
    let sum = 0;
    for (let i = 0; i < values.length; i += 1) {
      const raw = values[i] * 200 * resample; // bands are normalised by 200
      sum += raw * raw;
    }
    const impact = Math.min(
      1,
      Math.max(0, (reaction.sensitivity * Math.sqrt(sum)) / maxImpact),
    );
    const smoothing = Math.min(1, Math.max(0, reaction.smoothing));
    if (this.reactionPrev === 0) this.reactionPrev = impact;
    else this.reactionPrev = this.reactionPrev * smoothing + (1 - smoothing) * impact;
    return reaction.amount * this.reactionPrev;
  }

  async loadTexture(): Promise<void> {
    if (!this.particleImage) {
      this.particleTexture = proceduralDotTexture();
      this.applyUniforms();
      return;
    }
    if (this.textureUrlPending === this.particleImage) {
      // Presets can change the filter/premultiply flags without swapping the
      // sprite. Re-apply them to the already loaded texture instead of
      // returning early, which left the new flags invisible until the image
      // happened to change.
      if (this.particleTexture) {
        this.particleTexture.magFilter =
          this.magFilter === "Nearest" ? THREE.NearestFilter : THREE.LinearFilter;
        this.particleTexture.minFilter =
          this.minFilter === "Nearest" ? THREE.NearestFilter : THREE.LinearFilter;
        this.particleTexture.premultiplyAlpha = this.premultiplyAlpha;
        this.particleTexture.needsUpdate = true;
      }
      return;
    }
    this.textureUrlPending = this.particleImage;
    const loader = new THREE.TextureLoader();
    const load = (url: string): Promise<THREE.Texture> =>
      new Promise((resolve, reject) => loader.load(url, resolve, undefined, reject));
    try {
      const texture = await load(this.particleImage);
      // Module 1354 only sets premultiplyAlpha and the two filters; the texture
      // keeps three's default colour space, so no sRGB decode is applied.
      texture.colorSpace = THREE.NoColorSpace;
      texture.magFilter = this.magFilter === "Nearest" ? THREE.NearestFilter : THREE.LinearFilter;
      texture.minFilter = this.minFilter === "Nearest" ? THREE.NearestFilter : THREE.LinearFilter;
      texture.premultiplyAlpha = this.premultiplyAlpha;
      // The reference disposes the previous sprite before swapping in the new one.
      this.particleTexture?.dispose();
      this.particleTexture = texture;
    } catch {
      // A soft procedural dot keeps the field visible without the asset.
      this.particleTexture = proceduralDotTexture();
    }
    this.applyUniforms();
  }

  sync(time: number): void {
    // The item's mesh is scaled by `scale + 34`; the particle attributes are the
    // only values the reference converts from degrees. The item's own position is
    // a plain world transform (−500 on z in the export).
    this.group.scale.set(
      this.particleScale.x + 34,
      this.particleScale.y + 34,
      this.particleScale.z + 34,
    );
    this.group.position.set(this.particleOffset.x, this.particleOffset.y, this.particleOffset.z);
    const resolution = this.ctx.resolution?.() ?? { x: 1280, y: 720 };
    const analyzer = this.audioAnalyzer;
    const data = this.ctx.spectrumFor?.(analyzer) ?? this.ctx.spectrum();
    let impact = 0;
    if (data && data.length > 10) {
      // Our band values are normalised by 200; the reference averages raw ones
      // (sum / (6000 * length)), so scale back before averaging.
      const raw = new Float32Array(data.length);
      for (let i = 0; i < data.length; i += 1) raw[i] = data[i] * 200;
      const smoothed = new Float32Array(raw.length);
      if (this.previous && this.previous.length === raw.length) {
        for (let i = 0; i < raw.length; i += 1) {
          smoothed[i] = this.previous[i] + (raw[i] - this.previous[i]) * this.smoothingTimeConstant;
        }
      } else {
        smoothed.set(raw);
      }
      let sum = 0;
      for (const value of smoothed) sum += value;
      impact = (sum / (6000 * smoothed.length)) * this.impactMultiplier;
      this.previous = smoothed;
    }
    this.cumMult += impact;
    const reaction = this.sampleReaction();
    const target = this.reaction?.target ?? null;
    const amount = this.reaction?.amount ?? 0;
    let sizeScale = 1;
    let alphaScale = 1;
    let spin = 0;
    let spread = 1;
    let flicker = 0;
    if (target === "size") sizeScale = 1 + reaction;
    else if (target === "alpha") alphaScale = Math.max(0, 1 - amount + reaction);
    else if (target === "spin") spin = reaction;
    else if (target === "spread") spread = 1 + reaction;
    else if (target === "flicker") flicker = Math.min(1, reaction);
    const speedScale = target === "speed" ? 1 + reaction : 1;
    this.reactionValue = reaction;
    this.reactionApplied =
      target === "size"
        ? sizeScale
        : target === "alpha"
          ? alphaScale
          : target === "spin"
            ? spin
            : target === "spread"
              ? spread
              : target === "flicker"
                ? flicker
                : speedScale;
    if (target === "speed") {
      // Module 1354 adds the band average to `cumMult`; a speed preset scales
      // that same term instead of adding a second, different one.
      this.cumMult += impact * reaction;
    }
    const realTime = this.incrementWithTime
      ? time * this.timeIncrementMultiplier + this.cumMult
      : this.cumMult;
    this.material.uniforms.realTime.value = realTime;
    this.material.uniforms.uPointSize.value = (resolution.y / 900) * sizeScale;
    this.material.uniforms.u_alpha.value = this.globalAlpha * alphaScale;
    this.material.uniforms.uSpin.value = spin;
    this.material.uniforms.uSpread.value = spread;
    this.material.uniforms.uFlicker.value = flicker;
    // Colour automations write `node.color` directly instead of going through
    // the inspector setter, so refresh the shader uniform every frame.
    (this.material.uniforms.uColor.value as THREE.Color).set(this.color);
  }

  dispose(): void {
    this.front?.geometry.dispose();
    this.back?.geometry.dispose();
    this.material.dispose();
    this.particleTexture?.dispose();
  }

  /** Reference Particles inspector: Appearance, Random, Behaviour, Origin, Transform. */
  override createControllerSetups(): ControllerSetups {
    const ranged = (
      id: string,
      label: string,
      range: [number, number],
      min: number,
      max: number,
      step: number,
      parentId: string,
      onChange: () => void,
      tooltip?: string,
    ): PropertyDescriptor[] => [
      // Reference `variant: RANGE` is one two-handle controller
      // (`{minValue, maxValue}`), not two rows. Range automations are
      // array-valued in the export and are not wired into our single-value
      // automation model yet.
      {
        id,
        label,
        kind: PropertyKind.Range,
        container: ContainerKind.Controller,
        parentId,
        min,
        max,
        step,
        tooltip,
        animatable: false,
        read: () => range[0],
        write: (value) => {
          range[0] = Math.max(min, Math.min(Number(value), range[1]));
          onChange();
        },
        readRange: () => [range[0], range[1]],
        writeRange: (low, high) => {
          range[0] = Math.max(min, Math.min(low, high));
          range[1] = Math.min(max, Math.max(high, low));
          onChange();
        },
      },
    ];
    const rebuild = () => this.rebuild();
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "random", label: "Random", kind: ContainerKind.Folder },
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "origin", label: "Origin", kind: ContainerKind.Folder },
        { id: "originX", label: "Position X", kind: ContainerKind.Folder, parentId: "origin" },
        { id: "originY", label: "Position Y", kind: ContainerKind.Folder, parentId: "origin" },
        { id: "originZ", label: "Position Z", kind: ContainerKind.Folder, parentId: "origin" },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
        { id: "basics", label: "Basics", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.imageGrid("appearance.particleImage", "Particle image", {
          parentId: "appearance",
          values: PARTICLE_IMAGES.map((image) => image.url),
          tooltip:
            "The image used for the particles. Upload your own or use one of our presets",
          get: () => this.particleImage,
          set: (v) => {
            this.particleImage = v;
            void this.loadTexture();
          },
        }),
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          tooltip: "The color of the particles.",
          get: () => this.color,
          set: (v) => {
            this.color = v;
            this.applyUniforms();
          },
        }),
        this.toggle("appearance.mirror", "Mirror", {
          parentId: "appearance",
          tooltip: "Mirrors the particles to the other side",
          get: () => this.mirror,
          set: (v) => {
            this.mirror = v;
            this.rebuild();
          },
        }),
        this.toggle("appearance.constantSize", "Constant size", {
          parentId: "appearance",
          tooltip: "If this is enabled the particles will not scale in size by distance",
          get: () => this.constantSize,
          set: (v) => {
            this.constantSize = v;
            this.applyUniforms();
          },
        }),
        this.slider("appearance.frontLimit", "Front limit", {
          parentId: "appearance",
          min: 0,
          max: 250,
          step: 1,
          tooltip:
            "This controls at what point close to the camera the particles start disappearing. Useful for eliminating particles that smack the camera's virtual lens",
          get: () => this.zLimit,
          set: (v) => {
            this.zLimit = v;
            this.limitOverrides.zLimit = true;
            this.applyUniforms();
          },
        }),
        this.slider("appearance.frontLimitTime", "Front limit time", {
          parentId: "appearance",
          min: 0,
          max: 250,
          step: 1,
          tooltip:
            "This controls the speed at which the particles will disappear when they get close to the front limit",
          get: () => this.zLimitGrace,
          set: (v) => {
            this.zLimitGrace = v;
            this.limitOverrides.zLimitGrace = true;
            this.applyUniforms();
          },
        }),
        this.slider("appearance.backLimit", "Back limit", {
          parentId: "appearance",
          min: 0,
          max: 2000,
          step: 1,
          tooltip:
            "This controls at how far to the camera the particles start disappearing. Useful for making the particles appear out of nowhere",
          get: () => this.backLimit,
          set: (v) => {
            this.backLimit = v;
            this.limitOverrides.backLimit = true;
            this.applyUniforms();
          },
        }),
        this.slider("appearance.backLimitTime", "Back limit time", {
          parentId: "appearance",
          min: 0,
          max: 250,
          step: 1,
          tooltip:
            "This controls the speed at which the particles will disappear when they get close to the back limit",
          get: () => this.backLimitGrace,
          set: (v) => {
            this.backLimitGrace = v;
            this.limitOverrides.backLimitGrace = true;
            this.applyUniforms();
          },
        }),
        this.slider("appearance.alphaMultiplier", "Alpha multiplier", {
          parentId: "appearance",
          min: 0,
          max: 1,
          step: 0.01,
          tooltip:
            "Alpha is a value between 0 and 1 and determines the transparency. A value of 0 means completely hidden.",
          get: () => this.globalAlpha,
          set: (v) => {
            this.globalAlpha = v;
            this.applyUniforms();
          },
        }),
        this.slider("appearance.amount", "Amount", {
          parentId: "appearance",
          min: 10,
          max: 10000,
          step: 5,
          get: () => this.instances,
          set: (v) => {
            this.instances = Math.min(10000, Math.max(1, Math.round(v)));
            this.rebuild();
          },
        }),
        ...ranged(
          "appearance.opacity",
          "Opacity",
          this.alphaRange,
          0,
          1,
          0.01,
          "appearance",
          rebuild,
          "The opacity of the each particle will be a random value between min and max.",
        ),
        ...ranged(
          "appearance.size",
          "Size",
          this.sizeRange,
          0,
          3,
          0.1,
          "appearance",
          rebuild,
          "The size of the each particle will be a random value between min and max.",
        ),
        this.toggle("appearance.fadeIn", "Fade in opacity", {
          parentId: "appearance",
          get: () => this.fadeBeginning,
          set: (v) => {
            this.fadeBeginning = v;
            this.applyUniforms();
          },
        }),
        this.toggle("appearance.fadeOut", "Fade out opacity", {
          parentId: "appearance",
          get: () => this.fadeEnd,
          set: (v) => {
            this.fadeEnd = v;
            this.applyUniforms();
          },
        }),

        this.slider("random.seed", "Seed", {
          parentId: "random",
          min: 0,
          max: 2 ** 24,
          step: 1,
          tooltip: "Number which controls the random generation for the particles, up to 2^32",
          get: () => Number(this.seed),
          set: (v) => {
            this.seed = String(Math.round(v));
            this.rebuild();
          },
        }),
        this.toggle("random.enableRandomSize", "Random size", {
          parentId: "random",
          tooltip: "Enable random size multiplier dependant on particle position",
          constraint: () => !this.constantSize,
          get: () => this.enableRandomSize,
          set: (v) => {
            this.enableRandomSize = v;
            this.applyUniforms();
          },
        }),
        this.slider("random.randomSizeSpeed", "Random size speed", {
          parentId: "random",
          min: 1,
          max: 10,
          step: 0.1,
          tooltip: "The speed at which the particles will randomly resize",
          constraint: () => this.enableRandomSize && !this.constantSize,
          get: () => this.randomSizeSpeed,
          set: (v) => {
            this.randomSizeSpeed = v;
            this.applyUniforms();
          },
        }),
        this.toggle("random.enableRandomAlpha", "Random opacity", {
          parentId: "random",
          tooltip: "Enable random opacity multiplier dependant on particle position",
          get: () => this.enableRandomAlpha,
          set: (v) => {
            this.enableRandomAlpha = v;
            this.applyUniforms();
          },
        }),
        this.slider("random.randomAlphaSpeed", "Random opacity speed", {
          parentId: "random",
          min: 1,
          max: 10,
          step: 0.1,
          tooltip: "The speed at which the particles will randomly change opacity",
          constraint: () => this.enableRandomAlpha,
          get: () => this.randomAlphaSpeed,
          set: (v) => {
            this.randomAlphaSpeed = v;
            this.applyUniforms();
          },
        }),
        this.toggle("random.enableRandomRotation", "Random rotation", {
          parentId: "random",
          tooltip: "Enable random rotation multiplier dependant on particle position",
          get: () => this.enableRandomRotation,
          set: (v) => {
            this.enableRandomRotation = v;
            this.applyUniforms();
          },
        }),
        this.slider("random.randomRotationSpeed", "Random rotation speed", {
          parentId: "random",
          min: 1,
          max: 10,
          step: 0.1,
          tooltip: "The speed at which the particles will randomly rotate",
          constraint: () => this.enableRandomRotation,
          get: () => this.randomRotationSpeed,
          set: (v) => {
            this.randomRotationSpeed = v;
            this.applyUniforms();
          },
        }),

        this.analyzerSelect("behaviour.audioAnalyzer", "Audio analyzer", {
          parentId: "behaviour",
          tooltip:
            "The audio analyzer used determines how the audio will be analyzed for this object",
          get: () => this.audioAnalyzer,
          set: (v) => {
            this.audioAnalyzer = v;
          },
        }),
        this.slider("behaviour.impact", "Audio Impact", {
          parentId: "behaviour",
          min: -20,
          max: 20,
          step: 0.01,
          get: () => this.impactMultiplier,
          set: (v) => {
            this.impactMultiplier = v;
          },
        }),
        this.slider("behaviour.reactionSpeed", "Reaction speed", {
          parentId: "behaviour",
          min: 0,
          max: 1,
          step: 0.01,
          tooltip:
            "A value between 0 and 1 that determines how fast the particles will react to the music. A value of 1 means instant reaction, a value of 0 means no changes will be visibile due to how slow it will react.",
          get: () => this.smoothingTimeConstant,
          set: (v) => {
            this.smoothingTimeConstant = v;
          },
        }),
        this.toggle("behaviour.incrementWithTime", "Time increment", {
          parentId: "behaviour",
          get: () => this.incrementWithTime,
          set: (v) => {
            this.incrementWithTime = v;
          },
        }),
        this.slider("behaviour.incrementMultiplier", "Increment multiplier", {
          parentId: "behaviour",
          min: -20,
          max: 20,
          step: 0.01,
          constraint: () => this.incrementWithTime,
          get: () => this.timeIncrementMultiplier,
          set: (v) => {
            this.timeIncrementMultiplier = v;
          },
        }),
        ...ranged("behaviour.timeToLive", "Time To Live", this.timeToLiveRange, 0, 20, 0.1, "behaviour", rebuild),
        ...ranged("behaviour.phaseAmplitude", "Phase Amplitude", this.phaseAmplitude, -100, 100, 1, "behaviour", rebuild),
        ...ranged("behaviour.phase", "Phase", this.phaseRange, -360, 360, 1, "behaviour", rebuild),
        ...ranged(
          "behaviour.phaseSpeed",
          "Phase Speed",
          this.phaseSpeedRange,
          0,
          2,
          0.01,
          "behaviour",
          rebuild,
          "The phase speed of the each particle will be a random value between min and max.",
        ),
        ...ranged(
          "behaviour.speed",
          "Speed",
          this.speedRange,
          0,
          3,
          0.01,
          "behaviour",
          rebuild,
          "The speed of the each particle will be a random value between min and max.",
        ),

        this.slider("origin.startPosX", "From", {
          parentId: "originX",
          min: -500,
          max: 500,
          step: 1,
          tooltip:
            "A random value between 'from' and 'to' is used to determine the initial X position of the particle.",
          get: () => this.startPos.x,
          set: (v) => {
            this.startPos.x = v;
            this.rebuild();
          },
        }),
        this.slider("origin.endPosX", "To", {
          parentId: "originX",
          min: -500,
          max: 500,
          step: 1,
          tooltip:
            "A random value between 'from' and 'to' is used to determine the initial X position of the particle.",
          get: () => this.endPos.x,
          set: (v) => {
            this.endPos.x = v;
            this.rebuild();
          },
        }),
        this.slider("origin.startPosY", "From", {
          parentId: "originY",
          min: -500,
          max: 500,
          step: 1,
          tooltip:
            "A random value between 'from' and 'to' is used to determine the initial Y position of the particle.",
          get: () => this.startPos.y,
          set: (v) => {
            this.startPos.y = v;
            this.rebuild();
          },
        }),
        this.slider("origin.endPosY", "To", {
          parentId: "originY",
          min: -500,
          max: 500,
          step: 1,
          tooltip:
            "A random value between 'from' and 'to' is used to determine the initial Y position of the particle.",
          get: () => this.endPos.y,
          set: (v) => {
            this.endPos.y = v;
            this.rebuild();
          },
        }),
        this.slider("origin.startPosZ", "From", {
          parentId: "originZ",
          min: -1000,
          max: 1000,
          step: 1,
          tooltip:
            "A random value between 'from' and 'to' is used to determine the initial Z position of the particle.",
          get: () => this.startPos.z,
          set: (v) => {
            this.startPos.z = v;
            this.rebuild();
          },
        }),
        this.slider("origin.endPosZ", "To", {
          parentId: "originZ",
          min: -1000,
          max: 1000,
          step: 1,
          tooltip:
            "A random value between 'from' and 'to' is used to determine the initial Z position of the particle.",
          get: () => this.endPos.z,
          set: (v) => {
            this.endPos.z = v;
            this.rebuild();
          },
        }),
        ...ranged(
          "origin.directionX",
          "Direction X",
          this.directionX,
          -360,
          360,
          1,
          "origin",
          rebuild,
          "The direction of the particles along the X-axis given in degrees. The particles will spawn with a random value between min and max.",
        ),
        ...ranged(
          "origin.directionY",
          "Direction Y",
          this.directionY,
          -360,
          360,
          1,
          "origin",
          rebuild,
          "The direction of the particles along the Y-axis given in degrees. The particles will spawn with a random value between min and max.",
        ),
        ...ranged(
          "origin.directionZ",
          "Direction Z",
          this.directionZ,
          -360,
          360,
          1,
          "origin",
          rebuild,
          "The direction of the particles along the Z-axis given in degrees. The particles will spawn with a random value between min and max.",
        ),

        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.particleOffset.x,
          set: (v) => {
            this.particleOffset.x = v;
          },
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.particleOffset.y,
          set: (v) => {
            this.particleOffset.y = v;
          },
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          step: 1,
          get: () => this.particleOffset.z,
          set: (v) => {
            this.particleOffset.z = v;
          },
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0.1,
          max: 3,
          step: 0.1,
          get: () => this.particleScale.x,
          set: (v) => {
            this.particleScale.x = v;
          },
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0.1,
          max: 3,
          step: 0.1,
          get: () => this.particleScale.y,
          set: (v) => {
            this.particleScale.y = v;
          },
        }),
        this.slider("transform.scaleZ", "Scale Z", {
          parentId: "transform",
          min: 0.1,
          max: 3,
          step: 0.1,
          get: () => this.particleScale.z,
          set: (v) => {
            this.particleScale.z = v;
          },
        }),

        this.choose("basics.objectType", "Object type", {
          parentId: "basics",
          values: [this.typeLabel],
          get: () => this.typeLabel,
          set: () => void 0,
        }),
        this.text("basics.name", "Name", {
          parentId: "basics",
          get: () => this.name,
          set: (v) => {
            this.name = v;
            this.group.name = v;
          },
        }),
        this.slider("basics.start", "Time", {
          parentId: "basics",
          min: 0,
          max: 120,
          step: 0.01,
          unit: "s",
          get: () => this.start,
          set: (v) => {
            this.start = v;
          },
        }),
        this.toggle("basics.ignoreTimeSpan", "Ignore time span", {
          parentId: "basics",
          get: () => this.ignoreTimeSpan,
          set: (v) => {
            this.ignoreTimeSpan = v;
          },
        }),
      ],
    };
  }
}

function proceduralDotTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (context) {
    // The material blends normally (SrcAlpha, OneMinusSrcAlpha), so the dot is
    // white with an alpha falloff, like the reference's own sprite.
    const gradient = context.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.55, "rgba(255,255,255,0.8)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, size, size);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/* ------------------------------------------------------------------ */
/* Spectrum — FFT-driven bars / radial, drawn in a fragment shader.    */
/* ------------------------------------------------------------------ */

interface SpectrumLayerPass {
  mesh: THREE.Mesh;
  material: THREE.ShaderMaterial;
  /** Custom fragment source on the current material, or null for the built-in one. */
  shaderSource: string | null;
  /** This pass's band values; each analyzer drives its own. */
  spectrum: Float32Array;
  /** Path-coverage mask for a Shader layer (null for built-in layers). */
  mask?: SpectrumCanvasRenderer;
}

type Rgb = [number, number, number];

/** Matches the default spectrum colour (#f72585) in sRGB, as the old shader did. */
const SPECTRUM_DEFAULT_COLOR: Rgb = [247 / 255, 37 / 255, 133 / 255];

/** Sampler fallback for materials that do not use a Shader-layer mask. */
const WHITE_MASK = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
WHITE_MASK.needsUpdate = true;

/**
 * Parse a CSS hex colour to sRGB components without colour management: the old
 * shader wrote its hardcoded colour straight to `gl_FragColor`.
 */
function parseHexColor(hex: string): Rgb | null {
  const raw = hex.trim().replace(/^#/, "");
  const full =
    raw.length === 3
      ? raw
          .split("")
          .map((char) => char + char)
          .join("")
      : raw;
  if (!/^[0-9a-f]{6}$/i.test(full)) return null;
  return [0, 2, 4].map((offset) => parseInt(full.slice(offset, offset + 2), 16) / 255) as Rgb;
}

function rgbOf(hex: string, fallback: Rgb = SPECTRUM_DEFAULT_COLOR): Rgb {
  return parseHexColor(hex) ?? fallback;
}

/**
 * The shipped three.js build predates colour management, so `new
 * THREE.Color("#5d3c5c")` keeps the authored sRGB bytes. Current three converts
 * hex to the linear working space, and the layer compositor writes that linear
 * value straight to the frame, rendering flat colours ~2.2x too dark
 * (milky-cubiq's #5d3c5c background read 28,11,27 instead of 93,60,92). Store
 * the parsed sRGB triple unchanged in the working space instead.
 */
function setUnmanagedColor(target: THREE.Color, hex: string): void {
  const rgb = parseHexColor(hex);
  if (rgb) target.setRGB(rgb[0], rgb[1], rgb[2], THREE.LinearSRGBColorSpace);
  else target.set(hex);
}

/**
 * Gradient stops for a layer: colorFrom first, the colorGradient stops in the
 * middle, colorTo last. The shader supports four stops; extra stops are dropped.
 */
function layerGradient(layer: SpectrumLayer): { stops: Rgb[]; count: number } {
  const from = rgbOf(layer.colorFrom, [1, 0, 0]);
  const to = rgbOf(layer.colorTo, [0, 0, 0]);
  const middle = layer.colorGradient
    .split(/[:|,]/)
    .map((entry) => parseHexColor(entry))
    .filter((entry): entry is Rgb => entry !== null);
  const stops: Rgb[] = [];
  for (const color of [from, ...middle, to]) {
    const previous = stops[stops.length - 1];
    if (previous && previous.every((value, index) => Math.abs(value - color[index]) < 1e-4)) {
      continue;
    }
    stops.push(color);
  }
  return { stops: stops.slice(0, 4), count: Math.min(stops.length, 4) };
}

const clampNumber = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

/**
 * Calibrated against vizzy's own "Save preview as image" of the same project:
 * its halo peaks at ~26% white at the silhouette edge and is gone within ~30px,
 * i.e. an effective sigma of ~10px at 720p — half the authored
 * globalShadowSigma of 20.
 */
const SHADOW_ALPHA_SCALE = 0.73;
const SHADOW_SIGMA_SCALE = 0.72;


export class SpectrumNode extends SceneNode {
  readonly kind = NodeKind.Effects;
  readonly typeLabel = "Spectrum";

  type: SpectrumType = "Bars";
  draw: SpectrumDraw = "Line";
  fillStyle: SpectrumFillStyle = "Fill";
  color = "#f72585";
  circleColor = "#f72585";
  /** Multi-layer data model; every enabled layer is rendered as its own pass. */
  readonly layers: SpectrumLayer[] = [createSpectrumLayer(0, this.color)];
  /**
   * Draw through the decompiled Canvas2D path renderer instead of the shader.
   * The shader fallback rendered a circle "line" as separate ring segments
   * (`step(local, 0.68)`), so its bars never joined into the reference's
   * continuous circle. Every spectrum now uses the path renderer; the shader
   * remains only as a fallback when the canvas is unavailable.
   */
  pathMode = true;
  /** Reference custom-path command string (`lineTo/quadTo/arcTo`). */
  customPath = "";
  closeLine = true;
  moveBack = false;
  repeatPointsOnPath = true;
  smoothStartAndEnd = true;
  smoothingWidth = 10;
  smoothingPasses = 4;
  stretchToEnd = false;
  spacing = 0;
  /**
   * Texture rasterisation scale for the Canvas2D spectrum surface. The reference
   * repaints and re-uploads the whole item every frame, so at 1920x1080 the
   * upload dominates (2 items at 1.0 = ~10 fps on an RTX 3060, at 0.5 = ~30).
   * 1 is the reference's project-resolution surface.
   */
  renderScale = 1;
  /**
   * Constant spin for built-in presets, degrees per second. Applied on top of
   * the item's `transform.rotation`, so a preset can demonstrate motion without
   * adding an automation row to the project. 0 means no spin.
   */
  spinSpeed = 0;
  /** Last rendered time, used for the spin angle. */
  private spinTime = 0;
  lineCap = "round";
  pathEffect = "none";
  dashOffset = 10;
  clipSize = 0.95;
  /** Item-space transform from the reference (`preScaling` inputs). */
  positionX = 0;
  positionY = 0;
  scaleX = 1;
  scaleY = 1;
  /**
   * The reference's own `scaleMultiplier` factor, kept alongside the calibrated
   * `transform.scaleMultiplier` percent. Audio-impact automations are calibrated
   * for the shader, but the path renderer must use the raw reference factor.
   */
  referenceScaleMultiplier = 1;
  /** Optional image used by the Custom / Image spectrum types. */
  assetId: string | null = null;
  /** Remote image source (the reference's Link row). */
  imageUrl: string | null = null;
  private urlTexture: THREE.Texture | null = null;
  private urlPending: string | null = null;
  colorShift = 0;
  bands = 64;
  mirror = false;
  /** Mean band value for the current frame (reference `currentData`). */
  private currentData = 0;
  /** Running audio energy (reference `cumulativeData`, += current / 5000). */
  private cumulativeData = 0;
  private geometry!: THREE.PlaneGeometry;
  /** One pass per enabled layer; pooled and reused as layers change. */
  private readonly layerPasses: SpectrumLayerPass[] = [];
  /** Canvas2D path renderer and its plane, used when `pathMode` is on. */
  private pathRenderer: SpectrumCanvasRenderer | null = null;
  private pathMesh: THREE.Mesh | null = null;
  /**
   * Per-layer custom-shader failures, keyed by layer id. A layer listed here is
   * rendering its solid colour because `shaderSrc` was rejected.
   */
  readonly shaderErrors = new Map<string, string>();
  private readonly spectrumData = new Float32Array(256);
  private readonly waveData = new Float32Array(256);

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("behaviour.opacity", 100);
    this.objectMapping.set("behaviour.scale", 100);
    this.objectMapping.set("behaviour.height", 100);
    this.objectMapping.set("behaviour.dotSize", 3);
    this.objectMapping.set("behaviour.feather", 8);
    this.objectMapping.set("behaviour.bands", 64);
    this.objectMapping.set("behaviour.downsample", 1);
    this.objectMapping.set("behaviour.lineWidth", 3);
    this.objectMapping.set("behaviour.smoothWidth", 10);
    this.objectMapping.set("behaviour.smoothPasses", 4);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.width", 100);
    this.objectMapping.set("transform.height", 100);
    this.objectMapping.set("transform.rotation", 0);
    this.objectMapping.set("transform.scaleMultiplier", 100);
    this.objectMapping.set("transform.textureX", 0);
    this.objectMapping.set("transform.textureY", 0);
    this.objectMapping.set("transform.textureScaleX", 100);
    this.objectMapping.set("transform.textureScaleY", 100);
    this.objectMapping.set("effects.colorShift", 0);
    this.objectMapping.set("effects.smoothing", 60);
    this.objectMapping.set("effects.gain", 1);
    this.objectMapping.set("channel.shadow", 0);
    this.objectMapping.set("channel.shadowScale", 100);
    this.objectMapping.set("channel.shadowAlpha", 100);
    this.objectMapping.set("channel.shadowX", 0);
    this.objectMapping.set("channel.shadowY", 0);
    this.objectMapping.set("channel.shadowSigmaX", 20);
    this.objectMapping.set("channel.shadowSigmaY", 20);
    this.objectMapping.set("channel.circleSize", 100);
    this.objectMapping.set("channel.fillCircle", 0);
    this.objectMapping.set("channel.clipCircle", 0);
    this.objectMapping.set("channel.connect", 0);
    this.objectMapping.set("channel.aa", 1);
    this.objectMapping.set("channel.aspectFix", 1);
    this.objectMapping.set("channel.imageSize", 100);
    this.objectMapping.set("channel.circularImage", 0);
    this.objectMapping.set("channel.baseRadius", 51.4);
    this.objectMapping.set("channel.contourWidth", 1.2);
  }

  protected build(): void {
    this.geometry = new THREE.PlaneGeometry(3.6, 1.6, 1, 1);
    this.ensureLayerPasses(this.layers.length);
    this.pathRenderer = new SpectrumCanvasRenderer();
    const material = new THREE.MeshBasicMaterial({
      map: this.pathRenderer.texture,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    this.pathMesh = new THREE.Mesh(this.geometry, material);
    this.pathMesh.visible = false;
    this.group.add(this.pathMesh);
  }

  /**
   * One material per layer. Every pass shares the same geometry, spectrum arrays
   * and object-level uniforms; only the per-layer colour, transform, blur and
   * shadow uniforms differ.
   */
  private createLayerMaterial(
    fragmentSource: string | null = null,
    spectrum: Float32Array = this.spectrumData,
  ): THREE.ShaderMaterial {
    return new THREE.ShaderMaterial({
      transparent: true,
      // Layer passes are sorted by renderOrder/z. Writing depth would let a
      // nearer pass's transparent quad occlude every pass behind it.
      depthWrite: false,
      uniforms: {
        uSpectrum: { value: spectrum },
        uWave: { value: this.waveData },
        uBands: { value: this.bands },
        uType: { value: 0 },
        uDraw: { value: 0 },
        uFill: { value: 1 },
        uMirror: { value: 0 },
        uColorShift: { value: 0 },
        uGain: { value: 1 },
        uOpacity: { value: 1 },
        uAspect: { value: 16 / 9 },
        uHeight: { value: 1 },
        uDot: { value: 0.018 },
        uFeather: { value: 0.08 },
        uLineWidth: { value: 3 },
        uDownsample: { value: 1 },
        uRotation: { value: 0 },
        uScaleMul: { value: 1 },
        uLayerScale: { value: 1 },
        uLayerRotation: { value: 0 },
        uLayerAlpha: { value: 1 },
        uLayerGain: { value: 1 },
        uColorType: { value: 0 },
        uBaseOn: { value: 0 },
        uColorSolid: { value: new THREE.Vector3(...SPECTRUM_DEFAULT_COLOR) },
        uColorMix: { value: 0.5 },
        uGrad0: { value: new THREE.Vector3(1, 0, 0) },
        uGrad1: { value: new THREE.Vector3(0, 0, 0) },
        uGrad2: { value: new THREE.Vector3(0, 0, 0) },
        uGrad3: { value: new THREE.Vector3(0, 0, 0) },
        uGradCount: { value: 2 },
        uBlur: { value: 0 },
        uMean: { value: 0 },
        uCeiling: { value: 5 },
        uBass: { value: 0 },
        uMid: { value: 0 },
        uTreble: { value: 0 },
        uLayerIndex: { value: 0 },
        uLayerCount: { value: 1 },
        uBaseRadius: { value: 0.26 },
        uContourWidth: { value: 0.012 },
        uTexPos: { value: new THREE.Vector2(0, 0) },
        uTexScale: { value: new THREE.Vector2(1, 1) },
        uShadowOn: { value: 0 },
        uShadowScale: { value: 1 },
        uShadowAlpha: { value: 0.45 },
        uShadowColor: { value: new THREE.Vector3(1, 1, 1) },
        uShadowOffset: { value: new THREE.Vector2(0, 0) },
        uShadowBlur: { value: new THREE.Vector2(0, 0) },
        uCircleSize: { value: 0.16 },
        uCircleColor: { value: new THREE.Color("#f72585") },
        uFillCircle: { value: 0 },
        uClipCircle: { value: 0 },
        uConnect: { value: 0 },
        uAA: { value: 1 },
        uAspectFix: { value: 1 },
        uImage: { value: null },
        uHasImage: { value: 0 },
        uImageSize: { value: 1 },
        uCircularImage: { value: 0 },
        // SkSL contract: the reference's runtime effects declare these.
        u_resolution: { value: new THREE.Vector2(1920, 1080) },
        u_itemSize: { value: 1000 },
        u_time: { value: 0 },
        u_amt: { value: 1 },
        u_audio_cumulative: { value: 0 },
        u_audio_current: { value: 0 },
        uMask: { value: WHITE_MASK },
        u_col1: { value: new THREE.Vector4(1, 1, 1, 1) },
        u_col2: { value: new THREE.Vector4(0, 0, 0, 1) },
      },
      vertexShader: SPECTRUM_VERTEX_SHADER,
      fragmentShader: fragmentSource ?? /* glsl */ `
        precision highp float;
        uniform float uSpectrum[256];
        uniform float uWave[256];
        uniform float uBands;
        uniform float uType;      // 0 = bars, 1 = circle
        uniform float uDraw;      // 0 line, 1 curve, 2 plexus, 3 point
        uniform float uFill;      // 1 = fill, 0 = stroke
        uniform float uMirror;    // 0 = off, 1 = mirrored across the centre
        uniform float uColorShift;
        uniform float uGain;
        uniform float uOpacity;
        uniform float uAspect;
        uniform float uHeight;
        uniform float uDot;
        uniform float uFeather;
        uniform float uLineWidth;
        uniform float uDownsample;
        uniform float uRotation;
        uniform float uScaleMul;
        uniform float uLayerScale;
        uniform float uLayerRotation;
        uniform float uLayerAlpha;
        uniform float uLayerGain;
        uniform float uColorType; // 0 = solid/fallback, 1 = gradient, 2 = from-to
        uniform float uBaseOn;    // 0 value, 1 y, 2 x, 3 distance (from-to only)
        uniform vec3  uColorSolid;
        uniform float uColorMix;
        uniform vec3  uGrad0;
        uniform vec3  uGrad1;
        uniform vec3  uGrad2;
        uniform vec3  uGrad3;
        uniform float uGradCount;
        uniform float uBlur;
        uniform float uMean;
        uniform float uCeiling;
        uniform float uBass;
        uniform float uMid;
        uniform float uTreble;
        uniform float uLayerIndex;
        uniform float uLayerCount;
        uniform float uBaseRadius;
        uniform float uContourWidth;
        uniform vec2  uTexPos;
        uniform vec2  uTexScale;
        uniform float uShadowOn;
        uniform float uShadowScale;
        uniform float uShadowAlpha;
        uniform vec3  uShadowColor;
        uniform vec2  uShadowOffset;
        uniform vec2  uShadowBlur;
        uniform float uCircleSize;
        uniform vec3  uCircleColor;
        uniform float uFillCircle;
        uniform float uClipCircle;
        uniform float uConnect;
        uniform float uAA;
        uniform float uAspectFix;
        uniform sampler2D uImage;
        uniform float uHasImage;
        uniform float uImageSize;
        uniform float uCircularImage;
        varying vec2 vUv;

        float bandAt(float index) {
          // The reference clamps each analyzer sample to the layer's ceiling
          // before scaling by multiplier * spectrumHeight.
          return min(uSpectrum[int(clamp(index, 0.0, 255.0))], uCeiling);
        }

        float waveAt(float index) {
          return uWave[int(clamp(index, 0.0, 255.0))];
        }

        float rawBand(float i) {
          return bandAt(i * (256.0 / max(uBands, 2.0)));
        }

        // Amplitude at a normalised position along the shape, with the band
        // stride applied and linear interpolation between samples.
        float valueAt(float t) {
          float n = max(uBands / max(uDownsample, 1.0), 2.0);
          float idx = clamp(t, 0.0, 0.9999) * (n - 1.0);
          float i0 = floor(idx);
          float f = fract(idx);
          float a = rawBand(i0 * uDownsample);
          float b = rawBand(min(i0 + 1.0, n - 1.0) * uDownsample);
          return mix(a, b, f) * uGain * uLayerGain * uHeight;
        }

        // Soft edge with a user-controlled feather width; anti-aliasing can be off.
        float edge(float d) {
          float w = uLineWidth * 0.0012 + uFeather * 0.0009;
          return uAA > 0.5 ? smoothstep(w, 0.001, d) : step(d, w);
        }

        float planar(vec2 p) {
          float base = 0.08;
          float n = max(uBands / max(uDownsample, 1.0), 2.0);

          if (uDraw < 0.5) {
            float local = fract(clamp(p.x, 0.0, 0.9999) * n);
            float h = valueAt(p.x);
            return step(local, 0.68) * step(base, p.y) * step(p.y, base + h);
          }
          if (uDraw < 1.5) {
            float top = base + valueAt(p.x);
            return (uFill > 0.5)
              ? step(base, p.y) * step(p.y, top)
              : edge(abs(p.y - top));
          }
          if (uDraw < 2.5) {
            float idx = clamp(p.x, 0.0, 0.9999) * (n - 1.0);
            float i0 = floor(idx);
            float f = fract(idx);
            float y0 = base + rawBand(i0 * uDownsample) * uGain * uLayerGain * uHeight;
            float y1 = base + rawBand(min(i0 + 1.0, n - 1.0) * uDownsample) * uGain * uLayerGain * uHeight;
            return edge(abs(p.y - mix(y0, y1, f)));
          }

          float idx = clamp(p.x, 0.0, 0.9999) * n;
          float i0 = floor(idx);
          float local = fract(idx) - 0.5;
          float y = base + rawBand(i0 * uDownsample) * uGain * uLayerGain * uHeight;
          float af = mix(1.0, 2.25, uAspectFix);
          vec2 d = vec2(local * af / n, p.y - y);
          float bead = 1.0 - smoothstep(uDot, uDot + 0.006 + uFeather * 0.0009, length(d));

          if (uConnect < 0.5) return bead;
          float y1 = base + rawBand(min(i0 + 1.0, n - 1.0) * uDownsample) * uGain * uLayerGain * uHeight;
          return max(bead, edge(abs(p.y - mix(y, y1, fract(idx)))));
        }

        float ring(vec2 p) {
          float r = length(p);
          float a = atan(p.y, p.x) / 6.2831853 + 0.5;

          // Mirroring makes the ring symmetric about the vertical axis: both
          // sides read the same half of the spectrum (the reference's
          // mirrorHorizontal). atan2(y, |x|) folds the left half onto the right.
          if (uMirror > 0.5) {
            a = atan(p.y, abs(p.x)) / 3.14159265 + 0.5;
          }

          // The reference fills or strokes one closed silhouette per layer, with
          // this layer's own sample as the radius (curRad + value). Every layer
          // is painted over the previous one, so a colour survives only where it
          // reaches past the layer above it; at silence all layers coincide and
          // only the last one is visible.
          // Band 0 sits at the top and runs to the bottom over the right half
          // (drawSpectrumPoints: angle = -pi/2 + pi*u, y down), so the middle of
          // the spectrum lands on the horizontal axis and mirrors left/right.
          // Without mirroring the full circle spans the spectrum: u = 0.75 - a.
          float u = (uMirror > 0.5) ? (1.0 - a) : (0.75 - a);
          u -= floor(u);

          // valueAt already applies uHeight. The reference's radius is curRad + t,
          // with curRad reset to 120 on every update (the 400 in its constructor
          // is overwritten) and t in canvas pixels, so a sample displaces
          // (t / 120) of the base radius. Ours are normalised by 200, which is
          // what the coefficient converts; it is fitted against the reference's
          // own frame at 19.946s, where its rim reaches ~37px past the ring while
          // our uncorrected mapping reached ~90px.
          float amp = valueAt(u) * 0.8 * uBaseRadius;
          float radius = uBaseRadius + amp;

          // The reference fills the band between curRad and curRad + value
          // (drawSpectrumPoints traces the displaced outline and returns along
          // the base circle), not the whole disc. Filling the disc painted the
          // emblem area white and hid every layer underneath.
          if (uFill > 0.5) return step(uBaseRadius, r) * step(r, radius);

          float outline = 1.0 - smoothstep(uContourWidth, uContourWidth + 0.004, abs(r - radius));
          return outline;
        }

        vec3 hueShift(vec3 c, float h) {
          const vec3 k = vec3(0.57735);
          float cosA = cos(h);
          return c * cosA + cross(k, c) * sin(h) + k * dot(k, c) * (1.0 - cosA);
        }

        // Gradient across the layer's local x axis. colorMix shifts the sampled
        // window so 0.5 spans the full from-to ramp.
        vec3 gradientColor(float t) {
          float shifted = clamp(t + (uColorMix - 0.5), 0.0, 1.0);
          if (uGradCount < 1.5) return uGrad0;
          float last = max(uGradCount - 1.0, 1.0);
          float s = shifted * last;
          if (s < 1.0) return mix(uGrad0, uGrad1, s);
          if (uGradCount < 2.5) return uGrad1;
          if (s < 2.0) return mix(uGrad1, uGrad2, s - 1.0);
          if (uGradCount < 3.5) return uGrad2;
          return mix(uGrad2, uGrad3, clamp(s - 2.0, 0.0, 1.0));
        }

        float shapeCoverage(vec2 q) {
          vec2 shape = q + 0.5;
          if (uMirror > 0.5 && uType < 0.5) {
            shape.x = abs(shape.x - 0.5) * 2.0;
          }
          return (uType < 0.5) ? planar(shape) : ring(vec2(q.x * uAspect, q.y));
        }

        // The reference's global shadow is a blurred copy of the item drawn
        // behind it (CanvasKit ImageFilter.MakeBlur with the global sigmas), not
        // an offset drop shadow. Two rings of taps approximate that Gaussian.
        float blurCoverage(vec2 q, vec2 radius) {
          float total = shapeCoverage(q) * 0.2;
          for (int i = 0; i < 8; i++) {
            float a = (float(i) + 0.5) * 0.78539816;
            vec2 dir = vec2(cos(a), sin(a));
            total += shapeCoverage(q + dir * radius * 0.55) * 0.05;
            total += shapeCoverage(q + dir * radius) * 0.05;
          }
          return total;
        }

        // Nine-tap box blur over the procedural shape; zero blur keeps the hard
        // single-sample edge. blurAmount is a 0..1 fraction of an 0.08 plane radius.
        float softCoverage(vec2 q) {
          if (uBlur <= 0.0001) return shapeCoverage(q);
          float radius = clamp(uBlur, 0.0, 1.0) * 0.08;
          float diagonal = radius * 0.70710678;
          float sum = shapeCoverage(q) * 2.0;
          sum += shapeCoverage(q + vec2(radius, 0.0));
          sum += shapeCoverage(q - vec2(radius, 0.0));
          sum += shapeCoverage(q + vec2(0.0, radius));
          sum += shapeCoverage(q - vec2(0.0, radius));
          sum += shapeCoverage(q + vec2(diagonal, diagonal));
          sum += shapeCoverage(q + vec2(-diagonal, diagonal));
          sum += shapeCoverage(q + vec2(diagonal, -diagonal));
          sum += shapeCoverage(q - vec2(diagonal, diagonal));
          return sum / 10.0;
        }

        void main() {
          // Layer transform composes with the object transform: scales multiply
          // and rotations add before the texture mapping is applied.
          vec2 p = (vUv - 0.5) / max(uScaleMul * uLayerScale, 0.05);

          float c = cos(uRotation + uLayerRotation);
          float s = sin(uRotation + uLayerRotation);
          p = mat2(c, -s, s, c) * p;

          p = p / max(uTexScale, vec2(0.05)) + uTexPos;

          float cov = softCoverage(p);

          float t = (uMirror > 0.5 && uType < 0.5)
            ? clamp(abs(p.x) * 2.0, 0.0, 1.0)
            : clamp(p.x + 0.5, 0.0, 1.0);
          vec3 col;
          if (uColorType > 1.5) {
            // Reference getFromToShader: mix two colours along baseOn.
            // Its denominator is 750 * colorMix in reference pixels; our local
            // plane spans -0.5..0.5, so 0.5 is the equivalent half-extent.
            float base = 0.5 * max(uColorMix, 0.001);
            float ft = uColorMix;
            if (uBaseOn > 2.5) ft = length(p) / base;
            else if (uBaseOn > 1.5) ft = abs(p.x) / base;
            else if (uBaseOn > 0.5) ft = abs(p.y) / base;
            col = mix(uGrad0, uGrad1, ft);
          } else if (uColorType > 0.5) {
            col = gradientColor(t);
          } else {
            col = uColorSolid;
          }
          col = hueShift(col, uColorShift);

          // drawCircleImage runs after every layer in the reference, clipped to a
          // circle of 0.98 * curRad, so the artwork is always a clean circle on
          // top of the spectrum — never cropped by a deformed silhouette.
          vec3 logoSample = vec3(0.0);
          float logoAlpha = 0.0;
          if (uHasImage > 0.5 && uLayerIndex >= uLayerCount - 1.5) {
            vec2 imageUv;
            if (uType > 0.5) {
              float logoRadius = max(0.02, uBaseRadius * clamp(uImageSize, 0.05, 1.0) * 0.98);
              imageUv = vec2(p.x * uAspect, p.y) / (2.0 * logoRadius) + 0.5;
              logoAlpha = step(length(vec2(p.x * uAspect, p.y)), logoRadius);
            } else {
              imageUv = (vUv - 0.5) / max(uImageSize, 0.05) + 0.5;
              logoAlpha = 1.0;
            }
            vec4 texel = texture2D(uImage, imageUv);
            logoSample = texel.rgb;
            logoAlpha *= texel.a;
          }

          float shadow = 0.0;
          if (uShadowOn > 0.5) {
            vec2 offsetP = p - uShadowOffset;
            if (uShadowBlur.x > 0.0005 || uShadowBlur.y > 0.0005) {
              shadow = blurCoverage(offsetP, uShadowBlur);
            } else {
              shadow = softCoverage(offsetP / max(uShadowScale, 0.05));
            }
            shadow *= uShadowAlpha;
          }

          // Composite the shadow underneath this layer's coverage. With shadow
          // off this reduces exactly to the previous mix()/alpha formula.
          // Reference drawCircleFill: a disc behind the spectrum when Fill
          // circle is on. The Canvas2D path already draws it; the GPU path did
          // not, so circle templates lost their background disc.
          float disc = 0.0;
          if (uFillCircle > 0.5 && uType > 0.5) {
            float discRadius = uBaseRadius * clamp(uCircleSize, 0.0, 2.0);
            disc = 1.0 - smoothstep(discRadius, discRadius + 0.004, length(vec2(p.x * uAspect, p.y)));
          }
          float coverage = max(cov, disc);
          vec3 fill = mix(mix(vec3(0.03, 0.02, 0.03), uCircleColor, disc), col, cov);
          float alpha = coverage + shadow * (1.0 - coverage);
          vec3 rgb = (fill * coverage + uShadowColor * shadow * (1.0 - coverage)) / max(alpha, 1e-4);

          // The artwork is drawn last, over the layers and the glow.
          rgb = mix(rgb, logoSample, logoAlpha);
          alpha = alpha * (1.0 - logoAlpha) + logoAlpha;
          gl_FragColor = vec4(rgb, alpha * uOpacity * uLayerAlpha);
        }
      `,
    });
  }

  /** Apply a preset to the same state a freshly-created Spectrum item has. */
  resetPresetLook(): void {
    // These defaults are the reference Spectrum item's own defaults
    // (`spectrumType circle`, `drawType curve`, `lineWidth 2`, and so on).
    // Presets are full looks: omitted fields must not inherit the previous
    // preset's value, which made e.g. `clipCircle` and `dotSize` order-dependent.
    this.type = "Circle";
    this.draw = "Curve";
    this.fillStyle = "Fill";
    this.mirror = true;
    this.bands = 64;
    this.setDefaults({
      "behaviour.opacity": 95,
      "behaviour.scale": 100,
      "behaviour.height": 100,
      "behaviour.dotSize": 5,
      "behaviour.feather": 8,
      "behaviour.bands": 64,
      "behaviour.downsample": 1,
      "behaviour.lineWidth": 2,
      "behaviour.smoothWidth": 10,
      "behaviour.smoothPasses": 4,
      "transform.x": 0,
      "transform.y": 0,
      "transform.width": 100,
      "transform.height": 100,
      "transform.rotation": 0,
      "transform.scaleMultiplier": 200,
      "transform.textureX": 0,
      "transform.textureY": 0,
      "transform.textureScaleX": 100,
      "transform.textureScaleY": 100,
      "effects.colorShift": 0,
      "effects.smoothing": 60,
      "effects.gain": 1,
      "channel.shadow": 1,
      "channel.shadowScale": 100,
      "channel.shadowAlpha": 100,
      "channel.shadowX": 0,
      "channel.shadowY": 0,
      "channel.shadowSigmaX": 20,
      "channel.shadowSigmaY": 20,
      "channel.circleSize": 100,
      "channel.fillCircle": 1,
      "channel.clipCircle": 0,
      "channel.connect": 0,
      "channel.aa": 1,
      "channel.aspectFix": 1,
      "channel.imageSize": 100,
      "channel.circularImage": 1,
      "channel.baseRadius": 51.4,
      "channel.contourWidth": 1.2,
    });

    this.customPath = "";
    this.closeLine = true;
    this.moveBack = false;
    this.repeatPointsOnPath = true;
    this.smoothStartAndEnd = true;
    this.smoothingWidth = 10;
    this.smoothingPasses = 4;
    this.stretchToEnd = false;
    this.spacing = 0;
    this.lineCap = "square";
    this.pathEffect = "none";
    this.dashOffset = 10;
    this.clipSize = 0.95;
    this.positionX = 0;
    this.positionY = 0;
    this.scaleX = 1;
    this.scaleY = 1;
    this.referenceScaleMultiplier = 2;
    this.spinSpeed = 0;
    this.circleColor = "#ffffff";
    this.resetImageSource();
  }

  /** Clears the file/link image and releases its texture. */
  resetImageSource(): void {
    this.assetId = null;
    this.imageUrl = null;
    this.urlPending = null;
    this.urlTexture?.dispose();
    this.urlTexture = null;
  }

  private setDefaults(values: Record<string, number>): void {
    for (const [key, value] of Object.entries(values)) {
      this.objectMapping.set(key, value);
    }
  }

  dispose(): void {
    this.pathRenderer?.dispose();
    this.pathRenderer = null;
    if (this.pathMesh) {
      this.pathMesh.geometry.dispose();
      const material = this.pathMesh.material;
      if (Array.isArray(material)) material.forEach((item) => item.dispose());
      else material.dispose();
      this.pathMesh = null;
    }
    for (const pass of this.layerPasses) {
      pass.material.dispose();
      pass.mask?.dispose();
    }
    this.layerPasses.splice(0, this.layerPasses.length);
    this.urlTexture?.dispose();
    this.urlTexture = null;
  }

  private ensureLayerPasses(count: number): void {
    while (this.layerPasses.length < count) {
      const data = new Float32Array(256);
      const material = this.createLayerMaterial(null, data);
      const mesh = new THREE.Mesh(this.geometry, material);
      const index = this.layerPasses.length;
      this.group.add(mesh);
      this.layerPasses.push({ mesh, material, shaderSource: null, spectrum: data });
    }
  }

  /**
   * Give a pass the material its layer needs. A `Shader` layer compiles its own
   * fragment source; when that source is missing or rejected the pass keeps the
   * built-in material and falls back to the layer's solid colour, with the
   * reason recorded in {@link shaderErrors}.
   */
  private applyLayerShader(pass: SpectrumLayerPass, layer: SpectrumLayer): void {
    let desired: string | null = null;

    if (layer.colorType === "Shader") {
      const built = buildSpectrumFragment(layer.shaderSrc, this.pathMode);
      if (built.source) {
        desired = built.source;
        this.shaderErrors.delete(layer.id);
      } else if (built.error) {
        this.shaderErrors.set(layer.id, built.error);
      } else {
        // The GPU check is still in flight; keep the built-in material until
        // a verdict arrives rather than handing an unverified shader to the
        // renderer.
        this.shaderErrors.delete(layer.id);
      }
    } else {
      this.shaderErrors.delete(layer.id);
    }

    if (pass.shaderSource === desired) return;

    pass.material.dispose();
    pass.material = this.createLayerMaterial(desired, pass.spectrum);
    pass.mesh.material = pass.material;
    pass.shaderSource = desired;
  }

  private syncLayerPass(
    pass: SpectrumLayerPass,
    layer: SpectrumLayer,
    index: number,
    count: number,
    texture: THREE.Texture | null,
    time: number,
  ): void {
    this.applyLayerShader(pass, layer);
    const uniform = pass.material.uniforms;

    const typeIndex = this.type === "Circle" ? 1 : 0;
    const drawIndex =
      this.draw === "Curve" ? 1 : this.draw === "Plexus" ? 2 : this.draw === "Point" ? 3 : 0;
    uniform.uType.value = typeIndex;
    uniform.uDraw.value = drawIndex;
    uniform.uFill.value = this.fillStyle === "Fill" ? 1 : 0;

    // Each layer reads its own analyzer; an unbound layer follows the item's
    // analyzer / the project's Default one, like the reference's layer default.
    const analyzerId = this.layerAnalyzer(layer);
    const analyzerSpectrum = this.slotsFor(layer);
    if (analyzerSpectrum) {
      // The pass holds a fixed 256-slot spectrum and the shader reads it with a
      // stride of length/bands, so an analyzer's 64 bands must be spread across
      // the slots. Copying them into the first 64 left the rest stale and made
      // the ring read mostly zeros.
      const target = pass.spectrum;
      const stride = target.length / Math.max(1, analyzerSpectrum.length);
      target.fill(0);
      for (let i = 0; i < analyzerSpectrum.length; i += 1) {
        target[Math.min(target.length - 1, Math.round(i * stride))] = analyzerSpectrum[i];
      }
    } else {
      pass.spectrum.set(this.spectrumData);
    }

    // A Shader layer paints its SkSL colour only where the reference's path
    // covers the item. Draw that coverage into an alpha texture and let the
    // fragment shader sample it.
    if (this.pathMode && layer.colorType === "Shader") {
      if (!pass.mask) pass.mask = new SpectrumCanvasRenderer();
      const pathBands = this.bandsFor(layer) ?? analyzerSpectrum;
      pass.mask.drawMask(this.pathSettings(), {
        ...layer,
        bands: this.referenceBands(pathBands ?? this.spectrumData),
      });
      pass.material.uniforms.uMask.value = pass.mask.texture;
    }

    // A layer bound to an analyzer samples that analyzer's band count and gain,
    // so two layers can read the same spectrum at different resolutions.
    const analyzerBands = analyzerId ? this.ctx.analyzerBands?.(analyzerId) ?? null : null;
    const analyzerAmplitude = analyzerId ? this.ctx.analyzerGain?.(analyzerId) ?? 1 : 1;
    uniform.uBands.value = analyzerBands ?? this.bands;

    // The reference smooths the path geometry (smoothingWidth / smoothingPasses).
    // Ours smooths the band series feeding that path, which rounds the silhouette
    // the same way without a resampling pass.
    const smoothPasses = Math.round(this.readNumber("behaviour.smoothPasses"));
    const smoothWidth = Math.max(1, Math.round(this.readNumber("behaviour.smoothWidth")));
    const bandCount = Math.max(1, Math.min(pass.spectrum.length, Math.round(uniform.uBands.value as number)));
    if (smoothPasses > 0 && smoothWidth > 1 && bandCount > 2) {
      const radius = Math.min(smoothWidth, Math.max(1, Math.floor(bandCount / 8)));
      for (let p = 0; p < smoothPasses; p += 1) {
        const prev = Float32Array.from(pass.spectrum.subarray(0, bandCount));
        for (let i = 0; i < bandCount; i += 1) {
          let sum = 0;
          let n = 0;
          for (let k = -radius; k <= radius; k += 1) {
            sum += prev[(i + k + bandCount) % bandCount];
            n += 1;
          }
          pass.spectrum[i] = sum / n;
        }
      }
    }

    // Mean amplitude for the image disc's pulse; computed here so the fragment
    // shader needs no loop (software rendering makes one very expensive).
    const sampleCount = Math.max(1, Math.min(256, Math.round(uniform.uBands.value as number)));
    let mean = 0;
    for (let i = 0; i < sampleCount; i += 1) mean += pass.spectrum[i];
    uniform.uMean.value = mean / sampleCount;

    // Split the spectrum into low/mid/high energy so the silhouette can respond
    // differently per region instead of scaling uniformly.
    const lowEnd = Math.max(1, Math.floor(sampleCount * 0.25));
    const midEnd = Math.max(lowEnd + 1, Math.floor(sampleCount * 0.65));
    let bass = 0;
    let mid = 0;
    let treble = 0;
    for (let i = 0; i < sampleCount; i += 1) {
      const value = pass.spectrum[i];
      if (i < lowEnd) bass += value;
      else if (i < midEnd) mid += value;
      else treble += value;
    }
    uniform.uBass.value = bass / lowEnd;
    uniform.uMid.value = mid / Math.max(1, midEnd - lowEnd);
    uniform.uTreble.value = treble / Math.max(1, sampleCount - midEnd);

    // The reference's `curRad` is a radius in item space, and preScaling divides
    // by the same transform as the samples, so the disc reads as a fraction of
    // the item's height rather than growing with scaleMultiplier. Keep the
    // parameter as a percentage of half-height and convert to plane units here.
    uniform.uLayerIndex.value = index;
    uniform.uLayerCount.value = Math.max(1, count);
    // The reference's `curRad` is a radius in item space, and the item is scaled
    // by `scaleMultiplier` as a whole. That zoom already reaches the shader
    // through `uScaleMul`, so dividing by it here would cancel the reference's
    // audio reaction; only the layer's own scale belongs in this conversion.
    const planeScale = Math.max(0.01, layer.scale);
    uniform.uBaseRadius.value = (this.readNumber("channel.baseRadius") / 100) * 0.5 / planeScale;
    uniform.uContourWidth.value = this.readNumber("channel.contourWidth") / 100;

    // SkSL runtime-effect uniforms. u_time drives animated shaders; the colour
    // pair follows the layer's own colours since the export does not define
    // what u_col1/u_col2 mean beyond being per-layer.
    uniform.u_time.value = time;
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    (uniform.u_resolution.value as THREE.Vector2).set(resolution.x, resolution.y);
    // SkSL contract: u_amt is the deprecated name for u_audio_cumulative.
    uniform.u_amt.value = this.cumulativeData;
    uniform.u_audio_cumulative.value = this.cumulativeData;
    uniform.u_audio_current.value = this.currentData;
    (uniform.u_col1.value as THREE.Vector4).set(...rgbOf(layer.colorFrom), 1);
    (uniform.u_col2.value as THREE.Vector4).set(...rgbOf(layer.colorTo, [0, 0, 0]), 1);
    uniform.uMirror.value = this.mirror ? 1 : 0;
    uniform.uColorShift.value = (this.readNumber("effects.colorShift") / 100) * Math.PI * 2;
    uniform.uGain.value = this.readNumber("effects.gain");
    uniform.uOpacity.value = (this.readNumber("behaviour.opacity") / 100) * (this.visible ? 1 : 0);
    // The spectrum plane is 3.6 x 1.6 units, so this is the aspect that keeps a
    // Circle spectrum circular on screen. It was hardcoded to 16:9, which drew
    // circles as ellipses.
    uniform.uAspect.value = 3.6 / 1.6;

    uniform.uHeight.value = this.readNumber("behaviour.height") / 100;
    uniform.uDot.value = this.readNumber("behaviour.dotSize") * 0.006;
    uniform.uFeather.value = this.readNumber("behaviour.feather") / 100;
    uniform.uLineWidth.value = this.readNumber("behaviour.lineWidth");
    uniform.uDownsample.value = Math.max(1, this.readNumber("behaviour.downsample"));
    uniform.uRotation.value = (this.rotationDegrees() / 180) * Math.PI;
    uniform.uScaleMul.value = this.readNumber("transform.scaleMultiplier") / 100;
    (uniform.uTexPos.value as THREE.Vector2).set(
      this.readNumber("transform.textureX") / 100,
      this.readNumber("transform.textureY") / 100,
    );
    (uniform.uTexScale.value as THREE.Vector2).set(
      Math.max(0.05, this.readNumber("transform.textureScaleX") / 100),
      Math.max(0.05, this.readNumber("transform.textureScaleY") / 100),
    );

    // Per-layer colour. "Shader" layers draw with their own fragment source
    // (see applyLayerShader); the solid colour below is what they fall back to
    // when that source is missing or does not compile.
    const fromTo = layer.colorType === "From-to";
    const gradient = fromTo
      ? {
          stops: [rgbOf(layer.colorFrom, [1, 0, 0]), rgbOf(layer.colorTo, [0, 0, 0])],
          count: 2,
        }
      : layerGradient(layer);
    uniform.uColorType.value =
      layer.colorType === "From-to" ? 2 : layer.colorType === "Gradient" ? 1 : 0;
    uniform.uBaseOn.value =
      layer.baseOn === "Y-Position"
        ? 1
        : layer.baseOn === "X-Position"
          ? 2
          : layer.baseOn === "Distance from center"
            ? 3
            : 0;
    (uniform.uColorSolid.value as THREE.Vector3).set(...rgbOf(layer.color));
    uniform.uColorMix.value = clampNumber(layer.colorMix, 0, 1);
    const stopUniforms = [uniform.uGrad0, uniform.uGrad1, uniform.uGrad2, uniform.uGrad3];
    stopUniforms.forEach((stop, slot) => {
      (stop.value as THREE.Vector3).set(
        ...(gradient.stops[Math.min(slot, gradient.stops.length - 1)] ?? SPECTRUM_DEFAULT_COLOR),
      );
    });
    uniform.uGradCount.value = gradient.count;

    // Per-layer transform and contribution.
    uniform.uLayerScale.value = Math.max(0.01, layer.scale);
    uniform.uLayerRotation.value = (layer.rotation / 180) * Math.PI;
    uniform.uLayerAlpha.value = clampNumber(layer.alpha, 0, 1);
    uniform.uLayerGain.value = Math.max(0, layer.multiplier) * analyzerAmplitude;
    uniform.uBlur.value = clampNumber(layer.blurAmount, 0, 1);

    // Ceiling is stored in the reference's units; our band data is normalised.
    uniform.uCeiling.value = Math.max(0, layer.ceiling) / REFERENCE_VALUE_SCALE;

    // The object-level "Global shadow" toggle stays the master switch so a
    // default layer (shadowAlpha 1, shadowScale 0.01) does not gain a shadow.
    // Per-layer values then scale the shadow, and the object alpha/scale/offset
    // controls still modulate it. shadowScale is normalised so its schema
    // default 0.01 maps to the previous 100% object scale.
    // The shadow is a property of the composited item, so it is drawn once, by
    // the last layer, rather than once per layer.
    uniform.uShadowOn.value =
      index >= count - 1 &&
      this.readNumber("channel.shadow") > 0.5 &&
      layer.shadowAlpha > 0.001 &&
      layer.shadowScale > 0.0001
        ? 1
        : 0;
    uniform.uShadowAlpha.value =
      clampNumber(layer.shadowAlpha, 0, 1) *
      (this.readNumber("channel.shadowAlpha") / 100) *
      SHADOW_ALPHA_SCALE;
    // Per-layer shadow scale arrives in two conventions: the schema default is
    // 0.01 (fraction of the object scale) while exported presets carry 1 (a plain
    // multiplier). Normalise both to "1 = object scale", then apply the object
    // percentage. Multiplying the raw 1 by 100 produced a 100x blur.
    const layerShadow =
      layer.shadowScale < 0.1 && layer.shadowScale > 0
        ? layer.shadowScale / 0.01
        : layer.shadowScale;
    uniform.uShadowScale.value = clampNumber(
      layerShadow * (this.readNumber("channel.shadowScale") / 100),
      0.05,
      4,
    );
    (uniform.uShadowColor.value as THREE.Vector3).set(...rgbOf(layer.shadowColor, [1, 1, 1]));
    (uniform.uShadowOffset.value as THREE.Vector2).set(
      this.readNumber("channel.shadowX") / 100,
      this.readNumber("channel.shadowY") / 100,
    );
    // Sigma is authored in output pixels; convert to plane units the same way
    // the base radius is converted.
    const shadowHalfHeight = Math.max(1, resolution.y * 0.5);
    (uniform.uShadowBlur.value as THREE.Vector2).set(
      ((this.readNumber("channel.shadowSigmaX") * SHADOW_SIGMA_SCALE) / shadowHalfHeight) * 0.5 / planeScale,
      ((this.readNumber("channel.shadowSigmaY") * SHADOW_SIGMA_SCALE) / shadowHalfHeight) * 0.5 / planeScale,
    );

    uniform.uCircleSize.value = Math.max(0.02, this.readNumber("channel.circleSize") / 100);
    (uniform.uCircleColor.value as THREE.Color).set(this.circleColor);
    uniform.uFillCircle.value = this.readNumber("channel.fillCircle") > 0.5 ? 1 : 0;
    uniform.uClipCircle.value = this.readNumber("channel.clipCircle") > 0.5 ? 1 : 0;
    uniform.uConnect.value = this.readNumber("channel.connect") > 0.5 ? 1 : 0;
    uniform.uAA.value = this.readNumber("channel.aa") > 0.5 ? 1 : 0;
    uniform.uAspectFix.value = this.readNumber("channel.aspectFix") > 0.5 ? 1 : 0;

    uniform.uHasImage.value = texture ? 1 : 0;
    if (texture) uniform.uImage.value = texture;
    uniform.uImageSize.value = Math.max(0.05, this.readNumber("channel.imageSize") / 100);
    uniform.uCircularImage.value = this.readNumber("channel.circularImage") > 0.5 ? 1 : 0;

    const scale = this.readNumber("behaviour.scale") / 100;
    const width = this.readNumber("transform.width") / 100;
    const height = this.readNumber("transform.height") / 100;
    pass.mesh.visible = true;
    pass.mesh.scale.set(scale * width, scale * height, 1);
    pass.mesh.position.x = (this.readNumber("transform.x") / 100) * 1.8;
    pass.mesh.position.y = (this.readNumber("transform.y") / 100) * 0.8;
    // Coplanar passes need a stable paint order: the reference draws layer 0
    // first and layer n last, so later layers cover earlier ones. The node's own
    // rank is folded in so a Spectrum still sits correctly among other items.
    pass.mesh.renderOrder = (this.group.renderOrder || 0) * 100 + index;
    // Coplanar passes need distinct depths so depth testing keeps layer order.
    pass.mesh.position.z = this.z + index * 0.0001;
  }

  /**
   * The shader bank normalises every analyser to 0..1; the decompiled path
   * renderer adds band values directly to `curRad` in the reference's units.
   */
  private referenceBands(values: Float32Array): Float32Array {
    const bands = new Float32Array(values.length);
    for (let index = 0; index < values.length; index += 1) {
      bands[index] = values[index] * REFERENCE_VALUE_SCALE;
    }
    return bands;
  }

  /**
   * Analyzer a layer reads. The reference's layer default is the project's
   * permanent Default analyzer (`u()` in the spectrum module:
   * `{ ...layerDefaults, audioAnalyzer: c.n.DEFAULT }`), and its `update` reads
   * `t.audioAnalyzerData[layer.audioAnalyzer]` unconditionally. A layer without
   * its own binding therefore follows that default - never the shared
   * `spectrum()` series, which the reference never feeds to a spectrum.
   * Built-in presets leave `audioAnalyzer` null, so this is the difference
   * between them drawing a real analyzer and drawing the shared FFT's
   * low-bin plateau.
   */
  private layerAnalyzer(layer: SpectrumLayer | null): string | null {
    return (
      layer?.audioAnalyzer ??
      this.ctx.defaultAnalyzerId?.() ??
      this.analyzerId ??
      null
    );
  }

  /** The item's own analyzer (its `spectrumData` series), then the default. */
  private itemAnalyzer(): string | null {
    return this.analyzerId ?? this.ctx.defaultAnalyzerId?.() ?? null;
  }

  /** Native-length band series for a layer, 0..1 in the shader's units. */
  private bandsFor(layer: SpectrumLayer | null): Float32Array | null {
    const analyzerId = this.layerAnalyzer(layer);
    if (!analyzerId) return null;
    return (
      this.ctx.spectrumBandsFor?.(analyzerId) ??
      this.ctx.spectrumFor?.(analyzerId) ??
      null
    );
  }

  /** 256-slot series for a layer, used by the GPU pass uniforms. */
  private slotsFor(layer: SpectrumLayer | null): Float32Array | null {
    const analyzerId = this.layerAnalyzer(layer);
    if (!analyzerId) return null;
    return this.ctx.spectrumFor?.(analyzerId) ?? null;
  }

  /** 256-slot item-level series, the fallback when no analyzer can be found. */
  private itemSlots(): Float32Array | null {
    const analyzerId = this.itemAnalyzer();
    if (!analyzerId) return null;
    return this.ctx.spectrumFor?.(analyzerId) ?? null;
  }

  /** Per-layer band series for the Canvas2D renderer. */
  private pathLayers(layers: readonly SpectrumLayer[]): Array<
    SpectrumLayer & { bands: Float32Array }
  > {
    return layers.map((layer) => {
      const analyzer = this.bandsFor(layer);
      const bands = this.referenceBands(analyzer ?? this.spectrumData);
      // Reference `update`: `r = r.map(v => v > layer.ceiling ? layer.ceiling : v)`.
      if (layer.ceiling > 0) {
        for (let index = 0; index < bands.length; index += 1) {
          if (bands[index] > layer.ceiling) bands[index] = layer.ceiling;
        }
      }
      return { ...layer, bands };
    });
  }

  /** Item rotation in degrees, including a preset's constant spin. */
  private rotationDegrees(): number {
    const elapsed = Math.max(0, this.spinTime - this.start);
    return this.readNumber("transform.rotation") + this.spinSpeed * elapsed;
  }

  private pathSettings(): PathSettings {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    return {
      renderWidth: resolution.x,
      renderHeight: resolution.y,
      spectrumType: this.type,
      drawType: this.draw,
      fillStyle: this.fillStyle,
      mirrorHorizontal: this.mirror,
      stretchToEnd: this.stretchToEnd,
      repeatPointsOnPath: this.repeatPointsOnPath,
      closeLine: this.closeLine,
      moveBack: this.moveBack,
      spacing: this.spacing,
      customPath: this.customPath,
      smoothStartAndEnd: this.smoothStartAndEnd,
      smoothingWidth: this.smoothingWidth,
      smoothingPasses: this.smoothingPasses,
      dotSize: this.readNumber("behaviour.dotSize"),
      downsample: Math.max(1, this.readNumber("behaviour.downsample")),
      clipCircle: this.readNumber("channel.clipCircle") > 0.5,
      clipSize: this.clipSize,
      height: this.readNumber("behaviour.height"),
      lineWidth: this.readNumber("behaviour.lineWidth"),
      lineCap: this.lineCap,
      pathEffect: this.pathEffect,
      dashOffset: this.dashOffset,
      opacity: this.readNumber("behaviour.opacity"),
      positionX: this.positionX,
      positionY: this.positionY,
      scaleX: this.scaleX,
      scaleY: this.scaleY,
      rotation: this.rotationDegrees(),
      scaleMultiplier: this.referenceScaleMultiplier,
      globalShadow: this.readNumber("channel.shadow") > 0.5,
      globalShadowScale: this.readNumber("channel.shadowScale"),
      globalShadowAlpha: this.readNumber("channel.shadowAlpha"),
      globalShadowSigmaX: this.readNumber("channel.shadowSigmaX"),
      globalShadowSigmaY: this.readNumber("channel.shadowSigmaY"),
      fillCircle: this.readNumber("channel.fillCircle") > 0.5,
      circleSize: this.readNumber("channel.circleSize") / 100,
      circleColor: this.circleColor,
      circularImage: this.readNumber("channel.circularImage") > 0.5,
      imageSize: this.readNumber("channel.imageSize") / 100,
    };
  }

  sync(time: number): void {
    this.spinTime = time;
    // The item-level series (GPU pass fallback, shader `uMean`, energy) follows
    // the item's analyser, then the project's Default analyser. Copying
    // `ctx.spectrum()` here read the editor's own log-spaced FFT, whose first
    // ~26 bands all land in the same bin, so unbound layers and the GPU fallback
    // saw a flat plateau instead of the audio.
    const itemSlots = this.itemSlots();
    if (itemSlots) {
      this.spectrumData.set(itemSlots.subarray(0, this.spectrumData.length));
    } else {
      const spectrum = this.ctx.spectrum();
      this.spectrumData.set(spectrum.subarray(0, this.spectrumData.length));
    }

    // The reference feeds custom shaders two scalars from its point pipeline:
    // `currentData` is the mean of the last layer's points (after
    // multiplier * spectrumHeight and downsampling) and `cumulativeData` is a
    // running sum of that mean divided by 5000.
    const downsample = Math.max(1, this.readNumber("behaviour.downsample"));
    const heightFactor = this.readNumber("behaviour.height") / 100;
    let energy = 0;
    for (const layer of this.layers) {
      const analyzer = this.bandsFor(layer);
      const bands = this.referenceBands(analyzer ?? this.spectrumData);
      const ceiling = layer.ceiling > 0 ? layer.ceiling : Infinity;
      for (let index = 0; index < bands.length; index += 1) {
        if (bands[index] > ceiling) bands[index] = ceiling;
      }
      const points = spectrumPoints(bands, downsample, layer.multiplier * heightFactor);
      let sum = 0;
      for (let index = 0; index < points.length; index += 1) sum += points[index];
      energy = points.length > 0 ? sum / points.length : 0;
    }
    this.currentData = energy;
    this.cumulativeData += energy / 5000;

    const wave = this.ctx.waveform();
    this.waveData.set(wave.subarray(0, this.waveData.length));

    let texture = this.assetId ? this.ctx.texture(this.assetId) : null;

    // Remote link source: load once per URL, then reuse the texture.
    if (!texture && this.imageUrl) {
      if (this.urlPending !== this.imageUrl) {
        this.urlPending = this.imageUrl;
        this.urlTexture?.dispose();
        this.urlTexture = null;
        const pendingUrl = this.imageUrl;
        new THREE.TextureLoader().load(
          this.imageUrl,
          (loaded) => {
            if (this.imageUrl !== pendingUrl) {
              loaded.dispose();
              return;
            }
            loaded.colorSpace = THREE.NoColorSpace;
            this.urlTexture = loaded;
          },
          undefined,
          () => {
            if (this.imageUrl === pendingUrl) this.urlTexture = null;
          },
        );
      } else if (this.urlTexture) {
        texture = this.urlTexture;
      }
    }

    const enabled = this.layers.filter((layer) => layer.enabled);
    const activeShaders = new Set(
      enabled.filter((layer) => layer.colorType === "Shader").map((layer) => layer.id),
    );
    this.pathRenderer?.retainShaderLayers(this.pathMode ? activeShaders : new Set());
    if (this.pathMode && this.pathRenderer && this.pathMesh) {
      this.pathMesh.visible = true;
      // The reference draws the spectrum straight onto the render surface
      // (CanvasKit) and composites it 1:1, so the texture is the render size and
      // the quad is the camera's full viewport. The old 3.6x1.6 quad drew the
      // path 20% smaller than the reference.
      const renderSize = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
      this.pathRenderer.setRenderScale(this.renderScale);
      this.pathRenderer.setSize(renderSize.x, renderSize.y);
      const frameAspect = renderSize.x / Math.max(1, renderSize.y);
      const geometry = this.pathMesh.geometry as THREE.PlaneGeometry;
      if (Math.abs(geometry.parameters.width - 2 * frameAspect) > 0.001) {
        geometry.dispose();
        this.pathMesh.geometry = new THREE.PlaneGeometry(2 * frameAspect, 2);
      }
      this.pathRenderer.draw(
        this.pathSettings(),
        this.pathLayers(enabled),
        (texture?.image as CanvasImageSource | undefined) ?? null,
        time,
        this.cumulativeData,
        this.currentData,
      );
      for (const pass of this.layerPasses) pass.mesh.visible = false;
      return;
    }
    if (this.pathMesh) this.pathMesh.visible = false;

    this.ensureLayerPasses(enabled.length);
    enabled.forEach((layer, index) => {
      this.syncLayerPass(this.layerPasses[index], layer, index, enabled.length, texture, time);
    });
    for (let index = enabled.length; index < this.layerPasses.length; index += 1) {
      this.layerPasses[index].mesh.visible = false;
    }

    // Drop failures for layers that are no longer enabled Shader layers, so the
    // inspector never reports a stale fallback.
    for (const id of this.shaderErrors.keys()) {
      if (!activeShaders.has(id)) this.shaderErrors.delete(id);
    }
  }

  /** Current parameter set, in the same shape a preset stores. */
  readParams(): SpectrumParams {
    return {
      type: this.type,
      draw: this.draw,
      fillStyle: this.fillStyle,
      bands: this.bands,
      gain: this.readNumber("effects.gain"),
      colorShift: this.readNumber("effects.colorShift"),
      mirror: this.mirror,
      smoothing: this.readNumber("effects.smoothing"),
      opacity: this.readNumber("behaviour.opacity"),
      height: this.readNumber("behaviour.height"),
      dotSize: this.readNumber("behaviour.dotSize"),
      feather: this.readNumber("behaviour.feather"),
      downsample: this.readNumber("behaviour.downsample"),
      circularImage: this.readNumber("channel.circularImage") > 0.5,
      imageSize: this.readNumber("channel.imageSize"),
      imageUrl: this.imageUrl ?? undefined,
      contourColors: this.layers.slice(0, -1).map((layer) => layer.color),
      color: this.layers[this.layers.length - 1]?.color,
      baseRadius: this.readNumber("channel.baseRadius"),
      contourWidth: this.readNumber("channel.contourWidth"),
      fillCircle: this.readNumber("channel.fillCircle") > 0.5,
      clipCircle: this.readNumber("channel.clipCircle") > 0.5,
      circleSize: this.readNumber("channel.circleSize"),
      scaleMultiplier: this.readNumber("transform.scaleMultiplier"),
      spinSpeed: this.spinSpeed,
      shadowEnabled: this.readNumber("channel.shadow") > 0.5,
      shadowScale: this.readNumber("channel.shadowScale"),
      shadowAlpha: this.readNumber("channel.shadowAlpha"),
    };
  }

  /** Applies any subset of parameters, leaving the rest untouched. */

  applyParams(params: Partial<SpectrumParams>): void {
    if (params.type) this.type = params.type;
    if (params.draw) this.draw = params.draw;
    if (params.fillStyle) this.fillStyle = params.fillStyle;
    if (params.bands !== undefined) this.bands = params.bands;
    if (params.mirror !== undefined) this.mirror = params.mirror;
    if (params.scale !== undefined) this.objectMapping.set("behaviour.scale", params.scale);
    if (params.gain !== undefined) this.objectMapping.set("effects.gain", params.gain);
    if (params.colorShift !== undefined) {
      this.objectMapping.set("effects.colorShift", params.colorShift);
    }
    if (params.smoothing !== undefined) {
      this.objectMapping.set("effects.smoothing", params.smoothing);
    }
    if (params.opacity !== undefined) this.objectMapping.set("behaviour.opacity", params.opacity);
    if (params.height !== undefined) this.objectMapping.set("behaviour.height", params.height);
    if (params.dotSize !== undefined) this.objectMapping.set("behaviour.dotSize", params.dotSize);
    if (params.feather !== undefined) this.objectMapping.set("behaviour.feather", params.feather);
    if (params.downsample !== undefined) {
      this.objectMapping.set("behaviour.downsample", params.downsample);
    }
    if (params.circularImage !== undefined) {
      this.objectMapping.set("channel.circularImage", params.circularImage ? 1 : 0);
    }
    if (params.imageSize !== undefined) {
      this.objectMapping.set("channel.imageSize", params.imageSize);
    }
    // A preset replaces the look wholesale: without an image of its own it must
    // not inherit the previous preset's texture (e.g. Trap Motion's).
    if (params.imageUrl === undefined) {
      this.imageUrl = null;
      this.objectMapping.set("channel.circularImage", 0);
    }
    if (params.imageUrl !== undefined) this.imageUrl = params.imageUrl || null;
    if (params.contourColors !== undefined) {
      const colors = [...params.contourColors, params.color ?? "#ffffff"];
      this.layers.splice(0, this.layers.length);
      colors.forEach((color, index) => {
        this.layers.push(createSpectrumLayer(index, color));
      });
      this.color = colors[colors.length - 1];
    }
    if (params.baseRadius !== undefined) {
      this.objectMapping.set("channel.baseRadius", params.baseRadius);
    }
    if (params.contourWidth !== undefined) {
      this.objectMapping.set("channel.contourWidth", params.contourWidth);
    }
    if (params.fillCircle !== undefined) {
      this.objectMapping.set("channel.fillCircle", params.fillCircle ? 1 : 0);
    }
    if (params.clipCircle !== undefined) {
      this.objectMapping.set("channel.clipCircle", params.clipCircle ? 1 : 0);
    }
    if (params.circleSize !== undefined) {
      this.objectMapping.set("channel.circleSize", params.circleSize);
    }
    if (params.scaleMultiplier !== undefined) {
      this.objectMapping.set("transform.scaleMultiplier", params.scaleMultiplier);
    }
    if (params.spinSpeed !== undefined) this.spinSpeed = params.spinSpeed;
    if (params.shadowEnabled !== undefined) {
      this.objectMapping.set("channel.shadow", params.shadowEnabled ? 1 : 0);
    }
    if (params.shadowScale !== undefined) {
      this.objectMapping.set("channel.shadowScale", params.shadowScale);
    }
    if (params.shadowAlpha !== undefined) {
      this.objectMapping.set("channel.shadowAlpha", params.shadowAlpha);
    }
    if (params.shadowSigma !== undefined) {
      this.objectMapping.set("channel.shadowSigmaX", params.shadowSigma);
      this.objectMapping.set("channel.shadowSigmaY", params.shadowSigma);
    }
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        // Section names and order mirror the reference inspector, measured
        // 2026-10-27: General, Positioning & Size, Basics.
        { id: "behaviour", label: "General", kind: ContainerKind.Folder },
        { id: "transform", label: "Positioning & Size", kind: ContainerKind.Folder },
        { id: "effects", label: "Basics", kind: ContainerKind.Folder },
      ],
      controllers: [
        // Order below is the reference inspector's, measured 2026-10-27.
        this.choose("behaviour.type", "Spectrum Type", {
          parentId: "behaviour",
          values: ["Circle", "Bars", "Custom", "Image"],
          get: () => this.type,
          set: (v) => {
            this.type = v as SpectrumType;
          },
        }),
        this.fileField("channel.imageFile", "File", {
          parentId: "behaviour",
          get: () => this.assetId ?? "",
          set: (v) => {
            this.assetId = v || null;
          },
        }),
        this.text("channel.imageLink", "Link", {
          parentId: "behaviour",
          get: () => this.imageUrl ?? "",
          set: (v) => {
            this.imageUrl = v.trim() || null;
          },
        }),
        this.fileField("channel.imageUpload", "Upload", {
          parentId: "behaviour",
          get: () => this.assetId ?? "",
          set: (v) => {
            this.assetId = v || null;
          },
        }),
        this.choose("behaviour.fillStyle", "Spectrum style", {
          parentId: "behaviour",
          values: ["Fill", "Stroke"],
          get: () => this.fillStyle,
          set: (v) => {
            this.fillStyle = v as SpectrumFillStyle;
          },
        }),
        this.slider("behaviour.height", "Spectrum height", {
          parentId: "behaviour",
          min: 0,
          max: 300,
          unit: "%",
          get: () => this.readNumber("behaviour.height"),
          set: (v) => this.objectMapping.set("behaviour.height", v),
        }),
        this.slider("channel.imageSize", "Image size", {
          parentId: "behaviour",
          min: 10,
          max: 300,
          unit: "%",
          get: () => this.readNumber("channel.imageSize"),
          set: (v) => this.objectMapping.set("channel.imageSize", v),
        }),
        this.toggle("channel.circularImage", "Circular image", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.circularImage") > 0.5,
          set: (v) => this.objectMapping.set("channel.circularImage", v ? 1 : 0),
        }),
        this.toggle("channel.fillCircle", "Fill circle", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.fillCircle") > 0.5,
          set: (v) => this.objectMapping.set("channel.fillCircle", v ? 1 : 0),
        }),
        this.slider("channel.circleSize", "Circle size", {
          parentId: "behaviour",
          // Percent of the frame. The reference stores 1.0 and Trap Motion
          // ships 100, so the old 60 ceiling could not hold our own value.
          min: 2,
          max: 200,
          unit: "%",
          get: () => this.readNumber("channel.circleSize"),
          set: (v) => this.objectMapping.set("channel.circleSize", v),
        }),
        this.colorField("channel.circleColor", "Circle Color", {
          parentId: "behaviour",
          get: () => this.circleColor,
          set: (v) => {
            this.circleColor = v;
          },
        }),
        this.toggle("behaviour.mirror", "Mirror", {
          parentId: "behaviour",
          get: () => this.mirror,
          set: (v) => {
            this.mirror = v;
          },
        }),
        this.toggle("channel.clipCircle", "Clip circle", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.clipCircle") > 0.5,
          set: (v) => this.objectMapping.set("channel.clipCircle", v ? 1 : 0),
        }),
        this.choose("behaviour.draw", "Draw type", {
          parentId: "behaviour",
          values: ["Curve", "Line", "Plexus", "Point"],
          get: () => this.draw,
          set: (v) => {
            this.draw = v as SpectrumDraw;
          },
        }),
        this.slider("behaviour.dotSize", "Dot size", {
          parentId: "behaviour",
          min: 1,
          max: 12,
          step: 0.5,
          get: () => this.readNumber("behaviour.dotSize"),
          set: (v) => this.objectMapping.set("behaviour.dotSize", v),
        }),
        this.slider("behaviour.feather", "Feather effect", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          unit: "%",
          get: () => this.readNumber("behaviour.feather"),
          set: (v) => this.objectMapping.set("behaviour.feather", v),
        }),
        this.choose("behaviour.downsample", "Downsample", {
          parentId: "behaviour",
          values: ["1", "2", "4", "8"],
          get: () => String(this.readNumber("behaviour.downsample")),
          set: (v) => this.objectMapping.set("behaviour.downsample", Number(v)),
        }),
        this.toggle("channel.connect", "Connect paths", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.connect") > 0.5,
          set: (v) => this.objectMapping.set("channel.connect", v ? 1 : 0),
        }),
        this.toggle("channel.aa", "Anti-aliasing", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.aa") > 0.5,
          set: (v) => this.objectMapping.set("channel.aa", v ? 1 : 0),
        }),
        this.toggle("channel.shadow", "Global shadow", {
          parentId: "behaviour",
          get: () => this.readNumber("channel.shadow") > 0.5,
          set: (v) => this.objectMapping.set("channel.shadow", v ? 1 : 0),
        }),
        this.slider("channel.shadowScale", "Shadow scale", {
          parentId: "behaviour",
          min: 10,
          max: 300,
          unit: "%",
          get: () => this.readNumber("channel.shadowScale"),
          set: (v) => this.objectMapping.set("channel.shadowScale", v),
        }),
        this.slider("channel.shadowAlpha", "Shadow alpha", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          unit: "%",
          get: () => this.readNumber("channel.shadowAlpha"),
          set: (v) => this.objectMapping.set("channel.shadowAlpha", v),
        }),
        // The reference's Shadow X / Y are blur sigmas, not offsets: measured
        // at 20 alongside scale 1 and alpha 1 (its globalShadowSigmaX/Y).
        this.slider("channel.shadowSigmaX", "Shadow X", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          step: 0.1,
          get: () => this.readNumber("channel.shadowSigmaX"),
          set: (v) => this.objectMapping.set("channel.shadowSigmaX", v),
        }),
        this.slider("channel.shadowSigmaY", "Shadow Y", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          step: 0.1,
          get: () => this.readNumber("channel.shadowSigmaY"),
          set: (v) => this.objectMapping.set("channel.shadowSigmaY", v),
        }),
        // Ours alone: the reference has no controls for these five. Bands live
        // on an Analyzer object there, and gain/smoothing/opacity are folded
        // into its layer model. Kept here, after the mirrored surface, rather
        // than removed, because the engine and the presets depend on them.
        this.slider("behaviour.bands", "Bands", {
          parentId: "behaviour",
          min: 8,
          max: 256,
          step: 1,
          get: () => this.bands,
          set: (v) => {
            this.bands = Math.round(v);
          },
        }),
        this.slider("effects.gain", "Gain", {
          parentId: "behaviour",
          min: 0,
          max: 4,
          step: 0.05,
          get: () => this.readNumber("effects.gain"),
          set: (v) => this.objectMapping.set("effects.gain", v),
        }),
        this.slider("effects.colorShift", "Color shift", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          unit: "%",
          get: () => this.readNumber("effects.colorShift"),
          set: (v) => this.objectMapping.set("effects.colorShift", v),
        }),
        this.slider("effects.smoothing", "Smoothing", {
          parentId: "behaviour",
          min: 0,
          max: 95,
          unit: "%",
          get: () => this.readNumber("effects.smoothing"),
          set: (v) => this.objectMapping.set("effects.smoothing", v),
        }),
        this.slider("behaviour.opacity", "Opacity", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          unit: "%",
          get: () => this.readNumber("behaviour.opacity"),
          set: (v) => this.objectMapping.set("behaviour.opacity", v),
        }),
        this.slider("transform.textureX", "Texture Position X", {
          parentId: "transform",
          min: -100,
          max: 100,
          unit: "%",
          get: () => this.readNumber("transform.textureX"),
          set: (v) => this.objectMapping.set("transform.textureX", v),
        }),
        this.slider("transform.textureY", "Texture Position Y", {
          parentId: "transform",
          min: -100,
          max: 100,
          unit: "%",
          get: () => this.readNumber("transform.textureY"),
          set: (v) => this.objectMapping.set("transform.textureY", v),
        }),
        this.slider("transform.textureScaleX", "Texture Scale X", {
          parentId: "transform",
          min: 10,
          max: 300,
          unit: "%",
          get: () => this.readNumber("transform.textureScaleX"),
          set: (v) => this.objectMapping.set("transform.textureScaleX", v),
        }),
        this.slider("transform.textureScaleY", "Texture Scale Y", {
          parentId: "transform",
          min: 10,
          max: 300,
          unit: "%",
          get: () => this.readNumber("transform.textureScaleY"),
          set: (v) => this.objectMapping.set("transform.textureScaleY", v),
        }),
        this.slider("transform.rotation", "Rotation", {
          parentId: "transform",
          min: -180,
          max: 180,
          unit: "°",
          get: () => this.readNumber("transform.rotation"),
          set: (v) => this.objectMapping.set("transform.rotation", v),
        }),
        this.slider("transform.scaleMultiplier", "Scale multiplier", {
          parentId: "transform",
          min: 10,
          max: 300,
          unit: "%",
          get: () => this.readNumber("transform.scaleMultiplier"),
          set: (v) => this.objectMapping.set("transform.scaleMultiplier", v),
        }),
        this.toggle("channel.aspectFix", "Disable aspect scaling", {
          parentId: "transform",
          get: () => this.readNumber("channel.aspectFix") > 0.5,
          set: (v) => this.objectMapping.set("channel.aspectFix", v ? 1 : 0),
        }),
        // Ours alone (reference positions objects on the canvas instead).
        this.slider("behaviour.scale", "Scale", {
          parentId: "transform",
          min: 0,
          max: 400,
          unit: "%",
          get: () => this.readNumber("behaviour.scale"),
          set: (v) => this.objectMapping.set("behaviour.scale", v),
        }),
        this.slider("transform.x", "X", {
          parentId: "transform",
          min: -100,
          max: 100,
          unit: "%",
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Y", {
          parentId: "transform",
          min: -100,
          max: 100,
          unit: "%",
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.width", "Width", {
          parentId: "transform",
          min: 10,
          max: 200,
          unit: "%",
          get: () => this.readNumber("transform.width"),
          set: (v) => this.objectMapping.set("transform.width", v),
        }),
        this.slider("transform.height", "Height", {
          parentId: "transform",
          min: 10,
          max: 200,
          unit: "%",
          get: () => this.readNumber("transform.height"),
          set: (v) => this.objectMapping.set("transform.height", v),
        }),
        this.choose("basics.objectType", "Object type", {
          parentId: "effects",
          values: [this.typeLabel],
          get: () => this.typeLabel,
          set: () => void 0,
        }),
        this.text("basics.name", "Name", {
          parentId: "effects",
          get: () => this.name,
          set: (v) => {
            this.name = v;
            this.group.name = v;
          },
        }),
        this.slider("basics.start", "Time", {
          parentId: "effects",
          min: 0,
          max: 120,
          step: 0.01,
          unit: "s",
          get: () => this.start,
          set: (v) => {
            this.start = v;
          },
        }),
        this.toggle("basics.ignoreTimeSpan", "Ignore time span", {
          parentId: "effects",
          get: () => this.ignoreTimeSpan,
          set: (v) => {
            this.ignoreTimeSpan = v;
          },
        }),
        this.slider("basics.trackRow", "Track row", {
          parentId: "effects",
          min: 0,
          max: 8,
          step: 1,
          get: () => this.trackRow,
          set: (v) => {
            this.trackRow = Math.max(0, Math.round(v));
          },
        }),
      ],
    };
  }
}

/**
 * Basic geometry / light items from the reference's 3D and 2D primitive set.
 * These share transform controllers; item-specific controls are limited to the
 * properties the reference exposes for each primitive.
 */
export class PrimitiveNode extends SceneNode {
  readonly kind: NodeKind;
  readonly typeLabel: string;
  readonly primitive: "cube" | "square" | "plane" | "point-light";
  override readonly is3D: boolean;

  color = "#ffffff";
  opacity = 1;
  boxWidth = 100;
  boxHeight = 100;
  intensity = 1;
  distance = 1000;
  decay = 2;

  private mesh: THREE.Mesh | null = null;
  private material: THREE.MeshBasicMaterial | null = null;
  private light: THREE.PointLight | null = null;

  constructor(kind: NodeKind, name: string, ctx: NodeContext) {
    super(name, ctx);
    this.kind = kind;
    this.is3D = kind !== NodeKind.Square;
    this.primitive =
      kind === NodeKind.Cube
        ? "cube"
        : kind === NodeKind.Square
          ? "square"
          : kind === NodeKind.PointLight
            ? "point-light"
            : "plane";
    this.typeLabel =
      this.primitive === "cube"
        ? "Cube"
        : this.primitive === "square"
          ? "Square"
          : this.primitive === "point-light"
            ? "Point Light"
            : "Plane";
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("behaviour.opacity", 100);
    this.objectMapping.set("behaviour.scale", 100);
    this.objectMapping.set("behaviour.rotation", 0);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set(
      "transform.z",
      this.primitive === "plane" ? -50 : this.primitive === "point-light" ? -500 : 0,
    );
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
    this.objectMapping.set("basics.shy", 0);
  }

  protected build(): void {
    if (this.primitive === "point-light") {
      const light = new THREE.PointLight(this.color, this.intensity, this.distance, this.decay);
      this.light = light;
      this.group.add(light);
      return;
    }

    // Reference `Plane` (module 1373) is `PlaneBufferGeometry(1024, 1024)` in
    // the 1000-unit stage, so its world size is 2.05 * 1024 / 1000 and it is
    // square, not the frame's 16:9 aspect.
    const planeSize = 2.05 * (1024 / 1000);
    const geometry =
      this.primitive === "cube"
        ? new THREE.BoxGeometry(1, 1, 1)
        : new THREE.PlaneGeometry(planeSize, planeSize, 32, 32);
    // A fully opaque plane is a background: the reference leaves it
    // `transparent:true`, but its renderer sorts transparent meshes
    // back-to-front, so a plane at z=-500 paints before the text at z=0. Rea
    // orders items by their node rank instead, which put this mask's white
    // plane between the two text lines and erased the first one
    // (milky-cubiq's "Text"). An opacity-1 plane has no blending to do, so
    // painting it in the opaque pass restores the reference's stacking without
    // touching the depth-sorted transparent items.
    this.material = new THREE.MeshBasicMaterial({
      side: THREE.DoubleSide,
      transparent: this.opacity < 0.999,
      opacity: this.opacity,
    });
    setUnmanagedColor(this.material.color, this.color);
    this.mesh = new THREE.Mesh(geometry, this.material);
    if (this.primitive === "plane") this.mesh.position.z = -0.5;
    this.group.add(this.mesh);
  }

  sync(_time: number): void {
    const scale = this.readNumber("behaviour.scale") / 100;
    const sx = (this.readNumber("transform.scaleX") / 100) * scale;
    const sy = (this.readNumber("transform.scaleY") / 100) * scale;
    const sz = (this.readNumber("transform.scaleZ") / 100) * scale;
    const opacity = this.readNumber("behaviour.opacity") / 100;
    const x = this.readNumber("transform.x") / 100;
    const y = this.readNumber("transform.y") / 100;
    const z = this.z + this.readNumber("transform.z") / 100;

    if (this.light) {
      setUnmanagedColor(this.light.color, this.color);
      this.light.intensity = this.intensity;
      this.light.distance = this.distance;
      this.light.decay = this.decay;
      this.light.position.set(x, y, z);
      this.light.visible = this.visible;
      return;
    }

    if (!this.mesh || !this.material) return;
    setUnmanagedColor(this.material.color, this.color);
    this.material.transparent = opacity < 0.999;
    this.material.opacity = opacity * (this.visible ? 1 : 0);
    this.material.visible = this.material.opacity > 0.001;
    this.mesh.position.set(x, y, z);
    this.mesh.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      ((this.readNumber("behaviour.rotation") + this.readNumber("transform.rotZ")) * Math.PI) /
        180,
    );
    if (this.primitive === "square") {
      this.mesh.scale.set(
        Math.max(0.001, (this.boxWidth / 100) * sx),
        Math.max(0.001, (this.boxHeight / 100) * sy),
        1,
      );
    } else {
      this.mesh.scale.set(sx, sy, sz);
    }
  }

  override createControllerSetups(): ControllerSetups {
    const containers = [
      { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
      { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
    ];
    const controllers: PropertyDescriptor[] = [
      this.slider("transform.x", "Position X", {
        parentId: "transform",
        min: -200,
        max: 200,
        get: () => this.readNumber("transform.x"),
        set: (v) => this.objectMapping.set("transform.x", v),
      }),
      this.slider("transform.y", "Position Y", {
        parentId: "transform",
        min: -200,
        max: 200,
        get: () => this.readNumber("transform.y"),
        set: (v) => this.objectMapping.set("transform.y", v),
      }),
      this.slider("transform.z", "Position Z", {
        parentId: "transform",
        min: -1000,
        max: 1000,
        get: () => this.readNumber("transform.z"),
        set: (v) => this.objectMapping.set("transform.z", v),
      }),
      this.slider("transform.rotX", "Rotation X", {
        parentId: "transform",
        min: -360,
        max: 360,
        unit: "°",
        get: () => this.readNumber("transform.rotX"),
        set: (v) => this.objectMapping.set("transform.rotX", v),
      }),
      this.slider("transform.rotY", "Rotation Y", {
        parentId: "transform",
        min: -360,
        max: 360,
        unit: "°",
        get: () => this.readNumber("transform.rotY"),
        set: (v) => this.objectMapping.set("transform.rotY", v),
      }),
      this.slider("transform.rotZ", "Rotation Z", {
        parentId: "transform",
        min: -360,
        max: 360,
        unit: "°",
        get: () => this.readNumber("transform.rotZ"),
        set: (v) => this.objectMapping.set("transform.rotZ", v),
      }),
      this.slider("transform.scaleX", "Scale X", {
        parentId: "transform",
        min: 0,
        max: 500,
        get: () => this.readNumber("transform.scaleX"),
        set: (v) => this.objectMapping.set("transform.scaleX", v),
      }),
      this.slider("transform.scaleY", "Scale Y", {
        parentId: "transform",
        min: 0,
        max: 500,
        get: () => this.readNumber("transform.scaleY"),
        set: (v) => this.objectMapping.set("transform.scaleY", v),
      }),
      this.slider("behaviour.opacity", "Opacity", {
        parentId: "behaviour",
        min: 0,
        max: 100,
        unit: "%",
        get: () => this.readNumber("behaviour.opacity"),
        set: (v) => this.objectMapping.set("behaviour.opacity", v),
      }),
    ];

    if (this.primitive !== "point-light") {
      controllers.push(
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
      );
    }
    if (this.primitive === "square") {
      controllers.push(
        this.slider("basics.boxWidth", "Box width", {
          parentId: "behaviour",
          min: 0,
          max: 1000,
          step: 1,
          get: () => this.boxWidth,
          set: (v) => {
            this.boxWidth = v;
          },
        }),
        this.slider("basics.boxHeight", "Box height", {
          parentId: "behaviour",
          min: 0,
          max: 1000,
          step: 1,
          get: () => this.boxHeight,
          set: (v) => {
            this.boxHeight = v;
          },
        }),
      );
    }
    if (this.primitive === "point-light") {
      controllers.push(
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("behaviour.intensity", "Intensity", {
          parentId: "behaviour",
          min: 0,
          max: 50,
          get: () => this.intensity,
          set: (v) => {
            this.intensity = v;
          },
        }),
        this.slider("behaviour.distance", "Distance", {
          parentId: "behaviour",
          min: 0,
          max: 1000,
          get: () => this.distance,
          set: (v) => {
            this.distance = v;
          },
        }),
        this.slider("behaviour.decay", "Decay", {
          parentId: "behaviour",
          min: 0,
          max: 50,
          get: () => this.decay,
          set: (v) => {
            this.decay = v;
          },
        }),
      );
    }

    return { containers, controllers };
  }
}

/** 2D progress bar using the decompiled module 1376 shader. */
export class ProgressBarNode extends SceneNode {
  readonly kind = NodeKind.ProgressBar;
  readonly typeLabel = "Progress Bar";

  barType = "Line";
  lineDirection = "Left to Right";
  circleDirection = "Clockwise";
  autoProgress = true;
  manualProgress = 0.5;
  fgColor = "#ffffff";
  bgColor = "#444444";
  fgOpacity = 1;
  bgOpacity = 0.35;
  length = 800;
  thickness = 40;
  radius = 300;
  cornerRadius = 20;
  circleStartAngle = 0;
  segments = 1;
  gap = 5;
  continuousSegments = false;
  skipSegmentGapsDuringProgress = false;
  circleConsistentGapThickness = false;

  private mesh!: THREE.Mesh;
  private material!: THREE.ShaderMaterial;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("behaviour.opacity", 100);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
  }

  protected build(): void {
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        uBarType: { value: 0 },
        uDirection: { value: 0 },
        uProgress: { value: 0 },
        uFgColor: { value: new THREE.Color(this.fgColor) },
        uBgColor: { value: new THREE.Color(this.bgColor) },
        uFgAlpha: { value: this.fgOpacity },
        uBgAlpha: { value: this.bgOpacity },
        uLength: { value: this.length },
        uThickness: { value: this.thickness },
        uRadius: { value: this.radius },
        uCornerRadius: { value: this.cornerRadius },
        uCircleStartAngle: { value: 0 },
        uSegments: { value: this.segments },
        uGap: { value: this.gap },
        uContinuousSegments: { value: 0 },
        uSkipSegmentGapsDuringProgress: { value: 0 },
        uCircleConsistentGapThickness: { value: 0 },
        uCanvasSize: { value: 1024 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: PROGRESS_BAR_SHADER,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2.05, 2.05), this.material);
    this.group.add(this.mesh);
  }

  sync(time: number): void {
    const direction =
      this.barType === "Line"
        ? Math.max(0, ["Left to Right", "Right to Left", "Top to Bottom", "Bottom to Top", "Center Horizontal", "Center Vertical"].indexOf(this.lineDirection))
        : Math.max(0, ["Clockwise", "Counter-Clockwise", "Center Expand"].indexOf(this.circleDirection));
    const progress = this.autoProgress
      ? Math.max(0, Math.min(1, (time - this.start) / Math.max(0.0001, this.duration)))
      : Math.max(0, Math.min(1, this.manualProgress));
    const opacity = this.readNumber("behaviour.opacity") / 100;
    const u = this.material.uniforms;
    u.uBarType.value = this.barType === "Line" ? 0 : 1;
    u.uDirection.value = direction;
    u.uProgress.value = progress;
    (u.uFgColor.value as THREE.Color).set(this.fgColor);
    (u.uBgColor.value as THREE.Color).set(this.bgColor);
    u.uFgAlpha.value = this.fgOpacity * opacity;
    u.uBgAlpha.value = this.bgOpacity * opacity;
    u.uLength.value = this.length;
    u.uThickness.value = this.thickness;
    u.uRadius.value = this.radius;
    u.uCornerRadius.value = this.cornerRadius;
    u.uCircleStartAngle.value = (this.circleStartAngle * Math.PI) / 180;
    u.uSegments.value = this.segments;
    u.uGap.value = this.gap;
    u.uContinuousSegments.value = this.continuousSegments ? 1 : 0;
    u.uSkipSegmentGapsDuringProgress.value = this.skipSegmentGapsDuringProgress ? 1 : 0;
    u.uCircleConsistentGapThickness.value = this.circleConsistentGapThickness ? 1 : 0;
    // The reference item base `positionChanged` writes `f(x, y, true)` straight
    // into the mesh position (module 22's `u`, `vizzy-main-25704ef2:9880`) and
    // its layer camera is the 1000-unit stage, so an item position is
    // `x * aspect / 500` in our 2-unit stage ΓÇö not the old percent-of-stage
    // `/100`. `chill`'s progress bars (the album card) sat at world x=-4.4,
    // five times too far out and fully off-frame.
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const frameAspect = resolution.x / Math.max(1, resolution.y);
    const landscape = frameAspect > 1;
    const unit = 2 / 1000;
    this.mesh.position.set(
      this.readNumber("transform.x") * unit * (landscape ? frameAspect : 1),
      this.readNumber("transform.y") * unit * (landscape ? 1 : frameAspect),
      this.z + this.readNumber("transform.z") * unit,
    );
    this.mesh.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      1,
    );
    this.mesh.visible = this.visible && opacity > 0.001;
  }

  override createControllerSetups(): ControllerSetups {
    const containers = [
      { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
      { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
      { id: "transform", label: "Transform", kind: ContainerKind.Folder },
    ];
    const controllers: PropertyDescriptor[] = [
      this.choose("appearance.barType", "Type", {
        parentId: "appearance",
        values: ["Line", "Circle"],
        get: () => this.barType,
        set: (v) => {
          this.barType = v;
        },
      }),
      this.choose("appearance.lineDirection", "Line direction", {
        parentId: "appearance",
        values: ["Left to Right", "Right to Left", "Top to Bottom", "Bottom to Top", "Center Horizontal", "Center Vertical"],
        get: () => this.lineDirection,
        set: (v) => {
          this.lineDirection = v;
        },
      }),
      this.choose("appearance.circleDirection", "Circle direction", {
        parentId: "appearance",
        values: ["Clockwise", "Counter-Clockwise", "Center Expand"],
        get: () => this.circleDirection,
        set: (v) => {
          this.circleDirection = v;
        },
      }),
      this.colorField("appearance.fgColor", "Progress color", {
        parentId: "appearance",
        get: () => this.fgColor,
        set: (v) => {
          this.fgColor = v;
        },
      }),
      this.slider("appearance.fgOpacity", "Progress opacity", {
        parentId: "appearance",
        min: 0,
        max: 1,
        step: 0.01,
        get: () => this.fgOpacity,
        set: (v) => {
          this.fgOpacity = v;
        },
      }),
      this.colorField("appearance.bgColor", "Background color", {
        parentId: "appearance",
        get: () => this.bgColor,
        set: (v) => {
          this.bgColor = v;
        },
      }),
      this.slider("appearance.bgOpacity", "Background opacity", {
        parentId: "appearance",
        min: 0,
        max: 1,
        step: 0.01,
        get: () => this.bgOpacity,
        set: (v) => {
          this.bgOpacity = v;
        },
      }),
      this.slider("appearance.length", "Line length", {
        parentId: "appearance",
        min: 10,
        max: 1000,
        step: 1,
        get: () => this.length,
        set: (v) => {
          this.length = v;
        },
      }),
      this.slider("appearance.thickness", "Thickness", {
        parentId: "appearance",
        min: 1,
        max: 200,
        step: 1,
        get: () => this.thickness,
        set: (v) => {
          this.thickness = v;
        },
      }),
      this.slider("appearance.radius", "Circle radius", {
        parentId: "appearance",
        min: 10,
        max: 600,
        step: 1,
        get: () => this.radius,
        set: (v) => {
          this.radius = v;
        },
      }),
      this.slider("appearance.cornerRadius", "Corner radius", {
        parentId: "appearance",
        min: 0,
        max: 100,
        get: () => this.cornerRadius,
        set: (v) => {
          this.cornerRadius = v;
        },
      }),
      this.slider("appearance.circleStartAngle", "Circle start angle", {
        parentId: "appearance",
        min: -180,
        max: 180,
        step: 1,
        unit: "°",
        get: () => this.circleStartAngle,
        set: (v) => {
          this.circleStartAngle = v;
        },
      }),
      this.slider("appearance.segments", "Segments", {
        parentId: "appearance",
        min: 1,
        max: 100,
        step: 1,
        get: () => this.segments,
        set: (v) => {
          this.segments = v;
        },
      }),
      this.slider("appearance.gap", "Segment gap", {
        parentId: "appearance",
        min: 0,
        max: 50,
        get: () => this.gap,
        set: (v) => {
          this.gap = v;
        },
      }),
      this.toggle("behaviour.autoProgress", "Auto progress", {
        parentId: "behaviour",
        get: () => this.autoProgress,
        set: (v) => {
          this.autoProgress = v;
        },
      }),
      this.slider("behaviour.manualProgress", "Manual progress", {
        parentId: "behaviour",
        min: 0,
        max: 1,
        step: 0.01,
        get: () => this.manualProgress,
        set: (v) => {
          this.manualProgress = v;
        },
      }),
      this.toggle("behaviour.continuousSegments", "Continuous segments", {
        parentId: "behaviour",
        get: () => this.continuousSegments,
        set: (v) => {
          this.continuousSegments = v;
        },
      }),
      this.toggle("behaviour.skipSegmentGapsDuringProgress", "Skip segment gaps", {
        parentId: "behaviour",
        get: () => this.skipSegmentGapsDuringProgress,
        set: (v) => {
          this.skipSegmentGapsDuringProgress = v;
        },
      }),
      this.toggle("behaviour.circleConsistentGapThickness", "Consistent gap thickness", {
        parentId: "behaviour",
        get: () => this.circleConsistentGapThickness,
        set: (v) => {
          this.circleConsistentGapThickness = v;
        },
      }),
      this.slider("transform.x", "Position X", {
        parentId: "transform",
        min: -200,
        max: 200,
        get: () => this.readNumber("transform.x"),
        set: (v) => this.objectMapping.set("transform.x", v),
      }),
      this.slider("transform.y", "Position Y", {
        parentId: "transform",
        min: -200,
        max: 200,
        get: () => this.readNumber("transform.y"),
        set: (v) => this.objectMapping.set("transform.y", v),
      }),
      this.slider("transform.scaleX", "Scale X", {
        parentId: "transform",
        min: 0,
        max: 500,
        get: () => this.readNumber("transform.scaleX"),
        set: (v) => this.objectMapping.set("transform.scaleX", v),
      }),
      this.slider("transform.scaleY", "Scale Y", {
        parentId: "transform",
        min: 0,
        max: 500,
        get: () => this.readNumber("transform.scaleY"),
        set: (v) => this.objectMapping.set("transform.scaleY", v),
      }),
    ];
    return { containers, controllers };
  }
}

/** 2D logo/image item using the decompiled module 1366 shader. */
export class LogoNode extends SceneNode {
  readonly kind = NodeKind.Logo;
  readonly typeLabel = "Logo";

  imageUrl = "";
  matPositionX = 0;
  matPositionY = 0;
  matScaleX = 1;
  matScaleY = 1;
  scaleMult = 1;
  rotation = 0;
  circleCutoff = 1;
  textureWrap = "Discard";
  width = 500;
  height = 500;
  /** Uploaded image aspect, the shader's square-UV correction (source default). */
  aspect = 1.6777;

  private mesh!: THREE.Mesh;
  private material!: THREE.ShaderMaterial;
  private texture: THREE.Texture | null = null;
  private pendingUrl = "";

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
  }

  protected build(): void {
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: null },
        transform1: { value: new THREE.Vector4() },
        transform2: { value: new THREE.Vector4() },
        resolution: { value: new THREE.Vector2(1920, 1080) },
        cutoff: { value: 1 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: LOGO_SHADER,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.material);
    this.group.add(this.mesh);
  }

  sync(_time: number): void {
    if (this.imageUrl && this.pendingUrl !== this.imageUrl) {
      this.pendingUrl = this.imageUrl;
      new THREE.TextureLoader().load(
        this.imageUrl,
        (texture) => {
          texture.colorSpace = THREE.NoColorSpace;
          texture.minFilter = THREE.LinearFilter;
          texture.magFilter = THREE.LinearFilter;
          texture.generateMipmaps = false;
          this.texture = texture;
          const image = texture.image as { width?: number; height?: number } | null;
          if (image?.width && image?.height) this.aspect = image.width / image.height;
        },
        undefined,
        () => {
          this.texture = null;
        },
      );
    }
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.material.uniforms.tDiffuse.value = this.texture;
    // Shipped Logo `setUniforms`: the UV scale is `matScale * scaleMult * 0.12`
    // and the shader divides the square UV by it, so 0.12 is the factor that
    // fits the whole upload inside a `scaleMult`-sized fraction of the quad.
    // Without it the quad sampled the texture's middle at ~3x and every
    // render-layer copy of the logo became a cropped blob.
    (this.material.uniforms.transform1.value as THREE.Vector4).set(
      this.matPositionX,
      this.matPositionY,
      this.matScaleX * this.scaleMult * 0.12,
      this.matScaleY * this.scaleMult * 0.12,
    );
    (this.material.uniforms.transform2.value as THREE.Vector4).set(
      (this.rotation * Math.PI) / 180,
      // Shipped Logo uses the *texture* aspect here (`this.aspect`, set from the
      // loaded image, default 1.6777), not the quad's.
      this.aspect,
      this.circleCutoff,
      ["Clamp", "Repeat", "Discard"].indexOf(this.textureWrap),
    );
    (this.material.uniforms.resolution.value as THREE.Vector2).set(resolution.x, resolution.y);
    this.mesh.position.set(
      this.readNumber("transform.x") / 100,
      this.readNumber("transform.y") / 100,
      this.z + this.readNumber("transform.z") / 100,
    );
    this.mesh.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      1,
    );
    this.mesh.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    const containers = [
      { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
      // The logo samples its texture through its own matrix. The reference
      // groups those as Position 2D / Scale 2D with x/y labels; name them as
      // texture groups so they cannot be mistaken for the item Transform.
      { id: "logoPosition", label: "Texture Position", kind: ContainerKind.Folder, parentId: "appearance" },
      { id: "logoScale", label: "Texture Scale", kind: ContainerKind.Folder, parentId: "appearance" },
      { id: "transform", label: "Transform", kind: ContainerKind.Folder },
    ];
    return {
      containers,
      controllers: [
        this.fileField("appearance.imageSrc", "Image", {
          parentId: "appearance",
          get: () => this.imageUrl,
          set: (v) => {
            this.imageUrl = v;
            this.pendingUrl = "";
            this.texture = null;
          },
        }),
        this.slider("appearance.matPositionX", "x", {
          parentId: "logoPosition",
          min: -2,
          max: 2,
          step: 0.01,
          get: () => this.matPositionX,
          set: (v) => {
            this.matPositionX = v;
          },
        }),
        this.slider("appearance.matPositionY", "y", {
          parentId: "logoPosition",
          min: -2,
          max: 2,
          step: 0.01,
          get: () => this.matPositionY,
          set: (v) => {
            this.matPositionY = v;
          },
        }),
        this.slider("appearance.matScaleX", "x", {
          parentId: "logoScale",
          min: 0,
          max: 4,
          step: 0.01,
          get: () => this.matScaleX,
          set: (v) => {
            this.matScaleX = v;
          },
        }),
        this.slider("appearance.matScaleY", "y", {
          parentId: "logoScale",
          min: 0,
          max: 4,
          step: 0.01,
          get: () => this.matScaleY,
          set: (v) => {
            this.matScaleY = v;
          },
        }),
        this.slider("appearance.scaleMult", "Scale multiplier", {
          parentId: "appearance",
          min: 0,
          max: 10,
          step: 0.01,
          get: () => this.scaleMult,
          set: (v) => {
            this.scaleMult = v;
          },
        }),
        this.slider("appearance.rotation", "Rotation", {
          parentId: "appearance",
          min: -360,
          max: 360,
          step: 1,
          unit: "°",
          get: () => this.rotation,
          set: (v) => {
            this.rotation = v;
          },
        }),
        this.slider("appearance.circleCutoff", "Circle cutoff", {
          parentId: "appearance",
          min: 0,
          max: 1.5,
          step: 0.01,
          get: () => this.circleCutoff,
          set: (v) => {
            this.circleCutoff = v;
          },
        }),
        this.choose("appearance.textureWrap", "Texture wrap", {
          parentId: "appearance",
          values: ["Repeat", "Clamp", "Discard"],
          get: () => this.textureWrap,
          set: (v) => {
            this.textureWrap = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
      ],
    };
  }
}

/** Decompiled Ground heightfield item (Vizzy module 1361). */
export class GroundNode extends SceneNode {
  readonly kind = NodeKind.Ground;
  readonly typeLabel = "Ground";
  override readonly is3D = true;

  multiplier = 1;
  private elapsed = 5;
  /** Last project time the audio clock advanced on (guards re-renders). */
  private lastClockTime = Number.NEGATIVE_INFINITY;
  private mesh!: THREE.Mesh;
  private material!: THREE.RawShaderMaterial;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", -150);
    this.objectMapping.set("transform.z", -700);
    // Module 1361's constructor lays the plane flat through the *item's* own
    // `rotation.x = -90`, the same field the export's `rotation:x` writes:
    //   this.mesh.position.z = -700, this.mesh.position.y = -150,
    //   this.mesh.rotation.x = -Math.PI / 2,
    //   this.position.z = -700, this.position.y = -150,
    //   this.rotation.x = Object(h.u)(-Math.PI / 2);
    // A saved rotation therefore *replaces* the flat pose instead of adding to
    // it. `record-label-endlos` exports -71 / 30.1 / -22, a tilted ground; with
    // the old `-90 + rotX` composition it stayed horizontal and its vinyl
    // ripples crossed the whole lower frame where the reference shows none.
    this.objectMapping.set("transform.rotX", -90);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.material = new THREE.RawShaderMaterial({
      uniforms: { time: { value: 0 } },
      vertexShader: /* glsl */ `
        attribute vec3 position;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        uniform float time;
        varying vec3 vPosition;
        void main() {
          float sin1 = sin((position.x + position.y) * 0.2 + time * 0.5);
          float sin2 = sin((position.x - position.y) * 0.4 + time * 2.0);
          float sin3 = sin((position.x + position.y) * -0.6 + time);
          vec3 updatePosition = vec3(
            position.x,
            position.y,
            position.z + sin1 * 50.0 + sin2 * 10.0 + sin3 * 8.0
          );
          vPosition = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(updatePosition, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        precision highp float;
        uniform float time;
        varying vec3 vPosition;
        const float duration = 8.0;
        const float delay = 4.0;
        vec3 convertHsvToRgb(vec3 c) {
          vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
          vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
          return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
        }
        void main() {
          float now = clamp((time - delay) / duration, 0.0, 1.0);
          float opacity = (1.0 - length(vPosition.xy / vec2(512.0))) * 0.6 * now;
          vec3 v = normalize(vPosition);
          vec3 rgb = convertHsvToRgb(vec3(
            0.5 + (v.x + v.y + v.x) / 40.0 + time * 0.1,
            0.4,
            1.0
          ));
          gl_FragColor = vec4(rgb, opacity);
        }
      `,
      transparent: true,
      wireframe: true,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1024, 1024, 32, 32), this.material);
    // The plane is authored flat and the pose lives on the item's transform
    // (`this.group`), matching module 1361, where a saved `rotation:x` replaces
    // the constructor's -90 rather than stacking on it.
    this.group.add(this.mesh);
  }

  sync(time: number): void {
    // Reference module 1361: `hypot(...audioAnalyzerData)` over the
    // analyzer's raw values, then `elapsed += multiplier * magnitude / 1e4`.
    // The shader clock starts at 5 s and is advanced by the music, which is
    // what animates the hue and fades the grid in. Our band arrays are
    // normalised by 200, so scale them back before the hypot; using the
    // normalised values made the clock advance ~200x too slowly (the grid
    // stayed dim and off-hue).
    const bands = this.analyzerId
      ? this.ctx.spectrumBandsFor?.(this.analyzerId) ??
        this.ctx.spectrumFor?.(this.analyzerId) ??
        null
      : null;
    if (bands && bands.length) {
      // The reference advances this clock once per rendered frame. A pause or
      // a repeated render of the same timestamp (our captures render the final
      // frame several times, and the live loop can interleave a render) must not
      // add more audio, otherwise the hue drifts between otherwise identical
      // frames. A rewind starts a fresh timeline.
      if (time < this.lastClockTime - 1e-6) {
        this.lastClockTime = time;
      } else if (time > this.lastClockTime) {
        let magnitude = 0;
        for (const value of bands) {
          const raw = value * REFERENCE_VALUE_SCALE;
          magnitude += raw * raw;
        }
        this.elapsed += this.multiplier * (Math.sqrt(magnitude) / 10000);
        this.lastClockTime = time;
      }
    }
    this.material.uniforms.time.value = time + this.elapsed;
    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    // The flat pose is the item's own `rotation.x` default (-90), so the saved
    // rotation is used as-is rather than added to a mesh-space quarter turn.
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.slider("behaviour.multiplier", "Audio reaction", {
          parentId: "behaviour",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.multiplier,
          set: (v) => {
            this.multiplier = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.rotY", "Rotation Y", {
          parentId: "transform",
          min: -360,
          max: 360,
          unit: "°",
          get: () => this.readNumber("transform.rotY"),
          set: (v) => this.objectMapping.set("transform.rotY", v),
        }),
      ],
    };
  }
}

function formatSkiaTime(value: number, decimals: number, format: string): string {
  if (format === "s") return value.toFixed(decimals);
  const whole = Math.floor(value);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole - 3600 * hours) / 60);
  const seconds = whole - 3600 * hours - 60 * minutes;
  // The reference concatenates (not numeric-coerces), so `0` becomes `00`:
  // `s < 10 && (s = "0" + s)`.
  const pad = (part: number): string => String(part).padStart(2, "0");
  let result =
    format === "hh:mm:ss"
      ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
      : `${pad(minutes)}:${pad(seconds)}`;
  if (decimals > 0) {
    result += `.${(value - Math.floor(value)).toFixed(decimals).substr(2)}`;
  }
  return result;
}

function replaceSkiaVariables(text: string, values: Record<string, string>): string {
  return text.replace(/\{\{([^}]+)\}\}/g, (_match, expression: string) => {
    const parts = expression.split(":");
    const name = parts[0].trim();
    const modifiers = parts.slice(1);
    let value =
      name.startsWith("`") && name.endsWith("`")
        ? name.slice(1, -1)
        : values[name]?.toString() || "";
    for (const modifier of modifiers) {
      switch (modifier.trim().toLowerCase()) {
        case "upper":
          value = value.toUpperCase();
          break;
        case "lower":
          value = value.toLowerCase();
          break;
        case "capitalize":
          value = value.charAt(0).toUpperCase() + value.slice(1);
          break;
        case "title":
          value = value.replace(/\b\w/g, (char) => char.toUpperCase());
          break;
        case "strip":
          value = value.replace(/\.[^/.]+$/, "");
          break;
        case "trim":
          value = value.trim();
          break;
        case "spaces":
          value = value
            .split("")
            .map((char, index, all) =>
              char === "\n" || index === 0
                ? char
                : index === all.length - 1
                  ? ` ${char}`
                  : char === " "
                    ? "   "
                    : ` ${char}`,
            )
            .join("");
          break;
        default:
          break;
      }
    }
    return value;
  });
}

/** 2D text item rendered through the decompiled Canvas2D text layout. */
export class SkiaTextNode extends SceneNode {
  readonly kind = NodeKind.SkiaText;
  readonly typeLabel = "Text";

  textValue = "Text";
  color = "#ffffff";
  alpha = 1;
  antiAliasing = true;
  textSize = 60;
  timeFormat = "mm:ss";
  timeDecimals = 2;
  drawTime = false;
  drawTimeCountdown = false;
  textAlign: "left" | "center" | "right" = "center";
  textAlignV: "top" | "middle" | "bottom" = "middle";
  textBaseline: CanvasTextBaseline = "bottom";
  font = "SourceSansPro";
  positionX = 0;
  positionY = 0;
  scaleX = 1;
  scaleY = 1;
  scaleMultiplier = 1;
  showBoundingBox = false;
  textWidth = 850;
  textHeight = 500;
  fontStyle = "normal";
  fontWeight = 400;
  rotation = 0;
  projectName = "";
  audioName = "";
  dropShadow = {
    enableShadow: false,
    shadowColor: "#000000",
    shadowOffsetX: 4,
    shadowOffsetY: 4,
    shadowBlur: 1,
  };
  outlineDropShadow = {
    enableOutline: false,
    outlineColor: "#000000",
    outlineOffsetX: 0,
    outlineOffsetY: 0,
    outlineExtent: 1,
    outlineBlur: 0,
    outlineHighPrecision: false,
  };
  textJustify = false;

  private canvas!: HTMLCanvasElement;
  /** Everything the last paint depended on, so static text is not re-uploaded. */
  private lastDrawKey = "";
  private context!: CanvasRenderingContext2D;
  private texture!: THREE.CanvasTexture;
  private mesh!: THREE.Mesh;
  private fontName = "SourceSansPro";
  private elapsed = 0;
  private pendingFont = "";

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
    void this.loadFont();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.z", -5);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.canvas = document.createElement("canvas");
    this.canvas.width = Math.max(1, Math.round(resolution.x));
    this.canvas.height = Math.max(1, Math.round(resolution.y));
    this.context = this.canvas.getContext("2d")!;
    this.texture = new THREE.CanvasTexture(this.canvas);
    // The canvas already holds sRGB bytes from `fillStyle = this.color` and the
    // frame is composited without an output encode (Image, Video and the
    // spectrum uploads are all NoColorSpace). Tagging the canvas sRGB made three
    // decode it to linear and hand the frame those darker values: top-pop's
    // `#C9A6E8` artist row rendered (148,97,205) instead of the authored
    // (201,166,232), its `#CFC5D3` numbers (156,139,163) instead of (207,197,211),
    // and its `#FADC8C` year (243,182,67) - the saturated orange the design does
    // not have. NoColorSpace keeps the authored colour, like every other upload.
    this.texture.colorSpace = THREE.NoColorSpace;
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;

    const aspect = resolution.x / resolution.y;
    const material = new THREE.MeshBasicMaterial({
      map: this.texture,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2 * aspect, 2), material);
    this.mesh.position.z = this.readNumber("transform.z") * REFERENCE_SCALE;
    this.mesh.renderOrder = 10;
    this.group.add(this.mesh);
  }

  async loadFont(): Promise<void> {
    const requested = this.font;
    const family = await loadSkiaFont(requested);
    // The constructor kicks off a load for the default family before import
    // assigns the item's real font. That stale promise can resolve after the
    // requested face and overwrite it (remote Playfair/Manrope text fell back
    // to SourceSansPro in renders). Only the latest request may win.
    if (requested !== this.font) return;
    this.fontName = family;
    if (this.context) this.draw(this.elapsed);
  }

  private draw(time: number): void {
    const ctx = this.context;
    if (!ctx) return;
    const resolution = this.ctx.resolution?.() ?? { x: this.canvas.width, y: this.canvas.height };
    const pixelWidth = Math.max(1, Math.round(resolution.x));
    const pixelHeight = Math.max(1, Math.round(resolution.y));
    if (this.canvas.width !== pixelWidth || this.canvas.height !== pixelHeight) {
      // Same immutable `texStorage2D` rule as the canvas-backed items: a canvas
      // resized after the texture's first upload keeps the old allocation, so
      // every later paint uploads into storage the driver rejects and the
      // composite keeps showing the first frame (a countdown frozen at 00:36).
      this.texture.dispose();
      this.canvas.width = pixelWidth;
      this.canvas.height = pixelHeight;
    }

    const duration = this.ctx.projectDuration?.() ?? this.duration;
    const remaining = duration - time;
    const values: Record<string, string> = {
      time: formatSkiaTime(time, this.timeDecimals, this.timeFormat),
      duration: formatSkiaTime(duration, this.timeDecimals, this.timeFormat),
      remaining_time: formatSkiaTime(remaining, this.timeDecimals, this.timeFormat),
      raw_time: time.toString(),
      raw_duration: duration.toString(),
      raw_remaining_time: remaining.toString(),
      project_name: this.ctx.projectName?.() ?? this.projectName,
      audio_name: this.ctx.audioName?.() ?? this.audioName,
      tag_format: "",
      tag_title: "",
      tag_artist: "",
      tag_album: "",
      tag_year: "",
      tag_track: "",
      tag_comment: "",
      tag_genre: "",
      tag_vendor: "",
    };
    const text = replaceSkiaVariables(this.textValue, values);

    // A text item rasterises into a full project-resolution canvas. Repainting
    // and re-uploading it every frame costs ~3 ms and ~8 MB per item, which made
    // a 37-label template run at 1 fps. Paint only when something the paint
    // depends on actually changed (the string, the style, the transform or the
    // surface size); the font promise calls draw() again, which changes
    // `fontName` and therefore the key.
    const drawKey = [
      this.canvas.width,
      this.canvas.height,
      text,
      this.fontName,
      this.textSize,
      this.alpha,
      this.color,
      this.textAlign,
      this.textAlignV,
      this.textBaseline,
      this.textJustify ? 1 : 0,
      this.fontStyle,
      this.fontWeight,
      this.positionX,
      this.positionY,
      this.scaleX,
      this.scaleY,
      this.scaleMultiplier,
      this.rotation,
      this.textWidth,
      this.textHeight,
      this.showBoundingBox ? 1 : 0,
      this.dropShadow.enableShadow ? 1 : 0,
      this.dropShadow.shadowColor,
      this.dropShadow.shadowOffsetX,
      this.dropShadow.shadowOffsetY,
      this.dropShadow.shadowBlur,
      this.outlineDropShadow.enableOutline ? 1 : 0,
      this.outlineDropShadow.outlineColor,
      this.outlineDropShadow.outlineOffsetX,
      this.outlineDropShadow.outlineOffsetY,
      this.outlineDropShadow.outlineExtent,
      this.outlineDropShadow.outlineBlur,
      this.outlineDropShadow.outlineHighPrecision ? 1 : 0,
    ].join("|");
    if (drawKey === this.lastDrawKey) return;
    this.lastDrawKey = drawKey;

    ctx.save();
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.font = `${this.textSize / 2}pt ${this.fontName}`;
    const alpha = Math.max(0, Math.min(1, this.alpha));
    ctx.fillStyle = this.color;
    ctx.textAlign = this.textAlign;
    ctx.textBaseline = this.textBaseline;

    const scaleFactor = Math.sqrt(
      this.canvas.width * this.canvas.width + this.canvas.height * this.canvas.height,
    ) / 1000;
    const filters: string[] = [];
    const outline = this.outlineDropShadow;
    if (outline.enableOutline) {
      const extent =
        outline.outlineExtent * scaleFactor * (outline.outlineHighPrecision ? 0.5 : 1);
      const blur = outline.outlineBlur * scaleFactor;
      const offsetX = outline.outlineOffsetX * scaleFactor;
      const offsetY = outline.outlineOffsetY * scaleFactor;
      const color = outline.outlineColor;
      filters.push(
        `drop-shadow(${offsetX + extent}px ${offsetY - extent}px ${blur}px ${color})`,
        `drop-shadow(${offsetX + extent}px ${offsetY + extent}px ${blur}px ${color})`,
        `drop-shadow(${offsetX - extent}px ${offsetY + extent}px ${blur}px ${color})`,
        `drop-shadow(${offsetX - extent}px ${offsetY - extent}px ${blur}px ${color})`,
      );
      if (outline.outlineHighPrecision) {
        filters.push(
          `drop-shadow(${offsetX}px ${offsetY - extent}px ${blur}px ${color})`,
          `drop-shadow(${offsetX + extent}px ${offsetY}px ${blur}px ${color})`,
          `drop-shadow(${offsetX}px ${offsetY + extent}px ${blur}px ${color})`,
          `drop-shadow(${offsetX - extent}px ${offsetY}px ${blur}px ${color})`,
        );
      }
    }
    const shadow = this.dropShadow;
    if (shadow.enableShadow) {
      filters.push(
        `drop-shadow(${shadow.shadowOffsetX * scaleFactor}px ${shadow.shadowOffsetY * scaleFactor}px ${shadow.shadowBlur * scaleFactor}px ${shadow.shadowColor})`,
      );
    }
    if (alpha < 1) filters.push(`opacity(${alpha})`);
    ctx.filter = filters.length ? filters.join(" ") : "none";
    ctx.globalAlpha = 1;

    const scaleX = this.canvas.width / 1000;
    const scaleY = this.canvas.height / 1000;
    ctx.scale(scaleX, scaleY);
    ctx.translate(500 + this.positionX, 500 + this.positionY);
    ctx.scale(1, scaleX / scaleY);
    ctx.scale(this.scaleX * this.scaleMultiplier, this.scaleY * this.scaleMultiplier);
    ctx.rotate((this.rotation * Math.PI) / 180);

    drawText(ctx, text, {
      x: -this.textWidth / 2,
      y: -this.textHeight / 2,
      width: this.textWidth <= 0 ? 1 : this.textWidth,
      height: this.textHeight <= 0 ? 1 : this.textHeight,
      debug: this.showBoundingBox,
      align: this.textAlign,
      vAlign: this.textAlignV,
      fontSize: this.textSize,
      font: this.fontName,
      fontStyle: this.fontStyle,
      fontWeight: this.fontWeight.toString(),
      justify: this.textJustify,
    });
    ctx.restore();
    this.texture.needsUpdate = true;
  }

  sync(time: number): void {
    this.elapsed = time;
    const resolution = this.ctx.resolution?.() ?? { x: this.canvas.width, y: this.canvas.height };
    const aspect = resolution.x / Math.max(1, resolution.y);
    const geometry = this.mesh.geometry as THREE.PlaneGeometry;
    if (Math.abs(geometry.parameters.width - 2 * aspect) > 0.001) {
      geometry.dispose();
      this.mesh.geometry = new THREE.PlaneGeometry(2 * aspect, 2);
    }
    this.mesh.position.set(0, 0, this.readNumber("transform.z") * REFERENCE_SCALE);
    this.mesh.visible = this.visible;
    this.draw(time);
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "text", label: "Text", kind: ContainerKind.Folder },
        { id: "shadow", label: "Drop shadow", kind: ContainerKind.Folder },
        { id: "position", label: "Positioning & Size", kind: ContainerKind.Folder },
        { id: "position2d", label: "Texture Position", kind: ContainerKind.Folder, parentId: "position" },
        { id: "scale2d", label: "Texture Scale", kind: ContainerKind.Folder, parentId: "position" },
      ],
      controllers: [
        this.text("text.text", "Text", {
          parentId: "text",
          get: () => this.textValue,
          set: (v) => {
            this.textValue = v;
          },
        }),
        this.choose("text.font", "Font", {
          parentId: "text",
          values: SKIA_FONT_TITLES,
          get: () => this.font,
          set: (v) => {
            this.font = v;
            void this.loadFont();
          },
        }),
        this.toggle("text.antiAliasing", "Antialiasing", {
          parentId: "text",
          get: () => this.antiAliasing,
          set: (v) => {
            this.antiAliasing = v;
          },
        }),
        this.colorField("text.color", "Text color", {
          parentId: "text",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("text.alpha", "Text alpha", {
          parentId: "text",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.alpha,
          set: (v) => {
            this.alpha = v;
          },
        }),
        this.slider("text.textSize", "Text size", {
          parentId: "text",
          min: 1,
          max: 200,
          get: () => this.textSize,
          set: (v) => {
            this.textSize = v;
          },
        }),
        this.slider("text.fontWeight", "Font weight", {
          parentId: "text",
          min: 100,
          max: 1000,
          step: 1,
          get: () => this.fontWeight,
          set: (v) => {
            this.fontWeight = v;
          },
        }),
        this.choose("text.fontStyle", "Font style", {
          parentId: "text",
          values: ["normal", "italic", "oblique"],
          get: () => this.fontStyle,
          set: (v) => {
            this.fontStyle = v;
          },
        }),
        this.choose("text.textAlign", "Text align", {
          parentId: "text",
          values: ["left", "center", "right"],
          get: () => this.textAlign,
          set: (v) => {
            this.textAlign = v as typeof this.textAlign;
          },
        }),
        this.choose("text.textBaseline", "Text baseline", {
          parentId: "text",
          values: ["top", "hanging", "middle", "alphabetic", "ideographic", "bottom"],
          get: () => this.textBaseline,
          set: (v) => {
            this.textBaseline = v as CanvasTextBaseline;
          },
        }),
        this.toggle("text.textJustify", "Text justify", {
          parentId: "text",
          get: () => this.textJustify,
          set: (v) => {
            this.textJustify = v;
          },
        }),
        this.slider("text.timeDecimals", "Decimals", {
          parentId: "text",
          min: 0,
          max: 4,
          step: 1,
          get: () => this.timeDecimals,
          set: (v) => {
            this.timeDecimals = Math.max(0, Math.min(100, Math.round(v)));
          },
        }),
        this.choose("text.timeFormat", "Format", {
          parentId: "text",
          values: ["s", "mm:ss", "hh:mm:ss"],
          get: () => this.timeFormat,
          set: (v) => {
            this.timeFormat = v;
          },
        }),
        this.toggle("shadow.enableShadow", "Enable shadow", {
          parentId: "shadow",
          get: () => this.dropShadow.enableShadow,
          set: (v) => {
            this.dropShadow.enableShadow = v;
          },
        }),
        this.colorField("shadow.shadowColor", "Shadow color", {
          parentId: "shadow",
          get: () => this.dropShadow.shadowColor,
          set: (v) => {
            this.dropShadow.shadowColor = v;
          },
        }),
        this.slider("shadow.shadowOffsetX", "Shadow offset X", {
          parentId: "shadow",
          min: -10,
          max: 10,
          step: 0.1,
          get: () => this.dropShadow.shadowOffsetX,
          set: (v) => {
            this.dropShadow.shadowOffsetX = v;
          },
        }),
        this.slider("shadow.shadowOffsetY", "Shadow offset Y", {
          parentId: "shadow",
          min: -10,
          max: 10,
          step: 0.1,
          get: () => this.dropShadow.shadowOffsetY,
          set: (v) => {
            this.dropShadow.shadowOffsetY = v;
          },
        }),
        this.slider("shadow.shadowBlur", "Shadow blur", {
          parentId: "shadow",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.dropShadow.shadowBlur,
          set: (v) => {
            this.dropShadow.shadowBlur = v;
          },
        }),
        this.toggle("shadow.enableOutline", "Enable outline", {
          parentId: "shadow",
          get: () => this.outlineDropShadow.enableOutline,
          set: (v) => {
            this.outlineDropShadow.enableOutline = v;
          },
        }),
        this.colorField("shadow.outlineColor", "Outline color", {
          parentId: "shadow",
          get: () => this.outlineDropShadow.outlineColor,
          set: (v) => {
            this.outlineDropShadow.outlineColor = v;
          },
        }),
        this.slider("shadow.outlineOffsetX", "Outline offset X", {
          parentId: "shadow",
          min: -10,
          max: 10,
          step: 0.1,
          get: () => this.outlineDropShadow.outlineOffsetX,
          set: (v) => {
            this.outlineDropShadow.outlineOffsetX = v;
          },
        }),
        this.slider("shadow.outlineOffsetY", "Outline offset Y", {
          parentId: "shadow",
          min: -10,
          max: 10,
          step: 0.1,
          get: () => this.outlineDropShadow.outlineOffsetY,
          set: (v) => {
            this.outlineDropShadow.outlineOffsetY = v;
          },
        }),
        this.slider("shadow.outlineExtent", "Outline extent", {
          parentId: "shadow",
          min: 1,
          max: 8,
          step: 1,
          get: () => this.outlineDropShadow.outlineExtent,
          set: (v) => {
            this.outlineDropShadow.outlineExtent = v;
          },
        }),
        this.slider("shadow.outlineBlur", "Outline blur", {
          parentId: "shadow",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.outlineDropShadow.outlineBlur,
          set: (v) => {
            this.outlineDropShadow.outlineBlur = v;
          },
        }),
        this.toggle("shadow.outlineHighPrecision", "High precision", {
          parentId: "shadow",
          get: () => this.outlineDropShadow.outlineHighPrecision,
          set: (v) => {
            this.outlineDropShadow.outlineHighPrecision = v;
          },
        }),
        this.slider("position.positionX", "x", {
          parentId: "position2d",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.positionX,
          set: (v) => {
            this.positionX = v;
          },
        }),
        this.slider("position.positionY", "y", {
          parentId: "position2d",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.positionY,
          set: (v) => {
            this.positionY = v;
          },
        }),
        this.slider("position.scaleX", "x", {
          parentId: "scale2d",
          min: -10,
          max: 10,
          step: 0.05,
          get: () => this.scaleX,
          set: (v) => {
            this.scaleX = v;
          },
        }),
        this.slider("position.scaleY", "y", {
          parentId: "scale2d",
          min: -10,
          max: 10,
          step: 0.05,
          get: () => this.scaleY,
          set: (v) => {
            this.scaleY = v;
          },
        }),
        this.slider("position.rotation", "Rotation", {
          parentId: "position",
          min: -360,
          max: 360,
          step: 1,
          unit: "°",
          get: () => this.rotation,
          set: (v) => {
            this.rotation = v;
          },
        }),
        this.slider("position.scaleMultiplier", "Scale multiplier", {
          parentId: "position",
          min: -5,
          max: 5,
          step: 0.01,
          get: () => this.scaleMultiplier,
          set: (v) => {
            this.scaleMultiplier = v;
          },
        }),
        this.slider("position.textWidth", "Text box width", {
          parentId: "position",
          min: 0,
          max: 4000,
          step: 1,
          get: () => this.textWidth,
          set: (v) => {
            this.textWidth = v;
          },
        }),
        this.slider("position.textHeight", "Text box height", {
          parentId: "position",
          min: 0,
          max: 4000,
          step: 1,
          get: () => this.textHeight,
          set: (v) => {
            this.textHeight = v;
          },
        }),
        this.toggle("position.showBoundingBox", "Show bounding box", {
          parentId: "position",
          get: () => this.showBoundingBox,
          set: (v) => {
            this.showBoundingBox = v;
          },
        }),
      ],
    };
  }

  dispose(): void {
    this.texture.dispose();
    this.canvas.width = 1;
    this.canvas.height = 1;
    (this.mesh.geometry as THREE.BufferGeometry).dispose();
    (this.mesh.material as THREE.Material).dispose();
  }
}

/** Animated SDF text using the reference BMFont and shaders (modules 1343-1346). */
export class AnimatedTextNode extends SceneNode {
  readonly kind = NodeKind.AnimatedText;
  readonly typeLabel = "Animated Text";

  textValue = "Hello, I'm AnimatedText";
  color = "#d478ff";
  animationDuration = 2;
  useCustomDuration = false;
  align: "left" | "center" | "right" = "center";
  width = 600;
  scaleMultiplier = 0.05;
  showBoundingBox = false;
  letterSpacing = 0;
  useReactiveAlpha = false;

  private font: BmFont | null = null;
  private layout = new BmFontLayout();
  private textMesh!: THREE.Mesh;
  private material!: THREE.RawShaderMaterial;
  private helper!: THREE.Mesh;
  private texture: THREE.Texture | null = null;
  private layoutKey = "";
  private lineHeight = 0;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
    void this.loadAssets();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.material = new THREE.RawShaderMaterial({
      vertexShader: ANIMATED_TEXT_VERTEX_SHADER,
      fragmentShader: ANIMATED_TEXT_FRAGMENT_SHADER,
      uniforms: {
        animate: { value: 0.5 },
        iGlobalTime: { value: 0 },
        map: { value: null },
        color: { value: new THREE.Color(this.color) },
        opacity: { value: 1 },
      },
      transparent: true,
      depthTest: false,
      side: THREE.DoubleSide,
    });
    this.textMesh = new THREE.Mesh(new THREE.BufferGeometry(), this.material);
    this.textMesh.rotation.x = Math.PI;
    const scale = this.scaleMultiplier;
    this.textMesh.scale.setScalar(scale);
    this.group.add(this.textMesh);

    this.helper = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({ color: 0xffffff, visible: this.showBoundingBox }),
    );
    this.helper.visible = this.showBoundingBox;
    this.group.add(this.helper);
  }

  private async loadAssets(): Promise<void> {
    try {
      const response = await fetch("/fonts/DejaVu-sdf.fnt");
      const text = await response.text();
      this.font = parseBmFont(text);
      this.rebuildGeometry(true);
    } catch {
      this.font = null;
    }
    new THREE.TextureLoader().load(
      "/fonts/DejaVu-sdf.png",
      (texture) => {
        texture.colorSpace = THREE.NoColorSpace;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = false;
        this.texture = texture;
        this.material.uniforms.map.value = texture;
      },
      undefined,
      () => {
        this.texture = null;
      },
    );
  }

  rebuildGeometry(force = false): void {
    if (!this.font) return;
    const key = `${this.textValue}|${this.width}|${this.align}|${this.letterSpacing}|${this.scaleMultiplier}`;
    if (!force && key === this.layoutKey) return;
    this.layoutKey = key;
    this.layout.update(this.font, {
      text: this.textValue,
      width: this.width,
      align: this.align,
      letterSpacing: this.letterSpacing,
    });
    const geometry = buildBmFontGeometry(this.layout, this.font, this.letterSpacing);
    const positions = geometry.getAttribute("position");
    let minY = Infinity;
    let maxY = -Infinity;
    for (let index = 0; index < positions.count; index += 1) {
      const value = positions.getY(index);
      minY = Math.min(minY, value);
      maxY = Math.max(maxY, value);
    }
    const scale = this.scaleMultiplier;
    this.textMesh.geometry.dispose();
    this.textMesh.geometry = geometry;
    this.textMesh.scale.setScalar(scale);
    this.lineHeight = Number.isFinite(maxY) ? (maxY - minY) * scale : 0;
    this.textMesh.position.x = (-this.width * scale) / 2;
    this.textMesh.position.y = -this.lineHeight / 2;
    this.helper.scale.set(this.width * scale, this.lineHeight, 1);
    this.helper.visible = this.showBoundingBox;
  }

  sync(time: number): void {
    this.rebuildGeometry();
    const elapsed = (time - this.start) % Math.max(0.0001, this.animationDuration);
    this.material.uniforms.iGlobalTime.value = elapsed;
    this.material.uniforms.animate.value = 0.5;
    (this.material.uniforms.color.value as THREE.Color).set(this.color);
    this.material.uniforms.opacity.value = this.useReactiveAlpha ? elapsed : 1;
    this.helper.visible = this.showBoundingBox;

    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      -40 + this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "text", label: "Text", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.text("text.text", "Text", {
          parentId: "text",
          get: () => this.textValue,
          set: (v) => {
            this.textValue = v;
            this.rebuildGeometry();
          },
        }),
        this.colorField("text.color", "Color", {
          parentId: "text",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("text.duration", "Animation duration", {
          parentId: "text",
          min: 0.1,
          max: 10,
          step: 0.1,
          get: () => this.animationDuration,
          set: (v) => {
            this.animationDuration = v;
          },
        }),
        this.slider("text.letterSpacing", "Letter spacing", {
          parentId: "text",
          min: -20,
          max: 40,
          step: 1,
          get: () => this.letterSpacing,
          set: (v) => {
            this.letterSpacing = v;
            this.rebuildGeometry();
          },
        }),
        this.choose("text.align", "Align", {
          parentId: "text",
          values: ["left", "center", "right"],
          get: () => this.align,
          set: (v) => {
            this.align = v as typeof this.align;
            this.rebuildGeometry();
          },
        }),
        this.slider("text.width", "Width", {
          parentId: "text",
          min: 0,
          max: 1000,
          step: 1,
          get: () => this.width,
          set: (v) => {
            this.width = v;
            this.rebuildGeometry();
          },
        }),
        this.toggle("text.showBoundingBox", "Show bounding box", {
          parentId: "text",
          get: () => this.showBoundingBox,
          set: (v) => {
            this.showBoundingBox = v;
          },
        }),
        this.toggle("text.useReactiveAlpha", "Reactive alpha", {
          parentId: "text",
          get: () => this.useReactiveAlpha,
          set: (v) => {
            this.useReactiveAlpha = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -2000,
          max: 2000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -2000,
          max: 2000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 2000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.rotY", "Rotation Y", {
          parentId: "transform",
          min: -360,
          max: 360,
          unit: "°",
          get: () => this.readNumber("transform.rotY"),
          set: (v) => this.objectMapping.set("transform.rotY", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.textMesh.geometry.dispose();
    this.material.dispose();
    this.helper.geometry.dispose();
    (this.helper.material as THREE.Material).dispose();
    this.texture?.dispose();
  }
}

const AUDIO_WAVE_DRAW_TYPES = ["skew", "normal", "circle"] as const;
const AUDIO_WAVE_LINE_TYPES = ["Flat line", "Normal", "Tube"] as const;
const DOWNSAMPLE_OPTIONS = ["1", "2", "4", "8", "16", "32", "64"] as const;

function downsampleWaveform(
  input: Float32Array,
  factor: number,
  scale: number,
  takeEvery: number,
): Float32Array {
  let values = input.slice();
  if (scale !== 1) {
    for (let index = 0; index < values.length; index += 1) values[index] *= scale;
  }
  if (factor !== 1) {
    const length = Math.ceil(values.length / factor);
    const output = new Float32Array(length);
    for (let index = 0; index < values.length; index += factor) {
      let sum = 0;
      const start = Math.max(index - factor / 2, 0);
      const end = Math.min(values.length, index + factor / 2);
      for (let sample = start; sample < end; sample += 1) sum += values[sample];
      output[index / factor] = sum / (end - start);
    }
    values = output;
  }
  if (takeEvery !== 1) {
    const length = Math.floor(values.length / takeEvery);
    const output = new Float32Array(length);
    for (let index = 0; index < values.length; index += takeEvery) {
      output[index / takeEvery] = values[index];
    }
    values = output;
  }
  return values;
}

/** Audio waveform / oscilloscope line using the reference Line2 pipeline. */
export class AudioWaveNode extends SceneNode {
  readonly kind = NodeKind.AudioWave;
  readonly typeLabel = "Audio wave";
  override readonly is3D = true;

  amplitude = 1;
  extent = 30;
  width = 40;
  height = 2;
  timeMultiplier = 1;
  color = "#ffffff";
  positionX = 0;
  positionY = 0.35;
  textureScale = 1;
  downsample = "1";
  audioDuration = 500;
  takeEvery = "1";
  absolute = false;
  drawType = "Normal";
  lineType = "Tube";
  lineThickness = 0.4;
  bufferKeepAmount = 1;
  useAudioAnalyzer = false;
  audioAnalyzer = "analyzer_default";
  syncToDominant = false;
  analyserFreqRange: [number, number] = [20, 130];
  periodsVisible = "1";

  private dataBuffer = new Float32Array(0);
  private previousBufferLength = -1;
  private line: THREE.Line | Line2 | null = null;
  private lineGeometry: THREE.BufferGeometry | LineGeometry = new THREE.BufferGeometry();
  private lineMaterial: THREE.LineBasicMaterial | LineMaterial | null = null;
  private lastDominantFrequency = 0;
  private frequencyChangeCount = 0;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -100);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.createLine();
    // Reference constructor parks the item at z=-100 in the 1000-unit world.
    this.group.position.z = this.readNumber("transform.z") * (2 / 1000);
  }

  private createLine(): void {
    if (this.line) this.group.remove(this.line);
    this.lineGeometry.dispose();
    if (this.lineMaterial) this.lineMaterial.dispose();
    this.lineGeometry = new THREE.BufferGeometry();
    if (this.lineType === "Normal" || this.lineType === "Flat line") {
      this.lineMaterial = new THREE.LineBasicMaterial({ color: new THREE.Color(this.color) });
      this.line = new THREE.Line(this.lineGeometry, this.lineMaterial);
    } else {
      const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
      this.lineGeometry = new LineGeometry();
      this.lineMaterial = new LineMaterial({
        color: new THREE.Color(this.color),
        linewidth: this.lineThickness,
        resolution: new THREE.Vector2(resolution.x, resolution.y),
        dashed: false,
      });
      this.line = new Line2(this.lineGeometry as LineGeometry, this.lineMaterial);
    }
    this.group.add(this.line);
  }

  private initializeBuffer(count: number): void {
    if (isNaN(count) || count === 0 || count === -Infinity || count === Infinity) return;
    const length = count * this.bufferKeepAmount * 3;
    if (length === this.previousBufferLength) return;
    this.dataBuffer = new Float32Array(length);
    this.previousBufferLength = length;
    if (this.lineType === "Normal" || this.lineType === "Flat line") {
      this.lineGeometry.dispose();
      this.lineGeometry = new THREE.BufferGeometry();
      this.lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(this.dataBuffer, 3));
      (this.line as THREE.Line).geometry = this.lineGeometry;
    } else {
      this.lineGeometry.dispose();
      this.lineGeometry = new LineGeometry();
      this.group.remove(this.line!);
      this.line = new Line2(this.lineGeometry as LineGeometry, this.lineMaterial as LineMaterial);
      this.group.add(this.line);
    }
  }

  private dominantFrequency(values: Float32Array): number {
    let bestIndex = 0;
    let best = 0;
    values.forEach((value, index) => {
      if (value > best) {
        best = value;
        bestIndex = index;
      }
    });
    const span = (this.analyserFreqRange[1] - this.analyserFreqRange[0]) / values.length;
    const frequency = this.analyserFreqRange[0] + bestIndex * span;
    if (this.lastDominantFrequency === 0) {
      this.lastDominantFrequency = frequency;
      return frequency;
    }
    const delta = frequency - this.lastDominantFrequency;
    if (Math.abs(delta) <= 10) {
      this.lastDominantFrequency = frequency;
      this.frequencyChangeCount = 0;
    } else {
      this.frequencyChangeCount += 1;
      if (this.frequencyChangeCount > 5) {
        this.lastDominantFrequency = frequency;
        this.frequencyChangeCount = 0;
      }
    }
    return this.lastDominantFrequency;
  }

  sync(time: number): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    if (this.lineMaterial instanceof LineMaterial) {
      this.lineMaterial.resolution.set(resolution.x, resolution.y);
      this.lineMaterial.linewidth = this.lineThickness * (resolution.x / 1920);
      this.lineMaterial.color.set(this.color);
    } else if (this.lineMaterial instanceof THREE.LineBasicMaterial) {
      this.lineMaterial.color.set(this.color);
    }

    let values: Float32Array;
    if (this.useAudioAnalyzer) {
      values = this.ctx.spectrumFor?.(this.audioAnalyzer) ?? this.ctx.spectrum();
      this.initializeBuffer(values.length);
    } else {
      const sampleRate = this.ctx.sampleRate?.() ?? 48000;
      const sampleCount = Math.max(1, Math.round((this.audioDuration / 1000) * sampleRate));
      let window = this.ctx.waveformWindow?.(sampleCount, time) ?? this.ctx.waveform();
      if (this.syncToDominant) {
        const analyzer = this.ctx.spectrumFor?.(this.audioAnalyzer);
        if (!analyzer) return;
        const frequency = this.dominantFrequency(analyzer) / Number(this.periodsVisible);
        const periodSamples = frequency > 0 ? Math.floor(sampleRate / frequency) : 0;
        window = this.ctx.waveformWindow?.(periodSamples > 0 ? periodSamples : sampleCount, time) ?? window;
      }
      const factor = Number(this.downsample);
      const takeEvery = Number(this.takeEvery);
      this.initializeBuffer(Math.max(1, Math.round(sampleCount / (factor * takeEvery))));
      values = downsampleWaveform(window, factor, 100, takeEvery);
    }

    const count = values.length;
    if (this.dataBuffer.length > 3 * count) {
      this.dataBuffer.set(
        new Float32Array(this.dataBuffer.subarray(0, this.dataBuffer.length - 3 * count)),
        3 * count,
      );
    }
    let cursor = 0;
    // The shipped AudioWave keeps its geometry in reference pixels: `x` spans
    // +/-width and `amplitude = value*amplitude*extent/200`. The layer camera is
    // the reference's 1000-unit frustum (half-height 500), while our layer
    // camera spans 2 units. Item-space geometry therefore maps with `* 2/1000`
    // and takes no aspect factor (only the *position* is aspect-mapped).
    const unit = 2 / 1000;
    for (let index = 0; index < count; index += 1) {
      const angle = (index / count) * Math.PI * this.timeMultiplier - Math.PI / 2;
      const x = ((index / count) * 2 * this.width - this.width) * unit;
      let amplitude = ((values[index] * this.amplitude * this.extent) / 200) * unit;
      if (this.absolute) amplitude = Math.abs(amplitude);
      if (this.drawType === "skew") {
        this.dataBuffer[cursor++] = x;
        this.dataBuffer[cursor++] = Math.sin(angle) * amplitude;
        this.dataBuffer[cursor++] = Math.cos(angle) * amplitude;
      } else if (this.drawType === "circle") {
        const radius = this.width * unit + amplitude;
        this.dataBuffer[cursor++] = Math.cos(angle) * radius;
        this.dataBuffer[cursor++] = Math.sin(angle) * radius;
        this.dataBuffer[cursor++] = 0;
      } else {
        this.dataBuffer[cursor++] = x;
        this.dataBuffer[cursor++] = amplitude;
        this.dataBuffer[cursor++] = 0;
      }
    }

    if (this.lineType === "Normal" || this.lineType === "Flat line") {
      const attribute = this.lineGeometry.getAttribute("position") as THREE.BufferAttribute;
      (attribute.array as Float32Array).set(this.dataBuffer);
      attribute.needsUpdate = true;
    } else {
      (this.lineGeometry as LineGeometry).setPositions(this.dataBuffer);
      (this.line as Line2).computeLineDistances();
    }

    // Base class `positionChanged`: `F(x, y, true)` gives x the aspect in
    // landscape (and y in portrait), then the mesh sits at that position in the
    // layer's camera. The reference orthographic camera is half-height 500 and
    // half-width 500*aspect; ours is half-height 1 and half-width aspect, so
    // `x/500` of the reference must become `x*aspect/500` here while `y/500`
    // stays as-is. Geometry already lives in item space and takes no aspect.
    const aspect = resolution.x / Math.max(1, resolution.y);
    const unitX = unit * (aspect > 1 ? aspect : 1);
    const unitY = unit * (aspect > 1 ? 1 : aspect);
    this.group.position.set(
      this.readNumber("transform.x") * unitX,
      this.readNumber("transform.y") * unitY,
      this.readNumber("transform.z") * unit,
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.choose("appearance.drawType", "Draw type", {
          parentId: "appearance",
          values: AUDIO_WAVE_DRAW_TYPES,
          get: () => this.drawType,
          set: (v) => {
            this.drawType = v;
          },
        }),
        this.choose("appearance.lineType", "Line type", {
          parentId: "appearance",
          values: AUDIO_WAVE_LINE_TYPES,
          get: () => this.lineType,
          set: (v) => {
            this.lineType = v;
            this.createLine();
            this.previousBufferLength = -1;
          },
        }),
        this.slider("appearance.lineThickness", "Line Thickness", {
          parentId: "appearance",
          min: 0.1,
          max: 5,
          step: 0.01,
          get: () => this.lineThickness,
          set: (v) => {
            this.lineThickness = v;
          },
        }),
        this.slider("appearance.extent", "Extent", {
          parentId: "appearance",
          min: -100,
          max: 100,
          step: 1,
          get: () => this.extent,
          set: (v) => {
            this.extent = v;
          },
        }),
        this.slider("appearance.width", "Width", {
          parentId: "appearance",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.width,
          set: (v) => {
            this.width = v;
          },
        }),
        this.slider("appearance.amplitude", "Amplitude", {
          parentId: "appearance",
          min: 0,
          max: 10,
          step: 0.01,
          get: () => this.amplitude,
          set: (v) => {
            this.amplitude = v;
          },
        }),
        this.choose("appearance.downsample", "Downsample", {
          parentId: "appearance",
          values: DOWNSAMPLE_OPTIONS,
          get: () => this.downsample,
          set: (v) => {
            this.downsample = v;
          },
        }),
        this.choose("appearance.takeEvery", "Take every", {
          parentId: "appearance",
          values: DOWNSAMPLE_OPTIONS,
          get: () => this.takeEvery,
          set: (v) => {
            this.takeEvery = v;
          },
        }),
        this.slider("appearance.audioDuration", "Audio duration", {
          parentId: "appearance",
          min: 16,
          max: 2000,
          step: 1,
          get: () => this.audioDuration,
          set: (v) => {
            this.audioDuration = v;
          },
        }),
        this.toggle("appearance.absolute", "Absolute value", {
          parentId: "appearance",
          get: () => this.absolute,
          set: (v) => {
            this.absolute = v;
          },
        }),
        this.slider("appearance.timeMultiplier", "Time multiplier", {
          parentId: "appearance",
          min: -5,
          max: 5,
          step: 0.01,
          get: () => this.timeMultiplier,
          set: (v) => {
            this.timeMultiplier = v;
          },
        }),
        this.toggle("appearance.syncToDominant", "Frequency lock", {
          parentId: "appearance",
          get: () => this.syncToDominant,
          set: (v) => {
            this.syncToDominant = v;
          },
        }),
        this.choose("appearance.periodsVisible", "Periods", {
          parentId: "appearance",
          values: ["0.5", "1", "2", "3", "4"],
          get: () => this.periodsVisible,
          set: (v) => {
            this.periodsVisible = v;
          },
        }),
        this.toggle("appearance.useAudioAnalyzer", "Use audio analyzer", {
          parentId: "appearance",
          get: () => this.useAudioAnalyzer,
          set: (v) => {
            this.useAudioAnalyzer = v;
          },
        }),
        this.text("appearance.audioAnalyzer", "Audio analyzer", {
          parentId: "appearance",
          get: () => this.audioAnalyzer,
          set: (v) => {
            this.audioAnalyzer = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.lineGeometry.dispose();
    this.lineMaterial?.dispose();
  }
}

/** 3D spectrum bars, one box per analyzer band (reference BasicSpectrumBars). */
export class BasicSpectrumBarsNode extends SceneNode {
  readonly kind = NodeKind.BasicSpectrumBars;
  readonly typeLabel = "3D Bars";
  override readonly is3D = true;

  spacing = 2;
  color = "#ffffff";
  audioAnalyzer = "analyzer_default";

  private bars: THREE.Mesh[] = [];
  private size = 0;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
    this.group.position.z = -300;
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -300);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.createBars(128);
  }

  private createBars(size: number): void {
    for (const bar of this.bars) {
      bar.geometry.dispose();
      (bar.material as THREE.Material).dispose();
      this.group.remove(bar);
    }
    this.bars = [];
    this.size = size;
    for (let index = 0; index < size; index += 1) {
      const material = new THREE.MeshBasicMaterial({ transparent: true });
      material.color.set(this.color);
      const bar = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), material);
      bar.position.x = index * this.spacing - (size / 2) * this.spacing;
      this.group.add(bar);
      this.bars.push(bar);
    }
  }

  sync(_time: number): void {
    const values = this.ctx.spectrumFor?.(this.audioAnalyzer) ?? this.ctx.spectrum();
    if (values.length !== this.size) this.createBars(values.length);
    this.bars.forEach((bar, index) => {
      const value = values[index] ?? 0;
      const scale = value / 8 + (value < 0 ? -1 : 1);
      bar.scale.set(1, scale, 1);
      bar.position.y = scale / 2;
      (bar.material as THREE.MeshBasicMaterial).color.set(this.color);
    });
    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.text("appearance.audioAnalyzer", "Audio analyzer", {
          parentId: "appearance",
          get: () => this.audioAnalyzer,
          set: (v) => {
            this.audioAnalyzer = v;
          },
        }),
        this.slider("appearance.spacing", "Spacing", {
          parentId: "appearance",
          min: 0.1,
          max: 20,
          step: 0.1,
          get: () => this.spacing,
          set: (v) => {
            this.spacing = v;
            this.createBars(this.size);
          },
        }),
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
      ],
    };
  }
}

interface ParticleLineState {
  line: Line2;
  material: LineMaterial;
  flat: number[];
  reverse: number[];
  speed: number;
  current: number;
  visibleLength: number;
}

interface ConfettiFlake {
  geo: THREE.Mesh;
  velX: number;
  velY: number;
  velZ: number;
}

const SHADER_ITEM_VERTEX = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

function formatShaderItemSource(source: string): string {
  let code = source;
  code = code
    .replace("#extension GL_OES_standard_derivatives : enable", "")
    .replace("uniform vec2 u_resolution;\n", "#define u_resolution resolution")
    .replace("uniform float u_time;\n", "#define u_time time")
    .replace("uniform float mouse;\n", "vec2 mouse = vec2(0.5, 0.5);\n");
  const define = (name: string, value: string) => {
    if (!code.includes(`#define ${name} ${value}`)) code = `#define ${name} ${value}\n${code}`;
  };
  define("iResolution", "resolution");
  define("u_resolution", "resolution");
  define("iTime", "time");
  define("u_time", "time");
  define("iChannel0", "u_img_tex");
  define("iChannel1", "u_lay_tex");
  define("iChannel2", "u_lay_tex2");
  define("iChannel3", "u_lay_tex3");
  define("iChannel4", "u_lay_tex4");
  const uniform = (declaration: string) => {
    // Sources often annotate the declaration with a trailing comment, so
    // matching the exact line missed it and produced a redefinition compile
    // error (minimal's shader declares u_img_tex/u_lay_tex itself).
    const name = declaration
      .replace(/^uniform\s+/, "")
      .replace(/[;,]/g, "")
      .trim()
      .split(/\s+/)
      .pop();
    if (!name) return;
    if (new RegExp(`\\buniform\\s+\\w+\\s+${name}\\b`).test(code)) return;
    code = `${declaration}\n${code}`;
  };
  uniform("uniform float time;");
  uniform("uniform vec2 resolution;");
  uniform("uniform sampler2D u_img_tex;");
  uniform("uniform sampler2D u_lay_tex;");
  uniform("uniform sampler2D u_lay_tex2;");
  uniform("uniform sampler2D u_lay_tex3;");
  uniform("uniform sampler2D u_lay_tex4;");
  uniform("uniform sampler2D u_analyzer_tex;");
  uniform("uniform float u_value;");
  for (let index = 2; index <= 6; index += 1) uniform(`uniform float u_value${index};`);
  for (let index = 1; index <= 5; index += 1) uniform(`uniform float u_g${index};`);
  if (!code.includes("void main(")) {
    code += `
void main(void) {
  mainImage(gl_FragColor, gl_FragCoord.xy);
}`;
  }
  return code;
}

/** Particles travelling along a custom vector path (reference module W). */
export class ParticleTimeLineNode extends SceneNode {
  readonly kind = NodeKind.ParticleTimeLine;
  readonly typeLabel = "Timeline";
  override readonly is3D = true;

  customPath = "";
  distanceDone = 0;
  maxTime = 4;
  nParticles = 2000;
  pointSize = 5;

  private points!: THREE.Points;
  private material!: THREE.ShaderMaterial;
  private texture: THREE.Texture;
  private timeOffsets!: Float32Array;
  private noise!: Float32Array;
  private sizes!: Float32Array;
  private positions: CustomPathPoint[] = [];
  private lastPath = "";

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    // Module `W` uses image module 460 (particle1.webp) as its sprite.
    this.texture = new THREE.TextureLoader().load("/media/particles/particle1.webp");
    this.build();
    this.initParticles();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -500);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
  }

  protected build(): void {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute([], 3));
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        inSize: { value: 1 },
        tDiffuse: { value: this.texture },
      },
      vertexShader: /* glsl */ `
        attribute float a_size;
        void main() {
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = 5. * a_size;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform sampler2D tDiffuse;
        void main() {
          gl_FragColor = texture2D(tDiffuse, gl_PointCoord);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });
    this.points = new THREE.Points(geometry, this.material);
    this.points.position.z = -500;
    this.group.add(this.points);
  }

  private initParticles(): void {
    this.timeOffsets = new Float32Array(this.nParticles);
    this.noise = new Float32Array(this.nParticles);
    this.sizes = new Float32Array(this.nParticles);
    for (let index = 0; index < this.nParticles; index += 1) {
      this.timeOffsets[index] = Math.random();
      this.noise[index] = Math.random();
      this.sizes[index] = 5 * (Math.random() + 0.5);
    }
    this.points.geometry.setAttribute("a_size", new THREE.Float32BufferAttribute(this.sizes, 1));
  }

  private positionOnPath(
    time: number,
    points: CustomPathPoint[],
    offset: number,
  ): { x: number; y: number } {
    return sampleCustomPath(time, points, offset, this.distanceDone);
  }

  sync(time: number): void {
    if (this.customPath !== this.lastPath) {
      this.positions = parseCustomPath(this.customPath);
      this.lastPath = this.customPath;
    }
    const positions = new Float32Array(this.nParticles * 3);
    for (let index = 0; index < this.nParticles; index += 1) {
      // A missing/quad path resolves to the origin, but the per-particle noise
      // jitter still applies — that is what module `W` does.
      const point = this.positionOnPath(time, this.positions, this.timeOffsets[index]);
      positions[3 * index] =
        500 * point.x + Math.sin(time * this.noise[index]) * this.noise[index] * 20;
      positions[3 * index + 1] =
        -500 * point.y + Math.cos(time * this.noise[index]) * this.noise[index] * 20;
      positions[3 * index + 2] = 0;
    }
    const geometry = this.points.geometry as THREE.BufferGeometry;
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.computeBoundingSphere();

    this.points.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.points.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      1,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "general", label: "General", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.customPathField("general.customPath", "Path", {
          parentId: "general",
          tooltip: "Vertices for custom path",
          get: () => this.customPath,
          set: (v) => {
            this.customPath = v;
            this.positions = parseCustomPath(v);
          },
        }),
        this.slider("general.distanceDone", "t", {
          parentId: "general",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.distanceDone,
          set: (v) => {
            this.distanceDone = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.points.geometry.dispose();
    this.material.dispose();
    this.texture.dispose();
  }
}

/** Butterchurn Milkdrop visualizer, ported from reference module 1349. */
export class ButterchurnNode extends SceneNode {
  readonly kind = NodeKind.Butterchurn;
  readonly typeLabel = "Butterchurn";

  src = "";
  color = "#ffffff";
  opacity = 1;
  presetName = "None";
  blendTime = 1;
  audioMultiplier = 1;
  updateSpeed = 1;
  /** Reference "Clear buffers": reset the visualizer at time 0, erasing afterimages. */
  wantsClearFrameBuffers = true;
  useAudioAnalyzer = false;
  audioAnalyzer = "analyzer_default";
  outputAA = false;
  fitToScreen = true;
  width = 960;
  height = 540;
  matchToCanvas = true;
  srcBlending = "SrcAlpha";
  dstBlending = "OneMinusSrcAlpha";
  blendEquation = "Add";

  presets: Record<string, unknown>;
  private glCanvas: HTMLCanvasElement;
  private displayCanvas: HTMLCanvasElement;
  private displayContext: CanvasRenderingContext2D;
  /** CPU-backed copy of the visualizer frame, uploaded to the canvas texture. */
  private uploadCanvas: HTMLCanvasElement;
  private uploadContext: CanvasRenderingContext2D;
  /** Size last pushed to the visualizer; `setRendererSize` recreates its buffer. */
  private visualizerSize = { width: 0, height: 0 };
  /** Frames captured since the texture was last recreated. */
  private captureFrames = 0;
  private texture: THREE.CanvasTexture;
  private material: THREE.MeshBasicMaterial;
  private mesh!: THREE.Mesh;
  private visualizer: any = null;
  private visualizerError = "";
  private presetReady = false;
  private prevTime = -1;
  /** Scratch buffer for the reference's mono (L+R)/2 Butterchurn input. */
  private mixedWindow = new Float32Array(1024);

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.presets = sortPresets({
      ...butterchurnPresetsLib.getPresets(),
      ...referenceButterchurnPresets,
    });
    this.initializeObjectMapping();
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.width = Math.max(160, Math.round(resolution.x));
    this.height = Math.max(90, Math.round(resolution.y));
    this.glCanvas = document.createElement("canvas");
    this.glCanvas.width = this.width;
    this.glCanvas.height = this.height;
    this.displayCanvas = document.createElement("canvas");
    this.displayCanvas.width = this.width;
    this.displayCanvas.height = this.height;
    // `displayCanvas` receives the visualizer's own 2D blit of its WebGL frame.
    // During long playback that frame is still readable from the canvas while the
    // canvas texture we hand to three.js samples as fully transparent, which made
    // both butterchurn layers - and the Color Tint + Transform chain that turns
    // them into the yellow spectrum band - vanish from the capture. Upload from a
    // separate CPU-backed canvas so the texture always reads the pixels we just
    // copied rather than a GPU shared image.
    this.displayContext = this.displayCanvas.getContext("2d", {
      willReadFrequently: true,
    })!;
    this.uploadCanvas = document.createElement("canvas");
    this.uploadCanvas.width = this.width;
    this.uploadCanvas.height = this.height;
    this.uploadContext = this.uploadCanvas.getContext("2d", {
      willReadFrequently: true,
    })!;
    this.texture = new THREE.CanvasTexture(this.uploadCanvas);
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;
    this.material = new THREE.MeshBasicMaterial({
      map: this.texture,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: this.opacity,
    });
    this.build();
    this.initVisualizer();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const aspect = resolution.x / Math.max(1, resolution.y);
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2 * aspect, 2), this.material);
    this.mesh.position.z = this.readNumber("transform.z") * REFERENCE_SCALE;
    this.group.add(this.mesh);
  }

  private initVisualizer(): void {
    try {
      this.visualizer = butterchurnLib.createVisualizer(null, this.glCanvas, {
        width: this.width,
        height: this.height,
      });
      // The reference build draws through a 2D output canvas; npm builds do not
      // expose setCanvas and are read back from WebGL instead.
      this.visualizer.setCanvas?.(this.displayCanvas);
      this.visualizer.setOutputAA(this.outputAA);
    } catch (error) {
      this.visualizer = null;
      this.visualizerError = String(error);
    }
  }

  private rotateTexture(): void {
    const previous = this.texture;
    const next = new THREE.CanvasTexture(this.uploadCanvas);
    next.minFilter = THREE.LinearFilter;
    next.magFilter = THREE.LinearFilter;
    next.generateMipmaps = false;
    this.texture = next;
    this.material.map = next;
    this.material.needsUpdate = true;
    previous.dispose();
  }

  private updateSize(): void {
    if (!this.visualizer) return;
    // setRendererSize composes a frame and needs the preset's frame variables;
    // the WASM EEL path loads them asynchronously.
    if (!this.presetReady) return;
    if (this.matchToCanvas) {
      const resolution = this.ctx.resolution?.() ?? { x: this.width, y: this.height };
      this.width = Math.max(160, Math.round(resolution.x));
      this.height = Math.max(90, Math.round(resolution.y));
    }
    if (this.glCanvas.width !== this.width || this.glCanvas.height !== this.height) {
      // three allocates a canvas texture with immutable `texStorage2D` storage.
      // Resizing the canvas afterwards makes every later upload a texSubImage2D
      // that is larger than the storage, which the driver rejects: the texture
      // stays the blank allocation (transparent black) for the rest of the
      // session, so the item composites nothing.
      this.texture.dispose();
      this.glCanvas.width = this.width;
      this.glCanvas.height = this.height;
      this.displayCanvas.width = this.width;
      this.displayCanvas.height = this.height;
      this.uploadCanvas.width = this.width;
      this.uploadCanvas.height = this.height;
      this.texture.needsUpdate = true;
    }
    // `setRendererSize` assigns internalCanvas.width/height, which recreates the
    // visualizer's WebGL drawing buffer. The reference only pushes a new size
    // when it changes, and sync runs at 60 Hz, so calling it every frame churned
    // the whole preset pipeline for nothing.
    if (this.visualizerSize.width !== this.width || this.visualizerSize.height !== this.height) {
      this.visualizerSize = { width: this.width, height: this.height };
      this.visualizer.setRendererSize(this.width, this.height);
    }
  }

  private capture(): void {
    if (this.visualizer?.setCanvas) {
      // render() already drew the internal canvas into displayCanvas; copy it
      // into the CPU-backed upload canvas the texture samples.
      this.uploadContext.clearRect(0, 0, this.uploadCanvas.width, this.uploadCanvas.height);
      this.uploadContext.drawImage(this.displayCanvas, 0, 0);
      this.texture.needsUpdate = true;
      // A long-lived canvas texture stops reaching the GPU partway through a
      // playback: the canvas keeps the frame, `texture.needsUpdate` keeps
      // bumping the version, and the texture still samples as fully transparent
      // (measured at 34.63 s: canvas mean 9-14, texture mean 0). A freshly
      // created texture from the same canvas uploads correctly, so rotate it
      // about once per second instead of trusting one GL texture for the whole
      // timeline.
      this.captureFrames += 1;
      if (this.captureFrames % 60 === 0) this.rotateTexture();
      return;
    }
    if (!this.visualizer?.renderer?.gl) return;
    const gl = this.visualizer.renderer.gl;
    const width = this.glCanvas.width;
    const height = this.glCanvas.height;
    const pixels = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    const image = this.uploadContext.createImageData(width, height);
    const row = width * 4;
    for (let y = 0; y < height; y += 1) {
      const source = (height - 1 - y) * row;
      image.data.set(pixels.subarray(source, source + row), y * row);
    }
    this.uploadContext.putImageData(image, 0, 0);
    this.texture.needsUpdate = true;
  }

  renderPreset(): void {
    if (!this.visualizer || this.presetName === "None") return;
    const preset = this.presets[this.presetName];
    if (!preset) return;
    this.presetReady = false;
    const visualizer = this.visualizer;
    const ready = (): void => {
      if (this.visualizer !== visualizer) return;
      this.presetReady = true;
      this.updateSize();
    };
    try {
      const result = visualizer.loadPreset(preset, this.blendTime);
      if (result && typeof result.then === "function") {
        void result.then(ready).catch(() => {
          if (this.visualizer === visualizer) this.visualizerError = "preset load failed";
        });
      } else {
        ready();
      }
    } catch (error) {
      this.visualizerError = String(error);
    }
  }

  /**
   * Reference `clearFrameBuffers()`: wipe the visualizer's history textures and
   * internal clock so an export starting at 0 does not inherit preview trails.
   */
  clearFrameBuffers(): void {
    if (!this.visualizer || !this.presetReady) return;
    const renderer = this.visualizer.renderer;
    try {
      renderer.frameNum = 0;
      renderer.time = 0;
      renderer.presetTime = 0;
      renderer.lastTime = performance.now();
      renderer.timeHist = [0];
      const gl = renderer.gl;
      const empty = new Uint8Array(renderer.texsizeX * renderer.texsizeY * 4);
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        renderer.texsizeX,
        renderer.texsizeY,
        0,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        empty,
      );
      gl.generateMipmap(gl.TEXTURE_2D);
      for (const [buffer, bound] of [
        [renderer.prevFrameBuffer, renderer.prevTexture],
        [renderer.targetFrameBuffer, renderer.targetTexture],
        [renderer.compFrameBuffer, renderer.compTexture],
      ] as const) {
        gl.bindFramebuffer(gl.FRAMEBUFFER, buffer);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
        renderer.bindFrameBufferTexture(buffer, bound);
      }
      renderer.audioLevels.val.fill(0);
      renderer.audioLevels.imm.fill(0);
      renderer.audioLevels.att.fill(1);
      renderer.audioLevels.avg.fill(1);
      renderer.audioLevels.longAvg.fill(1);
    } catch {
      // A different butterchurn build may not expose every internal buffer;
      // resetting its clock still restarts the preset from silence.
      renderer.frameNum = 0;
      renderer.presetTime = 0;
      renderer.timeHist = [0];
    }
  }

  private audioLevels(): { timeByteArray: Uint8Array; timeByteArrayL: Uint8Array; timeByteArrayR: Uint8Array } | null {
    if (this.useAudioAnalyzer) {
      const values = this.ctx.spectrumFor?.(this.audioAnalyzer) ?? this.ctx.spectrum();
      const bytes = new Uint8Array(values.length);
      for (let index = 0; index < values.length; index += 1) {
        const value = Number.isFinite(values[index]) ? values[index] : 0;
        bytes[index] = Math.max(0, Math.min(255, Math.floor((value / 2) * this.audioMultiplier)));
      }
      return { timeByteArray: bytes, timeByteArrayL: bytes, timeByteArrayR: bytes };
    }
    const windows = this.ctx.waveformWindowChannels?.(1024, this.frameTimeFallback);
    const left = windows?.[0] ?? this.ctx.waveformWindow?.(1024, this.frameTimeFallback) ?? this.ctx.waveform();
    const right = windows?.[1] ?? left;
    if (this.mixedWindow.length !== left.length) this.mixedWindow = new Float32Array(left.length);
    for (let index = 0; index < left.length; index += 1) {
      this.mixedWindow[index] = (left[index] + right[index]) / 2;
    }
    const convert = (values: Float32Array): Uint8Array => {
      const bytes = new Uint8Array(values.length);
      for (let index = 0; index < values.length; index += 1) {
        bytes[index] = Math.floor(127.5 * (values[index] + 1) * this.audioMultiplier);
      }
      return bytes;
    };
    // Reference channel mapping: mono averages L/R, `timeByteArrayL` receives the
    // second channel and `timeByteArrayR` the first.
    return {
      timeByteArray: convert(this.mixedWindow),
      timeByteArrayL: convert(right),
      timeByteArrayR: convert(left),
    };
  }

  private frameTimeFallback = 0;

  sync(time: number): void {
    this.frameTimeFallback = time;
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const aspect = resolution.x / Math.max(1, resolution.y);
    const geometry = this.mesh.geometry as THREE.PlaneGeometry;
    if (Math.abs(geometry.parameters.width - 2 * aspect) > 0.001) {
      geometry.dispose();
      this.mesh.geometry = new THREE.PlaneGeometry(2 * aspect, 2);
    }
    this.updateSize();
    applyBlending(this.material, this.blendEquation, this.srcBlending, this.dstBlending);
    this.material.color.set(this.color);
    this.material.opacity = this.opacity;

    if (this.visualizer && this.presetReady) {
      // The reference refuses to update without data for the selected analyzer,
      // even when it renders from the waveform.
      if (!this.ctx.spectrumFor?.(this.audioAnalyzer)) return;
      if (time === 0 && this.wantsClearFrameBuffers) {
        this.clearFrameBuffers();
        this.texture.needsUpdate = true;
        this.prevTime = time;
        return;
      }
      const levels = this.audioLevels();
      if (levels && (this.prevTime !== time || this.texture.needsUpdate)) {
        try {
          this.visualizer.render({
            audioLevels: levels,
            elapsedTime: (1 / 60) * this.updateSpeed,
          });
          this.capture();
        } catch {
          /* ignore transient visualizer errors while resizing */
        }
      }
      this.prevTime = time;
    }

    let fitX = 1;
    let fitY = 1;
    if (this.fitToScreen) {
      fitX = aspect / (this.width / Math.max(1, this.height));
    }
    this.mesh.scale.set(fitX, fitY, 1);
    this.mesh.position.set(
      this.readNumber("transform.x") * REFERENCE_SCALE * (aspect > 1 ? aspect : 1),
      this.readNumber("transform.y") * REFERENCE_SCALE * (aspect > 1 ? 1 : aspect),
      this.readNumber("transform.z") * REFERENCE_SCALE,
    );
    this.mesh.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "preset", label: "Preset", kind: ContainerKind.Folder },
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "blending", label: "Blending", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.choose("preset.presetName", "Preset", {
          parentId: "preset",
          values: ["None", ...Object.keys(this.presets)],
          get: () => this.presetName,
          set: (v) => {
            this.presetName = v;
            this.renderPreset();
          },
        }),
        this.slider("preset.blendTime", "Blend time", {
          parentId: "preset",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.blendTime,
          set: (v) => {
            this.blendTime = v;
          },
        }),
        this.fileField("preset.src", "Preset file (.json)", {
          parentId: "preset",
          get: () => this.src,
          set: (v) => {
            this.src = v;
          },
        }),
        this.colorField("appearance.color", "Tint", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("appearance.opacity", "Opacity", {
          parentId: "appearance",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.opacity,
          set: (v) => {
            this.opacity = v;
          },
        }),
        this.toggle("appearance.outputAA", "Antialiasing", {
          parentId: "appearance",
          get: () => this.outputAA,
          set: (v) => {
            this.outputAA = v;
            this.visualizer?.setOutputAA(v);
          },
        }),
        this.toggle("appearance.fitToScreen", "Fit to screen", {
          parentId: "appearance",
          get: () => this.fitToScreen,
          set: (v) => {
            this.fitToScreen = v;
          },
        }),
        this.toggle("behaviour.useAudioAnalyzer", "Use audio analyzer", {
          parentId: "behaviour",
          get: () => this.useAudioAnalyzer,
          set: (v) => {
            this.useAudioAnalyzer = v;
          },
        }),
        this.text("behaviour.audioAnalyzer", "Audio analyzer", {
          parentId: "behaviour",
          get: () => this.audioAnalyzer,
          set: (v) => {
            this.audioAnalyzer = v;
          },
        }),
        this.slider("behaviour.audioMultiplier", "Audio multiplier", {
          parentId: "behaviour",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.audioMultiplier,
          set: (v) => {
            this.audioMultiplier = v;
          },
        }),
        this.slider("behaviour.updateSpeed", "Update time", {
          parentId: "behaviour",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.updateSpeed,
          set: (v) => {
            this.updateSpeed = v;
          },
        }),
        this.toggle("behaviour.wantsClearFrameBuffers", "Clear buffers", {
          parentId: "behaviour",
          get: () => this.wantsClearFrameBuffers,
          set: (v) => {
            this.wantsClearFrameBuffers = v;
            // Re-render the current frame so the clear takes effect immediately.
            this.prevTime = -1;
          },
        }),
        this.slider("behaviour.width", "Width", {
          parentId: "behaviour",
          min: 160,
          max: 3200,
          step: 1,
          get: () => this.width,
          set: (v) => {
            this.width = Math.round(v);
            this.updateSize();
          },
        }),
        this.slider("behaviour.height", "Height", {
          parentId: "behaviour",
          min: 90,
          max: 1800,
          step: 1,
          get: () => this.height,
          set: (v) => {
            this.height = Math.round(v);
            this.updateSize();
          },
        }),
        this.toggle("behaviour.matchToCanvas", "Match to render size", {
          parentId: "behaviour",
          get: () => this.matchToCanvas,
          set: (v) => {
            this.matchToCanvas = v;
            this.updateSize();
          },
        }),
        this.choose("blending.blendEquation", "Blend equation", {
          parentId: "blending",
          values: BLEND_EQUATIONS,
          get: () => this.blendEquation,
          set: (v) => {
            this.blendEquation = v;
          },
        }),
        this.choose("blending.srcBlending", "Source blend factor", {
          parentId: "blending",
          values: BLEND_FACTORS,
          get: () => this.srcBlending,
          set: (v) => {
            this.srcBlending = v;
          },
        }),
        this.choose("blending.dstBlending", "Dst blend factor", {
          parentId: "blending",
          values: BLEND_FACTORS,
          get: () => this.dstBlending,
          set: (v) => {
            this.dstBlending = v;
          },
        }),
      ],
    };
  }

  dispose(): void {
    // Each visualizer owns a WebGL context and (with EEL presets) a WASM
    // instance. Releasing the context keeps a 90-template import run from
    // exhausting the browser's context limit.
    try {
      const gl = this.visualizer?.renderer?.gl;
      gl?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      /* context may already be lost */
    }
    this.visualizer = null;
    this.texture.dispose();
    this.material.dispose();
    (this.mesh.geometry as THREE.BufferGeometry).dispose();
  }
}

/** Timeline-driven video item using a browser video texture. */
export class VideoNode extends SceneNode {
  readonly kind: NodeKind;
  readonly typeLabel: string;

  src = "";
  loop = true;
  fitToScreen = true;
  playbackRate = 1;
  /** Reference Video2 alphaInterpretation: "straight" or "premultiplied". */
  alphaInterpretation = "straight";
  /**
   * The export's authored `aspect`, or 0 when it has none.
   *
   * The reference `setScaling` fits the quad from the *item's* `aspect`
   * (`o = fitToScreen ? canvasAspect / aspect : 1`, mesh `(aspect * o, o)`),
   * and its export writes that member. `new-wayve`'s Background video is the
   * case that proves the value is used as authored: the export says `0.9`
   * while the local 450x450 transcode is square, and the reference frame's
   * white ring measures 407x450 px (h/w 1.106 = 1/0.9) where the square
   * reading draws 404x404. Refreshing from `videoWidth/videoHeight` always
   * overrode it; keep the authored value when the export has one.
   */
  authoredAspect = 0;

  /** Seconds into the video where the clip starts (trim-in / slip). */
  sourceIn = 0;
  blending = "normal";
  aspect = 16 / 9;

  private video: HTMLVideoElement;
  private texture: THREE.VideoTexture | null = null;
  private mesh!: THREE.Mesh;
  private lastSeek = -1;
  /**
   * Capture/replay hook: hold paused seeks until the harness reaches the final
   * playhead. A 60 Hz replay otherwise queues thousands of decode seeks.
   */
  deferSeeks = false;

  constructor(kind: NodeKind, name: string, ctx: NodeContext) {
    super(name, ctx);
    this.kind = kind;
    this.typeLabel =
      kind === NodeKind.Video2 ? "Video 2 (WebCodecs)" : "Video";
    this.initializeObjectMapping();
    this.video = document.createElement("video");
    this.video.muted = true;
    this.video.playsInline = true;
    this.video.preload = "auto";
    this.video.crossOrigin = "anonymous";
    this.video.loop = false;
    // Chrome only decodes frames for a media element that is in the document.
    // Keep it offscreen and inert; the timeline drives its currentTime.
    if (typeof document !== "undefined") {
      this.video.style.cssText =
        "position:fixed;left:-10000px;top:0;width:2px;height:2px;opacity:0;pointer-events:none";
      document.body.append(this.video);
    }
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -5);
    // Reference `scale`: one uniform factor, stored as a percent by controllers.
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const aspect = resolution.x / resolution.y;
    this.texture = new THREE.VideoTexture(this.video);
    this.texture.colorSpace = THREE.NoColorSpace;
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(2 * aspect, 2),
      new THREE.MeshBasicMaterial({
        map: this.texture,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      }),
    );
    this.mesh.position.z = this.readNumber("transform.z") * REFERENCE_SCALE;
    this.mesh.renderOrder = 5;
    this.group.add(this.mesh);
  }

  /** (Re)loads the current `src`; the importer calls this after assigning URLs. */
  loadSource(): void {
    if (!this.src) return;
    this.video.src = this.src;
    this.video.load();
    this.lastSeek = -1;
    this.video.addEventListener(
      "loadedmetadata",
      () => {
        if (this.video.videoWidth && this.video.videoHeight && this.authoredAspect <= 0) {
          this.aspect = this.video.videoWidth / this.video.videoHeight;
        }
        // Do not prime with play()/pause(): the reference's HTML video item
        // never plays unless the timeline is playing, and priming perturbs the
        // frame cache and currentTime before the first seek.
        this.lastSeek = -1;
      },
      { once: true },
    );
  }

  /** Source position for a timeline time, including trim-in and playback rate. */
  sourceTimeAt(time: number): number {
    return Math.max(0, (time - this.start) * this.playbackRate + this.sourceIn);
  }

  sync(time: number): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const frameAspect = resolution.x / Math.max(1, resolution.y);
    const videoMaterial = this.mesh.material as THREE.MeshBasicMaterial;
    const premultiplied = this.alphaInterpretation === "premultiplied";
    videoMaterial.premultipliedAlpha = premultiplied;
    if (premultiplied) {
      videoMaterial.blending = THREE.CustomBlending;
      videoMaterial.blendSrc = THREE.OneFactor;
      videoMaterial.blendDst = THREE.OneMinusSrcAlphaFactor;
      videoMaterial.blendEquation = THREE.AddEquation;
    } else {
      // Reference module 253: NO/NORMAL/ADD/MULTIPLY/SUBTRACT, mapped straight
      // onto three's modes (`main~b2b284db` @87798):
      //   `{[g.NO]:s.NoBlending,[g.NORMAL]:s.NormalBlending,
      //     [g.ADD]:s.AdditiveBlending,[g.SUBTRACT]:s.SubtractiveBlending,
      //     [g.MULTIPLY]:s.MultiplyBlending}`
      // so ADD is `SrcAlpha / One` on *both* colour and alpha. Three r116's
      // `setBlending` writes `blendFunc(SRC_ALPHA, ONE)` for it, which leaves an
      // opaque video's alpha at 1 in the layer buffer. Forcing the destination
      // alpha to 0 instead (CustomBlending with a Zero src-alpha factor) sent
      // `retro`'s VHS layer into its last pass with top alpha 0, where the
      // shipped Blending program takes
      //   `if (topPixel.a == 0.0) gl_FragColor = bottomPixel;`
      // with the unresolved ("Screen") base - i.e. it replaced the whole layer
      // with a transparent sample and the VHS overlay never reached the frame.
      const blending = String(this.blending).toLowerCase();
      if (blending === "add") {
        videoMaterial.blending = THREE.AdditiveBlending;
      } else {
        videoMaterial.blending =
          blending === "multiply"
            ? THREE.MultiplyBlending
            : blending === "subtract"
              ? THREE.SubtractiveBlending
              : blending === "no"
                ? THREE.NoBlending
                : THREE.NormalBlending;
      }
    }
    const geometry = this.mesh.geometry as THREE.PlaneGeometry;
    if (Math.abs(geometry.parameters.width - 2 * frameAspect) > 0.001) {
      geometry.dispose();
      this.mesh.geometry = new THREE.PlaneGeometry(2 * frameAspect, 2);
    }
    if (this.video.src && this.video.readyState >= 1) {
      const duration = this.video.duration || 0;
      // Reference module 585 `setTime(t)` is `video.currentTime = t % duration`
      // - plain project time, no trim-in arithmetic and no rate scaling. The
      // item's start only clips it out of the layer.
      let mediaTime = time;
      if (duration > 0) {
        mediaTime = this.loop
          ? ((mediaTime % duration) + duration) % duration
          : Math.max(0, Math.min(duration, mediaTime));
        if (this.ctx.playing?.()) {
          this.video.playbackRate = Math.max(0.1, Math.min(4, this.playbackRate));
          if (this.video.paused) {
            void this.video.play().catch(() => {});
          }
          // Let the decoder run; only correct real drift so playback is smooth.
          if (Math.abs(this.video.currentTime - mediaTime) > 0.35) {
            try {
              this.video.currentTime = mediaTime;
            } catch {
              /* seeking is best-effort while metadata loads */
            }
            this.lastSeek = mediaTime;
          }
        } else {
          if (!this.video.paused) this.video.pause();
          // The shipped HTML element path re-seeks on every `setTime`. The
          // capture harness defers those seeks to its final playhead: sending
          // one per replay frame leaves Chrome in readyState 1 and uploads a
          // black VideoTexture.
          if (this.deferSeeks) {
            this.lastSeek = -1;
          } else if (mediaTime !== this.lastSeek) {
            try {
              this.video.currentTime = mediaTime;
            } catch {
              /* seeking is best-effort while metadata loads */
            }
            this.lastSeek = mediaTime;
          }
        }
      } else if (!this.video.paused) {
        this.video.pause();
      }
    }

    // The reference's video mesh is a 500-unit square: `setScaling` computes
    // `o = fitToScreen ? canvasAspect / aspect : 1` and scales the mesh by
    // `(aspect * o, o)`. Our quad is the frame viewport (2*aspect x 2 world
    // units, 2 world = 1000 reference units), so halve the reference size.
    if (this.video.videoWidth > 0 && this.video.videoHeight > 0 && this.authoredAspect <= 0) {
      this.aspect = this.video.videoWidth / this.video.videoHeight;
    }
    const aspect = this.aspect > 0 ? this.aspect : frameAspect;
    const fitScale = this.fitToScreen ? frameAspect / aspect : 1;
    // Reference `Video.setScaling`: world size `(aspect * o, o)` frame-heights,
    // multiplied by the item's own scale (`scale` in the export). Our quad spans
    // the frame (2*aspect x 2 world units), so the width divides by the frame
    // aspect and the height is half the reference height.
    const itemScaleX = this.readNumber("transform.scaleX") / 100 || 1;
    const itemScaleY = this.readNumber("transform.scaleY") / 100 || 1;
    this.mesh.scale.set(
      (aspect * fitScale * itemScaleX) / frameAspect,
      fitScale * itemScaleY,
      1,
    );
    this.mesh.position.set(
      this.readNumber("transform.x") * REFERENCE_SCALE * (frameAspect > 1 ? frameAspect : 1),
      this.readNumber("transform.y") * REFERENCE_SCALE * (frameAspect > 1 ? 1 : frameAspect),
      this.readNumber("transform.z") * REFERENCE_SCALE,
    );
    this.mesh.visible = this.visible && Boolean(this.src);
    if (this.texture) this.texture.needsUpdate = true;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "media", label: "Media", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.fileField("media.src", "Video file", {
          parentId: "media",
          get: () => this.src,
          set: (v) => {
            this.src = v;
            this.loadSource();
          },
        }),
        this.toggle("media.loop", "Loop", {
          parentId: "media",
          get: () => this.loop,
          set: (v) => {
            this.loop = v;
          },
        }),
        this.toggle("media.fitToScreen", "Fit to screen", {
          parentId: "media",
          get: () => this.fitToScreen,
          set: (v) => {
            this.fitToScreen = v;
          },
        }),
        this.slider("media.playbackRate", "Playback rate", {
          parentId: "media",
          min: 0.1,
          max: 4,
          step: 0.01,
          get: () => this.playbackRate,
          set: (v) => {
            this.playbackRate = v;
          },
        }),
        this.slider("media.sourceIn", "Source in (s)", {
          parentId: "media",
          min: 0,
          max: 3600,
          step: 0.01,
          get: () => this.sourceIn,
          set: (v) => {
            this.sourceIn = Math.max(0, v);
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -200,
          max: 200,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.video.pause();
    this.video.removeAttribute("src");
    this.video.load();
    this.video.remove();
    this.texture?.dispose();
    (this.mesh.geometry as THREE.BufferGeometry).dispose();
    (this.mesh.material as THREE.Material).dispose();
  }
}

/** Lottie animation rendered through CanvasKit, ported from module 1389. */
export class SkottieNode extends SceneNode {
  readonly kind = NodeKind.Skottie;
  readonly typeLabel = "Skottie";

  animationDuration = 1;
  loaded = false;
  bounds = { fLeft: 0, fTop: 0, fRight: 533, fBottom: 500 };

  private canvas!: HTMLCanvasElement;
  private context!: CanvasRenderingContext2D;
  private lottieCanvas!: HTMLCanvasElement;
  private lottieContext!: CanvasRenderingContext2D;
  private texture!: THREE.CanvasTexture;
  private mesh!: THREE.Mesh;
  private lottie: AnimationItem | null = null;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
    void this.init();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.z", -5);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.canvas = document.createElement("canvas");
    this.canvas.width = Math.max(1, Math.round(resolution.x));
    this.canvas.height = Math.max(1, Math.round(resolution.y));
    this.context = this.canvas.getContext("2d")!;
    this.lottieCanvas = document.createElement("canvas");
    this.lottieCanvas.width = 60;
    this.lottieCanvas.height = 60;
    this.lottieContext = this.lottieCanvas.getContext("2d")!;
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.colorSpace = THREE.NoColorSpace;
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;
    const aspect = resolution.x / resolution.y;
    this.mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(2 * aspect, 2),
      new THREE.MeshBasicMaterial({
        map: this.texture,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      }),
    );
    this.mesh.position.z = this.readNumber("transform.z") * REFERENCE_SCALE;
    this.mesh.renderOrder = 10;
    this.group.add(this.mesh);
  }

  private async init(): Promise<void> {
    try {
      const lottieModule = await import("lottie-web");
      const lottie = lottieModule.default ?? lottieModule;
      const json = await (await fetch("/lottie/default.json")).json();
      this.lottie = lottie.loadAnimation<"canvas">({
        // A container would make lottie-web create (and size) its own canvas
        // from the detached wrapper, which is 0x0 here: every frame rendered
        // into that canvas and the item stayed invisible. Without a wrapper it
        // draws into the supplied context/canvas instead.
        container: null as unknown as Element,
        renderer: "canvas",
        loop: true,
        autoplay: false,
        animationData: json,
        rendererSettings: {
          context: this.lottieContext,
          clearCanvas: true,
        },
      });
      this.animationDuration =
        (this.lottie.totalFrames / Math.max(1, this.lottie.frameRate)) * 1000;
      this.loaded = true;
    } catch {
      this.loaded = false;
    }
  }

  sync(time: number): void {
    const resolution = this.ctx.resolution?.() ?? { x: this.canvas.width, y: this.canvas.height };
    const aspect = resolution.x / Math.max(1, resolution.y);
    const geometry = this.mesh.geometry as THREE.PlaneGeometry;
    if (Math.abs(geometry.parameters.width - 2 * aspect) > 0.001) {
      geometry.dispose();
      this.mesh.geometry = new THREE.PlaneGeometry(2 * aspect, 2);
    }
    this.mesh.position.set(0, 0, this.readNumber("transform.z") * REFERENCE_SCALE);
    this.mesh.visible = this.visible;

    if (!this.loaded || !this.lottie) return;
    const width = this.canvas.width;
    const height = this.canvas.height;
    if (this.canvas.width !== Math.round(resolution.x) || this.canvas.height !== Math.round(resolution.y)) {
      this.canvas.width = Math.round(resolution.x);
      this.canvas.height = Math.round(resolution.y);
      this.texture.needsUpdate = true;
      return;
    }
    const progress = this.animationDuration > 0 ? ((time - this.start) * 1000) / this.animationDuration % 1 : 0;
    const frame = (progress < 0 ? progress + 1 : progress) * Math.max(0, this.lottie.totalFrames - 1);
    this.lottie.goToAndStop(frame, true);
    this.context.clearRect(0, 0, width, height);
    this.context.drawImage(this.lottieCanvas, width / 2 - 30, height / 2 - 30, 60, 60);
    this.texture.needsUpdate = true;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [{ id: "transform", label: "Transform", kind: ContainerKind.Folder }],
      controllers: [
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -200,
          max: 100,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.texture.dispose();
    (this.mesh.geometry as THREE.BufferGeometry).dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.lottie?.destroy();
  }
}

/** Custom GLSL item, ported from reference module 1377. */
export class ShaderItemNode extends SceneNode {
  readonly kind = NodeKind.ShaderItem;
  readonly typeLabel = "Shader Item";
  override readonly is3D = true;

  src = "";
  private fragSource = DEFAULT_SHADER_ITEM_FRAGMENT;
  private vertSource = SHADER_ITEM_VERTEX;
  /**
   * The importer writes the reference fragment/vertex source after the node is
   * constructed, so the material has to be rebuilt when the source changes.
   * Without this the node kept rendering the built-in default shader (the green
   * wave) for every template (depth-xo, minimal, burning-moon, ...).
   */
  get fragInput(): string {
    return this.fragSource;
  }
  set fragInput(value: string) {
    if (value === this.fragSource) return;
    this.fragSource = value;
    if (this.material && this.mesh) this.recreateMaterial();
  }
  get vertInput(): string {
    return this.vertSource;
  }
  set vertInput(value: string) {
    if (value === this.vertSource) return;
    this.vertSource = value;
    if (this.material && this.mesh) this.recreateMaterial();
  }
  side: "front" | "back" | "double" = "double";
  fitToScreen = true;
  targetLayer = "";
  targetLayer2 = "";
  targetLayer3 = "";
  targetLayer4 = "";
  audioAnalyzer = "analyzer_default";
  value = 0;
  value2 = 0;
  value3 = 0;
  value4 = 0;
  value5 = 0;
  value6 = 0;
  srcBlending = "SrcAlpha";
  dstBlending = "OneMinusSrcAlpha";
  blendEquation = "Add";

  private material!: THREE.ShaderMaterial;
  private mesh!: THREE.Mesh;
  private imageTexture: THREE.Texture | null = null;
  private analyzerTexture: THREE.DataTexture | null = null;
  private analyzerLength = 0;
  private loadedImage = "";

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -100);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        u_img_tex: { value: null },
        u_lay_tex: { value: null },
        u_lay_tex2: { value: null },
        u_lay_tex3: { value: null },
        u_lay_tex4: { value: null },
        u_analyzer_tex: { value: null },
        time: { value: 0 },
        u_value: { value: 0 },
        u_value2: { value: 0 },
        u_value3: { value: 0 },
        u_value4: { value: 0 },
        u_value5: { value: 0 },
        u_value6: { value: 0 },
        u_g1: { value: 0 },
        u_g2: { value: 0 },
        u_g3: { value: 0 },
        u_g4: { value: 0 },
        u_g5: { value: 0 },
        resolution: { value: new THREE.Vector2(resolution.x, resolution.y) },
      },
      vertexShader: this.vertInput,
      fragmentShader: formatShaderItemSource(this.fragInput),
      transparent: true,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1000, 1000), this.material);
    // The reference constructs the plane at z=-100 but every saved project
    // carries `position:z` (the mesh's z, default -100), and applying it sets
    // the mesh z directly. The group below carries that same value, so the
    // mesh itself stays at the origin; otherwise loaded `position:z` values
    // stack on top of the -100 default (google's White plane at 0 sat behind
    // the background photo and never masked it).
    this.mesh.position.z = 0;
    this.group.add(this.mesh);
  }

  private setSide(): void {
    this.material.side =
      this.side === "double"
        ? THREE.DoubleSide
        : this.side === "front"
          ? THREE.FrontSide
          : THREE.BackSide;
  }

  private recreateMaterial(): void {
    this.material.dispose();
    this.material = new THREE.ShaderMaterial({
      uniforms: this.material.uniforms,
      vertexShader: this.vertInput,
      fragmentShader: formatShaderItemSource(this.fragInput),
      transparent: true,
    });
    this.mesh.material = this.material;
    this.setSide();
  }

  private loadImage(): void {
    if (!this.src || this.src === this.loadedImage) return;
    this.loadedImage = this.src;
    new THREE.TextureLoader().load(
      this.src,
      (texture) => {
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        this.imageTexture?.dispose();
        this.imageTexture = texture;
        this.material.uniforms.u_img_tex.value = texture;
        this.material.needsUpdate = true;
      },
      undefined,
      () => {
        this.imageTexture = null;
      },
    );
  }

  private updateAnalyzerTexture(values: Float32Array): void {
    if (this.analyzerLength !== values.length) {
      this.analyzerTexture?.dispose();
      const data = new Float32Array(values.length * 4);
      this.analyzerTexture = new THREE.DataTexture(
        data,
        values.length,
        1,
        THREE.RGBAFormat,
        THREE.FloatType,
      );
      this.analyzerTexture.needsUpdate = true;
      this.analyzerLength = values.length;
      this.material.uniforms.u_analyzer_tex.value = this.analyzerTexture;
    }
    const data = this.analyzerTexture?.image.data as Float32Array;
    for (let index = 0; index < values.length; index += 1) {
      const offset = index * 4;
      // The shipped `ShaderItem.getData` copies `audioAnalyzerData` straight
      // into the texture, i.e. the wasm's post-`outputMultiplier`/tilt values
      // (0..~200, peaks past 300). Our band arrays are normalised to 0..1 for
      // the rest of the editor, so undo that here: shaders that divide the
      // texture by 100 (`disk`'s palette lookup) otherwise land on the LUT's
      // black end.
      const value = values[index] * REFERENCE_VALUE_SCALE;
      data[offset] = value;
      data[offset + 1] = value;
      data[offset + 2] = value;
      data[offset + 3] = 1;
    }
    if (this.analyzerTexture) this.analyzerTexture.needsUpdate = true;
  }

  sync(time: number): void {
    this.loadImage();
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const aspect = resolution.x / Math.max(1, resolution.y);
    // Shipped ShaderItem.setScaling (module 1377):
    //   n = renderAspect; n !== this.aspect && (this.aspect = n);
    //   r = fitToScreen ? n / this.aspect : 1;
    // `this.aspect` is overwritten with the canvas aspect first, so r is always
    // 1 and fitToScreen has no effect on the mesh; the 1000-unit quad keeps
    // `scale` and only takes the canvas aspect on x (y in portrait).
    this.mesh.scale.set(
      aspect > 1 ? aspect : 1,
      aspect > 1 ? 1 : 1 / aspect,
      1,
    );

    const uniforms = this.material.uniforms;
    (uniforms.resolution.value as THREE.Vector2).set(resolution.x, resolution.y);
    uniforms.time.value = time;
    uniforms.u_value.value = this.value;
    uniforms.u_value2.value = this.value2;
    uniforms.u_value3.value = this.value3;
    uniforms.u_value4.value = this.value4;
    uniforms.u_value5.value = this.value5;
    uniforms.u_value6.value = this.value6;
    for (let index = 1; index <= 5; index += 1) {
      uniforms[`u_g${index}`].value = this.ctx.globalVar?.(index - 1) ?? 0;
    }
    uniforms.u_lay_tex.value = this.ctx.layerTexture?.(this.targetLayer) ?? null;
    uniforms.u_lay_tex2.value = this.ctx.layerTexture?.(this.targetLayer2) ?? null;
    uniforms.u_lay_tex3.value = this.ctx.layerTexture?.(this.targetLayer3) ?? null;
    uniforms.u_lay_tex4.value = this.ctx.layerTexture?.(this.targetLayer4) ?? null;
    const analyzer = this.ctx.spectrumFor?.(this.audioAnalyzer) ?? this.ctx.spectrum();
    this.updateAnalyzerTexture(analyzer);

    this.setSide();
    applyBlending(this.material, this.blendEquation, this.srcBlending, this.dstBlending);

    // Shipped ShaderItem constructor (module 1377):
    //   const r = h.a, c = h.a, p = new PlaneBufferGeometry(r, c, 1e3, 1e3);
    // with module 71 exporting `h.a = 1e3`, so the quad is 1000x1000 in the
    // reference's 1000-unit orthographic stage (Layer.createCamera:
    // `new OrthographicCamera(-e*n, e*n, e, -e, 0, 200)` with `e = 1000/2`).
    // Our 2D layer camera spans 2 units, so an orthographic ShaderItem's
    // position and scale map with `2/1000`. A perspective layer keeps the
    // reference's raw units: its plane sits at z=-100 under a fov-45 camera,
    // which the reference projects at the same 1000-unit scale we already use.
    const orthoUnit = this.ctx.orthographicLayer?.(this.id) === false ? 1 : 2 / 1000;
    const landscape = aspect > 1;
    this.group.position.set(
      this.readNumber("transform.x") * orthoUnit * (landscape ? aspect : 1),
      this.readNumber("transform.y") * orthoUnit * (landscape ? 1 : aspect),
      this.readNumber("transform.z") * orthoUnit,
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      (this.readNumber("transform.scaleX") / 100) * orthoUnit,
      (this.readNumber("transform.scaleY") / 100) * orthoUnit,
      (this.readNumber("transform.scaleZ") / 100) * orthoUnit,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "blending", label: "Blending", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.text("appearance.fragInput", "Fragment shader", {
          parentId: "appearance",
          get: () => this.fragInput,
          set: (v) => {
            this.fragInput = v;
            this.recreateMaterial();
          },
        }),
        this.text("appearance.vertInput", "Vertex shader", {
          parentId: "appearance",
          get: () => this.vertInput,
          set: (v) => {
            this.vertInput = v;
            this.recreateMaterial();
          },
        }),
        this.fileField("appearance.src", "Image texture", {
          parentId: "appearance",
          get: () => this.src,
          set: (v) => {
            this.src = v;
            this.loadImage();
          },
        }),
        this.text("appearance.targetLayer", "Target layer", {
          parentId: "appearance",
          get: () => this.targetLayer,
          set: (v) => {
            this.targetLayer = v;
          },
        }),
        this.text("appearance.targetLayer2", "Target layer 2", {
          parentId: "appearance",
          get: () => this.targetLayer2,
          set: (v) => {
            this.targetLayer2 = v;
          },
        }),
        this.text("appearance.targetLayer3", "Target layer 3", {
          parentId: "appearance",
          get: () => this.targetLayer3,
          set: (v) => {
            this.targetLayer3 = v;
          },
        }),
        this.text("appearance.targetLayer4", "Target layer 4", {
          parentId: "appearance",
          get: () => this.targetLayer4,
          set: (v) => {
            this.targetLayer4 = v;
          },
        }),
        this.choose("appearance.side", "Side", {
          parentId: "behaviour",
          values: ["front", "back", "double"],
          get: () => this.side,
          set: (v) => {
            this.side = v as typeof this.side;
            this.setSide();
          },
        }),
        this.toggle("appearance.fitToScreen", "Fit to screen", {
          parentId: "behaviour",
          get: () => this.fitToScreen,
          set: (v) => {
            this.fitToScreen = v;
          },
        }),
        ...[1, 2, 3, 4, 5, 6].map((index) =>
          this.slider(`behaviour.value${index}`, `Uniform u_value${index === 1 ? "" : index}`, {
            parentId: "behaviour",
            min: -1000,
            max: 1000,
            step: 0.1,
            get: () => (this as unknown as Record<string, number>)[index === 1 ? "value" : `value${index}`],
            set: (v) => {
              (this as unknown as Record<string, number>)[index === 1 ? "value" : `value${index}`] = v;
            },
          }),
        ),
        this.choose("blending.blendEquation", "Blend equation", {
          parentId: "blending",
          values: BLEND_EQUATIONS,
          get: () => this.blendEquation,
          set: (v) => {
            this.blendEquation = v;
          },
        }),
        this.choose("blending.srcBlending", "Source blend factor", {
          parentId: "blending",
          values: BLEND_FACTORS,
          get: () => this.srcBlending,
          set: (v) => {
            this.srcBlending = v;
          },
        }),
        this.choose("blending.dstBlending", "Dst blend factor", {
          parentId: "blending",
          values: BLEND_FACTORS,
          get: () => this.dstBlending,
          set: (v) => {
            this.dstBlending = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.material.dispose();
    this.imageTexture?.dispose();
    this.analyzerTexture?.dispose();
  }
}

/** Confetti particle field, ported from reference module 1353. */
export class ConfettiNode extends SceneNode {
  readonly kind = NodeKind.Confetti;
  readonly typeLabel = "Confetti";
  override readonly is3D = true;

  width = 1000;
  height = 1000;
  depth = 1000;
  fall = 2;
  swirl = 1;
  step = 100;
  flakeCount = 1000;
  shape = "hexagon";
  hemisphereSkyColor = "#114417";
  hemisphereGroundColor = "#ffffff";
  hemisphereSkyIntensity = 0.3;
  light2Color = "#ff0000";
  light3Color = "#00ff00";
  light4Color = "#3333ff";

  private material!: THREE.MeshPhongMaterial;
  private flakes: ConfettiFlake[] = [];
  private geometry!: THREE.BufferGeometry;
  private lights: THREE.Light[] = [];
  private noise = createNoise3D();

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.rotX", -90);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.material = new THREE.MeshPhongMaterial({
      color: 0xffffff,
      specular: 0xffffff,
      shininess: 100,
      side: THREE.DoubleSide,
      flatShading: true,
      blending: THREE.AdditiveBlending,
    });
    const hemisphere = new THREE.HemisphereLight(0xffffff, 0xffffff, 0.3);
    hemisphere.position.set(0, 0, -this.depth);
    hemisphere.lookAt(0, 0, -1);
    const light2 = new THREE.DirectionalLight(0xff0000, 1);
    light2.position.set(-1, 1, 1);
    const light3 = new THREE.DirectionalLight(0x00ff00, 1);
    light3.position.set(-1, -1, 1);
    const light4 = new THREE.DirectionalLight(0x3333ff, 1);
    light4.position.set(1, -1, 1);
    this.lights = [hemisphere, light2, light3, light4];
    for (const light of this.lights) this.group.add(light);
    this.group.rotation.x = -Math.PI / 2;
    this.updateShape();
    this.initFlakes();
  }

  private polygonGeometry(sides: number, radius: number): THREE.BufferGeometry {
    const vertices: THREE.Vector3[] = [];
    for (let index = 0; index < sides; index += 1) {
      const angle = (index * 2 * Math.PI) / sides;
      vertices.push(new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0));
    }
    const faces: number[] = [];
    for (let index = 1; index < sides - 1; index += 1) {
      faces.push(0, index, index + 1);
    }
    return this.makeGeometry(vertices, faces);
  }

  private makeGeometry(vertices: THREE.Vector3[], faces: number[]): THREE.BufferGeometry {
    const positions: number[] = [];
    for (const vertex of vertices) positions.push(vertex.x, vertex.y, vertex.z);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(faces);
    geometry.computeVertexNormals();
    return geometry;
  }

  private squareGeometry(size: number): THREE.BufferGeometry {
    const half = size / 2;
    return this.makeGeometry(
      [
        new THREE.Vector3(-half, half, 0),
        new THREE.Vector3(half, half, 0),
        new THREE.Vector3(half, -half, 0),
        new THREE.Vector3(-half, -half, 0),
      ],
      [0, 1, 2, 0, 2, 3],
    );
  }

  private triangleGeometry(size: number): THREE.BufferGeometry {
    const height = size * (Math.sqrt(3) / 2);
    return this.makeGeometry(
      [
        new THREE.Vector3(-size / 2, -height / 3, 0),
        new THREE.Vector3(size / 2, -height / 3, 0),
        new THREE.Vector3(0, (2 * height) / 3, 0),
      ],
      [0, 1, 2],
    );
  }

  private starGeometry(inner: number, outer: number, points: number): THREE.BufferGeometry {
    const vertices: THREE.Vector3[] = [];
    const angle = (2 * Math.PI) / (2 * points);
    for (let index = 0; index < 2 * points; index += 1) {
      const radius = index % 2 === 0 ? outer : inner;
      vertices.push(new THREE.Vector3(Math.cos(index * angle) * radius, Math.sin(index * angle) * radius, 0));
    }
    vertices.push(new THREE.Vector3(0, 0, 0));
    const faces: number[] = [];
    for (let index = 0; index < 2 * points; index += 1) {
      faces.push(2 * points, index, (index + 1) % (2 * points));
    }
    return this.makeGeometry(vertices, faces);
  }

  private randomShape(): THREE.BufferGeometry {
    const sides = Math.floor(6 * Math.random()) + 3;
    return this.polygonGeometry(sides, 3 * Math.random() + 1).scale(2, 2, 2);
  }

  private updateShape(): void {
    this.geometry?.dispose();
    switch (this.shape) {
      case "circle":
        this.geometry = this.polygonGeometry(32, 1);
        break;
      case "square":
        this.geometry = this.squareGeometry(1);
        break;
      case "triangle":
        this.geometry = this.triangleGeometry(1);
        break;
      case "star":
        this.geometry = this.starGeometry(0.5, 1, 5);
        break;
      case "random":
        this.geometry = this.randomShape();
        break;
      case "hexagon":
      default:
        this.geometry = this.polygonGeometry(6, 1);
        break;
    }
    this.geometry.scale(7, 7, 7);
  }

  private initFlakes(): void {
    for (const flake of this.flakes) this.group.remove(flake.geo);
    this.flakes = [];
    for (let index = 0; index < this.flakeCount; index += 1) {
      const geometry = this.shape === "random" ? this.randomShape() : this.geometry;
      const mesh = new THREE.Mesh(geometry, this.material);
      mesh.position.set(
        this.width / 2 - Math.random() * this.width,
        this.height / 2 - Math.random() * this.height,
        this.depth / 2 - Math.random() * this.depth,
      );
      mesh.rotation.set(2 * (Math.random() - 1), 2 * (Math.random() - 1), 2 * (Math.random() - 1));
      mesh.scale.set(0.25, 0.25, 0.25);
      this.flakes.push({
        geo: mesh,
        velX: 0.5 - Math.random(),
        velY: 0.5 - Math.random(),
        velZ: 0.5 - Math.random(),
      });
      this.group.add(mesh);
    }
  }

  sync(time: number): void {
    void time;
    const [hemisphere, light2, light3, light4] = this.lights as [
      THREE.HemisphereLight,
      THREE.DirectionalLight,
      THREE.DirectionalLight,
      THREE.DirectionalLight,
    ];
    hemisphere.color.set(this.hemisphereSkyColor);
    hemisphere.groundColor.set(this.hemisphereGroundColor);
    hemisphere.intensity = this.hemisphereSkyIntensity;
    light2.color.set(this.light2Color);
    light3.color.set(this.light3Color);
    light4.color.set(this.light4Color);

    const cross = new THREE.Vector3();
    const step = this.step;
    for (const flake of this.flakes) {
      const position = flake.geo.position;
      cross.set(position.y * 1, position.z * 0, 0);
      cross.x = position.y * 1 - position.z * 0;
      cross.y = position.z * 0 - position.x * 1;
      cross.z = position.x * 0 - position.y * 0;
      const length = Math.sqrt(cross.x * cross.x + cross.y * cross.y + cross.z * cross.z) || 1;
      flake.velX = this.swirl * (cross.x / length);
      flake.velY = this.swirl * (cross.y / length);

      const x = position.x / step;
      const y = position.y / step;
      const z = position.z / step;
      const epsilon = 1e-4;
      const curlX = (this.noise(x, y + epsilon, z) - this.noise(x, y - epsilon, z)) / (2 * epsilon);
      const curlY = (this.noise(x, y, z + epsilon) - this.noise(x, y, z - epsilon)) / (2 * epsilon);
      const curlZ = (this.noise(x + epsilon, y, z) - this.noise(x - epsilon, y, z)) / (2 * epsilon);
      const curlLength = Math.sqrt(curlX * curlX + curlY * curlY + curlZ * curlZ) || 1;
      flake.velX -= (this.fall / 4) * (curlX / curlLength);
      flake.velY -= (this.fall / 4) * (curlY / curlLength);
      if (this.fall > 0) {
        flake.velZ -= this.fall / 60;
        flake.velZ = Math.max(flake.velZ, -this.fall);
      } else {
        flake.velZ = 0;
      }
      flake.geo.rotation.x += flake.velX / 10 + flake.velZ / 60;
      flake.geo.rotation.y += flake.velY / 10 + flake.velZ / 60;
      flake.geo.visible = Math.sqrt(position.x ** 2 + position.y ** 2 + position.z ** 2) <= this.width / 2;
      if (position.z < -this.depth / 2 || Math.sqrt(position.x ** 2 + position.y ** 2) > this.width) {
        position.set(
          this.width / 2 - Math.random() * this.width,
          this.height / 2 - Math.random() * this.height,
          this.depth / 2,
        );
        flake.velX = 0;
        flake.velY = 0;
      } else {
        position.x += flake.velX;
        position.y += flake.velY;
        position.z += flake.velZ;
      }
    }

    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.colorField("appearance.light2Color", "Light 1 color", {
          parentId: "appearance",
          get: () => this.light2Color,
          set: (v) => {
            this.light2Color = v;
          },
        }),
        this.colorField("appearance.light3Color", "Light 2 color", {
          parentId: "appearance",
          get: () => this.light3Color,
          set: (v) => {
            this.light3Color = v;
          },
        }),
        this.colorField("appearance.light4Color", "Light 3 color", {
          parentId: "appearance",
          get: () => this.light4Color,
          set: (v) => {
            this.light4Color = v;
          },
        }),
        this.choose("appearance.shape", "Shape", {
          parentId: "appearance",
          values: ["hexagon", "circle", "square", "triangle", "star", "random"],
          get: () => this.shape,
          set: (v) => {
            this.shape = v;
            this.updateShape();
            this.initFlakes();
          },
        }),
        this.slider("appearance.fall", "Fall", {
          parentId: "appearance",
          min: -15,
          max: 15,
          step: 0.1,
          get: () => this.fall,
          set: (v) => {
            this.fall = v;
          },
        }),
        this.slider("appearance.swirl", "Swirl", {
          parentId: "appearance",
          min: -5,
          max: 5,
          step: 0.01,
          get: () => this.swirl,
          set: (v) => {
            this.swirl = v;
          },
        }),
        this.slider("appearance.flakeCount", "Nr. flakes", {
          parentId: "appearance",
          min: 1,
          max: 10000,
          step: 1,
          get: () => this.flakeCount,
          set: (v) => {
            this.flakeCount = Math.round(v);
            this.initFlakes();
          },
        }),
        this.colorField("appearance.hemisphereSkyColor", "Hemisphere sky", {
          parentId: "appearance",
          get: () => this.hemisphereSkyColor,
          set: (v) => {
            this.hemisphereSkyColor = v;
          },
        }),
        this.colorField("appearance.hemisphereGroundColor", "Hemisphere ground", {
          parentId: "appearance",
          get: () => this.hemisphereGroundColor,
          set: (v) => {
            this.hemisphereGroundColor = v;
          },
        }),
        this.slider("appearance.hemisphereSkyIntensity", "Hemisphere intensity", {
          parentId: "appearance",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.hemisphereSkyIntensity,
          set: (v) => {
            this.hemisphereSkyIntensity = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    for (const flake of this.flakes) {
      flake.geo.geometry.dispose();
    }
    this.geometry?.dispose();
    this.material.dispose();
  }
}

/** Time-based additive particle system, ported from reference module 1372. */
export class ParticleSystemNode extends SceneNode {
  readonly kind = NodeKind.ParticleSystem;
  readonly typeLabel = "Particle System";
  override readonly is3D = true;

  instances = 1200;
  timeToLive = 5;
  origin = "Point";
  startX = -1;
  startY = -1;
  startZ = -1;
  endX = 1;
  endY = 1;
  endZ = 1;
  baseSpeed = 0.3;
  rotation = 0;
  reactiveScaling = 1;
  pointSize = 1;
  alphaMult = 1;

  private points!: THREE.Points;
  private material!: THREE.RawShaderMaterial;
  private texture!: THREE.Texture;
  private geometry!: THREE.InstancedBufferGeometry;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    this.texture = new THREE.TextureLoader().load("/img/lensflare0_alpha.png");
    this.texture.premultiplyAlpha = true;
    this.geometry = new THREE.InstancedBufferGeometry();
    this.init();
    this.material = new THREE.RawShaderMaterial({
      uniforms: {
        time: { value: 1 },
        timeToLive: { value: this.timeToLive },
        realTime: { value: 0 },
        scale: { value: this.pointSize },
        sineTime: { value: 1 },
        alpha: { value: 0.3 },
        texture: { value: this.texture },
      },
      vertexShader: /* glsl */ `
        precision highp float;
        uniform float sineTime;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        attribute float startTime;
        attribute vec4 color;
        attribute vec3 orientationStart;
        uniform float time;
        uniform float scale;
        uniform float realTime;
        uniform float timeToLive;
        varying vec3 vPosition;
        varying vec4 vColor;
        void main() {
          float diff = mod(realTime + startTime, timeToLive);
          vPosition = orientationStart * diff;
          vColor = color;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(vPosition, 1.0);
          gl_PointSize = 30.;
        }
      `,
      fragmentShader: /* glsl */ `
        precision highp float;
        uniform float time;
        uniform float alpha;
        uniform sampler2D texture;
        varying vec3 vPosition;
        varying vec4 vColor;
        void main() {
          vec4 color = vec4(vColor);
          color.r += sin(vPosition.x * 10.0 + time) * 0.5;
          gl_FragColor = color * texture2D(texture, gl_PointCoord);
          gl_FragColor.a = 1.;
        }
      `,
      depthTest: false,
      depthWrite: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });
    this.points = new THREE.Points(this.geometry, this.material);
    this.points.renderOrder = 999;
    this.group.add(this.points);
  }

  private init(): void {
    if (!this.geometry) return;
    const startTimes: number[] = [];
    const colors: number[] = [];
    const orientations: number[] = [];
    const vector = new THREE.Vector3();
    for (let index = 0; index < this.instances; index += 1) {
      startTimes.push(Math.random() * this.timeToLive);
      colors.push(Math.random(), Math.random(), Math.random(), Math.random());
      vector.set(2 * Math.random() - 1, 2 * Math.random() - 1, 2 * Math.random() - 1).normalize();
      orientations.push(vector.x, vector.y, vector.z);
    }
    this.geometry.setAttribute("startTime", new THREE.Float32BufferAttribute(startTimes, 1));
    this.geometry.setAttribute(
      "color",
      new THREE.InstancedBufferAttribute(new Float32Array(colors), 4),
    );
    this.geometry.setAttribute(
      "orientationStart",
      new THREE.InstancedBufferAttribute(new Float32Array(orientations), 3),
    );
    this.geometry.computeBoundingSphere();
  }

  sync(time: number): void {
    this.material.uniforms.realTime.value = Math.max(time, 0.01);
    this.material.uniforms.timeToLive.value = this.timeToLive;
    this.material.uniforms.scale.value = this.pointSize;
    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "basics", label: "Basics", kind: ContainerKind.Folder },
        { id: "origin", label: "Origin", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.slider("basics.instances", "Instances", {
          parentId: "basics",
          min: 10,
          max: 5000,
          step: 4,
          get: () => this.instances,
          set: (v) => {
            this.instances = Math.round(v);
            this.init();
          },
        }),
        this.slider("basics.baseSpeed", "Base speed", {
          parentId: "basics",
          min: 0,
          max: 5,
          get: () => this.baseSpeed,
          set: (v) => {
            this.baseSpeed = v;
          },
        }),
        this.slider("basics.reactiveScaling", "Reactive scaling", {
          parentId: "basics",
          min: 0,
          max: 5,
          get: () => this.reactiveScaling,
          set: (v) => {
            this.reactiveScaling = v;
          },
        }),
        this.slider("basics.pointSize", "Point size", {
          parentId: "basics",
          min: 0,
          max: 10,
          get: () => this.pointSize,
          set: (v) => {
            this.pointSize = v;
          },
        }),
        this.slider("basics.alphaMult", "Alpha multiplier", {
          parentId: "basics",
          min: 0,
          max: 5,
          get: () => this.alphaMult,
          set: (v) => {
            this.alphaMult = v;
          },
        }),
        this.choose("origin.origin", "Origin", {
          parentId: "origin",
          values: ["Point", "Box"],
          get: () => this.origin,
          set: (v) => {
            this.origin = v;
          },
        }),
        this.slider("origin.startX", "Direction X from", {
          parentId: "origin",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.startX,
          set: (v) => {
            this.startX = v;
          },
        }),
        this.slider("origin.endX", "Direction X to", {
          parentId: "origin",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.endX,
          set: (v) => {
            this.endX = v;
          },
        }),
        this.slider("origin.startY", "Direction Y from", {
          parentId: "origin",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.startY,
          set: (v) => {
            this.startY = v;
          },
        }),
        this.slider("origin.endY", "Direction Y to", {
          parentId: "origin",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.endY,
          set: (v) => {
            this.endY = v;
          },
        }),
        this.slider("origin.startZ", "Direction Z from", {
          parentId: "origin",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.startZ,
          set: (v) => {
            this.startZ = v;
          },
        }),
        this.slider("origin.endZ", "Direction Z to", {
          parentId: "origin",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.endZ,
          set: (v) => {
            this.endZ = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.points.geometry.dispose();
    this.material.dispose();
    this.texture.dispose();
  }
}

/** Instanced additive particle cloud, ported from reference module 1364. */
export class InstancedParticleSystemNode extends SceneNode {
  readonly kind = NodeKind.InstancedParticleSystem;
  readonly typeLabel = "Instanced Particle System";
  override readonly is3D = true;

  private points!: THREE.Points;
  private material!: THREE.RawShaderMaterial;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", 0);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    const count = 3000;
    const offsets: number[] = [];
    const colors: number[] = [];
    const starts: number[] = [];
    const ends: number[] = [];
    const vector = new THREE.Vector4();
    for (let index = 0; index < count; index += 1) {
      offsets.push(Math.random(), Math.random(), Math.random());
      colors.push(Math.random(), Math.random(), Math.random(), Math.random());
      vector.set(
        2 * Math.random() - 1,
        2 * Math.random() - 1,
        2 * Math.random() - 1,
        2 * Math.random() - 1,
      ).normalize();
      starts.push(vector.x, vector.y, vector.z, vector.w);
      vector.set(
        2 * Math.random() - 1,
        2 * Math.random() - 1,
        2 * Math.random() - 1,
        2 * Math.random() - 1,
      ).normalize();
      ends.push(vector.x, vector.y, vector.z, vector.w);
    }

    const geometry = new THREE.InstancedBufferGeometry();
    geometry.instanceCount = count;
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute([0.025, -0.025, 0], 3),
    );
    geometry.setAttribute("offset", new THREE.InstancedBufferAttribute(new Float32Array(offsets), 3));
    geometry.setAttribute("color", new THREE.InstancedBufferAttribute(new Float32Array(colors), 4));
    geometry.setAttribute(
      "orientationStart",
      new THREE.InstancedBufferAttribute(new Float32Array(starts), 4),
    );
    geometry.setAttribute(
      "orientationEnd",
      new THREE.InstancedBufferAttribute(new Float32Array(ends), 4),
    );

    const texture = new THREE.TextureLoader().load("/img/lensflare0_alpha.png");
    this.material = new THREE.RawShaderMaterial({
      uniforms: {
        time: { value: 1 },
        sineTime: { value: 1 },
        alpha: { value: 0.3 },
        texture: { value: texture },
      },
      vertexShader: /* glsl */ `
        precision highp float;
        uniform float sineTime;
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        attribute vec3 position;
        attribute vec3 offset;
        attribute vec4 color;
        attribute vec4 orientationStart;
        attribute vec4 orientationEnd;
        uniform float time;
        varying vec3 vPosition;
        varying vec4 vColor;
        void main() {
          vPosition = offset * max(abs(sineTime * 2.0 + 1.0), 0.5) + position;
          vec4 orientation = normalize(mix(orientationStart, orientationEnd, sineTime));
          vec3 vcV = cross(orientation.xyz, vPosition);
          vPosition = vcV * (2.0 * orientation.w) + (cross(orientation.xyz, vcV) * 2.0 + vPosition);
          vColor = color;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(vPosition, 1.0);
          gl_PointSize = (orientation.w + 1.0) * 30.;
        }
      `,
      fragmentShader: /* glsl */ `
        precision highp float;
        uniform float time;
        uniform float alpha;
        uniform sampler2D texture;
        varying vec3 vPosition;
        varying vec4 vColor;
        void main() {
          vec4 color = vec4(vColor);
          color.r += sin(vPosition.x * 10.0 + time) * 0.5;
          gl_FragColor = color * texture2D(texture, gl_PointCoord);
          gl_FragColor.a = alpha;
        }
      `,
      depthTest: false,
      depthWrite: false,
      transparent: true,
      blending: THREE.AdditiveBlending,
    });

    geometry.computeBoundingSphere();
    this.points = new THREE.Points(geometry, this.material);
    this.points.renderOrder = 999;
    this.points.frustumCulled = false;
    this.points.scale.multiplyScalar(10);
    this.group.add(this.points);
  }

  sync(_time: number): void {
    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [{ id: "transform", label: "Transform", kind: ContainerKind.Folder }],
      controllers: [
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.points.geometry.dispose();
    this.material.dispose();
    (this.material.uniforms.texture.value as THREE.Texture | null)?.dispose();
  }
}

/** Spherical point field using the decompiled module 1390 shaders. */
export class SphericalFieldNode extends SceneNode {
  readonly kind = NodeKind.SphericalField;
  readonly typeLabel = "Spherical Field";
  override readonly is3D = true;

  color = "#00ffff";
  opacity = 0.5;
  size = 2.5;
  w = 2;
  h = 2;
  divX = 100;
  divY = 100;
  radius = 250;
  strength = 100;
  fractScale = 1.8;
  flowX = 1;
  flowY = 2;
  evolution = 1.5;
  displace = 30;
  audioAnalyzer = "analyzer_default";
  squishTo2D = true;
  premultiply = true;
  constantAudioFactor = 0;
  audioReaction = 1;
  audioAmt = 0;

  private positions: number[] = [];
  private points!: THREE.Points;
  private material!: THREE.ShaderMaterial;
  private texture: THREE.Texture | null = null;
  private positionsKey = "";

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
    new THREE.TextureLoader().load("/media/circle.webp", (texture) => {
      this.texture = texture;
      this.material.uniforms.circleTexture.value = texture;
    });
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -5);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.material = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        audioAmt: { value: 0 },
        fractScale: { value: this.fractScale },
        flow: { value: new THREE.Vector2(this.flowX, this.flowY) },
        evolution: { value: this.evolution },
        displace: { value: this.displace },
        radius: { value: this.radius },
        strength: { value: this.strength * 0.01 },
        pointSize: { value: this.size * (resolution.y / 900 / 1.2) },
        stageScale: { value: 2 / 1000 },
        baseColor: { value: new THREE.Color(this.color) },
        opacity: { value: this.opacity },
        circleTexture: { value: null },
        squish: { value: this.squishTo2D },
        premultiply: { value: this.premultiply },
      },
      vertexShader: SPHERICAL_VERTEX_SHADER,
      fragmentShader: SPHERICAL_FRAGMENT_SHADER,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      premultipliedAlpha: this.premultiply,
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute([], 3));
    this.points = new THREE.Points(geometry, this.material);
    // The shipped module does `this.mesh.position.z = -5` in its 1000-unit
    // world, and the item transform writes that same mesh position. Our group
    // already carries the item transform in reference units (`transform.z` is
    // authored as -5 on every Spherical Field row), so an extra -5 here would
    // double it: -5 stage units is -2500 reference units. Orthographic layers
    // only clip on z, which is why the offset has been invisible; a perspective
    // layer would put the field 500x too far away.
    this.points.position.z = 0;
    this.group.add(this.points);
  }

  private rebuildPositions(): void {
    const key = `${this.w}|${this.h}|${this.divX}|${this.divY}`;
    if (key === this.positionsKey) return;
    this.positionsKey = key;
    this.positions = [];
    const stepX = this.w / Math.max(1, this.divX);
    const stepY = this.h / Math.max(1, this.divY);
    for (let row = 0; row <= this.divX; row += 1) {
      for (let column = 0; column <= this.divY; column += 1) {
        this.positions.push(row * stepX - this.w / 2, column * stepY - this.h / 2, 0);
      }
    }
    const geometry = this.points.geometry as THREE.BufferGeometry;
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(this.positions, 3));
  }

  sync(time: number): void {
    this.rebuildPositions();
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    const data = this.ctx.spectrumFor?.(this.audioAnalyzer) ?? this.ctx.spectrum();
    const sample = data.slice(0, 100);
    let sum = 0;
    for (const value of sample) sum += value;
    this.audioAmt =
      sum / (6000 * Math.max(1, sample.length)) + this.constantAudioFactor / 100;

    const uniforms = this.material.uniforms;
    uniforms.time.value = time;
    uniforms.audioAmt.value = this.audioAmt;
    uniforms.fractScale.value = this.fractScale / 2;
    (uniforms.flow.value as THREE.Vector2).set(this.flowX, this.flowY);
    uniforms.evolution.value = this.evolution / 2;
    uniforms.displace.value = this.displace;
    uniforms.radius.value = this.radius;
    uniforms.strength.value = this.strength * 0.01;
    uniforms.pointSize.value = this.size * (resolution.y / 900 / 1.2);
    uniforms.stageScale.value = 2 / 1000;
    (uniforms.baseColor.value as THREE.Color).set(this.color);
    uniforms.opacity.value = this.opacity;
    uniforms.squish.value = this.squishTo2D;
    uniforms.premultiply.value = this.premultiply;
    this.material.premultipliedAlpha = this.premultiply;

    // Item transforms are authored in the reference's 1000-unit stage, like
    // every other 2D item; the orthographic layer camera is the 2-unit stage.
    const unit = 2 / 1000;
    this.group.position.set(
      this.readNumber("transform.x") * unit,
      this.readNumber("transform.y") * unit,
      this.readNumber("transform.z") * unit,
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.colorField("behaviour.color", "Color", {
          parentId: "behaviour",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("behaviour.opacity", "Opacity", {
          parentId: "behaviour",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.opacity,
          set: (v) => {
            this.opacity = v;
          },
        }),
        this.slider("behaviour.size", "Point size", {
          parentId: "behaviour",
          min: 0,
          max: 50,
          get: () => this.size,
          set: (v) => {
            this.size = v;
          },
        }),
        this.slider("behaviour.w", "Field width", {
          parentId: "behaviour",
          min: 0,
          max: 5000,
          get: () => this.w,
          set: (v) => {
            this.w = v;
          },
        }),
        this.slider("behaviour.h", "Field height", {
          parentId: "behaviour",
          min: 0,
          max: 5000,
          get: () => this.h,
          set: (v) => {
            this.h = v;
          },
        }),
        this.slider("behaviour.strength", "Field scale", {
          parentId: "behaviour",
          min: 0,
          max: 5000,
          get: () => this.strength,
          set: (v) => {
            this.strength = v;
          },
        }),
        this.slider("behaviour.divX", "Row count", {
          parentId: "behaviour",
          min: 1,
          max: 300,
          step: 1,
          get: () => this.divX,
          set: (v) => {
            this.divX = Math.round(v);
          },
        }),
        this.slider("behaviour.divY", "Column count", {
          parentId: "behaviour",
          min: 1,
          max: 300,
          step: 1,
          get: () => this.divY,
          set: (v) => {
            this.divY = Math.round(v);
          },
        }),
        this.slider("behaviour.radius", "Circle radius", {
          parentId: "behaviour",
          min: 0,
          max: 5000,
          get: () => this.radius,
          set: (v) => {
            this.radius = v;
          },
        }),
        this.slider("behaviour.fractScale", "Noise scale", {
          parentId: "behaviour",
          min: -20,
          max: 20,
          step: 0.01,
          get: () => this.fractScale,
          set: (v) => {
            this.fractScale = v;
          },
        }),
        this.slider("behaviour.flowX", "Horizontal movement", {
          parentId: "behaviour",
          min: -10,
          max: 10,
          step: 0.01,
          get: () => this.flowX,
          set: (v) => {
            this.flowX = v;
          },
        }),
        this.slider("behaviour.flowY", "Vertical movement", {
          parentId: "behaviour",
          min: -10,
          max: 10,
          step: 0.01,
          get: () => this.flowY,
          set: (v) => {
            this.flowY = v;
          },
        }),
        this.slider("behaviour.evolution", "Evolution amount", {
          parentId: "behaviour",
          min: 0,
          max: 20,
          step: 0.01,
          get: () => this.evolution,
          set: (v) => {
            this.evolution = v;
          },
        }),
        this.slider("behaviour.audioReaction", "Audio Reaction", {
          parentId: "behaviour",
          min: 0,
          max: 5,
          step: 0.1,
          get: () => this.audioReaction,
          set: (v) => {
            this.audioReaction = v;
          },
        }),
        this.slider("behaviour.constantAudioFactor", "Constant audio factor", {
          parentId: "behaviour",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.constantAudioFactor,
          set: (v) => {
            this.constantAudioFactor = v;
          },
        }),
        this.slider("behaviour.displace", "Displacement amount", {
          parentId: "behaviour",
          min: 0,
          max: 300,
          step: 0.1,
          get: () => this.displace,
          set: (v) => {
            this.displace = v;
          },
        }),
        this.text("behaviour.audioAnalyzer", "Audio analyzer", {
          parentId: "behaviour",
          get: () => this.audioAnalyzer,
          set: (v) => {
            this.audioAnalyzer = v;
          },
        }),
        this.toggle("behaviour.premultiply", "Premultiply points", {
          parentId: "behaviour",
          get: () => this.premultiply,
          set: (v) => {
            this.premultiply = v;
          },
        }),
        this.toggle("behaviour.squishTo2D", "Flatten", {
          parentId: "transform",
          get: () => this.squishTo2D,
          set: (v) => {
            this.squishTo2D = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.points.geometry.dispose();
    this.material.dispose();
    this.texture?.dispose();
  }
}

/** 3D spectrum "bed" of lines, ported from reference module 1365. */
export class LineBedNode extends SceneNode {
  readonly kind = NodeKind.LineBed;
  readonly typeLabel = "Line Bed";
  override readonly is3D = true;

  nrLines = 40;
  size = 40;
  lineLength = 10;
  spacing = 10;
  amplitude = 10;
  startColor = "#4f2eb2";
  endColor = "#ffffff";
  colorSplit = 0;
  audioAnalyzer = "analyzer_default";
  speed = 1;

  private lines: THREE.Line[] = [];
  private lastUpdateTime = 0;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.init();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", -140);
    this.objectMapping.set("transform.y", -30);
    this.objectMapping.set("transform.z", -250);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {}

  private colorFor(index: number): THREE.Color {
    const split = Math.max(this.colorSplit + 1 - index / Math.max(1, this.nrLines), 0);
    return new THREE.Color(this.endColor).lerp(new THREE.Color(this.startColor), split);
  }

  private init(): void {
    for (const line of this.lines) {
      this.group.remove(line);
      line.geometry.dispose();
      (line.material as THREE.Material).dispose();
    }
    this.lines = [];
    for (let lineIndex = 0; lineIndex < this.nrLines; lineIndex += 1) {
      const positions = new Float32Array(3 * this.size);
      for (let point = 0; point < this.size; point += 1) {
        positions[3 * point] = point * this.lineLength;
        positions[3 * point + 1] = 0;
        positions[3 * point + 2] =
          (-this.nrLines / 2) * this.spacing + lineIndex * this.spacing + 1;
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      const material = new THREE.MeshBasicMaterial({ color: this.colorFor(lineIndex) });
      const line = new THREE.Line(geometry, material);
      this.lines.push(line);
      this.group.add(line);
    }
  }

  sync(time: number): void {
    const data = this.ctx.spectrumFor?.(this.audioAnalyzer) ?? this.ctx.spectrum();
    const interval = 1 / 60 / Math.max(0.0001, this.speed);
    if (Math.abs(time - this.lastUpdateTime) >= interval && this.lines.length > 0) {
      this.lastUpdateTime = time;
      for (let index = this.lines.length - 1; index > 0; index -= 1) {
        const line = this.lines[index];
        const previous = this.lines[index - 1];
        const geometry = line.geometry.getAttribute("position") as THREE.BufferAttribute;
        const source = previous.geometry.getAttribute("position") as THREE.BufferAttribute;
        for (let offset = 0; offset < geometry.array.length; offset += 3) {
          (geometry.array as Float32Array)[offset + 1] = (source.array as Float32Array)[offset + 1];
        }
        (line.material as THREE.MeshBasicMaterial).color = this.colorFor(index);
        (line.material as THREE.Material).needsUpdate = true;
        geometry.needsUpdate = true;
      }
      const first = this.lines[0].geometry.getAttribute("position") as THREE.BufferAttribute;
      const values = data;
      for (let offset = 0; offset < Math.min(3 * values.length, first.array.length); offset += 3) {
        (first.array as Float32Array)[offset + 1] =
          (values[offset / 3] ?? 0) * (this.amplitude / 100);
      }
      first.needsUpdate = true;
    }

    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.colorField("appearance.startColor", "Start color", {
          parentId: "appearance",
          get: () => this.startColor,
          set: (v) => {
            this.startColor = v;
            this.init();
          },
        }),
        this.colorField("appearance.endColor", "End color", {
          parentId: "appearance",
          get: () => this.endColor,
          set: (v) => {
            this.endColor = v;
            this.init();
          },
        }),
        this.slider("appearance.colorSplit", "Color split", {
          parentId: "appearance",
          min: -1,
          max: 1,
          step: 0.01,
          get: () => this.colorSplit,
          set: (v) => {
            this.colorSplit = v;
            this.init();
          },
        }),
        this.slider("appearance.speed", "Speed", {
          parentId: "appearance",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.speed,
          set: (v) => {
            this.speed = v;
          },
        }),
        this.slider("appearance.amplitude", "Amplitude", {
          parentId: "appearance",
          min: 0,
          max: 100,
          step: 0.1,
          get: () => this.amplitude,
          set: (v) => {
            this.amplitude = v;
          },
        }),
        this.slider("appearance.nrLines", "Nr lines", {
          parentId: "appearance",
          min: 1,
          max: 100,
          step: 1,
          get: () => this.nrLines,
          set: (v) => {
            this.nrLines = Math.round(v);
            this.init();
          },
        }),
        this.slider("appearance.lineLength", "Line length", {
          parentId: "appearance",
          min: 1,
          max: 100,
          step: 0.1,
          get: () => this.lineLength,
          set: (v) => {
            this.lineLength = v;
            this.init();
          },
        }),
        this.slider("appearance.size", "Size", {
          parentId: "appearance",
          min: 1,
          max: 100,
          step: 1,
          get: () => this.size,
          set: (v) => {
            this.size = Math.round(v);
            this.init();
          },
        }),
        this.slider("appearance.spacing", "Spacing", {
          parentId: "appearance",
          min: 0,
          max: 100,
          step: 0.5,
          get: () => this.spacing,
          set: (v) => {
            this.spacing = v;
            this.init();
          },
        }),
        this.text("appearance.audioAnalyzer", "Audio analyzer", {
          parentId: "appearance",
          get: () => this.audioAnalyzer,
          set: (v) => {
            this.audioAnalyzer = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    for (const line of this.lines) {
      line.geometry.dispose();
      (line.material as THREE.Material).dispose();
    }
    this.lines = [];
  }
}

/** GLTF / OBJ model item, ported from reference module 1368. */
export class ModelNode extends SceneNode {
  readonly kind = NodeKind.Model;
  readonly typeLabel = "Model";
  override readonly is3D = true;

  color = "#ffffff";
  opacity = 1;
  modelSrc = "";

  private material = new THREE.MeshBasicMaterial({
    color: new THREE.Color("#ffffff"),
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 1,
  });
  private holder = new THREE.Group();
  private loadedSource = "";

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.group.add(this.holder);
    this.loadDefault();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -500);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {}

  private loadDefault(): void {
    new OBJLoader().load("/models/teapot.obj", (object) => {
      object.scale.set(50, 50, 50);
      this.applyModel(object);
      this.loadedSource = "teapot";
    });
  }

  private applyModel(object: THREE.Object3D): void {
    while (this.holder.children.length) this.holder.remove(this.holder.children[0]);
    object.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.material = this.material;
      }
    });
    this.holder.add(object);
  }

  async loadModel(): Promise<void> {
    if (!this.modelSrc || this.modelSrc === this.loadedSource) return;
    try {
      const response = await fetch(this.modelSrc);
      const buffer = await response.arrayBuffer();
      const isGlb = this.modelSrc.toLowerCase().includes(".glb");
      const data = isGlb ? buffer : new TextDecoder().decode(buffer);
      new GLTFLoader().parse(
        data,
        "",
        (gltf) => {
          this.applyModel(gltf.scene);
          this.loadedSource = this.modelSrc;
        },
        () => {
          this.loadedSource = this.modelSrc;
        },
      );
    } catch {
      this.loadedSource = this.modelSrc;
    }
  }

  sync(_time: number): void {
    void this.loadModel();
    this.material.color.set(this.color);
    this.material.opacity = this.opacity;
    this.material.visible = this.opacity > 0.001;
    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.fileField("appearance.modelSrc", "Model file (.glb, .gltf)", {
          parentId: "appearance",
          get: () => this.modelSrc,
          set: (v) => {
            this.modelSrc = v;
            void this.loadModel();
          },
        }),
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("appearance.opacity", "Opacity", {
          parentId: "appearance",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.opacity,
          set: (v) => {
            this.opacity = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.rotX", "Rotation X", {
          parentId: "transform",
          min: -360,
          max: 360,
          unit: "°",
          get: () => this.readNumber("transform.rotX"),
          set: (v) => this.objectMapping.set("transform.rotX", v),
        }),
        this.slider("transform.rotY", "Rotation Y", {
          parentId: "transform",
          min: -360,
          max: 360,
          unit: "°",
          get: () => this.readNumber("transform.rotY"),
          set: (v) => this.objectMapping.set("transform.rotY", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
      ],
    };
  }

  dispose(): void {
    this.material.dispose();
    this.holder.traverse((child) => {
      if (child instanceof THREE.Mesh) child.geometry.dispose();
    });
  }
}

/** Animated particle trails, ported from the reference Particle Lines generator. */
export class ParticleLinesNode extends SceneNode {
  readonly kind = NodeKind.ParticleLines;
  readonly typeLabel = "Particle Lines";
  override readonly is3D = true;

  frequency = 5;
  maxNrLines = 20;
  mirror = false;
  opacity = 1;
  color = "#ffffff";
  width = 3;
  scale = 15;
  nrPoints = 5;
  nrPrecisionPoints = 300;
  lengthRange: [number, number] = [8, 15];
  lengthMult = 1;
  visibleLengthRange: [number, number] = [0.05, 0.2];
  visibleLengthMult = 0.15;
  speedRange: [number, number] = [0.4, 0.8];
  speedMult = 1;
  /** Reference ParticleLines.update multiplier (`60 * dt * speedAmplitude`). */
  speedAmplitude = 0.73;
  originX: [number, number] = [0, 0];
  originY: [number, number] = [0, 0];
  originZ: [number, number] = [0, 0];
  directionX: [number, number] = [-0.1, 0.1];
  directionY: [number, number] = [-0.1, 0.1];
  directionZ: [number, number] = [0, 0.8];
  turbulenceAmt = 2;

  private state: ParticleLineState[] = [];
  private lastTime: number | null = null;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.group.position.z = -100;
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
    this.objectMapping.set("transform.z", -100);
    this.objectMapping.set("transform.rotX", 0);
    this.objectMapping.set("transform.rotY", 0);
    this.objectMapping.set("transform.rotZ", 0);
    this.objectMapping.set("transform.scaleX", 100);
    this.objectMapping.set("transform.scaleY", 100);
    this.objectMapping.set("transform.scaleZ", 100);
  }

  protected build(): void {}

  private random(min: number, max: number): number {
    return Math.random() * (max - min) + min;
  }

  private spawn(): void {
    const length = this.lengthRange[1] > this.lengthRange[0]
      ? this.random(this.lengthRange[0], this.lengthRange[1]) * this.lengthMult
      : 0;
    const visibleLength = this.visibleLengthRange[1] > this.visibleLengthRange[0]
      ? this.random(this.visibleLengthRange[0], this.visibleLengthRange[1]) * this.visibleLengthMult
      : 0;
    const origin = new THREE.Vector3(
      this.originX[1] > this.originX[0] ? this.random(this.originX[0], this.originX[1]) : 0,
      this.originY[1] > this.originY[0] ? this.random(this.originY[0], this.originY[1]) : 0,
      this.originZ[1] > this.originZ[0] ? this.random(this.originZ[0], this.originZ[1]) : 0,
    );
    const turbulence = new THREE.Vector3(
      this.random(-this.turbulenceAmt, this.turbulenceAmt),
      this.random(-this.turbulenceAmt, this.turbulenceAmt),
      this.random(-this.turbulenceAmt, this.turbulenceAmt),
    );
    const direction = new THREE.Vector3(
      this.random(this.directionX[0], this.directionX[1]),
      this.random(this.directionY[0], this.directionY[1]),
      this.random(this.directionZ[0], this.directionZ[1]),
    ).normalize().multiplyScalar(length / Math.max(1, this.nrPoints));
    const points: THREE.Vector3[] = [origin.clone()];
    for (let index = 0; index < this.nrPoints - 1; index += 1) {
      origin.add(direction);
      points.push(
        origin
          .clone()
          .add(
            new THREE.Vector3(
              this.random(-turbulence.x, turbulence.x),
              this.random(-turbulence.y, turbulence.y),
              this.random(-turbulence.z, turbulence.z),
            ),
          ),
      );
    }
    origin.add(direction);
    points.push(origin.clone());
    const curve = new THREE.CatmullRomCurve3(points).getPoints(this.nrPrecisionPoints);
    const flat: number[] = [];
    const reverse: number[] = [];
    for (const point of curve) {
      flat.push(point.x, point.y, point.z);
      reverse.push(-point.x, point.y, point.z);
    }
    const speed = this.speedRange[1] > this.speedRange[0]
      ? this.random(this.speedRange[0] / 100, this.speedRange[1] / 100) * this.speedMult
      : 0;
    this.addTrail(flat, reverse, speed, visibleLength);
    if (this.mirror) this.addTrail(reverse, flat, speed, visibleLength);
  }

  private addTrail(flat: number[], reverse: number[], speed: number, visibleLength: number): void {
    const geometry = new LineGeometry();
    geometry.setPositions(flat);
    const material = new LineMaterial({
      color: new THREE.Color(this.color),
      linewidth: this.width,
      resolution: new THREE.Vector2(1280, 720),
      dashed: false,
      transparent: true,
      side: THREE.DoubleSide,
      opacity: 1,
    });
    const line = new Line2(geometry, material);
    line.computeLineDistances();
    line.scale.setScalar(this.scale);
    this.group.add(line);
    this.state.push({ line, material, flat, reverse, speed, current: 0, visibleLength });
  }

  sync(time: number): void {
    const delta = this.lastTime === null ? 0 : Math.min(0.1, Math.max(0, time - this.lastTime));
    this.lastTime = time;
    const step = delta * 60 * this.speedAmplitude;

    if (this.state.length < this.maxNrLines && Math.random() < this.frequency / 100) {
      this.spawn();
    }

    const resolution = this.ctx.resolution?.() ?? { x: 1280, y: 720 };
    for (let index = this.state.length - 1; index >= 0; index -= 1) {
      const trail = this.state[index];
      trail.material.resolution.set(resolution.x, resolution.y);
      trail.material.linewidth = this.width;
      trail.material.color.set(this.color);
      trail.material.opacity = this.opacity;
      trail.material.visible = this.opacity > 0.001;
      const positions =
        trail.current + trail.speed * step < 0 ? trail.reverse : trail.flat;
      const total = positions.length;
      const start = Math.floor(Math.abs(trail.current) * total);
      const end = Math.floor((Math.abs(trail.current) + trail.visibleLength) * total);
      const from = start - (start % 3);
      const to = end - ((end - from) % 3);
      const slice = positions.slice(from, to);
      if (slice.length >= 6 && to < total) {
        (trail.line.geometry as LineGeometry).setPositions(slice);
        trail.line.computeLineDistances();
      }
      trail.current += trail.speed * step;
      if (trail.current >= 1 || trail.current <= -1) {
        this.group.remove(trail.line);
        trail.line.geometry.dispose();
        trail.material.dispose();
        this.state.splice(index, 1);
      }
    }

    this.group.position.set(
      this.readNumber("transform.x"),
      this.readNumber("transform.y"),
      this.readNumber("transform.z"),
    );
    this.group.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.group.scale.set(
      this.readNumber("transform.scaleX") / 100,
      this.readNumber("transform.scaleY") / 100,
      this.readNumber("transform.scaleZ") / 100,
    );
    this.group.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    const rangeSliders = (
      id: string,
      label: string,
      range: [number, number],
      min: number,
      max: number,
      step: number,
      parentId: string,
    ): PropertyDescriptor[] => [
      this.slider(`${id}.min`, `${label} min`, {
        parentId,
        min,
        max,
        step,
        get: () => range[0],
        set: (v) => {
          range[0] = v;
        },
      }),
      this.slider(`${id}.max`, `${label} max`, {
        parentId,
        min,
        max,
        step,
        get: () => range[1],
        set: (v) => {
          range[1] = v;
        },
      }),
    ];
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
      ],
      controllers: [
        this.colorField("appearance.color", "Color", {
          parentId: "appearance",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("appearance.opacity", "Alpha", {
          parentId: "appearance",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.opacity,
          set: (v) => {
            this.opacity = v;
          },
        }),
        this.slider("appearance.maxNrLines", "Max nr lines", {
          parentId: "appearance",
          min: 1,
          max: 300,
          step: 1,
          get: () => this.maxNrLines,
          set: (v) => {
            this.maxNrLines = Math.round(v);
          },
        }),
        this.toggle("appearance.mirror", "Mirror", {
          parentId: "appearance",
          get: () => this.mirror,
          set: (v) => {
            this.mirror = v;
          },
        }),
        this.slider("appearance.width", "Width", {
          parentId: "appearance",
          min: 0.1,
          max: 20,
          step: 0.1,
          get: () => this.width,
          set: (v) => {
            this.width = v;
          },
        }),
        this.slider("appearance.scale", "Scale", {
          parentId: "appearance",
          min: 0,
          max: 100,
          step: 0.1,
          get: () => this.scale,
          set: (v) => {
            this.scale = v;
          },
        }),
        this.slider("appearance.nrPoints", "Line points", {
          parentId: "appearance",
          min: 2,
          max: 30,
          step: 1,
          get: () => this.nrPoints,
          set: (v) => {
            this.nrPoints = Math.round(v);
          },
        }),
        this.slider("appearance.nrPrecisionPoints", "Rounding points", {
          parentId: "appearance",
          min: 1,
          max: 200,
          step: 1,
          get: () => this.nrPrecisionPoints,
          set: (v) => {
            this.nrPrecisionPoints = Math.round(v);
          },
        }),
        this.slider("behaviour.frequency", "Frequency", {
          parentId: "behaviour",
          min: 0,
          max: 100,
          step: 1,
          get: () => this.frequency,
          set: (v) => {
            this.frequency = v;
          },
        }),
        this.slider("behaviour.turbulenceAmt", "Turbulence", {
          parentId: "behaviour",
          min: -10,
          max: 10,
          step: 0.1,
          get: () => this.turbulenceAmt,
          set: (v) => {
            this.turbulenceAmt = v;
          },
        }),
        ...rangeSliders("appearance.length", "Path length", this.lengthRange, 0, 10, 0.1, "appearance"),
        ...rangeSliders(
          "appearance.visibleLength",
          "Visible length",
          this.visibleLengthRange,
          0,
          1,
          0.001,
          "appearance",
        ),
        ...rangeSliders("behaviour.speed", "Speed", this.speedRange, -2, 2, 0.01, "behaviour"),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -1000,
          max: 1000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
      ],
    };
  }

  dispose(): void {
    for (const trail of this.state) {
      trail.line.geometry.dispose();
      trail.material.dispose();
    }
    this.state = [];
  }
}

/** Lyrics/subtitles item using the decompiled canvas + shader pipeline. */
export class LyricsNode extends SceneNode {
  readonly kind = NodeKind.Lyrics;
  readonly typeLabel = "Lyrics";

  textValue = "";
  src = "";
  lyricsMapping: LyricLine[] = [];
  color = "#ffffff";
  alpha = 1;
  antiAliasing = true;
  textSize = 60;
  timeFormat = "mm:ss";
  timeDecimals = 2;
  drawTime = false;
  textAlign: "left" | "center" | "right" = "center";
  textAlignV: "top" | "middle" | "bottom" = "middle";
  textBaseline: CanvasTextBaseline = "bottom";
  textTiming = "word";
  offsetLine = 0;
  timeMultiplier = 1;
  font = "SourceSansPro";
  positionX = 0;
  positionY = 0;
  scaleX = 1;
  scaleY = 1;
  scaleMultiplier = 1;
  showBoundingBox = false;
  textWidth = 850;
  textHeight = 500;
  fontStyle = "normal";
  fontWeight = 400;
  rotation = 0;
  textJustify = false;
  dropShadow = {
    enableShadow: false,
    shadowColor: "#000000",
    shadowOffsetX: 4,
    shadowOffsetY: 4,
    shadowBlur: 1,
  };
  outlineDropShadow = {
    enableOutline: false,
    outlineColor: "#000000",
    outlineOffsetX: 0,
    outlineOffsetY: 0,
    outlineExtent: 1,
    outlineBlur: 0,
    outlineHighPrecision: false,
  };

  alphaEnabled = false;
  alphaInDuration = 0.1;
  alphaInRange: [number, number] = [0, 1];
  alphaInEasing = "linear";
  alphaOutDuration = 0.1;
  alphaOutRange: [number, number] = [1, 0];
  alphaOutEasing = "linear";

  scaleEnabled = false;
  scaleInDuration = 0.2;
  scaleInRange: [number, number] = [0.8, 1];
  scaleInEasing = "easeOutExpo";
  scaleOutDuration = 0.2;
  scaleOutRange: [number, number] = [1, 0.8];
  scaleOutEasing = "easeOutExpo";

  posXEnabled = false;
  posXInDuration = 0.2;
  posXInRange: [number, number] = [-50, 0];
  posXInEasing = "easeOutExpo";
  posXOutDuration = 0.2;
  posXOutRange: [number, number] = [0, 50];
  posXOutEasing = "easeOutExpo";

  posYEnabled = false;
  posYInDuration = 0.2;
  posYInRange: [number, number] = [-50, 0];
  posYInEasing = "easeOutExpo";
  posYOutDuration = 0.2;
  posYOutRange: [number, number] = [0, 50];
  posYOutEasing = "easeOutExpo";

  blurEnabled = false;
  blurInDuration = 0.1;
  blurInRange: [number, number] = [10, 0];
  blurInEasing = "linear";
  blurOutDuration = 0.1;
  blurOutRange: [number, number] = [0, 10];
  blurOutEasing = "linear";

  liquidEnabled = false;
  liquidInDuration = 0.2;
  liquidInEasing = "easeOutExpo";
  liquidOutDuration = 0.2;
  liquidOutEasing = "easeOutExpo";
  liquidMultiplier = 1;
  liquidNoiseScale = 1;
  liquidSoftNoise = false;

  distortionEnabled = false;
  distortionInDuration = 0.2;
  distortionInEasing = "easeOutExpo";
  distortionOutDuration = 0.2;
  distortionOutEasing = "easeOutExpo";
  distortionMultiplier = 1;
  distortionNoiseScale = 1;
  distortionHardNoise = false;

  shakeEnabled = false;
  shakeInDuration = 0.2;
  shakeInEasing = "easeOutExpo";
  shakeOutDuration = 0.2;
  shakeOutEasing = "easeOutExpo";
  shakeMultiplier = 10;
  shakeFrequency = 15;
  shakeAmplitude = 25;

  useMotionBlur = true;
  motionBlurIterations = 20;
  motionBlurLength = 10;
  motionExaggeration = 0.5;

  private canvas!: HTMLCanvasElement;
  private context!: CanvasRenderingContext2D;
  private texture!: THREE.CanvasTexture;
  private material!: THREE.ShaderMaterial;
  private mesh!: THREE.Mesh;
  private fontName = "SourceSansPro";
  private elapsed = 0;
  private animationAlpha = 1;
  private animationScale = 1;
  private animationPosX = 0;
  private animationPosY = 0;
  private animationBlur = 0;
  private animationLiquid = 0;
  private animationDistortion = 0;
  private animationShake = 0;
  private prevMotion = { x: 0, y: 0, scaleX: 1, scaleY: 1 };
  private appliedBlurLength = 10;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
    void this.loadFont();
  }

  protected initializeObjectMapping(): void {
    this.objectMapping.set("transform.z", -5);
    this.objectMapping.set("transform.x", 0);
    this.objectMapping.set("transform.y", 0);
  }

  protected build(): void {
    const resolution = this.ctx.resolution?.() ?? { x: 1920, y: 1080 };
    this.canvas = document.createElement("canvas");
    this.canvas.width = Math.max(1, Math.round(resolution.x));
    this.canvas.height = Math.max(1, Math.round(resolution.y));
    this.context = this.canvas.getContext("2d")!;
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.colorSpace = THREE.NoColorSpace;
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;

    this.material = new THREE.ShaderMaterial({
      uniforms: {
        tDiffuse: { value: this.texture },
        motion: { value: new THREE.Vector2(0, 0) },
        motionBlurIterations: { value: this.motionBlurIterations },
        motionBlurLength: { value: this.motionBlurLength },
        useMotionBlur: { value: this.useMotionBlur },
        scaleMotion: { value: 0 },
        liquidMotion: { value: 0 },
        distortionMotion: { value: 0 },
        shakeMotion: { value: 0 },
        shakeFrequency: { value: this.shakeFrequency },
        shakeAmplitude: { value: this.shakeAmplitude },
        time: { value: 0 },
        distortionHardNoise: { value: this.distortionHardNoise },
        liquidSoftNoise: { value: this.liquidSoftNoise },
        distortionNoiseScale: { value: this.distortionNoiseScale },
        liquidNoiseScale: { value: this.liquidNoiseScale },
      },
      vertexShader: LYRICS_VERTEX_SHADER,
      fragmentShader: LYRICS_FRAGMENT_SHADER,
      premultipliedAlpha: true,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    const aspect = resolution.x / resolution.y;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2 * aspect, 2), this.material);
    this.mesh.position.z = this.readNumber("transform.z") * REFERENCE_SCALE;
    this.mesh.renderOrder = 10;
    this.group.add(this.mesh);
  }

  async loadFont(): Promise<void> {
    this.fontName = await loadSkiaFont(this.font);
    this.draw(this.elapsed);
  }

  async loadLyrics(): Promise<void> {
    if (!this.src) return;
    try {
      const text = this.src.trim().startsWith("{") || this.src.trim().startsWith("[")
        ? this.src
        : await (await fetch(this.src)).text();
      this.lyricsMapping = parseLyrics(text);
    } catch {
      this.lyricsMapping = [];
    }
  }

  setLyricsText(text: string): void {
    try {
      this.lyricsMapping = parseLyrics(text);
    } catch {
      this.lyricsMapping = [];
    }
  }

  private getLine(time: number): LyricLine | null {
    const length = this.lyricsMapping.length;
    for (let index = 0; index < length; index += 1) {
      const line = this.lyricsMapping[index];
      if (line.start <= time && line.end >= time) {
        const shifted = index + this.offsetLine;
        return {
          start: line.start,
          end: line.end,
          text: shifted >= 0 && shifted < length ? this.lyricsMapping[shifted].text : "",
        };
      }
    }
    return null;
  }

  private formatClock(seconds: number): string {
    const minutes = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
    const whole = String(seconds % 60).split(".")[0].padStart(2, "0");
    let result = `${minutes}:${whole}`;
    if (this.timeDecimals <= 0) return result;
    const fraction = String(seconds).split(".")[1] ?? "";
    result += ".";
    result += fraction.substring(0, this.timeDecimals);
    while (result.length < 6 + this.timeDecimals) result += "0";
    return result;
  }

  private entrance(
    local: number,
    line: LyricLine,
    enabled: boolean,
    inDuration: number,
    inEasing: string,
    inRange: [number, number],
    outDuration: number,
    outEasing: string,
    outRange: [number, number],
    fallback: number,
  ): number {
    let value = fallback;
    if (!enabled) return value;
    if (local - line.start <= inDuration) {
      const t = ease(inEasing, (local - line.start) / Math.max(0.0001, inDuration));
      value = inRange[0] + (inRange[1] - inRange[0]) * t;
    }
    if (line.end - local <= outDuration) {
      const t = ease(outEasing, (line.end - local) / Math.max(0.0001, outDuration));
      value = outRange[1] + (outRange[0] - outRange[1]) * t;
    }
    return value;
  }

  private effectEnvelope(
    local: number,
    line: LyricLine,
    enabled: boolean,
    inDuration: number,
    inEasing: string,
    outDuration: number,
    outEasing: string,
    multiplier: number,
  ): number {
    if (!enabled) return 0;
    if (local - line.start <= inDuration) {
      const t = ease(inEasing, (local - line.start) / Math.max(0.0001, inDuration));
      return (1 + (0 - 1) * t) * multiplier;
    }
    if (line.end - local <= outDuration) {
      const t = ease(outEasing, (line.end - local) / Math.max(0.0001, outDuration));
      return (1 + (0 - 1) * t) * multiplier;
    }
    return 0;
  }

  private draw(time: number): void {
    const ctx = this.context;
    if (!ctx) return;
    const resolution = this.ctx.resolution?.() ?? { x: this.canvas.width, y: this.canvas.height };
    const pixelWidth = Math.max(1, Math.round(resolution.x));
    const pixelHeight = Math.max(1, Math.round(resolution.y));
    if (this.canvas.width !== pixelWidth || this.canvas.height !== pixelHeight) {
      // Same immutable `texStorage2D` rule as the canvas-backed items: a canvas
      // resized after the texture's first upload keeps the old allocation, so
      // every later paint uploads into storage the driver rejects and the
      // composite keeps showing the first frame (a countdown frozen at 00:36).
      this.texture.dispose();
      this.canvas.width = pixelWidth;
      this.canvas.height = pixelHeight;
    }

    let text = this.textValue;
    const scaledTime = time * this.timeMultiplier;
    const line = this.getLine(scaledTime);
    if (line) {
      this.animationAlpha = 1;
      this.animationScale = this.entrance(
        scaledTime,
        line,
        this.scaleEnabled,
        this.scaleInDuration,
        this.scaleInEasing,
        this.scaleInRange,
        this.scaleOutDuration,
        this.scaleOutEasing,
        this.scaleOutRange,
        1,
      );
      if (this.alphaEnabled) {
        this.animationAlpha = this.entrance(
          scaledTime,
          line,
          true,
          this.alphaInDuration,
          this.alphaInEasing,
          this.alphaInRange,
          this.alphaOutDuration,
          this.alphaOutEasing,
          this.alphaOutRange,
          1,
        );
      }
      this.animationPosX = this.entrance(
        scaledTime,
        line,
        this.posXEnabled,
        this.posXInDuration,
        this.posXInEasing,
        this.posXInRange,
        this.posXOutDuration,
        this.posXOutEasing,
        this.posXOutRange,
        0,
      );
      this.animationPosY = this.entrance(
        scaledTime,
        line,
        this.posYEnabled,
        this.posYInDuration,
        this.posYInEasing,
        this.posYInRange,
        this.posYOutDuration,
        this.posYOutEasing,
        this.posYOutRange,
        0,
      );
      this.animationBlur = this.entrance(
        scaledTime,
        line,
        this.blurEnabled,
        this.blurInDuration,
        this.blurInEasing,
        this.blurInRange,
        this.blurOutDuration,
        this.blurOutEasing,
        this.blurOutRange,
        0,
      );
      this.animationLiquid = this.effectEnvelope(
        scaledTime,
        line,
        this.liquidEnabled,
        this.liquidInDuration,
        this.liquidInEasing,
        this.liquidOutDuration,
        this.liquidOutEasing,
        this.liquidMultiplier,
      );
      this.animationDistortion = this.effectEnvelope(
        scaledTime,
        line,
        this.distortionEnabled,
        this.distortionInDuration,
        this.distortionInEasing,
        this.distortionOutDuration,
        this.distortionOutEasing,
        this.distortionMultiplier,
      );
      this.animationShake = this.effectEnvelope(
        scaledTime,
        line,
        this.shakeEnabled,
        this.shakeInDuration,
        this.shakeInEasing,
        this.shakeOutDuration,
        this.shakeOutEasing,
        this.shakeMultiplier,
      );
      text = line.text.replace(/\\n/g, "\n");
    }
    if (this.drawTime) {
      text = this.timeFormat === "s" ? time.toFixed(this.timeDecimals) : this.formatClock(time);
    }

    ctx.save();
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.font = `${this.textSize / 2}pt ${this.fontName}`;
    ctx.fillStyle = this.color;
    ctx.textAlign = this.textAlign;
    ctx.textBaseline = this.textBaseline;

    const scaleFactor =
      Math.sqrt(this.canvas.width * this.canvas.width + this.canvas.height * this.canvas.height) /
      1000;
    const filters: string[] = [];
    if (this.animationBlur) filters.push(`blur(${this.animationBlur * scaleFactor}px)`);
    const outline = this.outlineDropShadow;
    if (outline.enableOutline) {
      const extent = outline.outlineExtent * scaleFactor * (outline.outlineHighPrecision ? 0.5 : 1);
      const blur = outline.outlineBlur * scaleFactor;
      const offsetX = outline.outlineOffsetX * scaleFactor;
      const offsetY = outline.outlineOffsetY * scaleFactor;
      const color = outline.outlineColor;
      filters.push(
        `drop-shadow(${offsetX + extent}px ${offsetY - extent}px ${blur}px ${color})`,
        `drop-shadow(${offsetX + extent}px ${offsetY + extent}px ${blur}px ${color})`,
        `drop-shadow(${offsetX - extent}px ${offsetY + extent}px ${blur}px ${color})`,
        `drop-shadow(${offsetX - extent}px ${offsetY - extent}px ${blur}px ${color})`,
      );
      if (outline.outlineHighPrecision) {
        filters.push(
          `drop-shadow(${offsetX}px ${offsetY - extent}px ${blur}px ${color})`,
          `drop-shadow(${offsetX + extent}px ${offsetY}px ${blur}px ${color})`,
          `drop-shadow(${offsetX}px ${offsetY + extent}px ${blur}px ${color})`,
          `drop-shadow(${offsetX - extent}px ${offsetY}px ${blur}px ${color})`,
        );
      }
    }
    const shadow = this.dropShadow;
    if (shadow.enableShadow) {
      filters.push(
        `drop-shadow(${shadow.shadowOffsetX * scaleFactor}px ${shadow.shadowOffsetY * scaleFactor}px ${shadow.shadowBlur * scaleFactor}px ${shadow.shadowColor})`,
      );
    }
    const opacity = Math.max(0, Math.min(1, this.alpha * this.animationAlpha));
    if (opacity < 1) filters.push(`opacity(${opacity})`);
    ctx.filter = filters.length ? filters.join(" ") : "none";
    ctx.globalAlpha = 1;

    const scaleX = this.canvas.width / 1000;
    const scaleY = this.canvas.height / 1000;
    ctx.scale(scaleX, scaleY);
    ctx.translate(500 + this.positionX + this.animationPosX, 500 + this.positionY + this.animationPosY);
    ctx.scale(1, scaleX / scaleY);
    ctx.scale(
      this.scaleX * this.scaleMultiplier * this.animationScale,
      this.scaleY * this.scaleMultiplier * this.animationScale,
    );
    ctx.rotate((this.rotation * Math.PI) / 180);
    drawText(ctx, text, {
      x: -this.textWidth / 2,
      y: -this.textHeight / 2,
      width: this.textWidth <= 0 ? 1 : this.textWidth,
      height: this.textHeight <= 0 ? 1 : this.textHeight,
      debug: this.showBoundingBox,
      align: this.textAlign,
      vAlign: this.textAlignV,
      fontSize: this.textSize,
      font: this.fontName,
      fontStyle: this.fontStyle,
      fontWeight: this.fontWeight.toString(),
      justify: this.textJustify,
    });
    ctx.restore();
    this.texture.needsUpdate = true;
  }

  sync(time: number): void {
    this.elapsed = time;
    const resolution = this.ctx.resolution?.() ?? { x: this.canvas.width, y: this.canvas.height };
    const aspect = resolution.x / Math.max(1, resolution.y);
    const geometry = this.mesh.geometry as THREE.PlaneGeometry;
    if (Math.abs(geometry.parameters.width - 2 * aspect) > 0.001) {
      geometry.dispose();
      this.mesh.geometry = new THREE.PlaneGeometry(2 * aspect, 2);
    }
    this.mesh.position.set(0, 0, this.readNumber("transform.z") * REFERENCE_SCALE);
    this.mesh.visible = this.visible;

    const local = time - this.start;
    const uniforms = this.material.uniforms;
    uniforms.time.value = local;
    const motionX =
      (this.prevMotion.x - (500 + this.positionX + this.animationPosX)) * this.motionExaggeration;
    const motionY =
      (this.prevMotion.y - (500 + this.positionY + this.animationPosY)) * this.motionExaggeration;
    const scaleDelta =
      (this.prevMotion.scaleX - this.scaleX * this.scaleMultiplier * this.animationScale) *
      this.motionExaggeration;
    uniforms.motion.value = new THREE.Vector2(motionX / 500, -motionY / 500);
    uniforms.scaleMotion.value = scaleDelta;
    uniforms.liquidMotion.value = this.animationLiquid;
    uniforms.distortionMotion.value = this.animationDistortion;
    uniforms.shakeMotion.value = this.animationShake;
    uniforms.shakeFrequency.value = this.shakeFrequency;
    uniforms.shakeAmplitude.value = this.shakeAmplitude;
    uniforms.liquidSoftNoise.value = this.liquidSoftNoise;
    uniforms.distortionHardNoise.value = this.distortionHardNoise;
    uniforms.liquidNoiseScale.value = this.liquidNoiseScale;
    uniforms.distortionNoiseScale.value = this.distortionNoiseScale;
    uniforms.useMotionBlur.value = this.useMotionBlur;
    uniforms.motionBlurIterations.value = this.motionBlurIterations;
    if (this.motionBlurLength !== this.appliedBlurLength) {
      uniforms.motionBlurLength.value = 100 - this.motionBlurLength + 0.01;
      this.appliedBlurLength = this.motionBlurLength;
    }
    this.prevMotion = {
      x: 500 + this.positionX + this.animationPosX,
      y: 500 + this.positionY + this.animationPosY,
      scaleX: this.scaleX * this.scaleMultiplier * this.animationScale,
      scaleY: this.scaleY * this.scaleMultiplier * this.animationScale,
    };
    this.draw(local);
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "text", label: "Text", kind: ContainerKind.Folder },
        { id: "animation", label: "Animation", kind: ContainerKind.Folder },
        { id: "shadow", label: "Drop shadow", kind: ContainerKind.Folder },
        { id: "position", label: "Positioning & Size", kind: ContainerKind.Folder },
        { id: "position2d", label: "Texture Position", kind: ContainerKind.Folder, parentId: "position" },
        { id: "scale2d", label: "Texture Scale", kind: ContainerKind.Folder, parentId: "position" },
      ],
      controllers: [
        this.fileField("text.src", "Lyrics file", {
          parentId: "text",
          get: () => this.src,
          set: (v) => {
            this.src = v;
            void this.loadLyrics();
          },
        }),
        this.choose("text.font", "Font", {
          parentId: "text",
          values: SKIA_FONT_TITLES,
          get: () => this.font,
          set: (v) => {
            this.font = v;
            void this.loadFont();
          },
        }),
        this.toggle("text.antiAliasing", "Antialiasing", {
          parentId: "text",
          get: () => this.antiAliasing,
          set: (v) => {
            this.antiAliasing = v;
          },
        }),
        this.colorField("text.color", "Text color", {
          parentId: "text",
          get: () => this.color,
          set: (v) => {
            this.color = v;
          },
        }),
        this.slider("text.alpha", "Text alpha", {
          parentId: "text",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.alpha,
          set: (v) => {
            this.alpha = v;
          },
        }),
        this.slider("text.fontWeight", "Font weight", {
          parentId: "text",
          min: 100,
          max: 1000,
          step: 1,
          get: () => this.fontWeight,
          set: (v) => {
            this.fontWeight = v;
          },
        }),
        this.choose("text.fontStyle", "Font style", {
          parentId: "text",
          values: ["normal", "italic", "oblique"],
          get: () => this.fontStyle,
          set: (v) => {
            this.fontStyle = v;
          },
        }),
        this.slider("text.textSize", "Text size", {
          parentId: "text",
          min: 1,
          max: 200,
          get: () => this.textSize,
          set: (v) => {
            this.textSize = v;
          },
        }),
        this.choose("text.textAlign", "Text horizontal align", {
          parentId: "text",
          values: ["left", "center", "right"],
          get: () => this.textAlign,
          set: (v) => {
            this.textAlign = v as typeof this.textAlign;
          },
        }),
        this.choose("text.textAlignV", "Text vertical align", {
          parentId: "text",
          values: ["top", "middle", "bottom"],
          get: () => this.textAlignV,
          set: (v) => {
            this.textAlignV = v as typeof this.textAlignV;
          },
        }),
        this.choose("text.textBaseline", "Text baseline", {
          parentId: "text",
          values: ["top", "hanging", "middle", "alphabetic", "ideographic", "bottom"],
          get: () => this.textBaseline,
          set: (v) => {
            this.textBaseline = v as CanvasTextBaseline;
          },
        }),
        this.toggle("text.textJustify", "Text justify", {
          parentId: "text",
          get: () => this.textJustify,
          set: (v) => {
            this.textJustify = v;
          },
        }),
        this.slider("animation.offsetLine", "Offset line", {
          parentId: "animation",
          min: -10,
          max: 10,
          step: 1,
          get: () => this.offsetLine,
          set: (v) => {
            this.offsetLine = v;
          },
        }),
        this.slider("animation.timeMultiplier", "Speed multiplier", {
          parentId: "animation",
          min: 0.1,
          max: 5,
          step: 0.01,
          get: () => this.timeMultiplier,
          set: (v) => {
            this.timeMultiplier = v;
          },
        }),
        this.toggle("animation.alphaEnabled", "Alpha animation", {
          parentId: "animation",
          get: () => this.alphaEnabled,
          set: (v) => {
            this.alphaEnabled = v;
          },
        }),
        this.slider("animation.alphaInDuration", "Alpha in duration", {
          parentId: "animation",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.alphaInDuration,
          set: (v) => {
            this.alphaInDuration = v;
          },
        }),
        this.choose("animation.alphaInEasing", "Alpha in easing", {
          parentId: "animation",
          values: EASING_OPTIONS,
          get: () => this.alphaInEasing,
          set: (v) => {
            this.alphaInEasing = v;
          },
        }),
        this.slider("animation.alphaOutDuration", "Alpha out duration", {
          parentId: "animation",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.alphaOutDuration,
          set: (v) => {
            this.alphaOutDuration = v;
          },
        }),
        this.choose("animation.alphaOutEasing", "Alpha out easing", {
          parentId: "animation",
          values: EASING_OPTIONS,
          get: () => this.alphaOutEasing,
          set: (v) => {
            this.alphaOutEasing = v;
          },
        }),
        this.toggle("animation.scaleEnabled", "Scale animation", {
          parentId: "animation",
          get: () => this.scaleEnabled,
          set: (v) => {
            this.scaleEnabled = v;
          },
        }),
        this.slider("animation.scaleInDuration", "Scale in duration", {
          parentId: "animation",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.scaleInDuration,
          set: (v) => {
            this.scaleInDuration = v;
          },
        }),
        this.slider("animation.scaleOutDuration", "Scale out duration", {
          parentId: "animation",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.scaleOutDuration,
          set: (v) => {
            this.scaleOutDuration = v;
          },
        }),
        this.toggle("animation.posXEnabled", "Position X animation", {
          parentId: "animation",
          get: () => this.posXEnabled,
          set: (v) => {
            this.posXEnabled = v;
          },
        }),
        this.toggle("animation.posYEnabled", "Position Y animation", {
          parentId: "animation",
          get: () => this.posYEnabled,
          set: (v) => {
            this.posYEnabled = v;
          },
        }),
        this.toggle("animation.blurEnabled", "Blur animation", {
          parentId: "animation",
          get: () => this.blurEnabled,
          set: (v) => {
            this.blurEnabled = v;
          },
        }),
        this.toggle("animation.liquidEnabled", "Liquid animation", {
          parentId: "animation",
          get: () => this.liquidEnabled,
          set: (v) => {
            this.liquidEnabled = v;
          },
        }),
        this.slider("animation.liquidMultiplier", "Liquid multiplier", {
          parentId: "animation",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.liquidMultiplier,
          set: (v) => {
            this.liquidMultiplier = v;
          },
        }),
        this.slider("animation.liquidNoiseScale", "Liquid noise scale", {
          parentId: "animation",
          min: 0.1,
          max: 10,
          step: 0.01,
          get: () => this.liquidNoiseScale,
          set: (v) => {
            this.liquidNoiseScale = v;
          },
        }),
        this.toggle("animation.liquidSoftNoise", "Liquid soft noise", {
          parentId: "animation",
          get: () => this.liquidSoftNoise,
          set: (v) => {
            this.liquidSoftNoise = v;
          },
        }),
        this.toggle("animation.distortionEnabled", "Distortion animation", {
          parentId: "animation",
          get: () => this.distortionEnabled,
          set: (v) => {
            this.distortionEnabled = v;
          },
        }),
        this.slider("animation.distortionMultiplier", "Distortion multiplier", {
          parentId: "animation",
          min: 0,
          max: 5,
          step: 0.01,
          get: () => this.distortionMultiplier,
          set: (v) => {
            this.distortionMultiplier = v;
          },
        }),
        this.slider("animation.distortionNoiseScale", "Distortion noise scale", {
          parentId: "animation",
          min: 0.1,
          max: 10,
          step: 0.01,
          get: () => this.distortionNoiseScale,
          set: (v) => {
            this.distortionNoiseScale = v;
          },
        }),
        this.toggle("animation.distortionHardNoise", "Distortion hard noise", {
          parentId: "animation",
          get: () => this.distortionHardNoise,
          set: (v) => {
            this.distortionHardNoise = v;
          },
        }),
        this.toggle("animation.shakeEnabled", "Shake animation", {
          parentId: "animation",
          get: () => this.shakeEnabled,
          set: (v) => {
            this.shakeEnabled = v;
          },
        }),
        this.slider("animation.shakeMultiplier", "Shake multiplier", {
          parentId: "animation",
          min: 0,
          max: 50,
          step: 0.1,
          get: () => this.shakeMultiplier,
          set: (v) => {
            this.shakeMultiplier = v;
          },
        }),
        this.slider("animation.shakeFrequency", "Shake frequency", {
          parentId: "animation",
          min: 0,
          max: 100,
          step: 0.01,
          get: () => this.shakeFrequency,
          set: (v) => {
            this.shakeFrequency = v;
          },
        }),
        this.slider("animation.shakeAmplitude", "Shake amplitude", {
          parentId: "animation",
          min: 0,
          max: 100,
          step: 0.01,
          get: () => this.shakeAmplitude,
          set: (v) => {
            this.shakeAmplitude = v;
          },
        }),
        this.toggle("shadow.enableShadow", "Enable shadow", {
          parentId: "shadow",
          get: () => this.dropShadow.enableShadow,
          set: (v) => {
            this.dropShadow.enableShadow = v;
          },
        }),
        this.colorField("shadow.shadowColor", "Shadow color", {
          parentId: "shadow",
          get: () => this.dropShadow.shadowColor,
          set: (v) => {
            this.dropShadow.shadowColor = v;
          },
        }),
        this.toggle("shadow.enableOutline", "Enable outline", {
          parentId: "shadow",
          get: () => this.outlineDropShadow.enableOutline,
          set: (v) => {
            this.outlineDropShadow.enableOutline = v;
          },
        }),
        this.colorField("shadow.outlineColor", "Outline color", {
          parentId: "shadow",
          get: () => this.outlineDropShadow.outlineColor,
          set: (v) => {
            this.outlineDropShadow.outlineColor = v;
          },
        }),
        this.slider("text.positionX", "x", {
          parentId: "position2d",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.positionX,
          set: (v) => {
            this.positionX = v;
          },
        }),
        this.slider("text.positionY", "y", {
          parentId: "position2d",
          min: -500,
          max: 500,
          step: 1,
          get: () => this.positionY,
          set: (v) => {
            this.positionY = v;
          },
        }),
        this.slider("text.scaleX", "x", {
          parentId: "scale2d",
          min: -10,
          max: 10,
          step: 0.05,
          get: () => this.scaleX,
          set: (v) => {
            this.scaleX = v;
          },
        }),
        this.slider("text.scaleY", "y", {
          parentId: "scale2d",
          min: -10,
          max: 10,
          step: 0.05,
          get: () => this.scaleY,
          set: (v) => {
            this.scaleY = v;
          },
        }),
        this.slider("text.rotation", "Rotation", {
          parentId: "position",
          min: -360,
          max: 360,
          step: 1,
          unit: "°",
          get: () => this.rotation,
          set: (v) => {
            this.rotation = v;
          },
        }),
        this.slider("text.scaleMultiplier", "Scale multiplier", {
          parentId: "position",
          min: -5,
          max: 5,
          step: 0.01,
          get: () => this.scaleMultiplier,
          set: (v) => {
            this.scaleMultiplier = v;
          },
        }),
        this.slider("text.textWidth", "Text box width", {
          parentId: "position",
          min: 0,
          max: 4000,
          step: 1,
          get: () => this.textWidth,
          set: (v) => {
            this.textWidth = v;
          },
        }),
        this.slider("text.textHeight", "Text box height", {
          parentId: "position",
          min: 0,
          max: 4000,
          step: 1,
          get: () => this.textHeight,
          set: (v) => {
            this.textHeight = v;
          },
        }),
        this.toggle("text.showBoundingBox", "Show bounding box", {
          parentId: "position",
          get: () => this.showBoundingBox,
          set: (v) => {
            this.showBoundingBox = v;
          },
        }),
        this.toggle("animation.useMotionBlur", "Motion blur", {
          parentId: "position",
          get: () => this.useMotionBlur,
          set: (v) => {
            this.useMotionBlur = v;
          },
        }),
        this.slider("animation.motionBlurIterations", "Motion blur iterations", {
          parentId: "position",
          min: 1,
          max: 100,
          step: 1,
          get: () => this.motionBlurIterations,
          set: (v) => {
            this.motionBlurIterations = v;
          },
        }),
        this.slider("animation.motionBlurLength", "Motion blur length", {
          parentId: "position",
          min: 1,
          max: 100,
          step: 1,
          get: () => this.motionBlurLength,
          set: (v) => {
            this.motionBlurLength = v;
          },
        }),
        this.slider("animation.motionExaggeration", "Motion exaggeration", {
          parentId: "position",
          min: -10,
          max: 10,
          step: 0.01,
          get: () => this.motionExaggeration,
          set: (v) => {
            this.motionExaggeration = v;
          },
        }),
      ],
    };
  }

  dispose(): void {
    this.texture.dispose();
    this.material.dispose();
    (this.mesh.geometry as THREE.BufferGeometry).dispose();
    this.canvas.width = 1;
    this.canvas.height = 1;
  }
}

/** Noise algorithms exposed by the reference Noise item. */
export const NOISE_TYPES = [
  "simplex2D",
  "simplex3D",
  "simplex4D",
  "classic2D",
  "classic3D",
  "classic4D",
  "cellular2D",
  "cellular3D",
  "psrdSimplex2D",
] as const;

export type NoiseType = (typeof NOISE_TYPES)[number];

function noiseShaderSetup(type: string): { source: string; call: string } {
  const evolution = "animate ? uTime * animateSpeed : evolution";
  switch (type) {
    case "classic2D":
      return {
        source: NOISE_SOURCES.classic2D,
        call: `cnoise(uvInput + vec2(${evolution}))`,
      };
    case "cellular2D":
      return {
        source: NOISE_SOURCES.cellular2D,
        call: `cellular(uvInput + vec2(${evolution})).x`,
      };
    case "psrdSimplex2D":
      return {
        source: NOISE_SOURCES.psrdSimplex2D,
        call: `psrnoise(uvInput + vec2(${evolution}), psrdPeriod, psrdRotation)`,
      };
    case "simplex3D":
      return {
        source: NOISE_SOURCES.simplex3D,
        call: `snoise(vec3(uvInput, ${evolution}))`,
      };
    case "classic3D":
      return {
        source: NOISE_SOURCES.classic3D,
        call: `cnoise(vec3(uvInput, ${evolution}))`,
      };
    case "cellular3D":
      return {
        source: NOISE_SOURCES.cellular3D,
        call: `cellular(vec3(uvInput, ${evolution})).x`,
      };
    case "simplex4D":
      return {
        source: NOISE_SOURCES.simplex4D,
        call: `snoise(vec4(uvInput, ${evolution}, 0.0))`,
      };
    case "classic4D":
      return {
        source: NOISE_SOURCES.classic4D,
        call: `cnoise(vec4(uvInput, ${evolution}, 0.0))`,
      };
    case "simplex2D":
    default:
      return {
        source: NOISE_SOURCES.simplex2D,
        call: `snoise(uvInput + vec2(${evolution}))`,
      };
  }
}

function buildNoiseFragment(type: string): string {
  const { source, call } = noiseShaderSetup(type);
  return /* glsl */ `
    ${source}

    uniform float uTime;
    uniform float frequency;
    uniform float amplitude;
    uniform float octaves;
    uniform float lacunarity;
    uniform float gain;
    uniform float contrast;
    uniform float brightness;
    uniform vec2 offset;
    uniform bool parallax;
    uniform float parallaxScale;
    uniform bool animate;
    uniform float evolution;
    uniform float animateSpeed;
    uniform bool discretize;
    uniform float discretizeStep;
    uniform vec2 uResolution;
    uniform vec2 psrdPeriod;
    uniform float psrdRotation;
    uniform float opacity;

    varying vec2 vUv;

    float noiseLayer(vec2 uvInput) {
      return ${call};
    }

    float fbm(vec2 uvInput) {
      float total = 0.0;
      float freq = frequency;
      float amp = amplitude;
      int n = int(floor(octaves));
      float remainder = octaves - float(n);
      for (int i = 0; i < 10; i++) {
        if (i >= n) break;
        vec2 uvLayer = uvInput + offset;
        if (parallax) {
          uvLayer += offset * (parallaxScale * float(i));
        }
        total += noiseLayer(uvLayer * freq) * amp;
        freq *= lacunarity;
        amp *= gain;
      }
      if (n < 10) {
        vec2 uvLayer = uvInput + offset;
        if (parallax) {
          uvLayer += offset * (parallaxScale * float(n));
        }
        total += remainder * noiseLayer(uvLayer * freq) * amp;
      }
      return total;
    }

    void main() {
      vec2 uv = vUv;
      float n = fbm(uv);
      n = n * contrast + brightness;
      if (discretize) {
        n = floor(n / discretizeStep) * discretizeStep;
      }
      gl_FragColor = vec4(vec3(n), opacity);
    }
  `;
}

const NOISE_VERTEX_SHADER = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

/** Procedural noise fill using the decompiled module 203 GLSL sources. */
export class NoiseNode extends SceneNode {
  readonly kind = NodeKind.Noise;
  readonly typeLabel = "Noise";

  noiseType: NoiseType = "simplex3D";
  frequency = 10;
  amplitude = 1;
  octaves = 10;
  lacunarity = 2;
  gain = 0.5;
  contrast = 0.5;
  brightness = 0.5;
  offsetX = 0;
  offsetY = 0;
  parallax = false;
  parallaxScale = 1;
  animate = true;
  evolution = 0;
  animateSpeed = 1;
  discretize = false;
  discretizeStep = 0.5;
  psrdPeriodX = 2;
  psrdPeriodY = 2;
  psrdRotation = 0;
  timeOffset = 0;
  opacity = 1;
  srcBlending = "SrcAlpha";
  dstBlending = "OneMinusSrcAlpha";
  blendEquation = "Add";

  private mesh!: THREE.Mesh;
  private material!: THREE.ShaderMaterial;

  constructor(name: string, ctx: NodeContext) {
    super(name, ctx);
    this.initializeObjectMapping();
    this.build();
  }

  protected initializeObjectMapping(): void {
    for (const key of ["x", "y"]) this.objectMapping.set(`transform.${key}`, 0);
    this.objectMapping.set("transform.z", -500);
    for (const key of ["rotX", "rotY", "rotZ"]) this.objectMapping.set(`transform.${key}`, 0);
    for (const key of ["scaleX", "scaleY", "scaleZ"]) this.objectMapping.set(`transform.${key}`, 100);
  }

  protected build(): void {
    this.material = this.createShaderMaterial();
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1024, 1024, 32, 32), this.material);
    this.group.add(this.mesh);
  }

  setNoiseType(type: NoiseType): void {
    if (!NOISE_TYPES.includes(type)) return;
    this.noiseType = type;
    this.material.dispose();
    this.material = this.createShaderMaterial();
    this.mesh.material = this.material;
  }

  private createShaderMaterial(): THREE.ShaderMaterial {
    const resolution = this.ctx.resolution?.() ?? { x: window.innerWidth, y: window.innerHeight };
    return new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        frequency: { value: this.frequency },
        amplitude: { value: this.amplitude },
        octaves: { value: this.octaves },
        lacunarity: { value: this.lacunarity },
        gain: { value: this.gain },
        contrast: { value: this.contrast },
        brightness: { value: this.brightness },
        offset: { value: new THREE.Vector2(this.offsetX, this.offsetY) },
        parallax: { value: this.parallax },
        parallaxScale: { value: this.parallaxScale },
        animate: { value: this.animate },
        evolution: { value: this.evolution },
        animateSpeed: { value: this.animateSpeed },
        discretize: { value: this.discretize },
        discretizeStep: { value: this.discretizeStep },
        uResolution: { value: new THREE.Vector2(resolution.x, resolution.y) },
        psrdPeriod: { value: new THREE.Vector2(this.psrdPeriodX, this.psrdPeriodY) },
        psrdRotation: { value: this.psrdRotation },
        opacity: { value: this.opacity },
      },
      vertexShader: NOISE_VERTEX_SHADER,
      fragmentShader: buildNoiseFragment(this.noiseType),
      transparent: true,
    });
  }

  sync(time: number): void {
    const material = this.material;
    applyBlending(material, this.blendEquation, this.srcBlending, this.dstBlending);
    const elapsed = time + this.timeOffset;
    const uniforms = material.uniforms;
    uniforms.frequency.value = this.frequency;
    uniforms.amplitude.value = this.amplitude;
    uniforms.octaves.value = this.octaves;
    uniforms.lacunarity.value = this.lacunarity;
    uniforms.gain.value = this.gain;
    uniforms.contrast.value = this.contrast;
    uniforms.brightness.value = this.brightness;
    (uniforms.offset.value as THREE.Vector2).set(this.offsetX, this.offsetY);
    uniforms.parallax.value = this.parallax;
    uniforms.parallaxScale.value = this.parallaxScale;
    uniforms.animate.value = this.animate;
    uniforms.animateSpeed.value = this.animateSpeed;
    uniforms.evolution.value = this.animate ? elapsed : this.evolution;
    uniforms.discretize.value = this.discretize;
    uniforms.discretizeStep.value = this.discretizeStep;
    uniforms.uTime.value = elapsed;
    (uniforms.psrdPeriod.value as THREE.Vector2).set(this.psrdPeriodX, this.psrdPeriodY);
    uniforms.psrdRotation.value = this.psrdRotation;
    uniforms.opacity.value = this.opacity;

    this.mesh.position.set(
      (this.readNumber("transform.x") * REFERENCE_SCALE),
      (this.readNumber("transform.y") * REFERENCE_SCALE),
      this.z + this.readNumber("transform.z") * REFERENCE_SCALE,
    );
    this.mesh.rotation.set(
      (this.readNumber("transform.rotX") * Math.PI) / 180,
      (this.readNumber("transform.rotY") * Math.PI) / 180,
      (this.readNumber("transform.rotZ") * Math.PI) / 180,
    );
    this.mesh.scale.set(
      (this.readNumber("transform.scaleX") / 100) * REFERENCE_SCALE,
      (this.readNumber("transform.scaleY") / 100) * REFERENCE_SCALE,
      (this.readNumber("transform.scaleZ") / 100) * REFERENCE_SCALE,
    );
    this.mesh.visible = this.visible;
  }

  override createControllerSetups(): ControllerSetups {
    return {
      containers: [
        { id: "appearance", label: "Appearance", kind: ContainerKind.Folder },
        { id: "behaviour", label: "Behaviour", kind: ContainerKind.Folder },
        { id: "blending", label: "Blending", kind: ContainerKind.Folder },
        { id: "postprocessing", label: "Post-processing", kind: ContainerKind.Folder },
        { id: "transform", label: "Transform", kind: ContainerKind.Folder },
        { id: "offset", label: "Offset", kind: ContainerKind.Folder, parentId: "transform" },
      ],
      controllers: [
        this.choose("appearance.noiseType", "Noise Type", {
          parentId: "appearance",
          values: NOISE_TYPES,
          get: () => this.noiseType,
          set: (v) => this.setNoiseType(v as NoiseType),
        }),
        this.slider("appearance.frequency", "Frequency", {
          parentId: "appearance",
          min: 0,
          max: 20,
          get: () => this.frequency,
          set: (v) => {
            this.frequency = v;
          },
        }),
        this.slider("appearance.amplitude", "Amplitude", {
          parentId: "appearance",
          min: 0,
          max: 10,
          get: () => this.amplitude,
          set: (v) => {
            this.amplitude = v;
          },
        }),
        this.slider("appearance.octaves", "Octaves", {
          parentId: "appearance",
          min: 1,
          max: 10,
          step: 0.1,
          get: () => this.octaves,
          set: (v) => {
            this.octaves = v;
          },
        }),
        this.slider("appearance.lacunarity", "Lacunarity", {
          parentId: "appearance",
          min: 1,
          max: 4,
          get: () => this.lacunarity,
          set: (v) => {
            this.lacunarity = v;
          },
        }),
        this.slider("appearance.gain", "Gain", {
          parentId: "appearance",
          min: 0,
          max: 1,
          get: () => this.gain,
          set: (v) => {
            this.gain = v;
          },
        }),
        this.toggle("appearance.discretize", "Discretize", {
          parentId: "appearance",
          get: () => this.discretize,
          set: (v) => {
            this.discretize = v;
          },
        }),
        this.slider("appearance.discretizeStep", "Discretize Step", {
          parentId: "appearance",
          min: 0.01,
          max: 1,
          get: () => this.discretizeStep,
          set: (v) => {
            this.discretizeStep = v;
          },
        }),
        this.slider("appearance.psrdPeriodX", "PSRD Period X", {
          parentId: "appearance",
          min: 1,
          max: 100,
          get: () => this.psrdPeriodX,
          set: (v) => {
            this.psrdPeriodX = v;
          },
        }),
        this.slider("appearance.psrdPeriodY", "PSRD Period Y", {
          parentId: "appearance",
          min: 1,
          max: 100,
          get: () => this.psrdPeriodY,
          set: (v) => {
            this.psrdPeriodY = v;
          },
        }),
        this.slider("appearance.psrdRotation", "PSRD Rotation", {
          parentId: "appearance",
          min: -3.14,
          max: 3.14,
          get: () => this.psrdRotation,
          set: (v) => {
            this.psrdRotation = v;
          },
        }),
        this.toggle("behaviour.parallax", "Parallax", {
          parentId: "behaviour",
          get: () => this.parallax,
          set: (v) => {
            this.parallax = v;
          },
        }),
        this.slider("behaviour.parallaxScale", "Parallax Scale", {
          parentId: "behaviour",
          min: 0.1,
          max: 5,
          get: () => this.parallaxScale,
          set: (v) => {
            this.parallaxScale = v;
          },
        }),
        this.toggle("behaviour.animate", "Animate", {
          parentId: "behaviour",
          get: () => this.animate,
          set: (v) => {
            this.animate = v;
          },
        }),
        this.slider("behaviour.animateSpeed", "Animate Speed", {
          parentId: "behaviour",
          min: 0,
          max: 10,
          step: 0.1,
          get: () => this.animateSpeed,
          set: (v) => {
            this.animateSpeed = v;
          },
        }),
        this.slider("behaviour.timeOffset", "Time Offset", {
          parentId: "behaviour",
          min: -10000,
          max: 10000,
          step: 0.01,
          get: () => this.timeOffset,
          set: (v) => {
            this.timeOffset = v;
          },
        }),
        this.slider("behaviour.evolution", "Evolution", {
          parentId: "behaviour",
          min: 0,
          max: 10000,
          step: 0.1,
          get: () => this.evolution,
          set: (v) => {
            this.evolution = v;
          },
        }),
        this.slider("postprocessing.contrast", "Contrast", {
          parentId: "postprocessing",
          min: 0,
          max: 5,
          get: () => this.contrast,
          set: (v) => {
            this.contrast = v;
          },
        }),
        this.slider("postprocessing.brightness", "Brightness", {
          parentId: "postprocessing",
          min: -1,
          max: 1,
          get: () => this.brightness,
          set: (v) => {
            this.brightness = v;
          },
        }),
        this.slider("blending.opacity", "Opacity", {
          parentId: "blending",
          min: 0,
          max: 1,
          step: 0.01,
          get: () => this.opacity,
          set: (v) => {
            this.opacity = v;
          },
        }),
        this.choose("blending.blendEquation", "Blend equation", {
          parentId: "blending",
          values: BLEND_EQUATIONS,
          get: () => this.blendEquation,
          set: (v) => {
            this.blendEquation = v;
          },
        }),
        this.choose("blending.srcBlending", "Source blend factor", {
          parentId: "blending",
          values: BLEND_FACTORS,
          get: () => this.srcBlending,
          set: (v) => {
            this.srcBlending = v;
          },
        }),
        this.choose("blending.dstBlending", "Dst blend factor", {
          parentId: "blending",
          values: BLEND_FACTORS,
          get: () => this.dstBlending,
          set: (v) => {
            this.dstBlending = v;
          },
        }),
        this.slider("transform.offsetX", "X", {
          parentId: "offset",
          min: -10,
          max: 10,
          get: () => this.offsetX,
          set: (v) => {
            this.offsetX = v;
          },
        }),
        this.slider("transform.offsetY", "Y", {
          parentId: "offset",
          min: -10,
          max: 10,
          get: () => this.offsetY,
          set: (v) => {
            this.offsetY = v;
          },
        }),
        this.slider("transform.x", "Position X", {
          parentId: "transform",
          min: -2000,
          max: 2000,
          get: () => this.readNumber("transform.x"),
          set: (v) => this.objectMapping.set("transform.x", v),
        }),
        this.slider("transform.y", "Position Y", {
          parentId: "transform",
          min: -2000,
          max: 2000,
          get: () => this.readNumber("transform.y"),
          set: (v) => this.objectMapping.set("transform.y", v),
        }),
        this.slider("transform.z", "Position Z", {
          parentId: "transform",
          min: -2000,
          max: 1000,
          get: () => this.readNumber("transform.z"),
          set: (v) => this.objectMapping.set("transform.z", v),
        }),
        this.slider("transform.scaleX", "Scale X", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleX"),
          set: (v) => this.objectMapping.set("transform.scaleX", v),
        }),
        this.slider("transform.scaleY", "Scale Y", {
          parentId: "transform",
          min: 0,
          max: 500,
          get: () => this.readNumber("transform.scaleY"),
          set: (v) => this.objectMapping.set("transform.scaleY", v),
        }),
      ],
    };
  }
}

export type AnyNode =
  | LayerNode
  | MediaNode
  | ParticlesNode
  | SpectrumNode
  | PrimitiveNode
  | ProgressBarNode
  | LogoNode
  | GroundNode
  | NoiseNode
  | SkiaTextNode
  | AnimatedTextNode
  | LyricsNode
  | AudioWaveNode
  | BasicSpectrumBarsNode
  | ParticleLinesNode
  | ModelNode
  | LineBedNode
  | SphericalFieldNode
  | InstancedParticleSystemNode
  | ParticleSystemNode
  | ConfettiNode
  | ShaderItemNode
  | SkottieNode
  | VideoNode
  | ButterchurnNode
  | ParticleTimeLineNode;

export function createNode(
  kind: NodeKind,
  name: string,
  ctx: NodeContext,
): AnyNode {
  switch (kind) {
    case NodeKind.Media:
      return new MediaNode(name, ctx);
    case NodeKind.Particles:
      return new ParticlesNode(name, ctx);
    case NodeKind.Effects:
      return new SpectrumNode(name, ctx);
    case NodeKind.Cube:
    case NodeKind.Square:
    case NodeKind.Plane:
    case NodeKind.PointLight:
      return new PrimitiveNode(kind, name, ctx);
    case NodeKind.ProgressBar:
      return new ProgressBarNode(name, ctx);
    case NodeKind.Logo:
      return new LogoNode(name, ctx);
    case NodeKind.Ground:
      return new GroundNode(name, ctx);
    case NodeKind.Noise:
      return new NoiseNode(name, ctx);
    case NodeKind.SkiaText:
      return new SkiaTextNode(name, ctx);
    case NodeKind.AnimatedText:
      return new AnimatedTextNode(name, ctx);
    case NodeKind.Lyrics:
      return new LyricsNode(name, ctx);
    case NodeKind.AudioWave:
      return new AudioWaveNode(name, ctx);
    case NodeKind.BasicSpectrumBars:
      return new BasicSpectrumBarsNode(name, ctx);
    case NodeKind.ParticleLines:
      return new ParticleLinesNode(name, ctx);
    case NodeKind.Model:
      return new ModelNode(name, ctx);
    case NodeKind.LineBed:
      return new LineBedNode(name, ctx);
    case NodeKind.SphericalField:
      return new SphericalFieldNode(name, ctx);
    case NodeKind.InstancedParticleSystem:
      return new InstancedParticleSystemNode(name, ctx);
    case NodeKind.ParticleSystem:
      return new ParticleSystemNode(name, ctx);
    case NodeKind.Confetti:
      return new ConfettiNode(name, ctx);
    case NodeKind.ShaderItem:
      return new ShaderItemNode(name, ctx);
    case NodeKind.Skottie:
      return new SkottieNode(name, ctx);
    case NodeKind.Video:
      return new VideoNode(NodeKind.Video, name, ctx);
    case NodeKind.WasmVideo:
      return new VideoNode(NodeKind.WasmVideo, name, ctx);
    case NodeKind.Video2:
      return new VideoNode(NodeKind.Video2, name, ctx);
    case NodeKind.Butterchurn:
      return new ButterchurnNode(name, ctx);
    case NodeKind.ParticleTimeLine:
      return new ParticleTimeLineNode(name, ctx);
    default:
      return new LayerNode(name, ctx);
  }
}

export type { Automation };

