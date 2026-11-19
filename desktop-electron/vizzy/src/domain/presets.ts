/**
 * Presets are plain parameter sets over a spectrum node. They are data, not
 * code, which is what makes them saveable, importable and diffable.
 *
 * Trap Motion is our built-in; the other 32 are the reference's own presets,
 * decompiled from its public Firestore payload (see UX-PARITY §6). The catalogue
 * is a summary; the full apply payload lives in spectrum-snapshots.json.
 */

import communityPresetData from "./community-presets.json";
import spectrumCatalogueData from "./spectrum-catalogue.json";
import spectrumSnapshotData from "./spectrum-snapshots.json";

/**
 * One analyser in a preset payload. The reference stores one analyser per
 * layer, in the same order, and the layer reads it positionally.
 */
export interface PresetAnalyzerSnapshot {
  name?: string;
  sampleProvider?: string;
  outputMultiplier?: number;
  sampleOutCount?: number;
  audioDuration?: number;
  audioOffset?: number;
  frequencyRange?: [number, number] | number[];
  windowFunction?: string;
  /** Every other reference field is kept verbatim for documentation/fidelity. */
  [key: string]: unknown;
}

/**
 * A reference preset's full apply payload, decompiled from the public Firestore
 * document `spectrum_presets/spectrum_preset:<id>`. The `item` carries the
 * spectrum settings only; item identity (name, time, row, visibility) belongs to
 * the project the preset is applied to.
 */
export interface PresetSnapshot {
  source?: Record<string, unknown>;
  item: Record<string, unknown>;
  layers: Record<string, unknown>[];
  analyzers?: PresetAnalyzerSnapshot[];
}

export type SpectrumType = "Bars" | "Circle" | "Custom" | "Image";
export type SpectrumDraw = "Line" | "Curve" | "Plexus" | "Point";
export type SpectrumFillStyle = "Fill" | "Stroke";

export interface SpectrumParams {
  type: SpectrumType;
  draw: SpectrumDraw;
  fillStyle: SpectrumFillStyle;
  bands: number;
  gain: number;
  colorShift: number;
  mirror: boolean;
  smoothing: number;
  opacity: number;
  /** Vertical amplitude multiplier, percent. */
  height: number;
  /** Point/bead radius in plane units, percent of a band slot. */
  dotSize: number;
  /** Soft edge width, 0..100. */
  feather: number;
  /** Band stride: 1, 2, 4 or 8. */
  downsample: number;
  /** Image-backed presets: mask the source image to a circle. */
  circularImage?: boolean;
  /** Image-backed presets: source image scale, percent. */
  imageSize?: number;
  /** Image-backed presets: source image, loaded over the network. */
  imageUrl?: string;
  /** Contour colours drawn behind the white body, outermost first. */
  contourColors?: string[];
  /** Body colour. */
  color?: string;
  /** Body radius before displacement, percent. */
  baseRadius?: number;
  /** Radial gap between contour layers, percent. */
  /** Contour stroke width, percent. */
  contourWidth?: number;
  /** Fill the disc behind the bands. */
  fillCircle?: boolean;
  /** Clip coverage to the circle radius. */
  clipCircle?: boolean;
  /** Circle radius, percent. */
  circleSize?: number;
  /** Whole-shape scale multiplier, percent. */
  scaleMultiplier?: number;
  /** Item scale, percent. The reference's default spectrum scale is 125. */
  scale?: number;
  /** Global shadow on this item. */
  shadowEnabled?: boolean;
  /** Shadow blur in reference-canvas pixels (the export's globalShadowSigmaX/Y). */
  shadowSigma?: number;
  shadowScale?: number;
  shadowAlpha?: number;
  /** Built-in presets only: constant spin, degrees per second. */
  spinSpeed?: number;
}

