/**
 * Importer for the reference editor's project exports.
 *
 * The export is a graph: `objects` holds every entity, and `values` holds each
 * entity's settings under the same id (`item:Spectrum:…`, `analyzer:…`,
 * `effect:…`, `automation:…`). Effects, analyzers and automations also appear in
 * their own maps, which carry the connection data.
 *
 * Only what the editor can actually render is imported. Anything else is
 * reported in `skipped` rather than silently dropped or guessed at.
 */

import { createAnalyzer, type SampleProvider } from "./analyzers";
import { EASING_OPTIONS, type EasingName } from "./easing";
import { createEffect, definitionsFor, GLOBAL_TARGET } from "./effects";
import { AnimatedTextNode, AudioWaveNode, BasicSpectrumBarsNode, ButterchurnNode, ConfettiNode, createNode, ParticleLinesNode, GroundNode, LogoNode, InstancedParticleSystemNode, LineBedNode, ParticleSystemNode, ParticleTimeLineNode, LyricsNode, MediaNode, SphericalFieldNode, ModelNode, NoiseNode, ParticlesNode, PrimitiveNode, ProgressBarNode, ShaderItemNode, SkiaTextNode, SkottieNode, VideoNode } from "./nodes";
import type { AnyNode, SpectrumNode } from "./nodes";
import type { Project } from "./project";
import { scaleMultiplierFromReference } from "./reference-scale";
import { deserializeLayers } from "./spectrum-layers";
import { NodeKind, type Automation, type Easing } from "./types";

type Loose = Record<string, unknown>;

const asRecord = (value: unknown): Loose =>
  value && typeof value === "object" ? (value as Loose) : {};

const num = (value: unknown, fallback: number): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const str = (value: unknown, fallback: string): string =>
  typeof value === "string" ? value : fallback;

/**
 * The export names item properties without our container prefix: an automation
 * targets `scaleMultiplier`, while the node exposes `transform.scaleMultiplier`.
 */
const NODE_PROPERTY_IDS: Record<string, string> = {
  scaleMultiplier: "transform.scaleMultiplier",
  height: "behaviour.height",
  dotSize: "behaviour.dotSize",
  feather: "behaviour.feather",
  // Item transforms are addressed by the reference's own surface names
  // (`position:x`, `rotation:z`, `scale:y`). Without this mapping automation
  // wrote unused keys, so every keyframed item move/rotate/scale was ignored.
  "position:x": "transform.x",
  "position:y": "transform.y",
  "position:z": "transform.z",
  "rotation:x": "transform.rotX",
  "rotation:y": "transform.rotY",
  "rotation:z": "transform.rotZ",
  "scale:x": "transform.scaleX",
  "scale:y": "transform.scaleY",
  "scale:z": "transform.scaleZ",
};

function mapNodeProperty(name: string): string {
  return NODE_PROPERTY_IDS[name] ?? name;
}

const AXES = ["x", "y", "z"] as const;

/**
 * Copies the reference's Transform surface (`position:x`, `rotation:y`,
 * `scale:z`, …) onto a node's controller mapping. Scale factors are stored as
 * percentages in Rea; absent axes keep the node's current value.
 */
function applyReferenceTransform(node: AnyNode, entry: Loose): void {
  for (const axis of AXES) {
    const key = axis.toUpperCase();
    node.objectMapping.set(
      `transform.${axis}`,
      num(entry[`position:${axis}`], node.readNumber(`transform.${axis}`)),
    );
    node.objectMapping.set(
      `transform.rot${key}`,
      num(entry[`rotation:${axis}`], node.readNumber(`transform.rot${key}`)),
    );
    const scale = entry[`scale:${axis}`];
    node.objectMapping.set(
      `transform.scale${key}`,
      typeof scale === "number" || typeof scale === "string"
        ? num(scale, 1) * 100
        : node.readNumber(`transform.scale${key}`),
    );
  }
}

// The reference serves preset artwork from Firebase Storage. Those URLs reject
// the editor's cross-origin image fetch, leaving presets such as 22 on their
// fallback colour (a black disc with no logo). The same files ship under
// `/media`, so rewrite the five known URLs before they reach the texture loader.
const VENDORED_IMAGES: Record<string, string> = {
  "https://firebasestorage.googleapis.com/v0/b/vizzy-6ced1.appspot.com/o/images%2FwY07nYf1xiYsc0fEzJ5sI3gKsJX2%2FwY07nYf1xiYsc0fEzJ5sI3gKsJX2%2Fprojects_v0.91%2FhlippwZ9caHBjJaOXoBki%2FV_uKphKoBqRUiHHD20KPU?alt=media&token=75782370-78e9-4c35-ad35-de275f1ddbb8":
    "/media/preset-13.webp",
  "https://firebasestorage.googleapis.com/v0/b/vizzy-6ced1.appspot.com/o/images%2FfgcVkeFkoCPFnhiTWMfgJciQbm13%2FfgcVkeFkoCPFnhiTWMfgJciQbm13%2Fprojects_v0.91%2FlM5nDXhrg5Hhr41zNq4lq%2FWd7bbkEljxgM-bxLxBLH7?alt=media&token=fc252ac6-0024-42ee-a004-946117831f43":
    "/media/preset-19.png",
  "https://firebasestorage.googleapis.com/v0/b/vizzy-6ced1.appspot.com/o/images%2FGIxNEuJvMfOvaDfbzNhSiclaGAa2%2F0rnGJGDB0KL3Ea8zoKNvg.png?alt=media&token=5db9ea05-be72-4b3b-9fae-62918dbe4978":
    "/media/preset-22.png",
  "https://firebasestorage.googleapis.com/v0/b/vizzy-6ced1.appspot.com/o/images%2FlhncCGm4PwY4YZtGkuEzM4Bfhni1%2Fprojects_v0.91%2FNp1y-uCQ85orNU9XjGmLl%2FFN-2UoLiQFsnPQ1zztMjO?alt=media&token=f87c644a-57e9-4eee-9990-77cb8df7160a":
    "/media/preset-25.webp",
  "https://firebasestorage.googleapis.com/v0/b/vizzy-6ced1.appspot.com/o/images%2FaVqILeOXKaeGTojCs5RO79HbQsc2%2FaVqILeOXKaeGTojCs5RO79HbQsc2%2Fprojects_v0.91%2FfCmYKaSOt_dQsa9KKfSvt%2F3fQy9ugWrdsQcWqKG6jWb?alt=media&token=5d2cf54c-4a9a-4b8d-99a5-cf0fbb0cae62":
    "/media/preset-27.jpg",
};

/**
 * Reference effect display names that do not slugify to Rea's internal type id
 * (`Fish eye 2` -> `fisheye-2`, `Mask` -> `image-mask`, `Glow` -> `glow-bloom`).
 */
const EFFECT_TYPE_ALIASES: Record<string, string> = {
  "fish-eye": "fisheye",
  "fish-eye-2": "fisheye-2",
  "vhs-2": "vhs2",
  "simple-shadow": "drop-shadow",
  mask: "image-mask",
  "triangle-blur": "blur-triangle",
  glow: "glow-bloom",
  "glow-2": "glow",
};

// Reference bundle assets that ship with the editor. The old `/vizzy-static`
// prefix 404s on the live site, so only mapped files are served.
const STATIC_ASSETS: Record<string, string> = {
  "/static/media/logo_transparent.dded2d31.webp": "/media/logo_transparent.webp",
  "/static/media/16.c457b6c2.webp": "/creations/assets/background-16.c457b6c2.webp",
  "/static/media/circle_05_alpha.eaa86b2c.webp": "/creations/assets/circle_05_alpha.eaa86b2c.webp",
  "/static/media/circle_05_alpha.97791320.png":
    "/creations/assets/templates/bunny-ears/particle-circle-05-alpha.webp",
  "/static/media/Logo.2be98029.webp":
    "/creations/assets/templates/lightning-spectrum/logo-transparent.webp",
  "/static/media/preset1.07be03c2.webp": "/creations/assets/templates/burning-moon/preset1.07be03c2.webp",
};

const resolveAssetUrl = (value: string): string => {
  if (!value) return "";
  const vendored = VENDORED_IMAGES[value];
  if (vendored) return vendored;
  const staticAsset = STATIC_ASSETS[value];
  if (staticAsset) return staticAsset;
  if (value.startsWith("/creations/") || value.startsWith("/media/")) return value;
  if (/^https?:/i.test(value)) return value;
  return "";
};

export interface ImportDeps {
  /** Creates an unattached node; the caller owns attaching it to the renderer. */
  createNode: (kind: NodeKind, name: string) => AnyNode;
}

export interface ImportReport {
  name: string;
  nodes: number;
  layers: number;
  compositionLayers: number;
  analyzers: number;
  effects: number;
  automations: number;
  /** Remote images the caller should fetch and attach after import. */
  media: { nodeId: string; url: string }[];
  /** Approximations worth surfacing, e.g. an effect widened to the whole frame. */
  notes: string[];
  skipped: { what: string; reason: string }[];
}

function mapType(value: unknown): SpectrumNode["type"] {
  const raw = str(value, "").toLowerCase();
  if (raw === "circle") return "Circle";
  if (raw === "custom") return "Custom";
  if (raw === "image") return "Image";
  return "Bars";
}

function mapDraw(value: unknown): SpectrumNode["draw"] {
  const raw = str(value, "").toLowerCase();
  if (raw === "curve") return "Curve";
  if (raw === "plexus") return "Plexus";
  if (raw === "point") return "Point";
  return "Line";
}

const EASING_NAMES = new Set<string>(EASING_OPTIONS);

function mapEasing(value: unknown): Easing {
  const raw = str(value, "linear");
  if (EASING_NAMES.has(raw)) return raw as EasingName;
  // Legacy/hand-authored projects used the coarse vocabulary.
  const lower = raw.toLowerCase();
  if (lower === "hold" || lower === "step") return "hold";
  if (lower === "ease-in") return "ease-in";
  if (lower === "ease-out") return "ease-out";
  return "linear";
}

/**
 * Replace `target`'s contents with the export. Mutates in place so the renderer
 * and every other holder of the project reference stay valid.
 */
/**
 * Applies a reference Spectrum item's values to a node. Shared by whole-project
 * import and by presets, so both go through one proven mapping.
 * The entry may carry flattened `spectrum_layer:N:*` keys.
 */
