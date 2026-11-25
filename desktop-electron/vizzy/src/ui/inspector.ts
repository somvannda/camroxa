import { MediaNode, ParticlesNode, ParticleTimeLineNode, SpectrumNode, type AnyNode } from "../domain/nodes";
import type { SpectrumLayer } from "../domain/spectrum-layers";
import { analyzerControllerSetups } from "../domain/analyzer-controllers";
import { analyzerOf, type Analyzer } from "../domain/analyzers";
import {
  allPresets,
  deleteUserPreset,
  exportPresets,
  loadUserPresets,
  parsePresetFile,
  saveUserPreset,
  type Preset,
  type SpectrumParams,
} from "../domain/presets";
import {
  allParticlePresets,
  exportParticlePresets,
  loadUserParticlePresets,
  parseParticlePresetFile,
  type ParticleParams,
  type ParticlePreset,
} from "../domain/particle-presets";
import {
  ContainerKind,
  PropertyKind,
  type ContainerDescriptor,
  type PropertyDescriptor,
} from "../domain/types";
import { parseCustomPath, serializeCustomPath, type CustomPathPoint } from "../domain/custom-path";
import {
  reactionControllerValue,
  reactionDisplayValue,
  SPECTRUM_REACTION_PROPERTIES,
  type SpectrumReactionChange,
  type SpectrumReactionView,
} from "../domain/spectrum-reaction";
import { icon } from "./icons";
import type { IconName } from "./icons";

/**
 * Floating menu for inspector surfaces. Mirrors the reference's row menus
 * (`.dropdown.context`), which `main.ts` also uses.
 */
function openContextMenu(
  x: number,
  y: number,
  items: { label: string; icon: IconName; action: () => void }[],
): void {
  document.querySelectorAll(".dropdown.context").forEach((node) => node.remove());
  const panel = document.createElement("div");
  panel.className = "dropdown context";
  panel.setAttribute("role", "menu");
  const close = (): void => {
    panel.remove();
    document.removeEventListener("pointerdown", onDown, true);
  };
  const onDown = (event: PointerEvent): void => {
    if (!panel.contains(event.target as Node)) close();
  };
  for (const entry of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "dropdown-item";
    button.setAttribute("role", "menuitem");
    const lead = document.createElement("span");
    lead.className = "dd-icon";
    lead.append(icon(entry.icon, 14));
    const label = document.createElement("span");
    label.className = "dd-label";
    label.textContent = entry.label;
    button.append(lead, label);
    button.addEventListener("click", () => {
      close();
      entry.action();
    });
    panel.append(button);
  }
  document.body.append(panel);
  panel.style.left = `${Math.round(Math.min(x, window.innerWidth - 270))}px`;
  panel.style.top = `${Math.round(Math.min(y, window.innerHeight - 260))}px`;
  document.addEventListener("pointerdown", onDown, true);
  document.addEventListener("keydown", function onKey(event) {
    if (event.key !== "Escape") return;
    document.removeEventListener("keydown", onKey);
    close();
  });
}

const GROUP_ORDER = [
  "appearance",
  "random",
  "layers",
  "behaviour",
  "origin",
  "originX",
  "originY",
  "originZ",
  "rendering",
  "transform",
  "basics",
  "effects",
] as const;
const GROUP_LABELS: Record<string, string> = {
  layers: "Spectrum layers",
  behaviour: "General",
  transform: "Positioning & Size",
  effects: "Basics",
};

/**
 * Control order measured from the reference's spectrum inspector on 2026-10-27.
 * The reference surface ends at Shadow Y; the five controls after it exist only
 * in ours (see the note in nodes.ts), so they follow rather than interleave.
 * `basics.*` is unranked and keeps its declaration order.
 */
const SPECTRUM_ORDER = [
  "behaviour.type",
  "channel.imageFile",
  "channel.imageLink",
  "channel.imageUpload",
  "behaviour.fillStyle",
  "behaviour.height",
  "channel.imageSize",
  "channel.circularImage",
  "channel.fillCircle",
  "channel.circleSize",
  "channel.circleColor",
  "behaviour.mirror",
  "channel.clipCircle",
  "behaviour.draw",
  "behaviour.dotSize",
  "behaviour.feather",
  "behaviour.downsample",
  "channel.connect",
  "channel.aa",
  "channel.shadow",
  "channel.shadowScale",
  "channel.shadowAlpha",
  "channel.shadowX",
  "channel.shadowY",
  "behaviour.bands",
  "effects.gain",
  "effects.colorShift",
  "effects.smoothing",
  "behaviour.opacity",
  "transform.textureX",
  "transform.textureY",
  "transform.textureScaleX",
  "transform.textureScaleY",
  "transform.rotation",
  "transform.scaleMultiplier",
  "channel.aspectFix",
  "behaviour.scale",
  "transform.x",
  "transform.y",
  "transform.width",
  "transform.height",
];

function spectrumRank(id: string): number {
  const index = SPECTRUM_ORDER.indexOf(id);
  return index < 0 ? SPECTRUM_ORDER.length : index;
}

export interface InspectorCallbacks {
  onEdit(
    propertyId: string,
    label: string,
    value: number | string | boolean,
    animatable: boolean,
    previous?: number | string | boolean | readonly [number, number],
  ): void;
  onKeyframe(propertyId: string): void;
  onPreset(preset: Preset): void;
  onSavePreset(name: string): void;
  onOverwritePreset(preset: Preset): void;
  onEditPresetImage(preset: Preset): void;
  onImportPresets(presets: Preset[]): void;
  onDeletePreset(id: string): void;
  /** Particle presets mirror the spectrum gallery one-for-one. */
  onParticlePreset(preset: ParticlePreset): void;
  onSaveParticlePreset(name: string): void;
  onOverwriteParticlePreset(preset: ParticlePreset): void;
  onEditParticlePresetImage(preset: ParticlePreset): void;
  onImportParticlePresets(presets: ParticlePreset[]): void;
  onDeleteParticlePreset(id: string): void;
  onPickFile(propertyId: string): void;
  /** Current image for a file/upload row, so the control can show a thumbnail. */
  imagePreview?(propertyId: string): string | null;
  onClearImage?(propertyId: string): void;
  /** Reference spectrum-layer group actions. */
  onAddSpectrumLayer?(nodeId: string): void;
  onRemoveSpectrumLayer?(nodeId: string): void;
  /** Move an item to another analyzer, or detach it with null. */
  onAssignAnalyzer(nodeId: string, analyzerId: string | null): void;
  /** Bind one spectrum layer to an analyzer, or inherit the item's bands. */
  onAssignLayerAnalyzer(layerId: string, analyzerId: string | null): void;
  /** Bind a composition layer (Background Layer, etc.) to an analyzer. */
  onAssignCompositionLayerAnalyzer(layerId: string, analyzerId: string | null): void;
  /** Edit one spectrum layer property, optionally across the whole group. */
  onEditSpectrumLayer?(
    nodeId: string,
    layerId: string,
    property: keyof SpectrumLayer,
    value: string | number | boolean,
    group: boolean,
  ): void;
  /** Reference Add-layer colour shift, shown in the layers group header. */
  onSpectrumColorMode?(mode: "lighten" | "darken"): void;
  onSpectrumColorShift?(value: number): void;
  /** The reference opens the code-editor layout when the shader field is focused. */
  onFocusShader?(nodeId: string, layerId: string): void;
  /**
   * Edit a Spectrum item's Audio Impact automation (the reference's
   * `audioImpact` row that drives `scaleMultiplier` / `rotation`).
   */
  onSpectrumReaction?(nodeId: string, change: SpectrumReactionChange): void;
  /**
   * Add the reference's audio-impact row for this item (`Audio analyzers`
   * folder). The reference reacts to audio through these rows, never through
   * the analyzer binding alone, so the row is an explicit user action (except on
   * a background item, where choosing an analyzer creates it as one step).
   */
  onAddAudioImpact?(nodeId: string): void;
  /** Remove an audio-impact row created from the analyzer folder. */
  onRemoveAudioImpact?(automationId: string): void;
  /**
   * Edit an audio-impact row's range (module 682's `minValue`/`maxValue`) or its
   * response (`sensitivity`, `smoothing`). The reference exposes both on the
   * row; without this the inspector could only show a read-only summary.
   */
  onEditAudioImpact?(
    automationId: string,
    change: Partial<{ from: number; to: number; sensitivity: number; smoothing: number }>,
  ): void;
}

/** One row of the reference's automation list, as the inspector needs it. */
export interface InspectorAutomationInfo {
  /** Row id, so an audio-impact row can be removed from its inspector row. */
  id?: string;
  propertyId: string;
  keys: number[];
  /** Automation kind; `audioImpact` rows get their own inspector rows. */
  type?: string;
  /** Present for audio-impact rows: the range the row sweeps and its response. */
  impact?: {
    from: number;
    to: number;
    sensitivity?: number;
    smoothing?: number;
  };
}

/** True for video sources, so file rows render a video preview instead of an img. */
function isVideoSource(url: string): boolean {
  return /^data:video\//.test(url) || /\.(mp4|webm|mov|m4v|ogv)([?#]|$)/i.test(url);
}

/** Short label for a controller path in an automation row (`transform.scaleX`). */
function propertyLabel(propertyId: string): string {
  const tail = propertyId.includes(".") ? propertyId.split(".").pop() ?? propertyId : propertyId;
  const axis = /^(scale|position|rot)([XYZ])$/.exec(tail);
  if (axis) {
    const kind = axis[1] === "rot" ? "Rotation" : axis[1] === "scale" ? "Scale" : "Position";
    return `${kind} ${axis[2]}`;
  }
  return tail;
}

/** `100` / `1.5` / `0.01` without trailing zeros, for compact row readouts. */
function trimNumber(value: number): string {
  if (!Number.isFinite(value)) return "?";
  return String(Math.round(value * 1000) / 1000);
}

/** Display name for an image source: asset file name, path tail or data URL. */
function fileNameOf(url: string): string {
  if (url.startsWith("data:")) return "uploaded image";
  try {
    const path = new URL(url, location.href).pathname;
    return decodeURIComponent(path.split("/").pop() || url);
  } catch {
    return url.split("/").pop() || url;
  }
}

/** A rendered preview of a preset's own parameters (not third-party artwork). */
const THUMB_CACHE = new Map<string, string>();