export interface Preset {
  id: string;
  name: string;
  category: string;
  params: SpectrumParams;
  /** Built-ins cannot be deleted; user presets can. */
  builtin?: boolean;
  /** Where the preset came from; community presets are data-only imports. */
  source?: "builtin" | "authored" | "reference" | "community" | "user";
  /** Thumbnail image URL. Sourced presets use the reference's own artwork. */
  thumb?: string;
  /** Full item graph for sourced presets; takes precedence over `params`. */
  snapshot?: PresetSnapshot;
}

export const DEFAULT_PARAMS: SpectrumParams = {
  type: "Bars",
  draw: "Line",
  fillStyle: "Fill",
  bands: 64,
  gain: 1,
  colorShift: 0,
  mirror: false,
  smoothing: 60,
  opacity: 95,
  height: 100,
  dotSize: 5,
  feather: 8,
  downsample: 1,
};

const preset = (
  id: string,
  name: string,
  category: string,
  params: Partial<SpectrumParams>,
): Preset => ({
  id,
  name,
  category,
  params: { ...DEFAULT_PARAMS, ...params },
  builtin: true,
});

/**
 * The single built-in preset: the reference's Trap Motion spectrum — a white
 * radial silhouette filled with the logo artwork and ringed by six coloured
 * contours. Values read from the reference editor's own inspector.
 */
const TRAP_MOTION_BASE: Preset = preset("trap-motion", "Trap Motion", "Circle", {
  type: "Circle",
  draw: "Curve",
  fillStyle: "Fill",
  bands: 64,
  gain: 1,
  // The export mirrors the spectrum horizontally, which is what makes both
  // sides of the ring move instead of only the low-frequency side.
  mirror: true,
  height: 100,
  dotSize: 5,
  feather: 8,
  downsample: 1,
  circularImage: true,
  imageSize: 100,
  // The shipped emblem file is a sticker (opaque white rounded-square
  // background). Trap Motion is the black artwork over the spectrum's own
  // white body, so use the transparent cut of the same artwork.
  imageUrl: "/media/vizzy-emblem-alpha.png",
  // Twelve layers: eleven contours interpolated through the reference's six
  // anchor colours, then the white body. The node builds one pass and one
  // analyser per colour, so the count is data rather than code.
  contourColors: ["#00b950", "#00c9a8", "#00d8ff", "#0091ff", "#0049ff", "#8025ff", "#ff00ff", "#ff0080", "#ff0000", "#ff7701", "#ffed02"],
  color: "#ffffff",
  baseRadius: 51.4,
  contourWidth: 0.7,
  fillCircle: false,
  clipCircle: false,
  circleSize: 100,
  // Reference factor 2.225 at the 1.026s snapshot (see reference-scale.ts).
  scaleMultiplier: 103,
  scale: 125,
  shadowEnabled: true,
  // The export's global shadow: scaling 1, alpha 1, sigma 20.
  shadowSigma: 20,
  shadowScale: 100,
  shadowAlpha: 100,
});

// The gallery tile keeps the shipped sticker artwork; the applied preset uses
// the transparent cut so the white spectrum body forms the circle.
export const TRAP_MOTION_PRESET: Preset = {
  ...TRAP_MOTION_BASE,
  thumb: "/media/vizzy-emblem.webp",
};

/**
 * Aurora Ring - a cool, luminous circle built for dark templates.
 *
 * The reference draws one filled/stroked silhouette per layer in order, so a
 * contour colour survives only where that layer reaches past the layer above
 * it. `contourColors` alone cannot stagger those radii, so the look ships as a
 * snapshot: eleven teal -> ice-blue -> violet contours whose `scale` steps
 * inward by a fraction of a pixel each, then a near-white body.
 *
 * `params` is kept too: it is the human-readable intent (and the source of the
 * saved/exported preset), while the snapshot is what the editor applies.
 */
