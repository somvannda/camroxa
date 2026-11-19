/**
 * Domain vocabulary.
 *
 * These enums mirror the vocabulary recovered from the reference application's
 * client bundle during the analysis phase (object kinds, controller variants,
 * container kinds, undo operations, automation comparators). Only the *names of
 * the concepts* are reused — every line of implementation here is original.
 */

import type { EasingName } from "./easing";

export type Id = string;

let counter = 0;
export function newId(prefix: string): Id {
  counter += 1;
  return `${prefix}_${Date.now().toString(36)}${counter.toString(36)}`;
}

/** What a timeline row represents. */
export enum NodeKind {
  Layer = "layer",
  Media = "media",
  Particles = "particles",
  Effects = "effects",
  Cube = "cube",
  Square = "square",
  Plane = "plane",
  PointLight = "point-light",
  ProgressBar = "progress-bar",
  Logo = "logo",
  Ground = "ground",
  Noise = "noise",
  SkiaText = "skia-text",
  AnimatedText = "animated-text",
  Lyrics = "lyrics",
  AudioWave = "audio-wave",
  BasicSpectrumBars = "basic-spectrum-bars",
  ParticleLines = "particle-lines",
  Model = "model",
  LineBed = "line-bed",
  SphericalField = "spherical-field",
  InstancedParticleSystem = "instanced-particle-system",
  ParticleSystem = "particle-system",
  Confetti = "confetti",
  ShaderItem = "shader-item",
  Skottie = "skottie",
  Video = "video",
  WasmVideo = "wasm-video",
  Video2 = "video-2",
  Butterchurn = "butterchurn",
  ParticleTimeLine = "particle-time-line",
}

/** Inspector control widget for a property. */
export enum PropertyKind {
  Select = "select",
  Slider = "slider",
  /** Two-handle range, e.g. the analyzer frequency range. */
  Range = "range",
  Boolean = "boolean",
  Text = "text",
  Color = "color",
  File = "file",
  ImageGrid = "image-grid",
  Analyzer = "analyzer",
  CustomPath = "custom-path",
}

/** How an inspector row groups its children. */
export enum ContainerKind {
  Folder = "folder",
  Controller = "controller",
  Value = "value",
}

/** Every mutation is one of these four shapes, which is what makes undo cheap. */
export enum UndoOp {
  ValuesChange = "values_change",
  AddObjects = "add_objects",
  RemoveObjects = "remove_objects",
  ReorderObjects = "reorder_objects",
}

/** Automation trigger comparison. */
export enum Comparator {
  LessThan = "less-than",
  MoreThan = "more-than",
  EqualTo = "equal-to",
}

/** Keyframe interpolation. */
export type Easing = EasingName | "ease-in" | "ease-out" | "hold";

export interface Keyframe {
  /** Absolute time in seconds within the project. */
  t: number;
  value: number;
  easing: Easing;
}

/**
 * How an automation is driven. `property` is the reference's `KEYFRAME` kind:
 * keyframed by hand. `audioImpact` is its audio-reactive kind, recomputed every
 * frame from the analyser's magnitude (see `audio-impact.ts`). `math` is the
 * reference's `MATH` kind, whose value comes from a user formula evaluated each
 * frame (see `formula.ts`).
 */
export type AutomationType = "property" | "audioImpact" | "math";

/**
 * The reference's Audio Impact settings (`variant: "number"`): the analyser
 * magnitude is normalised by the project's maximum impact, scaled by
 * `sensitivity`, mapped onto `min..max` and smoothed.
 */
export interface AudioImpactSettings {
  min: number;
  max: number;
  sensitivity: number;
  smoothing: number;
  /** Magnitudes below this are ignored. */
  floor: number;
  /** Magnitudes above this are clamped; 0 disables the clamp. */
  ceiling: number;
  cumulative: boolean;
  /** Reference `deltaSmoothing`: decay instead of following small changes. */
  deltaSmoothing?: boolean;
  /** Reference `deltaDecay`: per-frame amount when delta smoothing is on. */
  deltaDecay?: number;
  /** Reference `deltaThreshold`: changes smaller than this decay. */
  deltaThreshold?: number;
  /** Reference colour variant: no smoothing/delta/cumulative math. */
  color?: boolean;
}