/**
 * Gallery tile and menu labels read `Category · Name`. Spelled as an escape so
 * the source stays ASCII: a raw U+00B7 (UTF-8 C2 B7) is decoded as `┬╖` by
 * CP437 consoles, which made DOM dumps look like a rendering bug. The Spectrum
 * and particle galleries both use this one separator.
 */
const PRESET_TITLE_SEPARATOR = "\u00B7";

const presetTitle = (preset: { category: string; name: string }): string =>
  `${preset.category} ${PRESET_TITLE_SEPARATOR} ${preset.name}`;

function thumbKey(params: SpectrumParams, size: number): string {
  return [
    params.type,
    params.draw,
    params.fillStyle,
    params.bands,
    params.gain.toFixed(2),
    params.colorShift.toFixed(1),
    params.mirror ? 1 : 0,
    params.opacity.toFixed(0),
    params.height.toFixed(0),
    params.dotSize.toFixed(1),
    params.feather.toFixed(0),
    params.downsample,
    params.shadowEnabled ? (params.shadowSigma ?? 0).toFixed(0) : "0",
    params.fillCircle ? 1 : 0,
    (params.circleSize ?? 100).toFixed(0),
    size,
  ].join("|");
}

/** Deterministic band heights, so a preset always previews identically. */
function bandHeight(index: number, count: number, gain: number): number {
  const base = 0.32 + 0.5 * Math.abs(Math.sin(index * 1.7 + 0.6));
  const envelope = 0.5 + 0.5 * Math.sin(Math.PI * (index / Math.max(1, count - 1)));
  return Math.min(1, base * envelope * (0.55 + gain * 0.45));
}