const AURORA_CONTOURS = [
  "#14e3c4",
  "#17dcd0",
  "#1fd3dc",
  "#2fc9e8",
  "#46bef2",
  "#60b3f9",
  "#7ba8fd",
  "#96a0ff",
  "#ad98ff",
  "#c090ff",
  "#d187ff",
];
const AURORA_BODY = "#f3fbff";
// Outermost layer first (painted first, largest radius) down to the body, which
// is painted last and sits innermost. The 0.0086 scale step is under a pixel at
// 720p, so the strokes overlap into a continuous gradient fringe.
const AURORA_LAYER_COLORS = [...AURORA_CONTOURS, AURORA_BODY];
const AURORA_SCALE_OUTER = 1.045;
const AURORA_SCALE_INNER = 0.95;

const AURORA_LAYER_SCALES = AURORA_LAYER_COLORS.map(
  (_, index) =>
    AURORA_SCALE_OUTER +
    ((AURORA_SCALE_INNER - AURORA_SCALE_OUTER) * index) /
      Math.max(1, AURORA_LAYER_COLORS.length - 1),
);

const AURORA_RING_SNAPSHOT: PresetSnapshot = {
  item: {
    imageSize: 1,
    smoothingPasses: 4,
    dotSize: 5,
    fillType: "stroke",
    spacing: 0,
    dashOffset: 10,
    positionY: 0,
    // 0.72 keeps the ring plus its tallest band inside a 16:9 frame: at 720p
    // the base is ~153px radius and the shadow reaches the frame edge only on
    // the loudest frames of the default test project.
    spectrumHeight: 0.72,
    closeLine: true,
    repeatPointsOnPath: true,
    drawType: "curve",
    pathEffect: "none",
    scaleY: 1,
    clipSize: 0.95,
    circleColor: "#ffffff",
    _rotation: 0,
    // Reference factor ~1.7 gives a ~153px ring at 720p, matching the
    // reference's own circle presets without touching the frame edges.
    scaleMultiplier: 1.7,
    moveBack: false,
    downSample: "1",
    lineCap: "round",
    mirrorHorizontal: true,
    clipImageToCircle: false,
    // Thin stroke: 2 item units is ~2.5px at 720p after the scale factors.
    lineWidth: 2,
    smoothStartAndEnd: true,
    fillCircle: false,
    spectrumType: "circle",
    customPath: "",
    scaleToAspect: false,
    imageSrc: "",
    clipCircle: false,
    scaleX: 1,
    positionX: 0,
    smoothingWidth: 10,
    circleSize: 1,
    type: "Spectrum",
    name: "Spectrum",
    useMSAA: true,
    // A soft halo rather than a bloom: 16px blur at 0.85 alpha.
    useGlobalShadow: true,
    globalShadowScaling: 1,
    globalShadowAlpha: 0.85,
    globalShadowSigmaX: 16,
    globalShadowSigmaY: 16,
  },
  layers: AURORA_LAYER_COLORS.map((color, index) => ({
    index,
    multiplier: 1,
    ceiling: 1000,
    alpha: 1,
    colorType: "Solid",
    color,
    colorFrom: color,
    colorTo: color,
    colorMix: 0.5,
    colorGradient: `${color}:${color}`,
    baseOn: "Value",
    shaderSrc: "",
    shadowAlpha: 0,
    shadowColor: "#ffffff",
    shadowScale: 1,
    blurAmount: 0,
    rotation: 0,
    scale: AURORA_LAYER_SCALES[index],
    enabled: true,
    analyzerIndex: 0,
  })),
  // One shared analyser: every contour reads the same band series, so the
  // fringe stays perfectly nested. A long window + slow release is the
  // "high smoothing" the design asks for; `effects.smoothing` is inert on the
  // Canvas2D path renderer, so the smoothing is delivered here instead.
  analyzers: [
    {
      name: "Aurora Ring",
      sampleProvider: "filter bank",
      outputMultiplier: 53,
      sampleOutCount: 64,
      audioDuration: 230,
      audioOffset: 0,
      audioReactionAlignment: -1,
      frequencyRange: [24, 900],
      smoothingTimeConstant: 0.7,
      windowFunction: "gaussian",
      windowParameter: 1,
      windowSkew: 0,
      frequencyScale: "log",
      hzLinearFactor: 0.5,
      cqtBandwidth: 8,
      downSample: false,
    },
  ],
};

