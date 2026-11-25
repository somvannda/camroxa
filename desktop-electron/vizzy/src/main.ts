import { AudioBus, BufferSource, SpectrumAnalyser } from "./audio/spectrum";
import { preloadVizzyAnalyser } from "./audio/vizzy-analyzer";
import { GroundNode, LayerNode, LogoNode, MediaNode, NoiseNode, ParticlesNode, PrimitiveNode, AnimatedTextNode, AudioWaveNode, BasicSpectrumBarsNode, ButterchurnNode, ConfettiNode, InstancedParticleSystemNode, LineBedNode, LyricsNode, ModelNode, ParticleSystemNode, ParticleTimeLineNode, SphericalFieldNode, ParticleLinesNode, ProgressBarNode, ShaderItemNode, SkiaTextNode, SkottieNode, VideoNode, SpectrumNode, createNode, type AnyNode } from "./domain/nodes";
import {
  deleteUserPreset,
  saveUserPreset,
  TRAP_MOTION_PRESET,
  updateUserPreset,
  type Preset,
} from "./domain/presets";
import {
  applyParticlePreset,
  deleteUserParticlePreset,
  readParticleParams,
  saveUserParticlePreset,
  updateUserParticlePreset,
} from "./domain/particle-presets";
import {
  scaleMultiplierFromReference,
  scaleMultiplierToReference,
} from "./domain/reference-scale";
import { AssetStore, createProject, sampleAutomation, type MediaAsset } from "./domain/project";
import { REFERENCE_VALUE_SCALE } from "./audio/analyzer-bank";
import {
  NodeKind,
  PropertyKind,
  newId,
  type Automation,
  type AutomationGroup,
  type AudioImpactSettings,
  type Easing,
  type Keyframe,
} from "./domain/types";
import { Formula } from "./domain/formula";
import { EASING_OPTIONS } from "./domain/easing";
import { EFFECT_CATALOGUE, EFFECT_CATEGORIES, GLOBAL_TARGET, createEffect, definitionsFor, type EffectInstance } from "./domain/effects";
import { createAnalyzer, assignUser, detachUser, restoreOwnership, snapshotOwnership, type Analyzer } from "./domain/analyzers";
import { analyzerControllerSetups } from "./domain/analyzer-controllers";
import { AudioImpactEngine } from "./domain/audio-impact";
import { createSpectrumLayer, type SpectrumLayer } from "./domain/spectrum-layers";
import {
  DEFAULT_SPECTRUM_REACTION_PROPERTY,
  defaultSpectrumReactionImpact,
  isSpectrumReactionProperty,
  reactionControllerValue,
  spectrumReactionValue,
  type SpectrumReactionChange,
  type SpectrumReactionProperty,
  type SpectrumReactionView,
} from "./domain/spectrum-reaction";
import { shiftHexColor } from "./domain/colors";
import { effectThumbnail } from "./domain/effect-thumbnails";
import { Coalescer, History } from "./domain/undo";
import { applyProjectExport, applySpectrumExport, type ImportReport } from "./domain/import-project";
import {
  isProjectSnapshot,
  restoreProject,
  serializeProject,
  type ProjectSnapshot,
} from "./domain/project-snapshot";
import { Exporter, type ExportCodec, type ExportResult } from "./export/exporter";
import { ReferenceWasmExporter } from "./export/reference-encoder";
import { WebCodecsExporter } from "./export/webcodecs-exporter";
import { StageRenderer } from "./renderer/renderer";
import { Inspector, type InspectorAutomationInfo } from "./ui/inspector";
import { TimelineView } from "./ui/timeline";
import { hydrateIcons, icon, type IconName } from "./ui/icons";

const $ = <T extends HTMLElement>(selector: string): T => document.querySelector(selector) as T;

/* ------------------------------------------------------------------ */
/* Session log (Help > Export current/last log)                        */
/* ------------------------------------------------------------------ */

type LogLevel = "log" | "info" | "warn" | "error";
interface LogEntry {
  at: string;
  level: LogLevel;
  text: string;
}

const LOG_LIMIT = 400;
const logEntries: LogEntry[] = [];

function logText(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

for (const level of ["log", "info", "warn", "error"] as const) {
  const original = console[level].bind(console);
  console[level] = (...args: unknown[]) => {
    logEntries.push({ at: new Date().toISOString(), level, text: args.map(logText).join(" ") });
    if (logEntries.length > LOG_LIMIT) logEntries.splice(0, logEntries.length - LOG_LIMIT);
    original(...args);
  };
}

window.addEventListener("beforeunload", () => {
  try {
    localStorage.setItem("studio:lastLog", JSON.stringify(logEntries.slice(-200)));
  } catch {
    /* storage may be unavailable */
  }
});

hydrateIcons();

// Track occupies 30% of the editor by default (reference Mosaic split) and is
// resizable by dragging its top edge.
{
  const splitter = document.createElement("div");
  splitter.id = "track-splitter";
  $("#timeline-wrap").prepend(splitter);
  const app = $("#app");
  const saved = Number(localStorage.getItem("studio:trackSize"));
  if (Number.isFinite(saved) && saved > 80) {
    app.style.setProperty("--track-size", `${saved}px`);
  }
  splitter.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = $("#timeline-wrap").getBoundingClientRect().height;
    const move = (moveEvent: PointerEvent) => {
      const next = Math.min(
        window.innerHeight * 0.7,
        Math.max(120, startHeight + (startY - moveEvent.clientY)),
      );
      app.style.setProperty("--track-size", `${next}px`);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      localStorage.setItem(
        "studio:trackSize",
        String(Math.round($("#timeline-wrap").getBoundingClientRect().height)),
      );
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
  });
}

// Sidebar splitters, mirroring Mosaic's draggable panes. Sizes persist and are
// ignored while the layout is locked.
{
  const app = $("#app");
  const root = document.documentElement;
  const saveSizes = (): void => {
    localStorage.setItem(
      "studio:panelSizes",
      JSON.stringify({
        compositor: Math.round($("#compositor").getBoundingClientRect().width),
        inspector: Math.round($("#inspector").getBoundingClientRect().width),
      }),
    );
  };
  const attach = (handle: HTMLElement, side: "left" | "right"): void => {
    handle.addEventListener("pointerdown", (event) => {
      if ($("#app").classList.contains("layout-locked")) return;
      event.preventDefault();
      const startX = event.clientX;
      const startWidth =
        side === "left"
          ? $("#compositor").getBoundingClientRect().width
          : $("#inspector").getBoundingClientRect().width;
      const move = (moveEvent: PointerEvent) => {
        const delta = moveEvent.clientX - startX;
        const inverted = side === "right" && $("#app").dataset.layout === "2";
        const next =
          side === "left"
            ? Math.min(520, Math.max(160, startWidth + delta))
            : Math.min(460, Math.max(180, startWidth + (inverted ? delta : -delta)));
        root.style.setProperty(side === "left" ? "--compositor" : "--inspector", `${next}px`);
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        saveSizes();
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up, { once: true });
    });
  };
  attach($("#split-left"), "left");
  attach($("#split-right"), "right");
  void app;
}

const project = createProject();
const assets = new AssetStore();

/**
 * Assets live in the store for rendering and in `project.assets` for snapshots.
 * Keep both in sync so uploaded artwork survives save/open and a reload.
 */
function registerAsset(asset: MediaAsset): MediaAsset {
  if (!project.assets.some((entry) => entry.id === asset.id)) project.assets.push(asset);
  return asset;
}
const spectrum = new SpectrumAnalyser();
const audio = new AudioBus();
const history = new History();
const coalescer = new Coalescer();
const impactEngine = new AudioImpactEngine();
const exporter = new Exporter();

let selectedId: string | null = null;
/** Layers are their own objects, selectable like items (reference tree shape). */
let selectedLayerId: string | null = null;
/** Analyzers are objects too: selecting one shows its controllers in the inspector. */
let selectedAnalyzerId: string | null = null;
/** Reference multi-select: Ctrl/Cmd-click adds items to the selection. */
let multiSelection = new Set<string>();
/** Reference object selection also covers automations (they are objects). */
let selectedAutomations = new Set<string>();
let timelineA11ySignature = "";
let timelineReady = false;
/** Reference `objectEditView`: the inspector edits controllers or automations. */
let inspectorAutomationView = false;
const layerNodes = new Map<string, LayerNode>();
// Restore the playhead across reloads (Vite HMR reloads the studio on edits).
// Without this, a reload dropped the preview back to 0, where a track's silent
// intro makes audio-driven items look frozen.
let time = Math.max(0, Number(sessionStorage.getItem("studio:time")) || 0);
let lastSavedTime = -1;
/**
 * Playhead of the last automation pass. The reference skips automation updates
 * on a rerender frame (`Automations.update(e, t) { if (e.rerender) return; … }`,
 * vizzy `main~412a0a1c` module 682 caller), so a paused editor that keeps
 * re-rendering the same frame must not advance cumulative `AudioImpact` rows.
 * Tracking the time is the equivalent gate: playback advances it every frame,
 * a seek changes it once, and a paused re-render leaves it untouched.
 */
let lastAutomationTime = -1;
let lastVolume = 100;
let playing = false;
let loop = true;
let zoom = 1;
/** Reference easing names for keyframes, plus the legacy hold mode. */
const KEYFRAME_EASINGS: readonly string[] = [...EASING_OPTIONS, "hold"];

let displaySeconds = localStorage.getItem("studio:displaySeconds") !== "0";
let is3D = false;
/** Reference Ctrl+H: hide shy objects (default) or reveal them. */
let hideShyLayers = true;
let lastFrame = performance.now();
let audioBuffer: AudioBuffer | null = null;
/** The decoded track after the reference's audio processing graph. */
let processedAudioBuffer: AudioBuffer | null = null;
/** The decoded track before the reference's processing graph is applied. */
let decodedAudioBuffer: AudioBuffer | null = null;
let audioTrackName = "";
let audioProcessToken = 0;
let audioLoadToken = 0;
/** Cancels a stale audio-impact scan (new track/load or a new scan). */
let impactScanToken = 0;
/** In-flight impact scan, awaited by exports so the normaliser is final. */
let impactScanPromise: Promise<void> | null = null;
/**
 * Track key the normaliser was last scanned for. A scan that runs before any
 * audio-impact row exists returns without a value, so a row created later has to
 * be able to ask for one more scan - once per track, not once per frame.
 */
let impactNormaliserScannedFor = "";
/** Peak envelope for the timeline's audio band. */
let waveformPeaks: Float32Array | null = null;
let analyserAudioKey = "";
let audioFile: { name: string; bytes: Uint8Array } | null = null;

const stageCanvas = $<HTMLCanvasElement>("#stage");
const renderer = new StageRenderer(stageCanvas, project, assets, spectrum);

const treeRoot = $("#tree");
const inspectorBody = $("#inspector-body");
const inspectorTitle = $("#inspector-title");
const codeEditorText = $<HTMLTextAreaElement>("#code-editor-text");
const codeApply = $<HTMLButtonElement>("#code-apply");
const codeClose = $<HTMLButtonElement>("#code-close");
const codeEditorNote = $("#code-editor-note");
let codeTarget:
  | { nodeId: string; kind: "shader"; layerId: string }
  | { nodeId: string; kind: "customPath" }
  | null = null;
/** Layer focused from the inspector's shader field (reference codeEditorActive). */
let codePreferredNode: string | null = null;
let codePreferredLayer: string | null = null;
/** Layout the reference restores when the code editor deactivates (Mosaic `b`). */
let layoutBeforeCodeEditor: number | null = null;
const statusBar = $("#status");
const timeReadout = $("#time-readout");
const hud = $("#hud");
const zoomLabel = $("#zoom-label");

/* ------------------------------------------------------------------ */
/* Bootstrap scene                                                     */
/* ------------------------------------------------------------------ */

function seed(): void {
  const ctx = renderer.makeContext();

  const background = new MediaNode("Image", ctx);
  background.start = 0;
  background.duration = project.duration;
  // Backdrop for every preset: the "Neon Music Dreamscape" portrait artwork
  // (1672x941), shipped in the repo so nothing is fetched at boot.
  const backdrop = registerAsset(
    assets.addImage("Neon music dreamscape", "/media/neon-dreamscape.png", 1672, 941),
  );
  background.assetId = backdrop.id;
  void assets.load(backdrop);

  const spectrumNode = new SpectrumNode("Spectrum", ctx);
  // The editor opens on the Trap Motion spectrum.
  spectrumNode.applyParams(TRAP_MOTION_PRESET.params);
  configureTrapMotion(spectrumNode);
  spectrumNode.start = 0;
  spectrumNode.duration = project.duration;
  // The reference project's spectrum is fully opaque; a dimmed body made the
  // white disc read grey against dark backgrounds.
  spectrumNode.writeNumber("behaviour.opacity", 100);

  // The reference's Trap Motion composition contains a Particles item in its 3D
  // layer. Its exported values are the class defaults, so the node only needs
  // its span and the analyzer binding set here.
  const particles = new ParticlesNode("Particles", ctx);
  particles.start = 0;
  particles.duration = project.duration;
  // The exported item sits at z = -500, which is what puts the whole field in
  // front of the layer's perspective camera (near 1, far 1000).
  particles.particleOffset.set(0, 0, -500);

  for (const node of [background, spectrumNode, particles]) {
    project.nodes.push(node);
    bindAnalyzer(node, project.analyzers[0]?.id ?? null);
    renderer.attach(node);
  }

  // The reference's composition is three layers, and their order is what puts
  // the particles behind the spectrum: the image sits in the background layer,
  // the particles in the 3D (perspective) layer, the spectrum in the 2D layer
  // that composites last.
  const visualizerLayer = {
    id: newId("layer"),
    name: "2D Visualizers",
    nodeIds: [spectrumNode.id],
    enabled: true,
    renderToBuffer: false,
    camera: { type: "Orthographic" as const, fov: 45, near: 1, far: 100000 },
  };
  project.layers.push(
    {
      id: newId("layer"),
      name: "Background Layer",
      nodeIds: [background.id],
      enabled: true,
      renderToBuffer: false,
      camera: { type: "Orthographic" as const, fov: 45, near: 1, far: 100000 },
    },
    {
      id: newId("layer"),
      name: "3D Visualizers",
      nodeIds: [particles.id],
      enabled: true,
      renderToBuffer: false,
      camera: { type: "Perspective" as const, fov: 45, near: 1, far: 100000 },
    },
    visualizerLayer,
  );

  // Effects belong to the preset, not the project: nothing is seeded here. The
  // reference's soft rim comes from the spectrum layers' own shadow/blur values,
  // which a preset snapshot carries.
  //
  // The one exception is the reference's default "Global alpha" effect. New
  // projects create it on the WebGLManager with alpha 1 and disabled; it is a
  // normal Alpha effect, not a per-item effect, and it does not change the frame
  // until enabled or animated.
  const globalAlpha = createEffect("alpha", [GLOBAL_TARGET], () => "effect:global_fade");
  if (globalAlpha) {
    globalAlpha.name = "Global alpha";
    globalAlpha.params.alpha = 100;
    globalAlpha.enabled = false;
    project.effects.push(globalAlpha);
  }

  // One automation so the timeline has something to show on first run.
  project.automations.push({
    id: newId("automation"),
    type: "property",
    nodeId: spectrumNode.id,
    propertyId: "effects.gain",
    connections: {},
    keyframes: [
      { t: 0, value: 0.7, easing: "ease-out" },
      { t: 2.5, value: 1.9, easing: "ease-in" },
      { t: 5, value: 0.8, easing: "ease-out" },
      { t: 9, value: 1.6, easing: "linear" },
    ],
  });

  // The reference's Trap Motion project drives the spectrum's scaleMultiplier
  // from audio impact (1.75 .. 3.25), so the whole visualiser - ring, bars and
  // logo - pumps with the beat. Its maximum impact is the one the export cached
  // for this track.
  project.audioImpactMax = 1254.375834090776;
  project.automations.push({
    id: newId("automation"),
    name: "Audio Impact",
    type: "audioImpact",
    nodeId: spectrumNode.id,
    propertyId: "transform.scaleMultiplier",
    connections: {},
    keyframes: [],
    audioAnalyzer: project.analyzers[0]?.id,
    impact: {
      min: scaleMultiplierFromReference(1.75),
      max: scaleMultiplierFromReference(3.25),
      sensitivity: 0.1,
      smoothing: 0.3,
      floor: 0,
      ceiling: 3000,
      cumulative: false,
    },
  });

  // The reference editor boots with nothing selected, showing composition properties.
  selectedId = null;
  selectedLayerId = null;
  packTrackRows();
  syncNodeOrder();
}

function syncNodeOrder(): void {
  // A perspective layer projects each item's authored z; the ordering nudge
  // below exists only to depth-sort 2D items and would move 3D content several
  // percent off its authored screen position. In `koharu`, the two 70%-black
  // Planes that fill the song-info and subscribe panels sit at z=-500 and the
  // nudge pushed their projections outside the ProgressBar border that frames
  // them.
  const projected = new Set(
    project.layers
      .filter((layer) => layer.camera?.type === "Perspective")
      .flatMap((layer) => layer.nodeIds),
  );
  // A layer whose items are authored at different depths is a stage group, and
  // its paint order comes from `position:z`, not from the timeline. The shipped
  // `Layer` only does `this.scene.add(t.mesh)` for each item
  // (`main~427b64a5`, the Layer constructor's `onAddChild`) and never assigns a
  // render order; `renderOrder` appears only on the particle/spectrum meshes
  // (`this._particles.renderOrder = 999`, `main~3fbe2d64`). The items are
  // transparent planes, so three's back-to-front transparent sort is what
  // decides - an item at z=-1.5 paints after one at z=-7.5 because it is nearer.
  // Painting in timeline order instead put `utopia`'s six fog strips, its sun
  // and its mountain *over* the skyline they sit behind (43.01 -> 8.2 mean
  // against the same reference, `docs/template-parity-status.md`).
  const ordered = [...project.nodes];
  const stageNodes = new Set<string>();
  for (const layer of project.layers) {
    const slots: number[] = [];
    ordered.forEach((node, index) => {
      if (layer.nodeIds.includes(node.id)) slots.push(index);
    });
    if (slots.length < 2) continue;
    const depth = (node: (typeof ordered)[number]): number => {
      const value = Number(node.readNumber("transform.z"));
      return Number.isFinite(value) ? value : 0;
    };
    const distinct = new Set(slots.map((slot) => Math.round(depth(ordered[slot]) * 1000)));
    // Coplanar items fall back to the timeline order, which is also the
    // reference's tie-break (three sorts equal depths by object id).
    if (distinct.size < 2) continue;
    // A pure render-layer stack is a compositing chain, not a stage: every item
    // reproduces a whole layer buffer and none of them writes depth, so the
    // timeline order is the chain the author built. Sorting `glass-3d`'s
    // "2 Final" and 3D-Spect stacks by depth scored 51.89 against its
    // play-through reference where the timeline order scores 19.78. A layer
    // with at least one item of its own (a plain Media) is the stage case.
    if (!slots.some((slot) => ordered[slot] instanceof MediaNode && !ordered[slot].useLayerAsImage)) {
      continue;
    }
    const members = slots.map((slot) => ordered[slot]).sort((a, b) => depth(a) - depth(b));
    slots.forEach((slot, index) => {
      ordered[slot] = members[index];
      stageNodes.add(members[index].id);
    });
  }
  ordered.forEach((node, index) => {
    // A stage item's own `position:z` is its depth; adding the paint-order
    // nudge on top of it put `utopia`'s six fog strips ~0.14 units in front of
    // the skyline they belong behind, and - because a plain Media item writes
    // depth - culled the buildings painted after them.
    node.z = projected.has(node.id) || stageNodes.has(node.id) ? 0 : index * 0.01;
    node.group.renderOrder = index;
  });
  renderer.reorder(ordered);
}

/** First timeline row whose clips do not overlap this node's span. */
function firstFreeTrackRow(node: AnyNode): number {
  const start = node.start;
  const end = node.start + Math.max(0.001, node.duration);
  for (let row = 0; ; row += 1) {
    const blocked = project.nodes.some((other) => {
      if (other === node) return false;
      if (Math.max(0, Math.round(other.trackRow)) !== row) return false;
      return start < other.start + other.duration - 1e-6 && end > other.start + 1e-6;
    });
    if (!blocked) return row;
  }
}

/**
 * Reference row assignment: sort clips by start time and give each the first
 * row where it does not overlap an earlier clip. Used for new items and for
 * Project > Organize track positions.
 */
function packTrackRows(): void {
  const rowEnds: number[] = [];
  const ordered = [...project.nodes].sort(
    (a, b) => a.start - b.start || b.duration - a.duration,
  );
  for (const node of ordered) {
    let row = rowEnds.findIndex((end) => end <= node.start + 1e-6);
    if (row < 0) row = rowEnds.length;
    rowEnds[row] = node.start + Math.max(0.001, node.duration);
    node.trackRow = row;
  }
}

/** Older snapshots/imports have no row data; pack only when every item is row 0. */
function normalizeTrackRows(): void {
  if (
    project.nodes.length > 1 &&
    project.nodes.every((node) => Math.max(0, Math.round(node.trackRow)) === 0)
  ) {
    packTrackRows();
  }
}

/** Reference Project > Organize track positions. */
function organizeTrackPositions(): void {
  const before = new Map(project.nodes.map((node) => [node.id, node.trackRow] as const));
  packTrackRows();
  const after = new Map(project.nodes.map((node) => [node.id, node.trackRow] as const));
  const rows = new Set(after.values()).size;
  const apply = (values: Map<string, number>): void => {
    for (const node of project.nodes) {
      const value = values.get(node.id);
      if (value !== undefined) node.trackRow = value;
    }
    refreshTree();
    refreshInspector();
  };
  history.push({
    label: "organize track positions",
    undo: () => apply(before),
    redo: () => apply(after),
  });
  apply(after);
  setStatus(`Organized ${project.nodes.length} items into ${rows} track rows.`);
}

/* ------------------------------------------------------------------ */
/* Tree                                                                */
/* ------------------------------------------------------------------ */

const TREE_GROUPS: {
  label: string;
  chip: string;
  kinds: NodeKind[];
  items: { kind: NodeKind; name: string }[];
}[] = [
  {
    label: "2D Visualizers",
    chip: "2D",
    kinds: [NodeKind.Effects, NodeKind.Square, NodeKind.ProgressBar, NodeKind.Logo, NodeKind.Noise, NodeKind.SkiaText, NodeKind.Lyrics, NodeKind.ShaderItem, NodeKind.Skottie, NodeKind.Video, NodeKind.Video2, NodeKind.Butterchurn],
    items: [
      { kind: NodeKind.Effects, name: "Spectrum" },
      { kind: NodeKind.Square, name: "Square" },
      { kind: NodeKind.ProgressBar, name: "Progress Bar" },
      { kind: NodeKind.Logo, name: "Logo" },
      { kind: NodeKind.Noise, name: "Noise" },
      { kind: NodeKind.SkiaText, name: "Text" },
      { kind: NodeKind.Lyrics, name: "Lyrics" },
      { kind: NodeKind.ShaderItem, name: "Shader Item" },
      { kind: NodeKind.Skottie, name: "Skottie" },
      { kind: NodeKind.Video, name: "Video" },
      { kind: NodeKind.Video2, name: "Video 2" },
      { kind: NodeKind.Butterchurn, name: "Butterchurn" },
    ],
  },
  {
    label: "3D Visualizers",
    chip: "3D",
    kinds: [NodeKind.Particles, NodeKind.Cube, NodeKind.Plane, NodeKind.PointLight, NodeKind.Ground, NodeKind.AnimatedText, NodeKind.AudioWave, NodeKind.BasicSpectrumBars, NodeKind.ParticleLines, NodeKind.Model, NodeKind.LineBed, NodeKind.SphericalField, NodeKind.InstancedParticleSystem, NodeKind.ParticleSystem, NodeKind.Confetti, NodeKind.ParticleTimeLine],
    items: [
      { kind: NodeKind.Particles, name: "Particles" },
      { kind: NodeKind.Cube, name: "Cube" },
      { kind: NodeKind.Plane, name: "Plane" },
      { kind: NodeKind.PointLight, name: "Point Light" },
      { kind: NodeKind.Ground, name: "Ground" },
      { kind: NodeKind.AnimatedText, name: "Animated Text" },
      { kind: NodeKind.AudioWave, name: "Audio wave" },
      { kind: NodeKind.BasicSpectrumBars, name: "3D Bars" },
      { kind: NodeKind.ParticleLines, name: "Particle Lines" },
      { kind: NodeKind.Model, name: "Model" },
      { kind: NodeKind.LineBed, name: "Line Bed" },
      { kind: NodeKind.SphericalField, name: "Spherical Field" },
      { kind: NodeKind.InstancedParticleSystem, name: "Instanced Particle System" },
      { kind: NodeKind.ParticleSystem, name: "Particle System" },
      { kind: NodeKind.Confetti, name: "Confetti" },
      { kind: NodeKind.ParticleTimeLine, name: "Timeline" },
    ],
  },
  {
    label: "Background Layer",
    chip: "2D",
    kinds: [NodeKind.Media],
    items: [{ kind: NodeKind.Media, name: "Image" }],
  },
];

let draggedNodeId: string | null = null;
let draggedGroup: HTMLElement | null = null;

let draggedLayerId: string | null = null;
let draggedNodeId2: string | null = null;
/** Item dragged from the right-hand stack onto an analyzer row. */
let draggedStackNodeId: string | null = null;

const ITEM_DIMENSION = new Map<NodeKind, "2D" | "3D">();
for (const group of TREE_GROUPS) {
  const dimension = group.label === "3D Visualizers" ? "3D" : "2D";
  for (const item of group.items) {
    if (!ITEM_DIMENSION.has(item.kind)) ITEM_DIMENSION.set(item.kind, dimension);
  }
}

const CATALOGUE_ITEMS = TREE_GROUPS.flatMap((group) => group.items)
  .filter(
    (item, index, list) => list.findIndex((entry) => entry.kind === item.kind) === index,
  )
  .map((item) => ({ ...item, dimension: ITEM_DIMENSION.get(item.kind) ?? "2D" }));

/** A layer is 2D or 3D by its contents; empty layers accept either. */
function layerDimension(layer: {
  nodeIds: string[];
  name?: string;
  camera?: { type?: string };
}): "2D" | "3D" | null {
  const nodes = layer.nodeIds
    .map((id) => findNode(id))
    .filter((node): node is AnyNode => Boolean(node));
  if (nodes.length > 0) return nodes.some((node) => node.is3D) ? "3D" : "2D";
  // Empty layers keep their dimension: the reference stores it in the layer's
  // camera, and the default layers are named by it.
  if (layer.camera?.type === "Perspective") return "3D";
  if (layer.camera?.type === "Orthographic") return "2D";
  if (layer.name?.includes("3D")) return "3D";
  if (layer.name?.includes("2D") || layer.name === "Background Layer") return "2D";
  return null;
}

/**
 * A layer's first item locks its dimension, as the reference's layer camera
 * does; emptying the layer later must not make it accept the other dimension.
 */
function lockLayerDimension(
  layer: {
    nodeIds: string[];
    camera?: { type?: string; fov?: number; near?: number; far?: number };
  },
  node: AnyNode,
): void {
  if (layer.nodeIds.length > 0 || layer.camera) return;
  layer.camera = {
    type: node.is3D ? "Perspective" : "Orthographic",
    fov: 45,
    near: 1,
    far: 100000,
  };
}

/** Mirror the canvas clips into a hidden focusable list for screen readers. */
function refreshTimelineA11y(): void {
  if (!timelineReady) return;
  const root = document.querySelector<HTMLElement>("#timeline-a11y");
  if (!root) return;
  const items = timeline.getAccessibilityItems();
  const signature = items
    .map(
      (item) =>
        `${item.id}:${item.name}:${item.layer}:${item.start.toFixed(2)}:${item.duration.toFixed(2)}`,
    )
    .join("|");
  if (signature === timelineA11ySignature) return;
  timelineA11ySignature = signature;
  root.textContent = "";
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "a11y-clip";
    button.dataset.nodeId = item.id;
    button.setAttribute("role", "listitem");
    button.textContent = `${item.name}, ${item.layer}, ${item.start.toFixed(2)}s to ${(
      item.start + item.duration
    ).toFixed(2)}s`;
    button.addEventListener("click", () => select(item.id));
    button.addEventListener("focus", () => select(item.id));
    button.addEventListener("keydown", (event) => {
      const buttons = [
        ...root.querySelectorAll<HTMLButtonElement>("button.a11y-clip"),
      ];
      const index = buttons.indexOf(button);
      if (index < 0) return;
      let next: number | null = null;
      if (event.key === "ArrowDown" || event.key === "ArrowRight") {
        next = Math.min(buttons.length - 1, index + 1);
      } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
        next = Math.max(0, index - 1);
      } else if (event.key === "Home") {
        next = 0;
      } else if (event.key === "End") {
        next = buttons.length - 1;
      }
      if (next === null) return;
      event.preventDefault();
      buttons[next]?.focus();
    });
    root.append(button);
  }
}

/** Layer visibility from the tree, menu or timeline header (one undo step). */
function setLayerEnabled(layer: { name: string; enabled: boolean }, enabled: boolean): void {
  const before = layer.enabled;
  if (before === enabled) return;
  const apply = (value: boolean): void => {
    layer.enabled = value;
    refreshTree();
    refreshInspector();
  };
  apply(enabled);
  history.push({
    label: enabled ? "show layer" : "hide layer",
    undo: () => apply(before),
    redo: () => apply(enabled),
  });
  setStatus(`${layer.name} ${enabled ? "shown" : "hidden"}.`);
}

/** Layer rename from the layer menu (one undo step). */
function renameLayer(layer: { name: string }, name: string): void {
  const before = layer.name;
  if (!name || name === before) return;
  const apply = (value: string): void => {
    layer.name = value;
    refreshTree();
    refreshInspector();
  };
  apply(name);
  history.push({
    label: "rename layer",
    undo: () => apply(before),
    redo: () => apply(name),
  });
  setStatus(`Renamed layer to ${name}.`);
}

/** Item Solo/Shy/visibility flags (one undo step). */
function setNodeFlag(
  node: AnyNode,
  flag: "solo" | "shy" | "visible",
  enabled: boolean,
): void {
  const before = node[flag];
  if (before === enabled) return;
  const apply = (value: boolean): void => {
    node[flag] = value;
    refreshTree();
    refreshInspector();
  };
  apply(enabled);
  history.push({
    label: `${enabled ? "enable" : "disable"} ${flag}`,
    undo: () => apply(before),
    redo: () => apply(enabled),
  });
  const label = flag === "solo" ? "Solo" : flag === "shy" ? "Shy" : "Visible";
  setStatus(`${label} ${enabled ? "on" : "off"} \u2014 ${node.name}`);
}

/** Layer "render to buffer" is an edit, from the layer menu. */
function setLayerRenderToBuffer(
  layer: { name: string; renderToBuffer: boolean },
  enabled: boolean,
): void {
  const before = layer.renderToBuffer;
  if (before === enabled) return;
  const apply = (value: boolean): void => {
    layer.renderToBuffer = value;
    refreshTree();
    refreshInspector();
  };
  apply(enabled);
  history.push({
    label: enabled ? "enable render to buffer" : "disable render to buffer",
    undo: () => apply(before),
    redo: () => apply(enabled),
  });
  setStatus(`${layer.name} ${enabled ? "renders to buffer" : "renders directly"}.`);
}

/** Object rename from the item menu (one undo step). */
function renameNode(node: AnyNode, name: string): void {
  const before = node.name;
  if (!name || name === before) return;
  const apply = (value: string): void => {
    node.name = value;
    refreshTree();
    refreshInspector();
  };
  apply(name);
  history.push({
    label: "rename object",
    undo: () => apply(before),
    redo: () => apply(name),
  });
  setStatus(`Renamed ${before} to ${name}.`);
}

/** Effect enable/disable from any panel (one undo step). */
function setEffectEnabled(effect: EffectInstance, enabled: boolean): void {
  const before = effect.enabled;
  if (before === enabled) return;
  const apply = (value: boolean): void => {
    effect.enabled = value;
    refreshTree();
    refreshInspector();
  };
  apply(enabled);
  history.push({
    label: enabled ? "enable effect" : "disable effect",
    undo: () => apply(before),
    redo: () => apply(enabled),
  });
  setStatus(`${effect.name} ${enabled ? "enabled" : "disabled"}.`);
}

/** Automation enable/disable (one undo step). */
function setAutomationEnabled(automation: Automation, enabled: boolean): void {
  const before = automation.enabled;
  if (before === enabled) return;
  const apply = (value: boolean): void => {
    automation.enabled = value;
    refreshTree();
  };
  apply(enabled);
  // Re-enabling an impact row on a track that never scanned needs a normaliser.
  if (enabled && automation.type === "audioImpact") ensureAudioImpactNormaliser();
  history.push({
    label: enabled ? "enable automation" : "disable automation",
    undo: () => apply(before as boolean),
    redo: () => apply(enabled),
  });
  setStatus(`Automation ${enabled ? "enabled" : "disabled"}.`);
}

/** Ratio of the reference's shipped background pulse (`terminal.json`: 1 -> 1.05). */
const AUDIO_IMPACT_PULSE_RATIO = 1.05;

/** Audio-impact rows that drive this item's transform scale. */
function scaleImpactRowsFor(nodeId: string): Automation[] {
  return project.automations.filter(
    (automation) =>
      automation.type === "audioImpact" &&
      (automation.nodeId === nodeId ||
        (automation.connections[nodeId] ?? []).includes("transform.scaleX")),
  );
}

/**
 * The reference's background pulse seeded from the item's drawn scale.
 *
 * `terminal.json` drives an Image's `scale:x`/`scale:y` from 1 to 1.05 with
 * sensitivity 1 and smoothing 0.95. Node controllers store scale as a
 * percentage, so a default item is 100 -> 105; an item drawn at 130% gets
 * 130 -> 136.5 so the pulse is the same 5% zoom, not a jump to an absolute size.
 */
function createAudioImpactPulse(node: AnyNode, analyzerId: string | null): Automation {
  const hasScale = node.objectMapping.has("transform.scaleX");
  const drawn = hasScale ? node.readNumber("transform.scaleX") : 100;
  const min = Number.isFinite(drawn) ? Math.round(drawn * 100) / 100 : 100;
  const max = Math.round(min * AUDIO_IMPACT_PULSE_RATIO * 100) / 100;
  return {
    id: newId("automation"),
    name: "Audio Impact",
    type: "audioImpact",
    nodeId: node.id,
    propertyId: "transform.scaleX",
    connections: { [node.id]: ["transform.scaleY"] },
    keyframes: [],
    audioAnalyzer: analyzerId ?? undefined,
    impact: {
      min,
      max,
      sensitivity: 1,
      smoothing: 0.95,
      floor: 0,
      ceiling: 3000,
      cumulative: false,
      deltaSmoothing: false,
      deltaDecay: 0.01,
      deltaThreshold: 0,
    },
  };
}

/**
 * The `React to audio` action from the inspector's Audio analyzers folder.
 *
 * The reference only reacts to audio through `audioImpact` automations: an
 * item's analyzer binding picks the bands it reads for its own features (the
 * Image vignette), while a row samples `audioAnalyzerData[audioAnalyzer]` and
 * writes the normalised value into the connected controllers. Creating the row
 * is an explicit action here - the shipped templates author it by hand - except
 * on a background item, where choosing an analyzer creates it (see
 * `onAssignAnalyzer`).
 */
function addAudioImpactReaction(nodeId: string): void {
  const node = findNode(nodeId);
  if (!node) return;
  if (scaleImpactRowsFor(nodeId).length > 0) {
    setStatus(`${node.name} already has an audio-impact row for its scale.`);
    return;
  }
  const analyzerId = node.analyzerId ?? project.analyzers[0]?.id ?? "";
  const automation = createAudioImpactPulse(node, analyzerId || null);
  project.automations.push(automation);
  const index = project.automations.length - 1;
  // The normaliser is scanned when a track loads only if an impact row already
  // exists; without this the new row is pinned at `min` (a still image).
  ensureAudioImpactNormaliser();
  history.push({
    label: "add audio impact",
    undo: () => {
      project.automations = project.automations.filter((entry) => entry !== automation);
      refreshAutomationViews();
    },
    redo: () => {
      project.automations.splice(Math.min(index, project.automations.length), 0, automation);
      refreshAutomationViews();
    },
  });
  refreshAutomationViews();
  const analyzer = project.analyzers.find((entry) => entry.id === analyzerId);
  setStatus(
    `${node.name} reacts to ${analyzer?.name ?? "the analyzer"} (scale ${automation.impact!.min} -> ${automation.impact!.max}%).`,
  );
}

/** Remove an audio-impact row created from the Audio analyzers folder. */
function removeAudioImpactReaction(automationId: string): void {
  const automation = project.automations.find((entry) => entry.id === automationId);
  if (!automation) return;
  const index = project.automations.indexOf(automation);
  project.automations = project.automations.filter((entry) => entry !== automation);
  history.push({
    label: "remove audio impact",
    undo: () => {
      project.automations.splice(Math.min(index, project.automations.length), 0, automation);
      refreshAutomationViews();
    },
    redo: () => {
      project.automations = project.automations.filter((entry) => entry !== automation);
      refreshAutomationViews();
    },
  });
  refreshAutomationViews();
  setStatus("Audio impact removed.");
}

/**
 * Edit an audio-impact row's range or response from the inspector.
 *
 * `min`/`max` are the driven controller's units (module 682's `minValue`/
 * `maxValue`), `sensitivity` scales the analyzer reading and `smoothing` is the
 * per-frame blend (0 = snap, 1 = frozen). Values are clamped to what the engine
 * can use and the whole edit is one history step.
 */
function editAudioImpactReaction(
  automationId: string,
  change: Partial<{ from: number; to: number; sensitivity: number; smoothing: number }>,
): void {
  const automation = project.automations.find((entry) => entry.id === automationId);
  if (!automation?.impact) return;
  const before = { ...automation.impact };
  const next = { ...automation.impact };
  if (change.from !== undefined && Number.isFinite(change.from)) next.min = change.from;
  if (change.to !== undefined && Number.isFinite(change.to)) next.max = change.to;
  if (change.sensitivity !== undefined && Number.isFinite(change.sensitivity)) {
    next.sensitivity = Math.max(0, change.sensitivity);
  }
  if (change.smoothing !== undefined && Number.isFinite(change.smoothing)) {
    next.smoothing = Math.max(0, Math.min(1, change.smoothing));
  }
  if (
    next.min === before.min &&
    next.max === before.max &&
    next.sensitivity === before.sensitivity &&
    next.smoothing === before.smoothing
  ) {
    return;
  }
  const apply = (state: typeof before): void => {
    automation.impact = { ...state };
    // A ceiling below the new maximum would clip the sweep, so keep the engine's
    // bounds consistent with what the row now stores.
    refreshInspector();
    refreshAutomationViews();
  };
  automation.impact = next;
  history.push({
    label: "edit audio impact",
    undo: () => apply(before),
    redo: () => apply(next),
  });
  apply(next);
}

/** True for an Image that the reference treats as the automatic background. */
function isBackgroundItem(node: AnyNode): boolean {
  return node.typeLabel === "Media" && node.readNumber("basics.autoBackground") > 0.5;
}

function refreshTree(): void {
  refreshTimelineA11y();
  if (leftPanel !== "composition") {
    setLeftPanel(leftPanel);
    return;
  }
  treeRoot.textContent = "";

  // Every item belongs to exactly one layer; imported projects may leave gaps.
  const known = new Set(project.nodes.map((node) => node.id));
  for (const layer of project.layers) {
    layer.nodeIds = layer.nodeIds.filter((id) => known.has(id));
  }
  const assigned = new Set(project.layers.flatMap((layer) => layer.nodeIds));
  const unassigned = project.nodes.filter((node) => !assigned.has(node.id));
  // Imported projects can leave gaps. Route each orphan to a layer of its own
  // dimension instead of dumping every orphan into 3D Visualizers (which put 2D
  // items into the perspective layer).
  for (const node of unassigned) {
    const dimension = node.is3D ? "3D" : "2D";
    // Prefer the reference's named layer for that dimension, then any layer
    // locked to it; only create one when neither exists.
    let layer =
      project.layers.find((entry) => entry.name === `${dimension} Visualizers`) ??
      project.layers.find((entry) => layerDimension(entry) === dimension);
    if (!layer) {
      const baseName = dimension === "3D" ? "3D Visualizers" : "2D Visualizers";
      let name = baseName;
      let index = 2;
      while (project.layers.some((entry) => entry.name === name)) {
        name = `${baseName} (${index})`;
        index += 1;
      }
      layer = {
        id: newId("layer"),
        name,
        nodeIds: [],
        enabled: true,
        renderToBuffer: false,
        camera: {
          type: dimension === "3D" ? ("Perspective" as const) : ("Orthographic" as const),
          fov: 45,
          near: 1,
          far: 100000,
        },
      };
      project.layers.push(layer);
    }
    layer.nodeIds.push(node.id);
  }

  for (const layer of project.layers) {
    const nodes = layer.nodeIds
      .map((id) => findNode(id))
      .filter((node): node is AnyNode => Boolean(node));

    const wrap = document.createElement("div");
    wrap.className = "tree-group";

    const head = document.createElement("div");
    head.className = `tree-row layer-row${layer.id === selectedLayerId ? " selected" : ""}`;
    head.draggable = true;

    const twist = document.createElement("span");
    twist.className = "twist";
    twist.append(icon("expand_more", 14));

    const enabled = document.createElement("span");
    enabled.className = `check${layer.enabled ? " on" : ""}`;
    enabled.append(icon("check", 12));
    enabled.title = layer.enabled ? "Hide layer" : "Show layer";
    enabled.addEventListener("click", (event) => {
      event.stopPropagation();
      setLayerEnabled(layer, !layer.enabled);
    });

    const headName = document.createElement("span");
    headName.className = "name";
    headName.textContent = layer.name;

    const count = document.createElement("span");
    count.className = "kind";
    count.textContent = String(nodes.length);

    const add = document.createElement("button");
    add.className = "tree-add";
    add.title = `Add to ${layer.name}`;
    add.append(icon("add", 14));
    add.addEventListener("click", (event) => {
      event.stopPropagation();
      openAddItemDialog(layer.id);
    });

    head.append(twist, enabled, headName, count, add);
    head.addEventListener("click", () => selectLayer(layer.id));
    head.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      const next = window.prompt("Layer name", layer.name);
      if (!next?.trim()) return;
      renameLayer(layer, next.trim());
    });
    head.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      openLayerMenu(event, layer);
    });
    head.addEventListener("dragstart", (event) => {
      draggedLayerId = layer.id;
      head.classList.add("dragging");
      event.dataTransfer?.setData("text/plain", layer.id);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
    });
    head.addEventListener("dragover", (event) => {
      if (!draggedNodeId2 && (!draggedLayerId || draggedLayerId === layer.id)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      head.classList.add(draggedNodeId2 ? "drop-inside" : "drop-before");
    });
    head.addEventListener("dragleave", () => head.classList.remove("drop-before", "drop-inside"));
    head.addEventListener("drop", (event) => {
      event.preventDefault();
      if (draggedNodeId2) {
        moveNodeToLayer(draggedNodeId2, layer.id, null, false);
        return;
      }
      if (!draggedLayerId || draggedLayerId === layer.id) return;
      reorderLayer(draggedLayerId, layer.id);
    });
    head.addEventListener("dragend", () => {
      draggedLayerId = null;
      head.classList.remove("dragging", "drop-before", "drop-inside");
    });

    wrap.append(head);

    const children = document.createElement("div");
    children.className = "tree-children";

    nodes.forEach((node) => {
      const row = document.createElement("div");
      row.className = `tree-row${node.id === selectedId || multiSelection.has(node.id) ? " selected" : ""}`;

      const spacer = document.createElement("span");
      spacer.className = "twist";

      const visible = document.createElement("span");
      visible.className = `check${node.visible ? " on" : ""}`;
      visible.append(icon("check", 12));
      visible.addEventListener("click", (event) => {
        event.stopPropagation();
        setNodeFlag(node, "visible", !node.visible);
      });

      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = node.is3D ? "3D" : "2D";

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = node.name;

      row.append(spacer, visible, chip, name);
      row.addEventListener("click", (event) =>
        select(node.id, event.ctrlKey || event.metaKey),
      );
      row.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        openItemMenuAt(event.clientX, event.clientY, node);
      });
      row.draggable = true;
      row.addEventListener("dragstart", (event) => {
        draggedNodeId2 = node.id;
        row.classList.add("dragging");
        event.dataTransfer?.setData("text/plain", node.id);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
      });
      row.addEventListener("dragover", (event) => {
        if (!draggedNodeId2 || draggedNodeId2 === node.id) return;
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
        const rect = row.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        row.classList.toggle("drop-before", !after);
        row.classList.toggle("drop-after", after);
      });
      row.addEventListener("dragleave", () => {
        row.classList.remove("drop-before", "drop-after");
      });
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        if (!draggedNodeId2) return;
        moveNodeToLayer(
          draggedNodeId2,
          layer.id,
          node.id,
          row.classList.contains("drop-after"),
        );
      });
      row.addEventListener("dragend", () => {
        draggedNodeId2 = null;
        treeRoot
          .querySelectorAll(".dragging, .drop-before, .drop-after")
          .forEach((entry) => entry.classList.remove("dragging", "drop-before", "drop-after"));
      });

      children.append(row);
    });

    wrap.append(children);
    treeRoot.append(wrap);
  }
}

function sortNodesByLayers(): void {
  const byId = new Map(project.nodes.map((node) => [node.id, node]));
  const ordered: AnyNode[] = [];
  for (const layer of project.layers) {
    for (const id of layer.nodeIds) {
      const node = byId.get(id);
      if (node) ordered.push(node);
    }
  }
  for (const node of project.nodes) {
    if (!ordered.includes(node)) ordered.push(node);
  }
  project.nodes = ordered;
}

function moveNodeToLayer(
  nodeId: string,
  targetLayerId: string,
  targetNodeId: string | null,
  after: boolean,
): void {
  const node = findNode(nodeId);
  const target = project.layers.find((layer) => layer.id === targetLayerId);
  if (!node || !target) return;
  const dimension = layerDimension(target);
  const nodeDimension = node.is3D ? "3D" : "2D";
  if (dimension && dimension !== nodeDimension) {
    setStatus(`${target.name} is a ${dimension} layer; ${node.name} is ${nodeDimension}.`);
    return;
  }
  const layerState = () =>
    project.layers.map((layer) => ({
      id: layer.id,
      nodeIds: [...layer.nodeIds],
      camera: layer.camera ? { ...layer.camera } : undefined,
    }));
  const before = layerState();
  for (const layer of project.layers) {
    layer.nodeIds = layer.nodeIds.filter((id) => id !== nodeId);
  }
  lockLayerDimension(target, node);
  const index = targetNodeId ? target.nodeIds.indexOf(targetNodeId) : -1;
  if (index >= 0) target.nodeIds.splice(after ? index + 1 : index, 0, nodeId);
  else target.nodeIds.push(nodeId);
  const afterState = layerState();
  const apply = (state: ReturnType<typeof layerState>): void => {
    for (const saved of state) {
      const layer = project.layers.find((entry) => entry.id === saved.id);
      if (!layer) continue;
      layer.nodeIds = [...saved.nodeIds];
      if (saved.camera) layer.camera = { ...saved.camera };
      else delete layer.camera;
    }
    sortNodesByLayers();
    syncNodeOrder();
    refreshTree();
    refreshInspector();
  };
  apply(afterState);
  history.push({
    label: "move item to layer",
    undo: () => apply(before),
    redo: () => apply(afterState),
  });
  setStatus(`Moved ${node.name} to ${target.name}.`);
}

function reorderLayer(layerId: string, targetId: string): void {
  const from = project.layers.findIndex((layer) => layer.id === layerId);
  const to = project.layers.findIndex((layer) => layer.id === targetId);
  if (from < 0 || to < 0) return;
  const before = project.layers.map((layer) => layer.id);
  const [layer] = project.layers.splice(from, 1);
  project.layers.splice(to, 0, layer);
  const after = project.layers.map((entry) => entry.id);
  const apply = (order: string[]): void => {
    project.layers.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
    sortNodesByLayers();
    syncNodeOrder();
    refreshTree();
    refreshInspector();
  };
  apply(after);
  history.push({
    label: "reorder layer",
    undo: () => apply(before),
    redo: () => apply(after),
  });
  setStatus(`Reordered ${layer.name}.`);
}

function deleteLayer(layer: { id: string; name: string; nodeIds: string[] }): void {
  const target = project.layers.find((entry) => entry.id === layer.id);
  if (!target) return;
  if (!window.confirm(`Delete "${target.name}" and its ${target.nodeIds.length} item(s)?`)) return;

  const layerIndex = project.layers.indexOf(target);
  const layerNodeIds = [...target.nodeIds];
  const removedNodes = layerNodeIds
    .map((id) => findNode(id))
    .filter((node): node is AnyNode => Boolean(node));
  const nodeIndices = removedNodes.map((node) => project.nodes.indexOf(node));
  const analyzerIds = removedNodes.map((node) => node.analyzerId);
  const removedAutomations = project.automations
    .map((automation, index) => ({ automation, index }))
    .filter(({ automation }) => automation.nodeId && layerNodeIds.includes(automation.nodeId));
  const removedAutomationSet = new Set(removedAutomations.map((entry) => entry.automation));
  const ownershipBefore = snapshotOwnership(project.analyzers);

  const remove = (): void => {
    for (const node of removedNodes) {
      renderer.detach(node);
      detachUser(project.analyzers, node.id);
      node.analyzerId = null;
    }
    project.nodes = project.nodes.filter((node) => !layerNodeIds.includes(node.id));
    project.automations = project.automations.filter(
      (automation) => !removedAutomationSet.has(automation),
    );
    project.layers = project.layers.filter((entry) => entry !== target);
    if (selectedLayerId === target.id) selectedLayerId = null;
    multiSelection.clear();
    selectedId = null;
    timeline.setSelection([]);
    renderer.setGizmoTarget(null);
    refreshTree();
    refreshInspector();
    refreshStack();
    setStatus(`Deleted ${target.name}.`);
  };

  remove();
  const ownershipAfter = snapshotOwnership(project.analyzers);

  history.push({
    label: `remove ${target.name}`,
    undo: () => {
      restoreOwnership(project.analyzers, ownershipBefore);
      project.layers.splice(layerIndex, 0, target);
      removedNodes.forEach((node, index) => {
        project.nodes.splice(nodeIndices[index], 0, node);
        node.analyzerId = analyzerIds[index] ?? null;
        renderer.attach(node);
      });
      for (const { automation, index } of removedAutomations) {
        project.automations.splice(Math.min(index, project.automations.length), 0, automation);
      }
      sortNodesByLayers();
      syncNodeOrder();
      refreshTree();
      refreshInspector();
      refreshStack();
    },
    redo: () => {
      restoreOwnership(project.analyzers, ownershipAfter);
      remove();
    },
  });
}

function openLayerMenu(event: MouseEvent, layer: { id: string; name: string; enabled: boolean; renderToBuffer: boolean; nodeIds: string[] }): void {
  selectLayer(layer.id);
  const anchor = { x: event.clientX, y: event.clientY };
  showMenuAt(anchor.x, anchor.y, [
    {
      label: "Add Item",
      icon: "add",
      action: () => openAddItemDialog(layer.id),
    },
    { label: "Add Effect", icon: "auto_awesome", action: () => openAddEffectDialog([layer.id]) },
    {
      label: "Rename",
      icon: "text_fields",
      action: () => {
        const next = window.prompt("Layer name", layer.name);
        if (!next?.trim()) return;
        const target = project.layers.find((entry) => entry.id === layer.id);
        if (!target) return;
        renameLayer(target, next.trim());
      },
    },
    {
      label: layer.enabled ? "Hide layer" : "Show layer",
      icon: layer.enabled ? "visibility_off" : "visibility",
      action: () => {
        const target = project.layers.find((entry) => entry.id === layer.id);
        if (!target) return;
        setLayerEnabled(target, !target.enabled);
      },
    },
    {
      label: layer.renderToBuffer ? "Disable render to buffer" : "Render to buffer",
      icon: "visibility",
      action: () => {
        const target = project.layers.find((entry) => entry.id === layer.id);
        if (!target) return;
        target.renderToBuffer = !target.renderToBuffer;
        refreshTree();
        refreshInspector();
      },
    },
    { label: "Delete", icon: "delete", action: () => deleteLayer(layer) },
  ]);
}

/** Reorders items within one tree group (same-kind layers share draw order). */
function reorderNode(nodeId: string, targetId: string, after: boolean): void {
  const from = project.nodes.findIndex((node) => node.id === nodeId);
  if (from < 0 || nodeId === targetId) return;
  const [moved] = project.nodes.splice(from, 1);
  const target = project.nodes.findIndex((node) => node.id === targetId);
  if (!moved || target < 0) return;
  project.nodes.splice(after ? target + 1 : target, 0, moved);
  syncNodeOrder();
  refreshTree();
  setStatus(`Moved ${moved.name}.`);
}

function select(nodeId: string | null, additive = false): void {
  if (!nodeId) {
    multiSelection.clear();
    selectedAutomations = new Set();
    selectedId = null;
    selectedLayerId = null;
    selectedAnalyzerId = null;
    timeline.setSelection([]);
    renderer.setGizmoTarget(null);
    refreshTree();
    refreshInspector();
    return;
  }
  selectedAnalyzerId = null;
  selectedAutomations = new Set();
  if (additive) {
    if (multiSelection.has(nodeId) && multiSelection.size > 1) multiSelection.delete(nodeId);
    else multiSelection.add(nodeId);
    selectedId = nodeId;
  } else {
    multiSelection = new Set([nodeId]);
    selectedId = nodeId;
  }
  selectedLayerId = null;
  renderer.setGizmoTarget(findNode(nodeId) ?? null);
  timeline.setSelection([...multiSelection]);
  refreshTree();
  refreshInspector();
}

function selectLayer(layerId: string): void {
  multiSelection.clear();
  selectedAutomations = new Set();
  selectedId = null;
  selectedLayerId = layerId;
  selectedAnalyzerId = null;
  timeline.setSelection([]);
  renderer.setGizmoTarget(null);
  refreshTree();
  refreshInspector();
}

/** Reference analyzer selection: controllers open in the inspector. */
function selectAnalyzer(analyzerId: string): void {
  multiSelection.clear();
  selectedAutomations = new Set();
  selectedId = null;
  selectedLayerId = null;
  selectedAnalyzerId = analyzerId;
  renderer.setGizmoTarget(null);
  refreshTree();
  refreshInspector();
}

function addCompositionLayer(): void {
  let n = project.layers.length + 1;
  let name = `Layer ${n}`;
  while (project.layers.some((layer) => layer.name === name)) {
    n += 1;
    name = `Layer ${n}`;
  }
  const layer = {
    id: newId("layer"),
    name,
    nodeIds: [] as string[],
    enabled: true,
    renderToBuffer: false,
  };
  project.layers.push(layer);
  history.push({
    label: `add ${name}`,
    undo: () => {
      project.layers = project.layers.filter((entry) => entry.id !== layer.id);
      if (selectedLayerId === layer.id) selectedLayerId = null;
      refreshTree();
      refreshInspector();
    },
    redo: () => {
      project.layers.push(layer);
      refreshTree();
      refreshInspector();
    },
  });
  setLeftPanel("composition");
  selectLayer(layer.id);
  setStatus(`Added ${name}.`);
}

/** A layer's inspector object, created once and kept for the session. */
function layerNodeFor(layerId: string): LayerNode {
  const layer = project.layers.find((entry) => entry.id === layerId);
  const cached = layerNodes.get(layerId);
  if (cached) {
    // Restore/open can replace the layer array while the inspector node is
    // cached; keep the layer binding in sync.
    if (layer) {
      cached.name = layer.name;
      cached.compositionLayerId = layer.id;
      cached.audioAnalyzer = layer.audioAnalyzer ?? null;
    }
    return cached;
  }
  const node = createNode(NodeKind.Layer, layer?.name ?? "Layer", renderer.makeContext()) as LayerNode;
  node.compositionLayerId = layerId;
  node.audioAnalyzer = layer?.audioAnalyzer ?? null;
  if (layer) {
    node.objectMapping.set("rendering.renderToBuffer", layer.renderToBuffer ? 1 : 0);
    node.cameraType =
      layer.camera?.type ?? (layer.name === "3D Visualizers" ? "Perspective" : "Orthographic");
    node.cameraFov = layer.camera?.fov ?? 45;
    node.cameraNear = layer.camera?.near ?? 1;
    node.cameraFar = layer.camera?.far ?? 100000;
    node.onRenderToBufferChange = (value) => {
      layer.renderToBuffer = value;
    };
    node.onCameraChange = () => {
      layer.camera = {
        type: node.cameraType,
        fov: node.cameraFov,
        near: node.cameraNear,
        far: node.cameraFar,
      };
      // Ortho <-> perspective changes whether the order nudge is projected.
      syncNodeOrder();
    };
  }
  layerNodes.set(layerId, node);
  return node;
}

/* ------------------------------------------------------------------ */
/* Inspector                                                           */
/* ------------------------------------------------------------------ */

const inspector = new Inspector(inspectorBody, inspectorTitle, {
  onEdit(propertyId, label, value, animatable, previousValue) {
    if (propertyId.startsWith("project.")) {
      applyProjectEdit(propertyId, value);
      return;
    }
    if (!selectedId && selectedLayerId) {
      const layer = project.layers.find((entry) => entry.id === selectedLayerId);
      const layerNode = layerNodeFor(selectedLayerId);
      if (!layer) return;
      if (propertyId === "basics.name") {
        const name = String(value).trim();
        if (!name) return;
        layer.name = name;
        layerNode.name = name;
        refreshTree();
        refreshInspector();
        return;
      }
      if (propertyId === "rendering.renderToBuffer") {
        layer.renderToBuffer = Boolean(value);
        layerNode.writeNumber(propertyId, value ? 1 : 0);
        refreshTree();
        refreshInspector();
        return;
      }
      // Camera controls update the layer through LayerNode.onCameraChange.
      void label;
      void animatable;
      return;
    }
    if (!selectedId && selectedAnalyzerId) {
      // Analyzer controllers write through their own descriptors; journal the
      // edit here so undo works the same as for items.
      const analyzer = project.analyzers.find((entry) => entry.id === selectedAnalyzerId);
      if (!analyzer) return;
      const controller = analyzerControllerSetups(analyzer).controllers.find(
        (entry) => entry.id === propertyId,
      );
      if (!controller || previousValue === undefined) return;
      const before = previousValue;
      const afterPair = controller.writeRange ? controller.readRange?.() : undefined;
      // Slider drags emit on every move; journal the gesture once.
      const coalesce =
        controller.kind === PropertyKind.Slider &&
        coalescer.shouldCoalesce(`${project.id}:${analyzer.id}:${propertyId}`);
      if (!coalesce) {
        history.push({
          label: `set ${label}`,
          undo: () => {
            if (typeof before === "object") controller.writeRange?.(before[0], before[1]);
            else controller.write(before);
            refreshInspector();
          },
          redo: () => {
            if (afterPair) controller.writeRange?.(afterPair[0], afterPair[1]);
            else controller.write(value);
            refreshInspector();
          },
        });
      }
      refreshInspector();
      return;
    }
    if (!selectedId) return;
    const node = findNode(selectedId);
    if (!node) return;

    if (!animatable) {
      // Reference controller edits map over the whole selection, including
      // non-animatable controls (colours, toggles, selects, text, paths).
      const controllerFor = (target: AnyNode) =>
        target.createControllerSetups().controllers.find((entry) => entry.id === propertyId);
      const targets: { node: AnyNode; controller: ReturnType<typeof controllerFor> }[] = [
        { node, controller: controllerFor(node) },
      ];
      for (const otherId of multiSelection) {
        if (otherId === node.id) continue;
        const other = findNode(otherId);
        if (other) targets.push({ node: other, controller: controllerFor(other) });
      }
      const primaryController = targets[0]?.controller;
      const isRange = primaryController?.writeRange !== undefined;
      const afterRange = isRange ? primaryController?.readRange?.() : undefined;
      // The primary was written before this callback; the inspector passes its
      // old value. Siblings are snapshotted here, before they are updated.
      const snapshots = targets.map((entry, index) => ({
        ...entry,
        before:
          index === 0 && previousValue !== undefined
            ? previousValue
            : isRange
              ? entry.controller?.readRange?.()
              : entry.controller?.read(),
      }));
      for (const entry of snapshots.slice(1)) {
        if (isRange && afterRange) entry.controller?.writeRange?.(afterRange[0], afterRange[1]);
        else entry.controller?.write(value);
      }
      // Colour pickers emit on every pointer move; journal the gesture once so
      // undo returns to the colour the user started from.
      const coalesce =
        primaryController?.kind === PropertyKind.Color &&
        coalescer.shouldCoalesce(`${project.id}:${node.id}:${propertyId}`);
      if (!coalesce) {
        history.push({
          label: `set ${label}`,
          undo: () => {
            for (const entry of snapshots) {
              const before = entry.before;
              if (before === undefined) continue;
              const controller = controllerFor(entry.node);
              if (!controller) continue;
              if (typeof before === "object") {
                controller.writeRange?.(before[0], before[1]);
              } else {
                controller.write(before);
              }
            }
            refreshTree();
            refreshInspector();
          },
          redo: () => {
            for (const entry of snapshots) {
              const controller = controllerFor(entry.node);
              if (!controller) continue;
              if (isRange && afterRange && controller.writeRange) {
                controller.writeRange(afterRange[0], afterRange[1]);
              } else if (!isRange) {
                controller.write(value);
              }
            }
            refreshTree();
            refreshInspector();
          },
        });
      }
      refreshTree();
      refreshInspector();
      return;
    }

    const previous = Number(previousValue ?? node.objectMapping.get(propertyId) ?? 0);
    if (!coalescer.shouldCoalesce(`${project.id}:${node.id}:${propertyId}`)) {
      history.push({
        label: `change ${label}`,
        undo: () => {
          node.writeNumber(propertyId, previous);
          refreshInspector();
        },
        redo: () => {
          node.writeNumber(propertyId, Number(value));
          refreshInspector();
        },
      });
    } else {
      node.writeNumber(propertyId, Number(value));
    }
    // A multi-selection shares the primary object's edit when both expose the
    // same controller (numeric, colour, toggle, select, text, path).
    for (const otherId of multiSelection) {
      if (otherId === node.id) continue;
      const other = findNode(otherId);
      if (!other) continue;
      const controller = other
        .createControllerSetups()
        .controllers.find((entry) => entry.id === propertyId);
      controller?.write(value);
    }
    // Editing a keyframed property while stopped also moves the keyframe under
    // the playhead, so the change is visible immediately.
    const automation = project.automations.find(
      (a) => a.nodeId === node.id && a.propertyId === propertyId,
    );
    if (automation) {
      const key = automation.keyframes.find((k) => Math.abs(k.t - time) < 0.05);
      if (key) key.value = Number(value);
    }
  },
  onKeyframe(propertyId) {
    if (!selectedId) return;
    addKeyframe(selectedId, propertyId);
  },
  onPickFile(propertyId) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!node) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = node instanceof VideoNode ? "video/*" : "image/*";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      // Data URLs keep the picked file inside the session (and any future
      // save) instead of pointing at a blob that dies with the page.
      const url = await readFileAsDataUrl(file);
      if (node instanceof VideoNode) {
        const controller = node
          .createControllerSetups()
          .controllers.find((entry) => entry.id === propertyId);
        const before = String(controller?.read() ?? "");
        controller?.write(url);
        history.push({
          label: "set video file",
          undo: () => {
            controller?.write(before);
            refreshInspector();
          },
          redo: () => {
            controller?.write(url);
            refreshInspector();
          },
        });
        refreshInspector();
        setStatus(`Video set to ${file.name}.`);
        return;
      }
      if (node instanceof ParticlesNode) {
        // Module 1354 stores the uploaded sprite on the item itself.
        node.particleImage = url;
        await node.loadTexture();
        refreshInspector();
        setStatus(`Particle image set to ${file.name}.`);
        return;
      }
      if (node instanceof MediaNode || node instanceof SpectrumNode) {
        const asset = registerAsset(assets.addImage(file.name, url, 0, 0));
        await assets.load(asset);
        node.assetId = asset.id;
        node.imageUrl = null;
        void propertyId;
        refreshTree();
        refreshInspector();
        setStatus(`${node.name} image set to ${file.name}.`);
        return;
      }
      setStatus(`${node.name} has no image to replace.`);
    });
    input.click();
  },
  imagePreview(propertyId) {
    void propertyId;
    const node = selectedId ? findNode(selectedId) : null;
    if (!node) return null;
    if (node instanceof VideoNode) return node.src || null;
    if (node instanceof ParticlesNode) return node.particleImage || null;
    if (node instanceof MediaNode || node instanceof SpectrumNode) {
      if (node.imageUrl) return node.imageUrl;
      return node.assetId ? assets.record(node.assetId)?.url ?? null : null;
    }
    return null;
  },
  onClearImage(propertyId) {
    void propertyId;
    const node = selectedId ? findNode(selectedId) : null;
    if (!node) return;
    if (node instanceof ParticlesNode) {
      node.particleImage = "";
      void node.loadTexture();
    } else if (node instanceof MediaNode || node instanceof SpectrumNode) {
      node.assetId = null;
      node.imageUrl = null;
    } else {
      return;
    }
    refreshTree();
    refreshInspector();
    setStatus(`${node.name} image cleared.`);
  },
  onAddSpectrumLayer(nodeId) {
    const node = findNode(nodeId);
    if (!(node instanceof SpectrumNode)) return;
    const palette = [
      "#f72585",
      "#4cc9f0",
      "#f9c74f",
      "#90be6d",
      "#b5179e",
      "#4895ef",
      "#f9844a",
      "#43aa8b",
    ];
    const before = node.layers.length;
    const shift = project.spectrumLayerColorShift;
    const mode = project.spectrumLayerColorMode;
    const layer = createSpectrumLayer(
      before,
      shiftHexColor(palette[before % palette.length], mode, shift),
    );
    layer.colorFrom = shiftHexColor(layer.colorFrom, mode, shift);
    layer.colorTo = shiftHexColor(layer.colorTo, mode, shift);
    layer.shadowColor = shiftHexColor(layer.shadowColor, mode, shift);
    node.layers.push(layer);
    history.push({
      label: "add spectrum layer",
      undo: () => {
        node.layers.length = before;
        refreshInspector();
      },
      redo: () => {
        node.layers.push(layer);
        refreshInspector();
      },
    });
    refreshInspector();
    setStatus(`${node.name}: ${node.layers.length} spectrum layers.`);
  },
  onRemoveSpectrumLayer(nodeId) {
    const node = findNode(nodeId);
    if (!(node instanceof SpectrumNode)) return;
    if (node.layers.length <= 1) {
      setStatus("A spectrum needs at least one layer.");
      return;
    }
    const removed = node.layers.pop();
    if (!removed) return;
    history.push({
      label: "remove spectrum layer",
      undo: () => {
        node.layers.push(removed);
        refreshInspector();
      },
      redo: () => {
        node.layers.pop();
        refreshInspector();
      },
    });
    refreshInspector();
    setStatus(`${node.name}: ${node.layers.length} spectrum layers.`);
  },
  onAssignAnalyzer(nodeId, analyzerId) {
    const node = findNode(nodeId);
    if (!node) return;

    const beforeId = node.analyzerId;
    const before = snapshotOwnership(project.analyzers);
    // Background items react as soon as they have an analyzer. The reference only
    // reacts through `audioImpact` rows (its Image reads the analyser for the
    // vignette alone), so choosing one creates the shipped pulse inside the same
    // undo step. Intentional product behaviour - see
    // docs/audio-impact-binding-decompiled.md; every other item keeps the
    // explicit "React to audio" button and never gets a silent row.
    const pulse =
      !beforeId &&
      analyzerId &&
      isBackgroundItem(node) &&
      scaleImpactRowsFor(node.id).length === 0
        ? createAudioImpactPulse(node, analyzerId)
        : null;
    if (pulse) project.automations.push(pulse);
    bindAnalyzer(node, analyzerId);
    const afterId = node.analyzerId;
    if (beforeId === afterId) {
      if (pulse) project.automations = project.automations.filter((entry) => entry !== pulse);
      return;
    }
    const after = snapshotOwnership(project.analyzers);

    history.push({
      label: pulse ? "add audio impact" : "assign analyzer",
      undo: () => {
        if (pulse) {
          project.automations = project.automations.filter((entry) => entry !== pulse);
        }
        restoreOwnership(project.analyzers, before);
        node.analyzerId = beforeId;
        refreshTree();
        refreshInspector();
      },
      redo: () => {
        if (pulse && !project.automations.includes(pulse)) project.automations.push(pulse);
        restoreOwnership(project.analyzers, after);
        node.analyzerId = afterId;
        refreshTree();
        refreshInspector();
      },
    });

    if (pulse) ensureAudioImpactNormaliser();
    refreshTree();
    refreshInspector();
    const name = project.analyzers.find((item) => item.id === afterId)?.name ?? "None";
    setStatus(
      pulse && pulse.impact
        ? `${node.name} reacts to ${name} (scale ${pulse.impact.min} -> ${pulse.impact.max}%).`
        : `${node.name} uses ${name}.`,
    );
  },
  onAssignLayerAnalyzer(layerId, analyzerId) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!(node instanceof SpectrumNode)) return;
    const layer = node.layers.find((item) => item.id === layerId);
    if (!layer || layer.audioAnalyzer === analyzerId) return;

    const before = layer.audioAnalyzer;
    layer.audioAnalyzer = analyzerId;
    history.push({
      label: "layer analyzer",
      undo: () => {
        layer.audioAnalyzer = before;
        refreshInspector();
      },
      redo: () => {
        layer.audioAnalyzer = analyzerId;
        refreshInspector();
      },
    });
    refreshInspector();
    const name = project.analyzers.find((item) => item.id === analyzerId)?.name ?? "item bands";
    setStatus(`Layer uses ${name}.`);
  },
  onAssignCompositionLayerAnalyzer(layerId, analyzerId) {
    const layer = project.layers.find((entry) => entry.id === layerId);
    if (!layer || (layer.audioAnalyzer ?? null) === analyzerId) return;
    const beforeLayer = layer.audioAnalyzer ?? null;
    const beforeOwners = snapshotOwnership(project.analyzers);
    // Contents without their own binding, or still following the previous
    // layer binding, inherit the new one; an item with its own analyzer keeps it.
    const inheriting = layer.nodeIds
      .map((id) => findNode(id))
      .filter((node): node is AnyNode => Boolean(node))
      .filter((node) => node.analyzerId === null || node.analyzerId === beforeLayer);
    const beforeNodes = inheriting.map((node) => ({ node, analyzerId: node.analyzerId }));
    const apply = (value: string | null): void => {
      layer.audioAnalyzer = value;
      const layerNode = layerNodeFor(layerId);
      layerNode.audioAnalyzer = value;
      assignUser(project.analyzers, layerId, value);
      for (const node of inheriting) {
        node.analyzerId = value;
        assignUser(project.analyzers, node.id, value);
      }
    };
    apply(analyzerId);
    const afterOwners = snapshotOwnership(project.analyzers);
    const afterNodes = inheriting.map((node) => ({ node, analyzerId: node.analyzerId }));
    history.push({
      label: "layer analyzer",
      undo: () => {
        layer.audioAnalyzer = beforeLayer;
        layerNodeFor(layerId).audioAnalyzer = beforeLayer;
        restoreOwnership(project.analyzers, beforeOwners);
        for (const entry of beforeNodes) entry.node.analyzerId = entry.analyzerId;
        refreshTree();
        refreshInspector();
        renderAnalyzerPanel();
      },
      redo: () => {
        layer.audioAnalyzer = analyzerId;
        layerNodeFor(layerId).audioAnalyzer = analyzerId;
        restoreOwnership(project.analyzers, afterOwners);
        for (const entry of afterNodes) entry.node.analyzerId = entry.analyzerId;
        refreshTree();
        refreshInspector();
        renderAnalyzerPanel();
      },
    });
    refreshTree();
    refreshInspector();
    renderAnalyzerPanel();
    const name = project.analyzers.find((item) => item.id === analyzerId)?.name ?? "None";
    setStatus(`${layer.name} uses ${name}.`);
  },
  onAddAudioImpact(nodeId) {
    addAudioImpactReaction(nodeId);
  },
  onRemoveAudioImpact(automationId) {
    removeAudioImpactReaction(automationId);
  },
  onEditAudioImpact(automationId, change) {
    editAudioImpactReaction(automationId, change);
  },
  onEditSpectrumLayer(nodeId, layerId, property, value, group) {
    const node = findNode(nodeId);
    if (!(node instanceof SpectrumNode)) return;
    const targets = group
      ? [...node.layers]
      : node.layers.filter((layer) => layer.id === layerId);
    if (targets.length === 0) return;

    const before = targets.map((layer) => ({ layer, value: layer[property] }));
    const apply = (): void => {
      for (const layer of targets) {
        (layer as unknown as Record<string, unknown>)[property as string] = value;
      }
    };
    apply();
    history.push({
      label: `layer ${property}`,
      undo: () => {
        for (const entry of before) {
          (entry.layer as unknown as Record<string, unknown>)[property as string] = entry.value;
        }
        refreshInspector();
      },
      redo: () => {
        apply();
        refreshInspector();
      },
    });
    refreshInspector();
    setStatus(
      group
        ? `Updated ${property} on ${targets.length} layers.`
        : `Updated layer ${property}.`,
    );
  },
  onSpectrumColorMode(mode) {
    project.spectrumLayerColorMode = mode;
    persistComposition();
    setStatus(`New spectrum layers will ${mode === "lighten" ? "lighten" : "darken"} their colour.`);
  },
  onSpectrumColorShift(value) {
    project.spectrumLayerColorShift = Math.min(1, Math.max(0, value));
    persistComposition();
  },
  onFocusShader(nodeId, layerId) {
    codePreferredNode = nodeId;
    codePreferredLayer = layerId;
    openCodeEditorLayout();
    syncCodeEditor();
    setStatus("Code editor opened for the selected shader.");
  },
  onSpectrumReaction(nodeId, change) {
    setSpectrumReaction(nodeId, change);
  },
  onPreset(preset) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!(node instanceof SpectrumNode)) return;
    const before = {
      params: node.readParams(),
      layers: node.layers.map((l) => ({ ...l })),
      path: {
        pathMode: node.pathMode,
        customPath: node.customPath,
        closeLine: node.closeLine,
        moveBack: node.moveBack,
        repeatPointsOnPath: node.repeatPointsOnPath,
        smoothStartAndEnd: node.smoothStartAndEnd,
        smoothingWidth: node.smoothingWidth,
        smoothingPasses: node.smoothingPasses,
        stretchToEnd: node.stretchToEnd,
        spacing: node.spacing,
        lineCap: node.lineCap,
        pathEffect: node.pathEffect,
        dashOffset: node.dashOffset,
        clipSize: node.clipSize,
        positionX: node.positionX,
        positionY: node.positionY,
        scaleX: node.scaleX,
        scaleY: node.scaleY,
        referenceScaleMultiplier: node.referenceScaleMultiplier,
        spinSpeed: node.spinSpeed,
        circleColor: node.circleColor,
        assetId: node.assetId,
      },
      // Applying a preset materialises its analysers in the project, so undo
      // must restore the previous set (and any settings it overwrote).
      analyzers: project.analyzers.map((analyzer) => ({ ...analyzer, users: [...analyzer.users] })),
    };
    const apply = () => {
      const analyzerIds = materializePresetAnalyzers(preset, node);
      if (preset.snapshot) {
        // Same mapping the project importer uses, so presets and Trap Motion
        // share one code path.
        const entry: Record<string, unknown> = { ...preset.snapshot.item };
        for (const layer of preset.snapshot.layers) {
          for (const [key, value] of Object.entries(layer)) {
            if (key === "index" || key === "analyzerIndex") continue;
            entry[`spectrum_layer:${layer.index}:${key}`] = value;
          }
          const analyzerIndex = Number(layer.analyzerIndex);
          if (Number.isInteger(analyzerIndex) && analyzerIds[analyzerIndex]) {
            entry[`spectrum_layer:${layer.index}:audioAnalyzer`] = analyzerIds[analyzerIndex];
          }
        }
        applySpectrumExport(node, entry, { pathRenderer: true });
      } else {
        node.resetPresetLook();
        node.applyParams(preset.params);
        // Built-in presets are reference circles too; the shader fallback
        // draws them as disjoint ring bars, so keep the path renderer.
        node.pathMode = true;
      }
      if (preset.id === "trap-motion") configureTrapMotion(node);
      renderer.retainAnalyzers(project.analyzers.map((analyzer) => analyzer.id));
    };
    apply();
    history.push({
      label: `preset ${preset.name}`,
      undo: () => {
        node.applyParams(before.params);
        node.layers.splice(0, node.layers.length, ...before.layers.map((l) => ({ ...l })));
        Object.assign(node, before.path);
        project.analyzers = before.analyzers.map((analyzer) => ({
          ...analyzer,
          users: [...analyzer.users],
        }));
        renderer.retainAnalyzers(project.analyzers.map((analyzer) => analyzer.id));
      },
      redo: apply,
    });
    refreshInspector();
    focusPreview();
    setStatus(`applied ${preset.name}`);
  },
  onSavePreset(name) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!(node instanceof SpectrumNode)) return;
    saveUserPreset(name, node.readParams());
    refreshInspector();
    setStatus(`saved preset: ${name}`);
  },
  onImportPresets(presets) {
    for (const preset of presets) saveUserPreset(preset.name, preset.params);
    refreshInspector();
    setStatus(`imported ${presets.length} preset(s)`);
  },
  onOverwritePreset(preset) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!(node instanceof SpectrumNode)) return;
    updateUserPreset(preset.id, { params: node.readParams() });
    refreshInspector();
    setStatus(`updated preset: ${preset.name}`);
  },
  onEditPresetImage(preset) {
    // Reference `SCREENSHOT`: replace the preset's picture with the current frame.
    // Downscale so the data URL stays small in local storage.
    const source = stageCanvas;
    const thumb = document.createElement("canvas");
    thumb.width = 160;
    thumb.height = Math.max(1, Math.round((160 * source.height) / Math.max(1, source.width)));
    const context = thumb.getContext("2d");
    if (!context) return;
    context.drawImage(source, 0, 0, thumb.width, thumb.height);
    updateUserPreset(preset.id, { thumb: thumb.toDataURL("image/jpeg", 0.8) });
    refreshInspector();
    setStatus(`updated the picture of ${preset.name}`);
  },
  onDeletePreset(id) {
    if (!window.confirm("Are you sure you want to delete this preset?")) return;
    deleteUserPreset(id);
    refreshInspector();
    setStatus(`deleted preset ${id}`);
  },
  onParticlePreset(preset) {
    const selected = selectedId ? findNode(selectedId) : null;
    if (selected instanceof ParticlesNode) {
      const node = selected;
      const before = readParticleParams(node);
      const apply = (): void => {
        applyParticlePreset(node, preset);
      };
      apply();
      history.push({
        label: `particle preset ${preset.name}`,
        undo: () => {
          applyParticlePreset(node, {
            id: "particle-preset-before",
            name: "Previous",
            category: "Custom",
            params: before,
          });
          refreshInspector();
        },
        redo: () => {
          apply();
          refreshInspector();
        },
      });
      refreshInspector();
      focusPreview();
      setStatus(`applied particle preset ${preset.name}`);
      return;
    }

    // Nothing particle-shaped is selected: create the item on the active layer
    // through the ordinary add-item path, so undo and project import agree.
    const layerId =
      selectedLayerId ??
      project.layers.find((layer) => layer.nodeIds.some((id) => findNode(id)?.is3D))?.id ??
      project.layers[0]?.id;
    addNodeOfKind(NodeKind.Particles, "Particles", layerId, (created) => {
      if (created instanceof ParticlesNode) applyParticlePreset(created, preset);
    });
    setStatus(`added Particles with ${preset.name}`);
  },
  onSaveParticlePreset(name) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!(node instanceof ParticlesNode)) {
      setStatus("Select a particle item before saving a particle preset.");
      return;
    }
    saveUserParticlePreset(name, readParticleParams(node), undefined, node.reaction ?? undefined);
    refreshInspector();
    setStatus(`saved particle preset: ${name}`);
  },
  onImportParticlePresets(presets) {
    for (const preset of presets) {
      saveUserParticlePreset(preset.name, preset.params, preset.thumb, preset.audio);
    }
    refreshInspector();
    setStatus(`imported ${presets.length} particle preset(s)`);
  },
  onOverwriteParticlePreset(preset) {
    const node = selectedId ? findNode(selectedId) : null;
    if (!(node instanceof ParticlesNode)) return;
    updateUserParticlePreset(preset.id, {
      params: readParticleParams(node),
      audio: node.reaction ?? undefined,
    });
    refreshInspector();
    setStatus(`updated particle preset: ${preset.name}`);
  },
  onEditParticlePresetImage(preset) {
    const source = stageCanvas;
    const thumb = document.createElement("canvas");
    thumb.width = 160;
    thumb.height = Math.max(1, Math.round((160 * source.height) / Math.max(1, source.width)));
    const context = thumb.getContext("2d");
    if (!context) return;
    context.drawImage(source, 0, 0, thumb.width, thumb.height);
    updateUserParticlePreset(preset.id, { thumb: thumb.toDataURL("image/jpeg", 0.8) });
    refreshInspector();
    setStatus(`updated the picture of ${preset.name}`);
  },
  onDeleteParticlePreset(id) {
    if (!window.confirm("Are you sure you want to delete this particle preset?")) return;
    deleteUserParticlePreset(id);
    refreshInspector();
    setStatus(`deleted particle preset ${id}`);
  },
});

function automationsFor(nodeId: string): InspectorAutomationInfo[] {
  return project.automations
    .filter((a) => a.nodeId === nodeId)
    .map((a) => ({
      id: a.id,
      propertyId: a.propertyId,
      keys: a.keyframes.map((k) => k.t),
      type: a.type,
      impact: a.impact
        ? {
            from: a.impact.min,
            to: a.impact.max,
            sensitivity: a.impact.sensitivity,
            smoothing: a.impact.smoothing,
          }
        : undefined,
    }));
}

/**
 * The reference's Audio Impact row that animates this Spectrum, if one exists.
 *
 * Reference projects bind it with `connections: { "item:Spectrum:<id>":
 * ["scaleMultiplier"] }`; the settings live on the automation itself
 * (`Min value`, `Max value`, `Upper limit`, `Sensitivity`, …). Only
 * `audioImpact` rows whose target is one of the item's transform controllers
 * belong to this group; anything else stays in the timeline.
 */
function spectrumReactionAutomation(nodeId: string): Automation | null {
  return (
    project.automations.find(
      (entry) =>
        entry.type === "audioImpact" &&
        entry.nodeId === nodeId &&
        entry.impact !== undefined &&
        isSpectrumReactionProperty(entry.propertyId),
    ) ?? null
  );
}

function spectrumReactionView(node: SpectrumNode): SpectrumReactionView | null {
  const automation = spectrumReactionAutomation(node.id);
  if (!automation || !automation.impact) return null;
  const propertyId = automation.propertyId as SpectrumReactionProperty;
  return {
    automationId: automation.id,
    propertyId,
    enabled: automation.enabled !== false,
    analyzerId:
      automation.audioAnalyzer ?? node.analyzerId ?? project.analyzers[0]?.id ?? "",
    impact: automation.impact,
    value: spectrumReactionValue(node, propertyId),
  };
}

function cloneAutomation(automation: Automation): Automation {
  return JSON.parse(JSON.stringify(automation)) as Automation;
}

/**
 * Create / edit / remove a Spectrum's Audio Impact automation.
 *
 * The whole automation is snapshotted for undo, because enabling it can create
 * the row and every controller writes one of its settings.
 */
function setSpectrumReaction(nodeId: string, change: SpectrumReactionChange): void {
  const node = findNode(nodeId);
  if (!(node instanceof SpectrumNode)) return;
  const existing = spectrumReactionAutomation(nodeId);
  const existingId = existing?.id;
  const index = existing ? project.automations.indexOf(existing) : project.automations.length;
  const before = existing ? cloneAutomation(existing) : null;
  let label = "edit audio impact";

  switch (change.kind) {
    case "remove":
      if (!existing) return;
      project.automations = project.automations.filter((entry) => entry !== existing);
      label = "remove audio impact";
      break;

    case "enabled": {
      if (!existing) {
        if (!change.enabled) return;
        const propertyId = DEFAULT_SPECTRUM_REACTION_PROPERTY;
        project.automations.push({
          id: newId("automation"),
          name: "Audio Impact",
          type: "audioImpact",
          nodeId,
          propertyId,
          connections: {},
          keyframes: [],
          audioAnalyzer: node.analyzerId ?? project.analyzers[0]?.id,
          // Seed from the value the item is drawn at, not the raw percent
          // controller: `referenceScaleMultiplier` is the factor `preScaling`
          // applies, which is what `Min value` shows.
          impact: defaultSpectrumReactionImpact(
            propertyId,
            reactionControllerValue(propertyId, spectrumReactionValue(node, propertyId)),
          ),
        });
        label = "add audio impact";
      } else {
        // The reference's `enabled` controller sits in the Automation folder;
        // absent means enabled.
        if (change.enabled) delete existing.enabled;
        else existing.enabled = false;
        label = change.enabled ? "enable audio impact" : "disable audio impact";
      }
      break;
    }

    case "property": {
      if (!existing || !existing.impact) return;
      if (existing.propertyId === change.propertyId) return;
      existing.propertyId = change.propertyId;
      // Re-seed the range in the new controller's units; a pump that was
      // authored for a 1.2x factor means nothing in degrees.
      existing.impact = defaultSpectrumReactionImpact(
        change.propertyId,
        reactionControllerValue(
          change.propertyId,
          spectrumReactionValue(node, change.propertyId),
        ),
      );
      label = "change audio impact target";
      break;
    }

    case "analyzer":
      if (!existing) return;
      if (change.analyzerId) existing.audioAnalyzer = change.analyzerId;
      else delete existing.audioAnalyzer;
      label = "change audio impact analyzer";
      break;

    case "impact":
      if (!existing || !existing.impact) return;
      existing.impact = { ...existing.impact, ...change.patch };
      break;
  }

  const after = spectrumReactionAutomation(nodeId);
  const afterId = after?.id;
  const afterSnapshot = after ? cloneAutomation(after) : null;

  const restore = (snapshot: Automation | null, id: string | undefined): void => {
    if (id) project.automations = project.automations.filter((entry) => entry.id !== id);
    if (snapshot) {
      project.automations.splice(
        Math.min(index, project.automations.length),
        0,
        cloneAutomation(snapshot),
      );
    }
    // The driven value is written on the next automation pass; run it now so
    // the preview (and the undo) lands without waiting a frame.
    applyAutomations(time);
    renderer.render(time);
    refreshAutomationViews();
  };

  history.push({
    label,
    undo: () => restore(before, existingId ?? afterId),
    redo: () => restore(afterSnapshot, existingId ?? afterId),
  });

  applyAutomations(time);
  renderer.render(time);
  refreshAutomationViews();
}

function refreshInspector(): void {
  syncCodeEditor();
  const analyzer = selectedAnalyzerId
    ? project.analyzers.find((entry) => entry.id === selectedAnalyzerId) ?? null
    : null;
  if (selectedAnalyzerId && !analyzer) selectedAnalyzerId = null;
  if (analyzer) {
    inspector.renderAnalyzer(analyzer, () => renderAnalyzerPanel());
    inspectorTitle.textContent = `Objects / ${analyzer.name}`;
    $("#inspector-body").style.display = "";
    $("#panel-stack").style.display = "none";
    return;
  }
  const layerNode = selectedLayerId ? layerNodeFor(selectedLayerId) : null;
  const node = layerNode ?? (selectedId ? findNode(selectedId) : null);
  const body = $("#inspector-body");
  const stack = $("#panel-stack");
  if (node) {
    const others =
      multiSelection.size > 1
        ? ` and ${multiSelection.size - 1} other${multiSelection.size === 2 ? "" : "s"}`
        : "";
    if (selectedId && inspectorAutomationView) {
      inspectorTitle.textContent = `Objects / ${node.name}${others}`;
      body.style.display = "";
      stack.style.display = "none";
      renderAutomationInspector(node);
      return;
    }
    inspector.render(
      node,
      selectedId ? automationsFor(node.id) : [],
      project.analyzers,
      {
        mode: project.spectrumLayerColorMode,
        shift: project.spectrumLayerColorShift,
      },
      node instanceof SpectrumNode ? spectrumReactionView(node) : null,
    );
    inspectorTitle.textContent = `Objects / ${node.name}${others}`;
    body.style.display = "";
    stack.style.display = "none";
    return;
  }
  inspector.render(null, [], project.analyzers, {
    mode: project.spectrumLayerColorMode,
    shift: project.spectrumLayerColorShift,
  });
  inspectorTitle.textContent = "Objects";
  body.style.display = "none";
  stack.style.display = "";
  refreshStack();
}

/** Reference "Edit automations" view: the selected object's automation list. */
function renderAutomationInspector(node: AnyNode): void {
  const body = $("#inspector-body");
  body.textContent = "";
  const wrap = document.createElement("div");
  wrap.className = "automation-inspector";

  const note = document.createElement("p");
  note.className = "panel-note";
  note.textContent = `${node.name} automations — keyframes live on the timeline clip.`;
  wrap.append(note);

  const automations = project.automations.filter((automation) => automation.nodeId === node.id);
  if (automations.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No automations on this object";
    wrap.append(empty);
  }
  for (const automation of automations) {
    const row = document.createElement("div");
    row.className = "automation-row";
    const name = document.createElement("span");
    name.className = "automation-name";
    name.textContent = automation.propertyId;
    const meta = document.createElement("span");
    meta.className = "automation-meta";
    meta.textContent = `${automation.keyframes.length} key${automation.keyframes.length === 1 ? "" : "s"}`;
    const actions = document.createElement("span");
    actions.className = "automation-actions";
    const key = document.createElement("button");
    key.type = "button";
    key.className = "icon";
    key.title = "Add keyframe at playhead";
    key.append(icon("keyframe", 12));
    key.addEventListener("click", () => {
      addKeyframe(node.id, automation.propertyId);
      refreshInspector();
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "icon";
    remove.title = "Remove automation";
    remove.append(icon("delete", 12));
    remove.addEventListener("click", () => {
      project.automations = project.automations.filter((entry) => entry !== automation);
      refreshInspector();
      refreshStack();
    });
    actions.append(key, remove);
    row.append(name, meta, actions);
    wrap.append(row);
  }

  const adder = document.createElement("div");
  adder.className = "automation-add";
  const select = document.createElement("select");
  for (const path of node.animatablePaths()) {
    const option = document.createElement("option");
    option.value = path;
    option.textContent = path;
    select.append(option);
  }
  const add = document.createElement("button");
  add.type = "button";
  add.className = "mini accent";
  add.textContent = "Add automation";
  add.addEventListener("click", () => {
    if (!select.value) return;
    ensureAutomation(node.id, select.value);
    addKeyframe(node.id, select.value);
    refreshInspector();
    refreshStack();
  });
  adder.append(select, add);
  wrap.append(adder);
  body.append(wrap);
}

/**
 * Point an item at an analyzer. Ownership is stored on the analyzer - the item
 * only mirrors it for display - so this is the single write path for both.
 */
function bindAnalyzer(node: AnyNode, analyzerId: string | null): void {
  const owner = assignUser(project.analyzers, node.id, analyzerId);
  node.analyzerId = owner?.id ?? null;
}

/* ------------------------------------------------------------------ */
/* Right-panel sections: Layers / Items / Analyzers / Automations /    */
/* Effects                                                             */
/* ------------------------------------------------------------------ */

const stackRoot = $("#panel-stack");

function stackRow(
  label: string,
  meta?: string,
  onOpen?: () => void,
  selected = false,
  lead?: IconName,
): HTMLElement {
  const row = document.createElement("button");
  row.type = "button";
  row.className = `panel-row${selected ? " selected" : ""}`;
  const name = document.createElement("span");
  name.className = "panel-row-name";
  if (lead) name.append(icon(lead, 12));
  name.append(document.createTextNode(label));
  row.append(name);
  if (meta) {
    const value = document.createElement("span");
    value.className = "panel-row-meta";
    value.textContent = meta;
    row.append(value);
  }
  if (onOpen) row.addEventListener("click", onOpen);
  return row;
}

function stackSection(title: string, content: HTMLElement[] | string, open = false): HTMLElement {
  const section = document.createElement("section");
  section.className = `group${open ? "" : " collapsed"}`;

  const head = document.createElement("button");
  head.type = "button";
  head.className = "group-head";
  const twist = document.createElement("span");
  twist.className = "twist";
  twist.append(icon(open ? "expand_more" : "chevron_right", 14));
  head.append(twist, document.createTextNode(title));
  head.addEventListener("click", () => {
    const collapsed = section.classList.toggle("collapsed");
    twist.replaceChildren(icon(collapsed ? "chevron_right" : "expand_more", 14));
  });

  const body = document.createElement("div");
  body.className = "group-body";
  if (typeof content === "string") {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = content;
    body.append(empty);
  } else {
    body.append(...content);
  }

  section.append(head, body);
  return section;
}

function refreshStack(): void {
  stackRoot.textContent = "";
  const node = selectedId ? findNode(selectedId) : null;

  stackRoot.append(
    stackSection("Layers", node ? [stackRow("Layer 1", node.typeLabel)] : "No object selected"),
  );

  const items = project.nodes.map((item) => {
    const row = stackRow(item.name, item.typeLabel, () => select(item.id), item.id === selectedId);
    // Reference drag-to-bind: drag an item onto an analyzer row in the left
    // Analyzers panel.
    row.draggable = true;
    row.addEventListener("dragstart", (event) => {
      draggedStackNodeId = item.id;
      row.classList.add("dragging");
      event.dataTransfer?.setData("text/plain", item.id);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "link";
    });
    row.addEventListener("dragend", () => {
      draggedStackNodeId = null;
      row.classList.remove("dragging");
      document
        .querySelectorAll(".analyzer.drop-target")
        .forEach((entry) => entry.classList.remove("drop-target"));
    });
    return row;
  });
  stackRoot.append(stackSection("Items", items.length ? items : "No objects", true));

  stackRoot.append(
    stackSection(
      "Analyzers",
      [
        stackRow(
          "Audio analyser",
          `${spectrum.sourceLabel} · ${spectrum.tier}`,
          () => setStatus(`Analyser: ${spectrum.sourceLabel} · fft ${spectrum.tier}`),
        ),
      ],
      false,
    ),
  );

  const automations = node
    ? project.automations.filter((automation) => automation.nodeId === node.id)
    : [];
  stackRoot.append(
    stackSection(
      "Automations",
      automations.length
        ? automations.map((automation) =>
            stackRow(
              automation.propertyId,
              `${automation.keyframes.length} keys`,
              () => setStatus(`${automation.propertyId}: ${automation.keyframes.length} keyframes`),
            ),
          )
        : "No automations",
      false,
    ),
  );

  stackRoot.append(
    stackSection(
      "Effects",
      (() => {
        const rows = project.effects.map((effect) => {
          const row = stackRow(
            effect.name,
            describeTargets(effect),
            () => {
              setEffectEnabled(effect, !effect.enabled);
            },
            false,
            effect.enabled ? "visibility" : "visibility_off",
          );
          row.title = describeTargetNames(effect);
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "panel-row-del";
          remove.title = `Remove ${effect.name}`;
          remove.append(icon("close", 12));
          remove.addEventListener("click", (event) => {
            event.stopPropagation();
            removeEffect(effect);
          });
          row.append(remove);
          return row;
        });

        const add = document.createElement("button");
        add.type = "button";
        add.className = "panel-row panel-row-add";
        add.append(icon("add", 12), document.createTextNode("Add effect"));
        add.addEventListener("click", () => openAddEffectDialog());
        rows.push(add);

        return rows;
      })(),
      project.effects.length > 0,
    ),
  );
}

const COMPOSITION_KEY = "studio:composition";

/** Composition settings that survive a reload. */
function persistComposition(): void {
  const snapshot = {
    name: project.name,
    width: project.width,
    height: project.height,
    fps: project.fps,
    bpm: project.bpm,
    duration: project.duration,
    background: project.background,
    volume: project.volume,
    spectrumLayerColorMode: project.spectrumLayerColorMode,
    spectrumLayerColorShift: project.spectrumLayerColorShift,
  };
  try {
    localStorage.setItem(COMPOSITION_KEY, JSON.stringify(snapshot));
  } catch {
    /* storage may be unavailable */
  }
}

function loadComposition(): void {
  try {
    const raw = localStorage.getItem(COMPOSITION_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw) as Partial<typeof project>;
    if (typeof saved.name === "string") project.name = saved.name;
    if (typeof saved.width === "number") project.width = saved.width;
    if (typeof saved.height === "number") project.height = saved.height;
    if (typeof saved.fps === "number") project.fps = saved.fps;
    if (typeof saved.bpm === "number" && saved.bpm > 0) project.bpm = saved.bpm;
    if (typeof saved.duration === "number") project.duration = saved.duration;
    if (typeof saved.background === "string") project.background = saved.background;
    if (typeof saved.volume === "number") project.volume = saved.volume;
    if (saved.spectrumLayerColorMode === "lighten" || saved.spectrumLayerColorMode === "darken") {
      project.spectrumLayerColorMode = saved.spectrumLayerColorMode;
    } else if (saved.spectrumLayerColorMode) {
      // Older builds stored Off/Fixed/Cycle; the reference always shifts.
      project.spectrumLayerColorMode = "lighten";
    }
    if (typeof saved.spectrumLayerColorShift === "number") {
      project.spectrumLayerColorShift =
        saved.spectrumLayerColorShift > 1
          ? saved.spectrumLayerColorShift / 360
          : saved.spectrumLayerColorShift;
    }
  } catch {
    /* ignore malformed state */
  }
}

/** Push the project's Audio-object settings into the live WebAudio chain. */
function applyAudioSettings(): void {
  const settings = project.audioSettings;
  audio.configure({
    volume: project.volume / 100,
    muted: project.muted,
    bassBoost: settings.bassBoost,
    frequency: settings.frequency,
    playbackRate: settings.playbackRate,
    attenuator: settings.attenuator,
    additionalGainDb: settings.additionalGainDb,
    compressor: settings.compressor,
  });
  // The reference reprocesses the track when these settings change; the
  // analysers (and therefore the visuals) follow the processed buffer.
  void refreshAnalyserAudio().then(() => {
    refreshTree();
    refreshInspector();
  });
}

/** Composition settings dialog: every project-level property in one place. */
function openCompositionSettings(): void {
  document.querySelector(".modal-backdrop")?.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.setAttribute("role", "dialog");

  const head = document.createElement("header");
  head.className = "modal-head modal-head-row";
  head.append(icon("settings", 16), document.createTextNode("Render settings"));
  const closeRender = document.createElement("button");
  closeRender.type = "button";
  closeRender.className = "icon";
  closeRender.title = "Close";
  closeRender.append(icon("close", 14));
  closeRender.addEventListener("click", () => backdrop.remove());
  head.append(closeRender);

  const body = document.createElement("div");
  body.className = "modal-body";

  const row = (label: string, control: HTMLElement): HTMLElement => {
    const wrap = document.createElement("div");
    wrap.className = "modal-row";
    const name = document.createElement("label");
    name.textContent = label;
    wrap.append(name, control);
    return wrap;
  };

  const text = (value: string): HTMLInputElement => {
    const input = document.createElement("input");
    input.type = "text";
    input.value = value;
    return input;
  };

  const number = (value: number, min: number, max: number, step = 1): HTMLInputElement => {
    const input = document.createElement("input");
    input.type = "number";
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(value);
    return input;
  };

  const widthInput = number(project.width, 320, 3840, 2);
  const heightInput = number(project.height, 180, 2160, 2);
  const fpsInput = number(project.fps, 1, 120, 1);
  const bpmInput = number(project.bpm, 30, 300, 1);
  const durationInput = number(project.duration, 1, 600, 0.1);
  const backgroundInput = text(project.background);

  // Reference "set background image": a real Image item lives in a Background
  // Layer, so the thumbnail shows exactly what the canvas composites.
  const backgroundPicker = document.createElement("div");
  backgroundPicker.className = "file-picker";
  const backgroundThumb = document.createElement("button");
  backgroundThumb.type = "button";
  backgroundThumb.className = "file-thumb";
  const backgroundActions = document.createElement("div");
  backgroundActions.className = "file-actions";
  const backgroundUpload = document.createElement("button");
  backgroundUpload.type = "button";
  backgroundUpload.className = "mini";
  const backgroundClear = document.createElement("button");
  backgroundClear.type = "button";
  backgroundClear.className = "mini";
  backgroundClear.textContent = "Remove";
  backgroundActions.append(backgroundUpload, backgroundClear);
  backgroundPicker.append(backgroundThumb, backgroundActions);

  const paintBackground = (): void => {
    const url = backgroundImageUrl();
    backgroundThumb.title = url ? "Replace background image" : "Upload background image";
    backgroundThumb.replaceChildren();
    if (url) {
      const img = document.createElement("img");
      img.src = url;
      img.alt = "";
      backgroundThumb.append(img);
    } else {
      backgroundThumb.append(icon("image", 15));
    }
    backgroundUpload.textContent = url ? "Replace" : "Upload";
    backgroundClear.hidden = !url;
  };

  const pickBackground = (): void => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      setBackgroundImage(await readFileAsDataUrl(file), file.name);
      paintBackground();
    });
    input.click();
  };
  backgroundThumb.addEventListener("click", pickBackground);
  backgroundUpload.addEventListener("click", pickBackground);
  backgroundClear.addEventListener("click", () => {
    setBackgroundImage(null, "");
    paintBackground();
  });
  paintBackground();

  // Reference WebGLManager exposes a fixed resolution list (module 8b8da8bb).
  const resolutionSelect = document.createElement("select");
  const presets = [
    "1280x720",
    "1920x1080",
    "2560x1440",
    "3840x2160",
    "1080x1080",
    "1080x1350",
    "1080x1920",
    "720x1280",
  ];
  const currentResolution = `${project.width}x${project.height}`;
  if (!presets.includes(currentResolution)) {
    const custom = document.createElement("option");
    custom.value = currentResolution;
    custom.textContent = `${currentResolution} (custom)`;
    custom.selected = true;
    resolutionSelect.append(custom);
  }
  for (const preset of presets) {
    const option = document.createElement("option");
    option.value = preset;
    option.textContent = preset;
    if (preset === currentResolution) option.selected = true;
    resolutionSelect.append(option);
  }
  resolutionSelect.addEventListener("change", () => {
    const [width, height] = resolutionSelect.value.split("x").map(Number);
    widthInput.value = String(width);
    heightInput.value = String(height);
  });
  const syncResolutionSelect = (): void => {
    const value = `${Math.round(Number(widthInput.value))}x${Math.round(Number(heightInput.value))}`;
    const match = [...resolutionSelect.options].find((option) => option.value === value);
    if (match) resolutionSelect.value = value;
  };
  widthInput.addEventListener("change", syncResolutionSelect);
  heightInput.addEventListener("change", syncResolutionSelect);

  const globals = project.globals.slice(0, 5);
  while (globals.length < 5) globals.push(0);
  const globalInputs = globals.map((value) => number(value, -1000, 1000, 0.01));

  body.append(
    row("Resolution", resolutionSelect),
    row("Width", widthInput),
    row("Height", heightInput),
    row("Frame rate", fpsInput),
    row("Tempo (BPM)", bpmInput),
    row("Duration", durationInput),
    row("Background", backgroundInput),
    row("Background image", backgroundPicker),
    ...globalInputs.map((input, index) => row(`Global g${index + 1}`, input)),
  );

  const note = document.createElement("p");
  note.className = "modal-note";
  note.textContent =
    "Global variables can be referenced in shaders as u_g1 to u_g5, or in Math automations as g1 to g5.";
  body.append(note);

  const foot = document.createElement("footer");
  foot.className = "modal-foot";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());

  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "accent pill";
  apply.textContent = "Apply";
  apply.addEventListener("click", () => {
    const capture = () => ({
      width: project.width,
      height: project.height,
      fps: project.fps,
      bpm: project.bpm,
      duration: project.duration,
      background: project.background,
      globals: [...project.globals],
    });
    const before = capture();
    project.width = Math.max(16, Math.round(Number(widthInput.value)));
    project.height = Math.max(16, Math.round(Number(heightInput.value)));
    project.fps = Math.max(1, Math.round(Number(fpsInput.value)));
    project.bpm = Math.max(1, Number(bpmInput.value) || 120);
    project.duration = Math.max(0.1, Number(durationInput.value));
    project.background = backgroundInput.value.trim() || project.background;
    project.globals = globalInputs.map((input, index) => {
      const value = Number(input.value);
      return Number.isFinite(value) ? value : (project.globals[index] ?? 0);
    });
    const after = capture();
    const applySettings = (state: typeof before): void => {
      project.width = state.width;
      project.height = state.height;
      project.fps = state.fps;
      project.bpm = state.bpm;
      project.duration = state.duration;
      project.background = state.background;
      project.globals = [...state.globals];
      applyAudioSettings();
      renderer.resize();
      refreshInspector();
      persistComposition();
      timeline.render(time, selectedId);
    };
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      history.push({
        label: "render settings",
        undo: () => applySettings(before),
        redo: () => applySettings(after),
      });
    }
    $("#project-name").textContent = project.name;
    applyAudioSettings();
    renderer.resize();
    refreshInspector();
    persistComposition();
    setStatus(
      `Render settings: ${project.width}×${project.height} @ ${project.fps} fps · ${project.duration}s.`,
    );
    backdrop.remove();
  });

  foot.append(cancel, apply);
  modal.append(head, body, foot);
  backdrop.append(modal);
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  document.body.append(backdrop);
  resolutionSelect.focus();
}

/** Reference Audio object: source info plus the processing chain. */
function openAudioProcessing(): void {
  document.querySelector(".modal-backdrop")?.remove();
  const settings = project.audioSettings;

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.setAttribute("role", "dialog");
  const head = document.createElement("header");
  head.className = "modal-head modal-head-row";
  head.append(icon("music_note", 16), document.createTextNode("Audio processing"));
  const closeAudio = document.createElement("button");
  closeAudio.type = "button";
  closeAudio.className = "icon";
  closeAudio.title = "Close";
  closeAudio.append(icon("close", 14));
  closeAudio.addEventListener("click", () => backdrop.remove());
  head.append(closeAudio);
  const body = document.createElement("div");
  body.className = "modal-body";

  const row = (label: string, control: HTMLElement): HTMLElement => {
    const wrap = document.createElement("div");
    wrap.className = "modal-row";
    const name = document.createElement("label");
    name.textContent = label;
    wrap.append(name, control);
    return wrap;
  };
  const range = (value: number, min: number, max: number, step: number): HTMLInputElement => {
    const input = document.createElement("input");
    input.type = "range";
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    input.value = String(value);
    return input;
  };
  const number = (
    value: number,
    min: number,
    max: number | null,
    step: number,
  ): HTMLInputElement => {
    const input = document.createElement("input");
    input.type = "number";
    input.min = String(min);
    if (max !== null) input.max = String(max);
    input.step = String(step);
    input.value = String(value);
    return input;
  };
  const check = (value: boolean): HTMLInputElement => {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = value;
    return input;
  };

  const buffer = audioBuffer;
  const info = document.createElement("p");
  info.className = "modal-note";
  info.textContent = buffer
    ? `${spectrum.sourceLabel} · ${buffer.duration.toFixed(2)}s · ${buffer.sampleRate} Hz · fft ${spectrum.tier}`
    : `${spectrum.sourceLabel} · fft ${spectrum.tier}`;

  const volumeInput = range(project.volume, 0, 100, 1);
  const mutedInput = check(project.muted);
  const bassInput = number(settings.bassBoost, 0, 15, 0.1);
  const frequencyInput = number(settings.frequency, 10, 200, 1);
  const rateInput = number(settings.playbackRate, 0.25, null, 0.01);
  const compressorInput = check(settings.compressor);
  const attenuatorInput = check(settings.attenuator);
  const gainInput = number(settings.additionalGainDb, -10, 10, 0.1);
  const syncAttenuator = () => {
    // Reference constraint: additional gain is only editable while the
    // attenuator is enabled.
    gainInput.disabled = !attenuatorInput.checked;
  };
  attenuatorInput.addEventListener("change", syncAttenuator);
  syncAttenuator();

  body.append(
    info,
    row("Volume", volumeInput),
    row("Muted", mutedInput),
    row("Bass boost", bassInput),
    row("Filter frequency", frequencyInput),
    row("Speed multiplier", rateInput),
    row("Enable limiter", compressorInput),
    row("Enable attenuator", attenuatorInput),
    row("Additional gain", gainInput),
  );

  const foot = document.createElement("footer");
  foot.className = "modal-foot";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());
  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "accent pill";
  apply.textContent = "Apply";
  apply.addEventListener("click", () => {
    const capture = () => ({
      volume: project.volume,
      muted: project.muted,
      bassBoost: settings.bassBoost,
      frequency: settings.frequency,
      playbackRate: settings.playbackRate,
      compressor: settings.compressor,
      attenuator: settings.attenuator,
      additionalGainDb: settings.additionalGainDb,
    });
    const before = capture();
    project.volume = Number(volumeInput.value);
    project.muted = mutedInput.checked;
    settings.bassBoost = Number(bassInput.value);
    settings.frequency = Number(frequencyInput.value);
    settings.playbackRate = Number(rateInput.value);
    settings.compressor = compressorInput.checked;
    settings.attenuator = attenuatorInput.checked;
    settings.additionalGainDb = Number(gainInput.value);
    const after = capture();
    const applySettings = (state: typeof before): void => {
      project.volume = state.volume;
      project.muted = state.muted;
      settings.bassBoost = state.bassBoost;
      settings.frequency = state.frequency;
      settings.playbackRate = state.playbackRate;
      settings.compressor = state.compressor;
      settings.attenuator = state.attenuator;
      settings.additionalGainDb = state.additionalGainDb;
      applyAudioSettings();
      persistComposition();
      refreshInspector();
    };
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      history.push({
        label: "audio settings",
        undo: () => applySettings(before),
        redo: () => applySettings(after),
      });
    }
    applyAudioSettings();
    persistComposition();
    setStatus("Audio processing settings applied.");
    backdrop.remove();
  });
  foot.append(cancel, apply);

  modal.append(head, body, foot);
  backdrop.append(modal);
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  document.body.append(backdrop);
  volumeInput.focus();
}

/** Modal scaffolding shared by the info dialogs (changelog, warnings). */
function openModalShell(
  title: string,
  iconName: IconName,
): { backdrop: HTMLElement; body: HTMLElement; foot: HTMLElement } {
  document.querySelector(".modal-backdrop")?.remove();
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.setAttribute("role", "dialog");

  const head = document.createElement("header");
  head.className = "modal-head modal-head-row";
  head.append(icon(iconName, 16), document.createTextNode(title));

  const close = document.createElement("button");
  close.type = "button";
  close.className = "icon";
  close.title = "Close";
  close.append(icon("close", 14));
  close.addEventListener("click", () => backdrop.remove());
  head.append(close);

  const body = document.createElement("div");
  body.className = "modal-body";

  const foot = document.createElement("footer");
  foot.className = "modal-foot";

  modal.append(head, body, foot);
  backdrop.append(modal);
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  document.body.append(backdrop);
  return { backdrop, body, foot };
}

/** Reference “Add Item” catalogue: search, dimension filter, item cards. */
function openAddItemDialog(layerId?: string): void {
  const layer =
    project.layers.find((entry) => entry.id === layerId) ??
    project.layers.find((entry) => entry.id === selectedLayerId) ??
    project.layers[0];
  const dimension = layer ? layerDimension(layer) : null;
  const { backdrop, body, foot } = openModalShell("Add Item", "add");

  const note = document.createElement("p");
  note.className = "modal-note";
  note.textContent = dimension
    ? `This is a ${dimension} layer. You should keep 2D and 3D items in separate layers.`
    : "Empty layers accept 2D or 3D items; the choice locks the layer's dimension.";
  body.append(note);

  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Search items";
  search.className = "catalogue-search";
  body.append(search);

  const grid = document.createElement("div");
  grid.className = "add-item-grid";
  body.append(grid);

  const items = CATALOGUE_ITEMS.filter((item) => !dimension || item.dimension === dimension);
  const render = (): void => {
    grid.textContent = "";
    const query = search.value.trim().toLowerCase();
    for (const item of items.filter((entry) => entry.name.toLowerCase().includes(query))) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "add-item-card";
      const name = document.createElement("span");
      name.textContent = item.name;
      const tag = document.createElement("span");
      tag.className = "add-item-tag";
      tag.textContent = item.dimension;
      button.append(name, tag);
      button.addEventListener("click", () => {
        addNodeOfKind(item.kind, item.name, layer?.id);
        backdrop.remove();
      });
      grid.append(button);
    }
  };
  search.addEventListener("input", render);
  render();

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());
  foot.append(cancel);
}

/** Human-readable target list, e.g. "global", "Spectrum", or "2 targets". */function describeTargets(effect: EffectInstance): string {
  if (effect.targets.length === 0) return "no target";
  if (effect.targets.length === 1) return describeTargetName(effect.targets[0]);
  return `${effect.targets.length} targets`;
}

function describeTargetName(id: string): string {
  if (id === GLOBAL_TARGET) return "global";
  return project.layers.find((layer) => layer.id === id)?.name ?? findNode(id)?.name ?? "missing target";
}

/** Every target by name, for a row tooltip. */
function describeTargetNames(effect: EffectInstance): string {
  return effect.targets.map(describeTargetName).join(", ");
}

function addEffect(type: string, targets: readonly string[]): void {
  const effect = createEffect(type, targets, () => newId("effect"));
  if (!effect) {
    const entry = EFFECT_CATALOGUE.find((definition) => definition.type === type);
    setStatus(`${entry?.name ?? type} is in the catalogue but not implemented yet.`);
    return;
  }
  project.effects.push(effect);
  const index = project.effects.length - 1;
  history.push({
    label: `add ${effect.name}`,
    undo: () => {
      project.effects = project.effects.filter((entry) => entry !== effect);
      refreshEffectViews();
    },
    redo: () => {
      project.effects.splice(Math.min(index, project.effects.length), 0, effect);
      refreshEffectViews();
    },
  });
  refreshStack();
  setStatus(`Added ${effect.name} to ${describeTargetNames(effect)}.`);
}

/** Refresh whichever view is showing effects (undo may run from any panel). */
function refreshEffectViews(): void {
  if (leftPanel === "effects") renderEffectPanel();
  refreshStack();
}

/** Remove an effect as one undo step (reference REMOVE_OBJECTS). */
function removeEffect(effect: EffectInstance): void {
  const index = project.effects.indexOf(effect);
  if (index < 0) return;
  const apply = (present: boolean): void => {
    if (present && !project.effects.includes(effect)) {
      project.effects.splice(Math.min(index, project.effects.length), 0, effect);
    } else if (!present) {
      project.effects = project.effects.filter((entry) => entry !== effect);
    }
    refreshEffectViews();
  };
  apply(false);
  history.push({
    label: `remove ${effect.name}`,
    undo: () => apply(true),
    redo: () => apply(false),
  });
  setStatus(`Removed ${effect.name}.`);
}

let expandedEffectId: string | null = null;

/** Reference panel switch: flat list vs effects grouped by their connections. */
let effectShowConnections = false;

/** Collapsed layer groups in the connections view, keyed by target id. */
const collapsedEffectGroups = new Set<string>();

/**
 * One effect row with its parameters inline, shared by the flat list and the
 * connections view. Returns the wrapper so the caller decides where it goes.
 */
function effectRow(effect: EffectInstance, target?: string): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "analyzer";

    const head = document.createElement("div");
    head.className = "analyzer-head";
    head.setAttribute("role", "button");
    head.tabIndex = 0;
    const name = document.createElement("span");
    name.className = "analyzer-name";
    name.append(icon(effect.enabled ? "visibility" : "visibility_off", 12));
    name.append(document.createTextNode(effect.name));
    const art = effectThumbnail(definitionsFor(effect.type)?.name ?? effect.name);
    const meta = document.createElement("span");
    meta.className = "analyzer-count";
    meta.textContent = target ? describeTargetName(target) : describeTargets(effect);
    meta.title = describeTargetNames(effect);

    // The reference reveals Rename / Toggle / Delete on row hover in addition
    // to the context menu.
    const actions = document.createElement("div");
    actions.className = "analyzer-row-actions";
    actions.append(
      panelIconButton("Rename", "text_fields", () => startEffectRename(effect, wrap, name)),
      panelIconButton(
        effect.enabled ? "Disable" : "Enable",
        effect.enabled ? "visibility" : "visibility_off",
        () => {
          setEffectEnabled(effect, !effect.enabled);
        },
      ),
      panelIconButton("Delete", "delete", () => removeEffect(effect)),
    );
    if (art) {
      const thumb = document.createElement("span");
      thumb.className = "effect-row-art";
      thumb.style.backgroundImage = `url("${art}")`;
      head.append(thumb);
    }
    head.append(name, meta, actions);
    head.addEventListener("click", () => {
      expandedEffectId = expandedEffectId === effect.id ? null : effect.id;
      renderEffectPanel();
    });
    // Reference row menu: Toggle / Rename, with the same icons.
    head.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      showMenuAt(event.clientX, event.clientY, [
        {
          label: "Toggle",
          icon: "power_settings_new",
          action: () => {
            setEffectEnabled(effect, !effect.enabled);
          },
        },
        {
          label: "Rename",
          icon: "text_fields",
          action: () => startEffectRename(effect, wrap, name),
        },
      ]);
    });
    wrap.append(head);

    if (expandedEffectId === effect.id) {
      const definition = definitionsFor(effect.type);
      for (const spec of definition?.params ?? []) {
        const row = document.createElement("div");
        row.className = "field";
        const label = document.createElement("label");
        label.textContent = spec.label;
        const current = effect.params[spec.key] ?? spec.default;

        if (spec.kind === "select" || spec.kind === "layer") {
          const input = document.createElement("select");
          const options =
            spec.kind === "layer"
              ? [
                  { value: "Screen", label: "Screen" },
                  ...project.layers.map((layer) => ({
                    value: layer.id,
                    label: `${layer.name}${layer.renderToBuffer ? "" : " (no buffer)"}`,
                  })),
                ]
              : (spec.options ?? []).map((option) => ({ value: option, label: option }));
          for (const option of options) {
            const item = document.createElement("option");
            item.value = option.value;
            item.textContent = option.label;
            item.selected = option.value === String(current);
            input.append(item);
          }
          input.addEventListener("change", () => {
            effect.params[spec.key] = input.value;
          });
          row.append(label, input);
          wrap.append(row);
          continue;
        }

        if (spec.kind === "text") {
          const input = document.createElement("input");
          input.type = "text";
          input.value = String(current);
          input.addEventListener("change", () => {
            effect.params[spec.key] = input.value;
          });
          row.append(label, input);
          wrap.append(row);
          continue;
        }

        if (spec.kind === "image") {
          const input = document.createElement("input");
          input.type = "url";
          input.placeholder = "Image URL";
          input.value = String(current);
          const file = document.createElement("input");
          file.type = "file";
          file.accept = "image/*";
          file.addEventListener("change", () => {
            const selected = file.files?.[0];
            if (!selected) return;
            const reader = new FileReader();
            reader.addEventListener("load", () => {
              const url = String(reader.result ?? "");
              input.value = url;
              effect.params[spec.key] = url;
            });
            reader.readAsDataURL(selected);
          });
          input.addEventListener("change", () => {
            effect.params[spec.key] = input.value;
          });
          row.append(label, input, file);
          wrap.append(row);
          continue;
        }

        if (spec.kind === "color") {
          const input = document.createElement("input");
          input.type = "color";
          input.value = String(current);
          const value = document.createElement("span");
          value.className = "value";
          value.textContent = input.value;
          input.addEventListener("input", () => {
            effect.params[spec.key] = input.value;
            value.textContent = input.value;
          });
          row.append(label, input, value);
          wrap.append(row);
          continue;
        }

        if (spec.kind === "boolean") {
          const input = document.createElement("input");
          input.type = "checkbox";
          input.checked = Boolean(current);
          const value = document.createElement("span");
          value.className = "value";
          value.textContent = input.checked ? "On" : "Off";
          input.addEventListener("change", () => {
            effect.params[spec.key] = input.checked;
            value.textContent = input.checked ? "On" : "Off";
          });
          row.append(label, input, value);
          wrap.append(row);
          continue;
        }

        const input = document.createElement("input");
        input.type = "range";
        input.min = String(spec.min);
        input.max = String(spec.max);
        input.step = String(spec.step ?? 1);
        input.value = String(current);
        const value = document.createElement("span");
        value.className = "value";
        value.textContent = `${input.value}${spec.unit ?? ""}`;
        input.addEventListener("input", () => {
          const next = Number(input.value);
          effect.params[spec.key] = next;
          value.textContent = `${input.value}${spec.unit ?? ""}`;
          // Editing at the playhead also moves the keyframe under it, matching
          // how keyframed item properties behave.
          const automation = project.automations.find((a) =>
            a.connections[effect.id]?.includes(spec.key),
          );
          const key = automation?.keyframes.find((k) => Math.abs(k.t - time) < 0.05);
          if (key) key.value = next;
        });

        // Keyframe this parameter at the playhead, creating its automation.
        const key = document.createElement("button");
        key.type = "button";
        key.className = "icon";
        key.title = `Keyframe ${effect.name} ${spec.label}`;
        key.append(icon("keyframe", 12));
        key.addEventListener("click", (event) => {
          event.stopPropagation();
          addEffectKeyframe(effect, spec.key);
        });

        row.append(label, input, value, key);
        wrap.append(row);
      }

      const actions = document.createElement("div");
      actions.className = "analyzer-actions";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "mini";
      toggle.textContent = effect.enabled ? "Disable" : "Enable";
      toggle.addEventListener("click", () => {
        setEffectEnabled(effect, !effect.enabled);
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "mini";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        expandedEffectId = null;
        removeEffect(effect);
      });
      actions.append(toggle, remove);
      wrap.append(actions);
    }

    return wrap;
}

/** Rename an effect inline, matching the reference's context-menu rename. */
function startEffectRename(effect: EffectInstance, wrap: HTMLElement, label: HTMLElement): void {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "inline-rename";
  input.value = effect.name;
  label.replaceWith(input);
  input.focus();
  input.select();
  const commit = (save: boolean): void => {
    const name = input.value.trim();
    const before = effect.name;
    if (save && name && name !== before) {
      effect.name = name;
      history.push({
        label: "rename effect",
        undo: () => {
          effect.name = before;
          refreshTree();
          refreshInspector();
        },
        redo: () => {
          effect.name = name;
          refreshTree();
          refreshInspector();
        },
      });
      setStatus(`Renamed effect to ${name}.`);
    }
    input.remove();
    refreshTree();
    refreshInspector();
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") commit(true);
    if (event.key === "Escape") commit(false);
  });
  input.addEventListener("blur", () => commit(true));
  void wrap;
}

/** Effects panel: flat list, or the reference's connections view by target. */
function renderEffectPanel(): void {
  const root = treeRoot;
  root.textContent = "";

  if (project.effects.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No effects applied";
    root.append(empty);
  }

  if (effectShowConnections) {
    // `connections` in the reference is the set of targets an effect feeds, so
    // the grouped view is target → effects (layers, then the global frame).
    const groups = new Map<string, EffectInstance[]>();
    for (const effect of project.effects) {
      for (const target of effect.targets.length > 0 ? effect.targets : [GLOBAL_TARGET]) {
        const list = groups.get(target) ?? [];
        list.push(effect);
        groups.set(target, list);
      }
    }
    for (const [target, effects] of groups) {
      const group = document.createElement("div");
      group.className = "effect-group";

      const head = document.createElement("button");
      head.type = "button";
      head.className = "analyzer-head";
      head.title = `Layer: ${describeTargetName(target)}`;
      const name = document.createElement("span");
      name.className = "analyzer-name";
      name.append(icon(collapsedEffectGroups.has(target) ? "chevron_right" : "expand_more", 12));
      name.append(icon("layers", 12));
      name.append(document.createTextNode(describeTargetName(target)));
      const count = document.createElement("span");
      count.className = "analyzer-count";
      count.textContent = String(effects.length);
      head.append(name, count);
      head.addEventListener("click", () => {
        if (collapsedEffectGroups.has(target)) collapsedEffectGroups.delete(target);
        else collapsedEffectGroups.add(target);
        renderEffectPanel();
      });
      group.append(head);

      if (!collapsedEffectGroups.has(target)) {
        for (const effect of effects) group.append(effectRow(effect, target));
      }
      root.append(group);
    }
    return;
  }

  for (const effect of project.effects) root.append(effectRow(effect));
}

/** Reference “Add effect” modal: category sidebar, effect list, Cancel / Add. */
function openAddEffectDialog(preselected?: readonly string[]): void {
  const { backdrop, body, foot } = openModalShell("Add effect", "tune");
  backdrop.querySelector<HTMLElement>(".modal")?.classList.add("modal-wide");

  const target = document.createElement("select");
  target.className = "catalogue-target";
  // Vizzy scopes post-processing effects to the composition root or a Layer,
  // not to individual items. Multiple so one effect can feed several layers.
  target.multiple = true;
  target.size = Math.min(5, project.layers.length + 1);
  target.title = "Ctrl-click to feed more than one layer";
  const globals = document.createElement("option");
  globals.value = GLOBAL_TARGET;
  globals.textContent = "Global (whole composition)";
  globals.selected = !preselected || preselected.length === 0;
  target.append(globals);
  for (const layer of project.layers) {
    const option = document.createElement("option");
    option.value = layer.id;
    option.textContent = `${layer.name}${layer.enabled ? "" : " (disabled)"}`;
    option.selected = Boolean(preselected?.includes(layer.id));
    target.append(option);
  }

  const layout = document.createElement("div");
  layout.className = "add-effect";

  const sidebar = document.createElement("div");
  sidebar.className = "add-effect-cats";

  const list = document.createElement("div");
  list.className = "add-effect-list";
  layout.append(sidebar, list);

  let category = "All";
  const pending = new Map<string, string>();

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "primary";
  addButton.disabled = true;
  addButton.textContent = "Add";

  const renderList = (): void => {
    sidebar.textContent = "";
    for (const name of ["All", ...EFFECT_CATEGORIES]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `add-effect-cat${category === name ? " active" : ""}`;
      button.textContent = name;
      button.addEventListener("click", () => {
        category = name;
        renderList();
      });
      sidebar.append(button);
    }

    list.textContent = "";
    for (const definition of EFFECT_CATALOGUE) {
      if (category !== "All" && definition.category !== category) continue;
      const item = document.createElement("button");
      item.type = "button";
      item.className = `add-effect-item${pending.has(definition.type) ? " pending" : ""}`;
      item.disabled = !definition.implemented;
      const name = document.createElement("span");
      name.textContent = definition.name;
      const meta = document.createElement("span");
      meta.className = "catalogue-meta";
      meta.textContent = definition.implemented ? definition.category : "not implemented";
      const text = document.createElement("span");
      text.className = "add-effect-text";
      text.append(name, meta);
      const thumbnail = effectThumbnail(definition.name);
      if (thumbnail) {
        const art = document.createElement("span");
        art.className = "add-effect-art";
        art.style.backgroundImage = `url("${thumbnail}")`;
        item.append(art);
      }
      item.append(text);
      item.addEventListener("click", () => {
        if (pending.has(definition.type)) pending.delete(definition.type);
        else pending.set(definition.type, definition.name);
        addButton.disabled = pending.size === 0;
        addButton.textContent = pending.size > 0 ? `Add (${pending.size})` : "Add";
        renderList();
      });
      list.append(item);
    }
  };
  renderList();

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());

  addButton.addEventListener("click", () => {
    const targets = [...target.selectedOptions].map((option) => option.value);
    for (const type of pending.keys()) {
      addEffect(type, targets.length > 0 ? targets : [GLOBAL_TARGET]);
    }
    backdrop.remove();
    renderEffectPanel();
  });

  body.append(target, layout);
  foot.append(cancel, addButton);
}


/** Effects panel header button labels live with the panel; see renderEffectPanel. */

/** Row label for an automation, whether it drives an item or an effect param. */
function automationLabel(automation: Automation): string {
  if (automation.nodeId) {
    const node = findNode(automation.nodeId);
    const property = automation.propertyId.split(".").pop() ?? automation.propertyId;
    return `${automation.name ?? node?.name ?? "Item"} - ${property}`;
  }
  for (const [effectId, params] of Object.entries(automation.connections)) {
    const effect = project.effects.find((item) => item.id === effectId);
    return `${effect?.name ?? "Effect"} - ${params[0] ?? "param"}`;
  }
  return automation.name ?? "Automation";
}

/** Analyzer rows expand by default; the reference keeps its own expansion state. */
const collapsedAnalyzers = new Set<string>();

/** Inline rename for an analyzer row, like the reference's rename action. */
function startAnalyzerRename(analyzer: { name: string }, label: HTMLElement): void {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "inline-rename";
  input.value = analyzer.name;
  label.replaceWith(input);
  input.focus();
  input.select();
  const commit = (save: boolean): void => {
    const name = input.value.trim();
    const before = analyzer.name;
    if (save && name && name !== before) {
      analyzer.name = name;
      history.push({
        label: "rename analyzer",
        undo: () => {
          analyzer.name = before;
          refreshTree();
          refreshInspector();
        },
        redo: () => {
          analyzer.name = name;
          refreshTree();
          refreshInspector();
        },
      });
      setStatus(`Renamed analyzer to ${name}.`);
    }
    input.remove();
    refreshTree();
    refreshInspector();
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") commit(true);
    if (event.key === "Escape") commit(false);
  });
  input.addEventListener("blur", () => commit(true));
}

/**
 * Analyzers panel: the reference's "Audio Analyzers" list. Selecting an analyzer
 * opens its controllers in the inspector; each row expands into the items it
 * drives ("This analyzer is not being used" when empty).
 */
/** The reference's permanent Default analyzer (`analyzer:default`). */
function isDefaultAnalyzer(analyzer: Analyzer): boolean {
  return analyzer.name === "Default" || analyzer.id === "analyzer:default";
}

/** Remove an analyzer and clear its selection (reference context menu `Delete`). */
function deleteAnalyzer(analyzer: Analyzer): void {
  // The reference's row hides Delete for the Default analyzer; its menu keeps
  // the item but the Default object is permanent.
  if (isDefaultAnalyzer(analyzer)) return;
  const index = project.analyzers.indexOf(analyzer);
  if (index < 0) return;
  const ownership = snapshotOwnership(project.analyzers);

  const remove = (): void => {
    project.analyzers = project.analyzers.filter((entry) => entry !== analyzer);
    if (selectedAnalyzerId === analyzer.id) selectedAnalyzerId = null;
    // Free the wasm context slot so a later analyzer does not inherit its bands.
    renderer.retainAnalyzers(project.analyzers.map((entry) => entry.id));
    renderAnalyzerPanel();
    refreshInspector();
  };

  remove();
  history.push({
    label: `remove ${analyzer.name}`,
    undo: () => {
      project.analyzers.splice(Math.min(index, project.analyzers.length), 0, analyzer);
      restoreOwnership(project.analyzers, ownership);
      renderer.retainAnalyzers(project.analyzers.map((entry) => entry.id));
      renderAnalyzerPanel();
      refreshInspector();
    },
    redo: remove,
  });
  setStatus(`Removed ${analyzer.name}.`);
}

/**
 * Reference analyzer connections. `audioAnalyzers[id].connections` maps an
 * object to the controllers bound to that analyzer:
 *
 * - `["audioAnalyzer"]` is an object-level binding;
 * - `["spectrum_layer:0:audioAnalyzer"]` is a per-layer binding on a Spectrum.
 *
 * The panel shows one row per controller, labelling layer rows
 * `"<container label> - <object name>"` (reference `V`), so a Spectrum with
 * four layers lists `Layer 1 - Spectrum` … `Layer 4 - Spectrum`.
 */
function analyzerUserRows(
  analyzer: Analyzer,
): { label: string; node?: AnyNode; automation?: Automation; layerId?: string }[] {
  const rows: { label: string; node?: AnyNode; automation?: Automation; layerId?: string }[] = [];
  for (const node of project.nodes) {
    // A Spectrum has no object-level analyzer controller: only its layers bind.
    if (node instanceof SpectrumNode) {
      node.layers.forEach((layer, index) => {
        if (layer.audioAnalyzer === analyzer.id) {
          rows.push({ label: `Layer ${index + 1} - ${node.name}`, node });
        }
      });
      continue;
    }
    if (node.analyzerId === analyzer.id) rows.push({ label: node.name, node });
  }
  // Composition layers own an `audioAnalyzer` controller too, so the analyzer
  // panel lists the layer by name (reference `layer:*` connections).
  for (const layer of project.layers) {
    if (layer.audioAnalyzer === analyzer.id) rows.push({ label: layer.name, layerId: layer.id });
  }
  // Reference connections include automations, e.g. `audioImpact` rows carrying
  // an `audioAnalyzer` controller.
  for (const automation of project.automations) {
    if (automation.audioAnalyzer === analyzer.id) {
      rows.push({ label: automation.name ?? "Automation", automation });
    }
  }
  return rows;
}

function renderAnalyzerPanel(): void {
  const root = treeRoot;
  root.textContent = "";

  // Reference info alert, dismissed for good via localStorage.
  if (localStorage.getItem("hasDisplayedAnalyzerInfo") !== "true") {
    const info = document.createElement("div");
    info.className = "panel-alert";
    const text = document.createElement("span");
    text.textContent =
      "Audio analyzers allow you to change how things react to audio. Here you can see your analyzers and which items are using them";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "icon panel-alert-close";
    close.title = "Don't show info text again";
    close.append(icon("close", 12));
    close.addEventListener("click", () => {
      localStorage.setItem("hasDisplayedAnalyzerInfo", "true");
      renderAnalyzerPanel();
    });
    info.append(text, close);
    root.append(info);
  }

  for (const analyzer of project.analyzers) {
    const users = analyzerUserRows(analyzer);
    const collapsed = collapsedAnalyzers.has(analyzer.id);

    const wrap = document.createElement("div");
    wrap.className = "analyzer";

    // Drop an item from the right-hand stack (or the composition tree) here to
    // bind it to this analyzer, matching the reference drag-to-bind flow.
    const draggedNode = (event: DragEvent): AnyNode | null => {
      const id =
        draggedStackNodeId ??
        draggedNodeId2 ??
        event.dataTransfer?.getData("text/plain") ??
        null;
      return id ? findNode(id) ?? null : null;
    };
    wrap.addEventListener("dragover", (event) => {
      if (!draggedNode(event)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "link";
      wrap.classList.add("drop-target");
    });
    wrap.addEventListener("dragleave", () => wrap.classList.remove("drop-target"));
    wrap.addEventListener("drop", (event) => {
      event.preventDefault();
      const node = draggedNode(event);
      wrap.classList.remove("drop-target");
      draggedStackNodeId = null;
      if (!node) return;
      bindAnalyzer(node, analyzer.id);
      renderAnalyzerPanel();
      refreshTree();
      refreshStack();
      refreshInspector();
      setStatus(`${node.name} now uses ${analyzer.name}.`);
    });

    const head = document.createElement("div");
    head.className = "analyzer-head";

    const twist = document.createElement("button");
    twist.type = "button";
    twist.className = "icon analyzer-twist";
    twist.title = collapsed ? "Show connections" : "Hide connections";
    twist.append(icon(collapsed ? "chevron_right" : "expand_more", 12));
    twist.addEventListener("click", () => {
      if (collapsed) collapsedAnalyzers.delete(analyzer.id);
      else collapsedAnalyzers.add(analyzer.id);
      renderAnalyzerPanel();
    });

    const name = document.createElement("button");
    name.type = "button";
    name.className = `analyzer-name analyzer-select${selectedAnalyzerId === analyzer.id ? " selected" : ""}`;
    name.textContent = analyzer.name;
    name.title = "Edit analyzer settings";
    name.addEventListener("click", () => selectAnalyzer(analyzer.id));

    const actions = document.createElement("div");
    actions.className = "analyzer-row-actions";
    actions.append(
      panelIconButton("Rename", "text_fields", () => startAnalyzerRename(analyzer, name)),
    );
    // The reference's Default analyzer hides the hover Delete button.
    if (!isDefaultAnalyzer(analyzer)) {
      actions.append(panelIconButton("Delete", "delete", () => deleteAnalyzer(analyzer)));
    }

    // Reference analyzer context menu: Edit / Rename / Delete.
    head.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      showMenuAt(event.clientX, event.clientY, [
        { label: "Edit", icon: "edit", action: () => selectAnalyzer(analyzer.id) },
        { label: "Rename", icon: "text_fields", action: () => startAnalyzerRename(analyzer, name) },
        // The menu item stays available for Default, exactly like the reference;
        // `deleteAnalyzer` refuses to remove it.
        { label: "Delete", icon: "delete", action: () => deleteAnalyzer(analyzer) },
      ]);
    });

    head.append(twist, name, actions);
    wrap.append(head);

    if (!collapsed) {
      if (users.length === 0) {
        const empty = document.createElement("div");
        empty.className = "analyzer-empty";
        empty.textContent = "This analyzer is not being used";
        wrap.append(empty);
      }
      for (const user of users) {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "analyzer-user";
        row.textContent = user.label;
        const edit = (): void => {
          if (user.automation) focusAutomation(user.automation);
          else if (user.node) select(user.node.id);
          else if (user.layerId) selectLayer(user.layerId);
        };
        row.addEventListener("click", edit);
        // Reference object context menu: Edit.
        row.addEventListener("contextmenu", (event) => {
          event.preventDefault();
          showMenuAt(event.clientX, event.clientY, [{ label: "Edit", icon: "edit", action: edit }]);
        });
        wrap.append(row);
      }
    }

    root.append(wrap);
  }
}

/** Automations expanded in the panel, by object identity. */
const expandedAutomations = new Set<Automation>();

/**
 * Reference analyzer "Edit" on an automation connection: select that row and
 * reveal its controllers. Our automation controllers live in the expanded
 * automations panel rather than the inspector.
 */
function focusAutomation(automation: Automation): void {
  setLeftPanel("automations");
  selectedAutomations = new Set([automation.id]);
  expandedAutomations.add(automation);
  renderAutomationPanel();
}

/** Automations expanded in a group folder, by object identity. */
const collapsedGroups = new Set<string>();

/**
 * Reference `G` (`addAutomationsToNewFolder`): move the selected automations
 * into a new folder. Selecting anything else is refused with the reference's
 * two messages.
 */
function addAutomationsToNewFolder(): void {
  const selected = project.automations.filter((automation) =>
    selectedAutomations.has(automation.id),
  );
  const otherSelection =
    selectedId !== null ||
    selectedLayerId !== null ||
    selectedAnalyzerId !== null ||
    multiSelection.size > 0;
  if (otherSelection) {
    setStatus("Only automations can be added to a folder");
    return;
  }
  if (selected.length === 0) {
    setStatus("No items selected to add to new folder");
    return;
  }

  const beforeGroups = structuredClone(project.automationGroups);
  const beforeMembers = selected.map((automation) => [automation.id, automation.groupId] as const);

  const group: AutomationGroup = { id: newId("group"), name: "Untitled group", children: [] };
  for (const automation of selected) {
    const previous = project.automationGroups.find((entry) => entry.id === automation.groupId);
    if (previous) previous.children = previous.children.filter((id) => id !== automation.id);
    if (!group.children.includes(automation.id)) group.children.push(automation.id);
    automation.groupId = group.id;
  }
  project.automationGroups.push(group);

  const afterGroups = structuredClone(project.automationGroups);
  const afterMembers = selected.map((automation) => [automation.id, automation.groupId] as const);
  const restore = (
    groups: AutomationGroup[],
    members: readonly (readonly [string, string | undefined])[],
  ): void => {
    project.automationGroups = structuredClone(groups);
    for (const [id, groupId] of members) {
      const automation = project.automations.find((entry) => entry.id === id);
      if (automation) automation.groupId = groupId as string | undefined;
    }
    refreshTree();
  };
  history.push({
    label: "add automations to new folder",
    undo: () => restore(beforeGroups, beforeMembers),
    redo: () => restore(afterGroups, afterMembers),
  });
  setStatus(`Added ${selected.length} automations to new folder`);
  refreshTree();
}

/** Controller ids an automation drives, the label the reference renders. */
function automationControllerIds(automation: Automation): string[] {
  const ids = [
    ...(automation.nodeId && automation.propertyId ? [automation.propertyId] : []),
    ...Object.values(automation.connections).flat(),
  ];
  return [...new Set(ids)];
}

/** Reference connection groups: one row per object the automation drives. */
interface AutomationObjectGroup {
  objectId: string;
  label: string;
  controllers: string[];
}

function automationObjectLabel(objectId: string): string {
  const node = findNode(objectId);
  if (node) return node.name;
  return project.effects.find((effect) => effect.id === objectId)?.name ?? objectId;
}

function automationConnectionGroups(automation: Automation): AutomationObjectGroup[] {
  const groups = new Map<string, string[]>();
  if (automation.nodeId && automation.propertyId) {
    groups.set(automation.nodeId, [automation.propertyId]);
  }
  for (const [objectId, controllers] of Object.entries(automation.connections)) {
    const list = groups.get(objectId) ?? [];
    for (const controller of controllers) {
      if (!list.includes(controller)) list.push(controller);
    }
    groups.set(objectId, list);
  }
  return [...groups].map(([objectId, controllers]) => ({
    objectId,
    label: automationObjectLabel(objectId),
    controllers,
  }));
}

/** The automation's live output, as written to its first target this frame. */
function automationOutput(automation: Automation): number {
  if (automation.nodeId && automation.propertyId) {
    const node = findNode(automation.nodeId);
    if (node) return Number(node.readNumber(automation.propertyId)) || 0;
  }
  for (const [objectId, controllers] of Object.entries(automation.connections)) {
    const controller = controllers[0];
    if (!controller) continue;
    const node = findNode(objectId);
    if (node) return Number(node.readNumber(controller)) || 0;
    const effect = project.effects.find((entry) => entry.id === objectId);
    if (effect) return Number(effect.params[controller]) || 0;
  }
  return 0;
}

/**
 * Reference `_id` OSCILLOSCOPE controller: a small rolling plot of the
 * automation's output. It stops as soon as the row is re-rendered away.
 */
function startAutomationScope(canvas: HTMLCanvasElement, automation: Automation): void {
  const samples: number[] = [];
  const draw = (): void => {
    if (!canvas.isConnected) return;
    samples.push(automationOutput(automation));
    if (samples.length > canvas.width) samples.shift();
    const context = canvas.getContext("2d");
    if (context) {
      context.clearRect(0, 0, canvas.width, canvas.height);
      const low = Math.min(...samples);
      const high = Math.max(...samples);
      const range = high - low || 1;
      context.strokeStyle = "#7fd1ff";
      context.lineWidth = 1;
      context.beginPath();
      samples.forEach((sample, index) => {
        const x = (index / Math.max(1, samples.length - 1)) * (canvas.width - 1);
        const y = canvas.height - 1 - ((sample - low) / range) * (canvas.height - 2);
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      });
      context.stroke();
    }
    requestAnimationFrame(draw);
  };
  requestAnimationFrame(draw);
}

/** Friendly name for a driven controller, for the expanded detail rows. */
function automationControllerLabel(automation: Automation, controllerId: string): string {
  for (const [objectId, ids] of Object.entries(automation.connections)) {
    if (!ids.includes(controllerId)) continue;
    const effect = project.effects.find((item) => item.id === objectId);
    if (effect) {
      const spec = definitionsFor(effect.type)?.params.find((entry) => entry.key === controllerId);
      return `${effect.name} · ${spec?.label ?? controllerId}`;
    }
    const node = findNode(objectId);
    return `${node?.name ?? "Item"} · ${controllerId.split(".").pop() ?? controllerId}`;
  }
  const node = automation.nodeId ? findNode(automation.nodeId) : null;
  return `${node?.name ?? "Item"} · ${controllerId.split(".").pop() ?? controllerId}`;
}

/** Reference `SET_AUTOMATION_GROUP_NAME`. */
function renameAutomationGroup(group: AutomationGroup): void {
  const next = prompt("Group name", group.name);
  if (next === null) return;
  const name = next.trim();
  if (!name || name === group.name) return;
  const before = group.name;
  group.name = name;
  history.push({
    label: "rename automation folder",
    undo: () => {
      group.name = before;
      refreshTree();
    },
    redo: () => {
      group.name = name;
      refreshTree();
    },
  });
  refreshTree();
  setStatus(`Renamed folder to ${name}.`);
}

/** Reference `REMOVE_AUTOMATION_GROUP`: the rows survive, ungrouped. */
function removeAutomationGroup(group: AutomationGroup): void {
  const beforeGroups = structuredClone(project.automationGroups);
  const members = group.children.slice();
  const restore = (groups: AutomationGroup[], groupId: string | undefined): void => {
    project.automationGroups = structuredClone(groups);
    for (const id of members) {
      const automation = project.automations.find((entry) => entry.id === id);
      if (automation) automation.groupId = groupId;
    }
    refreshTree();
  };
  removeAutomationGroupMembers(group.id, members);
  const afterGroups = structuredClone(project.automationGroups);
  history.push({
    label: "remove automation folder",
    undo: () => restore(beforeGroups, group.id),
    redo: () => restore(afterGroups, undefined),
  });
  setStatus(`Removed folder ${group.name}.`);
  refreshTree();
}

/** Detach rows from a group and drop the group itself. */
function removeAutomationGroupMembers(groupId: string, members: readonly string[]): void {
  project.automationGroups = project.automationGroups.filter((entry) => entry.id !== groupId);
  for (const id of members) {
    const automation = project.automations.find((entry) => entry.id === id);
    if (automation && automation.groupId === groupId) automation.groupId = undefined;
  }
}

/**
 * Reference `TOGGLE_ENABLE` on a folder: if every child is disabled it enables
 * them all, otherwise it disables them all.
 */
function setAutomationGroupEnabled(group: AutomationGroup, enabled: boolean): void {
  const members = group.children
    .map((id) => project.automations.find((automation) => automation.id === id))
    .filter((automation): automation is Automation => Boolean(automation));
  const before = members.map((automation) => [automation, automation.enabled] as const);
  const apply = (value: boolean): void => {
    for (const automation of members) automation.enabled = value;
    refreshTree();
  };
  apply(enabled);
  history.push({
    label: enabled ? "enable automations" : "disable automations",
    undo: () => {
      for (const [automation, value] of before) automation.enabled = value;
      refreshTree();
    },
    redo: () => apply(enabled),
  });
  setStatus(`${enabled ? "Enabled" : "Disabled"} ${members.length} automations.`);
}

/** Reference `REMOVE_OBJECT_FROM_AUTOMATION`. */
function removeObjectFromAutomation(automation: Automation, objectId: string | undefined): void {
  const before = {
    nodeId: automation.nodeId,
    propertyId: automation.propertyId,
    connections: structuredClone(automation.connections),
  };
  const apply = (state: typeof before): void => {
    automation.nodeId = state.nodeId;
    automation.propertyId = state.propertyId;
    automation.connections = structuredClone(state.connections);
    renderAutomationPanel();
  };
  if (objectId) {
    delete automation.connections[objectId];
    if (objectId === automation.nodeId) {
      automation.nodeId = "";
      automation.propertyId = "";
    }
  } else {
    automation.nodeId = "";
    automation.propertyId = "";
  }
  const after = {
    nodeId: automation.nodeId,
    propertyId: automation.propertyId,
    connections: structuredClone(automation.connections),
  };
  history.push({
    label: "remove object from automation",
    undo: () => apply(before),
    redo: () => apply(after),
  });
  setStatus("Removed the object from the automation.");
  renderAutomationPanel();
}

/** Reference "Add controller to automation" on a connected object. */
function addControllerToAutomation(
  automation: Automation,
  objectId: string,
  controllerId: string,
): void {
  const before = {
    nodeId: automation.nodeId,
    propertyId: automation.propertyId,
    connections: structuredClone(automation.connections),
  };
  const apply = (state: typeof before): void => {
    automation.nodeId = state.nodeId;
    automation.propertyId = state.propertyId;
    automation.connections = structuredClone(state.connections);
    renderAutomationPanel();
    refreshInspector();
  };
  const list = automation.connections[objectId] ?? [];
  if (!list.includes(controllerId)) list.push(controllerId);
  automation.connections[objectId] = list;
  // A node row without a primary controller adopts the new one.
  if (!automation.nodeId && findNode(objectId)) {
    automation.nodeId = objectId;
    automation.propertyId = controllerId;
  }
  const after = {
    nodeId: automation.nodeId,
    propertyId: automation.propertyId,
    connections: structuredClone(automation.connections),
  };
  history.push({
    label: "add controller to automation",
    undo: () => apply(before),
    redo: () => apply(after),
  });
  setStatus("Added the controller to the automation.");
  renderAutomationPanel();
  refreshInspector();
}

/** Reference header "Add folder": an empty Untitled group, undoable. */
function addAutomationFolder(): void {
  const group: AutomationGroup = { id: newId("group"), name: "Untitled group", children: [] };
  project.automationGroups.push(group);
  history.push({
    label: "add automation folder",
    undo: () => {
      project.automationGroups = project.automationGroups.filter((entry) => entry.id !== group.id);
      refreshTree();
    },
    redo: () => {
      project.automationGroups.push(group);
      refreshTree();
    },
  });
  setStatus("Added folder Untitled group");
  refreshTree();
}

/** Reference `RENAME` on an automation row. */
function renameAutomation(automation: Automation): void {
  const next = prompt("Automation name", automation.name ?? "");
  if (next === null) return;
  const name = next.trim();
  const before = automation.name;
  automation.name = name || undefined;
  history.push({
    label: "rename automation",
    undo: () => {
      automation.name = before;
      renderAutomationPanel();
    },
    redo: () => {
      automation.name = name || undefined;
      renderAutomationPanel();
    },
  });
  renderAutomationPanel();
  setStatus(name ? `Renamed automation to ${name}.` : "Cleared the automation name.");
}

/** Reference `DELETE_AUTOMATION`: also detach it from its folder. */
function deleteAutomation(automation: Automation): void {
  const index = project.automations.indexOf(automation);
  if (index < 0) return;
  const groupId = automation.groupId;
  const wasExpanded = expandedAutomations.has(automation);
  const wasSelected = selectedAutomations.has(automation.id);

  const remove = (): void => {
    project.automations = project.automations.filter((entry) => entry !== automation);
    for (const group of project.automationGroups) {
      group.children = group.children.filter((id) => id !== automation.id);
    }
    selectedAutomations.delete(automation.id);
    expandedAutomations.delete(automation);
    refreshAutomationViews();
  };

  remove();
  history.push({
    label: "remove automation",
    undo: () => {
      project.automations.splice(Math.min(index, project.automations.length), 0, automation);
      if (groupId) {
        const group = project.automationGroups.find((entry) => entry.id === groupId);
        if (group && !group.children.includes(automation.id)) group.children.push(automation.id);
        automation.groupId = groupId;
      }
      if (wasExpanded) expandedAutomations.add(automation);
      if (wasSelected) selectedAutomations.add(automation.id);
      refreshAutomationViews();
    },
    redo: remove,
  });
}

/** Refresh whichever view shows automations (undo may run from any panel). */
function refreshAutomationViews(): void {
  if (leftPanel === "automations") renderAutomationPanel();
  refreshInspector();
  refreshStack();
}

/** Reference automations panel: Keyframes / Math / Audio Impact sections. */
function renderAutomationPanel(): void {
  const root = treeRoot;
  root.textContent = "";

  const sections: { label: string; type: Automation["type"] }[] = [
    { label: "Keyframes", type: "property" },
    { label: "Math", type: "math" },
    { label: "Audio Impact", type: "audioImpact" },
  ];
  const grouped = new Set(project.automationGroups.flatMap((group) => group.children));
  const panels: { label: string; items: Automation[]; group?: AutomationGroup }[] = [];
  for (const section of sections) {
    const items = project.automations.filter(
      (automation) => automation.type === section.type && !grouped.has(automation.id),
    );
    if (items.length === 0) continue;
    // Reference sorts keyframe automations by their start time.
    items.sort((a, b) => (a.keyframes[0]?.t ?? 0) - (b.keyframes[0]?.t ?? 0));
    panels.push({ label: section.label, items });
  }
  for (const group of project.automationGroups) {
    const items = group.children
      .map((id) => project.automations.find((automation) => automation.id === id))
      .filter((automation): automation is Automation => Boolean(automation));
    panels.push({ label: group.name, items, group });
  }

  for (const panel of panels) {
    const items = panel.items;
    const wrap = document.createElement("div");
    wrap.className = "analyzer";
    const head = document.createElement("div");
    head.className = "analyzer-head";
    const title = document.createElement("span");
    title.className = "analyzer-name";
    if (panel.group) {
      const open = !collapsedGroups.has(panel.group.id);
      title.append(
        icon(open ? "expand_more" : "chevron_right", 12),
        icon("folder", 12),
        document.createTextNode(panel.label),
      );
      head.addEventListener("click", () => {
        if (collapsedGroups.has(panel.group!.id)) collapsedGroups.delete(panel.group!.id);
        else collapsedGroups.add(panel.group!.id);
        renderAutomationPanel();
      });
      // Reference `automation_group_context_menu`: Rename / Toggle / Remove.
      head.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        const group = panel.group!;
        const allOff =
          items.length > 0 && items.every((automation) => automation.enabled === false);
        showMenuAt(event.clientX, event.clientY, [
          { label: "Rename", icon: "text_fields", action: () => renameAutomationGroup(group) },
          {
            label: "Toggle",
            icon: "visibility_off",
            action: () => setAutomationGroupEnabled(group, allOff),
          },
          { label: "Remove", icon: "delete", action: () => removeAutomationGroup(group) },
        ]);
      });
      const rename = document.createElement("button");
      rename.type = "button";
      rename.className = "mini";
      rename.title = "Rename folder";
      rename.append(icon("edit", 12));
      rename.addEventListener("click", (event) => {
        event.stopPropagation();
        renameAutomationGroup(panel.group!);
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "mini";
      remove.title = "Remove folder";
      remove.append(icon("close", 12));
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        removeAutomationGroup(panel.group!);
      });
      // Reference `TOGGLE_ENABLE`: if every child is disabled, enable them all;
      // otherwise disable them all.
      const allDisabled =
        items.length > 0 && items.every((automation) => automation.enabled === false);
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "mini";
      toggle.title = allDisabled ? "Enable" : "Disable";
      toggle.append(icon(allDisabled ? "visibility" : "visibility_off", 12));
      toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        setAutomationGroupEnabled(panel.group!, allDisabled);
      });
      const count = document.createElement("span");
      count.className = "analyzer-count";
      count.textContent = String(items.length);
      head.classList.toggle("disabled", allDisabled);
      head.append(title, count, toggle, rename, remove);
    } else {
      title.append(icon("expand_more", 12), document.createTextNode(panel.label));
      const count = document.createElement("span");
      count.className = "analyzer-count";
      count.textContent = String(items.length);
      head.append(title, count);
    }
    wrap.append(head);
    if (panel.group && collapsedGroups.has(panel.group.id)) {
      root.append(wrap);
      continue;
    }

    for (const automation of items) {
      const expanded = expandedAutomations.has(automation);
      const row = document.createElement("button");
      row.type = "button";
      row.className = "analyzer-user automation-row";
      row.classList.toggle("selected", selectedAutomations.has(automation.id));
      const ids = automationControllerIds(automation);
      const label = ids.length > 0 ? ids.join(", ") : automationLabel(automation);
      // The chevron expands the row; clicking the row selects the automation
      // (reference object selection, which `G` groups).
      const chevron = document.createElement("span");
      chevron.className = "automation-chevron";
      chevron.append(icon(expanded ? "expand_more" : "chevron_right", 12));
      chevron.addEventListener("click", (event) => {
        event.stopPropagation();
        if (expandedAutomations.has(automation)) expandedAutomations.delete(automation);
        else expandedAutomations.add(automation);
        renderAutomationPanel();
      });
      // Reference row button: Enable/Disable this automation.
      const enabled = automation.enabled !== false;
      const power = document.createElement("button");
      power.type = "button";
      power.className = "mini";
      power.title = enabled ? "Disable" : "Enable";
      power.append(icon(enabled ? "visibility_off" : "visibility", 12));
      power.addEventListener("click", (event) => {
        event.stopPropagation();
        setAutomationEnabled(automation, !enabled);
      });
      row.classList.toggle("disabled", !enabled);
      row.append(chevron, document.createTextNode(label), power);
      row.title = `${automation.type} · ${automation.keyframes.length} keyframes`;
      row.addEventListener("click", (event) => {
        const additive = event.ctrlKey || event.metaKey;
        if (additive) {
          if (selectedAutomations.has(automation.id)) selectedAutomations.delete(automation.id);
          else selectedAutomations.add(automation.id);
        } else {
          selectedAutomations = new Set([automation.id]);
          multiSelection.clear();
          selectedId = null;
          selectedLayerId = null;
          selectedAnalyzerId = null;
          renderer.setGizmoTarget(null);
        }
        renderAutomationPanel();
        refreshInspector();
      });
      // Reference row menu: Rename / Toggle / Delete.
      row.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        showMenuAt(event.clientX, event.clientY, [
          { label: "Rename", icon: "text_fields", action: () => renameAutomation(automation) },
          {
            label: "Toggle",
            icon: "visibility_off",
            action: () => {
              automation.enabled = automation.enabled === false ? true : false;
              renderAutomationPanel();
            },
          },
          { label: "Delete", icon: "delete", action: () => deleteAutomation(automation) },
        ]);
      });
      wrap.append(row);

      if (!expanded) continue;

      const detail = document.createElement("div");
      detail.className = "automation-detail";
      // Reference groups the detail by connected object, each with its own
      // "Add controller" menu and "Remove object" action.
      for (const group of automationConnectionGroups(automation)) {
        const objectHead = document.createElement("div");
        objectHead.className = "automation-object";
        objectHead.append(icon("tune", 11));
        objectHead.append(document.createTextNode(group.label));
        const objectActions = document.createElement("span");
        objectActions.className = "automation-object-actions";

        const addController = document.createElement("button");
        addController.type = "button";
        addController.className = "icon";
        addController.title = "Add controller to automation";
        addController.append(icon("add", 11));
        addController.addEventListener("click", (event) => {
          event.stopPropagation();
          const existing = new Set(group.controllers);
          const targets = automationTargets().filter(
            (target) => target.id === group.objectId && !existing.has(target.param),
          );
          showMenuAt(
            event.clientX,
            event.clientY,
            targets.length
              ? targets.map((target) => ({
                  label: target.label,
                  icon: "add",
                  action: () => addControllerToAutomation(automation, group.objectId, target.param),
                }))
              : [{ label: "No controllers left", disabled: true, action: () => {} }],
          );
        });

        const removeObject = document.createElement("button");
        removeObject.type = "button";
        removeObject.className = "icon";
        removeObject.title = "Remove object from automation";
        removeObject.append(icon("delete", 11));
        removeObject.addEventListener("click", (event) => {
          event.stopPropagation();
          removeObjectFromAutomation(automation, group.objectId);
        });

        objectActions.append(addController, removeObject);
        objectHead.append(objectActions);
        detail.append(objectHead);

        for (const controllerId of group.controllers) {
          const line = document.createElement("div");
          line.className = "automation-controller";
          line.append(icon("tune", 11));
          line.append(document.createTextNode(automationControllerLabel(automation, controllerId)));
          // Reference `automation_object_context_menu`: drop one object's
          // connection from this automation.
          line.addEventListener("contextmenu", (event) => {
            event.preventDefault();
            showMenuAt(event.clientX, event.clientY, [
              {
                label: "Remove object from automation",
                icon: "delete",
                action: () => removeObjectFromAutomation(automation, group.objectId),
              },
            ]);
          });
          detail.append(line);
        }
      }

      // The reference expands an automation into its own controllers: start/end
      // value and time plus interpolation for keyframes, the formula for math,
      // and the mapping for audio impact. Editing here writes straight through.
      const detailNumber = (
        label: string,
        value: number,
        commit: (next: number) => void,
        options: { min?: number; max?: number; step?: number } = {},
      ): HTMLElement => {
        const row = document.createElement("div");
        row.className = "automation-field";
        const name = document.createElement("label");
        name.textContent = label;
        const input = document.createElement("input");
        input.type = "number";
        if (options.min !== undefined) input.min = String(options.min);
        if (options.max !== undefined) input.max = String(options.max);
        input.step = String(options.step ?? 0.01);
        input.value = String(value);
        input.addEventListener("change", () => {
          const next = Number(input.value);
          if (!Number.isFinite(next)) {
            input.value = String(value);
            return;
          }
          commit(next);
          refreshInspector();
          setStatus(`${label} updated.`);
        });
        row.append(name, input);
        return row;
      };

      if (automation.type === "property" && automation.keyframes.length > 0) {
        const first = automation.keyframes[0];
        const last = automation.keyframes[automation.keyframes.length - 1];
        detail.append(
          detailNumber("Start value", first.value, (next) => {
            first.value = next;
          }),
          detailNumber(
            "Start time (s)",
            first.t,
            (next) => {
              first.t = next;
              automation.keyframes.sort((a, b) => a.t - b.t);
            },
            { min: 0 },
          ),
          detailNumber("End value", last.value, (next) => {
            last.value = next;
          }),
          detailNumber(
            "End time (s)",
            last.t,
            (next) => {
              last.t = next;
              automation.keyframes.sort((a, b) => a.t - b.t);
            },
            { min: 0 },
          ),
        );
        const row = document.createElement("div");
        row.className = "automation-field";
        const name = document.createElement("label");
        name.textContent = "Interpolation";
        const select = document.createElement("select");
        const easingOptions = KEYFRAME_EASINGS.includes(first.easing)
          ? KEYFRAME_EASINGS
          : [first.easing, ...KEYFRAME_EASINGS];
        for (const value of easingOptions) {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = value;
          option.selected = first.easing === value;
          select.append(option);
        }
        select.addEventListener("change", () => {
          first.easing = select.value as Easing;
          refreshInspector();
        });
        row.append(name, select);
        detail.append(row);
      }

      if (automation.type === "math") {
        const row = document.createElement("div");
        row.className = "automation-field";
        const name = document.createElement("label");
        name.textContent = "Formula";
        const input = document.createElement("input");
        input.type = "text";
        input.className = "automation-formula-input";
        input.value = automation.formula ?? "";
        input.addEventListener("change", () => {
          if (!Formula.isValid(input.value)) {
            input.value = automation.formula ?? "";
            setStatus("Formula is not valid.");
            return;
          }
          automation.formula = input.value;
          refreshInspector();
          setStatus("Math automation updated.");
        });
        row.append(name, input);
        detail.append(row);
      }

      if (automation.type === "audioImpact" && automation.impact) {
        const impact = automation.impact;
        // Reference Automation folder: the Variant info row and a live "Value"
        // oscilloscope of the automation's output.
        const variantRow = document.createElement("div");
        variantRow.className = "automation-field";
        const variantLabel = document.createElement("label");
        variantLabel.textContent = "Variant";
        const variantValue = document.createElement("span");
        variantValue.className = "automation-value";
        variantValue.textContent = "Number";
        variantRow.append(variantLabel, variantValue);
        detail.append(variantRow);

        const scopeRow = document.createElement("div");
        scopeRow.className = "automation-field";
        const scopeLabel = document.createElement("label");
        scopeLabel.textContent = "Value";
        const scope = document.createElement("canvas");
        scope.className = "automation-scope";
        scope.width = 120;
        scope.height = 18;
        scopeRow.append(scopeLabel, scope);
        detail.append(scopeRow);
        startAutomationScope(scope, automation);

        detail.append(
          detailNumber("Min value", impact.min, (next) => {
            impact.min = next;
          }),
          detailNumber("Max value", impact.max, (next) => {
            impact.max = next;
          }),
          detailNumber(
            "Lower limit",
            impact.floor,
            (next) => {
              impact.floor = next;
            },
            { min: 0 },
          ),
          detailNumber(
            "Upper limit",
            impact.ceiling,
            (next) => {
              impact.ceiling = next;
            },
            { min: 0 },
          ),
          detailNumber(
            "Sensitivity",
            impact.sensitivity,
            (next) => {
              impact.sensitivity = next;
            },
            { min: 0, step: 0.1 },
          ),
          detailNumber(
            "Smoothing",
            impact.smoothing,
            (next) => {
              impact.smoothing = next;
            },
            { min: 0, max: 1 },
          ),
        );
        // Reference `isCumulative` controller.
        const cumulativeRow = document.createElement("div");
        cumulativeRow.className = "automation-field";
        const cumulativeLabel = document.createElement("label");
        cumulativeLabel.textContent = "Cumulative";
        const cumulative = document.createElement("input");
        cumulative.type = "checkbox";
        cumulative.checked = impact.cumulative;
        cumulative.addEventListener("change", () => {
          impact.cumulative = cumulative.checked;
        });
        cumulativeRow.append(cumulativeLabel, cumulative);
        detail.append(cumulativeRow);

        // Reference delta controls: amount/threshold are enabled only while
        // delta smoothing is on.
        const deltaRow = document.createElement("div");
        deltaRow.className = "automation-field";
        const deltaLabel = document.createElement("label");
        deltaLabel.textContent = "Delta smooth";
        const deltaSmoothing = document.createElement("input");
        deltaSmoothing.type = "checkbox";
        deltaSmoothing.checked = Boolean(impact.deltaSmoothing);
        deltaSmoothing.addEventListener("change", () => {
          impact.deltaSmoothing = deltaSmoothing.checked;
          renderAutomationPanel();
        });
        deltaRow.append(deltaLabel, deltaSmoothing);
        detail.append(deltaRow);
        const deltaAmount = detailNumber(
          "Delta amount",
          impact.deltaDecay ?? 0.01,
          (next) => {
            impact.deltaDecay = next;
          },
          { min: 0, max: 1 },
        );
        const deltaThreshold = detailNumber(
          "Delta threshold",
          impact.deltaThreshold ?? 0,
          (next) => {
            impact.deltaThreshold = next;
          },
          { min: 0, max: 1 },
        );
        for (const row of [deltaAmount, deltaThreshold]) {
          const input = row.querySelector("input");
          if (input) input.disabled = !impact.deltaSmoothing;
        }
        detail.append(deltaAmount, deltaThreshold);

        // Reference `audioAnalyzer` controller: the impact row can sample a
        // different analyzer from the object it drives.
        const row = document.createElement("div");
        row.className = "automation-field";
        const name = document.createElement("label");
        name.textContent = "Audio analyzer";
        const select = document.createElement("select");
        for (const analyzer of project.analyzers) {
          const option = document.createElement("option");
          option.value = analyzer.id;
          option.textContent = analyzer.name;
          option.selected = analyzer.id === automation.audioAnalyzer;
          select.append(option);
        }
        select.addEventListener("change", () => {
          automation.audioAnalyzer = select.value;
          renderAutomationPanel();
        });
        row.append(name, select);
        detail.append(row);
      }

      const actions = document.createElement("div");
      actions.className = "analyzer-actions";
      const open = document.createElement("button");
      open.type = "button";
      open.className = "mini";
      open.textContent = "Open";
      open.addEventListener("click", (event) => {
        event.stopPropagation();
        openAutomationTarget(automation);
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "mini";
      remove.textContent = "Remove";
      remove.addEventListener("click", (event) => {
        event.stopPropagation();
        deleteAutomation(automation);
      });
      actions.append(open, remove);
      detail.append(actions);
      wrap.append(detail);
    }

    root.append(wrap);
  }

  if (project.automations.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No automations yet";
    root.append(empty);
  }

  const addRow = document.createElement("div");
  addRow.className = "automation-add-row";
  const add = document.createElement("button");
  add.type = "button";
  add.className = "mini";
  add.textContent = "Add automation";
  add.addEventListener("click", () => openAddAutomationDialog());
  addRow.append(add);
  root.append(addRow);
}

/** Jump to whatever an automation drives (its item, or the effect it feeds). */
function openAutomationTarget(automation: Automation): void {
  if (automation.nodeId) {
    select(automation.nodeId);
    return;
  }
  const effectId = Object.keys(automation.connections)[0];
  if (effectId) {
    expandedEffectId = effectId;
    setLeftPanel("effects");
  }
}

/** A controller an automation can drive: an item property or an effect param. */
interface AutomationTarget {
  key: string;
  kind: "node" | "effect";
  id: string;
  param: string;
  label: string;
  value: number;
}

/** Every animatable numeric controller in the project. */
function automationTargets(): AutomationTarget[] {
  const out: AutomationTarget[] = [];
  for (const node of project.nodes) {
    for (const controller of node.createControllerSetups().controllers) {
      if (!controller.animatable) continue;
      if (typeof controller.read() !== "number") continue;
      out.push({
        key: `node:${node.id}|${controller.id}`,
        kind: "node",
        id: node.id,
        param: controller.id,
        label: `${node.name} · ${controller.label}`,
        value: Number(controller.read()),
      });
    }
  }
  for (const effect of project.effects) {
    const definition = definitionsFor(effect.type);
    for (const spec of definition?.params ?? []) {
      if (spec.kind && spec.kind !== "number") continue;
      const value = Number(effect.params[spec.key] ?? spec.default);
      if (!Number.isFinite(value)) continue;
      out.push({
        key: `effect:${effect.id}|${spec.key}`,
        kind: "effect",
        id: effect.id,
        param: spec.key,
        label: `${effect.name} · ${spec.label}`,
        value,
      });
    }
  }
  return out;
}

/**
 * Reference “Add automation” dialog: tabs for the three automation kinds, a
 * target controller picker, and the fields each kind needs.
 */
function openAddAutomationDialog(): void {
  const targets = automationTargets();
  if (targets.length === 0) {
    setStatus("Add an item before automating a controller.");
    return;
  }

  const { backdrop, body, foot } = openModalShell("Add automation", "timeline");
  backdrop.querySelector<HTMLElement>(".modal")?.classList.add("modal-wide");

  const note = document.createElement("p");
  note.className = "modal-note";
  note.textContent =
    "Automations allow you change the appearance and behaviour of things over time";
  body.append(note);

  let type: Automation["type"] = "property";
  const tabs = document.createElement("div");
  tabs.className = "automation-tabs";

  const target = document.createElement("select");
  target.className = "catalogue-target";
  target.title = "Controller to drive";
  for (const entry of targets) {
    const option = document.createElement("option");
    option.value = entry.key;
    option.textContent = entry.label;
    target.append(option);
  }

  const fields = document.createElement("div");
  fields.className = "automation-fields";

  const state = {
    start: Math.round(time * 100) / 100,
    end: Math.round(time * 100) / 100 + 1,
    startValue: targets[0].value,
    endValue: targets[0].value,
    min: 0,
    max: 100,
    sensitivity: 1,
    smoothing: 0,
    formula: "p",
    easing: "ease-in" as Easing,
    analyzerId: project.analyzers[0]?.id ?? "",
  };

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "primary";
  addButton.textContent = "Add automation";

  const numberField = (
    label: string,
    value: number,
    onChange: (next: number) => void,
    options: { min?: number; max?: number; step?: number } = {},
  ): HTMLElement => {
    const row = document.createElement("div");
    row.className = "field";
    const name = document.createElement("label");
    name.textContent = label;
    const input = document.createElement("input");
    input.type = "number";
    if (options.min !== undefined) input.min = String(options.min);
    if (options.max !== undefined) input.max = String(options.max);
    input.step = String(options.step ?? 0.01);
    input.value = String(value);
    input.addEventListener("change", () => {
      const next = Number(input.value);
      if (!Number.isFinite(next)) return;
      onChange(next);
    });
    row.append(name, input);
    return row;
  };

  const renderFields = (): void => {
    fields.textContent = "";
    const selection = targets.find((entry) => entry.key === target.value) ?? targets[0];
    state.startValue = selection.value;
    state.endValue = selection.value;
    state.start = Math.round(time * 100) / 100;
    state.end = state.start + 1;

    if (type === "property") {
      fields.append(
        numberField("Start value", state.startValue, (next) => (state.startValue = next)),
        numberField("Start time (s)", state.start, (next) => (state.start = next), { min: 0 }),
        numberField("End value", state.endValue, (next) => (state.endValue = next)),
        numberField("End time (s)", state.end, (next) => (state.end = next), { min: 0 }),
      );
      const row = document.createElement("div");
      row.className = "field";
      const name = document.createElement("label");
      name.textContent = "Interpolation";
      const select = document.createElement("select");
      for (const value of KEYFRAME_EASINGS) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.append(option);
      }
      state.easing = "ease-in";
      select.value = state.easing;
      select.addEventListener("change", () => {
        state.easing = select.value as typeof state.easing;
      });
      row.append(name, select);
      fields.append(row);
      addButton.disabled = false;
      return;
    }

    if (type === "audioImpact") {
      fields.append(
        numberField("Min value", state.min, (next) => (state.min = next)),
        numberField("Max value", state.max, (next) => (state.max = next)),
        numberField("Sensitivity", state.sensitivity, (next) => (state.sensitivity = next), {
          min: 0,
          step: 0.1,
        }),
        numberField("Smoothing", state.smoothing, (next) => (state.smoothing = next), {
          min: 0,
          max: 1,
        }),
      );
      // Reference `audioAnalyzer` controller (Automation folder).
      const row = document.createElement("div");
      row.className = "field";
      const name = document.createElement("label");
      name.textContent = "Audio analyzer";
      const select = document.createElement("select");
      for (const analyzer of project.analyzers) {
        const option = document.createElement("option");
        option.value = analyzer.id;
        option.textContent = analyzer.name;
        option.selected = analyzer.id === state.analyzerId;
        select.append(option);
      }
      select.addEventListener("change", () => {
        state.analyzerId = select.value;
      });
      row.append(name, select);
      fields.append(row);
      addButton.disabled = false;
      return;
    }

    // Math: the reference's formula box with its keyword help.
    const row = document.createElement("div");
    row.className = "field";
    const name = document.createElement("label");
    name.textContent = "Formula";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "automation-formula-input";
    input.spellcheck = false;
    input.value = state.formula;
    const update = (): void => {
      state.formula = input.value;
      addButton.disabled = !Formula.isValid(state.formula, {
        t: time,
        p: selection.value,
        m: project.audioImpactMax,
        d: audioBuffer?.duration ?? 0,
        g1: project.globals[0],
        g2: project.globals[1],
        g3: project.globals[2],
        g4: project.globals[3],
        g5: project.globals[4],
      });
      help.classList.toggle("invalid", addButton.disabled);
    };
    input.addEventListener("input", update);
    row.append(name, input);
    fields.append(row);

    const help = document.createElement("p");
    help.className = "modal-note automation-help";
    help.textContent =
      "t: time · p: previous value · a: audio impact · m: max impact · d: song duration · u1-u5: user variables · g1-g5: globals · rx/ry: resolution. Angles are degrees, e.g. cos(90) = 0.";
    fields.append(help);
    update();
  };

  for (const [value, label] of [
    ["property", "Keyframe"],
    ["audioImpact", "Audio Impact"],
    ["math", "Math"],
  ] as const) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "automation-tab";
    tab.textContent = label;
    tab.classList.toggle("active", type === value);
    tab.addEventListener("click", () => {
      type = value;
      for (const other of tabs.children) {
        other.classList.toggle("active", other === tab);
      }
      renderFields();
    });
    tabs.append(tab);
  }

  target.addEventListener("change", renderFields);
  renderFields();

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());

  addButton.addEventListener("click", () => {
    const selection = targets.find((entry) => entry.key === target.value) ?? targets[0];
    const automation: Automation = {
      id: newId("automation"),
      type,
      nodeId: selection.kind === "node" ? selection.id : "",
      propertyId: selection.kind === "node" ? selection.param : "",
      connections:
        selection.kind === "effect" ? { [selection.id]: [selection.param] } : {},
      keyframes: [],
    };
    if (type === "property") {
      automation.keyframes = [
        { t: state.start, value: state.startValue, easing: state.easing },
        { t: Math.max(state.start, state.end), value: state.endValue, easing: "linear" },
      ];
    } else if (type === "audioImpact") {
      automation.audioAnalyzer = state.analyzerId || project.analyzers[0]?.id;
      automation.impact = {
        min: state.min,
        max: state.max,
        sensitivity: state.sensitivity,
        smoothing: state.smoothing,
        floor: 0,
        ceiling: 0,
        cumulative: false,
        deltaSmoothing: false,
        deltaDecay: 0.01,
        deltaThreshold: 0,
      };
    } else {
      automation.formula = state.formula;
    }
    project.automations.push(automation);
    const index = project.automations.length - 1;
    // A track loaded before this row existed has no impact normaliser yet, and
    // every impact value would stay pinned at `minValue`.
    if (type === "audioImpact") ensureAudioImpactNormaliser();
    history.push({
      label: `add ${type} automation`,
      undo: () => {
        project.automations = project.automations.filter((entry) => entry !== automation);
        refreshAutomationViews();
      },
      redo: () => {
        project.automations.splice(Math.min(index, project.automations.length), 0, automation);
        refreshAutomationViews();
      },
    });
    backdrop.remove();
    renderAutomationPanel();
    refreshInspector();
    refreshStack();
    setStatus(`Added ${type === "property" ? "keyframe" : type} automation for ${selection.label}.`);
  });

  body.append(tabs, target, fields);
  foot.append(cancel, addButton);
}

let mediaTab = "Uploads";

/** Media library: reusable uploads, split by the reference's tabs. */
function renderMediaPanel(): void {
  const root = treeRoot;
  root.textContent = "";

  const intro = document.createElement("p");
  intro.className = "panel-note";
  intro.textContent =
    "Media uploaded here is reusable across projects. To use something once, drop it straight onto the canvas instead.";
  root.append(intro);

  const tabs = document.createElement("div");
  tabs.className = "catalogue-cats";
  for (const tab of ["Uploads", "Stock", "Audio", "Images", "Videos"]) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `cat-chip${mediaTab === tab ? " active" : ""}`;
    chip.textContent = tab;
    chip.addEventListener("click", () => {
      mediaTab = tab;
      renderMediaPanel();
    });
    tabs.append(chip);
  }
  root.append(tabs);

  if (mediaTab === "Stock") {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Stock media needs an account. Sign in to browse.";
    root.append(empty);
    return;
  }

  const items = assets.list().filter((asset) => {
    if (mediaTab === "Images") return asset.kind === "image";
    if (mediaTab === "Videos") return asset.kind === "video";
    if (mediaTab === "Audio") return false;
    return true;
  });

  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = `No ${mediaTab.toLowerCase()} yet`;
    root.append(empty);
  }

  for (const asset of items) {
    const row = document.createElement("div");
    row.className = "media-item";
    let thumb: HTMLImageElement | HTMLVideoElement;
    if (asset.kind === "video") {
      const video = document.createElement("video");
      video.src = asset.url;
      video.muted = true;
      video.playsInline = true;
      video.preload = "metadata";
      thumb = video;
    } else {
      const image = document.createElement("img");
      image.src = asset.url;
      image.alt = "";
      thumb = image;
    }
    const meta = document.createElement("div");
    const name = document.createElement("div");
    name.className = "media-name";
    name.textContent = asset.name;
    const kind = document.createElement("div");
    kind.className = "media-kind";
    kind.textContent = asset.kind;
    meta.append(name, kind);
    row.append(thumb, meta);
    root.append(row);
  }

  const upload = document.createElement("button");
  upload.type = "button";
  upload.className = "panel-row panel-row-add";
  upload.append(icon("upload", 12), document.createTextNode("Upload media"));
  upload.addEventListener("click", () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = mediaTab === "Audio" ? "audio/*" : "image/*,video/*";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      if (file.type.startsWith("audio/")) {
        setStatus(await loadAudioFromBytes(file.name, new Uint8Array(await file.arrayBuffer())));
      } else if (file.type.startsWith("image/")) {
        await addMediaFromFile(file);
      } else if (file.type.startsWith("video/")) {
        await addVideoFromFile(file);
      } else {
        setStatus(`${file.name}: this file type is not supported.`);
      }
      renderMediaPanel();
    });
    input.click();
  });
  root.append(upload);
}

interface SavedProject {
  id: string;
  name: string;
  savedAt: string;
  width: number;
  height: number;
  /** JPEG data URL captured from the stage canvas. */
  thumbnail?: string;
}

const PROJECTS_KEY = "studio:projects";

function loadSavedProjects(): SavedProject[] {
  try {
    const raw = localStorage.getItem(PROJECTS_KEY);
    const parsed = raw ? (JSON.parse(raw) as SavedProject[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** Projects panel: project settings, saved projects, account entry points. */
function renderProjectsPanel(): void {
  const root = treeRoot;
  root.textContent = "";

  const settings = document.createElement("button");
  settings.type = "button";
  settings.className = "analyzer-user";
  settings.textContent = "Project settings";
  settings.addEventListener("click", openCompositionSettings);
  root.append(settings);

  const heading = document.createElement("div");
  heading.className = "analyzer";
  const head = document.createElement("div");
  head.className = "analyzer-head";
  const label = document.createElement("span");
  label.className = "analyzer-name";
  label.textContent = "Your projects";
  head.append(label);
  heading.append(head);

  const saved = loadSavedProjects();
  if (saved.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No saved projects on this device";
    heading.append(empty);
  }
  for (const entry of saved) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "project-row";
    if (entry.thumbnail) {
      const img = document.createElement("img");
      img.src = entry.thumbnail;
      img.alt = "";
      row.append(img);
    } else {
      const placeholder = document.createElement("span");
      placeholder.className = "project-thumb-empty";
      placeholder.append(icon("image", 14));
      row.append(placeholder);
    }
    const meta = document.createElement("span");
    meta.className = "project-meta";
    const name = document.createElement("span");
    name.className = "media-name";
    name.textContent = entry.name;
    const detail = document.createElement("span");
    detail.className = "media-kind";
    detail.textContent = `${entry.width}×${entry.height}`;
    meta.append(name, detail);
    row.append(meta);
    row.title = `Saved ${new Date(entry.savedAt).toLocaleString()}`;
    row.addEventListener("click", () => void openSavedProject(entry.id));
    heading.append(row);
  }
  root.append(heading);

  const save = document.createElement("button");
  save.type = "button";
  save.className = "panel-row panel-row-add";
  save.append(icon("add", 12), document.createTextNode("Save current project"));
  save.addEventListener("click", () => {
    void saveProjectLocally().then(renderProjectsPanel);
  });
  root.append(save);

  const signIn = document.createElement("button");
  signIn.type = "button";
  signIn.className = "analyzer-user";
  signIn.textContent = "Sign in";
  signIn.addEventListener("click", openAccountDialog);
  root.append(signIn);

  const creations = document.createElement("button");
  creations.type = "button";
  creations.className = "analyzer-user";
  creations.textContent = "Creations (decompiled)";
  creations.title = "Load a captured reference project";
  creations.addEventListener("click", () => void openCreationsBrowser());
  root.append(creations);

  const templates = document.createElement("button");
  templates.type = "button";
  templates.className = "analyzer-user";
  templates.textContent = "Templates";
  templates.addEventListener("click", () => setLeftPanel("templates"));
  root.append(templates);

  const explore = document.createElement("button");
  explore.type = "button";
  explore.className = "analyzer-user";
  explore.textContent = "Explore creations";
  explore.addEventListener("click", () => openCommunity());
  root.append(explore);
}

interface CreationEntry {
  id?: string;
  name?: string;
  description?: string;
  audio?: string;
  file?: string;
  thumbnail?: string;
}

/**
 * Creation browser: every decompiled project under `public/creations/` can be
 * loaded here. This is the in-app counterpart to `test:creation`.
 */
async function openCreationsBrowser(): Promise<void> {
  document.querySelector(".modal-backdrop")?.remove();
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-label", "Creations");

  const head = document.createElement("div");
  head.className = "modal-head";
  const title = document.createElement("strong");
  title.textContent = "Creations";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "icon";
  close.append(icon("close", 14));
  close.title = "Close";
  close.addEventListener("click", () => backdrop.remove());
  head.append(title, close);

  const body = document.createElement("div");
  body.className = "modal-body";
  const intro = document.createElement("p");
  intro.className = "modal-note";
  intro.textContent = "Decompiled reference projects. Loading replaces the current project and its audio.";
  body.append(intro);

  const list = document.createElement("div");
  list.className = "creation-list";
  body.append(list);

  const status = document.createElement("div");
  status.className = "empty";
  status.textContent = "Loading catalogue…";
  body.append(status);

  modal.append(head, body);
  backdrop.append(modal);
  document.body.append(backdrop);

  try {
    const entries = await fetchCreationEntries();
    status.remove();
    intro.textContent = `Decompiled reference projects (${entries.length}). Loading replaces the current project and its audio.`;
    list.before(createCreationFilter(entries.length));
    appendCreationRows(list, entries, () => backdrop.remove());
  } catch (error) {
    status.textContent = `Could not load creations: ${error instanceof Error ? error.message : String(error)}`;
  }
}

/** Filter box for the creations/template lists; matches name, audio and text. */
function createCreationFilter(count: number): HTMLInputElement {
  const filter = document.createElement("input");
  filter.type = "search";
  filter.className = "creation-filter";
  filter.placeholder = `Filter ${count} templates…`;
  filter.setAttribute("aria-label", "Filter templates");
  filter.addEventListener("input", () => {
    const query = filter.value.trim().toLowerCase();
    const list = filter.nextElementSibling;
    if (!list) return;
    for (const item of list.querySelectorAll<HTMLElement>(".creation-item")) {
      item.hidden = query.length > 0 && !(item.dataset.search ?? "").includes(query);
    }
  });
  return filter;
}

async function fetchCreationEntries(): Promise<CreationEntry[]> {
  const response = await fetch("/creations/manifest.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const manifest = (await response.json()) as { creations?: CreationEntry[] };
  return Array.isArray(manifest.creations) ? manifest.creations : [];
}

function appendCreationRows(
  list: HTMLElement,
  entries: readonly CreationEntry[],
  closeParent?: () => void,
): void {
  if (entries.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No creations captured yet.";
    list.append(empty);
    return;
  }
  for (const entry of entries) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "creation-row creation-card";
    row.title = entry.description ?? "";
    row.addEventListener("click", () => confirmCreationLoad(entry, closeParent));

    let thumb: HTMLImageElement | HTMLDivElement;
    if (entry.thumbnail) {
      const image = document.createElement("img");
      image.className = "creation-thumb";
      image.src = entry.thumbnail;
      image.alt = "";
      image.loading = "lazy";
      image.decoding = "async";
      image.addEventListener("error", () => {
        image.classList.add("is-missing");
        image.alt = `${entry.name ?? "Template"} thumbnail unavailable`;
      });
      thumb = image;
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "creation-thumb is-missing";
      thumb = placeholder;
    }

    const name = document.createElement("span");
    name.className = "creation-name";
    name.textContent = entry.name ?? entry.id ?? "Creation";
    const meta = document.createElement("span");
    meta.className = "creation-meta";
    meta.textContent = entry.audio ?? entry.description ?? "";
    row.append(thumb, name, meta);

    const item = document.createElement("div");
    item.className = "creation-item";
    item.dataset.search = [entry.name, entry.description, entry.audio, entry.id]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    item.append(row);
    list.append(item);
  }
}

/** Confirmation popup shown when a template tile is clicked. */
function confirmCreationLoad(entry: CreationEntry, closeParent?: () => void): void {
  closeParent?.();
  document.querySelector(".modal-backdrop")?.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-label", `Load ${entry.name ?? "template"}`);

  const head = document.createElement("div");
  head.className = "modal-head";
  head.textContent = "Load template";
  const body = document.createElement("div");
  body.className = "modal-body";
  const name = document.createElement("strong");
  name.textContent = entry.name ?? entry.id ?? "Template";
  const detail = document.createElement("p");
  detail.className = "modal-note";
  detail.textContent = [entry.audio, entry.description].filter(Boolean).join(" · ");
  body.append(name, detail);

  const foot = document.createElement("div");
  foot.className = "modal-foot";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "mini";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());
  const load = document.createElement("button");
  load.type = "button";
  load.className = "mini accent";
  load.textContent = "Load template";
  load.addEventListener("click", () => {
    backdrop.remove();
    void loadCreationEntry(entry);
  });
  foot.append(cancel, load);

  modal.append(head, body, foot);
  backdrop.append(modal);
  document.body.append(backdrop);
}

/** Left-rail Templates panel: same catalogue as the modal, inline. */
async function renderTemplatesPanel(): Promise<void> {
  const root = treeRoot;
  root.textContent = "";

  const intro = document.createElement("p");
  intro.className = "panel-note";
  intro.textContent =
    "Decompiled reference projects. Loading a template replaces the current project and its audio.";
  root.append(intro);

  const list = document.createElement("div");
  list.className = "creation-list";
  root.append(list);

  const status = document.createElement("div");
  status.className = "empty";
  status.textContent = "Loading templates…";
  root.append(status);

  try {
    const entries = await fetchCreationEntries();
    status.remove();
    intro.textContent = `Decompiled reference projects (${entries.length}). Loading a template replaces the current project and its audio.`;
    root.insertBefore(createCreationFilter(entries.length), list);
    appendCreationRows(list, entries);
  } catch (error) {
    status.textContent = `Could not load templates: ${error instanceof Error ? error.message : String(error)}`;
  }
}

async function loadCreationEntry(
  entry: { name?: string; file?: string },
  backdrop?: HTMLElement,
): Promise<void> {
  if (!entry.file) return;
  try {
    setStatus(`Loading ${entry.name ?? entry.file}…`);
    const response = await fetch(entry.file, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const raw = (await response.json()) as {
      values?: { Audio?: { src?: string } };
    };
    const report = await importProjectJson(raw);
    backdrop?.remove();
    // importProjectJson already fetched and installed the project's own track
    // (keeping the imported clip spans). Re-loading it here fetched/decoded the
    // file a second time and reset every item's span to the full track.
    setLeftPanel("composition");
    setStatus(`Loaded "${entry.name ?? report.name}": ${report.nodes} items, ${report.layers} layers.`);
  } catch (error) {
    setStatus(`Creation failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

let lyricLines: string[] = [];

/** Lyrics panel: paste, split/join, LRCLIB search, file import. */
function renderLyricsPanel(): void {
  const root = treeRoot;
  root.textContent = "";

  const intro = document.createElement("p");
  intro.className = "panel-note";
  intro.textContent = "Input lyrics. Type a line break to split lines within a single lyric.";
  root.append(intro);

  const input = document.createElement("textarea");
  input.className = "lyrics-input";
  input.placeholder = "Start typing or paste your lyrics here";
  input.value = lyricLines.join("\n");
  input.addEventListener("change", () => {
    lyricLines = input.value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  });
  root.append(input);

  const actions = document.createElement("div");
  actions.className = "analyzer-actions";

  const split = document.createElement("button");
  split.type = "button";
  split.className = "mini";
  split.textContent = "Split";
  split.addEventListener("click", () => {
    lyricLines = input.value
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean);
    input.value = lyricLines.join("\n");
    setStatus(`Split into ${lyricLines.length} lyric lines.`);
  });

  const sync = document.createElement("button");
  sync.type = "button";
  sync.className = "mini";
  sync.textContent = "Start sync";
  sync.addEventListener("click", () =>
    setStatus("Lyric sync needs the timeline karaoke editor."),
  );

  const join = document.createElement("button");
  join.type = "button";
  join.className = "mini";
  join.textContent = "Join";
  join.addEventListener("click", () => {
    const merged = input.value
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean)
      .join(" ");
    lyricLines = merged ? [merged] : [];
    input.value = lyricLines.join("\n");
    setStatus("Joined lyrics into one line.");
  });

  actions.append(split, sync, join);
  root.append(actions);

  const or = document.createElement("p");
  or.className = "panel-note";
  or.textContent = "OR";
  root.append(or);

  const search = document.createElement("input");
  search.className = "catalogue-search";
  search.placeholder = "Use LRCLIB to search for lyrics";
  root.append(search);

  const searchButton = document.createElement("button");
  searchButton.type = "button";
  searchButton.className = "panel-row panel-row-add";
  searchButton.textContent = "Search LRCLIB";
  searchButton.addEventListener("click", () => setStatus("LRCLIB search is not wired yet."));
  root.append(searchButton);

  const importButton = document.createElement("button");
  importButton.type = "button";
  importButton.className = "panel-row panel-row-add";
  importButton.append(icon("upload", 12), document.createTextNode("Import lyrics file"));
  importButton.addEventListener("click", () => {
    const file = document.createElement("input");
    file.type = "file";
    file.accept = ".txt,.lrc,text/plain";
    file.addEventListener("change", async () => {
      const picked = file.files?.[0];
      if (!picked) return;
      const text = await picked.text();
      lyricLines = text
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean);
      input.value = lyricLines.join("\n");
      setStatus(`Imported ${lyricLines.length} lyric lines from ${picked.name}.`);
    });
    file.click();
  });
  root.append(importButton);
}

let leftPanel = "composition";

/** Title-bar action button, matching the reference's panel controls. */
function panelIconButton(
  title: string,
  iconName: IconName,
  action: () => void,
  active = false,
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `icon${active ? " on" : ""}`;
  button.title = title;
  button.append(icon(iconName, 14));
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    action();
  });
  return button;
}

/** Add analyzer row action: name it like the reference (`Analyzer (n)`). */
function addAnalyzer(): void {
  const index = project.analyzers.length;
  const analyzer = createAnalyzer(newId("analyzer"), `Analyzer (${index})`);
  const insert = (): void => {
    if (!project.analyzers.includes(analyzer)) {
      project.analyzers.splice(Math.min(index, project.analyzers.length), 0, analyzer);
    }
    selectedAnalyzerId = analyzer.id;
    renderAnalyzerPanel();
    refreshInspector();
    refreshStack();
  };
  insert();
  history.push({
    label: `add ${analyzer.name}`,
    undo: () => {
      project.analyzers = project.analyzers.filter((entry) => entry !== analyzer);
      if (selectedAnalyzerId === analyzer.id) selectedAnalyzerId = null;
      renderAnalyzerPanel();
      refreshInspector();
      refreshStack();
    },
    redo: insert,
  });
  setStatus(`Added Analyzer (${index}).`);
}

function setLeftPanel(panel: string): void {
  leftPanel = panel;
  document
    .querySelectorAll("#rail .rail-item")
    .forEach((node) => node.classList.toggle("active", (node as HTMLElement).dataset.panel === panel));

  const title = document.querySelector<HTMLElement>("#compositor .panel-title");
  const compositionActions = document.querySelector<HTMLElement>("#composition-actions");
  if (compositionActions) compositionActions.style.display = panel === "composition" ? "" : "none";
  const actions = document.querySelector<HTMLElement>("#panel-actions");
  if (actions) actions.textContent = "";

  if (panel === "analyzers") {
    if (title) title.textContent = "Audio Analyzers";
    actions?.append(panelIconButton("Add audio analyzer", "add", addAnalyzer));
    renderAnalyzerPanel();
    return;
  }
  if (panel === "automations") {
    if (title) title.textContent = "Automations";
    // Reference header controls: Add folder / Add automation.
    actions?.append(
      panelIconButton("Add folder", "create_new_folder", addAutomationFolder),
      panelIconButton("Add automation", "add", openAddAutomationDialog),
    );
    renderAutomationPanel();
    return;
  }
  if (panel === "lyrics") {
    if (title) title.textContent = "Lyrics";
    renderLyricsPanel();
    return;
  }
  if (panel === "projects") {
    if (title) title.textContent = "Projects";
    renderProjectsPanel();
    return;
  }
  if (panel === "templates") {
    if (title) title.textContent = "Templates";
    void renderTemplatesPanel();
    return;
  }
  if (panel === "media") {
    if (title) title.textContent = "Media";
    renderMediaPanel();
    return;
  }
  if (panel === "effects") {
    if (title) title.textContent = "Effects";
    actions?.append(
      panelIconButton(
        effectShowConnections ? "List all effects" : "Show connections",
        "account_tree",
        () => {
          effectShowConnections = !effectShowConnections;
          setLeftPanel("effects");
        },
        effectShowConnections,
      ),
      panelIconButton("Add effect", "add", () => openAddEffectDialog()),
    );
    renderEffectPanel();
    return;
  }
  if (title) title.textContent = "Composition";
  refreshTree();
  if (panel !== "composition") setStatus(`${panel}: browser not implemented yet.`);
}

/** Composition-level edits, applied before any object-level handling. */
function applyProjectEdit(propertyId: string, value: number | string | boolean): void {
  const key = propertyId.slice("project.".length);
  if (key === "name") {
    project.name = String(value).trim() || project.name;
    $("#project-name").textContent = project.name;
  } else if (key === "width") {
    project.width = Math.max(16, Math.round(Number(value)));
  } else if (key === "height") {
    project.height = Math.max(16, Math.round(Number(value)));
  } else if (key === "fps") {
    project.fps = Math.max(1, Math.round(Number(value)));
  } else if (key === "duration") {
    project.duration = Math.max(0.1, Number(value));
  } else if (key === "background") {
    project.background = String(value);
  } else {
    return;
  }
  renderer.resize();
  refreshInspector();
  setStatus(`Composition · ${key} = ${value}`);
}

function findNode(id: string): AnyNode | undefined {
  return project.nodes.find((node) => node.id === id);
}

/** Populate the layout-F code panel from the current selection. */
function syncCodeEditor(): void {
  codeTarget = null;
  codeApply.disabled = true;
  const node = selectedId ? findNode(selectedId) : null;
  if (!node) {
    codeEditorText.value = "// Select an item to edit its shader or custom path.";
    codeEditorNote.textContent = "";
    return;
  }
  if (codePreferredNode !== node.id) {
    codePreferredNode = null;
    codePreferredLayer = null;
  }
  if (node instanceof SpectrumNode) {
    const shader =
      node.layers.find(
        (layer) => layer.id === codePreferredLayer && layer.colorType === "Shader",
      ) ?? node.layers.find((layer) => layer.colorType === "Shader");
    if (shader) {
      codeEditorText.value = shader.shaderSrc;
      codeTarget = { nodeId: node.id, kind: "shader", layerId: shader.id };
      codeApply.disabled = false;
      codeEditorNote.textContent = `${node.name} · ${shader.id} shader`;
      return;
    }
    if (String(node.type).toLowerCase() === "custom") {
      codeEditorText.value = node.customPath;
      codeTarget = { nodeId: node.id, kind: "customPath" };
      codeApply.disabled = false;
      codeEditorNote.textContent = `${node.name} · custom path`;
      return;
    }
    codeEditorText.value = JSON.stringify(node.readParams(), null, 2);
    codeEditorNote.textContent = "No shader or custom path on this item (read-only).";
    return;
  }
  codeEditorText.value = JSON.stringify(
    { name: node.name, type: node.typeLabel, mapping: [...node.objectMapping] },
    null,
    2,
  );
  codeEditorNote.textContent = "Read-only item mapping.";
}

codeApply.addEventListener("click", () => {
  const target = codeTarget;
  if (!target) return;
  const node = findNode(target.nodeId);
  if (!(node instanceof SpectrumNode)) return;
  const next = codeEditorText.value;
  if (target.kind === "shader") {
    const layer = node.layers.find((entry) => entry.id === target.layerId);
    if (!layer) return;
    const before = layer.shaderSrc;
    if (before === next) return;
    layer.shaderSrc = next;
    history.push({
      label: "edit shader",
      undo: () => {
        layer.shaderSrc = before;
        refreshInspector();
      },
      redo: () => {
        layer.shaderSrc = next;
        refreshInspector();
      },
    });
    refreshInspector();
    setStatus(`Updated ${layer.id} shader.`);
    return;
  }
  const before = node.customPath;
  if (before === next) return;
  node.customPath = next;
  history.push({
    label: "edit custom path",
    undo: () => {
      node.customPath = before;
      refreshInspector();
    },
    redo: () => {
      node.customPath = next;
      refreshInspector();
    },
  });
  refreshInspector();
  setStatus("Updated custom path.");
});

function ensureAutomation(nodeId: string, propertyId: string): Automation {
  const existing = project.automations.find(
    (a) => a.nodeId === nodeId && a.propertyId === propertyId,
  );
  if (existing) return existing;
  const automation: Automation = {
    id: newId("automation"),
    type: "property",
    nodeId,
    propertyId,
    connections: {},
    keyframes: [],
  };
  project.automations.push(automation);
  return automation;
}

/** Automation driving one effect parameter, created on first keyframe. */
function ensureEffectAutomation(effectId: string, param: string): Automation {
  const existing = project.automations.find((a) => a.connections[effectId]?.includes(param));
  if (existing) return existing;
  const automation: Automation = {
    id: newId("automation"),
    type: "property",
    nodeId: "",
    propertyId: "",
    connections: { [effectId]: [param] },
    keyframes: [],
  };
  project.automations.push(automation);
  return automation;
}

/** Record the effect parameter's current value as a keyframe at the playhead. */
function addEffectKeyframe(effect: EffectInstance, param: string): void {
  const hadAutomation = project.automations.some(
    (entry) => entry.nodeId === "" && entry.connections[effect.id]?.includes(param),
  );
  const automation = ensureEffectAutomation(effect.id, param);
  const automationIndex = project.automations.indexOf(automation);
  const beforeKeys = automation.keyframes.map((key) => ({ ...key }));
  const value = Number(effect.params[param] ?? 0);
  const existing = automation.keyframes.findIndex((k) => Math.abs(k.t - time) < 0.02);
  const keyframe = { t: Math.round(time * 100) / 100, value, easing: "linear" as const };
  if (existing >= 0) automation.keyframes[existing] = keyframe;
  else automation.keyframes.push(keyframe);
  automation.keyframes.sort((a, b) => a.t - b.t);
  const afterKeys = automation.keyframes.map((key) => ({ ...key }));
  const apply = (keys: Keyframe[], withAutomation: boolean): void => {
    automation.keyframes = keys.map((key) => ({ ...key }));
    if (withAutomation && !project.automations.includes(automation)) {
      project.automations.splice(Math.min(automationIndex, project.automations.length), 0, automation);
    }
    if (!withAutomation) {
      project.automations = project.automations.filter((entry) => entry !== automation);
    }
    refreshTree();
    refreshInspector();
    timeline.render(time, selectedId);
  };
  history.push({
    label: "add keyframe",
    undo: () => apply(beforeKeys, hadAutomation),
    redo: () => apply(afterKeys, true),
  });
  setStatus(`keyframe ${effect.name} ${param} @ ${time.toFixed(2)}s`);
  refreshTree();
}

function addKeyframe(nodeId: string, propertyId: string): void {
  const node = findNode(nodeId);
  if (!node) return;
  const hadAutomation = project.automations.some(
    (entry) => entry.nodeId === nodeId && entry.propertyId === propertyId,
  );
  const automation = ensureAutomation(nodeId, propertyId);
  const automationIndex = project.automations.indexOf(automation);
  const beforeKeys = automation.keyframes.map((key) => ({ ...key }));
  const value = node.readNumber(propertyId);
  const existing = automation.keyframes.findIndex((k) => Math.abs(k.t - time) < 0.02);
  const keyframe = { t: Math.round(time * 100) / 100, value, easing: "linear" as const };
  if (existing >= 0) automation.keyframes[existing] = keyframe;
  else automation.keyframes.push(keyframe);
  automation.keyframes.sort((a, b) => a.t - b.t);
  const afterKeys = automation.keyframes.map((key) => ({ ...key }));
  const apply = (keys: Keyframe[], withAutomation: boolean): void => {
    automation.keyframes = keys.map((key) => ({ ...key }));
    if (withAutomation && !project.automations.includes(automation)) {
      project.automations.splice(Math.min(automationIndex, project.automations.length), 0, automation);
    }
    if (!withAutomation) {
      project.automations = project.automations.filter((entry) => entry !== automation);
    }
    refreshTree();
    refreshInspector();
    timeline.render(time, selectedId);
  };
  history.push({
    label: "add keyframe",
    undo: () => apply(beforeKeys, hadAutomation),
    redo: () => apply(afterKeys, true),
  });
  setStatus(`keyframe ${propertyId} @ ${time.toFixed(2)}s`);
  refreshInspector();
}

/* ------------------------------------------------------------------ */
/* Timeline                                                            */
/* ------------------------------------------------------------------ */

/** Final span of the clip drag currently being coalesced into one undo step. */
let clipDragTarget: { start: number; duration: number; sourceIn?: number } | null = null;

/** Keyframes captured when a timeline key drag starts, for one undo step. */
let keyDragBefore: { key: Keyframe; time: number; value: number }[] | null = null;

/** Slip drag: source position at the start and the live target. */
let slipDrag: { node: AnyNode; before: number; target: { value: number } } | null = null;

/** Marker drag: original time and the live target. */
let markerDrag: {
  marker: { id: string; time: number; name: string };
  before: number;
  target: { time: number };
} | null = null;

/** Keep every automation row in time order after a key drag. */
function sortAutomationKeys(): void {
  for (const automation of project.automations) {
    automation.keyframes.sort((a, b) => a.t - b.t);
  }
}

/** Group of clips moved by one timeline drag, coalesced into one undo step. */
let timelineGroupDrag: {
  key: string;
  entries: { node: AnyNode; before: number; after: number }[];
} | null = null;

function moveTimelineGroup(moves: { id: string; start: number }[]): void {
  const entries = moves
    .map((move) => {
      const node = findNode(move.id);
      return node ? { node, start: move.start } : null;
    })
    .filter((entry): entry is { node: AnyNode; start: number } => Boolean(entry));
  if (entries.length === 0) return;
  const key = `timeline-group:${entries
    .map((entry) => entry.node.id)
    .sort()
    .join(",")}`;
  const coalesce = coalescer.shouldCoalesce(key) && timelineGroupDrag?.key === key;
  if (!coalesce) {
    const record = entries.map((entry) => ({
      node: entry.node,
      before: entry.node.start,
      after: entry.start,
    }));
    timelineGroupDrag = { key, entries: record };
    history.push({
      label: "move clips",
      undo: () => {
        for (const entry of record) entry.node.start = entry.before;
        refreshInspector();
      },
      redo: () => {
        for (const entry of record) entry.node.start = entry.after;
        refreshInspector();
      },
    });
  } else if (timelineGroupDrag) {
    for (const entry of entries) {
      const record = timelineGroupDrag.entries.find((item) => item.node === entry.node);
      if (record) record.after = entry.start;
    }
  }
  for (const entry of entries) entry.node.start = entry.start;
  refreshInspector();
}

function editClipSpan(
  node: AnyNode,
  start: number,
  duration: number,
  label: string,
  edge?: "start" | "end",
): void {
  const media = node as AnyNode & { sourceIn?: number; playbackRate?: number };
  // Trimming the in point moves the source position with the edge, so the
  // picture does not restart or stretch. Moving the clip leaves it alone.
  const trimSource = edge === "start" && typeof media.sourceIn === "number";
  const beforeSource = media.sourceIn ?? 0;
  const sourceIn = trimSource
    ? Math.max(0, beforeSource + (start - node.start) * Math.max(0, media.playbackRate ?? 1))
    : beforeSource;
  const key = `${project.id}:${node.id}:${label}`;
  if (!coalescer.shouldCoalesce(key)) {
    const before = { start: node.start, duration: node.duration, sourceIn: beforeSource };
    const target = { start, duration, sourceIn };
    clipDragTarget = target;
    history.push({
      label,
      undo: () => {
        node.start = before.start;
        node.duration = before.duration;
        if (trimSource) media.sourceIn = before.sourceIn;
        refreshInspector();
      },
      redo: () => {
        node.start = target.start;
        node.duration = target.duration;
        if (trimSource) media.sourceIn = target.sourceIn;
        refreshInspector();
      },
    });
  } else if (clipDragTarget) {
    clipDragTarget.start = start;
    clipDragTarget.duration = duration;
    clipDragTarget.sourceIn = sourceIn;
  }
  node.start = start;
  node.duration = duration;
  if (trimSource) media.sourceIn = sourceIn;
  refreshInspector();
}

const timeline = new TimelineView($<HTMLCanvasElement>("#timeline"), project, {
  onSelect(nodeId) {
    selectedId = nodeId;
    refreshTree();
    refreshInspector();
  },
  onSelectMany(ids) {
    selectedId = ids[0] ?? null;
    multiSelection = new Set(ids);
    selectedLayerId = null;
    selectedAnalyzerId = null;
    selectedAutomations = new Set();
    refreshTree();
    refreshInspector();
  },
  onMoveMany(moves) {
    moveTimelineGroup(moves);
  },
  onSplitAt(nodeId, at) {
    splitNodeAt(nodeId, at);
  },
  onSeek(next) {
    time = Math.max(0, Math.min(project.duration, next));
    refreshInspector();
  },
  onMoveStart(nodeId, start) {
    const node = findNode(nodeId);
    if (!node) return;
    editClipSpan(node, start, node.duration, "move clip");
  },
  onResize(nodeId, start, duration, edge) {
    const node = findNode(nodeId);
    if (!node) return;
    editClipSpan(node, start, duration, "resize clip", edge);
  },
  onSlip(nodeId, delta) {
    const node = findNode(nodeId);
    const media = node as (AnyNode & { sourceIn?: number }) | null;
    if (!media || typeof media.sourceIn !== "number") return;
    if (!slipDrag || slipDrag.node !== media) {
      const before = media.sourceIn;
      const target = { value: before };
      slipDrag = { node: media, before, target };
      history.push({
        label: "slip clip",
        undo: () => {
          media.sourceIn = before;
          refreshInspector();
        },
        redo: () => {
          media.sourceIn = target.value;
          refreshInspector();
        },
      });
    }
    slipDrag.target.value = Math.max(0, slipDrag.before + delta);
    media.sourceIn = slipDrag.target.value;
    refreshInspector();
  },
  onSlipEnd() {
    slipDrag = null;
  },
  onMoveMarker(marker, next) {
    const key = `${project.id}:${marker.id}:marker`;
    if (!markerDrag || markerDrag.marker !== marker || !coalescer.shouldCoalesce(key)) {
      const before = marker.time;
      const target = { time: next };
      markerDrag = { marker, before, target };
      history.push({
        label: "move marker",
        undo: () => {
          marker.time = before;
          project.markers.sort((a, b) => a.time - b.time);
          timeline.render(time, selectedId);
        },
        redo: () => {
          marker.time = target.time;
          project.markers.sort((a, b) => a.time - b.time);
          timeline.render(time, selectedId);
        },
      });
    } else {
      markerDrag.target.time = next;
    }
    marker.time = next;
    project.markers.sort((a, b) => a.time - b.time);
    timeline.render(time, selectedId);
  },
  onMoveMarkerEnd() {
    markerDrag = null;
  },
  onContextMenu(nodeId, x, y) {
    const node = findNode(nodeId);
    if (node) openItemMenuAt(x, y, node);
  },
  onMarkerMenu(index, x, y) {
    openMarkerMenu(index, x, y);
  },
  onSelectLayer(layerId) {
    selectLayer(layerId);
  },
  onToggleLayer(layerId) {
    const layer = project.layers.find((entry) => entry.id === layerId);
    if (!layer) return;
    setLayerEnabled(layer, !layer.enabled);
  },
  onMoveKeyframes(moves) {
    if (!keyDragBefore) {
      keyDragBefore = moves.map((move) => ({
        key: move.key,
        time: move.key.t,
        value: move.key.value,
      }));
    }
    for (const move of moves) {
      move.key.t = move.time;
      if (move.value !== undefined) move.key.value = move.value;
    }
    refreshInspector();
  },
  onCommitKeyframes() {
    const before = keyDragBefore;
    keyDragBefore = null;
    if (!before || before.length === 0) return;
    sortAutomationKeys();
    const after = before.map((entry) => ({ time: entry.key.t, value: entry.key.value }));
    if (
      before.every(
        (entry, index) =>
          Math.abs(entry.time - after[index].time) < 1e-6 &&
          Math.abs(entry.value - after[index].value) < 1e-9,
      )
    ) {
      return;
    }
    history.push({
      label: "move keyframes",
      undo: () => {
        for (const entry of before) {
          entry.key.t = entry.time;
          entry.key.value = entry.value;
        }
        sortAutomationKeys();
        refreshInspector();
      },
      redo: () => {
        before.forEach((entry, index) => {
          entry.key.t = after[index].time;
          entry.key.value = after[index].value;
        });
        sortAutomationKeys();
        refreshInspector();
      },
    });
    setStatus(
      `Moved ${before.length} keyframe${before.length === 1 ? "" : "s"}.`,
    );
  },
});
timelineReady = true;

/* ------------------------------------------------------------------ */
/* Transport                                                           */
/* ------------------------------------------------------------------ */

function setPlaying(next: boolean): void {
  playing = next;
  renderer.setPlaying(next);
  $<HTMLButtonElement>("#btn-play").replaceChildren(icon(next ? "pause" : "play_arrow", 16));
  if (next) {
    void audio.resume();
    audio.play(audioBuffer, time);
  } else {
    audio.stop();
  }
}

function formatTime(seconds: number): string {
  if (!displaySeconds) {
    return `frame ${Math.round(Math.max(0, seconds) * project.fps)}`;
  }
  const whole = Math.max(0, seconds);
  const mm = Math.floor(whole / 60);
  const ss = Math.floor(whole % 60);
  const cc = Math.floor((whole % 1) * 100);
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}.${String(cc).padStart(2, "0")}`;
}

function clampUnit(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function parseHexColor(value: string): [number, number, number] {
  const match = /^#?([0-9a-f]{6})$/i.exec(value.trim());
  if (!match) return [0, 0, 0];
  const parsed = Number.parseInt(match[1], 16);
  return [(parsed >> 16) & 255, (parsed >> 8) & 255, parsed & 255];
}

/** Linear mix between two hex colours, used by reference `variant: "color"` rows. */
function mixHexColor(from: string, to: string, amount: number): string {
  const t = clampUnit(amount);
  const a = parseHexColor(from);
  const b = parseHexColor(to);
  const channel = (index: number): string =>
    Math.round(a[index] + (b[index] - a[index]) * t)
      .toString(16)
      .padStart(2, "0");
  return `#${channel(0)}${channel(1)}${channel(2)}`;
}

function writeNodeColor(node: AnyNode, property: string, color: string): void {
  if (!property) return;
  if (property === "color") {
    (node as AnyNode & { color?: string }).color = color;
    return;
  }
  const layerMatch = /^spectrum_layer:(\d+):(color|colorFrom|colorTo)$/.exec(property);
  if (layerMatch && node instanceof SpectrumNode) {
    const layer = node.layers[Number(layerMatch[1])];
    if (!layer) return;
    if (layerMatch[2] === "color") layer.color = color;
    else if (layerMatch[2] === "colorFrom") layer.colorFrom = color;
    else layer.colorTo = color;
  }
}

/** Applies a colour automation to the node/effect properties it drives. */
function applyAutomationColor(automation: Automation, color: string): void {
  if (automation.nodeId && automation.propertyId) {
    const node = findNode(automation.nodeId);
    if (node) writeNodeColor(node, automation.propertyId, color);
  }
  for (const [objectId, params] of Object.entries(automation.connections)) {
    const node = findNode(objectId);
    if (node) {
      for (const param of params) writeNodeColor(node, param, color);
      continue;
    }
    const effect = project.effects.find((item) => item.id === objectId);
    if (!effect) continue;
    for (const param of params) effect.params[param] = color;
  }
}

/**
 * Reference item automations use the item's own units: `scale:*` is a 1x
 * multiplier while node controllers store percent (see applyReferenceTransform).
 */
function automationNodeValue(
  property: string,
  value: number,
  referenceScaleUnits: boolean,
): number {
  return referenceScaleUnits && /^transform\.scale[XYZ]$/.test(property) ? value * 100 : value;
}

/**
 * Media colour multipliers live on the node's `colorMult` fields, not in the
 * controller mapping. `colorMult:alpha` drives the item fade the reference uses.
 */
function writeMediaColor(node: AnyNode, property: string, value: number): boolean {
  if (!(node instanceof MediaNode) || !property.startsWith("colorMult:")) return false;
  const channel = property.slice("colorMult:".length);
  const key =
    channel === "red" ? "r" : channel === "green" ? "g" : channel === "blue" ? "b" : channel === "alpha" ? "a" : null;
  if (!key) return false;
  node.colorMult[key] = value;
  return true;
}

/**
 * Some reference item properties are exported 0..1 fields on the node itself
 * rather than controllers in the mapping (SkiaText/Lyrics `alpha`,
 * Plane/Spherical Field `opacity`). Write the field so those rows animate.
 */
function writeItemField(node: AnyNode, property: string, value: number): boolean {
  if (property !== "alpha" && property !== "opacity") return false;
  const target = node as unknown as Record<string, unknown>;
  if (typeof target[property] !== "number") return false;
  target[property] = value;
  return true;
}

/**
 * Some reference rows address a node field directly (`ShaderItem.value`,
 * `textSize`, `timeOffset`, `speedAmplitude`, …). If the name is not already a
 * controller in the mapping and the node owns that numeric field, write it.
 */
function writeNodeField(node: AnyNode, property: string, value: number): boolean {
  // Text items expose the reference's `scaleMultiplier` as a plain member
  // (`SkiaTextNode`/`LyricsNode` read `this.scaleMultiplier` in `draw`), so the
  // exported `transform.scaleMultiplier` target has no controller to write.
  if (property === "transform.scaleMultiplier") {
    const target = node as unknown as { scaleMultiplier?: unknown };
    if (typeof target.scaleMultiplier === "number") {
      target.scaleMultiplier = value;
      return true;
    }
  }
  if (node.objectMapping.has(property)) return false;
  const target = node as unknown as Record<string, unknown>;
  if (typeof target[property] !== "number") return false;
  target[property] = value;
  return true;
}

/**
 * Rows whose end value has already been written once (reference
 * `Keyframe.updateAutomation`'s `hasUpdatedRedux`). A keyframe outside its
 * [startTime, endTime] span must not clamp its value onto the property, or a
 * later row on the same property erases an earlier row's fade.
 */
const keyframeEndWrites = new Set<string>();

function applyAutomations(at: number): void {
  const byId = new Map(project.automations.map((automation) => [automation.id, automation]));

  // Reverse the reference's automation-to-automation edges so a source can be
  // evaluated on demand before its consumer (math inputs, impact sensitivity,
  // keyframe bounds).
  const incoming = new Map<string, { source: Automation; params: string[] }[]>();
  for (const automation of project.automations) {
    for (const [targetId, params] of Object.entries(automation.automationConnections ?? {})) {
      if (!byId.has(targetId)) continue;
      const list = incoming.get(targetId) ?? [];
      list.push({ source: automation, params });
      incoming.set(targetId, list);
    }
  }

  const values = new Map<string, number | null>();
  const visiting = new Set<string>();

  const evaluate = (automation: Automation): number | null => {
    if (values.has(automation.id)) return values.get(automation.id) ?? null;
    if (automation.enabled === false) return null;
    // Reference graphs are acyclic; a malformed cycle must not hang a frame.
    if (visiting.has(automation.id)) return 0;
    visiting.add(automation.id);

    const inputs: Record<string, number> = {};
    const impactOverride: Partial<AudioImpactSettings> = {};
    let startOverride: number | null = null;
    let endOverride: number | null = null;
    for (const { source, params } of incoming.get(automation.id) ?? []) {
      const sourceValue = evaluate(source);
      if (sourceValue === null || !Number.isFinite(sourceValue)) continue;
      for (const param of params) {
        if (/^u[1-5]$/.test(param)) inputs[param] = sourceValue;
        else if (param === "sensitivity") impactOverride.sensitivity = sourceValue;
        else if (param === "minValue") impactOverride.min = sourceValue;
        else if (param === "maxValue") impactOverride.max = sourceValue;
        else if (param === "floorValue") impactOverride.floor = sourceValue;
        else if (param === "ceilingValue") impactOverride.ceiling = sourceValue;
        else if (param === "startTime") startOverride = sourceValue;
        else if (param === "endTime") endOverride = sourceValue;
      }
    }

    let value: number | null = null;

    if (automation.type === "audioImpact" && automation.impact) {
      const node = automation.nodeId ? findNode(automation.nodeId) : null;
      // The reference gives the automation its own analyzer selection; older
      // saves without one fall back to the driven object's analyzer.
      const analyzerId =
        automation.audioAnalyzer ?? node?.analyzerId ?? project.analyzers[0]?.id ?? "";
      const bands = analyzerId
        ? // The shipped `updateAutomation` computes `hypot(...data)` over the
          // analyzer's own `sampleOutCount` bands. `spectrumFor` returns the
          // fixed 256 shader slots, which repeats those bands ~32x and inflated
          // every impact value by sqrt(256 / sampleOutCount).
          renderer.makeContext().spectrumBandsFor?.(analyzerId) ??
          renderer.makeContext().spectrumFor?.(analyzerId) ??
          null
        : null;
      // One running smoother per automation row.
      const key =
        automation.nodeId || automation.propertyId
          ? `${automation.nodeId}:${automation.propertyId}`
          : automation.id;
      value = impactEngine.sample(
        key,
        { ...automation.impact, ...impactOverride },
        bands,
        project.audioImpactMax,
      );
    } else if (automation.type === "math" && automation.formula) {
      // Math automations are evaluated every frame with the reference's
      // keywords in scope (see `domain/formula.ts`). `u1`-`u5` are the units
      // wired in from other automations; unconnected units fall back to globals.
      const node = automation.nodeId ? findNode(automation.nodeId) : null;
      const previous =
        node && automation.propertyId ? Number(node.readNumber(automation.propertyId)) : 0;
      // The reference Math row reads its own analyzer (`this.audioAnalyzer`),
      // never the driven object's: Math automation `updateAutomation` does
      //   const n = t.audioAnalyzerData[this.audioAnalyzer]; n && (e = Math.hypot(...n))
      //   mexp.eval(formula, …, { a: e, m: WebGLManager.getAudioImpact().maxAudioImpact })
      // so `a` is the hypot of the band series and `m` is the same project-wide
      // maximum AudioImpact divides by. Both are on the reference analyzer scale
      // (our native series is that scale divided by REFERENCE_VALUE_SCALE, the
      // shader normalisation), so `a` has to be scaled back up or `a/m` is
      // ~200x too small. A plain sum is not the reference statistic at all.
      const analyzerId =
        automation.audioAnalyzer ?? node?.analyzerId ?? project.analyzers[0]?.id ?? "";
      const bands = analyzerId
        ? // Same native band series the impact engine uses; the 256 shader
          // slots would multiply the formula's `a` by the resampling factor.
          renderer.makeContext().spectrumBandsFor?.(analyzerId) ??
          renderer.makeContext().spectrumFor?.(analyzerId) ??
          null
        : null;
      const impact = bands ? Math.hypot(...bands) * REFERENCE_VALUE_SCALE : 0;
      try {
        value = Formula.evaluate(automation.formula, {
          t: at,
          // Reference binds `p: this.prevValue || 1` - a previous value of 0
          // reads as 1 (the `||` is truthiness, not a default-parameter test).
          p: previous || 1,
          a: impact,
          m: project.audioImpactMax,
          d: audioBuffer?.duration ?? project.duration,
          u1: inputs.u1 ?? automation.units?.[0] ?? project.globals[0] ?? 0,
          u2: inputs.u2 ?? automation.units?.[1] ?? project.globals[1] ?? 0,
          u3: inputs.u3 ?? automation.units?.[2] ?? project.globals[2] ?? 0,
          u4: inputs.u4 ?? automation.units?.[3] ?? project.globals[3] ?? 0,
          u5: inputs.u5 ?? automation.units?.[4] ?? project.globals[4] ?? 0,
          g1: project.globals[0] ?? 0,
          g2: project.globals[1] ?? 0,
          g3: project.globals[2] ?? 0,
          g4: project.globals[3] ?? 0,
          g5: project.globals[4] ?? 0,
          rx: project.width,
          ry: project.height,
        });
      } catch {
        value = null;
      }
    } else {
      let sampled = automation;
      // A keyframe row can drive another keyframe's time bounds.
      if (
        automation.keyframes.length > 0 &&
        (startOverride !== null || endOverride !== null)
      ) {
        const keyframes = automation.keyframes.map((keyframe) => ({ ...keyframe }));
        if (startOverride !== null) keyframes[0].t = startOverride;
        if (endOverride !== null) keyframes[keyframes.length - 1].t = endOverride;
        sampled = { ...automation, keyframes };
      }
      const keys = sampled.keyframes;
      if (keys.length === 0) {
        value = sampleAutomation(sampled, at);
      } else {
        // Reference Keyframe.updateAutomation (module 145):
        //   if (!h && startTime < time && endTime > time) { ...interpolate... }
        //   else if (endTime > 0 && time > endTime && !hasUpdatedRedux) {
        //     ...write endValue once... hasUpdatedRedux = true
        //   }
        // Anything else writes nothing. A row that has not started yet must not
        // clamp its start value onto the property: oil-colors' FadeInOutPlane
        // has a 0..12 s fade (1 -> 0) and a 176..182 s fade (0 -> 1) on the same
        // opacity. Clamping the later row wrote 0 at t=2, so the black plane
        // never faded and the frame stayed at mean 39.1 against a 10.62
        // reference; with the plane at the active row's 0.741 the frame reads
        // 10.1 (lit 0.419 against 0.418).
        const first = keys[0].t;
        const last = keys[keys.length - 1].t;
        if (at > first && at < last) {
          keyframeEndWrites.delete(automation.id);
          value = sampleAutomation(sampled, at);
        } else if (last > 0 && at > last) {
          if (keyframeEndWrites.has(automation.id)) {
            value = null;
          } else {
            keyframeEndWrites.add(automation.id);
            value = keys[keys.length - 1].value;
          }
        } else {
          value = null;
        }
      }
    }

    visiting.delete(automation.id);
    values.set(automation.id, value);
    return value;
  };

  for (const automation of project.automations) {
    if (automation.enabled === false) continue;
    const value = evaluate(automation);
    if (value === null || !Number.isFinite(value)) continue;

    if (automation.variant === "color" && automation.colors) {
      applyAutomationColor(
        automation,
        mixHexColor(automation.colors.from, automation.colors.to, value),
      );
      continue;
    }

    if (automation.nodeId && automation.propertyId) {
      const node = findNode(automation.nodeId);
      if (node) {
        if (
          automation.propertyId === "transform.scaleMultiplier" &&
          node instanceof SpectrumNode
        ) {
          // Math/keyframe rows emit the reference factor; audio-impact min/max
          // were calibrated to our percent controller during import.
          const referenceUnits =
            automation.type === "math" ||
            (automation.type === "property" &&
              (automation.keyframes?.length ?? 0) > 0);
          node.writeNumber(
            automation.propertyId,
            referenceUnits ? scaleMultiplierFromReference(value) : value,
          );
          node.referenceScaleMultiplier = referenceUnits
            ? value
            : scaleMultiplierToReference(value);
        } else {
          if (
            !writeItemField(node, automation.propertyId, value) &&
            !writeMediaColor(node, automation.propertyId, value) &&
            !writeNodeField(node, automation.propertyId, value)
          ) {
            node.writeNumber(
              automation.propertyId,
              automationNodeValue(automation.propertyId, value, automation.referenceScaleUnits === true),
            );
          }
        }
      }
    }

    // Other objects the reference models as `connections: { objectId: [...] }`:
    // node controllers and effect parameters.
    for (const [objectId, params] of Object.entries(automation.connections)) {
      const node = findNode(objectId);
      if (node) {
        for (const controller of params) {
          if (objectId === automation.nodeId && controller === automation.propertyId) continue;
          if (controller === "transform.scaleMultiplier" && node instanceof SpectrumNode) {
            const referenceUnits =
              automation.type === "math" ||
              (automation.type === "property" &&
                (automation.keyframes?.length ?? 0) > 0);
            node.writeNumber(
              controller,
              referenceUnits ? scaleMultiplierFromReference(value) : value,
            );
            node.referenceScaleMultiplier = referenceUnits
              ? value
              : scaleMultiplierToReference(value);
          } else {
            if (
              !writeItemField(node, controller, value) &&
              !writeMediaColor(node, controller, value) &&
              !writeNodeField(node, controller, value)
            ) {
              node.writeNumber(controller, automationNodeValue(controller, value, automation.referenceScaleUnits === true));
            }
          }
        }
        continue;
      }
      const layer = project.layers.find((item) => item.id === objectId);
      if (layer) {
        layer.transform ??= {
          position: [0, 0, 0],
          rotation: [0, 0, 0],
          scale: [1, 1, 1],
        };
        for (const param of params) {
          if (param === "fov" && layer.camera) {
            layer.camera.fov = value;
            continue;
          }
          if (param === "nearPlane" && layer.camera) {
            layer.camera.near = value;
            continue;
          }
          if (param === "farPlane" && layer.camera) {
            layer.camera.far = value;
            continue;
          }
          const [kind, axis] = param.split(":");
          const index = axis === "x" ? 0 : axis === "y" ? 1 : axis === "z" ? 2 : -1;
          if (index < 0) continue;
          const slot = index as 0 | 1 | 2;
          if (kind === "position") layer.transform.position[slot] = value;
          else if (kind === "rotation") layer.transform.rotation[slot] = value;
          else if (kind === "scale") layer.transform.scale[slot] = value;
        }
        continue;
      }
      const analyzer = project.analyzers.find((item) => item.id === objectId);
      if (analyzer) {
        for (const param of params) {
          if (param === "outputMultiplier") analyzer.outputMultiplier = value;
          else if (param === "smoothingTimeConstant") analyzer.smoothingTimeConstant = value;
        }
        continue;
      }
      const effect = project.effects.find((item) => item.id === objectId);
      if (!effect) continue;
      for (const param of params) {
        // The reference Alpha uniform is 0..1; our Alpha controller is 0..100.
        // Keyframe rows that drive an Alpha effect are already scaled by the
        // importer, so only math/audioImpact values need converting.
        const toPercent =
          effect.type === "alpha" &&
          param === "alpha" &&
          !(automation.keyframes && automation.keyframes.length > 0);
        effect.params[param] = toPercent ? value * 100 : value;
      }
    }
  }
}

/* ------------------------------------------------------------------ */
/* Main loop                                                           */
/* ------------------------------------------------------------------ */

let frames = 0;
let fpsAt = performance.now();
let currentFps = 0;

function loopTick(): void {
  // A hot update re-ran this module; stop the superseded loop instead of
  // scheduling frames from two renderers.
  if ((globalThis as Record<string, unknown>)[loopGenerationKey] !== loopGeneration) return;
  // The exporter owns the renderer and analyser while a job is running; the
  // preview loop must not tick audio or repaint with preview-time state.
  if (exporting) {
    requestAnimationFrame(loopTick);
    return;
  }
  const now = performance.now();
  const delta = (now - lastFrame) / 1000;
  lastFrame = now;

  if (playing) {
    time += delta;
    const range = loop ? timeline.getLoopRange() : null;
    const end = range ? range.end : project.duration;
    if (time >= end) {
      if (loop) time = range ? range.start : 0;
      else {
        time = project.duration;
        setPlaying(false);
      }
    }
  }

  spectrum.tick(time, delta);
  // The reference analyses the frame and then runs automations against it.
  // `render` also sets the frame time, but it runs *after* the automation pass,
  // so without this every audio-reactive value read the previous frame's bands.
  renderer.setFrameTime(time);
  // A paused frame is a rerender: the reference returns before touching any
  // automation (`if (e.rerender) return`), which is what keeps a cumulative
  // AudioImpact row frozen while the transport is stopped. Running this on
  // every rAF tick instead let a paused project keep accumulating rotation and
  // made a capture race the preview loop (plasma-pill-kn @45: 32.8..85.7 on
  // the same build and reference).
  if (playing || time !== lastAutomationTime) {
    lastAutomationTime = time;
    applyAutomations(time);
  }
  renderer.render(time);
  timeline.render(time, selectedId, playing);

  if (Math.abs(time - lastSavedTime) >= 0.5) {
    lastSavedTime = time;
    try {
      sessionStorage.setItem("studio:time", time.toFixed(3));
    } catch {
      /* storage may be unavailable */
    }
  }

  timeReadout.textContent = `${formatTime(time)} / ${formatTime(project.duration)}`;
  const viewState = timeline.getViewState();
  zoom = viewState.zoom;
  zoomLabel.textContent = `Zoom: ${String(Number(viewState.zoom.toFixed(2)))}`;
  if (Math.abs(Number(zoomSlider.value) - viewState.zoom) > 0.001) {
    zoomSlider.value = String(viewState.zoom);
  }

  frames += 1;
  if (now - fpsAt >= 500) {
    currentFps = (frames * 1000) / (now - fpsAt);
    frames = 0;
    fpsAt = now;
  }
  hud.textContent =
    `${currentFps.toFixed(0)} fps\n` +
    `fft ${spectrum.tier} (${spectrum.lastTransformMs.toFixed(1)} ms)\n` +
    `spectrum source: ${spectrum.sourceLabel}`;

  requestAnimationFrame(loopTick);
}

/* ------------------------------------------------------------------ */
/* Actions                                                             */
/* ------------------------------------------------------------------ */

/** Read a picked file as a data URL, so the image survives without blob URLs. */
function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result ?? "")));
    reader.addEventListener("error", () => reject(reader.error));
    reader.readAsDataURL(file);
  });
}

/** First Image item marked as the composition background (`isBackground`). */
function backgroundImageNode(): MediaNode | null {
  for (const layer of project.layers) {
    for (const id of layer.nodeIds) {
      const node = findNode(id);
      if (node instanceof MediaNode && node.readNumber("basics.autoBackground") > 0.5) {
        return node;
      }
    }
  }
  return null;
}

/** Current background image source, for thumbnails in the settings dialog. */
function backgroundImageUrl(): string | null {
  const node = backgroundImageNode();
  if (!node) return null;
  if (node.imageUrl) return node.imageUrl;
  return node.assetId ? assets.record(node.assetId)?.url ?? null : null;
}

/**
 * Reference "set background image": reuse an Image item flagged as background,
 * or create an Image Layer at the bottom of the stack with one.
 */
function setBackgroundImage(url: string | null, name: string): void {
  let node = backgroundImageNode();
  let createdLayer: {
    id: string;
    name: string;
    nodeIds: string[];
    enabled: boolean;
    renderToBuffer: boolean;
  } | null = null;
  if (!node) {
    if (!url) return;
    const layer = {
      id: newId("layer"),
      name: "Background Layer",
      nodeIds: [] as string[],
      enabled: true,
      renderToBuffer: false,
    };
    project.layers.push(layer);
    node = createNode(NodeKind.Media, "Background", renderer.makeContext()) as MediaNode;
    node.start = 0;
    node.duration = project.duration;
    project.nodes.push(node);
    layer.nodeIds.push(node.id);
    renderer.attach(node);
    createdLayer = layer;
  }
  const before = createdLayer
    ? { present: false, assetId: null as string | null, imageUrl: null as string | null }
    : { present: true, assetId: node.assetId, imageUrl: node.imageUrl };
  if (url) {
    const asset = registerAsset(assets.addImage(name, url, 0, 0));
    void assets.load(asset);
    node.assetId = asset.id;
    node.imageUrl = null;
  } else {
    node.assetId = null;
    node.imageUrl = null;
  }
  const after = { present: true, assetId: node.assetId, imageUrl: node.imageUrl };
  const apply = (state: {
    present: boolean;
    assetId: string | null;
    imageUrl: string | null;
  }): void => {
    if (!state.present) {
      project.nodes = project.nodes.filter((entry) => entry !== node);
      if (createdLayer) project.layers = project.layers.filter((entry) => entry !== createdLayer);
      renderer.detach(node);
    } else {
      if (createdLayer) {
        if (!project.layers.includes(createdLayer)) project.layers.push(createdLayer);
        createdLayer.nodeIds = [node.id];
        if (!project.nodes.includes(node)) project.nodes.push(node);
        renderer.attach(node);
      }
      node.assetId = state.assetId;
      node.imageUrl = state.imageUrl;
    }
    sortNodesByLayers();
    syncNodeOrder();
    refreshTree();
    refreshInspector();
  };
  history.push({
    label: url ? "set background image" : "clear background image",
    undo: () => apply(before),
    redo: () => apply(after),
  });
  refreshTree();
  refreshInspector();
  setStatus(url ? `Background image set to ${name}.` : "Background image cleared.");
}

function addNodeOfKind(
  kind: NodeKind,
  name: string,
  layerId?: string,
  configure?: (node: AnyNode) => void,
): void {
  const node = createNode(kind, name, renderer.makeContext());
  // Preset-created items are configured before they join the history entry,
  // so one undo removes the item and its preset together.
  configure?.(node);
  node.start = Math.round(time * 100) / 100;
  node.duration = Math.max(1, project.duration - node.start);
  project.nodes.push(node);
  node.trackRow = firstFreeTrackRow(node);
  const layer = layerId ? project.layers.find((entry) => entry.id === layerId) : undefined;
  if (layer) {
    lockLayerDimension(layer, node);
    if (!layer.nodeIds.includes(node.id)) layer.nodeIds.push(node.id);
  }
  bindAnalyzer(node, project.analyzers[0]?.id ?? null);
  const ownerId = node.analyzerId;
  renderer.attach(node);
  sortNodesByLayers();
  syncNodeOrder();

  history.push({
    label: `add ${name}`,
    undo: () => {
      project.nodes = project.nodes.filter((n) => n.id !== node.id);
      if (layer) layer.nodeIds = layer.nodeIds.filter((id) => id !== node.id);
      detachUser(project.analyzers, node.id);
      node.analyzerId = null;
      renderer.detach(node);
      selectedId = null;
      refreshTree();
      refreshInspector();
    },
    redo: () => {
      project.nodes.push(node);
      if (layer && !layer.nodeIds.includes(node.id)) layer.nodeIds.push(node.id);
      bindAnalyzer(node, ownerId);
      renderer.attach(node);
      syncNodeOrder();
      refreshTree();
    },
  });

  select(node.id);
  setStatus(`added ${name}`);
}

/** Remove the current selection (one item, layer, or a multi-selection). */
function deleteSelection(): void {
  if (!selectedId && selectedLayerId) {
    const layer = project.layers.find((entry) => entry.id === selectedLayerId);
    if (layer) deleteLayer(layer);
    return;
  }
  const ids = [...multiSelection];
  if (ids.length > 1) {
    if (!window.confirm(`Delete ${ids.length} objects?`)) return;
    for (const id of ids) {
      if (!findNode(id)) continue;
      selectedId = id;
      deleteSelected();
    }
    multiSelection.clear();
    selectedId = null;
    timeline.setSelection([]);
    refreshTree();
    refreshInspector();
    return;
  }
  deleteSelected();
}

function deleteSelected(): void {
  if (!selectedId) return;
  const node = findNode(selectedId);
  if (!node) return;
  const index = project.nodes.indexOf(node);
  const ownerId = node.analyzerId;
  const ownershipBefore = snapshotOwnership(project.analyzers);
  const layer = project.layers.find((entry) => entry.nodeIds.includes(node.id));
  const layerIndex = layer ? layer.nodeIds.indexOf(node.id) : -1;

  project.nodes.splice(index, 1);
  if (layer) layer.nodeIds = layer.nodeIds.filter((id) => id !== node.id);
  multiSelection.delete(node.id);
  project.automations = project.automations.filter((a) => a.nodeId !== node.id);
  detachUser(project.analyzers, node.id);
  node.analyzerId = null;
  const ownershipAfter = snapshotOwnership(project.analyzers);

  renderer.detach(node);
  selectedId = null;
  renderer.setGizmoTarget(null);
  timeline.setSelection([...multiSelection]);
  syncNodeOrder();
  refreshTree();
  refreshInspector();

  history.push({
    label: "remove object",
    undo: () => {
      project.nodes.splice(index, 0, node);
      if (layer) layer.nodeIds.splice(layerIndex, 0, node.id);
      restoreOwnership(project.analyzers, ownershipBefore);
      node.analyzerId = ownerId;
      renderer.attach(node);
      sortNodesByLayers();
      syncNodeOrder();
      refreshTree();
      refreshInspector();
    },
    redo: () => {
      project.nodes = project.nodes.filter((n) => n.id !== node.id);
      if (layer) layer.nodeIds = layer.nodeIds.filter((id) => id !== node.id);
      restoreOwnership(project.analyzers, ownershipAfter);
      node.analyzerId = null;
      renderer.detach(node);
      refreshTree();
      refreshInspector();
    },
  });
}

/** Ripple delete: remove the selected clips and close their gaps in each layer. */
function rippleDeleteSelection(): void {
  const ids =
    multiSelection.size > 0
      ? [...multiSelection]
      : selectedId
        ? [selectedId]
        : [];
  if (ids.length === 0) return;
  if (!window.confirm(`Ripple delete ${ids.length} clip${ids.length === 1 ? "" : "s"}?`)) return;
  const nodes = ids
    .map((id) => findNode(id))
    .filter((node): node is AnyNode => Boolean(node));
  if (nodes.length === 0) return;

  const beforeStarts = new Map(project.nodes.map((node) => [node.id, node.start]));
  const entries = nodes.map((node) => {
    const layer = project.layers.find((entry) => entry.nodeIds.includes(node.id));
    return {
      node,
      layer,
      index: project.nodes.indexOf(node),
      layerIndex: layer ? layer.nodeIds.indexOf(node.id) : -1,
      analyzerId: node.analyzerId,
      automations: project.automations.filter((automation) => automation.nodeId === node.id),
    };
  });
  const ownership = snapshotOwnership(project.analyzers);

  const apply = (): void => {
    // Close the gap from the latest clip backwards so earlier shifts stay valid.
    for (const entry of [...entries].sort((a, b) => b.node.start - a.node.start)) {
      const { node, layer } = entry;
      if (!layer) continue;
      const end = node.start + node.duration;
      for (const id of layer.nodeIds) {
        if (ids.includes(id)) continue;
        const other = findNode(id);
        if (other && other.start >= end - 1e-3) other.start -= node.duration;
      }
    }
    for (const entry of entries) {
      const { node, layer, automations } = entry;
      project.nodes = project.nodes.filter((candidate) => candidate !== node);
      if (layer) layer.nodeIds = layer.nodeIds.filter((id) => id !== node.id);
      project.automations = project.automations.filter(
        (automation) => !automations.includes(automation),
      );
      detachUser(project.analyzers, node.id);
      node.analyzerId = null;
      renderer.detach(node);
    }
    multiSelection.clear();
    selectedId = null;
    selectedLayerId = null;
    timeline.setSelection([]);
    renderer.setGizmoTarget(null);
    sortNodesByLayers();
    syncNodeOrder();
    refreshTree();
    refreshInspector();
    setStatus(`Ripple-deleted ${entries.length} clip${entries.length === 1 ? "" : "s"}.`);
  };

  apply();
  history.push({
    label: "ripple delete",
    undo: () => {
      for (const entry of entries) {
        project.nodes.splice(Math.min(entry.index, project.nodes.length), 0, entry.node);
        if (entry.layer) {
          entry.layer.nodeIds.splice(
            Math.min(Math.max(0, entry.layerIndex), entry.layer.nodeIds.length),
            0,
            entry.node.id,
          );
        }
        entry.node.analyzerId = entry.analyzerId;
        for (const automation of entry.automations) {
          if (!project.automations.includes(automation)) project.automations.push(automation);
        }
        renderer.attach(entry.node);
      }
      restoreOwnership(project.analyzers, ownership);
      for (const [id, start] of beforeStarts) {
        const node = findNode(id);
        if (node) node.start = start;
      }
      sortNodesByLayers();
      syncNodeOrder();
      refreshTree();
      refreshInspector();
    },
    redo: apply,
  });
}

function setStatus(message: string): void {
  statusBar.textContent = message;
}

/**
 * Bring the preview back into focus after a gallery click. The inspector can be
 * scrolled far down its tile grid, so a click should not leave the stage out of
 * view; `nearest` is a no-op when it is already visible.
 */
function focusPreview(): void {
  document.getElementById("stage-wrap")?.scrollIntoView({
    block: "nearest",
    inline: "nearest",
  });
}

let lastEditSnapshot = { undoDepth: 0, redoDepth: 0 };

function refreshHistoryButtons(): void {
  $<HTMLButtonElement>("#btn-undo").disabled = !history.canUndo();
  $<HTMLButtonElement>("#btn-redo").disabled = !history.canRedo();
  const snapshot = {
    undoDepth: history.canUndo() ? 1 : 0,
    redoDepth: history.canRedo() ? 1 : 0,
  };
  if (
    snapshot.undoDepth !== lastEditSnapshot.undoDepth ||
    snapshot.redoDepth !== lastEditSnapshot.redoDepth
  ) {
    lastEditSnapshot = snapshot;
  }
}

/* ------------------------------------------------------------------ */
/* Wiring                                                              */
/* ------------------------------------------------------------------ */

$("#btn-play").addEventListener("click", () => setPlaying(!playing));
$("#btn-stop").addEventListener("click", () => {
  setPlaying(false);
  time = 0;
});
function stepFrame(direction: 1 | -1): void {
  setPlaying(false);
  const frame = 1 / Math.max(1, project.fps);
  time = Math.max(0, Math.min(project.duration, time + direction * frame));
}
$("#btn-frame-prev").addEventListener("click", () => stepFrame(-1));
$("#btn-frame-next").addEventListener("click", () => stepFrame(1));
async function addMediaFromFile(file: File): Promise<void> {
  // Data URLs (not blob URLs) keep the upload valid across save/open.
  const url = await readFileAsDataUrl(file);
  const asset = registerAsset(assets.addImage(file.name, url, 0, 0));
  await assets.load(asset);
  const node = createNode(NodeKind.Media, file.name, renderer.makeContext()) as MediaNode;
  node.assetId = asset.id;
  node.start = Math.round(time * 100) / 100;
  node.duration = Math.max(1, project.duration - node.start);
  project.nodes.push(node);
  node.trackRow = firstFreeTrackRow(node);
  bindAnalyzer(node, project.analyzers[0]?.id ?? null);
  renderer.attach(node);
  syncNodeOrder();
  select(node.id);
  setStatus(`Loaded ${file.name}.`);
}

async function addVideoFromFile(file: File): Promise<void> {
  const url = await readFileAsDataUrl(file);
  registerAsset(assets.addVideo(file.name, url));
  const node = createNode(NodeKind.Video, file.name, renderer.makeContext()) as VideoNode;
  node.start = Math.round(time * 100) / 100;
  node.duration = Math.max(1, project.duration - node.start);
  project.nodes.push(node);
  node.trackRow = firstFreeTrackRow(node);
  // The controller setter mirrors src onto the <video> element and loads it.
  node
    .createControllerSetups()
    .controllers.find((controller) => controller.id === "media.src")
    ?.write(url);
  renderer.attach(node);
  syncNodeOrder();
  select(node.id);
  setStatus(`Loaded ${file.name}.`);
}

function pickMediaFile(): void {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (file) await addMediaFromFile(file);
  });
  input.click();
}

/** Reference Ctrl+H / toolbar eye: hide or reveal shy objects. */
function toggleShyLayers(): void {
  hideShyLayers = !hideShyLayers;
  renderer.setHideShyLayers(hideShyLayers);
  const button = $("#btn-shy");
  button.classList.toggle("active", !hideShyLayers);
  button.title = hideShyLayers ? "Show shy layers" : "Hide shy layers";
  setStatus(hideShyLayers ? "Shy layers hidden." : "Shy layers shown.");
  refreshTree();
}

$("#btn-add-layer").addEventListener("click", addCompositionLayer);
$("#btn-add-effect").addEventListener("click", () => openAddEffectDialog());
$("#btn-shy").addEventListener("click", () => toggleShyLayers());
$("#btn-render-settings").addEventListener("click", openCompositionSettings);
$("#btn-audio-settings").addEventListener("click", openAudioProcessing);
$("#btn-clear-objects").addEventListener("click", () => {
  if (project.nodes.length === 0) {
    setStatus("Nothing to clear.");
    return;
  }
  if (!window.confirm(`Remove all ${project.nodes.length} objects?`)) return;
  for (const node of project.nodes) renderer.disposeNode(node);
  for (const node of project.nodes) detachUser(project.analyzers, node.id);
  project.nodes = [];
  project.automations = [];
  selectedId = null;
  refreshTree();
  refreshInspector();
  setStatus("Cleared all objects.");
});

// Preview resolution picker, matching the reference's 360/480/720/1080 row.
// The value is the short side in the current orientation; the aspect select
// snaps to the nearest preset the same way module 145 does.
const RESOLUTION_SIDES = [360, 480, 720, 1080] as const;
type Aspect = "16:9" | "9:16" | "1:1";

function currentAspect(): Aspect {
  if (project.width > project.height) return "16:9";
  if (project.width < project.height) return "9:16";
  return "1:1";
}

function updateResolutionControls(): void {
  const side = Math.min(project.width, project.height);
  const nearest = RESOLUTION_SIDES.reduce((best, candidate) =>
    Math.abs(candidate - side) < Math.abs(best - side) ? candidate : best,
  );
  document.querySelectorAll<HTMLButtonElement>("#stage-res .res").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.res) === nearest);
  });
  const aspect = $("#aspect-select") as HTMLSelectElement | null;
  if (aspect) aspect.value = currentAspect();
}

function applyResolution(shortSide?: number, aspect?: Aspect): void {
  const mode = aspect ?? currentAspect();
  const side = shortSide ?? Math.min(project.width, project.height);
  let width = side;
  let height = side;
  if (mode === "16:9") {
    height = side;
    width = Math.round((side * 16) / 9 / 2) * 2;
  } else if (mode === "9:16") {
    width = side;
    height = Math.round((side * 16) / 9 / 2) * 2;
  }
  project.width = width;
  project.height = height;
  renderer.resize();
  updateResolutionControls();
  setStatus(`Canvas set to ${width}×${height}.`);
}

$("#stage-res").addEventListener("click", (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>(".res");
  if (!button) return;
  const height = Number(button.dataset.res);
  if (!height) return;
  applyResolution(height);
});
$<HTMLSelectElement>("#aspect-select").addEventListener("change", (event) => {
  applyResolution(undefined, (event.target as HTMLSelectElement).value as Aspect);
});
updateResolutionControls();
$("#btn-3d").addEventListener("click", () => toggle3D());

// Drop target: audio goes through the analyser, images become media objects.
let dragDepth = 0;
const hint = $("#drop-hint");
$("#stage-wrap").addEventListener("dragenter", (event) => {
  event.preventDefault();
  dragDepth += 1;
  hint.hidden = false;
});
$("#stage-wrap").addEventListener("dragover", (event) => {
  event.preventDefault();
});
$("#stage-wrap").addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) hint.hidden = true;
});
$("#stage-wrap").addEventListener("drop", async (event) => {
  event.preventDefault();
  dragDepth = 0;
  hint.hidden = true;
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  if (file.type === "application/json" || file.name.toLowerCase().endsWith(".json")) {
    try {
      await importProjectJson(JSON.parse(await file.text()));
    } catch (error) {
      setStatus(`Import failed: ${error instanceof Error ? error.message : String(error)}`);
    }
    return;
  }
  if (file.type.startsWith("audio/")) {
    setStatus(await loadAudioFromBytes(file.name, new Uint8Array(await file.arrayBuffer())));
    return;
  }
  if (file.type.startsWith("image/")) {
    const node = selectedId ? findNode(selectedId) : null;
    if (node instanceof SpectrumNode) {
      const url = await readFileAsDataUrl(file);
      const asset = registerAsset(assets.addImage(file.name, url, 0, 0));
      await assets.load(asset);
      node.assetId = asset.id;
      refreshInspector();
      setStatus(`Spectrum fill set to ${file.name}.`);
      return;
    }
    await addMediaFromFile(file);
    return;
  }
  setStatus(`${file.name}: ${file.type || "unknown type"} is not supported yet.`);
});

/**
 * Materialise a decompiled preset's per-layer analysers.
 *
 * The reference creates a fresh analyzer for every layer on every preset apply
 * (it never reuses the previous preset's analyzer ids). We do the same: reusing
 * stable ids kept old wasm analyser instances and band history alive, so the
 * same preset could react differently depending on what had been applied before.
 */
let presetApplySerial = 0;

function materializePresetAnalyzers(preset: Preset, node: SpectrumNode): string[] {
  const snapshot = preset.snapshot;
  if (!snapshot) return [];

  detachUser(project.analyzers, node.id);
  // Drop analysers left behind by a previous preset on this item; keep anything
  // another item still owns, and never touch project-imported analysers. This
  // also runs for a preset that ships no analysers (Sunburst Bars reads the
  // item's own band series), so applying it cannot inherit the previous tile's
  // analyser rows ΓÇö otherwise the project state would depend on click order.
  project.analyzers = project.analyzers.filter(
    (analyzer) =>
      analyzer.users.length > 0 || !/^analyzer_(?:preset|trap)_/.test(analyzer.id),
  );
  if (!snapshot.analyzers?.length) return [];

  const run = ++presetApplySerial;
  return snapshot.analyzers.map((settings, index) => {
    const id = `analyzer_preset_${preset.id}_${run}_${index}`;
    const analyzer = createAnalyzer(id, `Layer ${index + 1}`);
    project.analyzers.push(analyzer);

    analyzer.name = String(settings.name ?? `Analyzer (${index + 1})`);
    analyzer.sampleProvider =
      settings.sampleProvider === "filter bank" ? "filter bank" : "goertzel";
    if (typeof settings.outputMultiplier === "number") {
      analyzer.outputMultiplier = settings.outputMultiplier;
    }
    if (typeof settings.sampleOutCount === "number") {
      analyzer.sampleOutCount = settings.sampleOutCount;
    }
    if (typeof settings.audioDuration === "number") {
      analyzer.audioDuration = settings.audioDuration;
    }
    if (typeof settings.audioOffset === "number") {
      analyzer.audioOffset = settings.audioOffset;
    }
    if (Array.isArray(settings.frequencyRange) && settings.frequencyRange.length >= 2) {
      analyzer.frequencyRange = [
        Number(settings.frequencyRange[0]),
        Number(settings.frequencyRange[1]),
      ];
    }
    if (typeof settings.windowFunction === "string") {
      analyzer.windowFunction = settings.windowFunction;
    }
    if (typeof settings.smoothingTimeConstant === "number") {
      analyzer.smoothingTimeConstant = settings.smoothingTimeConstant;
    }
    if (typeof settings.audioReactionAlignment === "number") {
      analyzer.audioReactionAlignment = settings.audioReactionAlignment;
    }
    if (typeof settings.windowParameter === "number") {
      analyzer.windowParameter = settings.windowParameter;
    }
    if (typeof settings.windowSkew === "number") analyzer.windowSkew = settings.windowSkew;
    if (typeof settings.frequencyScale === "string") {
      analyzer.frequencyScale = settings.frequencyScale;
    }
    if (typeof settings.hzLinearFactor === "number") {
      analyzer.hzLinearFactor = settings.hzLinearFactor;
    }
    if (typeof settings.cqtResolution === "number") {
      analyzer.cqtResolution = settings.cqtResolution;
    }
    if (typeof settings.cqtWindowFunction === "string") {
      analyzer.cqtWindowFunction = settings.cqtWindowFunction;
    }
    if (typeof settings.cqtWindowParameter === "number") {
      analyzer.cqtWindowParameter = settings.cqtWindowParameter;
    }
    if (typeof settings.cqtWindowSkew === "number") {
      analyzer.cqtWindowSkew = settings.cqtWindowSkew;
    }
    if (typeof settings.cqtBandwidth === "number") analyzer.cqtBandwidth = settings.cqtBandwidth;
    if (typeof settings.spectrumConstantQ === "boolean") {
      analyzer.spectrumConstantQ = settings.spectrumConstantQ;
    }
    if (typeof settings.perBinFrequencyTilt === "number") {
      analyzer.perBinFrequencyTilt = settings.perBinFrequencyTilt;
    }
    if (typeof settings.perBandFrequencyTilt === "number") {
      analyzer.perBandFrequencyTilt = settings.perBandFrequencyTilt;
    }
    if (typeof settings.perBandWeighting === "string") {
      analyzer.perBandWeighting = settings.perBandWeighting.toLowerCase();
    }
    if (typeof settings.perBandWeightingAmount === "number") {
      analyzer.perBandWeightingAmount = settings.perBandWeightingAmount;
    }
    if (typeof settings.downSample === "boolean") analyzer.downSample = settings.downSample;
    if (!analyzer.users.includes(node.id)) analyzer.users.push(node.id);
    return id;
  });
}

/** Rebuild the analyzer set the Trap Motion preset expects. */
function configureTrapMotion(node: SpectrumNode): void {
  // From the reference project itself (its exported JSON): one analyzer per
  // layer, goertzel provider, 64 bands over 20-110 Hz, raised-cosine window,
  // multiplier 50.5, and a window that grows by 15ms per layer (125ms, 140ms,
  // ...). The short windows are what make it react quickly; the window
  // difference is what separates the layers into a colour fringe.
  //
  // The reference spans 125..215ms across its seven layers. Keeping that range
  // (rather than a fixed 15ms step) means adding colour layers does not slow the
  // reaction down: with seven layers this is exactly 125 + 15 * index.
  const span = 90;
  const step = node.layers.length > 1 ? span / (node.layers.length - 1) : 0;
  detachUser(project.analyzers, node.id);
  project.analyzers = project.analyzers.filter(
    (analyzer) =>
      analyzer.users.length > 0 || !/^analyzer_(?:preset|trap)_/.test(analyzer.id),
  );
  const created = node.layers.map((_, index) =>
    createAnalyzer(`analyzer_trap_${index}`, `Layer ${index + 1}`, {
      sampleProvider: "goertzel",
      outputMultiplier: 50.5,
      sampleOutCount: 64,
      audioDuration: Math.round(125 + step * index),
      frequencyRange: [20, 110],
      windowFunction: "raised cosine",
      audioOffset: 65,
    }),
  );
  created.forEach((analyzer) => analyzer.users.push(node.id));
  project.analyzers.push(...created);
  node.layers.forEach((layer, index) => {
    layer.audioAnalyzer = created[index]?.id ?? null;
  });
}
/** Importing a project cancels the boot-time default track load. */
let defaultTrackSuppressed = false;

async function importProjectJson(raw: unknown): Promise<ImportReport> {
  defaultTrackSuppressed = true;
  // Invalidate a boot-track decode that started before this import: it must not
  // land afterwards and stretch the imported clips to the old duration.
  audioLoadToken += 1;
  // Our own save format: restore it directly instead of treating it as a
  // captured reference project.
  if (isProjectSnapshot(raw)) {
    applyProjectSnapshot(raw);
    return {
      name: raw.project.name,
      nodes: raw.nodes.length,
      layers: raw.layers.length,
      compositionLayers: raw.layers.length,
      analyzers: raw.analyzers.length,
      effects: raw.effects.length,
      automations: raw.automations.length,
      media: [],
      notes: ["Opened a saved editor project."],
      skipped: [],
    };
  }
  for (const node of project.nodes) renderer.disposeNode(node);
  renderer.resetLayers();
  const report = applyProjectExport(project, raw, {
    createNode: (kind, name) => createNode(kind, name, renderer.makeContext()),
  });
  // A restored playhead may sit past a shorter imported project.
  if (time > project.duration) time = 0;
  normalizeTrackRows();
  renderer.retainAnalyzers(project.analyzers.map((analyzer) => analyzer.id));
  for (const node of project.nodes) renderer.attach(node);
  // The imported WebGLManager resolution becomes the render size; the canvas
  // CSS size may not change, so the ResizeObserver never fires on its own.
  renderer.resize();
  updateResolutionControls();
  selectedId = null;
  // The old history references the disposed project; an undo would splice its
  // objects back into the imported one.
  history.clear();

  // Fetch any imported images; a failure leaves MediaNode's procedural stand-in.
  let loaded = 0;
  for (const media of report.media) {
    const node = findNode(media.nodeId);
    if (!(node instanceof MediaNode)) continue;
    try {
      const response = await fetch(media.url);
      if (!response.ok) continue;
      const blob = await response.blob();
      const asset = registerAsset(
        assets.addImage(`${node.name} (imported)`, URL.createObjectURL(blob), 0, 0),
      );
      await assets.load(asset);
      node.assetId = asset.id;
      // Blob URLs die with the page; keep the source URL for a later restore.
      node.imageUrl = media.url;
      loaded += 1;
    } catch {
      /* keep the stand-in */
    }
  }

  // The reference Audio object loads the project's own track through `src`.
  // Keep the imported clip spans; only the audio changes.
  let audioWarning: { what: string; reason: string } | null = null;
  const rawValues = (raw as { values?: Record<string, unknown> }).values;
  const audioValue = rawValues?.["Audio"];
  const audioRecord =
    audioValue && typeof audioValue === "object"
      ? (audioValue as Record<string, unknown>)
      : null;
  const sourceUrl =
    typeof audioRecord?.src === "string" && audioRecord.src
      ? audioRecord.src
      : typeof (raw as { audioName?: unknown }).audioName === "string"
        ? (raw as { audioName: string }).audioName
        : "";
  let audioLoaded = false;
  // Stop the previous project's track before the (possibly slow) fetch so the
  // old song never plays over the new project while its audio downloads.
  if (playing) audio.stop();
  if (sourceUrl) {
    try {
      const response = await fetch(sourceUrl);
      if (!response.ok) throw new Error(String(response.status));
      const bytes = new Uint8Array(await response.arrayBuffer());
      const filename = (() => {
        try {
          const url = new URL(sourceUrl, window.location.href);
          const decoded = decodeURIComponent(url.pathname.split("/").pop() || "");
          return decoded.split("/").pop() || "reference-track.mp3";
        } catch {
          return "reference-track.mp3";
        }
      })();
      await loadAudioFromBytes(filename, bytes, { resetSpans: false, computeImpact: false });
      audioLoaded = true;
    } catch {
      audioWarning = {
        what: "Audio",
        reason: "The project's audio track could not be fetched.",
      };
    }
  }
  // The imported project owns the track. If it has none (or the reference URL
  // is gone, e.g. burning-moon), do not leave the previous/boot song playing:
  // stop it and clear the buffers so export cannot mux the wrong track either.
  if (!audioLoaded) {
    if (playing) audio.stop();
    decodedAudioBuffer = null;
    audioBuffer = null;
    processedAudioBuffer = null;
    audioFile = null;
    audioTrackName = "";
    waveformPeaks = null;
    analyserAudioKey = "";
    const silent = audio.context.createBuffer(1, 1, audio.context.sampleRate);
    spectrum.setSource(new BufferSource(silent, "No audio"));
    timeline.setWaveform(null, "No audio");
    const audioNameLabel = document.querySelector<HTMLElement>("#audio-name");
    if (audioNameLabel) audioNameLabel.textContent = "No audio";
  }

  syncNodeOrder();
  refreshTree();
  refreshInspector();
  refreshStack();
  applyAudioSettings();

  const warnings = [
    ...(audioWarning ? [audioWarning] : []),
    ...report.skipped,
    ...report.notes.map((note) => ({ what: "Approximation", reason: note })),
  ];
  if (report.media.length > loaded) {
    warnings.push({
      what: "Media",
      reason: `${report.media.length - loaded} imported image(s) could not be fetched.`,
    });
  }
  setEditorWarnings(warnings);

  const skipped = report.skipped.length ? `, ${report.skipped.length} skipped` : "";
  const images = report.media.length ? `, ${loaded}/${report.media.length} images` : "";
  const notes = report.notes.length ? `, ${report.notes.length} approximated` : "";
  setStatus(
    `Imported "${report.name}": ${report.nodes} items, ${report.layers} layers, ` +
      `${report.analyzers} analyzers, ${report.effects} effects, ` +
      `${report.automations} automations${images}${notes}${skipped}.`,
  );
  return report;
}

function importProjectFile(): void {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "application/json,.json";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    try {
      await importProjectJson(JSON.parse(await file.text()));
    } catch (error) {
      setStatus(`Import failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  });
  input.click();
}

$("#btn-frames").addEventListener("click", () => {
  displaySeconds = !displaySeconds;
  localStorage.setItem("studio:displaySeconds", displaySeconds ? "1" : "0");
  setStatus(displaySeconds ? "Time shown in seconds." : "Time shown in frames.");
});
$("#btn-fullscreen").addEventListener("click", () => {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void document.documentElement.requestFullscreen();
});
$("#btn-external").addEventListener("click", () => {
  window.open(`${location.pathname}?preview=1`, "_blank", "noopener");
});

// A preview tab renders the stage only, the way the reference's external preview does.
if (new URLSearchParams(location.search).get("preview") === "1") {
  document.body.classList.add("preview-mode");
}

$("#btn-delete").addEventListener("click", deleteSelection);
$("#btn-note").addEventListener("click", () => {
  const node = selectedId
    ? findNode(selectedId)
    : selectedLayerId
      ? layerNodeFor(selectedLayerId)
      : null;
  if (!node) {
    setStatus("Select an object first.");
    return;
  }
  const note = window.prompt("Note", (node as unknown as { note?: string }).note ?? "");
  if (note === null) return;
  (node as unknown as { note?: string }).note = note;
  setStatus(`Note saved on ${node.name}.`);
});
$("#btn-edit-automations").addEventListener("click", () => {
  if (!selectedId) {
    setLeftPanel("automations");
    return;
  }
  inspectorAutomationView = !inspectorAutomationView;
  const button = $("#btn-edit-automations");
  button.title = inspectorAutomationView ? "Edit controllers" : "Edit automations";
  button.classList.toggle("on", inspectorAutomationView);
  refreshInspector();
});
$("#btn-reset").addEventListener("click", resetSelected);
$("#btn-item-effect").addEventListener("click", () => setLeftPanel("effects"));

/** Reference "Reset": clear the object's keyframes and property edits. */
function resetSelected(): void {
  const node = selectedId ? findNode(selectedId) : null;
  if (!node) {
    setStatus("Select an object to reset.");
    return;
  }
  if (!window.confirm(`Reset ${node.name}? Keyframes and property edits will be cleared.`)) return;
  project.automations = project.automations.filter((automation) => automation.nodeId !== node.id);
  const reset = (node as unknown as { initializeObjectMapping?: () => void }).initializeObjectMapping;
  reset?.call(node);
  node.sync(time);
  refreshTree();
  refreshInspector();
  refreshStack();
  setStatus(`Reset ${node.name}.`);
}

inspectorTitle.style.cursor = "pointer";
inspectorTitle.title = "Show object list";
inspectorTitle.addEventListener("click", () => select(null));

$("#btn-undo").addEventListener("click", () => {
  const entry = history.undo();
  if (entry) setStatus(`undo: ${entry.label}`);
  refreshHistoryButtons();
  refreshTree();
  refreshInspector();
});
$("#btn-redo").addEventListener("click", () => {
  const entry = history.redo();
  if (entry) setStatus(`redo: ${entry.label}`);
  refreshHistoryButtons();
  refreshTree();
  refreshInspector();
});

$("#zoom-in").addEventListener("click", () => {
  zoom = Math.min(8, zoom * 1.4);
  timeline.setZoom(zoom, time);
});
$("#zoom-out").addEventListener("click", () => {
  zoom = Math.max(0.5, zoom / 1.4);
  timeline.setZoom(zoom, time);
});
const zoomSlider = $<HTMLInputElement>("#zoom-slider");
zoomSlider.addEventListener("input", () => {
  zoom = Math.max(0.5, Math.min(8, Number(zoomSlider.value)));
  timeline.setZoom(zoom, time);
});
$("#btn-fit").addEventListener("click", () => {
  zoom = 1;
  timeline.fit();
});
$("#btn-snap").addEventListener("click", (event) => {
  const enabled = !timeline.getSnapEnabled();
  timeline.setSnapEnabled(enabled);
  (event.currentTarget as HTMLElement).classList.toggle("on", enabled);
  setStatus(`Snapping ${enabled ? "on" : "off"}.`);
});
function setTimelineTool(tool: "select" | "hand" | "razor" | "slip"): void {
  timeline.setTool(tool);
  $("#tool-select").classList.toggle("on", tool === "select");
  $("#tool-hand").classList.toggle("on", tool === "hand");
  $("#tool-razor").classList.toggle("on", tool === "razor");
  $("#tool-slip").classList.toggle("on", tool === "slip");
  const label =
    tool === "select" ? "Select" : tool === "hand" ? "Hand" : tool === "razor" ? "Razor" : "Slip";
  setStatus(`${label} tool.`);
}
$("#tool-select").addEventListener("click", () => setTimelineTool("select"));
$("#tool-hand").addEventListener("click", () => setTimelineTool("hand"));
$("#tool-razor").addEventListener("click", () => setTimelineTool("razor"));
$("#tool-slip").addEventListener("click", () => setTimelineTool("slip"));

$("#btn-loop").addEventListener("click", (event) => {
  loop = !loop;
  (event.currentTarget as HTMLElement).classList.toggle("on", loop);
});
$("#btn-keyframes").addEventListener("click", toggleKeyframes);

function buildWaveformPeaks(buffer: AudioBuffer, buckets = 2048): Float32Array {
  const data = buffer.getChannelData(0);
  const peaks = new Float32Array(buckets);
  if (data.length === 0) return peaks;
  const step = Math.max(1, Math.floor(data.length / buckets));
  for (let bucket = 0; bucket < buckets; bucket += 1) {
    const from = bucket * step;
    const to = Math.min(data.length, from + step);
    let peak = 0;
    for (let index = from; index < to; index += 1) {
      const value = Math.abs(data[index]);
      if (value > peak) peak = value;
    }
    peaks[bucket] = peak;
  }
  return peaks;
}

/**
 * The reference caches a track's maximum audio impact in the project
 * (`audioImpact.max`) and every audio-impact automation normalises its
 * `hypot(bands)` by it. Imported projects carry the reference's value; a track
 * chosen by the user gets a fresh scan over the processed buffer.
 *
 * The magnitude uses the same analyzer output the automation samples and the
 * same 800 calibration factor as `domain/audio-impact.ts`, so the loudest moment
 * of the track lands at the top of the automation's range.
 */
async function computeAudioImpactMax(): Promise<void> {
  const analyzer = project.analyzers[0];
  if (!analyzer) return;
  // The normaliser only feeds audio-impact automations. A project without one
  // (the usual case when someone just drops an MP3 onto a plain composition)
  // does not need the scan at all.
  const usesImpact = project.automations.some(
    (automation) => automation.type === "audioImpact" && automation.enabled !== false,
  );
  if (!usesImpact) {
    renderer.setFrameTime(time);
    return;
  }
  const token = ++impactScanToken;
  // The normalisation maximum only needs the loudest moment, not every frame.
  // A 10 Hz walk is 6x cheaper than the old 60 Hz one; the result is cached per
  // track, so a page reload (including Vite's HMR reload) skips the scan
  // entirely instead of blocking the preview for a minute.
  const cacheKey = `studio:impact:${audioTrackName || "track"}:${Math.round(project.duration * 1000)}:${analyzer.id}:${analyzer.sampleOutCount}`;
  let cached = 0;
  try {
    cached = Number(localStorage.getItem(cacheKey)) || 0;
  } catch {
    cached = 0;
  }
  if (cached > 0) {
    project.audioImpactMax = cached;
    renderer.setFrameTime(time);
    return;
  }
  // Let the load status/first frame paint before the scan starts.
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
  if (token !== impactScanToken) return;
  const context = renderer.makeContext();
  const step = 0.1;
  const frames = Math.max(1, Math.ceil(project.duration / step));
  // The reference scans with one analyser; `spectrumFor` would run every open
  // analyser (13 in a template) for each of these ~2000 steps.
  const sampleBands = context.spectrumScanFor ?? context.spectrumFor;
  let max = 0;
  // Time-budgeted slices: the analyser's per-window cost depends on the track
  // and the engine (wasm vs JS), so a fixed batch size either stalls slow
  // machines or spends seconds in timer clamping on fast ones. `MessageChannel`
  // yields without setTimeout's 4ms clamp, and ~8ms slices keep the preview
  // responsive.
  const yieldToLoop = (): Promise<void> =>
    new Promise<void>((resolve) => {
      if (typeof MessageChannel !== "undefined") {
        const channel = new MessageChannel();
        channel.port1.onmessage = () => resolve();
        channel.port2.postMessage(null);
      } else {
        setTimeout(resolve, 0);
      }
    });
  let sliceStart = performance.now();
  for (let index = 0; index <= frames; index += 1) {
    const at = index * step;
    renderer.setFrameTime(at);
    const bands = sampleBands?.call(context, analyzer.id);
    if (bands && bands.length > 0) {
      let sum = 0;
      for (let band = 0; band < bands.length; band += 1) {
        const value = bands[band];
        sum += value * value;
      }
      const magnitude = Math.sqrt(sum) * REFERENCE_VALUE_SCALE;
      if (magnitude > max) max = magnitude;
    }
    if (performance.now() - sliceStart >= 8) {
      await yieldToLoop();
      if (token !== impactScanToken) return;
      sliceStart = performance.now();
    }
  }
  if (token !== impactScanToken || !(max > 0)) return;
  project.audioImpactMax = max;
  try {
    localStorage.setItem(cacheKey, String(max));
  } catch {
    /* storage may be unavailable */
  }
  // The scan walks the analyzer across the whole track; leave the live
  // analysers at a clean starting point instead of mid-scan smoothing history.
  renderer.resetAnalysers();
  renderer.setFrameTime(time);
}

/**
 * Make sure a project that has audio-impact rows also has a normaliser.
 *
 * `computeAudioImpactMax` bails out when the project has no impact row, and it
 * only runs when a track loads. A row created afterwards (the automations
 * dialog, `React to audio`, choosing an analyzer on a background, enabling a
 * disabled row, undo/redo) therefore had `audioImpactMax === 0`, and
 * `AudioImpactEngine.sample` returns `min` for that value - the item sat still
 * even with a live analyzer. Ask for one scan per track; the scan caches its
 * result, and a track with no signal stays at 0 instead of rescanning every time
 * the check runs.
 */
function ensureAudioImpactNormaliser(): void {
  if (project.audioImpactMax > 0) return;
  if (!audioBuffer) return;
  const usesImpact = project.automations.some(
    (automation) => automation.type === "audioImpact" && automation.enabled !== false,
  );
  if (!usesImpact) return;
  const key = `${audioTrackName || "track"}:${Math.round(project.duration * 1000)}`;
  if (impactNormaliserScannedFor === key) return;
  impactNormaliserScannedFor = key;
  impactScanPromise = computeAudioImpactMax();
}

async function loadAudioFromBytes(
  name: string,
  bytes: Uint8Array,
  options: { resetSpans?: boolean; computeImpact?: boolean } = {},
): Promise<string> {
  // A chosen track always wins over the boot-time default, even when the
  // default's download is still in flight (it otherwise landed later and
  // silently replaced the loaded audio).
  defaultTrackSuppressed = true;
  // A later load (e.g. an import's own track) invalidates this one even if its
  // decode started earlier and finishes afterwards.
  const loadToken = ++audioLoadToken;
  // Cancel any impact scan still walking the previous track.
  impactScanToken += 1;
  // The live source keeps playing the old buffer until it is stopped, so an
  // import used to keep the boot/default song audible until the user pressed
  // stop/play. Stop it now; the new buffer is started below once decoded.
  if (playing) audio.stop();
  // decodeAudioData detaches the buffer it is given, so decode from one copy and
  // keep an untouched copy for the export muxer.
  const decodeCopy = bytes.slice();
  const buffer = await audio.context.decodeAudioData(decodeCopy.buffer);
  if (loadToken !== audioLoadToken) return `${name} - superseded by a newer track`;
  waveformPeaks = buildWaveformPeaks(buffer);
  timeline.setWaveform(waveformPeaks, name);
  decodedAudioBuffer = buffer;
  audioBuffer = buffer;
  processedAudioBuffer = null;
  audioTrackName = name;
  const audioNameLabel = document.querySelector<HTMLElement>("#audio-name");
  if (audioNameLabel) audioNameLabel.textContent = name;
  audioFile = { name: name.replace(/[^\w.-]/g, "_"), bytes: bytes.slice() };
  analyserAudioKey = "";
  // A new track gets its own normaliser scan.
  impactNormaliserScannedFor = "";
  await refreshAnalyserAudio(true);
  if (loadToken !== audioLoadToken) return `${name} - superseded by a newer track`;
  // Imported projects carry their own clip spans; only a track chosen by the
  // user (or the boot track) stretches every item to the new audio.
  if (options.resetSpans !== false) {
    for (const node of project.nodes) {
      node.start = 0;
      node.duration = project.duration;
    }
  }
  // A user-chosen track defines the project's impact normaliser; restores and
  // imports carry their own reference value and must keep it.
  if (options.computeImpact ?? options.resetSpans !== false) {
    impactScanPromise = computeAudioImpactMax();
  }
  // Keep the playhead when the new track can contain it: a reload restores the
  // viewer's position from sessionStorage, and the boot track must not reset it
  // to a silent 0.
  if (time > buffer.duration) time = 0;
  // Keep the transport running after a mid-playback track swap (template import
  // or a chosen file): start the freshly decoded buffer instead of leaving the
  // user on silence until they press stop/play.
  if (playing) audio.play(audioBuffer, time);
  refreshTree();
  refreshInspector();
  return `${name} - ${buffer.duration.toFixed(2)}s, ${buffer.numberOfChannels}ch @ ${buffer.sampleRate} Hz`;
}

/**
 * Reference `onAudioChanged`: the analysers see the buffer processed by the
 * bass/attenuator/compressor/playback-rate graph, not the raw decode. Preview
 * playback still uses the raw buffer with the equivalent live chain, but the
 * visuals must follow the processed result.
 */
async function refreshAnalyserAudio(force = false): Promise<void> {
  const raw = decodedAudioBuffer;
  if (!raw) return;
  const settings = project.audioSettings;
  const key = JSON.stringify([
    settings.bassBoost,
    settings.frequency,
    settings.playbackRate,
    settings.attenuator,
    settings.additionalGainDb,
    settings.compressor,
  ]);
  if (!force && key === analyserAudioKey) return;
  const token = ++audioProcessToken;
  const processed = await audio.process(raw, settings);
  // A newer load or settings change superseded this render.
  if (token !== audioProcessToken) return;
  analyserAudioKey = key;
  processedAudioBuffer = processed;
  spectrum.setSource(new BufferSource(processed, audioTrackName));
  project.duration = Math.max(1, Math.round(processed.duration * 100) / 100);
  // Changing the playback rate shortens the project; keep the playhead inside
  // the new span so playback does not start past the end of the track.
  if (time > project.duration) time = project.duration;
}

$("#btn-audio").addEventListener("click", () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "audio/*";
  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    if (!file) return;
    setStatus(`decoding ${file.name}…`);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      setStatus(`loaded ${await loadAudioFromBytes(file.name, bytes)}`);
    } catch (error) {
      setStatus(`audio load failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  });
  input.click();
});

$("#btn-export").addEventListener("click", openExportDialog);

let exporting = false;
// CAMXORA-PATCH (scripts/sync-vizzy.mjs): when the shell drives an export,
// runExport() reports progress and checks the host's cancel flag here.
let camxoraExportHooks: {
  progress(done: number, total: number, stage: string): void;
  cancelled(): boolean;
} | null = null;

interface ExportSettings {
  width: number;
  height: number;
  fps: number;
  start: number;
  end: number;
  /** ffmpeg.wasm (x264/VPx) or the browser's WebCodecs encoder. */
  engine: "wasm" | "webcodecs";
  codec: ExportCodec;
  /** Video bitrate in Mbps; 0 lets the encoder choose. */
  bitrate: number;
  /** x264 CRF used when the bitrate is 0. */
  crf: number;
  /** x264 speed preset. */
  preset: string;
  /** H.264 profile. */
  profile: string;
  /** Audio bitrate in kbps. */
  audioBitrate: number;
}

/** Reference defaults: bitrate tracks the chosen resolution. */
function defaultExportBitrate(height: number): number {
  if (height <= 360) return 5;
  if (height <= 480) return 5;
  if (height <= 720) return 15;
  if (height <= 1080) return 25;
  if (height <= 1440) return 50;
  if (height <= 2160) return 75;
  return 16;
}

/** Reference filename pattern: "<project> - <timestamp>.<ext>". */
function exportFilename(ext: string): string {
  const base =
    (project.name || "MyVideo")
      .trim()
      .replace(/[\\/:*?"<>|]+/g, "-")
      .replace(/\s+/g, " ")
      .slice(0, 60) || "MyVideo";
  const stamp = new Date()
    .toISOString()
    .slice(0, 19)
    .replace(/[:T]/g, "-");
  return `${base} - ${stamp}.${ext}`;
}

function defaultExportSettings(): ExportSettings {
  return {
    width: 1280,
    height: 720,
    fps: 60,
    start: 0,
    end: project.duration,
    engine: "wasm",
    codec: "h264",
    bitrate: defaultExportBitrate(720),
    crf: 20,
    preset: "veryfast",
    profile: "high",
    audioBitrate: 192,
  };
}

interface SaveFileHandle {
  name: string;
  createWritable(): Promise<{
    write(
      data:
        | Blob
        | { type: "write"; position: number; data: Uint8Array<ArrayBuffer> },
    ): Promise<void>;
    close(): Promise<void>;
    abort?(reason?: unknown): Promise<void>;
  }>;
}

type SaveFilePicker = (options: {
  suggestedName?: string;
  types?: { description: string; accept: Record<string, string[]> }[];
}) => Promise<SaveFileHandle>;

interface ExportProgressUi {
  isCancelled(): boolean;
  update(done: number, total: number, stage: string): void;
  succeed(result: ExportResult, savedName?: string): void;
  fail(message: string): void;
  markCancelled(): void;
}

/** Live export dialog: phase, bar, frame counts, elapsed/remaining and cancel. */
function openExportProgress(
  settings: ExportSettings,
  total: number,
): ExportProgressUi {
  document.querySelector(".modal-backdrop")?.remove();
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop export-progress-backdrop";
  const modal = document.createElement("div");
  modal.className = "modal export-progress";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");

  const head = document.createElement("header");
  head.className = "modal-head modal-head-row";
  head.append(icon("play_arrow", 16), document.createTextNode("Exporting video"));

  const body = document.createElement("div");
  body.className = "modal-body";
  const summary = document.createElement("p");
  summary.className = "export-summary";
  const typeLabel =
    settings.codec === "h264" ? "H.264 · MP4" : settings.codec === "vp9" ? "VP9 · WebM" : "VP8 · WebM";
  summary.textContent = `${settings.width}×${settings.height} · ${settings.fps} fps · ${typeLabel} · ${settings.start.toFixed(2)}–${settings.end.toFixed(2)}s`;

  const track = document.createElement("div");
  track.className = "export-track";
  const fill = document.createElement("div");
  fill.className = "export-fill";
  track.append(fill);

  const meta = document.createElement("div");
  meta.className = "export-meta";
  const stage = document.createElement("span");
  stage.className = "export-stage";
  stage.textContent = "Preparing…";
  const percent = document.createElement("span");
  percent.className = "export-percent";
  percent.textContent = "0%";
  meta.append(stage, percent);

  const detail = document.createElement("div");
  detail.className = "export-detail";
  detail.textContent = `frame 0 / ${total}`;

  body.append(summary, track, meta, detail);

  const foot = document.createElement("footer");
  foot.className = "modal-foot";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  foot.append(cancel);

  modal.append(head, body, foot);
  backdrop.append(modal);
  document.body.append(backdrop);

  let cancelled = false;
  let finished = false;
  const started = performance.now();
  let timer = 0;

  const clock = (seconds: number): string => {
    const whole = Math.max(0, Math.round(seconds));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  };

  const update = (done: number, frameTotal: number, text: string): void => {
    if (finished) return;
    const ratio = Math.max(0, Math.min(1, done / Math.max(1, frameTotal)));
    fill.style.width = `${(ratio * 100).toFixed(1)}%`;
    percent.textContent = `${Math.round(ratio * 100)}%`;
    stage.textContent = text;
    const elapsed = (performance.now() - started) / 1000;
    const remaining =
      done > 0 && done < frameTotal ? (elapsed / done) * (frameTotal - done) : 0;
    detail.textContent =
      `frame ${done} / ${frameTotal} · elapsed ${clock(elapsed)}` +
      (remaining > 1 ? ` · remaining ${clock(remaining)}` : "");
  };

  const finish = (): void => {
    finished = true;
    window.clearInterval(timer);
    cancel.remove();
  };

  const addButton = (label: string, className: string, action: () => void): HTMLButtonElement => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", action);
    return button;
  };

  cancel.addEventListener("click", () => {
    if (cancelled || finished) return;
    cancelled = true;
    cancel.disabled = true;
    cancel.textContent = "Cancelling…";
    stage.textContent = "Cancelling…";
  });

  const succeed = (result: ExportResult, savedName?: string): void => {
    finish();
    fill.style.width = "100%";
    percent.textContent = "100%";
    stage.textContent = savedName ? "Saved" : "Export complete";
    const size = `${((result.bytes ?? result.blob.size) / 1024 / 1024).toFixed(1)} MB`;
    detail.textContent = savedName
      ? `${savedName} · ${size}`
      : `${result.filename} · ${size} · ${result.frames} frames`;
    if (savedName) {
      foot.append(addButton("Close", "accent pill", () => backdrop.remove()));
      return;
    }
    const url = URL.createObjectURL(result.blob);
    const download = document.createElement("a");
    download.href = url;
    download.download = result.filename;
    download.className = "accent pill";
    download.textContent = "Download";
    download.style.textDecoration = "none";
    foot.append(
      download,
      addButton("Close", "menu-ghost", () => {
        URL.revokeObjectURL(url);
        backdrop.remove();
      }),
    );
  };

  const fail = (message: string): void => {
    finish();
    stage.textContent = "Export failed";
    detail.textContent = message;
    foot.append(addButton("Close", "accent pill", () => backdrop.remove()));
  };

  const markCancelled = (): void => {
    finish();
    stage.textContent = "Export cancelled";
    detail.textContent = "No file was written.";
    foot.append(addButton("Close", "accent pill", () => backdrop.remove()));
  };

  // Keep the elapsed clock moving while the encoder is between reports.
  timer = window.setInterval(() => {
    if (finished) return;
    const elapsed = (performance.now() - started) / 1000;
    stage.textContent = cancelled ? "Cancelling…" : stage.textContent;
    detail.textContent = detail.textContent.includes("· elapsed")
      ? detail.textContent.replace(/elapsed [0-9]+:[0-9]+/, `elapsed ${clock(elapsed)}`)
      : `elapsed ${clock(elapsed)}`;
  }, 1000);

  return {
    isCancelled: () => cancelled,
    update,
    succeed,
    fail,
    markCancelled,
  };
}

async function runExport(
  settings: ExportSettings = defaultExportSettings(),
  saveHandle: SaveFileHandle | null = null,
): Promise<void> {
  if (exporting) return;
  exporting = true;
  // The impact normaliser is scanned after a new track loads; finish it before
  // frames start so every exported automation frame uses the final value.
  if (impactScanPromise) {
    try {
      await impactScanPromise;
    } catch {
      /* a failed scan leaves the previous normaliser in place */
    }
  }
  const button = $<HTMLButtonElement>("#btn-export");
  button.disabled = true;
  setPlaying(false);
  renderer.setGizmoSuppressed(true);

  const start = Math.max(0, Math.min(settings.start, project.duration));
  const end = Math.max(start + 0.1, Math.min(settings.end, project.duration));
  const duration = Math.max(0.1, end - start);
  const fps = Math.max(1, Math.round(settings.fps));
  const totalFrames = Math.max(1, Math.round(duration * fps));
  const progress = openExportProgress({ ...settings, start, end }, totalFrames);
  // A full-length 1080p export is impossible to hold in ffmpeg.wasm memory.
  // Long runs therefore use WebCodecs, streaming chunks straight to the chosen
  // file when the user picked one.
  const useReference =
    settings.engine === "wasm" &&
    settings.codec === "h264" &&
    ReferenceWasmExporter.supported();
  const forcedWebCodecs =
    settings.engine === "wasm" &&
    !useReference &&
    totalFrames > 2400 &&
    WebCodecsExporter.available();
  const engine = forcedWebCodecs ? "webcodecs" : settings.engine;
  if (forcedWebCodecs) {
    progress.update(0, totalFrames, "using WebCodecs for this long export");
  }
  let streamFile: Awaited<ReturnType<SaveFileHandle["createWritable"]>> | null = null;
  let streamTarget:
    | WritableStream<{ type: "write"; data: Uint8Array<ArrayBuffer>; position: number }>
    | undefined;
  if (saveHandle && (engine === "webcodecs" || useReference)) {
    try {
      streamFile = await saveHandle.createWritable();
      const file = streamFile;
      streamTarget = new WritableStream({
        async write(chunk) {
          await file.write({ type: "write", position: chunk.position, data: chunk.data });
        },
        async close() {
          await file.close();
        },
        async abort(reason) {
          await file.abort?.(reason);
        },
      });
      progress.update(0, totalFrames, "streaming to the chosen file");
    } catch (error) {
      setStatus(
        `Could not open ${saveHandle.name} for streaming (${error instanceof Error ? error.message : String(error)}); exporting in memory.`,
      );
      streamFile = null;
      streamTarget = undefined;
    }
  }

  try {
    // The reference's exporter resets the analysers when it starts, so the first
    // exported frames do not inherit the preview's smoothing history.
    await spectrum.whenIdle();
    spectrum.reset();
    impactEngine.reset();
    renderer.resetAnalysers();
    const options = {
      width: Math.max(16, Math.round(settings.width)),
      height: Math.max(16, Math.round(settings.height)),
      fps,
      duration,
      startTime: start,
      codec: settings.codec,
      bitrate: Math.max(0, settings.bitrate),
      crf: Math.min(51, Math.max(0, settings.crf)),
      preset: settings.preset,
      profile: settings.profile,
      audioBitrate: Math.max(32, settings.audioBitrate),
      audio: audioFile
        ? { name: audioFile.name, bytes: audioFile.bytes }
        : undefined,
      audioBuffer: processedAudioBuffer ?? audioBuffer ?? undefined,
      streamTarget,
      shouldCancel: () =>
        progress.isCancelled() || camxoraExportHooks?.cancelled() === true,
      beforeFrame(frameTime: number) {
        // Advance the exported frame's analysis deterministically, then apply
        // keyframe/audio-impact automations for that instant.
        return (async () => {
          await spectrum.tickForExport(frameTime, 1 / fps);
          renderer.setFrameTime(frameTime);
          applyAutomations(frameTime);
        })();
      },
      onProgress(done: number, total: number, stage: string) {
        button.textContent = `${Math.round((done / total) * 100)}%`;
        setStatus(`${stage} ${done}/${total}`);
        progress.update(done, total, stage);
        // CAMXORA-PATCH: stream progress to the desktop shell.
        camxoraExportHooks?.progress(done, total, stage);
      },
    };

    let result;
    if (useReference) {
      result = await new ReferenceWasmExporter().export(renderer, project, options);
    } else if (engine === "webcodecs" && WebCodecsExporter.available()) {
      try {
        result = await new WebCodecsExporter().export(renderer, project, options);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") throw error;
        if (forcedWebCodecs) throw error;
        setStatus(
          `WebCodecs failed (${error instanceof Error ? error.message : String(error)}); falling back to WebAssembly.`,
        );
        result = await exporter.export(renderer, project, options);
      }
    } else {
      result = await exporter.export(renderer, project, options);
    }
    let savedName: string | undefined;
    if (result.streamed) {
      savedName = saveHandle?.name ?? result.filename;
      streamFile = null;
    } else if (saveHandle) {
      try {
        const writable = await saveHandle.createWritable();
        await writable.write(result.blob);
        await writable.close();
        savedName = saveHandle.name;
      } catch (error) {
        setStatus(
          `Could not write ${saveHandle.name} (${error instanceof Error ? error.message : String(error)}); downloading instead.`,
        );
      }
    }
    if (!savedName) {
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      link.click();
      // Chrome can block a programmatic download that starts after a long async
      // export (the click no longer has user activation). Keep a visible,
      // user-initiated fallback until the toast is dismissed or expires.
      const toast = document.createElement("div");
      toast.className = "export-ready";
      toast.style.cssText =
        "position:fixed;right:20px;bottom:48px;z-index:1200;display:flex;align-items:center;gap:12px;padding:10px 12px;background:#17171f;border:1px solid rgba(255,255,255,.16);border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.45);font:12px system-ui,sans-serif;color:#fff;";
      const label = document.createElement("span");
      label.textContent = `${result.filename} ready (${(result.blob.size / 1024 / 1024).toFixed(1)} MB)`;
      const again = document.createElement("a");
      again.href = url;
      again.download = result.filename;
      again.className = "accent pill";
      again.textContent = "Download";
      again.style.cssText =
        "padding:6px 10px;border-radius:6px;background:#5b5bd6;color:#fff;text-decoration:none;";
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.textContent = "\u00d7";
      dismiss.title = "Dismiss";
      dismiss.style.cssText = "background:none;border:0;color:#bbb;font-size:16px;cursor:pointer;";
      const cleanup = (): void => {
        if (toast.isConnected) toast.remove();
        URL.revokeObjectURL(url);
      };
      dismiss.addEventListener("click", cleanup);
      toast.append(label, again, dismiss);
      document.body.append(toast);
      window.setTimeout(cleanup, 600000);
    }
    progress.succeed(result, savedName);
    const sizeMb = ((result.bytes ?? result.blob.size) / 1024 / 1024).toFixed(1);
    setStatus(
      savedName
        ? `saved ${savedName} — ${result.frames} frames, ${sizeMb} MB${result.hadAudio ? ", with audio" : ""}`
        : `exported ${result.filename} — ${result.frames} frames, ${sizeMb} MB${result.hadAudio ? ", with audio" : ""}`,
    );
  } catch (error) {
    if (streamFile) {
      try {
        await streamFile.abort?.(error);
      } catch {
        /* already closed */
      }
      streamFile = null;
    }
    const aborted =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && /cancel/i.test(error.message));
    if (aborted) {
      progress.markCancelled();
      setStatus("Export cancelled.");
      exporter.reset();
    } else {
      const message = error instanceof Error ? error.message : String(error);
      progress.fail(message);
      setStatus(`export failed: ${message}`);
      exporter.reset();
    }
  } finally {
    button.disabled = false;
    button.textContent = "Export";
    exporting = false;
    renderer.setGizmoSuppressed(false);
  }
}

/** Reference export dialog: resolution, fps, codec, bitrate and a time range. */
function openExportDialog(): void {
  document.querySelector(".modal-backdrop")?.remove();
  const defaults = defaultExportSettings();
  if (project.width && project.height) {
    defaults.width = project.width;
    defaults.height = project.height;
    defaults.bitrate = defaultExportBitrate(project.height);
  }

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  const modal = document.createElement("div");
  modal.className = "modal export-modal";
  modal.setAttribute("role", "dialog");

  const head = document.createElement("header");
  head.className = "modal-head modal-head-row";
  head.append(icon("movie", 16), document.createTextNode("Export"));
  const close = document.createElement("button");
  close.type = "button";
  close.className = "icon";
  close.title = "Close";
  close.append(icon("close", 14));
  close.addEventListener("click", () => backdrop.remove());
  head.append(close);

  const body = document.createElement("div");
  body.className = "modal-body";

  const row = (label: string, control: HTMLElement, hint?: string): HTMLElement => {
    const wrap = document.createElement("div");
    wrap.className = "modal-row";
    const name = document.createElement("label");
    name.textContent = label;
    wrap.append(name, control);
    if (hint) {
      const note = document.createElement("span");
      note.className = "modal-hint";
      note.textContent = hint;
      wrap.append(note);
    }
    return wrap;
  };

  const encoder = document.createElement("select");
  encoder.id = "export-engine";
  {
    const software = document.createElement("option");
    software.value = "wasm";
    software.textContent = "WebAssembly (x264)";
    encoder.append(software);
    const native = document.createElement("option");
    native.value = "webcodecs";
    native.textContent = WebCodecsExporter.available()
      ? "WebCodecs (Experimental)"
      : "WebCodecs (unsupported)";
    native.disabled = !WebCodecsExporter.available();
    encoder.append(native);
  }
  encoder.value = defaults.engine;

  const resolutions: [string, string][] = [
    ["640x360", "640x360 (360p)"],
    ["854x480", "854x480 (480p)"],
    ["1280x720", "1280x720 (720p)"],
    ["1920x1080", "1920x1080 (1080p)"],
    ["2560x1440", "2560x1440 (1440p)"],
    ["3840x2160", "3840x2160 (4K)"],
    ["360x640", "360x640 (360p, Portrait)"],
    ["480x854", "480x854 (480p, Portrait)"],
    ["720x1280", "720x1280 (720p, Portrait)"],
    ["1080x1920", "1080x1920 (1080p, Portrait)"],
    ["1440x2560", "1440x2560 (1440p, Portrait)"],
    ["2160x3840", "2160x3840 (4K, Portrait)"],
    ["360x360", "360x360 (360p, Square)"],
    ["480x480", "480x480 (480p, Square)"],
    ["720x720", "720x720 (720p, Square)"],
    ["1080x1080", "1080x1080 (1080p, Square)"],
    ["1440x1440", "1440x1440 (1440p, Square)"],
    ["2160x2160", "2160x2160 (4K, Square)"],
    ["1080x1350", "1080x1350 (Portrait)"],
    ["1080x2160", "1080x2160 (1:2)"],
  ];
  const resolution = document.createElement("select");
  resolution.id = "export-resolution";
  for (const [value, label] of resolutions) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    resolution.append(option);
  }
  const current = `${defaults.width}x${defaults.height}`;
  resolution.value = resolutions.some(([value]) => value === current) ? current : "1280x720";
  if (resolution.value !== current) {
    const custom = document.createElement("option");
    custom.value = current;
    custom.textContent = `${current} (current)`;
    resolution.append(custom);
    resolution.value = current;
  }

  const fps = document.createElement("select");
  fps.id = "export-fps";
  for (const value of [24, 30, 60]) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = `${value} fps`;
    fps.append(option);
  }
  fps.value = "60";

  const format = document.createElement("select");
  format.id = "export-format";
  for (const [value, label] of [
    ["h264", "H.264 · MP4"],
    ["vp9", "VP9 · WebM"],
    ["vp8", "VP8 · WebM"],
  ] as const) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    format.append(option);
  }
  format.value = defaults.codec;

  const bitrate = document.createElement("input");
  bitrate.id = "export-bitrate";
  bitrate.type = "number";
  bitrate.min = "0";
  bitrate.max = "200";
  bitrate.step = "1";
  bitrate.value = String(defaults.bitrate);

  const crf = document.createElement("input");
  crf.id = "export-crf";
  crf.type = "number";
  crf.min = "0";
  crf.max = "51";
  crf.step = "1";
  crf.value = String(defaults.crf);

  const preset = document.createElement("select");
  preset.id = "export-preset";
  for (const value of [
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
  ]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    preset.append(option);
  }
  preset.value = defaults.preset;

  const profile = document.createElement("select");
  profile.id = "export-profile";
  for (const value of ["baseline", "main", "high"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    profile.append(option);
  }
  profile.value = defaults.profile;

  const audioBitrate = document.createElement("input");
  audioBitrate.id = "export-audio-bitrate";
  audioBitrate.type = "number";
  audioBitrate.min = "64";
  audioBitrate.max = "320";
  audioBitrate.step = "16";
  audioBitrate.value = String(defaults.audioBitrate);

  const syncFormatControls = (): void => {
    const h264 = format.value === "h264";
    const software = encoder.value === "wasm";
    crf.disabled = !h264 || !software;
    preset.disabled = !h264 || !software;
    profile.disabled = !h264 || !software;
  };
  format.addEventListener("change", syncFormatControls);
  encoder.addEventListener("change", syncFormatControls);

  const start = document.createElement("input");
  start.id = "export-start";
  start.type = "number";
  start.min = "0";
  start.max = String(project.duration);
  start.step = "0.1";
  start.value = "0";
  const end = document.createElement("input");
  end.id = "export-end";
  end.type = "number";
  end.min = "0.1";
  end.max = String(project.duration);
  end.step = "0.1";
  end.value = String(defaults.end);

  const estimate = document.createElement("p");
  estimate.className = "modal-note";
  const updateEstimate = (): void => {
    const from = Math.max(0, Number(start.value) || 0);
    const to = Math.max(from, Number(end.value) || from);
    const videoMbps =
      Math.max(0, Number(bitrate.value) || 0) || (format.value === "h264" ? 6 : 4);
    const audioMbps = (Number(audioBitrate.value) || 192) / 1000;
    const frames = Math.max(1, Math.round((to - from) * Number(fps.value)));
    const longHint =
      frames > 2400 && encoder.value === "wasm" && WebCodecsExporter.available()
        ? " · long exports switch to WebCodecs to avoid running out of memory"
        : "";
    estimate.textContent = `Estimated size: ≈ ${((to - from) * (videoMbps + audioMbps) / 8).toFixed(1)} MB · ${frames} frames${longHint}`;
  };
  resolution.addEventListener("change", () => {
    const height = Number(resolution.value.split("x")[1]) || 720;
    bitrate.value = String(defaultExportBitrate(height));
    updateEstimate();
  });
  bitrate.addEventListener("input", updateEstimate);
  start.addEventListener("input", updateEstimate);
  end.addEventListener("input", updateEstimate);
  fps.addEventListener("change", updateEstimate);
  audioBitrate.addEventListener("input", updateEstimate);

  body.append(
    row("Encoder", encoder, "WebCodecs uses the browser's hardware encoder"),
    row("Resolution", resolution),
    row("Frame rate", fps),
    row("Format", format),
    row("Bitrate", bitrate, "Mbps · 0 lets the encoder choose"),
    row("CRF", crf, "x264 quality · used when bitrate is 0"),
    row("Preset", preset, "x264 speed"),
    row("Profile", profile, "H.264 profile"),
    row("Audio bitrate", audioBitrate, "kbps"),
    row("Start", start, "seconds"),
    row("End", end, "seconds"),
    estimate,
  );

  const foot = document.createElement("footer");
  foot.className = "modal-foot";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.id = "export-confirm";
  confirm.className = "accent pill";
  confirm.textContent = "Export";
  confirm.addEventListener("click", async () => {
    const [width, height] = resolution.value.split("x").map(Number);
    // The reference's range fields are bounded by the composition duration; the
    // inputs' max attribute is advisory, so clamp here as well.
    const duration = Math.max(0, project.duration);
    const from = Math.max(0, Math.min(Number(start.value) || 0, duration));
    const to = Math.min(duration, Number(end.value));
    if (!Number.isFinite(width) || !Number.isFinite(height) || !(to > from)) {
      setStatus("Export range is invalid.");
      return;
    }
    backdrop.remove();
    const settings: ExportSettings = {
      width,
      height,
      fps: Number(fps.value) || 60,
      start: Math.max(0, from),
      end: to,
      engine: encoder.value === "webcodecs" ? "webcodecs" : "wasm",
      codec: format.value as ExportCodec,
      bitrate: Math.max(0, Number(bitrate.value) || 0),
      crf: Number(crf.value) || 20,
      preset: preset.value,
      profile: profile.value,
      audioBitrate: Number(audioBitrate.value) || 192,
    };
    const ext = settings.codec === "h264" ? "mp4" : "webm";
    let saveHandle: SaveFileHandle | null = null;
    const picker = (window as unknown as { showSaveFilePicker?: SaveFilePicker })
      .showSaveFilePicker;
    // The picker must run inside the click task to keep user activation. Tests
    // run under webdriver, where the native dialog would block automation.
    if (picker && !navigator.webdriver) {
      try {
        saveHandle = await picker.call(window, {
          suggestedName: exportFilename(ext),
          types: [
            {
              description: ext === "mp4" ? "MP4 video" : "WebM video",
              accept: {
                [ext === "mp4" ? "video/mp4" : "video/webm"]: [`.${ext}`],
              },
            },
          ],
        });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setStatus(
          `Save location unavailable (${error instanceof Error ? error.message : String(error)}); using Downloads.`,
        );
      }
    }
    void runExport(settings, saveHandle);
  });
  foot.append(cancel, confirm);

  modal.append(head, body, foot);
  backdrop.append(modal);
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  document.body.append(backdrop);
  syncFormatControls();
  updateEstimate();
  resolution.focus();
}

document.addEventListener("keydown", (event) => {
  const target = event.target as HTMLElement | null;
  if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;

  const mod = event.ctrlKey || event.metaKey;
  if (!mod && event.shiftKey && event.key.toLowerCase() === "z") {
    event.preventDefault();
    zoom = 1;
    timeline.fit();
    return;
  }
  if (!mod && !event.shiftKey && event.key.toLowerCase() === "z") {
    event.preventDefault();
    if (timeline.zoomToSelection()) {
      zoom = timeline.getViewState().zoom;
      setStatus("Zoomed to selection.");
    } else {
      setStatus("Select a clip to zoom to it.");
    }
    return;
  }
  if (!mod && event.shiftKey && event.key.toLowerCase() === "m") {
    event.preventDefault();
    addMarker();
    return;
  }
  if (!mod && !event.shiftKey && event.key.toLowerCase() === "v") {
    event.preventDefault();
    setTimelineTool("select");
    return;
  }
  if (!mod && !event.shiftKey && event.key.toLowerCase() === "h") {
    event.preventDefault();
    setTimelineTool("hand");
    return;
  }
  if (!mod && !event.shiftKey && event.key.toLowerCase() === "c") {
    event.preventDefault();
    setTimelineTool("razor");
    return;
  }
  if (!mod && !event.shiftKey && event.key.toLowerCase() === "y") {
    event.preventDefault();
    setTimelineTool("slip");
    return;
  }
  if (mod && /^Digit[1-4]$/.test(event.code)) {
    event.preventDefault();
    applyResolution(RESOLUTION_SIDES[Number(event.code.slice(5)) - 1]);
    return;
  }
  if (mod && event.key === "Enter") {
    event.preventDefault();
    $<HTMLButtonElement>("#btn-fullscreen").click();
    return;
  }
  if (mod && event.key.toLowerCase() === "k") {
    event.preventDefault();
    splitAtPlayhead();
    return;
  }
  if (mod && event.key.toLowerCase() === "h") {
    event.preventDefault();
    $<HTMLButtonElement>("#btn-shy").click();
    return;
  }
  if (event.code === "F2") {
    event.preventDefault();
    void savePreviewImage();
    return;
  }
  if (event.code === "F3") {
    event.preventDefault();
    $("#hud").classList.toggle("hidden");
    return;
  }
  if (event.code === "Space") {
    event.preventDefault();
    if (event.shiftKey) {
      time = 0;
      setPlaying(true);
    } else {
      setPlaying(!playing);
    }
    return;
  }
  if (event.key === "Period") {
    event.preventDefault();
    time = Math.min(project.duration, time + 1 / project.fps);
    return;
  }
  if (event.key === "Comma") {
    event.preventDefault();
    time = Math.max(0, time - 1 / project.fps);
    return;
  }
  if (!mod && /^[1-7]$/.test(event.key)) {
    event.preventDefault();
    const tabs = ["composition", "analyzers", "effects", "automations", "media", "projects", "lyrics"];
    setLeftPanel(tabs[Number(event.key) - 1]);
    return;
  }
  if (!mod && event.key.toLowerCase() === "i") {
    event.preventDefault();
    const enabled = !renderer.gizmoState().enabled;
    renderer.setGizmoEnabled(enabled);
    setStatus(`Transform controls ${enabled ? "on" : "off"}.`);
    return;
  }
  if (!mod && ["w", "e", "r"].includes(event.key.toLowerCase())) {
    event.preventDefault();
    const key = event.key.toLowerCase();
    const mode = key === "w" ? "translate" : key === "e" ? "rotate" : "scale";
    renderer.setGizmoMode(mode);
    renderer.setGizmoEnabled(true);
    setStatus(`Transform mode: ${mode}.`);
    return;
  }
  if (!mod && event.key.toLowerCase() === "m") {
    event.preventDefault();
    if (project.volume > 0) {
      lastVolume = project.volume;
      project.volume = 0;
    } else {
      project.volume = lastVolume || 100;
    }
    applyAudioSettings();
    setStatus(project.volume > 0 ? "Audio unmuted." : "Audio muted.");
    return;
  }
  if (!mod && event.key.toLowerCase() === "l") {
    event.preventDefault();
    $<HTMLButtonElement>("#btn-add-layer").click();
    return;
  }
  if (!mod && event.key.toLowerCase() === "f") {
    event.preventDefault();
    $<HTMLButtonElement>("#btn-add-effect").click();
    return;
  }
  if (!mod && event.key.toLowerCase() === "g") {
    event.preventDefault();
    addAutomationsToNewFolder();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
    event.preventDefault();
    if (event.shiftKey) $<HTMLButtonElement>("#btn-redo").click();
    else $<HTMLButtonElement>("#btn-undo").click();
    return;
  }
  if (event.shiftKey && (event.key === "Delete" || event.key === "Backspace")) {
    event.preventDefault();
    rippleDeleteSelection();
    return;
  }
  if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    deleteSelection();
    return;
  }
  if (event.key === "ArrowLeft") {
    time = Math.max(0, time - (event.shiftKey ? 1 : 0.05));
  }
  if (event.key === "ArrowRight") {
    time = Math.min(project.duration, time + (event.shiftKey ? 1 : 0.05));
  }
});


history.onChange(refreshHistoryButtons);

/* ------------------------------------------------------------------ */
/* Menus                                                               */
/* ------------------------------------------------------------------ */

type MenuEntry =
  | {
      label: string;
      /** Reference labels that depend on state (e.g. Lock/Unlock layout). */
      dynamicLabel?: () => string;
      shortcut?: string;
      action: () => void;
      disabled?: boolean | (() => boolean);
      icon?: IconName;
    }
  | { separator: true };

const notInBuild = (what: string) => () => setStatus(`${what}: not available in this build.`);

function downloadBlob(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Current session log, or the one persisted when the previous page unloaded. */
function logTextFor(kind: "current" | "last"): string {
  let entries: LogEntry[] = logEntries;
  if (kind === "last") {
    try {
      const parsed = JSON.parse(localStorage.getItem("studio:lastLog") ?? "[]") as LogEntry[];
      entries = Array.isArray(parsed) ? parsed : [];
    } catch {
      entries = [];
    }
  }
  return entries
    .map((entry) => `${entry.at} [${entry.level.toUpperCase()}] ${entry.text}`)
    .join("\n");
}

function exportLog(kind: "current" | "last"): void {
  const text = logTextFor(kind);
  if (!text) {
    setStatus(`No ${kind} log entries.`);
    return;
  }
  downloadBlob(`studio-${kind}-log.txt`, new Blob([text], { type: "text/plain" }));
  setStatus(`Exported the ${kind} log.`);
}

/* ------------------------------------------------------------------ */
/* Local project storage                                               */
/* ------------------------------------------------------------------ */

const PROJECT_DB = "studio-projects";
const PROJECT_STORE = "records";

function openProjectDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(PROJECT_DB, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(PROJECT_STORE)) {
        request.result.createObjectStore(PROJECT_STORE);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB unavailable"));
  });
}

async function idbPut(key: string, value: unknown): Promise<void> {
  const db = await openProjectDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(PROJECT_STORE, "readwrite");
      tx.objectStore(PROJECT_STORE).put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error("IndexedDB write failed"));
      tx.onabort = () => reject(tx.error ?? new Error("IndexedDB write aborted"));
    });
  } finally {
    db.close();
  }
}

async function idbGet<T>(key: string): Promise<T | null> {
  const db = await openProjectDatabase();
  try {
    return await new Promise<T | null>((resolve, reject) => {
      const tx = db.transaction(PROJECT_STORE, "readonly");
      const request = tx.objectStore(PROJECT_STORE).get(key);
      request.onsuccess = () => resolve((request.result as T | undefined) ?? null);
      request.onerror = () => reject(request.error ?? new Error("IndexedDB read failed"));
    });
  } finally {
    db.close();
  }
}

async function idbDelete(key: string): Promise<void> {
  const db = await openProjectDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(PROJECT_STORE, "readwrite");
      tx.objectStore(PROJECT_STORE).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error ?? new Error("IndexedDB delete failed"));
    });
  } finally {
    db.close();
  }
}

function rememberSavedProject(entry: SavedProject): void {
  const next = loadSavedProjects().filter(
    (item) => item.id !== entry.id && item.name !== entry.name,
  );
  next.push(entry);
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(next));
}

/** Small JPEG preview of the current stage frame for the Projects panel. */
function captureProjectThumbnail(): string | null {
  try {
    if (!stageCanvas.width || !stageCanvas.height) return null;
    const width = 320;
    const height = Math.max(1, Math.round((stageCanvas.height / stageCanvas.width) * width));
    const thumb = document.createElement("canvas");
    thumb.width = width;
    thumb.height = height;
    const ctx = thumb.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(stageCanvas, 0, 0, width, height);
    return thumb.toDataURL("image/jpeg", 0.72);
  } catch {
    return null;
  }
}

/** Reference Project > Update project thumbnail (stored with the saved project). */
function updateProjectThumbnail(): void {
  const saved = loadSavedProjects();
  const entry = saved.find((item) => item.id === project.id);
  if (!entry) {
    setStatus("Save the project first to set its thumbnail.");
    return;
  }
  const thumbnail = captureProjectThumbnail();
  if (!thumbnail) {
    setStatus("Could not capture the preview.");
    return;
  }
  rememberSavedProject({ ...entry, thumbnail, savedAt: new Date().toISOString() });
  if (leftPanel === "projects") renderProjectsPanel();
  setStatus("Project thumbnail updated.");
}

/** Replace the live project with a saved snapshot. */
function applyProjectSnapshot(snapshot: ProjectSnapshot): void {
  // The restored project carries the reference's impact maximum; stop any scan
  // still running for the previous track from overwriting it.
  impactScanToken += 1;
  for (const node of project.nodes) renderer.disposeNode(node);
  renderer.resetLayers();
  const nodes = restoreProject(project, snapshot, renderer.makeContext());
  // Rebuild the live asset store so uploaded artwork renders after a reload.
  assets.clear();
  for (const asset of project.assets) {
    assets.register(asset);
    if (asset.kind === "image" && asset.url) void assets.load(asset);
  }
  normalizeTrackRows();
  for (const node of nodes) renderer.attach(node);

  selectedId = null;
  selectedLayerId = null;
  multiSelection.clear();
  time = 0;
  history.clear();
  $("#project-name").textContent = project.name;
  applyAudioSettings();
  renderer.retainAnalyzers(project.analyzers.map((analyzer) => analyzer.id));
  renderer.resize();
  syncNodeOrder();
  refreshTree();
  refreshInspector();
  refreshStack();
  setEditorWarnings([]);
  persistComposition();
}

async function saveProjectLocally(): Promise<void> {
  const snapshot = serializeProject(project);
  const thumbnail = captureProjectThumbnail();
  // CAMXORA-PATCH (scripts/sync-vizzy.mjs): when the hosted desktop build
  // injects window.camxoraVizzy, Save is owned by the native project store.
  // The IndexedDB path below remains the browser fallback.
  const vizzyHost = (
    window as unknown as {
      camxoraVizzy?: {
        saveProject(name: string, json: string): Promise<{ path?: string } | null>;
      };
    }
  ).camxoraVizzy;
  if (vizzyHost) {
    try {
      const saved = await vizzyHost.saveProject(project.name, JSON.stringify(snapshot));
      if (saved) {
        $("#save-state").textContent = `Saved ${new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}`;
        setStatus(
          `Saved "${project.name}" - ${project.nodes.length} items, ${project.layers.length} layers.`,
        );
        return;
      }
    } catch {
      // Fall through to the local store so a host failure still keeps work.
    }
  }
  try {
    await idbPut(`project:${project.id}`, snapshot);
    if (audioFile) await idbPut(`audio:${project.id}`, audioFile);
    else await idbDelete(`audio:${project.id}`);
    // Keep the small boot-time composition record in localStorage.
    localStorage.setItem(
      "studio:project",
      JSON.stringify({
        name: project.name,
        width: project.width,
        height: project.height,
        fps: project.fps,
        duration: project.duration,
        background: project.background,
        volume: project.volume,
        spectrumLayerColorMode: project.spectrumLayerColorMode,
        spectrumLayerColorShift: project.spectrumLayerColorShift,
        globals: [...project.globals],
        audioSettings: { ...project.audioSettings },
      }),
    );
    rememberSavedProject({
      id: project.id,
      name: project.name,
      savedAt: snapshot.savedAt,
      width: project.width,
      height: project.height,
      thumbnail: thumbnail ?? undefined,
    });
    $("#save-state").textContent = `Saved ${new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
    setStatus(
      `Saved "${project.name}" — ${project.nodes.length} items, ${project.layers.length} layers.`,
    );
  } catch (error) {
    setStatus(`Save failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/** Open a project from the Projects panel. */
async function openSavedProject(id: string): Promise<void> {
  try {
    const snapshot = await idbGet<ProjectSnapshot>(`project:${id}`);
    if (!snapshot) {
      setStatus("Saved project not found on this device.");
      return;
    }
    if (!window.confirm(`Open "${snapshot.project.name}"? Unsaved changes will be lost.`)) {
      return;
    }
    const audioRecord = await idbGet<{ name: string; bytes: Uint8Array }>(`audio:${id}`);
    if (audioRecord) {
      const bytes =
        audioRecord.bytes instanceof Uint8Array
          ? audioRecord.bytes
          : new Uint8Array(audioRecord.bytes);
      await loadAudioFromBytes(audioRecord.name, bytes, { computeImpact: false });
    }
    applyProjectSnapshot(snapshot);
    setStatus(`Opened "${project.name}" — ${project.nodes.length} items.`);
  } catch (error) {
    setStatus(`Open failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function newProject(force = false): void {
  if (!force && !window.confirm("Start a new project? Unsaved changes will be lost.")) return;
  for (const node of project.nodes) renderer.disposeNode(node);
  renderer.resetLayers();
  project.nodes = [];
  project.layers = ["2D Visualizers", "3D Visualizers", "Background Layer"].map((name) => ({
    id: newId("layer"),
    name,
    nodeIds: [],
    enabled: true,
    renderToBuffer: false,
    camera: {
      type: name === "3D Visualizers" ? ("Perspective" as const) : ("Orthographic" as const),
      fov: 45,
      near: 1,
      far: 100000,
    },
  }));
  project.effects = [];
  project.automations = [];
  project.assets = [];
  assets.clear();
  project.analyzers = [createAnalyzer("analyzer_default", "Default")];
  project.id = newId("project");
  project.name = "Untitled";
  project.creatorNote = "";
  project.width = 1920;
  project.height = 1080;
  project.fps = 30;
  project.bpm = 120;
  project.markers = [];
  project.duration = 12;
  project.background = "#000000";
  project.volume = 100;
  project.muted = false;
  project.spectrumLayerColorMode = "lighten";
  project.spectrumLayerColorShift = 0.5;
  project.audioImpactMax = 0;
  impactScanToken += 1;
  impactNormaliserScannedFor = "";
  project.globals = [0, 0, 0, 0, 0];
  project.audioSettings = {
    bassBoost: 0,
    frequency: 60,
    playbackRate: 1,
    attenuator: false,
    additionalGainDb: 0,
    compressor: false,
  };
  selectedId = null;
  selectedLayerId = null;
  multiSelection.clear();
  time = 0;
  // A new project starts a fresh history; the old entries reference disposed
  // nodes and would splice them back into the empty project.
  history.clear();
  $("#project-name").textContent = project.name;
  applyAudioSettings();
  renderer.retainAnalyzers(project.analyzers.map((analyzer) => analyzer.id));
  syncNodeOrder();
  refreshTree();
  refreshInspector();
  refreshStack();
  setEditorWarnings([]);
  persistComposition();
  setStatus("New project started.");
}

async function saveProjectAsNew(): Promise<void> {
  const next = window.prompt("Save as", `${project.name} copy`)?.trim();
  if (!next) return;
  project.name = next;
  project.id = newId("project");
  $("#project-name").textContent = project.name;
  await saveProjectLocally();
  setStatus(`Saved "${project.name}" as a new project.`);
}

function renameProject(): void {
  const next = window.prompt("Project name", project.name);
  if (!next) return;
  project.name = next.trim() || project.name;
  $("#project-name").textContent = project.name;
  setStatus(`Renamed project to "${project.name}".`);
}

async function savePreviewImage(): Promise<void> {
  const blob = await renderer.frameBlob();
  downloadBlob(`${project.name.replace(/\s+/g, "-").toLowerCase()}.png`, blob);
  setStatus("Preview saved as PNG.");
}

function exportProjectJson(): void {
  downloadBlob(
    `${project.name.replace(/\s+/g, "-").toLowerCase()}.json`,
    new Blob([JSON.stringify(serializeProject(project), null, 2)], {
      type: "application/json",
    }),
  );
  setStatus("Project exported as JSON.");
}

function infoDialog(title: string, iconName: IconName, rows: [string, string][]): void {
  const { backdrop, body, foot } = openModalShell(title, iconName);
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "modal-row";
    const name = document.createElement("label");
    name.textContent = label;
    const text = document.createElement("span");
    text.className = "modal-value";
    text.textContent = value;
    row.append(name, text);
    body.append(row);
  }
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "accent pill";
  dismiss.textContent = "Dismiss";
  dismiss.addEventListener("click", () => backdrop.remove());
  foot.append(dismiss);
}

function openCreatorNote(): void {
  const { backdrop, body, foot } = openModalShell("Creator note", "sticky_note_2");
  const area = document.createElement("textarea");
  area.className = "modal-textarea";
  area.rows = 6;
  area.placeholder = "Notes about this project, shown with the project information.";
  area.value = project.creatorNote;
  body.append(area);

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "menu-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => backdrop.remove());
  const save = document.createElement("button");
  save.type = "button";
  save.className = "accent pill";
  save.textContent = "Save";
  save.addEventListener("click", () => {
    project.creatorNote = area.value;
    persistComposition();
    setStatus("Creator note saved.");
    backdrop.remove();
  });
  foot.append(cancel, save);
  area.focus();
}

function showProjectInformation(): void {
  infoDialog("Project information", "info", [
    ["Name", project.name],
    ["Resolution", `${project.width}×${project.height}`],
    ["Frame rate", `${project.fps} fps`],
    ["Duration", `${project.duration.toFixed(2)}s`],
    ["Objects", String(project.nodes.length)],
    ["Layers", String(project.layers.length)],
    ["Automations", String(project.automations.length)],
    ["Effects", String(project.effects.length)],
    ["Analyzers", String(project.analyzers.length)],
    ...(project.creatorNote ? [["Note", project.creatorNote] as [string, string]] : []),
  ]);
}

function showSystemInformation(): void {
  const caps = spectrum.capabilities;
  infoDialog("System information", "info", [
    ["FFT tier", spectrum.tier],
    ["SIMD", String(caps.wasmSimd)],
    ["Threads", String(caps.wasmThreads)],
    ["Cores", String(caps.hardwareConcurrency)],
    ["Cross-origin isolated", String(caps.crossOriginIsolated)],
    ["User agent", navigator.userAgent],
  ]);
}

/** Community browsing/publishing are account-gated in the reference. */
function openCommunity(): void {
  openAccountDialog();
}

function openAccountDialog(): void {
  const { backdrop, body, foot } = openModalShell("Account", "person");
  const note = document.createElement("p");
  note.className = "modal-note";
  note.textContent =
    "Accounts, cloud saves, and community publishing are not part of this build. Projects and presets stay in this browser.";
  body.append(note);
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "accent pill";
  dismiss.textContent = "Dismiss";
  dismiss.addEventListener("click", () => backdrop.remove());
  foot.append(dismiss);
}

/** Items the importer approximated or skipped, surfaced by the warning chip. */
let editorWarnings: { what: string; reason: string }[] = [];

function setEditorWarnings(warnings: { what: string; reason: string }[]): void {
  editorWarnings = warnings;
  const button = $("#btn-warnings");
  button.classList.toggle("warn-on", warnings.length > 0);
  button.title = warnings.length
    ? `${warnings.length} editor warning${warnings.length === 1 ? "" : "s"}`
    : "Editor warnings";
}

const DISCORD_URL = "https://discord.com/servers/vizzy-community-692843867812266075";
const FAQ_URL = "https://vizzy.io/faq";

function openDiscord(): void {
  window.open(DISCORD_URL, "_blank", "noopener,noreferrer");
}

function openFaq(): void {
  window.open(FAQ_URL, "_blank", "noopener,noreferrer");
}

interface TourStep {
  title: string;
  content: string;
  panel?: string;
}

/** Reference intro tour (module 2561), text and panel order preserved. */
const TOUR_STEPS: TourStep[] = [
  {
    title: "The Editor",
    content:
      "Our editor will allow you to create something truly unique! Please take a moment to familiarize yourself with some of its main features. Press Start to begin the tutorial.",
  },
  {
    title: "Uploading Audio",
    content:
      "First of all, of course, you can upload your own music by clicking this button. It will be saved on our cloud servers as soon as you save your project.",
    panel: "composition",
  },
  {
    title: "Layers",
    content:
      "This is the Layers area. \nThink of layers as containers for your items. Layers further up on the list will be drawn on top. If you can't see an item, try simply moving the layer further up! ",
    panel: "composition",
  },
  {
    title: "Adding Items to Layers",
    content:
      "Items are the things that make your spectrums, videos, etc. \nYou can add items to a layer simply by clicking this add button on the layer!",
    panel: "composition",
  },
  {
    title: "Adding Effects to Layers",
    content:
      "Want some fancy effects like a camera shake, and RGB split, or blur? \nClick this grey plus icon to add one!",
    panel: "composition",
  },
  {
    title: "Adding New Layers",
    content:
      "You can create a new layer by clicking this button. \nLayers are containers for items, and items are the things that make your spectrums, videos, etc.",
    panel: "composition",
  },
  {
    title: "Render Settings",
    content:
      "This is the Render Settings area. \nHere you can set the resolution, enable debug options, or add global effects to your project.",
    panel: "composition",
  },
  {
    title: "Audio Processing",
    content:
      "This is the Audio Processing area. \nHere you can bass boost your audio, or change its speed (for stuff like Nightcore!).",
    panel: "composition",
  },
  {
    title: "Timeline",
    content:
      "These are your items. They are on this timeline. \nTimeline means that the farther to the right something is, the later it will occcur. \nYou can click on an item here to select it, move it on the timeline, or resize it by dragging its ends. \nKeyframes from automations can be shown here.",
    panel: "composition",
  },
  {
    title: "Canvas",
    content:
      "This is the canvas, the area where your video will display. \nCheck out the buttons under it: \nPreview quality, 3D Camera Mode, External Preview Window, and Fullscreen",
    panel: "composition",
  },
  {
    title: "Controllers",
    content:
      "This is the Controllers area. It contains every setting (controller) of an object. There are tons of settings, so it might feel a bit overwhelming at first.\n A good idea is to take a few minutes and familiarize yourself by changing settings and seeing what they do.",
    panel: "composition",
  },
  {
    title: "Analyzers",
    content:
      "We've just switched tabs! Check the icons on the left to see what tab we are in. \nHere are the analyzers. They turn audio into numbers that we use to react to the beat. Analyzers have tons of settings in them.",
    panel: "analyzers",
  },
  {
    title: "Effects",
    content:
      "These are the effects you've added. They have their own timeline. Keyframes from automations can be shown here, too.",
    panel: "effects",
  },
  {
    title: "Automations",
    content:
      "Those are the automations. Automations allow you to change your controllers automatically, over time, statically, or reactive to the audio. \nThey also have their own timeline. Try adding an automation later to see what it can do!",
    panel: "automations",
  },
  {
    title: "Media",
    content:
      "Here's the media tab. You can upload files, like logos or assets to use later.\n You can also click 'Stock' to search royalty-free stock images and videos. Perfect for backgrounds!",
    panel: "media",
  },
  {
    title: "Projects",
    content:
      "And this is the Projects tab. You can change the current project's name, see who forked the project before you, and load your other projects\n Don't forget to explore the Creations section, you can do it from here, too!",
    panel: "projects",
  },
  {
    title: "Saving and Exporting",
    content:
      "Once you're done with your project, you'll want to get the video to upload it somewhere. That's called Exporting.\nGo into 'File', and select Export.\nBut before you do that, save your project into your profile, so you can access it later: go into 'File' and select Save, or use the keyboard shortcut Ctrl+S.",
  },
  {
    title: "Still need help?",
    content:
      "If you need help with something, you are welcome to join our Discord server, or launch this tutorial again.\n Have fun!",
  },
];

function startIntroTour(): void {
  const { backdrop, body, foot } = openModalShell("Intro tutorial", "info");
  let index = 0;

  const content = document.createElement("div");
  content.className = "tour-content";
  const heading = document.createElement("h3");
  heading.className = "tour-title";
  const text = document.createElement("p");
  const progress = document.createElement("span");
  progress.className = "tour-progress";
  content.append(heading, text, progress);
  body.append(content);

  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "mini";
  skip.textContent = "Skip";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "mini";
  back.textContent = "Back";
  const next = document.createElement("button");
  next.type = "button";
  next.className = "primary";
  foot.append(skip, back, next);

  const render = (): void => {
    const step = TOUR_STEPS[index];
    heading.textContent = step.title;
    text.textContent = step.content;
    progress.textContent = `${index + 1} / ${TOUR_STEPS.length}`;
    if (step.panel) setLeftPanel(step.panel);
    back.disabled = index === 0;
    next.textContent =
      index === 0 ? "Start" : index === TOUR_STEPS.length - 1 ? "Finish" : "Next";
  };

  skip.addEventListener("click", () => backdrop.remove());
  back.addEventListener("click", () => {
    if (index === 0) return;
    index -= 1;
    render();
  });
  next.addEventListener("click", () => {
    if (index >= TOUR_STEPS.length - 1) {
      backdrop.remove();
      return;
    }
    index += 1;
    render();
  });

  render();
}

function showChangelog(): void {
  const { backdrop, body, foot } = openModalShell("Changelog", "bolt");

  const intro = document.createElement("p");
  intro.className = "modal-note";
  intro.textContent =
    "This build is a clean-room rebuild of the Vizzy editor. Changes are grouped by area.";
  body.append(intro);

  const sections: { title: string; items: string[] }[] = [
    {
      title: "Release 1.0",
      items: [
        "66 effects with 87 shader outputs, including layer-scoped and global targets.",
        "30 composition items, with byte-for-byte presets, particles, and Timeline paths.",
        "Reference analyzers, presets, creation import, and video export with audio.",
      ],
    },
    {
      title: "Editor shell",
      items: [
        "Material icon set across the rail, toolbars, inspector, and timeline.",
        "Menus and disabled states aligned with the reference editor.",
        "Render settings, audio processing, changelog, and warnings dialogs.",
      ],
    },
  ];
  for (const section of sections) {
    const title = document.createElement("h3");
    title.className = "modal-section-title";
    title.textContent = section.title;
    const list = document.createElement("ul");
    list.className = "modal-list";
    for (const item of section.items) {
      const entry = document.createElement("li");
      entry.textContent = item;
      list.append(entry);
    }
    body.append(title, list);
  }

  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "accent pill";
  dismiss.textContent = "Dismiss";
  dismiss.addEventListener("click", () => backdrop.remove());
  foot.append(dismiss);
}

function openWarnings(): void {
  const { backdrop, body, foot } = openModalShell("Editor warnings", "warning");
  if (editorWarnings.length === 0) {
    const empty = document.createElement("p");
    empty.className = "modal-note";
    empty.textContent = "No editor warnings.";
    body.append(empty);
  } else {
    const list = document.createElement("ul");
    list.className = "modal-list";
    for (const warning of editorWarnings) {
      const item = document.createElement("li");
      const what = document.createElement("strong");
      what.textContent = `${warning.what}: `;
      item.append(what, document.createTextNode(warning.reason));
      list.append(item);
    }
    body.append(list);
  }
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "accent pill";
  dismiss.textContent = "Dismiss";
  dismiss.addEventListener("click", () => backdrop.remove());
  foot.append(dismiss);
}

/** Menu surfaces, in the order the reference presents them. */
const MENU_ITEMS: Record<string, MenuEntry[]> = {
  File: [
    { label: "Export", shortcut: "Ctrl+E", action: openExportDialog },
    { label: "New Project", shortcut: "Ctrl+B", action: newProject },
    { separator: true },
    { label: "Save", shortcut: "Ctrl+S", action: saveProjectLocally },
    { label: "Save As New", shortcut: "Ctrl+Shift+S", action: saveProjectAsNew },
    { separator: true },
    {
      label: "Close Editor",
      action: () => setStatus("Close Editor: close the browser tab to leave the editor."),
    },
  ],
  Edit: [
    {
      label: "Cut",
      shortcut: "Ctrl+X",
      action: cutSelection,
      disabled: () => !selectedId,
    },
    {
      label: "Copy",
      shortcut: "Ctrl+C",
      action: copySelection,
      disabled: () => !selectedId,
    },
    {
      label: "Paste",
      shortcut: "Ctrl+V",
      action: pasteClipboard,
      disabled: () => !clipboardId,
    },
  ],
  Project: [
    { label: "Explore creations", action: openCommunity },
    { separator: true },
    { label: "Rename project", action: renameProject },
    { label: "Publish to community", action: openCommunity },
    { label: "Update project thumbnail", action: updateProjectThumbnail },
    { label: "Set creator note", action: openCreatorNote },
    { separator: true },
    { label: "Set custom resolution", action: openCompositionSettings },
    { label: "Set background", action: openCompositionSettings },
    { separator: true },
    { label: "Organize track positions", action: organizeTrackPositions },
    { label: "Save preview as image", action: () => void savePreviewImage() },
  ],
  View: [
    { label: "Command Palette...", shortcut: "Ctrl+Shift+P", action: openCommandPalette },
    { label: "Change editor layout", action: cycleEditorLayout },
    { label: "Window dragging", shortcut: "Ctrl+D", action: toggleLayoutLock },
    {
      label: "Lock layout",
      dynamicLabel: () => (layout.locked ? "Unlock layout" : "Lock layout"),
      action: toggleLayoutLock,
    },
    // Ours alone: opens the shader/custom-path code editor layout.
    { label: "Code editor layout", action: toggleCodeEditorLayout },
    { separator: true },
    { label: "Theme", action: toggleTheme },
  ],
  Help: [
    { label: "Show project information", action: showProjectInformation },
    { label: "Show system information", action: showSystemInformation },
    { separator: true },
    { label: "Join our Discord", action: openDiscord },
    { label: "Frequently asked questions", action: openFaq },
    { label: "Launch intro tutorial", action: startIntroTour },
    { separator: true },
    { label: "Export project as JSON", action: exportProjectJson },
    { label: "Export current log", action: () => exportLog("current") },
    { label: "Export last log", action: () => exportLog("last") },
    { separator: true },
    { label: "Show changelog", action: showChangelog },
  ],
};

/**
 * Ours alone. They stay reachable from the command palette so the reference
 * menus keep their exact shape.
 */
const EXTRA_COMMANDS: MenuEntry[] = [
  { label: "Import project JSON", action: importProjectFile },
  { label: "Templates", action: () => setLeftPanel("templates") },
  { label: "Lock layout", action: toggleLayoutLock },
  { label: "Toggle 3D mode", shortcut: "Ctrl+F", action: toggle3D },
  { label: "Hide keyframes", action: toggleKeyframes },
];

function mountMenus(): void {
  const bar = $("#menus");
  let current: { name: string; panel: HTMLDivElement } | null = null;

  const close = (): void => {
    current?.panel.remove();
    current = null;
  };

  const open = (button: HTMLButtonElement, name: string): void => {
    close();
    const panel = document.createElement("div");
    panel.className = "dropdown";
    panel.setAttribute("role", "menu");
    panel.dataset.for = name;

    for (const entry of MENU_ITEMS[name] ?? []) {
      if ("separator" in entry) {
        const line = document.createElement("div");
        line.className = "dd-sep";
        panel.append(line);
        continue;
      }
      const item = document.createElement("button");
      item.className = "dropdown-item";
      item.type = "button";
      item.setAttribute("role", "menuitem");
      const labelSpan = document.createElement("span");
      labelSpan.className = "dd-label";
      labelSpan.textContent = entry.dynamicLabel ? entry.dynamicLabel() : entry.label;
      item.append(labelSpan);
      const disabled = typeof entry.disabled === "function" ? entry.disabled() : entry.disabled;
      if (disabled) {
        item.disabled = true;
        item.setAttribute("aria-disabled", "true");
      }
      if (entry.shortcut) {
        const key = document.createElement("span");
        key.className = "dd-key";
        key.textContent = entry.shortcut;
        item.append(key);
      }
      item.addEventListener("click", () => {
        close();
        entry.action();
      });
      panel.append(item);
    }

    document.body.append(panel);
    const rect = button.getBoundingClientRect();
    panel.style.left = `${Math.round(rect.left)}px`;
    panel.style.top = `${Math.round(rect.bottom + 4)}px`;
    button.setAttribute("aria-expanded", "true");
    current = { name, panel };

    // Reference menus take keyboard focus: arrows cycle, Escape returns.
    const items = [...panel.querySelectorAll<HTMLButtonElement>(".dropdown-item:not(:disabled)")];
    items[0]?.focus();
    panel.addEventListener("keydown", (event) => {
      const index = items.indexOf(document.activeElement as HTMLButtonElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        items[(index + 1) % items.length]?.focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        items[(index - 1 + items.length) % items.length]?.focus();
      } else if (event.key === "Escape") {
        event.preventDefault();
        close();
        button.focus();
      }
    });
  };

  bar.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-menu]");
    if (!button) return;
    const name = button.dataset.menu ?? "";
    const expanded = button.getAttribute("aria-expanded") === "true";
    bar.querySelectorAll("[data-menu]").forEach((node) => node.setAttribute("aria-expanded", "false"));
    if (expanded && current?.name === name) {
      close();
      return;
    }
    open(button, name);
  });

  document.addEventListener("pointerdown", (event) => {
    if (!current) return;
    const target = event.target as HTMLElement;
    if (current.panel.contains(target) || target.closest("[data-menu]")) return;
    close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  window.addEventListener("resize", close);
}

/** Floating menu shared by right-click surfaces. */
function showMenuAt(x: number, y: number, entries: MenuEntry[]): void {
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

  for (const entry of entries) {
    if ("separator" in entry) {
      const line = document.createElement("div");
      line.className = "dd-sep";
      panel.append(line);
      continue;
    }
    const item = document.createElement("button");
    item.type = "button";
    item.className = "dropdown-item";
    item.setAttribute("role", "menuitem");
    if (entry.icon) {
      const lead = document.createElement("span");
      lead.className = "dd-icon";
      lead.append(icon(entry.icon, 14));
      item.append(lead);
    }
    const labelSpan = document.createElement("span");
    labelSpan.className = "dd-label";
    labelSpan.textContent = entry.dynamicLabel ? entry.dynamicLabel() : entry.label;
    item.append(labelSpan);
    if (entry.shortcut) {
      const key = document.createElement("span");
      key.className = "dd-key";
      key.textContent = entry.shortcut;
      item.append(key);
    }
    item.addEventListener("click", () => {
      close();
      entry.action();
    });
    panel.append(item);
  }

  document.body.append(panel);
  panel.style.left = `${Math.round(Math.min(x, window.innerWidth - 270))}px`;
  panel.style.top = `${Math.round(Math.min(y, window.innerHeight - 380))}px`;

  document.addEventListener("pointerdown", onDown, true);
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape") close();
    },
    { once: true },
  );
}

/** Clipboard for Copy/Paste, mirroring the reference's enabled menu states. */
let clipboardId: string | null = null;
/** The copied object itself: pasting still works after Cut removed it. */
let clipboardNode: AnyNode | null = null;
/** Layer the copied object came from, so paste after Cut restores its place. */
let clipboardLayerId: string | null = null;

function copySelection(): void {
  const node = selectedId ? findNode(selectedId) : null;
  if (!node) {
    setStatus("Select an object to copy.");
    return;
  }
  clipboardId = node.id;
  clipboardNode = node;
  clipboardLayerId = project.layers.find((layer) => layer.nodeIds.includes(node.id))?.id ?? null;
  setStatus(`Copied ${node.name}.`);
}

function cutSelection(): void {
  const node = selectedId ? findNode(selectedId) : null;
  if (!node) {
    setStatus("Select an object to cut.");
    return;
  }
  clipboardId = node.id;
  clipboardNode = node;
  clipboardLayerId = project.layers.find((layer) => layer.nodeIds.includes(node.id))?.id ?? null;
  deleteSelected();
  setStatus(`Cut ${node.name}.`);
}

function pasteClipboard(): void {
  const source = clipboardNode ?? (clipboardId ? findNode(clipboardId) : null);
  if (!source) {
    setStatus("Clipboard is empty.");
    return;
  }
  duplicateNode(source, clipboardLayerId);
}

/**
 * Razor: split a clip at `at` into two clips with identical content. The copy
 * is created through `duplicateNode` (no history) and the split becomes one
 * undo step that restores the original duration and removes the copy.
 */
function splitNodeAt(nodeId: string, at: number): void {
  const node = findNode(nodeId);
  if (!node) return;
  const start = node.start;
  const end = start + node.duration;
  if (at <= start + 0.05 || at >= end - 0.05) {
    setStatus("Move the playhead inside the clip to split it.");
    return;
  }
  const layer = project.layers.find((entry) => entry.nodeIds.includes(node.id));
  const beforeDuration = node.duration;
  const copy = duplicateNode(node, layer?.id ?? null, {
    name: node.name,
    record: false,
    select: false,
  });
  const copyOwner = copy.analyzerId;
  const applySplit = (): void => {
    node.duration = at - start;
    copy.start = at;
    copy.duration = end - at;
  };
  applySplit();
  history.push({
    label: "split clip",
    undo: () => {
      node.duration = beforeDuration;
      project.nodes = project.nodes.filter((entry) => entry !== copy);
      if (layer) layer.nodeIds = layer.nodeIds.filter((id) => id !== copy.id);
      detachUser(project.analyzers, copy.id);
      copy.analyzerId = null;
      renderer.detach(copy);
      select(node.id);
      sortNodesByLayers();
      syncNodeOrder();
      refreshTree();
      refreshInspector();
    },
    redo: () => {
      if (!project.nodes.includes(copy)) {
        project.nodes.push(copy);
        if (layer) {
          const index = layer.nodeIds.indexOf(node.id);
          layer.nodeIds.splice(index >= 0 ? index + 1 : layer.nodeIds.length, 0, copy.id);
        }
        bindAnalyzer(copy, copyOwner);
        renderer.attach(copy);
      }
      applySplit();
      sortNodesByLayers();
      syncNodeOrder();
      select(copy.id);
      refreshTree();
      refreshInspector();
    },
  });
  select(copy.id);
  refreshTree();
  refreshInspector();
  setStatus(`Split ${node.name} at ${formatTime(at)}.`);
}

/** Split every selected clip that contains the playhead, as one undo step. */
function splitAtPlayhead(): void {
  const ids =
    multiSelection.size > 0
      ? [...multiSelection]
      : selectedId
        ? [selectedId]
        : [];
  const entries = ids
    .map((id) => {
      const node = findNode(id);
      if (!node) return null;
      const start = node.start;
      const end = start + node.duration;
      if (time <= start + 0.05 || time >= end - 0.05) return null;
      const layer = project.layers.find((entry) => entry.nodeIds.includes(node.id));
      const beforeDuration = node.duration;
      const copy = duplicateNode(node, layer?.id ?? null, {
        name: node.name,
        record: false,
        select: false,
      });
      return {
        node,
        layer,
        start,
        end,
        beforeDuration,
        copy,
        copyOwner: copy.analyzerId,
        layerIndex: layer ? layer.nodeIds.indexOf(node.id) : -1,
      };
    })
    .filter((entry): entry is NonNullable<typeof entry> => Boolean(entry));
  if (entries.length === 0) {
    setStatus("No selected clip under the playhead to split.");
    return;
  }
  const selectClips = (idsToSelect: string[]): void => {
    multiSelection = new Set(idsToSelect);
    selectedId = idsToSelect[0] ?? null;
    selectedLayerId = null;
    selectedAnalyzerId = null;
    selectedAutomations = new Set();
    renderer.setGizmoTarget(selectedId ? (findNode(selectedId) ?? null) : null);
    timeline.setSelection(idsToSelect);
    refreshTree();
    refreshInspector();
  };
  const applySplit = (): void => {
    for (const entry of entries) {
      entry.node.duration = time - entry.start;
      entry.copy.start = time;
      entry.copy.duration = entry.end - time;
    }
  };
  applySplit();
  sortNodesByLayers();
  syncNodeOrder();
  selectClips(entries.map((entry) => entry.copy.id));
  history.push({
    label: "split clips",
    undo: () => {
      for (const entry of entries) {
        entry.node.duration = entry.beforeDuration;
        project.nodes = project.nodes.filter((node) => node !== entry.copy);
        if (entry.layer) {
          entry.layer.nodeIds = entry.layer.nodeIds.filter((id) => id !== entry.copy.id);
        }
        detachUser(project.analyzers, entry.copy.id);
        entry.copy.analyzerId = null;
        renderer.detach(entry.copy);
      }
      sortNodesByLayers();
      syncNodeOrder();
      selectClips(entries.map((entry) => entry.node.id));
    },
    redo: () => {
      for (const entry of entries) {
        if (!project.nodes.includes(entry.copy)) {
          project.nodes.push(entry.copy);
          if (entry.layer) {
            const index = entry.layer.nodeIds.indexOf(entry.node.id);
            entry.layer.nodeIds.splice(
              index >= 0 ? index + 1 : entry.layer.nodeIds.length,
              0,
              entry.copy.id,
            );
          }
          bindAnalyzer(entry.copy, entry.copyOwner);
          renderer.attach(entry.copy);
        }
      }
      applySplit();
      sortNodesByLayers();
      syncNodeOrder();
      selectClips(entries.map((entry) => entry.copy.id));
    },
  });
  setStatus(
    `Split ${entries.length} clip${entries.length === 1 ? "" : "s"} at ${formatTime(time)}.`,
  );
}

function duplicateNode(
  node: AnyNode,
  preferredLayerId: string | null = null,
  options: { name?: string; record?: boolean; select?: boolean } = {},
): AnyNode {
  const copy = createNode(
    node.kind,
    options.name ?? `${node.name} copy`,
    renderer.makeContext(),
  );
  for (const [key, value] of node.objectMapping) copy.objectMapping.set(key, value);
  copy.start = node.start;
  copy.duration = node.duration;
  copy.visible = node.visible;
  (copy as AnyNode & { note?: string }).note = (node as AnyNode & { note?: string }).note;
  // The reference keeps the source row on paste; Organize fixes overlaps.
  copy.trackRow = node.trackRow;

  if (copy instanceof SpectrumNode && node instanceof SpectrumNode) {
    copy.type = node.type;
    copy.draw = node.draw;
    copy.fillStyle = node.fillStyle;
    copy.bands = node.bands;
    copy.mirror = node.mirror;
    copy.pathMode = node.pathMode;
    copy.layers.splice(0, copy.layers.length, ...node.layers.map((layer) => ({ ...layer })));
  }
  if (copy instanceof ParticlesNode && node instanceof ParticlesNode) {
    Object.assign(copy, {
      seed: node.seed,
      instances: node.instances,
      sizeRange: [...node.sizeRange],
      alphaRange: [...node.alphaRange],
      speedRange: [...node.speedRange],
      phaseRange: [...node.phaseRange],
      phaseAmplitude: [...node.phaseAmplitude],
      phaseSpeedRange: [...node.phaseSpeedRange],
      timeToLiveRange: [...node.timeToLiveRange],
      directionX: [...node.directionX],
      directionY: [...node.directionY],
      directionZ: [...node.directionZ],
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
      particleImage: node.particleImage,
      audioAnalyzer: node.audioAnalyzer,
      magFilter: node.magFilter,
      minFilter: node.minFilter,
      premultiplyAlpha: node.premultiplyAlpha,
    });
    copy.particleOffset.copy(node.particleOffset);
    copy.particleScale.copy(node.particleScale);
    copy.startPos.copy(node.startPos);
    copy.endPos.copy(node.endPos);
    copy.rebuild();
    void copy.loadTexture();
  }
  if (copy instanceof PrimitiveNode && node instanceof PrimitiveNode) {
    copy.color = node.color;
    copy.opacity = node.opacity;
    copy.boxWidth = node.boxWidth;
    copy.boxHeight = node.boxHeight;
    copy.intensity = node.intensity;
    copy.distance = node.distance;
    copy.decay = node.decay;
  }
  if (copy instanceof LogoNode && node instanceof LogoNode) {
    Object.assign(copy, {
      imageUrl: node.imageUrl,
      matPositionX: node.matPositionX,
      matPositionY: node.matPositionY,
      matScaleX: node.matScaleX,
      matScaleY: node.matScaleY,
      scaleMult: node.scaleMult,
      rotation: node.rotation,
      circleCutoff: node.circleCutoff,
      textureWrap: node.textureWrap,
      width: node.width,
      height: node.height,
    });
  }
  if (copy instanceof GroundNode && node instanceof GroundNode) {
    copy.multiplier = node.multiplier;
  }
  if (copy instanceof NoiseNode && node instanceof NoiseNode) {
    Object.assign(copy, {
      noiseType: node.noiseType,
      frequency: node.frequency,
      amplitude: node.amplitude,
      octaves: node.octaves,
      lacunarity: node.lacunarity,
      gain: node.gain,
      contrast: node.contrast,
      brightness: node.brightness,
      offsetX: node.offsetX,
      offsetY: node.offsetY,
      parallax: node.parallax,
      parallaxScale: node.parallaxScale,
      animate: node.animate,
      evolution: node.evolution,
      animateSpeed: node.animateSpeed,
      discretize: node.discretize,
      discretizeStep: node.discretizeStep,
      psrdPeriodX: node.psrdPeriodX,
      psrdPeriodY: node.psrdPeriodY,
      psrdRotation: node.psrdRotation,
      timeOffset: node.timeOffset,
      opacity: node.opacity,
      srcBlending: node.srcBlending,
      dstBlending: node.dstBlending,
      blendEquation: node.blendEquation,
    });
    copy.setNoiseType(node.noiseType);
  }
  if (copy instanceof VideoNode && node instanceof VideoNode) {
    copy.src = node.src;
    copy.loop = node.loop;
    copy.fitToScreen = node.fitToScreen;
    copy.playbackRate = node.playbackRate;
    copy.sourceIn = node.sourceIn;
    copy.authoredAspect = node.authoredAspect;
    copy.aspect = node.aspect;
  }
  if (copy instanceof ParticleTimeLineNode && node instanceof ParticleTimeLineNode) {
    Object.assign(copy, {
      customPath: node.customPath,
      distanceDone: node.distanceDone,
      maxTime: node.maxTime,
      nParticles: node.nParticles,
      pointSize: node.pointSize,
    });
  }
  if (copy instanceof ButterchurnNode && node instanceof ButterchurnNode) {
    Object.assign(copy, {
      src: node.src,
      color: node.color,
      opacity: node.opacity,
      presetName: node.presetName,
      blendTime: node.blendTime,
      audioMultiplier: node.audioMultiplier,
      updateSpeed: node.updateSpeed,
      useAudioAnalyzer: node.useAudioAnalyzer,
      audioAnalyzer: node.audioAnalyzer,
      outputAA: node.outputAA,
      fitToScreen: node.fitToScreen,
      width: node.width,
      height: node.height,
      matchToCanvas: node.matchToCanvas,
      srcBlending: node.srcBlending,
      dstBlending: node.dstBlending,
      blendEquation: node.blendEquation,
    });
    copy.renderPreset();
  }
  if (copy instanceof ShaderItemNode && node instanceof ShaderItemNode) {
    Object.assign(copy, {
      src: node.src,
      vertInput: node.vertInput,
      fragInput: node.fragInput,
      side: node.side,
      fitToScreen: node.fitToScreen,
      targetLayer: node.targetLayer,
      targetLayer2: node.targetLayer2,
      targetLayer3: node.targetLayer3,
      targetLayer4: node.targetLayer4,
      audioAnalyzer: node.audioAnalyzer,
      value: node.value,
      value2: node.value2,
      value3: node.value3,
      value4: node.value4,
      value5: node.value5,
      value6: node.value6,
      srcBlending: node.srcBlending,
      dstBlending: node.dstBlending,
      blendEquation: node.blendEquation,
    });
  }
  if (copy instanceof SphericalFieldNode && node instanceof SphericalFieldNode) {
    Object.assign(copy, {
      color: node.color,
      opacity: node.opacity,
      size: node.size,
      w: node.w,
      h: node.h,
      divX: node.divX,
      divY: node.divY,
      radius: node.radius,
      strength: node.strength,
      fractScale: node.fractScale,
      flowX: node.flowX,
      flowY: node.flowY,
      evolution: node.evolution,
      displace: node.displace,
      audioAnalyzer: node.audioAnalyzer,
      squishTo2D: node.squishTo2D,
      premultiply: node.premultiply,
      constantAudioFactor: node.constantAudioFactor,
      audioReaction: node.audioReaction,
    });
  }
  if (copy instanceof LineBedNode && node instanceof LineBedNode) {
    Object.assign(copy, {
      nrLines: node.nrLines,
      size: node.size,
      lineLength: node.lineLength,
      spacing: node.spacing,
      amplitude: node.amplitude,
      startColor: node.startColor,
      endColor: node.endColor,
      colorSplit: node.colorSplit,
      audioAnalyzer: node.audioAnalyzer,
      speed: node.speed,
    });
  }
  if (copy instanceof ModelNode && node instanceof ModelNode) {
    copy.color = node.color;
    copy.opacity = node.opacity;
    copy.modelSrc = node.modelSrc;
  }
  if (copy instanceof ParticleLinesNode && node instanceof ParticleLinesNode) {
    Object.assign(copy, {
      frequency: node.frequency,
      maxNrLines: node.maxNrLines,
      mirror: node.mirror,
      opacity: node.opacity,
      color: node.color,
      width: node.width,
      scale: node.scale,
      nrPoints: node.nrPoints,
      nrPrecisionPoints: node.nrPrecisionPoints,
      lengthRange: [...node.lengthRange],
      lengthMult: node.lengthMult,
      visibleLengthRange: [...node.visibleLengthRange],
      visibleLengthMult: node.visibleLengthMult,
      speedRange: [...node.speedRange],
      speedMult: node.speedMult,
      originX: [...node.originX],
      originY: [...node.originY],
      originZ: [...node.originZ],
      directionX: [...node.directionX],
      directionY: [...node.directionY],
      directionZ: [...node.directionZ],
      turbulenceAmt: node.turbulenceAmt,
    });
  }
  if (copy instanceof AudioWaveNode && node instanceof AudioWaveNode) {
    Object.assign(copy, {
      amplitude: node.amplitude,
      extent: node.extent,
      width: node.width,
      height: node.height,
      timeMultiplier: node.timeMultiplier,
      color: node.color,
      positionX: node.positionX,
      positionY: node.positionY,
      textureScale: node.textureScale,
      downsample: node.downsample,
      audioDuration: node.audioDuration,
      takeEvery: node.takeEvery,
      absolute: node.absolute,
      drawType: node.drawType,
      lineType: node.lineType,
      lineThickness: node.lineThickness,
      bufferKeepAmount: node.bufferKeepAmount,
      useAudioAnalyzer: node.useAudioAnalyzer,
      audioAnalyzer: node.audioAnalyzer,
      syncToDominant: node.syncToDominant,
      analyserFreqRange: [...node.analyserFreqRange],
      periodsVisible: node.periodsVisible,
    });
  }
  if (copy instanceof BasicSpectrumBarsNode && node instanceof BasicSpectrumBarsNode) {
    Object.assign(copy, {
      spacing: node.spacing,
      color: node.color,
      audioAnalyzer: node.audioAnalyzer,
    });
  }
  if (copy instanceof LyricsNode && node instanceof LyricsNode) {
    Object.assign(copy, {
      textValue: node.textValue,
      src: node.src,
      lyricsMapping: node.lyricsMapping.map((line) => ({ ...line })),
      color: node.color,
      alpha: node.alpha,
      antiAliasing: node.antiAliasing,
      textSize: node.textSize,
      timeFormat: node.timeFormat,
      timeDecimals: node.timeDecimals,
      drawTime: node.drawTime,
      textAlign: node.textAlign,
      textAlignV: node.textAlignV,
      textBaseline: node.textBaseline,
      textTiming: node.textTiming,
      offsetLine: node.offsetLine,
      timeMultiplier: node.timeMultiplier,
      font: node.font,
      positionX: node.positionX,
      positionY: node.positionY,
      scaleX: node.scaleX,
      scaleY: node.scaleY,
      scaleMultiplier: node.scaleMultiplier,
      showBoundingBox: node.showBoundingBox,
      textWidth: node.textWidth,
      textHeight: node.textHeight,
      fontStyle: node.fontStyle,
      fontWeight: node.fontWeight,
      rotation: node.rotation,
      textJustify: node.textJustify,
      dropShadow: { ...node.dropShadow },
      outlineDropShadow: { ...node.outlineDropShadow },
      alphaEnabled: node.alphaEnabled,
      scaleEnabled: node.scaleEnabled,
      posXEnabled: node.posXEnabled,
      posYEnabled: node.posYEnabled,
      blurEnabled: node.blurEnabled,
      liquidEnabled: node.liquidEnabled,
      distortionEnabled: node.distortionEnabled,
      shakeEnabled: node.shakeEnabled,
      useMotionBlur: node.useMotionBlur,
      motionBlurIterations: node.motionBlurIterations,
      motionBlurLength: node.motionBlurLength,
      motionExaggeration: node.motionExaggeration,
    });
    void copy.loadFont();
  }
  if (copy instanceof AnimatedTextNode && node instanceof AnimatedTextNode) {
    Object.assign(copy, {
      textValue: node.textValue,
      color: node.color,
      animationDuration: node.animationDuration,
      useCustomDuration: node.useCustomDuration,
      align: node.align,
      width: node.width,
      scaleMultiplier: node.scaleMultiplier,
      showBoundingBox: node.showBoundingBox,
      letterSpacing: node.letterSpacing,
      useReactiveAlpha: node.useReactiveAlpha,
    });
    copy.rebuildGeometry(true);
  }
  if (copy instanceof SkiaTextNode && node instanceof SkiaTextNode) {
    Object.assign(copy, {
      textValue: node.textValue,
      color: node.color,
      alpha: node.alpha,
      antiAliasing: node.antiAliasing,
      textSize: node.textSize,
      timeFormat: node.timeFormat,
      timeDecimals: node.timeDecimals,
      drawTime: node.drawTime,
      drawTimeCountdown: node.drawTimeCountdown,
      textAlign: node.textAlign,
      textAlignV: node.textAlignV,
      textBaseline: node.textBaseline,
      font: node.font,
      positionX: node.positionX,
      positionY: node.positionY,
      scaleX: node.scaleX,
      scaleY: node.scaleY,
      scaleMultiplier: node.scaleMultiplier,
      showBoundingBox: node.showBoundingBox,
      textWidth: node.textWidth,
      textHeight: node.textHeight,
      fontStyle: node.fontStyle,
      fontWeight: node.fontWeight,
      rotation: node.rotation,
      projectName: node.projectName,
      audioName: node.audioName,
      textJustify: node.textJustify,
      dropShadow: { ...node.dropShadow },
      outlineDropShadow: { ...node.outlineDropShadow },
    });
  }
  if (copy instanceof ProgressBarNode && node instanceof ProgressBarNode) {
    Object.assign(copy, {
      barType: node.barType,
      lineDirection: node.lineDirection,
      circleDirection: node.circleDirection,
      autoProgress: node.autoProgress,
      manualProgress: node.manualProgress,
      fgColor: node.fgColor,
      bgColor: node.bgColor,
      fgOpacity: node.fgOpacity,
      bgOpacity: node.bgOpacity,
      length: node.length,
      thickness: node.thickness,
      radius: node.radius,
      cornerRadius: node.cornerRadius,
      circleStartAngle: node.circleStartAngle,
      segments: node.segments,
      gap: node.gap,
      continuousSegments: node.continuousSegments,
      skipSegmentGapsDuringProgress: node.skipSegmentGapsDuringProgress,
      circleConsistentGapThickness: node.circleConsistentGapThickness,
    });
  }

  const sourceLayer =
    project.layers.find((layer) => layer.id === preferredLayerId) ??
    project.layers.find((layer) => layer.nodeIds.includes(node.id));
  const sourceIndex = sourceLayer
    ? Math.max(
        0,
        sourceLayer.nodeIds.includes(node.id)
          ? sourceLayer.nodeIds.indexOf(node.id)
          : sourceLayer.nodeIds.length - 1,
      )
    : -1;
  project.nodes.push(copy);
  if (sourceLayer) {
    sourceLayer.nodeIds.splice(sourceIndex + 1, 0, copy.id);
    sortNodesByLayers();
  }
  bindAnalyzer(copy, node.analyzerId);
  renderer.attach(copy);
  syncNodeOrder();
  const ownerId = copy.analyzerId;
  if (options.record !== false) {
    history.push({
      label: `create ${copy.name}`,
      undo: () => {
        project.nodes = project.nodes.filter((entry) => entry.id !== copy.id);
        if (sourceLayer) sourceLayer.nodeIds = sourceLayer.nodeIds.filter((id) => id !== copy.id);
        detachUser(project.analyzers, copy.id);
        copy.analyzerId = null;
        renderer.detach(copy);
        selectedId = null;
        refreshTree();
        refreshInspector();
      },
      redo: () => {
        project.nodes.push(copy);
        if (sourceLayer) sourceLayer.nodeIds.splice(sourceIndex + 1, 0, copy.id);
        bindAnalyzer(copy, ownerId);
        renderer.attach(copy);
        sortNodesByLayers();
        syncNodeOrder();
        select(copy.id);
        refreshTree();
      },
    });
  }
  if (options.select !== false) {
    select(copy.id);
    setStatus(`Created ${copy.name}.`);
  }
  return copy;
}

/** Reference Note controller on an object: stored with the node and undoable. */
function editNodeNote(node: AnyNode): void {
  const target = node as AnyNode & { note?: string };
  const before = target.note ?? "";
  const next = window.prompt("Note", before);
  if (next === null) return;
  const value = next.trim();
  const apply = (text: string): void => {
    target.note = text || undefined;
    refreshTree();
    refreshInspector();
  };
  apply(value);
  history.push({
    label: "edit note",
    undo: () => apply(before),
    redo: () => apply(value),
  });
  setStatus(value ? "Note updated." : "Note cleared.");
}

/** The 13-entry item menu from the reference, in the same order. */
function openItemMenuAt(x: number, y: number, node: AnyNode): void {
  select(node.id);
  showMenuAt(x, y, [
    {
      label: "Add Item",
      icon: "add",
      action: () => {
        const owner = project.layers.find((entry) => entry.nodeIds.includes(node.id));
        openAddItemDialog(owner?.id);
      },
    },
    {
      label: "Add Effect",
      icon: "auto_awesome",
      action: () => {
        // Effects attach to a composition layer (or Global), not to an item;
        // preselect the layer this item lives in.
        const owner = project.layers.find((entry) => entry.nodeIds.includes(node.id));
        openAddEffectDialog(owner ? [owner.id] : undefined);
      },
    },
    ...(clipboardId
      ? [{ label: "Paste", icon: "content_copy" as const, action: pasteClipboard }]
      : []),
    { label: "Copy", shortcut: "Ctrl+C", icon: "content_copy", action: () => duplicateNode(node) },
    {
      label: "Solo",
      icon: "brightness_1",
      action: () => {
        setNodeFlag(node, "solo", !node.solo);
      },
    },
    {
      label: "Shy",
      icon: "radio_button_unchecked",
      action: () => {
        setNodeFlag(node, "shy", !node.shy);
      },
    },
    {
      label: "Toggle",
      icon: "visibility_off",
      action: () => {
        setNodeFlag(node, "visible", !node.visible);
      },
    },
    {
      label: "Toggle render to buffer",
      icon: "visibility_off",
      action: () => {
        const owner = project.layers.find((entry) => entry.nodeIds.includes(node.id));
        if (!owner) {
          setStatus("This item has no layer.");
          return;
        }
        setLayerRenderToBuffer(owner, !owner.renderToBuffer);
      },
    },
    {
      label: "Rename",
      icon: "text_fields",
      action: () => {
        const next = window.prompt("Object name", node.name);
        if (!next?.trim()) return;
        renameNode(node, next.trim());
      },
    },
    {
      label: "Note",
      icon: "sticky_note_2",
      action: () => editNodeNote(node),
    },
    {
      label: "Delete",
      shortcut: "Del",
      icon: "delete",
      action: () => {
        select(node.id);
        deleteSelected();
      },
    },
    {
      label: "Add automation",
      icon: "timeline",
      action: () => {
        const path = node.animatablePaths()[0];
        if (!path) return;
        ensureAutomation(node.id, path);
        addKeyframe(node.id, path);
        refreshInspector();
        setStatus(`Added automation on ${path}.`);
      },
    },
  ]);
}

interface LayoutState {
  editorLayout: number;
  locked: boolean;
  expandedLeftSidebar: boolean;
}

const LAYOUT_KEY = "studio:layout";

function loadLayout(): LayoutState {
  const fallback: LayoutState = { editorLayout: 1, locked: false, expandedLeftSidebar: true };
  try {
    const raw = localStorage.getItem(LAYOUT_KEY);
    if (!raw) return fallback;
    const saved = JSON.parse(raw) as Partial<LayoutState>;
    return {
      editorLayout: typeof saved.editorLayout === "number" ? saved.editorLayout : 1,
      locked: Boolean(saved.locked),
      expandedLeftSidebar: saved.expandedLeftSidebar !== false,
    };
  } catch {
    return fallback;
  }
}

const layout = loadLayout();

/** Panel widths per layout preset; mirrors the reference's editorLayout key. */
function applyLayout(): void {
  const presets: Record<number, { compositor: string; inspector: string }> = {
    // Preset 1 matches the reference's measured layout at 1297px: left 347
    // (rail 68 + compositor 279), canvas 658, inspector 243.
    1: { compositor: "279px", inspector: "243px" },
    2: { compositor: "220px", inspector: "300px" },
    3: { compositor: "300px", inspector: "300px" },
  };
  const preset = presets[layout.editorLayout] ?? presets[1];
  const root = document.documentElement;
  root.style.setProperty("--compositor", preset.compositor);
  root.style.setProperty("--inspector", layout.expandedLeftSidebar ? preset.inspector : "0px");
  // Custom pane sizes from the splitters win over the preset defaults.
  try {
    const saved = JSON.parse(localStorage.getItem("studio:panelSizes") ?? "{}") as {
      compositor?: number;
      inspector?: number;
    };
    if (typeof saved.compositor === "number") {
      root.style.setProperty("--compositor", `${saved.compositor}px`);
    }
    if (typeof saved.inspector === "number" && layout.expandedLeftSidebar) {
      root.style.setProperty("--inspector", `${saved.inspector}px`);
    }
  } catch {
    /* ignore malformed sizes */
  }
  $("#app").classList.toggle("layout-locked", layout.locked);
  $("#app").dataset.layout = String(layout.editorLayout);

  // The reference stores the panel arrangement as a recursive tree; ours mirrors
  // the same shape so the key round-trips with the same structure.
  const customLayout =
    layout.editorLayout === 4
      ? {
          direction: "column",
          first: {
            direction: "row",
            first: { panel: "stage" },
            second: { panel: "codeEditor" },
            splitPercentage: 60,
          },
          second: { panel: "timeline" },
          splitPercentage: 75,
        }
      : {
          direction: "column",
          first: { direction: "row", first: { panel: "topbar" }, second: { panel: "menus" } },
          second: {
            direction: "column",
            first: {
              direction: "row",
              first: { panel: "rail" },
              second: {
                direction: "row",
                first: { panel: "compositor", width: preset.compositor },
                second: {
                  direction: "row",
                  first: { panel: "stage" },
                  second: {
                    panel: "inspector",
                    width: layout.expandedLeftSidebar ? preset.inspector : "0px",
                  },
                },
              },
            },
            second: { panel: "timeline" },
          },
        };

  localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
  localStorage.setItem("customEditorLayout", JSON.stringify(customLayout));
  syncCodeEditor();
}

/** Reference F: the focused Canvas + CodeEditor layout. */
function openCodeEditorLayout(): void {
  if (layout.editorLayout === 4) return;
  layoutBeforeCodeEditor = layout.editorLayout;
  layout.editorLayout = 4;
  applyLayout();
}

function closeCodeEditorLayout(): void {
  if (layout.editorLayout !== 4) return;
  layout.editorLayout = layoutBeforeCodeEditor ?? 1;
  layoutBeforeCodeEditor = null;
  applyLayout();
}

function toggleCodeEditorLayout(): void {
  const opening = layout.editorLayout !== 4;
  if (opening) openCodeEditorLayout();
  else closeCodeEditorLayout();
  setStatus(`Code editor layout ${opening ? "on" : "off"}.`);
}

codeClose.addEventListener("click", () => {
  if (layout.editorLayout !== 4) return;
  closeCodeEditorLayout();
  setStatus("Code editor closed.");
});

function cycleEditorLayout(): void {
  layoutBeforeCodeEditor = null;
  layout.editorLayout = layout.editorLayout === 4 || layout.editorLayout >= 3 ? 1 : layout.editorLayout + 1;
  applyLayout();
  setStatus(`Editor layout ${layout.editorLayout}${layout.locked ? " (locked)" : ""}.`);
}

function toggleLayoutLock(): void {
  layout.locked = !layout.locked;
  applyLayout();
  setStatus(`Layout ${layout.locked ? "locked" : "unlocked"}.`);
}

function toggleLeftSidebar(): void {
  if (layout.locked) {
    setStatus("Layout is locked.");
    return;
  }
  layout.expandedLeftSidebar = !layout.expandedLeftSidebar;
  applyLayout();
  setStatus(`Left sidebar ${layout.expandedLeftSidebar ? "expanded" : "collapsed"}.`);
}

function toggle3D(): void {
  is3D = renderer.set3D(!is3D);
  setStatus(is3D ? "3D mode on (perspective view)." : "3D mode off (orthographic view).");
}

function openCommandPalette(): void {
  document.querySelector(".modal-backdrop")?.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.setAttribute("role", "dialog");

  const head = document.createElement("header");
  head.className = "modal-head";
  head.textContent = "Command Palette";

  const input = document.createElement("input");
  input.className = "catalogue-search";
  input.placeholder = ">";

  const list = document.createElement("div");
  list.className = "catalogue-list";
  list.style.maxHeight = "320px";

  const referenceCommands: { title: string; key: string; action: () => void }[] = [
    { title: "(Global) Delete", key: "Del, Backspace", action: deleteSelection },
    { title: "(Global) Split at playhead", key: "Ctrl+K", action: splitAtPlayhead },
    {
      title: "(Global) Zoom to selection",
      key: "Z",
      action: () => {
        if (timeline.zoomToSelection()) {
          zoom = timeline.getViewState().zoom;
          setStatus("Zoomed to selection.");
        } else {
          setStatus("Select a clip to zoom to it.");
        }
      },
    },
    {
      title: "(Global) Toggle mute",
      key: "M",
      action: () => {
        if (project.volume > 0) {
          lastVolume = project.volume;
          project.volume = 0;
        } else {
          project.volume = lastVolume || 100;
        }
        applyAudioSettings();
      },
    },
    {
      title: "3D: Toggle transform control",
      key: "I",
      action: () => renderer.setGizmoEnabled(!renderer.gizmoState().enabled),
    },
    { title: "3D: Edit position", key: "W", action: () => renderer.setGizmoMode("translate") },
    { title: "3D: Edit rotation", key: "E", action: () => renderer.setGizmoMode("rotate") },
    { title: "3D: Edit scale", key: "R", action: () => renderer.setGizmoMode("scale") },
    { title: "3D: Toggle camera mode", key: "Ctrl+F", action: toggle3D },
    { title: "Add: Layer", key: "L", action: () => $<HTMLButtonElement>("#btn-add-layer").click() },
    { title: "Add: Effect", key: "F", action: () => $<HTMLButtonElement>("#btn-add-effect").click() },
    {
      title: "Automations: Add selected to new folder",
      key: "G",
      action: addAutomationsToNewFolder,
    },
    { title: "Edit: Copy", key: "Ctrl+C", action: copySelection },
    { title: "Edit: Paste", key: "Ctrl+V", action: pasteClipboard },
    { title: "File: Save project", key: "Ctrl+S", action: () => void saveProjectLocally() },
    { title: "File: Save as new", key: "Ctrl+Shift+S", action: () => void saveProjectAsNew() },
    { title: "File: Export", key: "Ctrl+E", action: openExportDialog },
    { title: "File: New project", key: "Ctrl+B", action: newProject },
    { title: "Preview: 360p", key: "Ctrl+1", action: () => applyResolution(RESOLUTION_SIDES[0]) },
    { title: "Preview: 480p", key: "Ctrl+2", action: () => applyResolution(RESOLUTION_SIDES[1]) },
    { title: "Preview: 720p", key: "Ctrl+3", action: () => applyResolution(RESOLUTION_SIDES[2]) },
    { title: "Preview: 1080p", key: "Ctrl+4", action: () => applyResolution(RESOLUTION_SIDES[3]) },
    { title: "Preview: Capture frame", key: "F2", action: () => void savePreviewImage() },
    {
      title: "Preview: Debug performance",
      key: "F3",
      action: () => $("#hud").classList.toggle("hidden"),
    },
    {
      title: "Preview: Fullscreen",
      key: "Ctrl+Enter",
      action: () => $<HTMLButtonElement>("#btn-fullscreen").click(),
    },
    ...["composition", "analyzers", "effects", "automations", "media", "projects", "lyrics"].map(
      (panel, index) => ({
        title: `Tab: ${panel.charAt(0).toUpperCase()}${panel.slice(1)}`,
        key: String(index + 1),
        action: () => setLeftPanel(panel),
      }),
    ),
    { title: "Transport: Play", key: "Space", action: () => setPlaying(!playing) },
    {
      title: "Transport: Play from beginning",
      key: "Shift+Space",
      action: () => {
        time = 0;
        setPlaying(true);
      },
    },
    {
      title: "Transport: One frame forward",
      key: "Period",
      action: () => {
        time = Math.min(project.duration, time + 1 / project.fps);
      },
    },
    {
      title: "Transport: One frame backwards",
      key: "Comma",
      action: () => {
        time = Math.max(0, time - 1 / project.fps);
      },
    },
    { title: "View: Command Palette", key: "Ctrl+Shift+P", action: openCommandPalette },
    { title: "View: Window dragging", key: "Ctrl+D", action: toggleLayoutLock },
    {
      title: "View: Toggle shy layers",
      key: "Ctrl+H",
      action: () => $<HTMLButtonElement>("#btn-shy").click(),
    },
  ];
  // The reference builds its palette from a fixed catalogue sorted by title and
  // filters with a plain case-insensitive substring match (MUI's default), so
  // match order is catalogue order rather than match position.
  if (typeof navigator !== "undefined" && /mac/i.test(navigator.platform)) {
    for (const command of referenceCommands) command.key = command.key.replace("Ctrl", "Cmd");
  }
  const studioCommands = EXTRA_COMMANDS.filter(
    (entry): entry is Exclude<MenuEntry, { separator: true }> => !("separator" in entry),
  )
    .map((entry) => ({ title: `Studio: ${entry.label}`, key: "", action: entry.action }))
    .sort((a, b) => a.title.localeCompare(b.title));
  const commands = [...referenceCommands, ...studioCommands].sort((a, b) =>
    a.title.localeCompare(b.title),
  );

  const render = (): void => {
    list.textContent = "";
    const query = input.value.trim().toLowerCase();
    const matches = commands
      .filter((command) => command.title.toLowerCase().includes(query))
      .slice(0, 40);
    for (const command of matches) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "catalogue-item";
      const label = document.createElement("span");
      label.textContent = command.title;
      button.append(label);
      if (command.key) {
        const hint = document.createElement("span");
        hint.className = "command-key";
        hint.textContent = command.key;
        button.append(hint);
      }
      button.addEventListener("click", () => {
        backdrop.remove();
        command.action();
      });
      list.append(button);
    }
  };

  input.addEventListener("input", render);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      backdrop.remove();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      list.querySelector<HTMLButtonElement>("button")?.focus();
    } else if (event.key === "Enter") {
      event.preventDefault();
      list.querySelector<HTMLButtonElement>("button")?.click();
    }
  });
  list.addEventListener("keydown", (event) => {
    const buttons = [...list.querySelectorAll<HTMLButtonElement>("button")];
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "Escape") {
      event.preventDefault();
      backdrop.remove();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      buttons[(index + 1) % buttons.length]?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      buttons[(index - 1 + buttons.length) % buttons.length]?.focus();
    }
  });
  render();

  modal.append(head, input, list);
  backdrop.append(modal);
  backdrop.addEventListener("pointerdown", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  document.body.append(backdrop);
  input.focus();
}

function applyTheme(theme: string): void {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("studio:theme", theme);
}

function toggleTheme(): void {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next);
  setStatus(`Theme: ${next}.`);
}

/** Add a named marker at the playhead (Shift+M), one undo step. */
function addMarker(): void {
  const marker = {
    id: newId("marker"),
    time: Math.round(time * 100) / 100,
    name: `Marker ${project.markers.length + 1}`,
  };
  const insert = (): void => {
    if (!project.markers.includes(marker)) project.markers.push(marker);
    project.markers.sort((a, b) => a.time - b.time);
  };
  insert();
  history.push({
    label: "add marker",
    undo: () => {
      project.markers = project.markers.filter((entry) => entry !== marker);
    },
    redo: insert,
  });
  setStatus(`Added ${marker.name} at ${formatTime(marker.time)}.`);
}

function openMarkerMenu(index: number, x: number, y: number): void {
  const marker = project.markers[index];
  if (!marker) return;
  showMenuAt(x, y, [
    {
      label: "Rename",
      icon: "text_fields",
      action: () => {
        const next = window.prompt("Marker name", marker.name);
        if (next === null) return;
        const name = next.trim() || marker.name;
        const before = marker.name;
        if (name === before) return;
        marker.name = name;
        timeline.render(time, selectedId);
        history.push({
          label: "rename marker",
          undo: () => {
            marker.name = before;
            timeline.render(time, selectedId);
          },
          redo: () => {
            marker.name = name;
            timeline.render(time, selectedId);
          },
        });
        setStatus("Marker renamed.");
      },
    },
    {
      label: "Delete",
      icon: "delete",
      action: () => {
        const at = project.markers.indexOf(marker);
        if (at < 0) return;
        const remove = (): void => {
          project.markers = project.markers.filter((entry) => entry !== marker);
        };
        remove();
        history.push({
          label: "remove marker",
          undo: () => {
            project.markers.splice(Math.min(at, project.markers.length), 0, marker);
            project.markers.sort((a, b) => a.time - b.time);
          },
          redo: remove,
        });
        setStatus("Marker removed.");
      },
    },
  ]);
}

function toggleKeyframes(): void {
  timeline.showKeyframes = !timeline.showKeyframes;
  const button = $("#btn-keyframes") as HTMLButtonElement | null;
  if (button) button.title = timeline.showKeyframes ? "Hide keyframes" : "Show keyframes";
  timeline.render(time, selectedId);
  setStatus(`Keyframes ${timeline.showKeyframes ? "shown" : "hidden"}.`);
}

function mountShortcuts(): void {
  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    const target = event.target as HTMLElement | null;
    if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
    const key = event.key.toLowerCase();
    if (key === "e") {
      event.preventDefault();
      openExportDialog();
    }
    if (key === "b") {
      event.preventDefault();
      newProject();
    }
    if (key === "c") {
      event.preventDefault();
      copySelection();
    }
    if (key === "x") {
      event.preventDefault();
      cutSelection();
    }
    if (key === "d") {
      event.preventDefault();
      toggleLayoutLock();
    }
    if (key === "v") {
      event.preventDefault();
      pasteClipboard();
    }
    if (key === "p" && event.shiftKey) {
      event.preventDefault();
      openCommandPalette();
      return;
    }
    if (key === "f") {
      event.preventDefault();
      toggle3D();
    }
    if (key === "s" && event.shiftKey) {
      event.preventDefault();
      void saveProjectAsNew();
      return;
    }
    if (key === "s") {
      event.preventDefault();
      void saveProjectLocally();
    }
  });
}

/* ------------------------------------------------------------------ */
/* Start                                                               */
/* ------------------------------------------------------------------ */

loadComposition();
applyLayout();
renderer.setHideShyLayers(hideShyLayers);
applyAudioSettings();
// The reference analyser is the primary band source; start its wasm early so
// the JS fallback is only used for the first frames.
preloadVizzyAnalyser();
seed();
refreshTree();
refreshInspector();
refreshHistoryButtons();
timeline.setZoom(zoom);

for (const button of document.querySelectorAll<HTMLButtonElement>("#rail .rail-item")) {
  button.addEventListener("click", () => setLeftPanel(button.dataset.panel ?? "composition"));
}

mountMenus();
mountShortcuts();
document.documentElement.dataset.dev = import.meta.env.DEV ? "1" : "0";
$("#project-name").textContent = project.name;
$("#btn-release").addEventListener("click", showChangelog);
$("#btn-warnings").addEventListener("click", openWarnings);
$("#btn-signin").addEventListener("click", openAccountDialog);
$("#compositor .panel-title").addEventListener("dblclick", toggleLeftSidebar);

$("#tier").textContent = `fft: ${spectrum.tier}`;
$("#tier").title = `${spectrum.reason}\nSIMD: ${spectrum.capabilities.wasmSimd}\nthreads: ${spectrum.capabilities.wasmThreads}\ncores: ${spectrum.capabilities.hardwareConcurrency}`;
setStatus(
  `fft tier "${spectrum.tier}" — ${spectrum.reason}. Drop an audio file to drive the spectrum, or leave it on the synthetic source.`,
);

requestAnimationFrame(loopTick);

// Boot with the project's default track when it is served; the synthetic source
// remains the fallback when the file is absent.
void (async () => {
  try {
    const response = await fetch("/audio/haende-hoch.mp3");
    if (!response.ok) return;
    const bytes = new Uint8Array(await response.arrayBuffer());
    // An import may have landed while the track was downloading.
    if (defaultTrackSuppressed) return;
    setStatus(await loadAudioFromBytes("Hände Hoch.mp3", bytes));
  } catch {
    /* keep the synthetic source */
  }
})();
Object.assign(globalThis, {
  editorProject: project,
  editorSpectrum: spectrum,
  editorRenderer: renderer,
  editHistory: history,
  editorAudio: audio,
  editorAssets: assets,
  /** Test hook: load a track and wait for its impact scan to finish. */
  editorLoadAudio: async (
    name: string,
    bytes: Uint8Array,
    options?: { resetSpans?: boolean; computeImpact?: boolean },
  ) => {
    const result = await loadAudioFromBytes(name, bytes, options);
    await impactScanPromise;
    return result;
  },
  /** Resolves when the background impact scan for the loaded track finishes. */
  editorAudioImpactReady: () => impactScanPromise ?? Promise.resolve(),
  // Exercises the real import path, media fetching included.
  editorImportProject: importProjectJson,
  editorOpenCreations: openCreationsBrowser,
  editorOpenExportDialog: openExportDialog,
  editorNewProject: (force = false) => newProject(force),
  // Direct export for the E2E harness, without driving the modal.
  editorExportNow: (settings?: Partial<ExportSettings>, saveHandle?: SaveFileHandle | null) =>
    runExport({ ...defaultExportSettings(), ...settings }, saveHandle ?? null),
  /** Test/thumbnail hook: run keyframe/math/audio-impact automations at a time. */
  editorApplyAutomations: (at: number) => applyAutomations(at),
  /** Test hook: the Spectrum item's Audio Impact automation, in display units. */
  editorSpectrumReaction: (nodeId: string) => {
    const node = findNode(nodeId);
    return node instanceof SpectrumNode ? spectrumReactionView(node) : null;
  },
  /** Test/thumbnail hook: resolve the analyser bands at a paused time. */
  editorTickAudio: (at: number, dt = 1 / 60) => spectrum.tickForExport(at, dt),
  // Save/open round-trip hooks used by the project test.
  editorSaveProject: saveProjectLocally,
  editorOpenProject: openSavedProject,
  editorSerializeProject: () => serializeProject(project),
  editorRestoreProject: (snapshot: ProjectSnapshot) => applyProjectSnapshot(snapshot),
  editorSetBackgroundImage: setBackgroundImage,
  editorAddVideo: addVideoFromFile,
  editorSeek: (seconds: number) => {
    time = seconds;
    timeline.setPlayhead(seconds);
  },
  editorTime: () => time,
  editorTimelineState: () => timeline.getViewState(),
  editorTimelineWaveform: () => timeline.getWaveformState(),
  editorTimelineLoop: () => timeline.getLoopRange(),
  editorTimelineRow: (nodeId: string) => timeline.getRowForNode(nodeId),
  editorTimelineSelection: () => timeline.getSelection(),
  editorTimelineLayers: () => timeline.getLayerRows(),
  editorTimelineAutomationRows: () => timeline.getAutomationRows(),
  editorTimelineDragReadout: () => timeline.getDragReadout(),
  editorTimelineSlipReadout: () => timeline.getSlipReadout(),
  editorTimelineKeyPositions: () => timeline.getKeyPositions(),
  editorTimelineKeySelection: () => timeline.getSelectedKeys(),
  editorTimelineRenderStats: () => timeline.getRenderStats(),
  editorAddKeyframe: addKeyframe,
  editorSelect: select,
  editorTimelineTool: () => timeline.getTool(),
  editorSelectedLayerId: () => selectedLayerId,
  editorSelectedId: () => selectedId,
  editorSelectedAnalyzerId: () => selectedAnalyzerId,
  editorLogText: logTextFor,
});

/* CAMXORA-PATCH (scripts/sync-vizzy.mjs): host-driven native export.
 *
 * The shell owns the job, the destination file and cancellation. This block
 * calls the editor's own runExport() with a SaveFileHandle whose write()
 * forwards encoded chunks to the desktop process (structured clone, never
 * base64), reports progress through the bridge, and reports a terminal state
 * exactly once. The in-page export dialog above is unchanged and still works
 * as the browser fallback.
 */
{
  interface HostExportSettings {
    width: number;
    height: number;
    fps: number;
    format: "mp4" | "webm";
    codec: "h264" | "vp8" | "vp9";
    bitrate: number;
    crf: number;
    start: number;
    end: number;
  }
  interface HostExportCommand {
    v: 1;
    type: string;
    jobId?: string;
    settings?: HostExportSettings;
  }
  interface HostExportBridge {
    exportChunk(jobId: string, position: number, data: Uint8Array): Promise<{ bytes: number }>;
    exportProgress(payload: {
      jobId: string;
      done: number;
      total: number;
      stage: string;
    }): void;
    exportFinished(payload: {
      jobId: string;
      ok: boolean;
      cancelled: boolean;
      frames: number;
      error?: string;
    }): void;
    onCommand(handler: (command: HostExportCommand) => void): () => void;
  }

  const exportHost = (window as unknown as { camxoraVizzy?: HostExportBridge }).camxoraVizzy;
  if (exportHost && typeof exportHost.onCommand === "function") {
    let activeJobId: string | null = null;
    let cancelRequested = false;

    const isAbort = (reason: unknown): boolean =>
      (reason instanceof DOMException && reason.name === "AbortError") ||
      (reason instanceof Error && /cancel/i.test(reason.message)) ||
      (typeof reason === "string" && /cancel/i.test(reason));

    exportHost.onCommand((command) => {
      if (command.type === "export-cancel") {
        if (command.jobId && command.jobId === activeJobId) cancelRequested = true;
        return;
      }
      if (command.type !== "export-run" || !command.jobId || !command.settings) return;
      if (activeJobId) return;

      const jobId = command.jobId;
      const request = command.settings;
      const format = request.format === "webm" ? "webm" : "mp4";
      const codec: ExportCodec =
        format === "mp4" ? "h264" : request.codec === "vp8" ? "vp8" : "vp9";
      const settings: ExportSettings = {
        ...defaultExportSettings(),
        width: request.width,
        height: request.height,
        fps: request.fps,
        start: request.start,
        end: request.end,
        codec,
        bitrate: request.bitrate,
        crf: request.crf,
        // Honour the requested encoder. WebCodecs supports AVC/MP4 as well as
        // VP8/VP9/WebM; the export dialog's choice used to be ignored for MP4,
        // which forced every H.264 render through the wasm encoder.
        engine:
          request.engine === "webcodecs" && WebCodecsExporter.available()
            ? "webcodecs"
            : "wasm",
      };
      let framesTotal = Math.max(
        1,
        Math.round(Math.max(0.1, settings.end - settings.start) * Math.max(1, Math.round(settings.fps))),
      );

      activeJobId = jobId;
      cancelRequested = false;
      let reported = false;
      let renderedFrames = 0;

      const report = (payload: {
        ok: boolean;
        cancelled: boolean;
        frames: number;
        error?: string;
      }): void => {
        if (reported) return;
        reported = true;
        activeJobId = null;
        camxoraExportHooks = null;
        exportHost.exportFinished({ jobId, ...payload });
      };

      const handle: SaveFileHandle = {
        name: `${jobId}.${format}`,
        async createWritable() {
          return {
            async write(data) {
              if (data && typeof data === "object" && "type" in data && data.type === "write") {
                await exportHost.exportChunk(jobId, data.position, data.data);
                return;
              }
              // Blob fallback (non-streaming wasm ladder): slice it so no IPC
              // message ever carries the whole video.
              const bytes = new Uint8Array(await (data as Blob).arrayBuffer());
              const size = 4 * 1024 * 1024;
              for (let offset = 0; offset < bytes.byteLength; offset += size) {
                await exportHost.exportChunk(
                  jobId,
                  offset,
                  bytes.subarray(offset, Math.min(bytes.byteLength, offset + size)),
                );
              }
            },
            async close() {
              report({ ok: true, cancelled: false, frames: Math.max(renderedFrames, framesTotal) });
            },
            async abort(reason) {
              report({
                ok: false,
                cancelled: cancelRequested || isAbort(reason),
                frames: renderedFrames,
                error:
                  reason instanceof Error
                    ? reason.message
                    : String(reason ?? "Export aborted"),
              });
            },
          };
        },
      };

      camxoraExportHooks = {
        progress(done: number, total: number, stage: string) {
          renderedFrames = Math.max(renderedFrames, done);
          if (total > 0) framesTotal = total;
          exportHost.exportProgress({ jobId, done, total, stage });
        },
        cancelled: () => cancelRequested,
      };

      void (async () => {
        try {
          await runExport(settings, handle);
        } finally {
          if (!reported) {
            report({
              ok: false,
              cancelled: cancelRequested,
              frames: renderedFrames,
              error: cancelRequested
                ? "The export was cancelled."
                : "The exporter finished without writing a file.",
            });
          }
          if (activeJobId === jobId) activeJobId = null;
          camxoraExportHooks = null;
        }
      })();
    });
  }
}

// This module owns the WebGL renderer, the editor DOM and the rAF loop. Vite's
// hot updates re-execute it in the same page, which used to stack another
// renderer/loop on top of the running one, so the studio got slower with every
// edit. A reload would fix that but it also kills CDP sessions and the test
// runner, so the loop is generation-guarded instead: only the newest module's
// rAF keeps scheduling frames.
const loopGenerationKey = "__studioLoopGeneration";
const loopGeneration =
  ((globalThis as Record<string, unknown>)[loopGenerationKey] as number | undefined ?? 0) + 1;
(globalThis as Record<string, unknown>)[loopGenerationKey] = loopGeneration;
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    (globalThis as Record<string, unknown>)[loopGenerationKey] = loopGeneration + 1;
  });
}