function thumbFor(params: SpectrumParams, size = 64): string {
  const key = thumbKey(params, size);
  const cached = THUMB_CACHE.get(key);
  if (cached) return cached;

  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  const hue = Math.round((((params.colorShift % 100) + 100) % 100) * 3.6);
  const color = `hsl(${hue} 92% 62%)`;
  const faded = `hsla(${hue} 92% 62% / 0.55)`;

  // Plate
  ctx.fillStyle = "#0f0f15";
  ctx.fillRect(0, 0, size, size);
  const glow = ctx.createRadialGradient(size / 2, size * 0.72, 2, size / 2, size * 0.72, size * 0.7);
  glow.addColorStop(0, `hsla(${hue} 90% 55% / 0.22)`);
  glow.addColorStop(1, "hsla(0 0% 0% / 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, size, size);

  const pad = size * 0.12;
  const inner = size - pad * 2;
  const amp = params.height / 100;
  const baseline = size - pad;
  const isCircle = params.type === "Circle";
  const ds = Math.max(1, params.downsample || 1);
  const shadowSigma = params.shadowSigma ?? 0;
  if (params.shadowEnabled) {
    // A soft halo behind the shape, so a shadowed preset reads differently.
    ctx.shadowColor = color;
    ctx.shadowBlur = Math.min(12, 4 + shadowSigma * 0.3);
  }

  const points = (count: number): { x: number; y: number; h: number }[] => {
    const out: { x: number; y: number; h: number }[] = [];
    for (let i = 0; i < count; i += 1) {
      const h = Math.min(1, bandHeight(i, count, params.gain) * amp);
      out.push({ x: pad + (i / Math.max(1, count - 1)) * inner, y: baseline - h * inner * 0.82, h });
    }
    return out;
  };

  if (isCircle) {
    const count = Math.max(10, Math.min(Math.round(params.bands / ds), 36));
    const cx = size / 2;
    const cy = size / 2;
    const base = inner * 0.2 * ((params.circleSize ?? 100) / 100);
    if (params.fillCircle) {
      ctx.fillStyle = faded;
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(2, base), 0, Math.PI * 2);
      ctx.fill();
    }

    const radial = (i: number) => {
      const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
      const h = Math.min(1, bandHeight(i, count, params.gain) * amp);
      const outer = base + h * inner * 0.42;
      return {
        x0: cx + Math.cos(angle) * base,
        y0: cy + Math.sin(angle) * base,
        x1: cx + Math.cos(angle) * outer,
        y1: cy + Math.sin(angle) * outer,
      };
    };

    if (params.draw === "Line") {
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1.4, ((Math.PI * base) / count) * 0.7);
      for (let i = 0; i < count; i += 1) {
        const p = radial(i);
        ctx.beginPath();
        ctx.moveTo(p.x0, p.y0);
        ctx.lineTo(p.x1, p.y1);
        ctx.stroke();
      }
    } else if (params.draw === "Curve" && params.fillStyle === "Fill") {
      ctx.beginPath();
      for (let i = 0; i <= count; i += 1) {
        const p = radial(i % count);
        i === 0 ? ctx.moveTo(p.x1, p.y1) : ctx.lineTo(p.x1, p.y1);
      }
      for (let i = count; i >= 0; i -= 1) {
        const p = radial(i % count);
        ctx.lineTo(p.x0, p.y0);
      }
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    } else if (params.draw === "Point") {
      for (let i = 0; i < count; i += 1) {
        const p = radial(i);
        ctx.fillStyle = i % 2 === 0 ? color : faded;
        ctx.beginPath();
        ctx.arc(p.x1, p.y1, Math.max(1, params.dotSize * 0.5), 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.strokeStyle = color;
      ctx.lineWidth = params.draw === "Plexus" ? 1 : Math.max(1.4, 1 + params.feather / 26);
      ctx.beginPath();
      for (let i = 0; i <= count; i += 1) {
        const p = radial(i % count);
        i === 0 ? ctx.moveTo(p.x1, p.y1) : ctx.lineTo(p.x1, p.y1);
      }
      ctx.closePath();
      ctx.stroke();
    }
  } else {
    const count = Math.max(5, Math.min(Math.round(params.bands / ds), 22));
    const pts = points(count);

    if (params.draw === "Line") {
      const gap = inner / count;
      ctx.fillStyle = color;
      for (let i = 0; i < count; i += 1) {
        const h = Math.max(0.02, baseline - pts[i].y);
        ctx.fillRect(pad + i * gap + gap * 0.2, baseline - h, gap * 0.62, h);
      }
    } else if (params.draw === "Curve" && params.fillStyle === "Fill") {
      ctx.beginPath();
      ctx.moveTo(pts[0].x, baseline);
      for (const p of pts) ctx.lineTo(p.x, p.y);
      ctx.lineTo(pts[pts.length - 1].x, baseline);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    } else if (params.draw === "Point") {
      for (let i = 0; i < pts.length; i += 1) {
        ctx.fillStyle = i % 2 === 0 ? color : faded;
        ctx.beginPath();
        ctx.arc(pts[i].x, pts[i].y, Math.max(1, params.dotSize * 0.5), 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.strokeStyle = color;
      ctx.lineWidth = params.draw === "Plexus" ? 1 : Math.max(1.3, 1 + params.feather / 30);
      ctx.beginPath();
      pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
      ctx.stroke();
      if (params.draw === "Plexus") {
        ctx.fillStyle = faded;
        for (const p of pts) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, 1.1, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
  }

  ctx.shadowBlur = 0;
  ctx.shadowColor = "transparent";

  if (params.mirror && !isCircle) {
    ctx.globalAlpha = 0.35;
    ctx.scale(-1, 1);
    ctx.drawImage(canvas, -size, 0);
    ctx.globalAlpha = 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }

  const url = canvas.toDataURL("image/png");
  THUMB_CACHE.set(key, url);
  return url;
}

/* ------------------------------------------------------------------ */
/* Particle preset thumbnails                                          */
/* ------------------------------------------------------------------ */

const PARTICLE_THUMB_CACHE = new Map<string, string>();

/** Small deterministic PRNG so a saved particle preset always previews alike. */
function particleRandom(seed: string): () => number {
  let state = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    state ^= seed.charCodeAt(index);
    state = Math.imul(state, 16777619);
  }
  return () => {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function particleThumbKey(params: ParticleParams, size: number): string {
  return [
    params.seed,
    params.instances,
    params.color,
    params.sizeRange.join(","),
    params.alphaRange.join(","),
    params.startPos.join(","),
    params.endPos.join(","),
    params.directionY.join(","),
    params.mirror ? 1 : 0,
    params.constantSize ? 1 : 0,
    size,
  ].join("|");
}

/**
 * A parameter-drawn fallback for presets without rendered artwork (saved and
 * imported ones). It follows the same idea as the spectrum `thumbFor`: the
 * tile is a deterministic, local preview of the preset, not third-party art.
 */
function particleThumbFor(params: ParticleParams, size = 64): string {
  const key = particleThumbKey(params, size);
  const cached = PARTICLE_THUMB_CACHE.get(key);
  if (cached) return cached;

  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) return "";

  const random = particleRandom(`${params.seed}|${params.instances}|${params.color}`);
  const pad = size * 0.08;
  const inner = size - pad * 2;
  const color = params.color || "#ffffff";

  context.fillStyle = "#0d0e13";
  context.fillRect(0, 0, size, size);
  const glow = context.createRadialGradient(
    size / 2,
    size * 0.52,
    1,
    size / 2,
    size * 0.52,
    size * 0.72,
  );
  context.globalAlpha = 0.2;
  glow.addColorStop(0, color);
  glow.addColorStop(1, "rgba(0,0,0,0)");
  context.fillStyle = glow;
  context.fillRect(0, 0, size, size);
  context.globalAlpha = 1;

  const count = Math.max(36, Math.min(150, Math.round(params.instances / 14)));
  const spreadX = Math.min(1, Math.max(0.3, (params.endPos[0] - params.startPos[0]) / 320));
  const spreadY = Math.min(1, Math.max(0.3, (params.endPos[1] - params.startPos[1]) / 220));
  const avgSize = (params.sizeRange[0] + params.sizeRange[1]) / 2;
  const streak = Math.abs((params.directionY[0] + params.directionY[1]) / 2) > 20;

  context.globalCompositeOperation = "lighter";
  context.shadowColor = color;
  context.shadowBlur = Math.max(1, size * 0.025);

  const drawParticle = (x: number, y: number, radius: number, alpha: number): void => {
    context.globalAlpha = Math.max(0.04, Math.min(1, alpha));
    context.fillStyle = color;
    context.strokeStyle = color;
    if (streak) {
      context.lineWidth = Math.max(0.6, radius * 0.9);
      context.beginPath();
      context.moveTo(x, y);
      context.lineTo(x, y - radius * 3.2);
      context.stroke();
    } else {
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
    }
  };

  for (let index = 0; index < count; index += 1) {
    const x = size / 2 + (random() - 0.5) * inner * spreadX;
    const y = size / 2 + (random() - 0.5) * inner * spreadY;
    const radius = Math.max(0.55, (0.6 + random() * avgSize) * size * 0.07);
    const alpha =
      params.alphaRange[0] + random() * (params.alphaRange[1] - params.alphaRange[0]);
    drawParticle(x, y, radius, alpha * params.globalAlpha);
    // The node's mirror duplicates the cloud; the tile should read the same.
    if (params.mirror) drawParticle(size - x, y, radius, alpha * params.globalAlpha * 0.55);
  }

  context.globalAlpha = 1;
  context.shadowBlur = 0;
  context.globalCompositeOperation = "source-over";
  const url = canvas.toDataURL("image/png");
  PARTICLE_THUMB_CACHE.set(key, url);
  return url;
}

/**
 * Builds the inspector from a node's own controller description, with a preset
 * gallery driven by data rather than hardcoded tiles. Sections start collapsed,
 * matching the reference, except the preset gallery.
 */
export class Inspector {
  private open = new Set<string>();
  /** Reference “group editing”: layer edits apply to every sibling layer. */
  private layerGroupEdit = false;
  /** Add-layer brighten/darken settings, mirrored from the project. */
  private colorSettings: { mode: "lighten" | "darken"; shift: number } = {
    mode: "lighten",
    shift: 0.5,
  };
  /** The preset the user last applied; the only tile that reads as selected. */
  private activePresetId: string | null = null;
  /** Same identity-based selection for the particle gallery. */
  private activeParticlePresetId: string | null = null;
  /**
   * Galleries that have been shown at least once. A gallery auto-opens on its
   * first render; after that its state in `open` is the user's toggle and is
   * left alone (collapsing a gallery must survive selection changes).
   */
  private galleriesSeen = new Set<string>();
  /** Spectrum nodes whose Audio impact group has already been opened once. */
  private reactionSeen = new Set<string>();
  private keyed = new Set<string>();
  /** Analyzers for the current render, used by `AUDIO_ANALYZER` controls. */
  private analyzers: readonly Analyzer[] = [];
  /** Selected node id, so analyzer selects can update ownership too. */
  private nodeId: string | null = null;
  /** Rows of the selected object's automation list (audio-impact rows included). */
  private automationRows: readonly InspectorAutomationInfo[] = [];


  constructor(
    private readonly root: HTMLElement,
    private readonly title: HTMLElement,
    private readonly callbacks: InspectorCallbacks,
  ) {}

  render(
    node: AnyNode | null,
    automations: readonly InspectorAutomationInfo[],
    analyzers?: readonly Analyzer[],
    colorSettings?: { mode: "lighten" | "darken"; shift: number },
    reaction?: SpectrumReactionView | null,
  ): void {
    this.root.textContent = "";
    this.analyzers = analyzers ?? [];
    this.automationRows = automations;
    if (colorSettings) this.colorSettings = { ...colorSettings };
    this.nodeId = node?.id ?? null;
    if (node instanceof ParticlesNode) this.open.add("appearance");
    if (node instanceof ParticleTimeLineNode) this.open.add("general");
    if (!node) {
      this.title.textContent = "Objects / —";
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No selected object";
      this.root.append(empty);
      return;
    }

    this.title.textContent = `Objects / ${node.name}`;
    this.keyed = new Set(automations.filter((a) => a.keys.length > 0).map((a) => a.propertyId));

    // Image/Link rows live in these folders; the reference opens them so the
    // upload control and its thumbnail are visible without a click.
    if (node instanceof MediaNode || node instanceof SpectrumNode) this.open.add("behaviour");

    if (node instanceof SpectrumNode) {
      this.root.append(this.buildPresets(node));
    }

    // Particle gallery: exactly the spectrum gallery's shape, on the particle
    // item itself. A selected layer also shows it, so a tile can create the
    // item on the active layer when nothing particle-shaped is selected.
    if (node instanceof ParticlesNode) {
      this.root.append(this.buildParticlePresets());
    } else if (node.typeLabel === "Layer") {
      this.root.append(this.buildParticlePresets());
    }

    const setups = node.createControllerSetups();
    if (node instanceof SpectrumNode) {
      setups.controllers.sort((a, b) => spectrumRank(a.id) - spectrumRank(b.id));
    }

    // Only a Spectrum item has spectrum layers in the reference inspector.
    if (node instanceof SpectrumNode) {
      this.root.append(this.buildSpectrumLayers(node, automations, analyzers));
    }

    for (const container of this.orderedContainers(setups.containers)) {
      const controllers = setups.controllers.filter((c) => c.parentId === container.id);
      if (controllers.length === 0) continue;
      this.root.append(
        this.buildGroup(
          container,
          controllers.map((c) => this.buildField(c)),
        ),
      );
    }

    // Ours alone: the reference has no per-item analyzer row. It follows the
    // mirrored sections so General / Positioning & Size / Basics stay in order.
    // Items that ship the reference's own AUDIO_ANALYZER control (Particles)
    // already bind an analyzer there, so the extra row would duplicate it.
    const ownsAnalyzer = setups.controllers.some((c) => c.kind === PropertyKind.Analyzer);
    if (analyzers && !ownsAnalyzer) {
      const row =
        node.typeLabel === "Layer"
          ? this.buildCompositionLayerAnalyzerRow(node, analyzers)
          : this.buildAnalyzerRow(node, analyzers);
      this.root.append(
        this.buildGroup(
          // Reference grouping: the analyzer choice is its own
          // "Audio analyzers" folder, on items and composition layers alike.
          { id: "audio", label: "Audio analyzers", kind: ContainerKind.Folder },
          // The reference's per-property audio-impact rows live next to the
          // analyzer binding: `Image.update` only reads the analyzer for its
          // vignette, so an item moves/zooms because an `audioImpact` row
          // drives its transform (see `buildAudioImpactRows`). Spectrum items
          // have their own reaction group further down.
          node.typeLabel === "Layer" || node instanceof SpectrumNode
            ? [row]
            : [row, ...this.buildAudioImpactRows(node)],
        ),
      );
    }

    // The reference expresses "how this item moves with the music" as an
    // Audio Impact automation on a transform controller. A Spectrum's rows
    // (`scaleMultiplier`, `_rotation`) are the ones its projects animate, so
    // the item gets that automation's controllers inline, next to the
    // analyser choice.
    if (node instanceof SpectrumNode) {
      // A node that already has a reaction opens its group the first time it is
      // shown; after that the user's collapse state wins.
      if (reaction && !this.reactionSeen.has(node.id)) {
        this.reactionSeen.add(node.id);
        this.open.add("reaction");
      }
      this.root.append(this.buildSpectrumReaction(node, reaction ?? null, analyzers));
    }

    const orphans = setups.controllers.filter((c) => !c.parentId);
    if (orphans.length > 0) {
      this.root.append(
        this.buildGroup(
          { id: "general", label: "General", kind: ContainerKind.Folder },
          orphans.map((c) => this.buildField(c)),
        ),
      );
    }
  }

  private orderedContainers(containers: ContainerDescriptor[]): ContainerDescriptor[] {
    const rank = new Map<string, number>(GROUP_ORDER.map((id, index) => [id, index]));
    return [...containers].sort((a, b) => (rank.get(a.id) ?? 99) - (rank.get(b.id) ?? 99));
  }

  /**
   * Analyzer object view. The reference shows an analyzer's controllers in the
   * inspector when the analyzer is selected, exactly like an item's.
   */
  renderAnalyzer(analyzer: Analyzer, onChange?: () => void): void {
    this.root.textContent = "";
    this.analyzers = [];
    this.nodeId = null;
    this.keyed.clear();
    // The reference's Basics folder is open by default.
    this.open.add("basics");
    this.title.textContent = `Objects / ${analyzer.name}`;

    const setups = analyzerControllerSetups(analyzer, () => {
      this.renderAnalyzer(analyzer);
      onChange?.();
    });
    for (const container of this.orderedContainers(setups.containers)) {
      const controllers = setups.controllers.filter((c) => c.parentId === container.id);
      if (controllers.length === 0) continue;
      this.root.append(
        this.buildGroup(
          container,
          controllers.map((c) => this.buildField(c)),
        ),
      );
    }
  }

  /* ---------------------------------------------------------------- */
  /* Presets                                                          */
  /* ---------------------------------------------------------------- */

  /**
   * Open a gallery the first time it is built; afterwards `open` is the user's
   * toggle. Keeping this per-gallery means collapsing the Spectrum gallery does
   * not affect the particle one (and vice versa), and a rebuilt inspector after
   * a selection change no longer flashes it collapsed.
   */
  private ensureGalleryOpen(key: string): void {
    if (this.galleriesSeen.has(key)) return;
    this.galleriesSeen.add(key);
    this.open.add(key);
  }

  private buildPresets(node: SpectrumNode): HTMLElement {
    this.ensureGalleryOpen("presets");
    const section = document.createElement("section");
    section.className = "group preset-group";

    const headRow = document.createElement("div");
    headRow.className = "group-head-row";

    const head = document.createElement("button");
    head.type = "button";
    head.className = "group-head";
    const twist = document.createElement("span");
    twist.className = "twist";
    twist.append(icon(this.open.has("presets") ? "expand_more" : "chevron_right", 14));
    head.append(twist, document.createTextNode("Preset"));

    const gear = document.createElement("button");
    gear.type = "button";
    gear.className = "icon";
    gear.title = "Preset tools";
    gear.setAttribute("aria-haspopup", "true");
    gear.append(icon("settings", 14));

    headRow.append(head, gear);

    const body = document.createElement("div");
    body.className = "group-body";
    if (!this.open.has("presets")) section.classList.add("collapsed");

    head.addEventListener("click", () => {
      if (this.open.has("presets")) this.open.delete("presets");
      else this.open.add("presets");
      section.classList.toggle("collapsed");
      twist.replaceChildren(
        icon(this.open.has("presets") ? "expand_more" : "chevron_right", 14),
      );
    });

    const grid = document.createElement("div");
    grid.className = "preset-grid";
    const current = node.readParams();

    for (const preset of allPresets()) {
      const button = document.createElement("button");
      // Highlight by identity, not by a loose parameter match: many presets share
      // type/draw/bands/mirror, which lit several tiles at once.
      const active = preset.id === this.activePresetId;
      button.className = `preset${active ? " active" : ""}`;
      button.title = presetTitle(preset);

      const thumb = document.createElement("img");
      thumb.alt = "";
      thumb.decoding = "async";
      // Sourced presets carry the reference's own thumbnail; image-backed ones
      // preview their artwork; anything else renders from its parameters.
      if (preset.thumb) {
        thumb.src = preset.thumb;
        thumb.className = "preset-art";
        thumb.referrerPolicy = "no-referrer";
      } else if (preset.params.imageUrl) {
        thumb.src = preset.params.imageUrl;
        thumb.className = "preset-art";
        thumb.referrerPolicy = "no-referrer";
      } else {
        thumb.src = thumbFor(preset.params);
      }
      button.append(thumb);

      button.addEventListener("click", () => {
        this.activePresetId = preset.id;
        // The save tile shares `.preset` for sizing; it is an action, never a
        // selection, so exclude it from the active-state pass.
        for (const other of grid.querySelectorAll<HTMLButtonElement>(".preset:not(.add)")) {
          other.classList.toggle("active", other === button);
        }
        this.callbacks.onPreset(preset);
      });
      button.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        // Reference preset menus: admin/built-in presets only offer "Choose
        // preset"; saved presets add Save as this preset / Edit image / Delete.
        const saved = loadUserPresets().some((entry) => entry.id === preset.id);
        const items: { label: string; icon: IconName; action: () => void }[] = [
          { label: "Choose preset", icon: "palette", action: () => this.callbacks.onPreset(preset) },
        ];
        if (saved) {
          items.push(
            {
              label: "Save as this preset",
              icon: "save",
              action: () => this.callbacks.onOverwritePreset(preset),
            },
            {
              label: "Edit image",
              icon: "camera_alt",
              action: () => this.callbacks.onEditPresetImage(preset),
            },
            {
              label: "Delete",
              icon: "delete",
              action: () => this.callbacks.onDeletePreset(preset.id),
            },
          );
        }
        openContextMenu(event.clientX, event.clientY, items);
      });
      grid.append(button);
    }

    const save = document.createElement("button");
    save.className = "preset add";
    save.title = "Save current settings as a preset";
    save.textContent = "+";
    save.addEventListener("click", () => {
      const name = window.prompt("Preset name", `Custom ${loadUserPresets().length + 1}`);
      if (name === null) return;
      this.callbacks.onSavePreset(name);
    });
    grid.append(save);

    const tools = document.createElement("div");
    tools.className = "preset-tools";

    const importButton = document.createElement("button");
    importButton.className = "mini";
    importButton.textContent = "Import";
    importButton.addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json,application/json";
      input.addEventListener("change", async () => {
        const file = input.files?.[0];
        if (!file) return;
        try {
          const presets = parsePresetFile(await file.text());
          this.callbacks.onImportPresets(presets);
        } catch (error) {
          console.error("preset import failed", error);
        }
      });
      input.click();
    });

    const exportButton = document.createElement("button");
    exportButton.className = "mini";
    exportButton.textContent = "Export all";
    exportButton.addEventListener("click", () => {
      const blob = new Blob([exportPresets(allPresets())], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "spectrum-presets.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    });

    tools.append(importButton, exportButton);
    tools.hidden = true;

    gear.addEventListener("click", () => {
      tools.hidden = !tools.hidden;
      gear.classList.toggle("on", !tools.hidden);
    });

    body.append(grid, tools);
    section.append(headRow, body);
    return section;
  }

  /* ---------------------------------------------------------------- */
  /* Particle presets                                                 */
  /* ---------------------------------------------------------------- */

  /**
   * The spectrum preset window, for `ParticlesNode`. Same markup and classes,
   * with a `particle-presets` open key so the two galleries collapse
   * independently. Selecting a layer also shows the group; its tiles then
   * create a Particles item on that layer.
   */
  private buildParticlePresets(): HTMLElement {
    this.ensureGalleryOpen("particle-presets");
    const section = document.createElement("section");
    section.className = "group preset-group particle-preset-group";

    const headRow = document.createElement("div");
    headRow.className = "group-head-row";

    const head = document.createElement("button");
    head.type = "button";
    head.className = "group-head";
    const twist = document.createElement("span");
    twist.className = "twist";
    twist.append(
      icon(this.open.has("particle-presets") ? "expand_more" : "chevron_right", 14),
    );
    head.append(twist, document.createTextNode("Preset"));

    const gear = document.createElement("button");
    gear.type = "button";
    gear.className = "icon";
    gear.title = "Preset tools";
    gear.setAttribute("aria-haspopup", "true");
    gear.append(icon("settings", 14));

    headRow.append(head, gear);

    const body = document.createElement("div");
    body.className = "group-body";
    if (!this.open.has("particle-presets")) section.classList.add("collapsed");

    head.addEventListener("click", () => {
      if (this.open.has("particle-presets")) this.open.delete("particle-presets");
      else this.open.add("particle-presets");
      section.classList.toggle("collapsed");
      twist.replaceChildren(
        icon(this.open.has("particle-presets") ? "expand_more" : "chevron_right", 14),
      );
    });

    const grid = document.createElement("div");
    grid.className = "preset-grid particle-preset-grid";

    const applyTile = (button: HTMLButtonElement, preset: ParticlePreset): void => {
      this.activeParticlePresetId = preset.id;
      for (const other of grid.querySelectorAll<HTMLButtonElement>(".preset:not(.add)")) {
        other.classList.toggle("active", other === button);
      }
      this.callbacks.onParticlePreset(preset);
    };

    for (const preset of allParticlePresets()) {
      const button = document.createElement("button");
      button.type = "button";
      const active = preset.id === this.activeParticlePresetId;
      button.className = `preset particle-preset${active ? " active" : ""}`;
      button.dataset.presetId = preset.id;
      button.title = `${preset.category} \u00B7 ${preset.name}`;

      const thumb = document.createElement("img");
      thumb.alt = "";
      thumb.decoding = "async";
      if (preset.thumb) {
        thumb.src = preset.thumb;
        thumb.className = "preset-art";
        thumb.referrerPolicy = "no-referrer";
      } else {
        thumb.src = particleThumbFor(preset.params);
      }
      button.append(thumb);

      button.addEventListener("click", () => applyTile(button, preset));
      button.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        const saved = loadUserParticlePresets().some((entry) => entry.id === preset.id);
        const items: { label: string; icon: IconName; action: () => void }[] = [
          { label: "Choose preset", icon: "palette", action: () => applyTile(button, preset) },
        ];
        if (saved) {
          items.push(
            {
              label: "Save as this preset",
              icon: "save",
              action: () => this.callbacks.onOverwriteParticlePreset(preset),
            },
            {
              label: "Edit image",
              icon: "camera_alt",
              action: () => this.callbacks.onEditParticlePresetImage(preset),
            },
            {
              label: "Delete",
              icon: "delete",
              action: () => this.callbacks.onDeleteParticlePreset(preset.id),
            },
          );
        }
        openContextMenu(event.clientX, event.clientY, items);
      });
      grid.append(button);
    }

    const save = document.createElement("button");
    save.type = "button";
    save.className = "preset add";
    save.title = "Save current settings as a preset";
    save.textContent = "+";
    save.addEventListener("click", () => {
      const name = window.prompt(
        "Particle preset name",
        `Particle ${loadUserParticlePresets().length + 1}`,
      );
      if (name === null) return;
      this.callbacks.onSaveParticlePreset(name);
    });
    grid.append(save);

    const importPresets = (): void => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json,application/json";
      input.addEventListener("change", async () => {
        const file = input.files?.[0];
        if (!file) return;
        try {
          this.callbacks.onImportParticlePresets(parseParticlePresetFile(await file.text()));
        } catch (error) {
          console.error("particle preset import failed", error);
        }
      });
      input.click();
    };

    const exportAll = (): void => {
      const blob = new Blob([exportParticlePresets(allParticlePresets())], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "particle-presets.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    };

    gear.addEventListener("click", (event) => {
      event.stopPropagation();
      const rect = gear.getBoundingClientRect();
      openContextMenu(rect.left, rect.bottom + 4, [
        {
          label: "Save current as preset",
          icon: "save",
          action: () => {
            const name = window.prompt(
              "Particle preset name",
              `Particle ${loadUserParticlePresets().length + 1}`,
            );
            if (name === null) return;
            this.callbacks.onSaveParticlePreset(name);
          },
        },
        { label: "Import JSON", icon: "upload", action: importPresets },
        { label: "Export all", icon: "download", action: exportAll },
        {
          label: "Delete a saved preset",
          icon: "delete",
          action: () => {
            const saved = loadUserParticlePresets();
            if (saved.length === 0) {
              window.alert("There are no saved particle presets to delete.");
              return;
            }
            const panel = gear.getBoundingClientRect();
            openContextMenu(
              panel.left,
              panel.bottom + 4,
              saved.map((preset) => ({
                label: `${preset.category} \u00B7 ${preset.name}`,
                icon: "delete" as IconName,
                action: () => this.callbacks.onDeleteParticlePreset(preset.id),
              })),
            );
          },
        },
      ]);
    });

    body.append(grid);
    section.append(headRow, body);
    return section;
  }

  /* ---------------------------------------------------------------- */
  /* Rows                                                             */
  /* ---------------------------------------------------------------- */

  private buildSpectrumLayers(
    node: SpectrumNode,
    automations: readonly InspectorAutomationInfo[],
    analyzers?: readonly Analyzer[],
  ): HTMLElement {
    // Reference "Spectrum layers" group: Add layer / Remove layer live in the
    // group header and the rows expand by default.
    const section = document.createElement("section");
    section.className = "group";
    if (!this.open.has("layers")) this.open.add("layers");

    const headRow = document.createElement("div");
    headRow.className = "group-head-row";

    const head = document.createElement("button");
    head.className = "group-head";
    const twist = document.createElement("span");
    twist.className = "twist";
    twist.append(icon("expand_more", 14));
    head.append(twist, document.createTextNode(GROUP_LABELS.layers));

    const actions = document.createElement("div");
    actions.className = "group-actions";

    const groupEdit = document.createElement("button");
    groupEdit.type = "button";
    groupEdit.className = `icon${this.layerGroupEdit ? " active" : ""}`;
    groupEdit.title = `${this.layerGroupEdit ? "Turn off" : "Turn on"} group editing`;
    groupEdit.append(icon("account_tree", 14));
    groupEdit.addEventListener("click", () => {
      this.layerGroupEdit = !this.layerGroupEdit;
      groupEdit.classList.toggle("active", this.layerGroupEdit);
      groupEdit.title = `${this.layerGroupEdit ? "Turn off" : "Turn on"} group editing`;
    });

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "icon";
    remove.title = "Remove layer";
    remove.append(icon("remove", 14));
    remove.addEventListener("click", () => this.callbacks.onRemoveSpectrumLayer?.(node.id));

    const add = document.createElement("button");
    add.type = "button";
    add.className = "icon";
    add.title = "Add layer";
    add.append(icon("add", 14));
    add.addEventListener("click", () => this.callbacks.onAddSpectrumLayer?.(node.id));

    const shiftButton = document.createElement("button");
    shiftButton.type = "button";
    shiftButton.className = "icon";
    shiftButton.title = "Change color shift";
    shiftButton.append(icon("tune", 14));

    const popover = document.createElement("div");
    popover.className = "layer-shift-popover";
    popover.hidden = true;

    const modes = document.createElement("div");
    modes.className = "layer-shift-modes";
    const modeButtons = new Map<"lighten" | "darken", HTMLButtonElement>();
    for (const mode of ["lighten", "darken"] as const) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = mode === "lighten" ? "Lighten" : "Darken";
      button.classList.toggle("active", this.colorSettings.mode === mode);
      button.addEventListener("click", () => {
        this.colorSettings.mode = mode;
        for (const [value, entry] of modeButtons) entry.classList.toggle("active", value === mode);
        this.callbacks.onSpectrumColorMode?.(mode);
      });
      modeButtons.set(mode, button);
      modes.append(button);
    }

    const shiftLabel = document.createElement("label");
    shiftLabel.className = "layer-shift-label";
    shiftLabel.textContent = `Color shift ${this.colorSettings.shift.toFixed(2)}`;
    const shiftRange = document.createElement("input");
    shiftRange.type = "range";
    shiftRange.min = "0";
    shiftRange.max = "1";
    shiftRange.step = "0.05";
    shiftRange.value = String(this.colorSettings.shift);
    shiftRange.addEventListener("input", () => {
      this.colorSettings.shift = Number(shiftRange.value);
      shiftLabel.textContent = `Color shift ${this.colorSettings.shift.toFixed(2)}`;
      this.callbacks.onSpectrumColorShift?.(this.colorSettings.shift);
    });
    popover.append(modes, shiftLabel, shiftRange);
    shiftButton.addEventListener("click", () => {
      popover.hidden = !popover.hidden;
    });

    actions.append(groupEdit, remove, add, shiftButton, popover);
    headRow.append(head, actions);

    const body = document.createElement("div");
    body.className = "group-body";
    body.append(...this.buildLayerRows(node, automations, analyzers));

    section.append(headRow, body);
    return section;
  }

  private buildLayerRows(
    node: AnyNode,
    _automations: readonly InspectorAutomationInfo[],
    analyzers?: readonly Analyzer[],
  ): HTMLElement[] {
    // One expandable entry per spectrum layer, matching the reference's
    // LIST container: head summary, analyzer binding, then its controllers.
    const spectrumNode = node instanceof SpectrumNode ? node : null;
    const layers = spectrumNode ? spectrumNode.layers : [];
    if (layers.length === 0) {
      const row = document.createElement("div");
      row.className = "field layer-row";
      const name = document.createElement("span");
      name.className = "layer-name";
      name.textContent = "No layers";
      row.append(name);
      return [row];
    }

    const edit = (
      layer: SpectrumLayer,
      property: keyof SpectrumLayer,
      value: string | number | boolean,
    ): void => {
      this.callbacks.onEditSpectrumLayer?.(
        node.id,
        layer.id,
        property,
        value,
        this.layerGroupEdit,
      );
    };
    const field = (label: string, control: HTMLElement, tooltip?: string): HTMLElement => {
      const wrap = document.createElement("div");
      wrap.className = "layer-field";
      const name = document.createElement("label");
      name.textContent = label;
      if (tooltip) {
        name.title = tooltip;
        name.classList.add("has-tooltip");
      }
      wrap.append(name, control);
      return wrap;
    };
    const number = (
      value: number,
      min: number,
      max: number,
      step: number,
      onCommit: (value: number) => void,
    ): HTMLInputElement => {
      const input = document.createElement("input");
      input.type = "number";
      input.min = String(min);
      input.max = String(max);
      input.step = String(step);
      input.value = String(value);
      input.addEventListener("change", () => onCommit(Number(input.value)));
      return input;
    };
    const select = (
      options: readonly string[],
      value: string,
      onCommit: (value: string) => void,
    ): HTMLSelectElement => {
      const element = document.createElement("select");
      for (const option of options) {
        const entry = document.createElement("option");
        entry.value = option;
        entry.textContent = option;
        if (option === value) entry.selected = true;
        element.append(entry);
      }
      element.addEventListener("change", () => onCommit(element.value));
      return element;
    };
    const color = (value: string, onCommit: (value: string) => void): HTMLInputElement => {
      const input = document.createElement("input");
      input.type = "color";
      input.value = value;
      input.addEventListener("change", () => onCommit(input.value));
      return input;
    };

    return layers.map((layer, index) => {
      const section = document.createElement("section");
      section.className = "spectrum-layer";

      const head = document.createElement("div");
      head.className = "layer-head";
      head.setAttribute("role", "button");
      head.tabIndex = 0;
      const openKey = `layer:${layer.id}`;
      const open = this.open.has(openKey);
      const twist = document.createElement("span");
      twist.className = "twist";
      twist.append(icon(open ? "expand_more" : "chevron_right", 14));

      const swatch = document.createElement("span");
      swatch.className = "layer-dot";
      swatch.style.background = layer.color;

      const name = document.createElement("span");
      name.className = "layer-name";
      name.textContent = `Layer ${index + 1}`;

      const meta = document.createElement("span");
      meta.className = "value";
      const shaderError =
        layer.colorType === "Shader" ? spectrumNode?.shaderErrors.get(layer.id) : undefined;
      if (!layer.enabled) {
        meta.textContent = "off";
      } else if (shaderError) {
        meta.textContent = "Shader (fallback)";
        head.title = shaderError;
      } else {
        meta.textContent = layer.colorType;
      }
      head.append(twist, swatch, name, meta);

      if (analyzers) {
        const analyzer = document.createElement("select");
        analyzer.className = "layer-analyzer";
        analyzer.title = "Audio analyzer driving this layer";
        const inherit = document.createElement("option");
        inherit.value = "";
        inherit.textContent = "Item bands";
        if (!layer.audioAnalyzer) inherit.selected = true;
        analyzer.append(inherit);
        for (const option of analyzers) {
          const entry = document.createElement("option");
          entry.value = option.id;
          entry.textContent = option.name;
          if (layer.audioAnalyzer === option.id) entry.selected = true;
          analyzer.append(entry);
        }
        analyzer.addEventListener("click", (event) => event.stopPropagation());
        analyzer.addEventListener("change", () => {
          this.callbacks.onAssignLayerAnalyzer(layer.id, analyzer.value || null);
        });
        head.append(analyzer);
      }

      const controls = document.createElement("div");
      controls.className = "layer-controls";
      controls.hidden = !open;

      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = layer.enabled;
      enabled.addEventListener("change", () => edit(layer, "enabled", enabled.checked));
      controls.append(field("Enabled", enabled));

      controls.append(
        field(
          "Color type",
          select(["Solid", "From-to", "Gradient", "Shader"], layer.colorType, (value) =>
            edit(layer, "colorType", value),
          ),
        ),
      );

      if (layer.colorType === "Solid") {
        controls.append(field("Color", color(layer.color, (value) => edit(layer, "color", value))));
      } else if (layer.colorType === "From-to") {
        controls.append(
          field("From", color(layer.colorFrom, (value) => edit(layer, "colorFrom", value))),
          field("To", color(layer.colorTo, (value) => edit(layer, "colorTo", value))),
          field(
            "Base on",
            select(
              ["Value", "Y-Position", "X-Position", "Distance from center"],
              layer.baseOn,
              (value) => edit(layer, "baseOn", value),
            ),
          ),
        );
      } else if (layer.colorType === "Gradient") {
        const gradient = document.createElement("input");
        gradient.type = "text";
        gradient.value = layer.colorGradient;
        gradient.addEventListener("change", () =>
          edit(layer, "colorGradient", gradient.value),
        );
        controls.append(field("Gradient", gradient));
      } else {
        const source = document.createElement("textarea");
        source.className = "layer-shader";
        source.spellcheck = false;
        source.value = layer.shaderSrc;
        source.addEventListener("change", () => edit(layer, "shaderSrc", source.value));
        // Reference SHADER_EDIT: focusing the inline editor activates layout F.
        source.addEventListener("focus", () =>
          this.callbacks.onFocusShader?.(node.id, layer.id),
        );
        controls.append(
          field(
            "Shader",
            source,
            "Looking for Color? Switch the type above to Solid! You can search for fragment shaders online to find inspiration. You can copy-paste most shaders from http://glslsandbox.com/",
          ),
        );
      }

      controls.append(
        field(
          "Multiplier",
          number(layer.multiplier, 0.1, 10, 0.1, (value) => edit(layer, "multiplier", value)),
        ),
        field("Alpha", number(layer.alpha, 0, 1, 0.01, (value) => edit(layer, "alpha", value))),
        field(
          "Rotation",
          number(layer.rotation, -360, 360, 1, (value) => edit(layer, "rotation", value)),
        ),
        field("Scale", number(layer.scale, 0.1, 4, 0.01, (value) => edit(layer, "scale", value))),
        field(
          "Shadow color",
          color(layer.shadowColor, (value) => edit(layer, "shadowColor", value)),
        ),
        field(
          "Shadow alpha",
          number(layer.shadowAlpha, 0, 1, 0.01, (value) => edit(layer, "shadowAlpha", value)),
        ),
        field(
          "Shadow scale",
          number(layer.shadowScale, 0, 2, 0.01, (value) => edit(layer, "shadowScale", value)),
        ),
        field(
          "Blur",
          number(layer.blurAmount, 0, 100, 0.1, (value) => edit(layer, "blurAmount", value)),
        ),
      );

      head.addEventListener("click", () => {
        if (this.open.has(openKey)) this.open.delete(openKey);
        else this.open.add(openKey);
        controls.hidden = !controls.hidden;
        twist.replaceChildren(icon(controls.hidden ? "chevron_right" : "expand_more", 14));
      });

      section.append(head, controls);
      return section;
    });
  }

  private buildAnalyzerRow(node: AnyNode, analyzers: readonly Analyzer[]): HTMLElement {
    const field = document.createElement("div");
    field.className = "field";

    const label = document.createElement("label");
    label.textContent = "Audio analyzer";

    const owner = analyzerOf(analyzers, node.id);
    const select = document.createElement("select");
    // Stable hook for checks and for the composition-layer row's twin.
    select.className = "audio-analyzer";
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "None";
    if (!owner) none.selected = true;
    select.append(none);

    for (const analyzer of analyzers) {
      const option = document.createElement("option");
      option.value = analyzer.id;
      option.textContent = analyzer.name;
      if (owner?.id === analyzer.id) option.selected = true;
      select.append(option);
    }

    select.addEventListener("change", () => {
      this.callbacks.onAssignAnalyzer(node.id, select.value || null);
    });

    field.append(label, select);
    return field;
  }

  /**
   * The reference's per-property audio-impact rows, next to the analyzer binding.
   *
   * Decompiled wiring (`main~412a0a1c` module 682, `AudioImpact.updateAutomation`):
   * the row samples `audioAnalyzerData[this.audioAnalyzer]`, normalises
   * `hypot(...bands)` by the project's `audioImpact.max`, maps that onto
   * `minValue..maxValue` and the manager writes the result to every controller in
   * the row's `connections` (`getUpdates`).
   *
   * An item's own analyzer binding only selects the bands it reads internally -
   * `Image.update` uses them for the vignette (`average(...) * brightnessMultiplier`)
   * - so an item cannot move or zoom from the binding alone. The create button
   * mirrors the reference's own shipped background pulse (`terminal.json`:
   * `scale:x`+`scale:y`, 1 -> 1.05, sensitivity 1, smoothing 0.95). A
   * *background* item gets that row automatically when an analyzer is chosen;
   * every other item has to ask for it.
   */
  private buildAudioImpactRows(node: AnyNode): HTMLElement[] {
    const rows = this.automationRows.filter((row) => row.type === "audioImpact");
    const out: HTMLElement[] = [];

    for (const row of rows) {
      const field = document.createElement("div");
      field.className = "field audio-impact";
      const label = document.createElement("label");
      const axis = propertyLabel(row.propertyId);
      label.textContent = "Audio impact";
      label.title = `${axis}: the range this item's analyzer sweeps`;
      const range = document.createElement("div");
      range.className = "range-pair";
      const commit = (change: Partial<{ from: number; to: number }>): void => {
        if (!row.id || !this.callbacks.onEditAudioImpact) return;
        this.callbacks.onEditAudioImpact(row.id, change);
      };
      const makeInput = (
        value: number,
        key: "from" | "to",
        title: string,
      ): HTMLInputElement => {
        const input = document.createElement("input");
        input.type = "number";
        input.className = "text";
        input.step = "any";
        input.value = trimNumber(value);
        input.title = `${axis} ${title}`;
        input.addEventListener("change", () => {
          const next = Number(input.value);
          if (!Number.isFinite(next)) {
            input.value = trimNumber(value);
            return;
          }
          commit({ [key]: next } as Partial<{ from: number; to: number }>);
        });
        return input;
      };
      if (row.impact) {
        const readout = document.createElement("span");
        readout.className = "value";
        readout.textContent = `${axis} ${trimNumber(row.impact.from)} -> ${trimNumber(row.impact.to)}`;
        range.append(
          readout,
          makeInput(row.impact.from, "from", "from"),
          makeInput(row.impact.to, "to", "to"),
        );
      } else {
        const readout = document.createElement("span");
        readout.className = "value";
        readout.textContent = axis;
        range.append(readout);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon";
      remove.title = "Remove audio impact";
      remove.append(icon("close", 12));
      remove.addEventListener("click", () => {
        if (row.id) this.callbacks.onRemoveAudioImpact?.(row.id);
      });
      field.append(label, range, remove);
      out.push(field);

      // Sensitivity and smoothing live on the same automation (module 682:
      // `hypot(bands) * sensitivity / max`, then the exponential smoother). They
      // were previously not editable anywhere in the inspector.
      if (row.impact) {
        const response = document.createElement("div");
        response.className = "field audio-impact";
        const responseLabel = document.createElement("label");
        responseLabel.textContent = "Response";
        responseLabel.title = "Sensitivity scales the analyzer reading; smoothing is the per-frame blend";
        const pair = document.createElement("div");
        pair.className = "range-pair";
        const responseInput = (
          value: number | undefined,
          key: "sensitivity" | "smoothing",
          title: string,
          min: number,
        ): HTMLInputElement => {
          const input = document.createElement("input");
          input.type = "number";
          input.className = "text";
          input.step = "0.05";
          input.min = String(min);
          input.value = value === undefined ? "" : trimNumber(value);
          input.title = title;
          input.addEventListener("change", () => {
            const next = Number(input.value);
            if (!Number.isFinite(next) || !row.id) {
              input.value = value === undefined ? "" : trimNumber(value);
              return;
            }
            this.callbacks.onEditAudioImpact?.(row.id, { [key]: next } as Partial<{
              sensitivity: number;
              smoothing: number;
            }>);
          });
          return input;
        };
        pair.append(
          responseInput(row.impact.sensitivity, "sensitivity", "Sensitivity", 0),
          responseInput(row.impact.smoothing, "smoothing", "Smoothing (0-1)", 0),
        );
        response.append(responseLabel, pair);
        out.push(response);
      }
    }

    // One click creates the scale row; a second button would duplicate the same
    // controller pair, so it disappears once the row exists. It also covers an
    // item that is already bound (the add-item default), which never went
    // through the None -> analyzer transition that creates the row.
    const hasScaleRow = rows.some((row) => row.propertyId === "transform.scaleX");
    const owner = analyzerOf(this.analyzers, node.id);
    if (owner && !hasScaleRow && node.objectMapping.has("transform.scaleX") && this.callbacks.onAddAudioImpact) {
      const field = document.createElement("div");
      field.className = "field";
      const add = document.createElement("button");
      add.type = "button";
      add.className = "mini audio-impact-add";
      add.append(icon("add", 12), document.createTextNode("React to audio"));
      add.title =
        "Add an Audio Impact automation that pulses this item's scale with its analyzer";
      add.addEventListener("click", () => this.callbacks.onAddAudioImpact?.(node.id));
      field.append(add);
      out.push(field);
    }
    return out;
  }

  /**
   * Composition layers carry an `audioAnalyzer` controller in the reference
   * inspector (`Fa.b(container, "audioAnalyzer")` in the editor bundle), so a
   * layer can pick the analyzer that its contents inherit. One analyzer per
   * layer, same as one per item.
   */
  private buildCompositionLayerAnalyzerRow(
    node: AnyNode,
    analyzers: readonly Analyzer[],
  ): HTMLElement {
    const field = document.createElement("div");
    field.className = "field";

    const label = document.createElement("label");
    label.textContent = "Audio analyzer";

    const layer = node as AnyNode & {
      audioAnalyzer?: string | null;
      compositionLayerId?: string | null;
    };
    const value = layer.audioAnalyzer ?? null;
    const select = document.createElement("select");
    select.title = "Audio analyzer driving this layer's contents";
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "None";
    if (!value) none.selected = true;
    select.append(none);

    for (const analyzer of analyzers) {
      const option = document.createElement("option");
      option.value = analyzer.id;
      option.textContent = analyzer.name;
      if (value === analyzer.id) option.selected = true;
      select.append(option);
    }

    select.addEventListener("change", () => {
      if (layer.compositionLayerId) {
        this.callbacks.onAssignCompositionLayerAnalyzer(
          layer.compositionLayerId,
          select.value || null,
        );
      }
    });

    field.append(label, select);
    return field;
  }

  /**
   * Reference Audio Impact controllers for a Spectrum item.
   *
   * The reference selects the automation's target in its "Add automation"
   * dialog and then shows the automation itself with these rows. We keep the
   * rows on the item so the reaction is discoverable next to the analyser,
   * and expose the target as the `Drives` row. Everything else (labels,
   * ranges, units, enable semantics) follows module 682 one for one.
   */
  private buildSpectrumReaction(
    node: SpectrumNode,
    reaction: SpectrumReactionView | null,
    analyzers?: readonly Analyzer[],
  ): HTMLElement {
    const section = document.createElement("section");
    section.className = "group spectrum-reaction";
    if (!this.open.has("reaction")) section.classList.add("collapsed");

    const headRow = document.createElement("div");
    headRow.className = "group-head-row";

    const head = document.createElement("button");
    head.className = "group-head";
    const twist = document.createElement("span");
    twist.className = "twist";
    twist.append(icon(this.open.has("reaction") ? "expand_more" : "chevron_right", 14));
    head.append(twist, document.createTextNode("Audio impact"));

    const actions = document.createElement("div");
    actions.className = "group-actions";
    if (reaction) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon";
      remove.title = "Remove audio impact";
      remove.append(icon("delete", 14));
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        this.callbacks.onSpectrumReaction?.(node.id, { kind: "remove" });
      });
      actions.append(remove);
    }
    headRow.append(head, actions);
    head.addEventListener("click", () => {
      if (this.open.has("reaction")) this.open.delete("reaction");
      else this.open.add("reaction");
      section.classList.toggle("collapsed");
      twist.replaceChildren(
        icon(this.open.has("reaction") ? "expand_more" : "chevron_right", 14),
      );
    });

    const body = document.createElement("div");
    body.className = "group-body";

    const field = (label: string, control: HTMLElement, tooltip?: string): HTMLElement => {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const name = document.createElement("label");
      name.textContent = label;
      if (tooltip) name.title = tooltip;
      wrap.append(name, control);
      return wrap;
    };
    const number = (
      value: number,
      min: number,
      max: number,
      step: number,
      onCommit: (value: number) => void,
      disabled = false,
    ): HTMLInputElement => {
      const input = document.createElement("input");
      input.type = "number";
      input.min = String(min);
      input.max = String(max);
      input.step = String(step);
      input.value = String(Number(value.toFixed(4)));
      input.disabled = disabled;
      input.addEventListener("change", () => {
        const next = Number(input.value);
        if (!Number.isFinite(next)) return;
        const clamped = Math.min(max, Math.max(min, next));
        input.value = String(clamped);
        onCommit(clamped);
      });
      return input;
    };
    const checkbox = (checked: boolean, onCommit: (value: boolean) => void): HTMLInputElement => {
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = checked;
      input.addEventListener("change", () => onCommit(input.checked));
      return input;
    };
    const change = (next: SpectrumReactionChange): void => {
      this.callbacks.onSpectrumReaction?.(node.id, next);
    };

    body.append(
      field(
        "Enabled",
        checkbox(reaction?.enabled ?? false, (enabled) =>
          change({ kind: "enabled", enabled }),
        ),
        "Turns the Audio Impact automation on or off; its settings are kept",
      ),
    );

    if (!reaction) {
      const hint = document.createElement("p");
      hint.className = "panel-note";
      hint.textContent =
        "Enable to add the reference's Audio Impact automation to this item.";
      body.append(hint);
      section.append(headRow, body);
      return section;
    }

    // `Drives` is the picker for the automation's target. The reference picks
    // it when the automation is created; the row labels are the reference's
    // own transform controllers.
    const drives = document.createElement("select");
    for (const property of SPECTRUM_REACTION_PROPERTIES) {
      const option = document.createElement("option");
      option.value = property.id;
      option.textContent = property.label;
      if (property.id === reaction.propertyId) option.selected = true;
      drives.append(option);
    }
    drives.addEventListener("change", () => {
      change({ kind: "property", propertyId: drives.value as SpectrumReactionView["propertyId"] });
    });
    body.append(field("Drives", drives, "The transform controller this reaction animates"));

    if (analyzers && analyzers.length > 0) {
      const analyzer = document.createElement("select");
      const none = document.createElement("option");
      none.value = "";
      none.textContent = "None";
      if (!reaction.analyzerId) none.selected = true;
      analyzer.append(none);
      for (const option of analyzers) {
        const entry = document.createElement("option");
        entry.value = option.id;
        entry.textContent = option.name;
        if (option.id === reaction.analyzerId) entry.selected = true;
        analyzer.append(entry);
      }
      analyzer.addEventListener("change", () => {
        change({ kind: "analyzer", analyzerId: analyzer.value });
      });
      body.append(
        field(
          "Audio analyzer",
          analyzer,
          "The audio analyzer being used determines how this spectrum layer should react to audio",
        ),
      );
    }

    const readout = document.createElement("span");
    readout.className = "value";
    readout.textContent = reaction.value.toFixed(2);
    body.append(
      field(
        "Value",
        readout,
        "The output value of the audio impact automation, rendered live (only while playing). Only for reference, not editable or terribly accurate",
      ),
    );

    const impact = reaction.impact;
    const display = (controller: number): number =>
      reactionDisplayValue(reaction.propertyId, controller);
    const store = (value: number): number =>
      reactionControllerValue(reaction.propertyId, value);
    const setImpact = (patch: Partial<SpectrumReactionView["impact"]>): void =>
      change({ kind: "impact", patch });

    body.append(
      field(
        "Min value",
        number(display(impact.min), -1000, 1000, 0.01, (value) =>
          setImpact({ min: store(value) }),
        ),
      ),
      field(
        "Max value",
        number(display(impact.max), -1000, 1000, 0.01, (value) =>
          setImpact({ max: store(value) }),
        ),
      ),
      field(
        "Lower limit",
        number(impact.floor, 0, 5000, 1, (value) => setImpact({ floor: value })),
        "The value below which there won't be a reaction",
      ),
      field(
        "Upper limit",
        number(impact.ceiling, 0, 3000, 1, (value) => setImpact({ ceiling: value })),
        "The value above which there won't be a reaction",
      ),
      field(
        "Sensitivity",
        number(impact.sensitivity, 0, 1, 0.01, (value) =>
          setImpact({ sensitivity: value }),
        ),
      ),
      field(
        "Smoothing",
        number(impact.smoothing, 0, 1, 0.01, (value) => setImpact({ smoothing: value })),
      ),
      field(
        "Cumulative",
        checkbox(impact.cumulative, (value) => setImpact({ cumulative: value })),
      ),
      field(
        "Delta smooth",
        checkbox(impact.deltaSmoothing === true, (value) =>
          setImpact({ deltaSmoothing: value }),
        ),
        "Use delta smoothing",
      ),
      field(
        "Delta amount",
        number(
          impact.deltaDecay ?? 0.01,
          0,
          1,
          0.01,
          (value) => setImpact({ deltaDecay: value }),
          impact.deltaSmoothing !== true,
        ),
        "Decays (or increases) by delta_amt * maxValue each frame",
      ),
      field(
        "Delta threshold",
        number(
          impact.deltaThreshold ?? 0,
          0,
          1,
          0.01,
          (value) => setImpact({ deltaThreshold: value }),
          impact.deltaSmoothing !== true,
        ),
        "Changes smaller than this decay instead of being followed",
      ),
    );

    section.append(headRow, body);
    return section;
  }

  private buildGroup(
    container: ContainerDescriptor,
    children: HTMLElement[],
  ): HTMLElement {
    const section = document.createElement("section");
    section.className = "group";
    if (!this.open.has(container.id)) section.classList.add("collapsed");

    const head = document.createElement("button");
    head.className = "group-head";
    const twist = document.createElement("span");
    twist.className = "twist";
    twist.append(icon(this.open.has(container.id) ? "expand_more" : "chevron_right", 14));
    head.append(twist, document.createTextNode(container.label));
    head.addEventListener("click", () => {
      if (this.open.has(container.id)) this.open.delete(container.id);
      else this.open.add(container.id);
      section.classList.toggle("collapsed");
      twist.replaceChildren(
        icon(this.open.has(container.id) ? "expand_more" : "chevron_right", 14),
      );
    });

    const body = document.createElement("div");
    body.className = "group-body";
    body.append(...children);

    section.append(head, body);
    return section;
  }

  private buildField(controller: PropertyDescriptor): HTMLElement {
    const field = this.buildFieldControl(controller);
    const constrained = controller.constraint ? !controller.constraint() : false;
    if (controller.disabled || constrained) {
      // Present for layout parity, but the reference greys it out too.
      field.classList.add("field-disabled");
      field.title = controller.disabled
        ? "Not implemented in Studio yet"
        : (controller.tooltip ?? "");
      field.querySelectorAll("input, select, button").forEach((el) => {
        (el as HTMLInputElement).disabled = true;
      });
    } else if (controller.tooltip) {
      field.title = controller.tooltip;
    }
    return field;
  }

  private buildFieldControl(controller: PropertyDescriptor): HTMLElement {
    const field = document.createElement("div");
    field.className = "field";

    const label = document.createElement("label");
    label.textContent = controller.label;
    label.title = controller.tooltip ?? controller.id;

    if (controller.kind === PropertyKind.Range) {
      // Reference RANGE controller: one row with a low and a high handle.
      const [low, high] = controller.readRange?.() ?? [0, 100];
      const pair = document.createElement("div");
      pair.className = "range-pair";

      const lowInput = document.createElement("input");
      lowInput.type = "number";
      lowInput.className = "text";
      lowInput.min = String(controller.min ?? 0);
      lowInput.max = String(controller.max ?? 100);
      lowInput.step = String(controller.step ?? 1);
      lowInput.value = String(low);
      lowInput.title = `${controller.label} low`;

      const highInput = document.createElement("input");
      highInput.type = "number";
      highInput.className = "text";
      highInput.min = String(controller.min ?? 0);
      highInput.max = String(controller.max ?? 100);
      highInput.step = String(controller.step ?? 1);
      highInput.value = String(high);
      highInput.title = `${controller.label} high`;

      const commit = (): void => {
        const nextLow = Number(lowInput.value);
        const nextHigh = Number(highInput.value);
        if (!Number.isFinite(nextLow) || !Number.isFinite(nextHigh)) return;
        const before = controller.readRange?.() ?? [nextLow, nextHigh];
        controller.writeRange?.(nextLow, nextHigh);
        const [settledLow, settledHigh] = controller.readRange?.() ?? [nextLow, nextHigh];
        lowInput.value = String(settledLow);
        highInput.value = String(settledHigh);
        this.callbacks.onEdit(
          controller.id,
          controller.label,
          settledHigh,
          false,
          before,
        );
      };
      lowInput.addEventListener("change", commit);
      highInput.addEventListener("change", commit);

      pair.append(lowInput, highInput);
      field.append(label, pair);
      return field;
    }

    if (controller.kind === PropertyKind.Slider) {
      const input = document.createElement("input");
      input.type = "range";
      input.min = String(controller.min ?? 0);
      input.max = String(controller.max ?? 100);
      input.step = String(controller.step ?? 0.01);
      input.value = String(Number(controller.read()));

      const value = document.createElement("span");
      value.className = "value";
      const paint = () => {
        const raw = Number(controller.read());
        value.textContent = `${raw.toFixed(controller.step && controller.step >= 1 ? 0 : 2)}${controller.unit ?? ""}`;
        input.value = String(raw);
      };
      paint();

      input.addEventListener("input", () => {
        const before = Number(controller.read());
        controller.write(Number(input.value));
        paint();
        this.callbacks.onEdit(
          controller.id,
          controller.label,
          Number(input.value),
          controller.animatable,
          before,
        );
      });
      field.append(label, input, value);

      if (controller.animatable) {
        const key = document.createElement("button");
        key.className = `icon${this.keyed.has(controller.id) ? " on" : ""}`;
        key.title = `Keyframe ${controller.label}`;
        key.append(icon("keyframe", 12));
        key.addEventListener("click", () => this.callbacks.onKeyframe(controller.id));
        field.append(key);
      }
      return field;
    }

    if (controller.kind === PropertyKind.File) {
      // Reference image rows: a thumbnail of the current image plus upload and
      // remove actions, so preset artwork is visible and replaceable.
      const preview = this.callbacks.imagePreview?.(controller.id) ?? null;
      const picker = document.createElement("div");
      picker.className = "file-picker";

      const thumb = document.createElement("button");
      thumb.type = "button";
      thumb.className = "file-thumb";
      thumb.title = preview ? "Replace image" : "Upload image";
      if (preview) {
        if (isVideoSource(preview)) {
          const video = document.createElement("video");
          video.src = preview;
          video.muted = true;
          video.playsInline = true;
          video.preload = "metadata";
          thumb.append(video);
        } else {
          const img = document.createElement("img");
          img.src = preview;
          img.alt = "";
          thumb.append(img);
        }
      } else {
        thumb.append(icon("image", 15));
      }
      thumb.addEventListener("click", () => this.callbacks.onPickFile(controller.id));

      const actions = document.createElement("div");
      actions.className = "file-actions";
      if (preview) {
        const name = document.createElement("span");
        name.className = "file-name";
        name.textContent = fileNameOf(preview);
        name.title = preview;
        actions.append(name);
      }
      // Reference split: the File row shows the current image, the Upload row
      // carries the actions. Both thumbnails open the picker.
      if (!controller.id.endsWith("imageFile")) {
        const upload = document.createElement("button");
        upload.type = "button";
        upload.className = "mini";
        upload.textContent = preview ? "Replace" : "Upload";
        upload.addEventListener("click", () => this.callbacks.onPickFile(controller.id));
        actions.append(upload);

        if (preview && this.callbacks.onClearImage) {
          const clear = document.createElement("button");
          clear.type = "button";
          clear.className = "mini";
          clear.textContent = "Remove";
          clear.addEventListener("click", () => this.callbacks.onClearImage?.(controller.id));
          actions.append(clear);
        }
      }

      picker.append(thumb, actions);
      field.append(label, picker);
      return field;
    }

    if (controller.kind === PropertyKind.Color) {
      const input = document.createElement("input");
      input.type = "color";
      input.className = "color";
      input.value = String(controller.read() ?? "#ffffff");
      input.addEventListener("input", () => {
        const before = String(controller.read() ?? "#ffffff");
        controller.write(input.value);
        this.callbacks.onEdit(controller.id, controller.label, input.value, false, before);
      });
      field.append(label, input);
      return field;
    }

    if (controller.kind === PropertyKind.Text) {
      const input = document.createElement("input");
      input.type = "text";
      input.className = "text";
      input.value = String(controller.read() ?? "");
      input.addEventListener("change", () => {
        const before = String(controller.read() ?? "");
        controller.write(input.value);
        this.callbacks.onEdit(controller.id, controller.label, input.value, false, before);
      });
      field.append(label, input);
      return field;
    }

    if (controller.kind === PropertyKind.Boolean) {
      field.classList.add("toggle");
      const button = document.createElement("button");
      button.className = `switch${controller.read() ? " on" : ""}`;
      button.addEventListener("click", () => {
        const before = Boolean(controller.read());
        const next = !before;
        controller.write(next);
        button.classList.toggle("on", next);
        this.callbacks.onEdit(controller.id, controller.label, next, false, before);
      });
      field.append(label, button);
      return field;
    }

    if (controller.kind === PropertyKind.ImageGrid) {
      field.classList.add("image-grid");
      const column = document.createElement("div");
      column.className = "image-grid-column";

      const grid = document.createElement("div");
      grid.className = "image-grid-options";
      for (const option of controller.options ?? []) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `image-option${String(controller.read()) === option ? " active" : ""}`;
        button.style.backgroundImage = `url("${option}")`;
        button.title = option.split("/").pop() ?? option;
        button.addEventListener("click", () => {
          const before = String(controller.read() ?? "");
          controller.write(option);
          grid.querySelectorAll(".image-option").forEach((entry) => entry.classList.remove("active"));
          button.classList.add("active");
          this.callbacks.onEdit(controller.id, controller.label, option, false, before);
        });
        grid.append(button);
      }
      column.append(grid);

      // The reference's grid component folds the uploader into the same
      // control, keyed by controller id (`["particleImage"]` in module 2606).
      if (controller.id === "particleImage" || controller.id === "appearance.particleImage") {
        const upload = document.createElement("button");
        upload.type = "button";
        upload.className = "image-upload";
        upload.textContent = "Upload";
        upload.addEventListener("click", () => this.callbacks.onPickFile(controller.id));
        column.append(upload);
      }

      field.append(label, column);
      return field;
    }

    if (controller.kind === PropertyKind.CustomPath) {
      field.classList.add("custom-path");
      const column = document.createElement("div");
      column.className = "custom-path-column";
      const points = parseCustomPath(String(controller.read()));
      const commit = (): void => {
        const before = String(controller.read() ?? "");
        const value = serializeCustomPath(points);
        controller.write(value);
        this.callbacks.onEdit(controller.id, controller.label, value, false, before);
      };

      points.forEach((point, index) =>
        column.append(
          this.buildPathRow(point, index, commit, () => {
            points.splice(index, 1);
            commit();
          }),
        ),
      );

      const add = document.createElement("button");
      add.type = "button";
      add.className = "custom-path-add";
      add.textContent = "+ Point";
      add.addEventListener("click", () => {
        const last = points[points.length - 1];
        points.push({
          type: "lineTo",
          invert: false,
          reverse: false,
          x: last?.x ?? 0,
          y: last?.y ?? 0,
          cx: 0,
          cy: 0,
        });
        commit();
      });
      column.append(add);

      field.append(label, column);
      return field;
    }

    if (controller.kind === PropertyKind.Analyzer) {
      const select = document.createElement("select");
      const current = String(controller.read());
      let matched = false;
      for (const analyzer of this.analyzers) {
        const item = document.createElement("option");
        item.value = analyzer.id;
        item.textContent = analyzer.name;
        if (current === analyzer.id) {
          item.selected = true;
          matched = true;
        }
        select.append(item);
      }
      if (!matched) {
        const item = document.createElement("option");
        item.value = current;
        item.textContent = current || "None";
        item.selected = true;
        select.prepend(item);
      }
      select.addEventListener("change", () => {
        const before = String(controller.read() ?? "");
        controller.write(select.value);
        // The reference has no separate ownership row: this control is the
        // item's analyzer binding.
        if (this.nodeId) this.callbacks.onAssignAnalyzer(this.nodeId, select.value || null);
        this.callbacks.onEdit(controller.id, controller.label, select.value, false, before);
      });
      field.append(label, select);
      return field;
    }

    const select = document.createElement("select");
    for (const option of controller.options ?? []) {
      const item = document.createElement("option");
      item.value = option;
      item.textContent = option;
      if (String(controller.read()) === option) item.selected = true;
      select.append(item);
    }
    select.addEventListener("change", () => {
      const before = String(controller.read() ?? "");
      controller.write(select.value);
      this.callbacks.onEdit(controller.id, controller.label, select.value, false, before);
    });
    field.append(label, select);
    return field;
  }

  /**
   * One row of the reference's `CUSTOM_PATH` editor (module `141`): remove,
   * type, invert/quad/flip toggles, and the point's numbers. The reference keeps
   * x/y read-only and drags vertices on the stage; we expose them as inputs so
   * the path is editable without that overlay.
   */
  private buildPathRow(
    point: CustomPathPoint,
    index: number,
    commit: () => void,
    removePoint: () => void,
  ): HTMLElement {
    const row = document.createElement("div");
    row.className = "custom-path-row";

    const head = document.createElement("div");
    head.className = "custom-path-head";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "custom-path-remove";
    remove.title = "Remove";
    remove.append(icon("close", 12));
    remove.addEventListener("click", removePoint);
    head.append(remove);

    if (index === 0) {
      const first = document.createElement("span");
      first.className = "custom-path-type";
      first.textContent = "moveTo";
      head.append(first);
    } else {
      const type = document.createElement("select");
      type.className = "custom-path-type";
      for (const value of ["lineTo", "quadTo", "arcTo"] as const) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (point.type === value) option.selected = true;
        type.append(option);
      }
      type.addEventListener("change", () => {
        point.type = type.value as CustomPathPoint["type"];
        commit();
      });
      head.append(type);
    }

    const toggle = (label: string, title: string, on: boolean, action: () => void): void => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `custom-path-toggle${on ? " on" : ""}`;
      button.title = title;
      button.textContent = label;
      button.addEventListener("click", () => {
        action();
        commit();
      });
      head.append(button);
    };
    toggle("I", "Invert", point.invert, () => {
      point.invert = !point.invert;
    });
    toggle("Q", "Quad to", point.reverse, () => {
      point.reverse = !point.reverse;
    });
    if (point.type === "arcTo") {
      toggle("F", "Flip arc", point.cy === -1, () => {
        point.cy = point.cy <= 0 ? 1 : -1;
      });
    }

    const values = document.createElement("div");
    values.className = "custom-path-values";
    const number = (
      label: string,
      value: number,
      step: number,
      apply: (next: number) => void,
    ): void => {
      const wrap = document.createElement("label");
      wrap.className = "custom-path-number";
      wrap.textContent = label;
      const input = document.createElement("input");
      input.type = "number";
      input.step = String(step);
      input.value = String(value);
      input.addEventListener("change", () => {
        const next = Number(input.value);
        if (!Number.isFinite(next)) return;
        apply(next);
        commit();
      });
      wrap.append(input);
      values.append(wrap);
    };
    number("x", point.x, 0.05, (v) => {
      point.x = v;
    });
    number("y", point.y, 0.05, (v) => {
      point.y = v;
    });
    if (point.type === "arcTo") {
      number("r", point.cx, 0.05, (v) => {
        point.cx = v;
      });
    } else if (point.type === "quadTo") {
      number("cx", point.cx, 0.05, (v) => {
        point.cx = v;
      });
      number("cy", point.cy, 0.05, (v) => {
        point.cy = v;
      });
    }

    row.append(head, values);
    return row;
  }
}