export const AURORA_RING_PRESET: Preset = {
  ...preset("aurora-ring", "Aurora Ring", "Circle", {
    type: "Circle",
    draw: "Curve",
    fillStyle: "Stroke",
    bands: 64,
    gain: 1,
    mirror: true,
    smoothing: 80,
    opacity: 95,
    height: 72,
    dotSize: 5,
    feather: 6,
    downsample: 1,
    contourColors: AURORA_CONTOURS,
    color: AURORA_BODY,
    baseRadius: 51.4,
    contourWidth: 0.7,
    fillCircle: false,
    clipCircle: false,
    circleSize: 100,
    scaleMultiplier: 170,
    scale: 125,
    shadowEnabled: true,
    shadowSigma: 16,
    shadowScale: 100,
    shadowAlpha: 85,
  }),
  thumb: "/presets/aurora-ring.webp",
  snapshot: AURORA_RING_SNAPSHOT,
};

const SUNBURST_RIM = ["#6d1200", "#f52700", "#ff7d00"] as const;
const SUNBURST_RIM_SCALE = [1.12, 1.085, 1.045] as const;

const SUNBURST_LAYERS: Record<string, unknown>[] = [
  ...SUNBURST_RIM.map((color, index) => ({
    index,
    // Amplitude x2 on top of the item's 100% height, with bands clamped at 55:
    // quiet tracks still read as a solid fan, and peaks stop growing before the
    // outer rim reaches the frame edge. The item is deliberately smaller than a
    // full-frame look because the demo project's audio-impact row pumps
    // scaleMultiplier to a 3.25 reference factor; at that maximum the fan fills
    // ~90% of a 16:9 frame and still keeps a margin.
    multiplier: 2,
    ceiling: 55,
    alpha: 1,
    colorType: "Solid",
    color,
    colorFrom: color,
    colorTo: color,
    colorMix: 0.5,
    colorGradient: `${color}:${color}`,
    baseOn: "Value",
    shaderSrc: "",
    shadowAlpha: 0,
    shadowColor: "#2a0700",
    shadowScale: 1,
    blurAmount: 0,
    rotation: 0,
    scale: SUNBURST_RIM_SCALE[index],
    enabled: true,
    audioAnalyzer: null,
  })),
  {
    index: 3,
    multiplier: 2,
    ceiling: 55,
    alpha: 1,
    // A radial ramp: white-hot at the spectrum's centre, amber at its edges.
    // The radius is 750 x colorMix in plane units, i.e. ~215, which is where
    // the outermost bars sit at spacing 3.
    colorType: "From-to",
    color: "#ffa11a",
    colorFrom: "#fffdf4",
    colorTo: "#ffa11a",
    colorMix: 0.286,
    colorGradient: "#fffdf4:#ffa11a",
    baseOn: "Distance from center",
    shaderSrc: "",
    shadowAlpha: 0,
    shadowColor: "#2a0700",
    shadowScale: 1,
    blurAmount: 0,
    rotation: 0,
    scale: 1,
    enabled: true,
    audioAnalyzer: null,
  },
];