export function applySpectrumExport(
  node: SpectrumNode,
  entry: Record<string, unknown>,
  options: { pathRenderer?: boolean } = {},
): number {
  // Presets are overlays in the reference payload, but a preset tile is a
  // complete look. Start from the reference item defaults so a missing field
  // cannot inherit the previous preset's value (the old bug made `clipCircle`
  // and `dotSize` depend on click order).
  node.resetPresetLook();

  node.type = mapType(entry.spectrumType);
  node.draw = mapDraw(entry.drawType);
  node.fillStyle = str(entry.fillType, "fill") === "stroke" ? "Stroke" : "Fill";
  node.mirror = Boolean(entry.mirrorHorizontal);

  // These are our own engine controls; the reference payload does not carry
  // them, so a preset must reset them instead of inheriting the previous look.
  node.bands = 64;
  node.objectMapping.set("effects.gain", 1);
  node.objectMapping.set("effects.colorShift", 0);
  node.objectMapping.set("effects.smoothing", 60);
  node.objectMapping.set("behaviour.opacity", 95);
  node.objectMapping.set("behaviour.feather", 8);

  const layers = deserializeLayers(entry);
  if (layers.length > 0) {
    node.layers.splice(0, node.layers.length, ...layers);
    node.color = layers[0].color;
  }

  // Preset snapshots carry the look, not the item's identity. Only a project
  // export has a time span / enabled flag, so applying a preset must not move
  // the item on the timeline or unhide it.
  if (Array.isArray(entry.time)) {
    const span = entry.time as unknown[];
    node.start = num(span[0], 0);
    node.duration = Math.max(0.1, num(span[1], node.start + 1) - node.start);
  }
  if (entry._rotation !== undefined) {
    node.objectMapping.set("transform.rotation", num(entry._rotation, 0));
  }
  const note = str(entry.note, "");
  if (note) (node as AnyNode & { note?: string }).note = note;
  if (entry.enabled !== undefined) node.visible = entry.enabled !== false;

  const setMapping = (key: string, value: number) => node.objectMapping.set(key, value);
  if (entry.spectrumHeight !== undefined) setMapping("behaviour.height", num(entry.spectrumHeight, 1) * 100);
  if (entry.scaleMultiplier !== undefined) {
    setMapping("transform.scaleMultiplier", num(entry.scaleMultiplier, 1) * 100);
    node.referenceScaleMultiplier = num(entry.scaleMultiplier, 1);
  }
  // Built-in presets may spin the whole item; ordinary project exports omit it.
  node.spinSpeed = num(entry.spinSpeed, 0);
  if (entry.scaleX !== undefined) setMapping("behaviour.scale", num(entry.scaleX, 1) * 100);
  if (entry.downSample !== undefined) setMapping("behaviour.downsample", Math.max(1, num(entry.downSample, 1)));
  if (entry.lineWidth !== undefined) setMapping("behaviour.lineWidth", num(entry.lineWidth, 3));
  if (entry.smoothingWidth !== undefined) setMapping("behaviour.smoothWidth", num(entry.smoothingWidth, 10));
  if (entry.smoothingPasses !== undefined) setMapping("behaviour.smoothPasses", num(entry.smoothingPasses, 4));
  if (entry.useGlobalShadow !== undefined) setMapping("channel.shadow", entry.useGlobalShadow ? 1 : 0);
  if (entry.useGlobalShadow === undefined) {
    // A preset document omits item-level defaults; the reference's Spectrum
    // item defaults to a 20px global shadow at full strength.
    setMapping("channel.shadow", 1);
    setMapping("channel.shadowScale", 100);
    setMapping("channel.shadowAlpha", 100);
    setMapping("channel.shadowSigmaX", 20);
    setMapping("channel.shadowSigmaY", 20);
  }
  if (entry.globalShadowScaling !== undefined) setMapping("channel.shadowScale", num(entry.globalShadowScaling, 1) * 100);
  if (entry.globalShadowAlpha !== undefined) setMapping("channel.shadowAlpha", num(entry.globalShadowAlpha, 1) * 100);
  if (entry.globalShadowSigmaX !== undefined) setMapping("channel.shadowSigmaX", num(entry.globalShadowSigmaX, 20));
  if (entry.globalShadowSigmaY !== undefined) setMapping("channel.shadowSigmaY", num(entry.globalShadowSigmaY, 20));
  if (entry.fillCircle !== undefined) setMapping("channel.fillCircle", entry.fillCircle ? 1 : 0);
  if (entry.clipCircle !== undefined) setMapping("channel.clipCircle", entry.clipCircle ? 1 : 0);
  if (entry.circleSize !== undefined) setMapping("channel.circleSize", num(entry.circleSize, 0.16) * 100);
  if (entry.clipImageToCircle !== undefined) setMapping("channel.circularImage", entry.clipImageToCircle ? 1 : 0);
  if (entry.imageSize !== undefined) setMapping("channel.imageSize", num(entry.imageSize, 1) * 100);
  if (typeof entry.circleColor === "string") node.circleColor = entry.circleColor;

  // Path-renderer inputs. The reference stores these on the Spectrum item and
  // applies them through `preScaling` / `drawSpectrumPoints`.
  node.customPath = str(entry.customPath, "");
  node.closeLine = entry.closeLine !== false;
  node.moveBack = Boolean(entry.moveBack);
  node.repeatPointsOnPath = entry.repeatPointsOnPath !== false;
  node.smoothStartAndEnd = entry.smoothStartAndEnd !== false;
  node.smoothingWidth = num(entry.smoothingWidth, 10);
  node.smoothingPasses = num(entry.smoothingPasses, 4);
  node.stretchToEnd = Boolean(entry.stretchToEnd);
  node.spacing = num(entry.spacing, 0);
  node.renderScale = num(entry.renderScale, 1);
  node.lineCap = str(entry.lineCap, "round");
  node.pathEffect = str(entry.pathEffect, "none");
  node.dashOffset = num(entry.dashOffset, 10);
  node.clipSize = num(entry.clipSize, 0.95);
  node.positionX = num(entry.positionX, 0);
  node.positionY = num(entry.positionY, 0);
  node.scaleX = num(entry.scaleX, 1);
  node.scaleY = num(entry.scaleY, 1);

  // A preset without an image must not keep the previous preset's texture.
  node.imageUrl = resolveAssetUrl(str(entry.imageSrc, "")) || null;

  if (options.pathRenderer) {
    // Everything uses the decompiled path renderer. Shader layers supply colour
    // through a GPU paint texture, which the path renderer masks exactly.
    node.pathMode = true;
  }

  return layers.length;
}