/**
 * Reference automation group (`ADD_AUTOMATION_GROUP`): a named folder whose
 * `children` list automation ids. Groups are created by `G` from the selected
 * automations and persist with the project.
 */
export interface AutomationGroup {
  id: Id;
  /** Display name; new folders start as "Untitled group". */
  name: string;
  /** Automation ids in this group, in display order. */
  children: Id[];
}

export interface Automation {
  id: Id;
  /** Optional display name, e.g. "Fade in". */
  name?: string;
  /**
   * Reference `enabled` (absent means enabled). Disabled rows are skipped by
   * the automation pass; a folder's Enable/Disable toggles all of its children.
   */
  enabled?: boolean;
  /** Kind of automation, e.g. "audioImpact". */
  type: AutomationType;
  /** Reference `group`: id of the automation group this row belongs to. */
  groupId?: Id;
  /** Node this automation drives; empty when it only drives effect parameters. */
  nodeId: string;
  propertyId: string;
  /**
   * Effect parameters this automation drives, keyed by effect id — the
   * reference's `connections: { effectId: ["amplitudeX", "amplitudeY"] }`.
   */
  connections: Record<string, string[]>;
  /**
   * Automations this row drives, keyed by automation id — the reference's
   * `connections` entries whose target is another automation. Math rows use
   * this for `u1`-`u5` inputs; impact rows drive `sensitivity`/`minValue`/
   * `maxValue`; keyframes drive `startTime`/`endTime`.
   */
  automationConnections?: Record<Id, string[]>;
  keyframes: Keyframe[];
  /**
   * Set when an imported math row drives a `transform.scale*` controller: the
   * formula emits reference 1x factors while the controller stores percent.
   * Native projects store percent already, so they leave this unset.
   */
  referenceScaleUnits?: boolean;
  /** Present when `type === "audioImpact"`. */
  impact?: AudioImpactSettings;
  /**
   * Analyzer driving an audio-impact automation (reference `audioAnalyzer`).
   * The reference gives every audio-impact row its own selection, independent
   * of the analyzer bound to the object it drives; the Default analyzer is the
   * initial value.
   */
  audioAnalyzer?: Id;
  /**
   * Present when `type === "math"`: the reference's `formula`, evaluated every
   * frame with `t, p, a, m, d, u1-u5, g1-g5, rx, ry` in scope.
   */
  formula?: string;
  /**
   * Reference math `u1`-`u5` unit values. They are the formula's default inputs
   * when another automation is not wired into that unit; every layer of a fan
   * layout carries its own set (`u1..u5 =` the key poses), which is what makes
   * the panels spread instead of collapsing onto one pose.
   */
  units?: number[];
  /**
   * Reference automation `variant`. Colour rows interpolate between two hex
   * values instead of writing a number.
   */
  variant?: "number" | "color";
  /** Colour endpoints for `variant === "color"` (reference min/max values). */
  colors?: { from: string; to: string };
  comparator?: Comparator;
  threshold?: number;
}

/** A property the inspector can drive and the automation system can animate. */
export interface PropertyDescriptor {
  /** Stable path, unique per node, e.g. `behaviour.opacity`. */
  id: string;
  label: string;
  kind: PropertyKind;
  container: ContainerKind;
  /** Container this row belongs to. */
  parentId?: string;
  options?: readonly string[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  /** True when the property is numeric and therefore keyframeable. */
  animatable: boolean;
  /** Hover text copied from the reference controller definition. */
  tooltip?: string;
  /** Reference `constraints.enabled`: the row is greyed out until this passes. */
  constraint?: () => boolean;
  /** Rendered in place but inert: the reference has it, we do not back it yet. */
  disabled?: boolean;
  read(): number | string | boolean;
  write(value: number | string | boolean): void;
  /** Low/high pair for `PropertyKind.Range`. */
  readRange?(): [number, number];
  writeRange?(low: number, high: number): void;
}

export interface ContainerDescriptor {
  id: string;
  label: string;
  kind: ContainerKind;
  parentId?: string;
}

export interface ControllerSetups {
  containers: ContainerDescriptor[];
  controllers: PropertyDescriptor[];
}