export const SUNBURST_BARS_PRESET: Preset = {
  id: "sunburst-bars",
  name: "Sunburst Bars",
  category: "Bars",
  builtin: true,
  source: "builtin",
  thumb: "/presets/sunburst-bars.webp",
  params: {
    ...DEFAULT_PARAMS,
    type: "Bars",
    draw: "Line",
    fillStyle: "Fill",
    bands: 64,
    mirror: true,
    downsample: 4,
    height: 100,
    opacity: 95,
    color: "#ffa11a",
    contourColors: [...SUNBURST_RIM],
    scaleMultiplier: 100,
    shadowEnabled: true,
    shadowSigma: 16,
    shadowAlpha: 60,
  },
  snapshot: {
    source: { label: "Studio built-in", spectrumType: "bars" },
    item: {
      type: "Spectrum",
      name: "Spectrum",
      spectrumType: "bars",
      drawType: "line",
      fillType: "fill",
      mirrorHorizontal: true,
      // 1x the reference's spectrum height; the fan's size comes from the
      // demo project's audio-impact pump (1.75-3.25x) rather than a static
      // full-frame scale.
      spectrumHeight: 1,
      downSample: "4",
      lineWidth: 2,
      lineCap: "square",
      // Bars pack their x positions into +/-CUR_RAD; spacing widens that span
      // (~64 points at 3 units each) so the fan is ~50% of the frame width at
      // the project's quiet scale and ~88% at its loud maximum.
      spacing: 3,
      closeLine: true,
      repeatPointsOnPath: true,
      smoothStartAndEnd: true,
      smoothingWidth: 10,
      smoothingPasses: 4,
      stretchToEnd: false,
      moveBack: false,
      pathEffect: "none",
      dashOffset: 10,
      clipSize: 0.95,
      fillCircle: false,
      clipCircle: false,
      circleSize: 1,
      circleColor: "#ffffff",
      scaleMultiplier: 1,
      scaleX: 1,
      scaleY: 1,
      positionX: 0,
      positionY: 0,
      _rotation: 0,
      useGlobalShadow: true,
      globalShadowSigmaX: 16,
      globalShadowSigmaY: 16,
      globalShadowAlpha: 0.6,
      globalShadowScaling: 1,
      imageSrc: "",
      imageSize: 1,
      clipImageToCircle: false,
      customPath: "",
    },
    layers: SUNBURST_LAYERS,
  },
};
const NEON_POP_MAGENTA = "#ff2bd6";
const NEON_POP_VIOLET = "#8a2cff";
const NEON_POP_GOLD = "#ffb300";

const NEON_POP_SNAPSHOT: PresetSnapshot = {
  item: {
    imageSize: 1,
    smoothingPasses: 4,
    dotSize: 5,
    fillType: "stroke",
    spacing: 14.5,
    dashOffset: 10,
    // 280 / 1000 puts the baseline at ~79% of a 16:9 frame after the item
    // transform; amplitude is measured upward from there.
    positionY: 280,
    // 1.6 with the 100-unit layer ceiling keeps every band (plus the 10px halo)
    // inside the frame: 100 * 1.6 * 0.72 = 115px below a 562px baseline at 720p.
    spectrumHeight: 1.6,
    // `moveBack` makes the reference emit a separate baseline-to-value segment
    // per band instead of one joined envelope, i.e. actual equalizer bars.
    closeLine: false,
    moveBack: true,
    repeatPointsOnPath: true,
    drawType: "line",
    pathEffect: "none",
    scaleY: 1,
    clipSize: 0.95,
    circleColor: "#ffffff",
    _rotation: 0,
    // Reference factor 1 keeps the bars at their native item scale: with
    // spacing 14.5 they span ~91% of a 1280-wide frame.
    scaleMultiplier: 1,
    downSample: "1",
    lineCap: "round",
    mirrorHorizontal: true,
    clipImageToCircle: false,
    // Bar thickness: ~9px at 720p, leaving a visible gap in each 10px slot.
    lineWidth: 12,
    smoothStartAndEnd: true,
    fillCircle: false,
    spectrumType: "bars",
    customPath: "",
    scaleToAspect: false,
    imageSrc: "",
    clipCircle: false,
    scaleX: 1,
    positionX: 0,
    smoothingWidth: 10,
    circleSize: 1,
    type: "Spectrum",
    name: "Spectrum",
    useMSAA: true,
    useGlobalShadow: true,
    globalShadowScaling: 1,
    globalShadowAlpha: 0.8,
    globalShadowSigmaX: 10,
    globalShadowSigmaY: 10,
  },
  layers: [
    {
      index: 0,
      multiplier: 1,
      // A gentle ceiling lifts the body of the mix without letting a kick band
      // push the reflection into the frame edge.
      ceiling: 100,
      alpha: 1,
      colorType: "From-to",
      color: NEON_POP_VIOLET,
      colorFrom: NEON_POP_GOLD,
      colorTo: NEON_POP_VIOLET,
      colorMix: 0.5,
      colorGradient: `${NEON_POP_VIOLET}:${NEON_POP_GOLD}`,
      // For a Bars path this axis runs across the bar sequence: violet at the
      // frame edges, gold through the centre, passing through magenta.
      baseOn: "Y-Position",
      shaderSrc: "",
      shadowAlpha: 0,
      shadowColor: "#ffffff",
      shadowScale: 1,
      blurAmount: 0,
      rotation: 0,
      scale: 1,
      enabled: true,
      analyzerIndex: 0,
    },
    {
      index: 1,
      multiplier: 1,
      ceiling: 100,
      alpha: 0.2,
      colorType: "Gradient",
      color: NEON_POP_VIOLET,
      colorFrom: NEON_POP_MAGENTA,
      colorTo: NEON_POP_GOLD,
      colorMix: 0.5,
      colorGradient: `${NEON_POP_VIOLET}:${NEON_POP_GOLD}`,
      baseOn: "Value",
      shaderSrc: "",
      shadowAlpha: 0,
      shadowColor: "#ffffff",
      shadowScale: 1,
      blurAmount: 0,
      rotation: 0,
      scale: 1,
      enabled: true,
      analyzerIndex: 0,
    },
  ],
  // One short-window, low-smoothing analyser: 96 bars over the pop range. The
  // short history is what keeps the equalizer lively instead of gliding.
  analyzers: [
    {
      name: "Neon Pop",
      sampleProvider: "filter bank",
      outputMultiplier: 60,
      sampleOutCount: 96,
      audioDuration: 96,
      audioOffset: 0,
      audioReactionAlignment: -1,
      frequencyRange: [24, 1800],
      smoothingTimeConstant: 0.12,
      windowFunction: "raised cosine",
      windowParameter: 1,
      windowSkew: 0,
      frequencyScale: "mel",
      hzLinearFactor: 0.5,
      // Lift the top octaves so the right half of the equalizer moves with the
      // vocal/pop content instead of sitting flat under the bass.
      perBandFrequencyTilt: 5,
      cqtBandwidth: 8,
      downSample: false,
    },
  ],
};