export function applyProjectExport(
  target: Project,
  raw: unknown,
  deps: ImportDeps,
): ImportReport {
  const root = asRecord(raw);
  const values = asRecord(root.values);
  const report: ImportReport = {
    name: "",
    nodes: 0,
    layers: 0,
    compositionLayers: 0,
    analyzers: 0,
    effects: 0,
    automations: 0,
    media: [],
    notes: [],
    skipped: [],
  };

  if (!root.values || !root.objects) {
    throw new Error("not a project export: missing objects/values");
  }

  // ------------------------------------------------------------------ project
  const projectValues = asRecord(values.Project);
  const webgl = asRecord(values.WebGLManager);
  target.name = str(projectValues.projectName, str(root.name, target.name));
  report.name = target.name;
  target.creatorNote = str(projectValues.creatorNote, target.creatorNote);
  target.globals = ["g1", "g2", "g3", "g4", "g5"].map((key) => num(webgl[key], 0));
  target.duration = num(projectValues.projectDuration, target.duration);
  target.fps = num(webgl.fps, target.fps);
  // The reference caches the track's maximum impact here; audio-impact
  // automations normalise their magnitude by it.
  target.audioImpactMax = num(asRecord(root.audioImpact).max, 0);
  const audioValues = asRecord(values.Audio);
  target.muted = audioValues.muted === true;
  // The reference stores `value` as 0..1; our project keeps 0..100. Older or
  // hand-written exports may already be percentages.
  const rawVolume = num(audioValues.value, 1);
  const volumePercent = rawVolume <= 1 ? rawVolume * 100 : rawVolume;
  target.volume = Math.max(0, Math.min(100, volumePercent));
  target.audioSettings = {
    bassBoost: num(audioValues.bassBoostAmount, target.audioSettings.bassBoost),
    frequency: num(audioValues.frequency, target.audioSettings.frequency),
    playbackRate: num(audioValues.playbackRate, target.audioSettings.playbackRate),
    attenuator: audioValues.attenuatorEnabled === true,
    additionalGainDb: num(audioValues.additionalGainDb, target.audioSettings.additionalGainDb),
    compressor: audioValues.compressorEnabled === true,
  };
  const [width, height] = str(webgl.resolution, "")
    .split("x")
    .map((part) => Number(part));
  if (width > 0 && height > 0) {
    target.width = width;
    target.height = height;
  }

  target.nodes = [];
  target.layers = [];
  target.automations = [];
  target.markers = [];
  target.effects = [];
  target.analyzers = [];

  // ---------------------------------------------------------------- analyzers
  for (const [id, rawValues] of Object.entries(values)) {
    if (!id.startsWith("analyzer:")) continue;
    const entry = asRecord(rawValues);
    const provider = str(entry.sampleProvider, "goertzel") === "filter bank"
      ? "filter bank"
      : "goertzel";
    target.analyzers.push(
      createAnalyzer(id, str(entry.name, "Analyzer"), {
        sampleProvider: provider as SampleProvider,
        outputMultiplier: num(entry.outputMultiplier, 50),
        sampleOutCount: num(entry.sampleOutCount, 64),
        audioDuration: num(entry.audioDuration, 200),
        audioOffset: num(entry.audioOffset, 0),
        frequencyRange: Array.isArray(entry.frequencyRange)
          ? [num(entry.frequencyRange[0], 20), num(entry.frequencyRange[1], 130)]
          : [20, 130],
        windowFunction: str(entry.windowFunction, "hann"),
        smoothingTimeConstant: num(entry.smoothingTimeConstant, 0),
        audioReactionAlignment: num(entry.audioReactionAlignment, -1),
        windowParameter: num(entry.windowParameter, 1),
        windowSkew: num(entry.windowSkew, 0),
        frequencyScale: str(entry.frequencyScale, "linear"),
        hzLinearFactor: num(entry.hzLinearFactor, 0.5),
        cqtResolution: num(entry.cqtResolution, 7),
        cqtWindowFunction: str(entry.cqtWindowFunction, "hann"),
        cqtWindowParameter: num(entry.cqtWindowParameter, 1),
        cqtWindowSkew: num(entry.cqtWindowSkew, 0),
        cqtBandwidth: num(entry.cqtBandwidth, 8),
        spectrumConstantQ: entry.spectrumConstantQ === true,
        perBinFrequencyTilt: num(entry.perBinFrequencyTilt, 0),
        perBandFrequencyTilt: num(entry.perBandFrequencyTilt, 0),
        perBandWeighting: str(entry.perBandWeighting, "a").toLowerCase(),
        perBandWeightingAmount: num(entry.perBandWeightingAmount, 0),
        downSample: entry.downSample !== false,
      }),
    );
  }
  // The reference lists analyzers in `audioAnalyzersOrder`, which is what the
  // inspector's "Audio analyzer" dropdown shows; iterating the value map gives
  // a different order (and the artist's "Scale"/"Shake"/"Particles" names end up
  // shuffled).
  const analyzerOrder = Array.isArray(root.audioAnalyzersOrder)
    ? (root.audioAnalyzersOrder as unknown[]).map((id) => String(id))
    : [];
  if (analyzerOrder.length) {
    const rank = new Map(analyzerOrder.map((id, index) => [id, index]));
    target.analyzers.sort(
      (left, right) =>
        (rank.get(left.id) ?? Number.MAX_SAFE_INTEGER) -
        (rank.get(right.id) ?? Number.MAX_SAFE_INTEGER),
    );
  }
  report.analyzers = target.analyzers.length;

  // -------------------------------------------------------------------- items
  const nodeByExportId = new Map<string, AnyNode>();
  // Only Spectrum stores `scaleMultiplier` as a percent controller; every other
  // item (text, lyrics) keeps the reference's raw factor on the node itself.
  const spectrumNodeIds = new Set<string>();

  for (const [id, rawValues] of Object.entries(values)) {
    if (!id.startsWith("item:")) continue;
    const entry = asRecord(rawValues);
    const type = str(entry.type, "");

    if (type === "Image") {
      const media = deps.createNode(NodeKind.Media, str(entry.name, "Image"));
      const span = Array.isArray(entry.time) ? entry.time : [];
      media.start = num(span[0], 0);
      media.duration = Math.max(0.1, num(span[1], media.start + 1) - media.start);
      media.visible = entry.enabled !== false;
      if (media instanceof MediaNode) {
        const mapped = (key: string, value: number): void => {
          media.objectMapping.set(key, value);
        };
        media.mirrorType = str(entry.mirrorType, "None");
        // The reference renders these through its controller surface: fit mode,
        // vignette and brightness are object-mapping values, not plain fields.
        mapped("channel.fitToScreen", entry.fitToScreen === false ? 0 : 1);
        mapped("effects.vignette", num(entry.vignette, 0) * 100);
        mapped("effects.brightnessMultiplier", num(entry.brightnessMultiplier, 0.2));
        applyReferenceTransform(media, entry);
        const red = num(entry["colorMult:red"], 1);
        const green = num(entry["colorMult:green"], 1);
        const blue = num(entry["colorMult:blue"], 1);
        media.colorMult = {
          r: red,
          g: green,
          b: blue,
          // The export writes the Image's colour-multiply alpha verbatim. A
          // stored 0 is a real "invisible" multiplier, not a missing default:
          // `watercolor-cave` keeps its EP cover at 0 for the whole timeline
          // (the reference frame at 00:45 shows only the shader stack, never
          // the artwork). Coercing 0 to 1 painted that cover over the frame.
          a: num(entry["colorMult:alpha"], 1),
        };
        media.colorAdd = {
          r: num(entry["colorAdd:red"], 0),
          g: num(entry["colorAdd:green"], 0),
          b: num(entry["colorAdd:blue"], 0),
          a: num(entry["colorAdd:alpha"], 0),
        };
        media.brightnessMultiplier = num(entry.brightnessMultiplier, 0.2);
        media.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
        // Reference Auto Background / Auto Cover Art preferences.
        media.objectMapping.set(
          "basics.autoBackground",
          entry.isBackground === true ? 1 : 0,
        );
        media.objectMapping.set(
          "basics.autoCoverArt",
          entry.isCoverArt === true ? 1 : 0,
        );
        if (red !== 1 || green !== 1 || blue !== 1) {
          const channel = (value: number): string =>
            Math.round(Math.max(0, Math.min(1, value)) * 255)
              .toString(16)
              .padStart(2, "0");
          media.tint = `#${channel(red)}${channel(green)}${channel(blue)}`;
        }
        const url = resolveAssetUrl(str(entry.src, ""));
        media.useLayerAsImage = entry.useLayerTexture === true;
        media.layerSource = str(entry.targetLayer, "");
        if (url) {
          report.media.push({ nodeId: media.id, url });
        } else if (str(entry.src, "")) {
          report.skipped.push({
            what: `${str(entry.name, "Image")} image`,
            reason: `unresolvable asset path (${str(entry.src, "")})`,
          });
        }
      }
      target.nodes.push(media);
      nodeByExportId.set(id, media);
      report.nodes += 1;
      continue;
    }

    if (type === "Particles") {
      const particles = deps.createNode(NodeKind.Particles, str(entry.name, "Particles"));
      if (!(particles instanceof ParticlesNode)) {
        report.skipped.push({ what: `${type} (${id})`, reason: "particle node unavailable" });
        continue;
      }
      const span = Array.isArray(entry.time) ? entry.time : [];
      particles.start = num(span[0], 0);
      particles.duration = Math.max(0.1, num(span[1], particles.start + 1) - particles.start);
      particles.visible = entry.enabled !== false;
      particles.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");

      const pair = (value: unknown, fallback: [number, number]): [number, number] =>
        Array.isArray(value) && value.length >= 2
          ? [num(value[0], fallback[0]), num(value[1], fallback[1])]
          : fallback;

      particles.instances = Math.max(1, Math.round(num(entry.instances, 1000)));
      particles.sizeRange = pair(entry.size, particles.sizeRange);
      particles.alphaRange = pair(entry.alpha, particles.alphaRange);
      particles.speedRange = pair(entry.speed, particles.speedRange);
      particles.phaseRange = pair(entry.phase, particles.phaseRange);
      particles.phaseAmplitude = pair(entry.phaseAmplitude, particles.phaseAmplitude);
      particles.phaseSpeedRange = pair(entry.phaseSpeed, particles.phaseSpeedRange);
      particles.timeToLiveRange = pair(entry.timeToLive, particles.timeToLiveRange);
      particles.directionX = pair(entry.directionX, particles.directionX);
      particles.directionY = pair(entry.directionY, particles.directionY);
      particles.directionZ = pair(entry.directionZ, particles.directionZ);
      particles.startPos.set(num(entry.startPosX, -45), num(entry.startPosY, -75), num(entry.startPosZ, -500));
      particles.endPos.set(num(entry.endPosX, 250), num(entry.endPosY, 75), num(entry.endPosZ, 500));
      particles.color = str(entry.color, "#ffffff");
      particles.mirror = entry.mirror !== false;
      particles.constantSize = entry.constantSize === true;
      // Reference `setValue` assigns a saved field (and fires `onValueChange`,
      // the only writer of the limit uniforms) only when it *differs* from the
      // constructor default. A project that stores the defaults (e.g. `chill`
      // with 5/500) therefore leaves the material's own limits (50/1000) in the
      // shader; pushing 500 made `length(gl_Position) Γëê 500` fall outside the
      // keep band and zeroed every particle.
      {
        const importLimit = <K extends "zLimit" | "zLimitGrace" | "backLimit" | "backLimitGrace">(
          key: K,
          fallback: number,
        ): void => {
          const value = num(entry[key], fallback);
          if (value !== fallback) {
            particles[key] = value;
            particles.limitOverrides[key] = true;
          }
        };
        importLimit("zLimit", 5);
        importLimit("zLimitGrace", 10);
        importLimit("backLimit", 500);
        importLimit("backLimitGrace", 10);
      }
      particles.impactMultiplier = num(entry.impactMultiplier, 3);
      particles.smoothingTimeConstant = num(entry.smoothingTimeConstant, 0.2);
      particles.globalAlpha = num(entry.globalAlpha, 1);
      particles.incrementWithTime = entry.incrementWithTime !== false;
      particles.timeIncrementMultiplier = num(entry.timeIncrementMultiplier, 0.3);
      particles.enableRandomSize = entry.enableRandomSize === true;
      particles.randomSizeSpeed = num(entry.randomSizeSpeed, 2);
      particles.enableRandomAlpha = entry.enableRandomAlpha !== false;
      particles.randomAlphaSpeed = num(entry.randomAlphaSpeed, 2);
      particles.enableRandomRotation = entry.enableRandomRotation === true;
      particles.randomRotationSpeed = num(entry.randomRotationSpeed, 2);
      particles.fadeBeginning = asRecord(entry["fadein:value"]).value !== false;
      particles.fadeEnd = asRecord(entry["fadeout:value"]).value !== false;
      particles.seed = str(entry.seed, "4982");
      particles.particleScale.set(
        num(entry["scale:x"], 1),
        num(entry["scale:y"], 1),
        num(entry["scale:z"], 1),
      );
      particles.particleOffset.set(
        num(entry["position:x"], 0),
        num(entry["position:y"], 0),
        num(entry["position:z"], 0),
      );
      // The reference serves this sprite from its own bundle, and falls back to
      // the same remote copy we ship as the node default if that fails.
      const image = resolveAssetUrl(str(entry.particleImage, ""));
      if (image) particles.particleImage = image;
      particles.rebuild();

      target.nodes.push(particles);
      nodeByExportId.set(id, particles);
      report.nodes += 1;
      continue;
    }

    const primitiveKind =
      type === "Cube"
        ? NodeKind.Cube
        : type === "Square"
          ? NodeKind.Square
          : type === "Plane"
            ? NodeKind.Plane
            : type === "PointLight"
              ? NodeKind.PointLight
              : null;
    if (primitiveKind) {
      const primitive = deps.createNode(primitiveKind, str(entry.name, type)) as PrimitiveNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      primitive.start = num(span[0], 0);
      primitive.duration = Math.max(0.1, num(span[1], primitive.start + 1) - primitive.start);
      primitive.visible = entry.enabled !== false;
      // Reference 3D layers use a fixed 1000-unit stage: `Layer.createCamera`
      // builds an orthographic camera from module 71's 1000 constant (half
      // height 500), primitives sit at their unit position, and `Plane` is
      // 1024 units with `z=-500`. Controllers store percent of the 2-unit
      // stage, so 1000 units map to 200.
      const pixelToPercent = 200 / 1000;
      // The reference's `f(x, y, true)` keeps positions the same physical
      // distance from the centre in either orientation: x carries the frame
      // aspect in landscape, y does in portrait (see MediaNode.sync).
      const frameAspect = target.width / Math.max(1, target.height);
      const landscape = frameAspect > 1;
      const xPercent = pixelToPercent * (landscape ? frameAspect : 1);
      const yPercent = pixelToPercent * (landscape ? 1 : frameAspect);
      const mappings: Record<string, number> = {
        "transform.x": num(entry["position:x"], 0) * xPercent,
        "transform.y": num(entry["position:y"], 0) * yPercent,
        "transform.z": num(entry["position:z"], 0) * pixelToPercent,
        "transform.rotX": num(entry["rotation:x"], 0),
        "transform.rotY": num(entry["rotation:y"], 0),
        "transform.rotZ": num(entry["rotation:z"], 0),
        "transform.scaleX": num(entry["scale:x"], 1) * 100,
        "transform.scaleY": num(entry["scale:y"], 1) * 100,
        "transform.scaleZ": num(entry["scale:z"], 1) * 100,
      };
      for (const [key, value] of Object.entries(mappings)) primitive.objectMapping.set(key, value);
      if (typeof entry.color === "string") primitive.color = entry.color;
      if (typeof entry.opacity === "number") {
        primitive.opacity = entry.opacity;
        // The controller reads `behaviour.opacity` (0..100); the exported
        // member is 0..1.
        primitive.objectMapping.set("behaviour.opacity", entry.opacity * 100);
      }
      if (typeof entry.boxWidth === "number") primitive.boxWidth = entry.boxWidth;
      if (typeof entry.boxHeight === "number") primitive.boxHeight = entry.boxHeight;
      if (typeof entry.intensity === "number") primitive.intensity = entry.intensity;
      if (typeof entry.distance === "number") primitive.distance = entry.distance;
      if (typeof entry.decay === "number") primitive.decay = entry.decay;
      target.nodes.push(primitive);
      nodeByExportId.set(id, primitive);
      report.nodes += 1;
      continue;
    }

    if (type === "Ground") {
      const ground = deps.createNode(NodeKind.Ground, str(entry.name, "Ground")) as GroundNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      ground.start = num(span[0], 0);
      ground.duration = Math.max(0.1, num(span[1], ground.start + 1) - ground.start);
      ground.visible = entry.enabled !== false;
      ground.multiplier = num(entry.multiplier, 1);
      ground.analyzerId = str(entry.audioAnalyzer, "") || null;
      // The reference stores the ground's pose on the item itself (module 1361:
      // `this.position.*` / `this.rotation.x`), including its rotation and
      // scale; importing only the position left every ground flat at 1x.
      applyReferenceTransform(ground, entry);
      target.nodes.push(ground);
      nodeByExportId.set(id, ground);
      report.nodes += 1;
      continue;
    }

    if (type === "ParticleTimeLine") {
      const timeline = deps.createNode(
        NodeKind.ParticleTimeLine,
        str(entry.name, "Timeline"),
      ) as ParticleTimeLineNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      timeline.start = num(span[0], 0);
      timeline.duration = Math.max(0.1, num(span[1], timeline.start + 1) - timeline.start);
      timeline.visible = entry.enabled !== false;
      timeline.customPath = str(entry.customPath, timeline.customPath);
      timeline.distanceDone = num(entry.distanceDone, timeline.distanceDone);
      timeline.maxTime = num(entry.maxTime, 4);
      timeline.nParticles = num(entry.nParticles, 2000);
      timeline.pointSize = num(entry.pointSize, 5);
      for (const axis of ["x", "y", "z"]) {
        timeline.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], timeline.readNumber(`transform.${axis}`)),
        );
      }
      target.nodes.push(timeline);
      nodeByExportId.set(id, timeline);
      report.nodes += 1;
      continue;
    }

    if (type === "Butterchurn") {
      const butter = deps.createNode(
        NodeKind.Butterchurn,
        str(entry.name, "Butterchurn"),
      ) as ButterchurnNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      butter.start = num(span[0], 0);
      butter.duration = Math.max(0.1, num(span[1], butter.start + 1) - butter.start);
      butter.visible = entry.enabled !== false;
      butter.src = resolveAssetUrl(str(entry.src, "")) || str(entry.src, "");
      butter.color = str(entry.color, "#ffffff");
      butter.opacity = num(entry.opacity, 1);
      butter.presetName = str(entry.presetName, "None");
      butter.blendTime = num(entry.blendTime, 1);
      butter.audioMultiplier = num(entry.audioMultiplier, 1);
      butter.updateSpeed = num(entry.updateSpeed, 1);
      butter.useAudioAnalyzer = entry.useAudioAnalyzer === true;
      butter.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
      butter.outputAA = entry.outputAA === true;
      butter.fitToScreen = entry.fitToScreen !== false;
      butter.width = num(entry.width, butter.width);
      butter.height = num(entry.height, butter.height);
      butter.matchToCanvas = entry.matchToCanvas !== false;
      butter.srcBlending = str(entry.srcBlending, "SrcAlpha");
      butter.dstBlending = str(entry.dstBlending, "OneMinusSrcAlpha");
      butter.blendEquation = str(entry.blendEquation, "Add");
      butter.renderPreset();
      for (const axis of ["x", "y", "z"]) {
        butter.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], butter.readNumber(`transform.${axis}`)),
        );
      }
      target.nodes.push(butter);
      nodeByExportId.set(id, butter);
      report.nodes += 1;
      continue;
    }

    if (type === "Video" || type === "WasmVideo" || type === "Video2") {
      const kind =
        type === "Video2"
          ? NodeKind.Video2
          : type === "WasmVideo"
            ? NodeKind.WasmVideo
            : NodeKind.Video;
      const video = deps.createNode(kind, str(entry.name, "Video")) as VideoNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      video.start = num(span[0], 0);
      video.duration = Math.max(0.1, num(span[1], video.start + 1) - video.start);
      video.visible = entry.enabled !== false;
      video.src = resolveAssetUrl(str(entry.src, "")) || str(entry.src, "");
      video.loadSource();
      video.loop = entry.loop !== false;
      video.fitToScreen = entry.fitToScreen !== false;
      video.playbackRate = num(entry.playbackRate, 1);
      video.alphaInterpretation = str(entry.alphaInterpretation, "straight");
      // Reference `Video.setScaling` fits the quad from the item's `aspect`
      // member (`o = fitToScreen ? canvasAspect / aspect : 1`; mesh
      // `(aspect * o, o)`), and the export writes it. Honouring it is what
      // keeps `new-wayve`'s Background video at the reference's 0.9 quad: the
      // local transcode is square, and refreshing from videoWidth/videoHeight
      // drew a circular ring where the reference frame's is 1.106x taller.
      const authoredAspect = num(entry.aspect, 0);
      if (Number.isFinite(authoredAspect) && authoredAspect > 0) {
        video.authoredAspect = authoredAspect;
        video.aspect = authoredAspect;
      }
      // Reference module 253 exposes NO/NORMAL/ADD/MULTIPLY/SUBTRACT on Video.
      // Dropping this made retro's additive VHS overlay composite normal and
      // cover the shader background with black.
      video.blending = str(entry.blending, "normal").toLowerCase();
      video.sourceIn = Math.max(0, num(entry.sourceIn, 0));
      for (const axis of ["x", "y", "z"]) {
        video.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], video.readNumber(`transform.${axis}`)),
        );
      }
      // The reference video's uniform `scale` multiplies the fitted quad; the
      // export's 0.6 (or 1) carries the YouTube-style letterbox sizing.
      const videoScale = num(entry.scale, 1);
      if (Number.isFinite(videoScale) && videoScale > 0) {
        video.objectMapping.set("transform.scaleX", videoScale * 100);
        video.objectMapping.set("transform.scaleY", videoScale * 100);
        video.objectMapping.set("transform.scaleZ", videoScale * 100);
      }
      target.nodes.push(video);
      nodeByExportId.set(id, video);
      report.nodes += 1;
      continue;
    }

    if (type === "SkottieItem") {
      const skottie = deps.createNode(NodeKind.Skottie, str(entry.name, "Skottie")) as SkottieNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      skottie.start = num(span[0], 0);
      skottie.duration = Math.max(0.1, num(span[1], skottie.start + 1) - skottie.start);
      skottie.visible = entry.enabled !== false;
      for (const axis of ["x", "y", "z"]) {
        skottie.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], skottie.readNumber(`transform.${axis}`)),
        );
      }
      target.nodes.push(skottie);
      nodeByExportId.set(id, skottie);
      report.nodes += 1;
      continue;
    }

    if (type === "ShaderItem") {
      const shader = deps.createNode(NodeKind.ShaderItem, str(entry.name, "Shader Item")) as ShaderItemNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      shader.start = num(span[0], 0);
      shader.duration = Math.max(0.1, num(span[1], shader.start + 1) - shader.start);
      shader.visible = entry.enabled !== false;
      shader.src = resolveAssetUrl(str(entry.src, "")) || str(entry.src, "");
      if (typeof entry.fragInput === "string" && entry.fragInput) shader.fragInput = entry.fragInput;
      if (typeof entry.vertInput === "string" && entry.vertInput) shader.vertInput = entry.vertInput;
      shader.side = str(entry.side, "double") as typeof shader.side;
      shader.fitToScreen = entry.fitToScreen !== false;
      shader.targetLayer = str(entry.targetLayer, "");
      shader.targetLayer2 = str(entry.targetLayer2, "");
      shader.targetLayer3 = str(entry.targetLayer3, "");
      shader.targetLayer4 = str(entry.targetLayer4, "");
      shader.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
      shader.value = num(entry.value, 0);
      shader.value2 = num(entry.value2, 0);
      shader.value3 = num(entry.value3, 0);
      shader.value4 = num(entry.value4, 0);
      shader.value5 = num(entry.value5, 0);
      shader.value6 = num(entry.value6, 0);
      shader.srcBlending = str(entry.srcBlending, "SrcAlpha");
      shader.dstBlending = str(entry.dstBlending, "OneMinusSrcAlpha");
      shader.blendEquation = str(entry.blendEquation, "Add");
      applyReferenceTransform(shader, entry);
      target.nodes.push(shader);
      nodeByExportId.set(id, shader);
      report.nodes += 1;
      continue;
    }

    if (type === "Confetti") {
      const confetti = deps.createNode(NodeKind.Confetti, str(entry.name, "Confetti")) as ConfettiNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      confetti.start = num(span[0], 0);
      confetti.duration = Math.max(0.1, num(span[1], confetti.start + 1) - confetti.start);
      confetti.visible = entry.enabled !== false;
      confetti.width = num(entry.width, 1000);
      confetti.height = num(entry.height, 1000);
      confetti.depth = num(entry.depth, 1000);
      confetti.fall = num(entry.fall, 2);
      confetti.swirl = num(entry.swirl, 1);
      confetti.step = num(entry.step, 100);
      confetti.flakeCount = num(entry.flakeCount, 1000);
      confetti.shape = str(entry.shape, "hexagon");
      confetti.hemisphereSkyColor = str(entry.hemisphereSkyColor, "#114417");
      confetti.hemisphereGroundColor = str(entry.hemisphereGroundColor, "#ffffff");
      confetti.hemisphereSkyIntensity = num(entry.hemisphereSkyIntensity, 0.3);
      confetti.light2Color = str(entry.light2Color, "#ff0000");
      confetti.light3Color = str(entry.light3Color, "#00ff00");
      confetti.light4Color = str(entry.light4Color, "#3333ff");
      for (const axis of ["x", "y", "z"]) {
        confetti.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], confetti.readNumber(`transform.${axis}`)),
        );
      }
      target.nodes.push(confetti);
      nodeByExportId.set(id, confetti);
      report.nodes += 1;
      continue;
    }

    if (type === "ParticleSystem") {
      const system = deps.createNode(
        NodeKind.ParticleSystem,
        str(entry.name, "Particle System"),
      ) as ParticleSystemNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      system.start = num(span[0], 0);
      system.duration = Math.max(0.1, num(span[1], system.start + 1) - system.start);
      system.visible = entry.enabled !== false;
      system.instances = num(entry.instances, 1200);
      system.timeToLive = num(entry.timeToLive, 5);
      system.origin = str(entry.origin, "Point");
      system.baseSpeed = num(entry.baseSpeed, 0.3);
      system.reactiveScaling = num(entry.reactiveScaling, 1);
      system.pointSize = num(entry.pointSize, 1);
      system.alphaMult = num(entry.alphaMult, 1);
      for (const axis of ["x", "y", "z"]) {
        system.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], system.readNumber(`transform.${axis}`)),
        );
      }
      target.nodes.push(system);
      nodeByExportId.set(id, system);
      report.nodes += 1;
      continue;
    }

    if (type === "InstancedParticleSystem") {
      const system = deps.createNode(
        NodeKind.InstancedParticleSystem,
        str(entry.name, "Instanced Particle System"),
      ) as InstancedParticleSystemNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      system.start = num(span[0], 0);
      system.duration = Math.max(0.1, num(span[1], system.start + 1) - system.start);
      system.visible = entry.enabled !== false;
      for (const axis of ["x", "y", "z"]) {
        system.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], system.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        system.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        system.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(system);
      nodeByExportId.set(id, system);
      report.nodes += 1;
      continue;
    }

    if (type === "SphericalField" || type === "Spherical Field") {
      const field = deps.createNode(
        NodeKind.SphericalField,
        str(entry.name, "Spherical Field"),
      ) as SphericalFieldNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      field.start = num(span[0], 0);
      field.duration = Math.max(0.1, num(span[1], field.start + 1) - field.start);
      field.visible = entry.enabled !== false;
      field.color = str(entry.color, "#00ffff");
      field.opacity = num(entry.opacity, 0.5);
      field.size = num(entry.size, 2.5);
      field.w = num(entry.w, 2);
      field.h = num(entry.h, 2);
      field.divX = num(entry.divX, 100);
      field.divY = num(entry.divY, 100);
      field.radius = num(entry.radius, 250);
      field.strength = num(entry.strength, 100);
      field.fractScale = num(entry.fractScale, 1.8);
      field.flowX = num(entry.flowX, 1);
      field.flowY = num(entry.flowY, 2);
      field.evolution = num(entry.evolution, 1.5);
      field.displace = num(entry.displace, 30);
      field.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
      field.squishTo2D = entry.squishTo2D !== false;
      field.premultiply = entry.premultiply !== false;
      field.constantAudioFactor = num(entry.constantAudioFactor, 0);
      field.audioReaction = num(entry.audioReaction, 1);
      for (const axis of ["x", "y", "z"]) {
        field.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], field.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        field.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        field.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(field);
      nodeByExportId.set(id, field);
      report.nodes += 1;
      continue;
    }

    if (type === "LineBed") {
      const bed = deps.createNode(NodeKind.LineBed, str(entry.name, "Line Bed")) as LineBedNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      bed.start = num(span[0], 0);
      bed.duration = Math.max(0.1, num(span[1], bed.start + 1) - bed.start);
      bed.visible = entry.enabled !== false;
      bed.nrLines = num(entry.nrLines, 40);
      bed.size = num(entry.size, 40);
      bed.lineLength = num(entry.lineLength, 10);
      bed.spacing = num(entry.spacing, 10);
      bed.amplitude = num(entry.amplitude, 10);
      bed.startColor = str(entry.startColor, "#4f2eb2");
      bed.endColor = str(entry.endColor, "#ffffff");
      bed.colorSplit = num(entry.colorSplit, 0);
      bed.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
      bed.speed = num(entry.speed, 1);
      for (const axis of ["x", "y", "z"]) {
        bed.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], bed.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        bed.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        bed.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(bed);
      nodeByExportId.set(id, bed);
      report.nodes += 1;
      continue;
    }

    if (type === "Model") {
      const model = deps.createNode(NodeKind.Model, str(entry.name, "Model")) as ModelNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      model.start = num(span[0], 0);
      model.duration = Math.max(0.1, num(span[1], model.start + 1) - model.start);
      model.visible = entry.enabled !== false;
      model.color = str(entry.color, "#ffffff");
      model.opacity = num(entry.opacity, 1);
      model.modelSrc = resolveAssetUrl(str(entry.modelSrc, "")) || str(entry.modelSrc, "");
      for (const axis of ["x", "y", "z"]) {
        model.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], model.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        model.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        model.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(model);
      nodeByExportId.set(id, model);
      report.nodes += 1;
      continue;
    }

    if (type === "ParticleLines") {
      const lines = deps.createNode(
        NodeKind.ParticleLines,
        str(entry.name, "Particle Lines"),
      ) as ParticleLinesNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      lines.start = num(span[0], 0);
      lines.duration = Math.max(0.1, num(span[1], lines.start + 1) - lines.start);
      lines.visible = entry.enabled !== false;
      lines.frequency = num(entry.frequency, 5);
      lines.maxNrLines = num(entry.maxNrLines, 20);
      lines.mirror = entry.mirror === true;
      lines.opacity = num(entry.opacity, 1);
      lines.color = str(entry.color, "#ffffff");
      lines.width = num(entry.width, 3);
      lines.scale = num(entry._scale, 15);
      lines.nrPoints = num(entry.nrPoints, 5);
      lines.nrPrecisionPoints = num(entry.nrPrecisionPoints, 300);
      lines.lengthMult = num(entry.lengthMult, 1);
      lines.visibleLengthMult = num(entry.visibleLengthMult, 0.15);
      lines.speedMult = num(entry.speedMult, 1);
      lines.speedAmplitude = num(entry.speedAmplitude, 0.73);
      lines.turbulenceAmt = num(entry.turbulenceAmt, 2);
      const range = (value: unknown, fallback: [number, number]): [number, number] => {
        if (!Array.isArray(value) || value.length < 2) return fallback;
        return [num(value[0], fallback[0]), num(value[1], fallback[1])];
      };
      lines.lengthRange = range(entry.length, [8, 15]);
      lines.visibleLengthRange = range(entry.visibleLength, [0.05, 0.2]);
      lines.speedRange = range(entry.speed, [0.4, 0.8]);
      lines.originX = range(entry.originX, [0, 0]);
      lines.originY = range(entry.originY, [0, 0]);
      lines.originZ = range(entry.originZ, [0, 0]);
      lines.directionX = range(entry.directionX, [-0.1, 0.1]);
      lines.directionY = range(entry.directionY, [-0.1, 0.1]);
      lines.directionZ = range(entry.directionZ, [0, 0.8]);
      for (const axis of ["x", "y", "z"]) {
        lines.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], lines.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        lines.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        lines.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(lines);
      nodeByExportId.set(id, lines);
      report.nodes += 1;
      continue;
    }

    if (type === "AudioWave") {
      const wave = deps.createNode(NodeKind.AudioWave, str(entry.name, "Audio wave")) as AudioWaveNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      wave.start = num(span[0], 0);
      wave.duration = Math.max(0.1, num(span[1], wave.start + 1) - wave.start);
      wave.visible = entry.enabled !== false;
      wave.amplitude = num(entry.amplitude, 1);
      wave.extent = num(entry.extent, 30);
      wave.width = num(entry.width, 40);
      wave.height = num(entry.height, 2);
      wave.timeMultiplier = num(entry.timeMultiplier, 1);
      wave.color = str(entry.color, "#ffffff");
      wave.downsample = str(entry.downsample, "1");
      wave.audioDuration = num(entry.audioDuration, 500);
      wave.takeEvery = str(entry.takeEvery, "1");
      wave.absolute = entry.absolute === true;
      wave.drawType = str(entry.drawType, "normal");
      wave.lineType = str(entry.lineType, "Tube");
      wave.lineThickness = num(entry.lineThickness, 0.4);
      wave.bufferKeepAmount = num(entry.bufferKeepAmount, 1);
      wave.useAudioAnalyzer = entry.useAudioAnalyzer === true;
      wave.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
      wave.syncToDominant = entry.syncToDominant === true;
      wave.periodsVisible = str(entry.periodsVisible, "1");
      if (Array.isArray(entry.analyserFreqRange)) {
        wave.analyserFreqRange = [
          num(entry.analyserFreqRange[0], 20),
          num(entry.analyserFreqRange[1], 130),
        ];
      }
      for (const axis of ["x", "y", "z"]) {
        wave.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], wave.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        wave.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        wave.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(wave);
      nodeByExportId.set(id, wave);
      report.nodes += 1;
      continue;
    }

    if (type === "BasicSpectrumBars") {
      const bars = deps.createNode(
        NodeKind.BasicSpectrumBars,
        str(entry.name, "3D Bars"),
      ) as BasicSpectrumBarsNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      bars.start = num(span[0], 0);
      bars.duration = Math.max(0.1, num(span[1], bars.start + 1) - bars.start);
      bars.visible = entry.enabled !== false;
      bars.spacing = num(entry.spacing, 2);
      bars.color = str(entry.color, "#ffffff");
      bars.audioAnalyzer = str(entry.audioAnalyzer, "analyzer_default");
      for (const axis of ["x", "y", "z"]) {
        bars.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], bars.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        bars.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
        bars.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], 1) * 100,
        );
      }
      target.nodes.push(bars);
      nodeByExportId.set(id, bars);
      report.nodes += 1;
      continue;
    }

    if (type === "Lyrics") {
      const lyrics = deps.createNode(NodeKind.Lyrics, str(entry.name, "Lyrics")) as LyricsNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      lyrics.start = num(span[0], 0);
      lyrics.duration = Math.max(0.1, num(span[1], lyrics.start + 1) - lyrics.start);
      lyrics.visible = entry.enabled !== false;
      lyrics.textValue = str(entry.text, "");
      lyrics.src = resolveAssetUrl(str(entry.src, "")) || str(entry.src, "");
      lyrics.color = str(entry.color, "#ffffff");
      lyrics.alpha = num(entry.alpha, 1);
      lyrics.antiAliasing = entry.antiAliasing !== false;
      lyrics.textSize = num(entry.textSize, 60);
      lyrics.timeFormat = str(entry.timeFormat, "mm:ss");
      lyrics.timeDecimals = num(entry.timeDecimals, 2);
      lyrics.drawTime = entry.drawTime === true;
      lyrics.textAlign = str(entry.textAlign, "center") as typeof lyrics.textAlign;
      lyrics.textAlignV = str(entry.textAlignV, "middle") as typeof lyrics.textAlignV;
      lyrics.textBaseline = str(entry.textBaseline, "bottom") as typeof lyrics.textBaseline;
      lyrics.textTiming = str(entry.textTiming, "word");
      lyrics.offsetLine = num(entry.offsetLine, 0);
      lyrics.timeMultiplier = num(entry.timeMultiplier, 1);
      lyrics.font = str(entry.font, "SourceSansPro");
      lyrics.positionX = num(entry.positionX, 0);
      lyrics.positionY = num(entry.positionY, 0);
      lyrics.scaleX = num(entry.scaleX, 1);
      lyrics.scaleY = num(entry.scaleY, 1);
      lyrics.scaleMultiplier = num(entry.scaleMultiplier, 1);
      lyrics.showBoundingBox = entry.showBoundingBox === true;
      lyrics.textWidth = num(entry.textWidth, 850);
      lyrics.textHeight = num(entry.textHeight, 500);
      lyrics.fontStyle = str(entry.fontStyle, "normal");
      lyrics.fontWeight = num(entry.fontWeight, 400);
      lyrics.rotation = num(entry._rotation, num(entry.rotation, 0));
      lyrics.textJustify = entry.textJustify === true;
      lyrics.alphaEnabled = entry.alphaEnabled === true;
      lyrics.scaleEnabled = entry.scaleEnabled === true;
      lyrics.posXEnabled = entry.posXEnabled === true;
      lyrics.posYEnabled = entry.posYEnabled === true;
      lyrics.blurEnabled = entry.blurEnabled === true;
      lyrics.liquidEnabled = entry.liquidEnabled === true;
      lyrics.distortionEnabled = entry.distortionEnabled === true;
      lyrics.shakeEnabled = entry.shakeEnabled === true;
      lyrics.useMotionBlur = entry.useMotionBlur !== false;
      lyrics.motionBlurIterations = num(entry.motionBlurIterations, 20);
      lyrics.motionBlurLength = num(entry.motionBlurLength, 10);
      lyrics.motionExaggeration = num(entry.motionExaggeration, 0.5);
      const shadow = (entry.dropShadow ?? {}) as Record<string, unknown>;
      lyrics.dropShadow = {
        enableShadow: Boolean(entry.enableShadow ?? shadow.enableShadow ?? false),
        shadowColor: str(entry.shadowColor ?? shadow.shadowColor, "#000000"),
        shadowOffsetX: num(entry.shadowOffsetX ?? shadow.shadowOffsetX, 4),
        shadowOffsetY: num(entry.shadowOffsetY ?? shadow.shadowOffsetY, 4),
        shadowBlur: num(entry.shadowBlur ?? shadow.shadowBlur, 1),
      };
      const outline = (entry.outlineDropShadow ?? {}) as Record<string, unknown>;
      lyrics.outlineDropShadow = {
        enableOutline: Boolean(entry.enableOutline ?? outline.enableOutline ?? false),
        outlineColor: str(entry.outlineColor ?? outline.outlineColor, "#000000"),
        outlineOffsetX: num(entry.outlineOffsetX ?? outline.outlineOffsetX, 0),
        outlineOffsetY: num(entry.outlineOffsetY ?? outline.outlineOffsetY, 0),
        outlineExtent: num(entry.outlineExtent ?? outline.outlineExtent, 1),
        outlineBlur: num(entry.outlineBlur ?? outline.outlineBlur, 0),
        outlineHighPrecision: Boolean(
          entry.outlineHighPrecision ?? outline.outlineHighPrecision ?? false,
        ),
      };
      if (Array.isArray(entry.lyricsMapping)) {
        lyrics.lyricsMapping = (entry.lyricsMapping as Array<Record<string, unknown>>)
          .filter((line) => typeof line.start === "number" && typeof line.text === "string")
          .map((line) => ({
            start: Number(line.start),
            end: Number(line.end ?? Number(line.start) + 1),
            text: String(line.text),
          }));
      } else if (lyrics.src) {
        void lyrics.loadLyrics();
      }
      void lyrics.loadFont();
      target.nodes.push(lyrics);
      nodeByExportId.set(id, lyrics);
      report.nodes += 1;
      continue;
    }

    if (type === "AnimatedText") {
      const text = deps.createNode(NodeKind.AnimatedText, str(entry.name, "Animated Text")) as AnimatedTextNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      text.start = num(span[0], 0);
      text.duration = Math.max(0.1, num(span[1], text.start + 1) - text.start);
      text.visible = entry.enabled !== false;
      text.textValue = str(entry.text, "Hello, I'm AnimatedText");
      text.color = str(entry.color, "#d478ff");
      text.animationDuration = num(entry.duration, 2);
      text.useCustomDuration = entry.useCustomDuration === true;
      text.align = str(entry.align, "center") as typeof text.align;
      text.width = num(entry.width, 600);
      text.scaleMultiplier = num(entry.scaleMultiplier, 0.05);
      text.showBoundingBox = entry.showBoundingBox === true;
      text.letterSpacing = num(entry.letterSpacing, 0);
      text.useReactiveAlpha = entry.useReactiveAlpha === true;
      for (const axis of ["x", "y", "z"]) {
        text.objectMapping.set(`transform.${axis}`, num(entry[`position:${axis}`], 0));
      }
      for (const axis of ["x", "y", "z"]) {
        text.objectMapping.set(`transform.rot${axis.toUpperCase()}`, num(entry[`rotation:${axis}`], 0));
      }
      for (const axis of ["x", "y", "z"]) {
        text.objectMapping.set(`transform.scale${axis.toUpperCase()}`, num(entry[`scale:${axis}`], 1) * 100);
      }
      text.rebuildGeometry(true);
      target.nodes.push(text);
      nodeByExportId.set(id, text);
      report.nodes += 1;
      continue;
    }

    if (type === "SkiaText") {
      const text = deps.createNode(NodeKind.SkiaText, str(entry.name, "Text")) as SkiaTextNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      text.start = num(span[0], 0);
      text.duration = Math.max(0.1, num(span[1], text.start + 1) - text.start);
      text.visible = entry.enabled !== false;
      text.textValue = str(entry.text, "Text");
      text.color = str(entry.color, "#ffffff");
      text.alpha = num(entry.alpha, 1);
      text.antiAliasing = entry.antiAliasing !== false;
      text.textSize = num(entry.textSize, 60);
      text.timeFormat = str(entry.timeFormat, "mm:ss");
      text.timeDecimals = num(entry.timeDecimals, 2);
      text.drawTime = entry.drawTime === true;
      text.drawTimeCountdown = entry.drawTimeCountdown === true;
      text.textAlign = str(entry.textAlign, "center") as typeof text.textAlign;
      text.textAlignV = str(entry.textAlignV, "middle") as typeof text.textAlignV;
      text.textBaseline = str(entry.textBaseline, "bottom") as typeof text.textBaseline;
      text.font = str(entry.font, "SourceSansPro");
      text.positionX = num(entry.positionX, 0);
      text.positionY = num(entry.positionY, 0);
      text.scaleX = num(entry.scaleX, 1);
      text.scaleY = num(entry.scaleY, 1);
      text.scaleMultiplier = num(entry.scaleMultiplier, 1);
      text.showBoundingBox = entry.showBoundingBox === true;
      text.textWidth = num(entry.textWidth, 850);
      text.textHeight = num(entry.textHeight, 500);
      text.fontStyle = str(entry.fontStyle, "normal");
      text.fontWeight = num(entry.fontWeight, 400);
      text.rotation = num(entry._rotation, num(entry.rotation, 0));
      text.projectName = str(entry.projectName, "");
      text.audioName = str(entry.audioName, "");
      text.textJustify = entry.textJustify === true;
      const shadow = (entry.dropShadow ?? {}) as Record<string, unknown>;
      text.dropShadow = {
        enableShadow: Boolean(entry.enableShadow ?? shadow.enableShadow ?? false),
        shadowColor: str(entry.shadowColor ?? shadow.shadowColor, "#000000"),
        shadowOffsetX: num(entry.shadowOffsetX ?? shadow.shadowOffsetX, 4),
        shadowOffsetY: num(entry.shadowOffsetY ?? shadow.shadowOffsetY, 4),
        shadowBlur: num(entry.shadowBlur ?? shadow.shadowBlur, 1),
      };
      const outline = (entry.outlineDropShadow ?? {}) as Record<string, unknown>;
      text.outlineDropShadow = {
        enableOutline: Boolean(entry.enableOutline ?? outline.enableOutline ?? false),
        outlineColor: str(entry.outlineColor ?? outline.outlineColor, "#000000"),
        outlineOffsetX: num(entry.outlineOffsetX ?? outline.outlineOffsetX, 0),
        outlineOffsetY: num(entry.outlineOffsetY ?? outline.outlineOffsetY, 0),
        outlineExtent: num(entry.outlineExtent ?? outline.outlineExtent, 1),
        outlineBlur: num(entry.outlineBlur ?? outline.outlineBlur, 0),
        outlineHighPrecision: Boolean(
          entry.outlineHighPrecision ?? outline.outlineHighPrecision ?? false,
        ),
      };
      void text.loadFont();
      target.nodes.push(text);
      nodeByExportId.set(id, text);
      report.nodes += 1;
      continue;
    }

    if (type === "Noise") {
      const noise = deps.createNode(NodeKind.Noise, str(entry.name, "Noise")) as NoiseNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      noise.start = num(span[0], 0);
      noise.duration = Math.max(0.1, num(span[1], noise.start + 1) - noise.start);
      noise.visible = entry.enabled !== false;
      noise.noiseType = str(entry.noiseType, "simplex3D") as typeof noise.noiseType;
      noise.frequency = num(entry.frequency, 10);
      noise.amplitude = num(entry.amplitude, 1);
      noise.octaves = num(entry.octaves, 10);
      noise.lacunarity = num(entry.lacunarity, 2);
      noise.gain = num(entry.gain, 0.5);
      noise.contrast = num(entry.contrast, 0.5);
      noise.brightness = num(entry.brightness, 0.5);
      noise.offsetX = num(entry.offsetX, 0);
      noise.offsetY = num(entry.offsetY, 0);
      noise.parallax = entry.parallax === true;
      noise.parallaxScale = num(entry.parallaxScale, 1);
      noise.animate = entry.animate !== false;
      noise.evolution = num(entry.evolution, 0);
      noise.animateSpeed = num(entry.animateSpeed, 1);
      noise.discretize = entry.discretize === true;
      noise.discretizeStep = num(entry.discretizeStep, 0.5);
      noise.psrdPeriodX = num(entry.psrdPeriodX, 2);
      noise.psrdPeriodY = num(entry.psrdPeriodY, 2);
      noise.psrdRotation = num(entry.psrdRotation, 0);
      noise.timeOffset = num(entry.timeOffset, 0);
      noise.opacity = num(entry.opacity, 1);
      noise.srcBlending = str(entry.srcBlending, "SrcAlpha");
      noise.dstBlending = str(entry.dstBlending, "OneMinusSrcAlpha");
      noise.blendEquation = str(entry.blendEquation, "Add");
      noise.setNoiseType(noise.noiseType);
      for (const axis of ["x", "y", "z"]) {
        noise.objectMapping.set(
          `transform.${axis}`,
          num(entry[`position:${axis}`], noise.readNumber(`transform.${axis}`)),
        );
      }
      for (const axis of ["x", "y", "z"]) {
        noise.objectMapping.set(
          `transform.scale${axis.toUpperCase()}`,
          num(entry[`scale:${axis}`], noise.readNumber(`transform.scale${axis.toUpperCase()}`) / 100) * 100,
        );
      }
      target.nodes.push(noise);
      nodeByExportId.set(id, noise);
      report.nodes += 1;
      continue;
    }

    if (type === "Logo") {
      const logo = deps.createNode(NodeKind.Logo, str(entry.name, "Logo")) as LogoNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      logo.start = num(span[0], 0);
      logo.duration = Math.max(0.1, num(span[1], logo.start + 1) - logo.start);
      logo.visible = entry.enabled !== false;
      const imageSrc = resolveAssetUrl(str(entry.imageSrc, ""));
      if (imageSrc) logo.imageUrl = imageSrc;
      logo.matPositionX = num(entry.matPositionX, 0);
      logo.matPositionY = num(entry.matPositionY, 0);
      logo.matScaleX = num(entry.matScaleX, 1);
      logo.matScaleY = num(entry.matScaleY, 1);
      logo.scaleMult = num(entry.scaleMult, 1);
      logo.rotation = num(entry.matRotation, 0);
      logo.circleCutoff = num(entry.circleCutoff, 1);
      logo.textureWrap = str(entry.textureWrap, "Discard");
      logo.width = num(entry.width, 500);
      logo.height = num(entry.height, 500);
      for (const axis of ["x", "y", "z"]) {
        logo.objectMapping.set(`transform.${axis}`, num(entry[`position:${axis}`], 0));
      }
      logo.objectMapping.set("transform.scaleX", num(entry["scale:x"], 1) * 100);
      logo.objectMapping.set("transform.scaleY", num(entry["scale:y"], 1) * 100);
      target.nodes.push(logo);
      nodeByExportId.set(id, logo);
      report.nodes += 1;
      continue;
    }

    if (type === "ProgressBar") {
      const bar = deps.createNode(NodeKind.ProgressBar, str(entry.name, "Progress Bar")) as ProgressBarNode;
      const span = Array.isArray(entry.time) ? entry.time : [];
      bar.start = num(span[0], 0);
      bar.duration = Math.max(0.1, num(span[1], bar.start + 1) - bar.start);
      bar.visible = entry.enabled !== false;
      const assign = <K extends keyof ProgressBarNode>(key: K, value: unknown) => {
        if (value !== undefined) (bar as unknown as Record<string, unknown>)[key as string] = value;
      };
      assign("barType", str(entry.barType, "Line"));
      assign("lineDirection", str(entry.lineDirection, "Left to Right"));
      assign("circleDirection", str(entry.circleDirection, "Clockwise"));
      assign("autoProgress", entry.autoProgress !== false);
      assign("manualProgress", num(entry.manualProgress, 0.5));
      assign("fgColor", str(entry.fgColor, "#ffffff"));
      assign("bgColor", str(entry.bgColor, "#444444"));
      assign("fgOpacity", num(entry.fgOpacity, 1));
      assign("bgOpacity", num(entry.bgOpacity, 0.35));
      assign("length", num(entry.length, 800));
      assign("thickness", num(entry.thickness, 40));
      assign("radius", num(entry.radius, 300));
      assign("cornerRadius", num(entry.cornerRadius, 20));
      assign("circleStartAngle", num(entry.circleStartAngle, 0));
      assign("segments", num(entry.segments, 1));
      assign("gap", num(entry.gap, 5));
      assign("continuousSegments", entry.continuousSegments === true);
      assign("skipSegmentGapsDuringProgress", entry.skipSegmentGapsDuringProgress === true);
      assign("circleConsistentGapThickness", entry.circleConsistentGapThickness === true);
      for (const axis of ["x", "y", "z"]) {
        bar.objectMapping.set(`transform.${axis}`, num(entry[`position:${axis}`], 0));
      }
      bar.objectMapping.set("transform.scaleX", num(entry["scale:x"], 1) * 100);
      bar.objectMapping.set("transform.scaleY", num(entry["scale:y"], 1) * 100);
      target.nodes.push(bar);
      nodeByExportId.set(id, bar);
      report.nodes += 1;
      continue;
    }

    if (type !== "Spectrum") {
      report.skipped.push({ what: `${type || "item"} (${id})`, reason: "item type not implemented" });
      continue;
    }

    const node = deps.createNode(NodeKind.Effects, str(entry.name, "Spectrum")) as SpectrumNode;
    // One mapping for both preset application and whole-project import.
    report.layers += applySpectrumExport(node, entry, { pathRenderer: true });

    const rawImage = str(entry.imageSrc, "");
    if (rawImage && !resolveAssetUrl(rawImage)) {
      report.skipped.push({
        what: `${str(entry.name, "Spectrum")} image`,
        reason: `unresolvable asset path (${rawImage})`,
      });
    }

    target.nodes.push(node);
    nodeByExportId.set(id, node);
    spectrumNodeIds.add(node.id);
    report.nodes += 1;
  }

  // Timeline rows: the export stores the reference's `rowIndex` per item.
  for (const [id, node] of nodeByExportId) {
    const entry = asRecord(values[id]);
    if (entry.rowIndex !== undefined) {
      node.trackRow = Math.max(0, Math.round(num(entry.rowIndex, 0)));
    }
  }

  // ------------------------------------------------------- composition layers
  for (const [id, rawValues] of Object.entries(values)) {
    if (!id.startsWith("layer:")) continue;
    const entry = asRecord(rawValues);
    const object = asRecord(asRecord(root.objects)[id]);
    const children = Array.isArray(object.children) ? object.children.map(String) : [];
    const nodeIds = children
      .map((childId) => nodeByExportId.get(childId)?.id)
      .filter((nodeId): nodeId is string => Boolean(nodeId));
    target.layers.push({
      id,
      name: str(entry.name, "Layer"),
      nodeIds,
      enabled: entry.enabled !== false,
      renderToBuffer: entry.renderToBuffer === true,
      audioAnalyzer: str(entry.audioAnalyzer, "") || null,
      camera: (() => {
        const type = str(entry.cameraType, "").toLowerCase();
        if (type === "perspective") {
          return {
            type: "Perspective" as const,
            fov: num(entry.fov, 45),
            near: num(entry.nearPlane, 1),
            far: num(entry.farPlane, 1000),
          };
        }
        if (type === "orthographic") {
          return {
            type: "Orthographic" as const,
            fov: num(entry.fov, 45),
            near: num(entry.nearPlane, 0),
            far: num(entry.farPlane, 200),
          };
        }
        return undefined;
      })(),
      transform: {
        position: [
          num(entry["position:x"], 0),
          num(entry["position:y"], 0),
          num(entry["position:z"], 0),
        ],
        rotation: [
          num(entry["rotation:x"], 0),
          num(entry["rotation:y"], 0),
          num(entry["rotation:z"], 0),
        ],
        scale: [
          num(entry["scale:x"], 1),
          num(entry["scale:y"], 1),
          num(entry["scale:z"], 1),
        ],
      },
    });
    report.compositionLayers += 1;
  }

  // ------------------------------------------------------------------ effects
  const effectByExportId = new Map<string, string>();
  for (const [id, rawEffect] of Object.entries(asRecord(root.effects))) {
    const entry = asRecord(rawEffect);
    const typeName = str(entry.type, "");
    const rawSlug = typeName.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const slug = EFFECT_TYPE_ALIASES[rawSlug] ?? rawSlug;
    const connections = Array.isArray(entry.connections) ? entry.connections.map(String) : [];

    // Effects attach to composition nodes. WebGLManager is the composition root
    // (global); a layer:* target is that layer's own chain.
    const targets: string[] = connections
      .map((targetId) => nodeByExportId.get(targetId)?.id ?? null)
      .filter((nodeId): nodeId is string => Boolean(nodeId));

    for (const targetId of connections) {
      if (targetId === "WebGLManager" || targetId === "Project") {
        if (!targets.includes(GLOBAL_TARGET)) targets.push(GLOBAL_TARGET);
      } else if (targetId.startsWith("layer:") && !targets.includes(targetId)) {
        targets.push(targetId);
      }
    }

    if (targets.length === 0) {
      report.skipped.push({ what: `effect ${typeName}`, reason: "no imported target item" });
      continue;
    }
    const effect = createEffect(slug, targets, () => id);
    if (!effect) {
      report.skipped.push({ what: `effect ${typeName}`, reason: "effect not implemented" });
      continue;
    }
    const settings = asRecord(values[id]);
    effect.time = Array.isArray(settings.time)
      ? [num(settings.time[0], 0), num(settings.time[1], target.duration)]
      : null;
    effect.ignoreTimeSpan = settings.ignoreTimeSpan !== false;
    // Copy every numeric parameter the definition exposes. Alpha is scaled
    // separately because its reference values are 0..1 while Rea shows 0..100.
    const definition = definitionsFor(effect.type);
    for (const spec of definition?.params ?? []) {
      const raw = settings[spec.key];
      if (spec.kind === "boolean") {
        if (typeof raw === "boolean") effect.params[spec.key] = raw;
        else if (typeof raw === "number") effect.params[spec.key] = raw !== 0;
      } else if (typeof raw === "number" && Number.isFinite(raw)) {
        effect.params[spec.key] = raw;
      } else if (typeof raw === "string" && spec.kind === "number") {
        // Vizzy serialises some scalars as strings (`equinox` stores
        // `matScaleX: ".4"`, `matPositionY: "0.7"` while `matPositionX` is a
        // number; 1766 such fields across 83 templates). Dropping them left the
        // effect on its definition defaults, so a Transform ran at scale 1 /
        // position 0 instead of the authored values.
        const parsed = raw.trim() === "" ? Number.NaN : Number(raw);
        if (Number.isFinite(parsed)) effect.params[spec.key] = parsed;
      } else if (typeof raw === "string" && spec.kind !== "number") {
        effect.params[spec.key] = raw;
      }
    }
    if (effect.type === "alpha") {
      effect.params.alpha = Math.max(0, Math.min(100, num(settings.alpha, 1) * 100));
    }
    // Respect the export's enabled flag rather than defaulting to on.
    if (settings.enabled === false) effect.enabled = false;
    target.effects.push(effect);
    effectByExportId.set(id, effect.id);
    report.effects += 1;
  }

  // Reference projects order effects per target (`effectsOrder[target]`), not
  // by the object key order in `effects`.
  for (const [rawTarget, rawOrder] of Object.entries(asRecord(root.effectsOrder))) {
    if (!Array.isArray(rawOrder)) continue;
    const targetId =
      rawTarget === "WebGLManager" || rawTarget === "Project" ? GLOBAL_TARGET : rawTarget;
    rawOrder.forEach((rawEffectId, index) => {
      const importedId = effectByExportId.get(String(rawEffectId));
      if (!importedId) return;
      const effect = target.effects.find((item) => item.id === importedId);
      if (effect) effect.orderByTarget[targetId] = index;
    });
  }

  // -------------------------------------------------------------- automations
  const groups = new Map<string, { id: string; name: string; children: string[] }>();
  for (const rawGroup of Array.isArray(root.automationGroups) ? root.automationGroups : []) {
    const group = asRecord(rawGroup);
    const id = str(group.id, "");
    if (!id) continue;
    groups.set(id, {
      id,
      name: str(group.name, "Automations") || "Untitled group",
      children: Array.isArray(group.children) ? group.children.map(String) : [],
    });
  }
  target.automationGroups = [...groups.values()];

  // Rows that only drive a composition layer's 3D transform. Our layers do not
  // model position/rotation/scale/fov yet, so report them explicitly instead of
  // pretending they are unreachable.
  const layerAutomations = new Set<string>();
  const invalidAutomations = new Set<string>();

  for (const [id, rawAutomation] of Object.entries(asRecord(root.automations))) {
    const entry = asRecord(rawAutomation);
    const groupId = str(entry.group, "");
    const automation: Automation = {
      id: id,
      name: str(asRecord(values[id]).name, "") || undefined,
      type:
        str(entry.type, "") === "audioImpact"
          ? "audioImpact"
          : str(entry.type, "") === "math"
            ? "math"
            : "property",
      groupId: groups.has(groupId) ? groupId : undefined,
      nodeId: "",
      propertyId: "",
      connections: {},
      automationConnections: {},
      keyframes: [],
    };

    for (const [targetId, rawParams] of Object.entries(asRecord(entry.connections))) {
      const params = Array.isArray(rawParams) ? rawParams.map(String) : [];
      const nodeId = nodeByExportId.get(targetId);
      if (targetId.startsWith("item:") && nodeId) {
        // Plane/Image items expose `opacity` as a 0..1 member; their controller
        // is `behaviour.opacity` (0..100). Without the redirect the intro black
        // planes never faded out and covered the frame.
        const mapped = params
          .map((param) =>
            param === "opacity" && nodeId.objectMapping.has("behaviour.opacity")
              ? "behaviour.opacity"
              : mapNodeProperty(param),
          )
          .filter(Boolean);
        if (!automation.nodeId) {
          automation.nodeId = nodeId.id;
          automation.propertyId = mapped[0] ?? "";
          if (mapped.length > 1) automation.connections[nodeId.id] = mapped.slice(1);
        } else if (automation.nodeId === nodeId.id) {
          const extras = mapped.filter((controller) => controller !== automation.propertyId);
          automation.connections[nodeId.id] = [
            ...new Set([...(automation.connections[nodeId.id] ?? []), ...extras]),
          ];
        } else {
          automation.connections[nodeId.id] = mapped;
        }
        continue;
      }
      if (targetId.startsWith("effect:")) {
        const effectId = effectByExportId.get(targetId);
        if (effectId) automation.connections[effectId] = params;
        else {
          report.skipped.push({ what: `automation ${id}`, reason: "target effect not imported" });
          invalidAutomations.add(id);
        }
      }
      if (targetId.startsWith("automation:")) {
        // Automation-to-automation links are resolved after every row exists.
        automation.automationConnections![targetId] = params;
      }
      if (targetId.startsWith("analyzer:")) {
        if (target.analyzers.some((analyzer) => analyzer.id === targetId)) {
          automation.connections[targetId] = params;
        } else {
          report.skipped.push({ what: `automation ${id}`, reason: "target analyzer not imported" });
        }
      }
      if (targetId.startsWith("layer:")) {
        if (target.layers.some((layer) => layer.id === targetId)) {
          automation.connections[targetId] = params;
        } else {
          layerAutomations.add(id);
        }
      }
    }

    // An automation with no reachable target would be an inert row. Rows that
    // only feed other automations are pruned later, once the graph is known.
    const feedsAutomation = Object.keys(automation.automationConnections ?? {}).length > 0;
    if (
      !automation.nodeId &&
      Object.keys(automation.connections).length === 0 &&
      !feedsAutomation
    ) {
      if (!invalidAutomations.has(id) || layerAutomations.has(id)) {
        report.skipped.push({
          what: `automation ${id}`,
          reason: layerAutomations.has(id)
            ? "target layer not imported"
            : "no imported target",
        });
      }
      continue;
    }

    // Keyframe automations are a start/end pair on one connection.
    const settings = asRecord(values[id]);
    // Reference scale rows are 1x factors; node controllers store percent.
    const drivesScale =
      /^transform\.scale[XYZ]$/.test(automation.propertyId) ||
      Object.values(automation.connections).some((props) =>
        props.some((property) => /^transform\.scale[XYZ]$/.test(property)),
      );
    // Plane/Image opacity is 0..1 in the export and 0..100 on the controller.
    const drivesOpacity =
      automation.propertyId === "behaviour.opacity" ||
      Object.values(automation.connections).some((props) =>
        props.some((property) => property === "behaviour.opacity"),
      );
    if (settings.enabled === false) automation.enabled = false;
    const referenceMin = str(settings.minValue, str(settings.startValue, ""));
    const referenceMax = str(settings.maxValue, str(settings.endValue, ""));
    const isColor =
      str(settings.variant, "") === "color" ||
      (/^#/.test(referenceMin) && /^#/.test(referenceMax));
    if (isColor) {
      automation.variant = "color";
      automation.colors = { from: referenceMin || "#000000", to: referenceMax || "#ffffff" };
    }
    if (str(settings.type, "") === "audioImpact") {
      // Audio-impact rows carry their own mapping; the reference's `minValue` /
      // `maxValue` are in the driven property's units, `scaleMultiplier` included.
      automation.impact = {
        min: isColor ? 0 : num(settings.minValue, 0),
        max: isColor ? 1 : num(settings.maxValue, 1),
        // Colour rows store 0 when the sensitivity slider was never touched;
        // the reference treats that as full sensitivity. A literal 0 would
        // leave the colour permanently at its `from` value (black particles).
        sensitivity: isColor
          ? Math.max(1, num(settings.sensitivity, 1))
          : num(settings.sensitivity, 1),
        smoothing: num(settings.smoothing, 0),
        floor: num(settings.floorValue, 0),
        ceiling: num(settings.ceilingValue, 0),
        cumulative: settings.isCumulative === true,
        deltaSmoothing: settings.deltaSmoothing === true,
        deltaDecay: num(settings.deltaDecay, 0.01),
        deltaThreshold: num(settings.deltaThreshold, 0),
        color: isColor,
      };
      automation.audioAnalyzer = str(settings.audioAnalyzer, "analyzer:default");
      // Our Spectrum scaleMultiplier is a percentage, the export's is a factor.
      // Text items keep the raw factor on the node (`scaleMultiplier` is read
      // directly by SkiaText/Lyrics), so calibrating them would inflate an
      // authored 5x to 5x46.3.
      let impactUnitScale = 1;
      if (
        !isColor &&
        automation.propertyId === "transform.scaleMultiplier" &&
        spectrumNodeIds.has(automation.nodeId)
      ) {
        impactUnitScale = scaleMultiplierFromReference(1);
      }
      if (!isColor && (drivesScale || drivesOpacity)) impactUnitScale *= 100;
      if (impactUnitScale !== 1) {
        const impact = automation.impact;
        impact.min *= impactUnitScale;
        impact.max *= impactUnitScale;
        // `deltaDecay`/`deltaThreshold` are deltas of the mapped value, so they
        // live in the same units. Leaving them unscaled made the reference's
        // aggressive per-frame decay 46x too gentle on scaleMultiplier rows.
        impact.deltaDecay = (impact.deltaDecay ?? 0) * impactUnitScale;
        impact.deltaThreshold = (impact.deltaThreshold ?? 0) * impactUnitScale;
      }
    }
    if (str(settings.type, "") === "math") {
      // Math automations keep only the formula; it is evaluated every frame.
      automation.formula = str(settings.formula, "");
      const units = [1, 2, 3, 4, 5].map((index) => settings[`u${index}`]);
      if (
        units.some(
          (value) =>
            typeof value === "number" ||
            (typeof value === "string" && value.trim() !== ""),
        )
      ) {
        automation.units = units.map((value) => num(value, 0));
      }
      if (drivesScale) automation.referenceScaleUnits = true;
    }
    if (str(settings.type, "") === "keyframe") {
      if (isColor) {
        const startTime = num(settings.startTime, 0);
        automation.keyframes = [
          { t: startTime, value: 0, easing: mapEasing(settings.interpolation) },
          { t: num(settings.endTime, startTime), value: 1, easing: "linear" },
        ];
      } else {
        // The reference stores effect parameters in their own units; our percent
        // params (alpha) need the same scale the effect import applied.
        const scaled =
          drivesScale ||
          drivesOpacity ||
          Object.keys(automation.connections).some(
            (effectId) => target.effects.find((effect) => effect.id === effectId)?.type === "alpha",
          );
        const scale = scaled ? 100 : 1;
        const startTime = num(settings.startTime, 0);
        automation.keyframes = [
          {
            t: startTime,
            value: num(settings.startValue, 0) * scale,
            easing: mapEasing(settings.interpolation),
          },
          {
            t: num(settings.endTime, startTime),
            value: num(settings.endValue, 1) * scale,
            easing: "linear",
          },
        ];
      }
    }

    target.automations.push(automation);
    report.automations += 1;
  }

  // A row that only feeds other automations is kept when its targets survive;
  // prune inert chains so the editor does not show rows that change nothing.
  {
    const direct = new Set(
      target.automations
        .filter(
          (automation) =>
            Boolean(automation.nodeId) || Object.keys(automation.connections).length > 0,
        )
        .map((automation) => automation.id),
    );
    let changed = true;
    while (changed) {
      changed = false;
      for (const automation of target.automations) {
        if (direct.has(automation.id)) continue;
        const feeds = Object.keys(automation.automationConnections ?? {}).some((id) =>
          direct.has(id),
        );
        if (feeds) {
          direct.add(automation.id);
          changed = true;
        }
      }
    }
    const kept = target.automations.filter((automation) => direct.has(automation.id));
    for (const automation of target.automations) {
      if (direct.has(automation.id)) continue;
      if (invalidAutomations.has(automation.id) && !layerAutomations.has(automation.id)) continue;
      report.skipped.push({
        what: `automation ${automation.id}`,
        reason: layerAutomations.has(automation.id)
          ? "target layer not imported"
          : "no imported target",
      });
    }
    for (const automation of kept) {
      for (const id of Object.keys(automation.automationConnections ?? {})) {
        if (!direct.has(id)) delete automation.automationConnections![id];
      }
    }
    target.automations = kept;
    report.automations = kept.length;
  }

  // Keep group membership consistent with what actually imported: drop children
  // that were skipped, and point each survivor at its group.
  {
    const imported = new Set(target.automations.map((automation) => automation.id));
    for (const group of target.automationGroups) {
      group.children = group.children.filter((id) => imported.has(id));
      for (const id of group.children) {
        const automation = target.automations.find((entry) => entry.id === id);
        if (automation) automation.groupId = group.id;
      }
    }
  }

  // ------------------------------------------------------- analyzer ownership
  const analyzerByExportId = new Map(target.analyzers.map((analyzer) => [analyzer.id, analyzer]));
  for (const [analyzerId, rawEntry] of Object.entries(asRecord(root.audioAnalyzers))) {
    const analyzer = analyzerByExportId.get(analyzerId);
    if (!analyzer) continue;
    const connections = asRecord(asRecord(rawEntry).connections);
    for (const userId of Object.keys(connections)) {
      const node = nodeByExportId.get(userId);
      if (node) {
        if (!analyzer.users.includes(node.id)) analyzer.users.push(node.id);
        continue;
      }
      // Composition layer connections (`layer:*`) use the layer's own
      // `audioAnalyzer` controller.
      const layer = target.layers.find((entry) => entry.id === userId);
      if (layer) {
        layer.audioAnalyzer = analyzer.id;
        if (!analyzer.users.includes(layer.id)) analyzer.users.push(layer.id);
      }
    }
  }
  for (const node of target.nodes) {
    const owner = target.analyzers.find((analyzer) => analyzer.users.includes(node.id));
    node.analyzerId = owner?.id ?? null;
  }

  return report;
}

export { createNode as defaultNodeFactory };