export const NEON_POP_PRESET: Preset = {
  ...preset("neon-pop", "Neon Pop", "Bars", {
    type: "Bars",
    draw: "Line",
    fillStyle: "Stroke",
    bands: 96,
    gain: 1,
    mirror: true,
    smoothing: 15,
    opacity: 95,
    height: 160,
    dotSize: 5,
    feather: 8,
    downsample: 1,
    color: NEON_POP_MAGENTA,
    scaleMultiplier: 100,
    scale: 100,
    shadowEnabled: true,
    shadowSigma: 10,
    shadowScale: 100,
    shadowAlpha: 80,
  }),
  thumb: "/presets/neon-pop.webp",
  snapshot: NEON_POP_SNAPSHOT,
};
const VINYL_MAGENTA = "#ff3d9a";
const VINYL_VIOLET = "#8a2cff";

const VINYL_SPIN_SNAPSHOT: PresetSnapshot = {
  item: {
    imageSize: 0.92,
    smoothingPasses: 4,
    dotSize: 5,
    fillType: "stroke",
    spacing: 0,
    dashOffset: 10,
    positionY: 0,
    // 0.9 keeps the ticks short-to-medium; the bars layer's 120-unit ceiling
    // caps the longest tip at ~155px past the 173px play ring at 720p.
    spectrumHeight: 0.9,
    closeLine: true,
    // A full circle: Image joins Circle in the non-bars path builder.
    stretchToEnd: true,
    moveBack: true,
    repeatPointsOnPath: true,
    drawType: "line",
    pathEffect: "none",
    scaleY: 1,
    clipSize: 0.95,
    // Label colour behind the black emblem. The image radius is 92% of the
    // 120-unit play ring, leaving a visible coloured label band.
    circleColor: "#a3188f",
    circleSize: 1,
    fillCircle: true,
    _rotation: 0,
    // Reference factor 2 gives a ~173px play ring at 720p (346px diameter).
    scaleMultiplier: 2,
    downSample: "1",
    lineCap: "round",
    mirrorHorizontal: false,
    clipImageToCircle: true,
    imageSrc: "/media/vizzy-emblem-alpha.png",
    // Thin ticks with visible gaps: 64 bands at ~17px slots at 720p.
    lineWidth: 3,
    smoothStartAndEnd: true,
    spectrumType: "image",
    customPath: "",
    scaleToAspect: false,
    clipCircle: false,
    scaleX: 1,
    positionX: 0,
    smoothingWidth: 10,
    type: "Spectrum",
    name: "Spectrum",
    useMSAA: true,
    useGlobalShadow: true,
    globalShadowScaling: 1,
    globalShadowAlpha: 0.6,
    globalShadowSigmaX: 10,
    globalShadowSigmaY: 10,
    // 10°/s: a full turn every 36s.
    spinSpeed: 10,
  },
  layers: [
    {
      index: 0,
      // A perfect base circle: multiplier 0 freezes the band displacement, and
      // `moveBack: false` strokes one continuous rim instead of ticks.
      multiplier: 0,
      ceiling: 1000,
      alpha: 1,
      colorType: "Solid",
      color: VINYL_MAGENTA,
      colorFrom: VINYL_MAGENTA,
      colorTo: VINYL_MAGENTA,
      colorMix: 0.5,
      colorGradient: `${VINYL_MAGENTA}:${VINYL_MAGENTA}`,
      baseOn: "Value",
      shaderSrc: "",
      shadowAlpha: 0,
      shadowColor: "#ffffff",
      shadowScale: 1,
      blurAmount: 0,
      rotation: 0,
      scale: 1,
      enabled: true,
      analyzerIndex: 0,
    },
    {
      index: 1,
      multiplier: 1,
      // Keep even a full-scale band inside the frame: 120 * 0.9 * 2 * 0.72
      // adds 155px to the 173px play ring at 720p.
      ceiling: 120,
      alpha: 1,
      colorType: "From-to",
      color: VINYL_MAGENTA,
      colorFrom: VINYL_MAGENTA,
      colorTo: VINYL_VIOLET,
      colorMix: 0.3,
      colorGradient: `${VINYL_MAGENTA}:${VINYL_VIOLET}`,
      // Radial ramp: warm magenta at the play ring, violet at the tick tips.
      baseOn: "Distance from center",
      shaderSrc: "",
      shadowAlpha: 0,
      shadowColor: "#ffffff",
      shadowScale: 1,
      blurAmount: 0,
      rotation: 0,
      scale: 1,
      enabled: true,
      analyzerIndex: 0,
    },
  ],
  analyzers: [
    {
      name: "Vinyl Spin",
      sampleProvider: "filter bank",
      outputMultiplier: 60,
      sampleOutCount: 64,
      audioDuration: 150,
      audioOffset: 0,
      audioReactionAlignment: -1,
      frequencyRange: [24, 1600],
      smoothingTimeConstant: 0.22,
      windowFunction: "gaussian",
      windowParameter: 1,
      windowSkew: 0,
      frequencyScale: "mel",
      hzLinearFactor: 0.5,
      cqtBandwidth: 8,
      downSample: false,
    },
  ],
};

export const VINYL_SPIN_PRESET: Preset = {
  ...preset("vinyl-spin", "Vinyl Spin", "Image", {
    type: "Image",
    draw: "Line",
    fillStyle: "Stroke",
    bands: 64,
    gain: 1,
    mirror: false,
    smoothing: 25,
    opacity: 95,
    height: 90,
    dotSize: 5,
    feather: 8,
    downsample: 1,
    circularImage: true,
    imageSize: 92,
    imageUrl: "/media/vizzy-emblem-alpha.png",
    fillCircle: true,
    clipCircle: false,
    circleSize: 100,
    color: VINYL_MAGENTA,
    scaleMultiplier: 200,
    scale: 125,
    shadowEnabled: true,
    shadowSigma: 10,
    shadowScale: 100,
    shadowAlpha: 60,
    spinSpeed: 10,
  }),
  thumb: "/presets/vinyl-spin.webp",
  snapshot: VINYL_SPIN_SNAPSHOT,
};
export const BUILTIN_PRESETS: Preset[] = [TRAP_MOTION_PRESET, AURORA_RING_PRESET, SUNBURST_BARS_PRESET, NEON_POP_PRESET, VINYL_SPIN_PRESET];

const STORAGE_KEY = "studio.presets.v1";

/** Presets imported from a community export; parameters only, thumbnails render locally. */
export const COMMUNITY_PRESETS: Preset[] = (Array.isArray(communityPresetData)
  ? (communityPresetData as Preset[])
  : []
).map((entry) => ({
  ...entry,
  source: "community",
}));

/**
 * The gallery we ship: Trap Motion plus the reference's 32 presets. Same size
 * and shape as the reference's gallery; the catalogue and snapshots are sourced
 * from its public payload (see editor/docs/UX-PARITY.md §6).
 */
const SNAPSHOTS = spectrumSnapshotData as Record<string, PresetSnapshot>;

export const SPECTRUM_CATALOGUE: Preset[] = (Array.isArray(spectrumCatalogueData)
  ? (spectrumCatalogueData as Preset[])
  : []
).map((entry) => ({
  ...entry,
  builtin: true,
  source: entry.source ?? "reference",
  snapshot: SNAPSHOTS[entry.id],
}));

export function loadUserPresets(): Preset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Preset[];
    if (!Array.isArray(parsed)) return [];
    // Older saved presets predate newer parameters; fill them from defaults.
    return parsed
      .filter((p) => p && typeof p.id === "string" && p.params)
      .map((p) => ({ ...p, params: { ...DEFAULT_PARAMS, ...p.params } }));
  } catch {
    return [];
  }
}

function persist(presets: Preset[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    /* storage may be unavailable; presets stay in memory */
  }
}

export function saveUserPreset(name: string, params: SpectrumParams): Preset[] {
  const presets = loadUserPresets();
  const entry: Preset = {
    id: `user-${Date.now().toString(36)}`,
    name: name || `Preset ${presets.length + 1}`,
    category: "Custom",
    params: { ...params },
  };
  const next = [...presets, entry];
  persist(next);
  return next;
}

export function deleteUserPreset(id: string): Preset[] {
  const next = loadUserPresets().filter((p) => p.id !== id);
  persist(next);
  return next;
}

/** Reference `SAVE_AS` / `SCREENSHOT`: update one saved preset in place. */
export function updateUserPreset(id: string, patch: Partial<Preset>): Preset[] {
  const next = loadUserPresets().map((preset) =>
    preset.id === id
      ? {
          ...preset,
          ...patch,
          params: patch.params ? { ...preset.params, ...patch.params } : preset.params,
        }
      : preset,
  );
  persist(next);
  return next;
}

export function allPresets(): Preset[] {
  return [
    ...BUILTIN_PRESETS,
    ...SPECTRUM_CATALOGUE,
    ...COMMUNITY_PRESETS,
    ...loadUserPresets(),
  ];
}

/** Accepts either an array of presets or a single preset object. */
export function parsePresetFile(text: string): Preset[] {
  const parsed = JSON.parse(text) as Preset | Preset[];
  const list = Array.isArray(parsed) ? parsed : [parsed];
  return list
    .filter((p) => p && typeof p.name === "string" && p.params)
    .map((p) => ({
      id: `import-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      name: p.name,
      category: p.category ?? "Imported",
      params: { ...DEFAULT_PARAMS, ...p.params },
    }));
}

export function exportPresets(presets: Preset[]): string {
  return JSON.stringify(
    presets.map(({ name, category, params }) => ({ name, category, params })),
    null,
    2,
  );
}
