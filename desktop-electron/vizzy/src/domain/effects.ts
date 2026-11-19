/**
 * Effect catalogue and instances.
 *
 * The catalogue records the *categories and names* observed in the reference
 * editor's effect browser (read-only observation). Implementations exist only
 * for the six marked `implemented`; the rest are listed so the browser behaves
 * like the reference and can be filled in slice by slice.
 */

export type EffectCategory =
  | "Color"
  | "Blending"
  | "Other"
  | "Blur"
  | "Lighting"
  | "Distortion"
  | "Motion"
  | "Stylize"
  | "Advanced Outline"
  | "Advanced Shadow";

export type EffectValue = number | boolean | string;

export interface EffectParam {
  key: string;
  label: string;
  min: number;
  max: number;
  step?: number;
  default: EffectValue;
  unit?: string;
  /** Number sliders are the default; booleans render as a checkbox. */
  kind?: "number" | "boolean" | "color" | "select" | "layer" | "text" | "image";
  options?: string[];
}

export interface EffectDefinition {
  type: string;
  name: string;
  category: EffectCategory;
  implemented: boolean;
  params: EffectParam[];
}

/** Target id that means "the whole composition" rather than a single item. */
export const GLOBAL_TARGET = "global";

export interface EffectInstance {
  id: string;
  type: string;
  name: string;
  /**
   * Target ids this effect feeds: {@link GLOBAL_TARGET} and/or item ids. One
   * effect can feed several items, matching the reference's
   * `effects[id].connections`. The post pass currently renders global effects
   * only, so item targets are recorded and displayed but not yet applied.
   */
  targets: string[];
  enabled: boolean;
  /** Reference display range; null means the whole project. */
  time: [number, number] | null;
  /** When true the effect ignores `time` and is always active. */
  ignoreTimeSpan: boolean;
  params: Record<string, EffectValue>;
  /**
   * Effect order within each target's chain, from the reference `effectsOrder`.
   * Effects can be ordered differently on the global frame and on each layer.
   */
  orderByTarget: Record<string, number>;
}

/** Order of an effect in a target's chain; missing entries fall back to 0. */
export function effectOrder(effect: EffectInstance, target: string): number {
  return effect.orderByTarget[target] ?? effect.orderByTarget[GLOBAL_TARGET] ?? 0;
}

/** True when the effect feeds the whole composition. */
export function affectsGlobal(effect: EffectInstance): boolean {
  return effect.targets.includes(GLOBAL_TARGET);
}

/** True when the effect feeds `itemId`. */
export function affectsItem(effect: EffectInstance, itemId: string): boolean {
  return effect.targets.includes(itemId);
}

const param = (
  key: string,
  label: string,
  min: number,
  max: number,
  def: number,
  unit?: string,
  step?: number,
): EffectParam => ({ key, label, min, max, default: def, unit, step, kind: "number" });

const boolParam = (key: string, label: string, def: boolean): EffectParam => ({
  key,
  label,
  min: 0,
  max: 1,
  default: def,
  kind: "boolean",
});

const colorParam = (key: string, label: string, def: string): EffectParam => ({
  key,
  label,
  min: 0,
  max: 1,
  default: def,
  kind: "color",
});

const selectParam = (
  key: string,
  label: string,
  options: string[],
  def: string,
): EffectParam => ({
  key,
  label,
  min: 0,
  max: Math.max(1, options.length - 1),
  default: def,
  kind: "select",
  options,
});

/** A select whose options are the composition's layers plus "Screen". */
const layerParam = (key: string, label: string, def = "Screen"): EffectParam => ({
  key,
  label,
  min: 0,
  max: 1,
  default: def,
  kind: "layer",
});

const textParam = (key: string, label: string, def: string): EffectParam => ({
  key,
  label,
  min: 0,
  max: 1,
  default: def,
  kind: "text",
});

const imageParam = (key: string, label: string, def = ""): EffectParam => ({
  key,
  label,
  min: 0,
  max: 1,
  default: def,
  kind: "image",
});

/** Reference blend-mode keys (module 324), in the same order as its options. */
export const BLEND_MODES = [
  "normal",
  "lighten",
  "darken",
  "multiply",
  "average",
  "add",
  "subtract",
  "divide",
  "difference",
  "negation",
  "exclusion",
  "screen",
  "lineardodge",
  "phoenix",
  "linearburn",
  "hue",
  "saturation",
  "color",
  "luminosity",
  "darkercolor",
  "lightercolor",
  "overlay",
  "softlight",
  "hardlight",
  "colordodge",
  "colorburn",
  "linearlight",
  "vividlight",
  "pinlight",
  "hardmix",
  "reflect",
  "glow",
] as const;

/** Implemented effects, with the parameters the composite pass actually reads. */
export const IMPLEMENTED_EFFECTS: EffectDefinition[] = [
  {
    type: "color-tint",
    name: "Color Tint",
    category: "Color",
    implemented: true,
    // Reference model: map luminance between two colours, then mix by amount.
    params: [
      param("amount", "Amount", 0, 1, 1, undefined, 0.01),
      param("weight", "Weight", 0, 3, 1, undefined, 0.01),
      boolParam("invert", "Invert", false),
      colorParam("mapBlackTo", "Map black to", "#000000"),
      colorParam("mapWhiteTo", "Map white to", "#ffffff"),
    ],
  },
  {
    type: "invert",
    name: "Invert",
    category: "Color",
    implemented: true,
    params: [param("strength", "Strength", 0, 1, 1, undefined, 0.01)],
  },
  {
    type: "pixelate",
    name: "Pixelate",
    category: "Stylize",
    implemented: true,
    params: [param("amount", "Amount", 1, 100, 12, undefined, 0.1)],
  },
  {
    type: "chromatic-aberration",
    name: "Chromatic aberration",
    category: "Color",
    implemented: true,
    params: [
      param("x", "X offset", -200, 200, 4, "px", 0.1),
      param("y", "Y offset", -200, 200, 0, "px", 0.1),
    ],
  },
  {
    type: "box-blur",
    name: "Box blur",
    category: "Blur",
    implemented: true,
    params: [
      param("radius", "Radius", 0, 50, 3, "px", 0.1),
      param("nrPasses", "Passes", 1, 10, 1, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy module 316.
    type: "render",
    name: "Render",
    category: "Other",
    implemented: true,
    params: [param("opa", "Opacity", 0, 1, 1, undefined, 0.01)],
  },
  {
    // Decompiled from Vizzy's two-pass blur base class.
    type: "two-pass-blur",
    name: "Two Pass Blur",
    category: "Blur",
    implemented: true,
    params: [
      param("amount", "Amount", 0, 100, 20, undefined, 1),
      param("nrPasses", "Passes", 1, 10, 1, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy module 1294.
    type: "blur-triangle",
    name: "Blur Triangle",
    category: "Blur",
    implemented: true,
    params: [param("amount", "Amount", 0, 200, 50, undefined, 1)],
  },
  {
    // Decompiled from Vizzy's VHS effect class and shader.
    type: "vhs",
    name: "VHS",
    category: "Stylize",
    implemented: true,
    params: [],
  },
  {
    // Decompiled from Vizzy's Time Stop effect class (module 053e).
    type: "time-stop",
    name: "Time stop",
    category: "Motion",
    implemented: true,
    params: [
      param("frameSkip", "Frame skip", 0, 60, 1, undefined, 1),
      param("delaySeconds", "Delay", 0, 5, 0, undefined, 0.1),
    ],
  },
  {
    // Decompiled from Vizzy module 1297 (FidelityFX FSR/CAS).
    type: "fidelityfx-cas",
    name: "FidelityFX CAS",
    category: "Stylize",
    implemented: true,
    params: [
      param("contrastAmt", "Contrast", 0, 2, 1, undefined, 0.01),
      param("sharpeningAmt", "Sharpness", 0, 2, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1320.
    type: "liquify",
    name: "Liquify",
    category: "Distortion",
    implemented: true,
    params: [
      param("intensity", "Intensity", -200, 200, 50, undefined, 1),
      param("control", "Control", -1000, 1000, 0, undefined, 1),
      param("zoom", "Zoom", -50, 50, 5, undefined, 0.1),
      param("complexity", "Complexity", 0, 100, 8, undefined, 0.1),
      param("scalDiv", "Noise scale", 0.01, 100, 40, undefined, 0.01),
      param("blobs", "Blobs", 0, 100, 0, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy module 1314.
    type: "gradient-map",
    name: "Gradient map",
    category: "Color",
    implemented: true,
    params: [
      selectParam(
        "paletteSource",
        "Palette source",
        ["Manual gradient", "Image", "Layer"],
        "Manual gradient",
      ),
      textParam("gradientStops", "Gradient stops", "0.0:#000000,1.0:#FFFFFF"),
      imageParam("imageSrc", "Palette image"),
      layerParam("targetLayer", "Palette layer"),
      param("strength", "Strength", 0, 1, 1, undefined, 0.01),
      boolParam("invert", "Invert", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1300.
    type: "chroma-shift",
    name: "Chroma Shift",
    category: "Color",
    implemented: true,
    params: [
      param("intensity", "Intensity", 0, 1, 1, undefined, 0.01),
      param("timeSpeed", "Shift speed", 0, 2, 0.5, undefined, 0.01),
      param("timeOffset", "Time offset", 0, 1, 0, undefined, 0.01),
      param("colorFrequency", "Color frequency", 0.1, 2, 0.7, undefined, 0.1),
      param("posterizationLevels", "Posterization levels", 2, 32, 32, undefined, 1),
      selectParam("colorPalette", "Color palette", ["1", "2", "3", "4", "5", "6"], "6"),
    ],
  },
  {
    // Decompiled from Vizzy module 1325.
    type: "premultiply-alpha",
    name: "Premultiply alpha",
    category: "Blending",
    implemented: true,
    params: [boolParam("demultiply", "De-multiply", false)],
  },
  {
    // Decompiled from Vizzy module 1339 and the JFA distance-field core.
    type: "distance-field",
    name: "Distance Field",
    category: "Stylize",
    implemented: true,
    params: [
      param("maxDistance", "Max distance", 1, 500, 100, undefined, 1),
      selectParam("visualizationMode", "Visualization", ["grayscale", "heatmap", "rainbow"], "grayscale"),
      boolParam("invertField", "Invert field", false),
      boolParam("normalizeField", "Normalize field", true),
      param("fieldOpacity", "Opacity", 0, 1, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1284 and the JFA distance-field core.
    type: "advanced-outline",
    name: "Advanced Outline",
    category: "Advanced Outline",
    implemented: true,
    params: [
      colorParam("outlineColor", "Outline color", "#ff0000"),
      param("outlineThreshLow", "Inner threshold", 0, 500, 1, undefined, 0.5),
      param("outlineThreshHigh", "Outer threshold", 1, 500, 25, undefined, 0.5),
      param("outlineOpacity", "Opacity", 0, 1, 1, undefined, 0.01),
      boolParam("outlineOnly", "Outline only", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1285 and the JFA distance-field core.
    type: "advanced-shadow",
    name: "Advanced Shadow",
    category: "Advanced Shadow",
    implemented: true,
    params: [
      colorParam("shadowColor", "Shadow color", "#000000"),
      param("shadowOpacity", "Opacity", 0, 1, 0.35, undefined, 0.01),
      param("shadowOffsetX", "Offset X", -100, 100, 0, undefined, 0.5),
      param("shadowOffsetY", "Offset Y", -100, 100, 0, undefined, 0.5),
      param("shadowSize", "Size", 1, 100, 50, undefined, 1),
      param("shadowSpread", "Spread", -100, 100, 0, undefined, 1),
      boolParam("shadowOnly", "Shadow only", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1341 and shader module 583.
    type: "glitch",
    name: "Glitch",
    category: "Stylize",
    implemented: true,
    params: [
      param("amount", "Amount", 0, 10, 0.5, undefined, 0.01),
      param("threshold", "Threshold", 0, 1, 0.5, undefined, 0.01),
      param("displacementAmount", "Displacement amount", 0, 3, 1, undefined, 0.01),
      param("snowAmount", "Snow amount", 0, 3, 0.3, undefined, 0.01),
      param("dt_size", "Noise size", 0, 256, 64, undefined, 1),
      boolParam("randomTrigger", "Random trigger", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1336.
    type: "vhs2",
    name: "VHS2",
    category: "Stylize",
    implemented: true,
    params: [
      param("scanlineStrength", "Scanline noise", 0, 2, 1, undefined, 0.01),
      param("noiseStrength", "Static noise", 0, 2, 0.5, undefined, 0.01),
      param("bloomStrength", "Bloom", 0, 10, 5, undefined, 0.01),
      param("distortionStrength", "Distortion", 0, 10, 1, undefined, 0.01),
      param("noiseSpeed", "Noise speed", 0, 10, 10, undefined, 0.001),
      param("clarity", "Clarity", -1, 1, -0.5, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy's outline effect class and shader.
    type: "outline",
    name: "Outline",
    category: "Advanced Outline",
    implemented: true,
    params: [
      colorParam("outlineColor", "Outline color", "#000000"),
      param("outlineThickness", "Thickness", 0, 50, 1, undefined, 1),
      param("outlineOpacity", "Opacity", 0, 1, 1, undefined, 0.01),
      boolParam("outlineOnly", "Outline only", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1340.
    type: "drop-shadow",
    name: "Drop shadow",
    category: "Advanced Shadow",
    implemented: true,
    params: [
      param("offsetX", "Offset X", -20, 20, 4, undefined, 1),
      param("offsetY", "Offset Y", -20, 20, 4, undefined, 1),
      param("opacity", "Opacity", 0, 1, 0.35, undefined, 0.01),
      colorParam("color", "Color", "#000000"),
      param("spread", "Spread", 0, 100, 0, undefined, 1),
      param("size", "Size", 0, 20, 5, undefined, 0.1),
      param("steps", "Steps", 0, 25, 10, undefined, 1),
      boolParam("isInner", "Inner shadow", false),
      boolParam("shadowOnly", "Shadow only", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1334.
    type: "streak-glow",
    name: "Streak Glow",
    category: "Lighting",
    implemented: true,
    params: [
      param("range", "Range", 0, 1, 0.1, undefined, 0.01),
      param("_steps", "Steps", 0.005, 0.1, 0.005, undefined, 0.001),
      param("threshold", "Threshold", 0, 1, 0.6, undefined, 0.01),
      param("brightness", "Brightness", 0, 10, 5, undefined, 0.1),
      param("numRays", "Number of rays", 1, 100, 4, undefined, 1),
      param("angleOffset", "Angle offset", -Math.PI, Math.PI, Math.PI / 4, undefined, 0.01),
      boolParam("renderInputOnTop", "Render input on top", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1322.
    type: "morphing-fractal",
    name: "Morphing fractal",
    category: "Stylize",
    implemented: true,
    params: [
      param("iterations", "Iterations", 1, 100, 100, undefined, 1),
      param("twirl", "Twirl", 0, 5, 0.002, undefined, 0.001),
      param("friction", "Friction", 0.1, 10, 3, undefined, 0.01),
      param("x", "Anchor X", -1, 1, 0.5, undefined, 0.001),
      param("y", "Anchor Y", -1, 1, 0.5, undefined, 0.001),
      colorParam("morphColor", "Morph color", "#ffffff"),
      param("timeOffset", "Time offset", 0, 10, 0, undefined, 0.01),
      param("baseTimeRate", "Time rate", -10, 10, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1306.
    type: "displacement",
    name: "Displacement",
    category: "Distortion",
    implemented: true,
    params: [
      boolParam("useImageTexture", "Use image texture", false),
      imageParam("imageSrc", "Displacement image"),
      layerParam("targetLayer", "Target layer"),
      boolParam("normalsMode", "Use normals", false),
      param("displacementX", "Displacement X", 0, 1, 0.1, undefined, 0.01),
      param("displacementY", "Displacement Y", 0, 1, 0.1, undefined, 0.01),
      param("texScale", "Texture scale", 0, 10, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1316.
    type: "image-mask",
    name: "Image Mask",
    category: "Other",
    implemented: true,
    params: [
      boolParam("useImageTexture", "Use image texture", true),
      imageParam("imageSrc", "Mask image"),
      layerParam("targetLayer", "Target layer"),
    ],
  },
  {
    // Decompiled from Vizzy module 1333.
    type: "spooky",
    name: "Spooky",
    category: "Stylize",
    implemented: true,
    params: [
      param("distortion", "Distortion", 0, 100, 25, undefined, 1),
      param("width", "Spread", 0, 1, 0.02, undefined, 0.01),
      param("speed", "Speed", 0, 1, 0.05, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1317.
    type: "impact-ripple",
    name: "Impact Ripple",
    category: "Distortion",
    implemented: true,
    params: [
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
      param("waveFrequency", "Wave frequency", 0.1, 50, 10, undefined, 0.1),
      param("waveAmplitude", "Wave amplitude", 0.1, 2, 0.8, undefined, 0.05),
      param("waveWidth", "Wave width", 0, 10, 1, undefined, 0.01),
      param("brightnessMultiplier", "Brightness multiplier", -2, 2, 1, undefined, 0.1),
      boolParam("manualControl", "Manual control", false),
      param("manualProgression", "Manual progression", 0, 1, 0, undefined, 0.01),
      param("autoFrequency", "Auto frequency", 0.1, 10, 1, undefined, 0.1),
    ],
  },
  {
    // Decompiled from Vizzy module 1327.
    type: "render-layer",
    name: "Render layer",
    category: "Other",
    implemented: true,
    params: [layerParam("targetLayer", "Target layer")],
  },
  {
    // Decompiled from Vizzy module 1328.
    type: "repeating-ripple",
    name: "Repeating Ripple",
    category: "Distortion",
    implemented: true,
    params: [
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
      param("distortionIntensity", "Distortion intensity", 0, 0.1, 0.02, undefined, 0.001),
      param("animationSpeed", "Animation speed", 0, 10, 4, undefined, 0.1),
      param("waveFrequency", "Wave frequency", 1, 50, 12, undefined, 0.5),
    ],
  },
  {
    // Decompiled from Vizzy module 1329.
    type: "rgb-displace",
    name: "RGB displace",
    category: "Color",
    implemented: true,
    params: [
      param("displaceRX", "Red X", -100, 100, 10, undefined, 0.1),
      param("displaceRY", "Red Y", -100, 100, 0, undefined, 0.1),
      param("scaleR", "Red scale", 0, 4, 1, undefined, 0.1),
      param("displaceGX", "Green X", -100, 100, 0, undefined, 0.1),
      param("displaceGY", "Green Y", -100, 100, 0, undefined, 0.1),
      param("scaleG", "Green scale", 0, 4, 1, undefined, 0.1),
      param("displaceBX", "Blue X", -100, 100, -10, undefined, 0.1),
      param("displaceBY", "Blue Y", -100, 100, 0, undefined, 0.1),
      param("scaleB", "Blue scale", 0, 4, 1, undefined, 0.1),
    ],
  },
  {
    // Decompiled from Vizzy module 1330.
    type: "scale",
    name: "Scale",
    category: "Distortion",
    implemented: true,
    params: [
      param("scaleX", "Scale X", 0, 4, 1.5, undefined, 0.01),
      param("scaleY", "Scale Y", 0, 4, 1.5, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1298.
    type: "channel-blur",
    name: "Channel blur",
    category: "Blur",
    implemented: true,
    params: [
      param("redBlur", "Red blur", 0, 50, 5, undefined, 0.1),
      param("greenBlur", "Green blur", 0, 50, 3, undefined, 0.1),
      param("blueBlur", "Blue blur", 0, 50, 1, undefined, 0.1),
    ],
  },
  {
    // Decompiled from Vizzy module 1313.
    type: "god-rays",
    name: "God rays",
    category: "Lighting",
    implemented: true,
    params: [
      param("rayCenterX", "Ray center X", -1, 1, 0, undefined, 0.01),
      param("rayCenterY", "Ray center Y", -1, 1, 0, undefined, 0.01),
      param("decay", "Decay multiplier", 0, 1, 0.9, undefined, 0.01),
      param("density", "Density", 0, 1, 1, undefined, 0.01),
      param("weight", "Weight", 0, 1, 0.58767, undefined, 0.01),
      param("nsamples", "Sample count", 1, 100, 50, undefined, 1),
      param("alphaMult", "Godrays alpha", 0, 3, 1, undefined, 0.01),
      param("saturationMult", "Godrays saturation", 0, 3, 1, undefined, 0.01),
      param("threshold", "Godrays threshold", 0, 1, 0, undefined, 0.01),
      boolParam("ignoreDark", "Ignore dark colors", false),
      boolParam("renderInputOnTop", "Render input on top", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1299.
    type: "chroma-key",
    name: "Chroma key",
    category: "Color",
    implemented: true,
    params: [
      colorParam("keyColor", "Key color", "#00ff00"),
      param("colorCutoff", "Color cutoff", 0, 1, 0.2, undefined, 0.01),
      param("colorFeathering", "Color feathering", 0, 1, 0.33, undefined, 0.01),
      param("despillAmt", "Despill amount", 0, 1, 1, undefined, 0.01),
      param("despillLuminanceAdd", "Despill luminance add", 0, 1, 0.2, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1307.
    type: "edge-detection",
    name: "Edge detection",
    category: "Stylize",
    implemented: true,
    params: [
      selectParam("edgeMode", "Edge mode", ["Sobel", "Laplacian", "Prewitt", "Roberts Cross"], "Sobel"),
      param("strength", "Strength", 0, 25, 10, undefined, 0.1),
      param("threshold", "Threshold", 0, 1, 0, undefined, 0.01),
      param("thickness", "Thickness", 0.1, 20, 3, undefined, 0.1),
      param("opacity", "Opacity", 0, 1, 1, undefined, 0.01),
      colorParam("color", "Edge color", "#ffffff"),
      boolParam("useOriginalColor", "Use original color", true),
      boolParam("maskToAlpha", "Mask to alpha", true),
      boolParam("overlay", "Overlay", false),
      param("sourceOpacity", "Source opacity", 0, 1, 1, undefined, 0.01),
      boolParam("invert", "Invert", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1311.
    type: "fxaa",
    name: "FXAA",
    category: "Other",
    implemented: true,
    params: [
      param("reduceMin", "Minimum reduction factor", 8, 1024, 8, undefined, 2),
      param("reduceMax", "Maximum reduction factor", 1, 10, 1, undefined, 0.1),
      param("spanMax", "Maximum span", 0, 25, 8, undefined, 0.1),
    ],
  },
  {
    // Decompiled from Vizzy's _GLOW alias of the Bloom effect.
    type: "glow-bloom",
    name: "Glow",
    category: "Lighting",
    implemented: true,
    params: [
      param("strength", "Strength", 0, 10, 1, undefined, 0.01),
      param("threshold", "Threshold", 0, 1, 0, undefined, 0.01),
      param("radius", "Radius", 0, 1, 0.1, undefined, 0.01),
      boolParam("renderBaseTexture", "Render base", false),
      boolParam("renderBaseAdditive", "Additive", true),
    ],
  },
  {
    // Decompiled from Vizzy module 1287 and shader modules 1288/252.
    type: "bloom",
    name: "Bloom",
    category: "Lighting",
    implemented: true,
    params: [
      param("strength", "Strength", 0, 10, 1, undefined, 0.01),
      param("threshold", "Threshold", 0, 1, 0, undefined, 0.01),
      param("radius", "Radius", 0, 1, 0.1, undefined, 0.01),
      boolParam("renderBaseTexture", "Render base", false),
      boolParam("renderBaseAdditive", "Additive", true),
    ],
  },
  {
    type: "alpha",
    name: "Alpha",
    category: "Other",
    implemented: true,
    params: [param("alpha", "Alpha", 0, 100, 100, "%")],
  },
  {
    // Decompiled from Vizzy module 1315: grayscale mixes the source toward its
    // RGB average; amount is 0..100 in the inspector.
    type: "gray-scale",
    name: "Gray scale",
    category: "Color",
    implemented: true,
    params: [param("amount", "Amount", 0, 100, 50, "%")],
  },
  {
    // Decompiled from Vizzy module 1310. The reference exposes all eight
    // controls; darken is a boolean.
    type: "flicker",
    name: "Flicker",
    category: "Motion",
    implemented: true,
    params: [
      param("amplitudeBrightness", "Brightness Amplitude", 0, 2, 1),
      param("frequencyBrightness", "Brightness Frequency", 0, 15, 7),
      param("amplitudeColor", "Color amplitude", 0, 2, 0.5),
      param("frequencyColor", "Color frequency", 0, 15, 4),
      param("seedColor", "Color seed", 0, 1000, 123),
      param("brightness", "Brightness", 0, 1, 1),
      param("contrast", "Contrast", 0, 1, 1),
      boolParam("darken", "Darken", true),
    ],
  },
  {
    // Decompiled from Vizzy module 1331.
    type: "sepia",
    name: "Sepia",
    category: "Color",
    implemented: true,
    params: [param("amount", "Amount", 0, 100, 20)],
  },
  {
    // Decompiled from Vizzy module 1305.
    type: "directional-blur",
    name: "Directional blur",
    category: "Blur",
    implemented: true,
    params: [
      param("amount", "Blur Amount", 0, 200, 5, undefined, 0.5),
      param("angle", "Direction", 0, 360, 0, undefined, 1),
      param("samples", "Samples", 5, 64, 15, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy module 1326.
    type: "radial-blur",
    name: "Radial blur",
    category: "Blur",
    implemented: true,
    params: [
      param("amount", "Blur Amount", 0, 50, 10, undefined, 1),
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
      param("samples", "Samples", 4, 64, 16, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy modules 457 and 458.
    type: "horizontal-blur",
    name: "Horizontal blur",
    category: "Blur",
    implemented: true,
    params: [param("amount", "Amount", 0, 200, 1, undefined, 0.1)],
  },
  {
    type: "vertical-blur",
    name: "Vertical blur",
    category: "Blur",
    implemented: true,
    params: [param("amount", "Amount", 0, 200, 1, undefined, 0.1)],
  },
  {
    // Decompiled from Vizzy module 1312.
    type: "glow",
    name: "Glow2",
    category: "Lighting",
    implemented: true,
    params: [
      colorParam("glowColor", "Color", "#4f2eb2"),
      param("distance", "Distance", 0, 100, 15, undefined, 0.1),
      param("outerStrength", "Outer glow", 0, 20, 2, undefined, 0.1),
      param("innerStrength", "Inner glow", 0, 20, 0, undefined, 0.1),
      param("xSpread", "Spread X", 0, 100, 50, undefined, 1),
      param("ySpread", "Spread Y", 0, 100, 50, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy modules 582 (transform) and 494 (shader).
    type: "camera-shake",
    name: "Camera Shake",
    category: "Motion",
    implemented: true,
    params: [
      param("amplitudeX", "Amplitude X", 0, 30, 8, undefined, 0.1),
      param("amplitudeY", "Amplitude Y", 0, 30, 8, undefined, 0.1),
      param("rotation", "Rotation", 0, 30, 2, undefined, 0.1),
      param("frequency", "Frequency", 0, 10, 1.5, undefined, 0.01),
      param("octaves", "Octaves", 1, 5, 1, undefined, 1),
      boolParam("autoScale", "Auto scale", true),
      param("preScale", "Pre scale", 0, 1, 1, undefined, 0.01),
      selectParam("textureWrap", "Texture wrap", ["Repeat", "Clamp", "Discard"], "Discard"),
      selectParam("repeatType", "Reverse mirror", ["Default", "Vertical", "Horizontal", "Both", "Either"], "Default"),
      boolParam("useMotionBlur", "Motion blur", false),
      param("motionBlurLength", "Blur spread", 0, 20, 5, undefined, 0.1),
      param("motionBlurIterations", "Blur copies", 1, 100, 8, undefined, 1),
      boolParam("useRgbSplit", "RGB split", false),
      param("rgbSplitLength", "Split length", 0, 100, 1, undefined, 1),
    ],
  },
  {
    // Decompiled from Vizzy module 1291 (shader) and the Transform effect class.
    type: "transform",
    name: "Transform",
    category: "Motion",
    implemented: true,
    params: [
      param("matPositionX", "Position X", -2, 2, 0, undefined, 0.01),
      param("matPositionY", "Position Y", -2, 2, 0, undefined, 0.01),
      param("matScaleX", "Scale X", 0, 4, 1, undefined, 0.01),
      param("matScaleY", "Scale Y", 0, 4, 1, undefined, 0.01),
      param("matRotation", "Warp rotation", -1000, 1000, 0, "°", 1),
      param("alpha", "Alpha multiplier", 0, 1, 1, undefined, 0.01),
      selectParam("textureWrap", "Texture wrap", ["Repeat", "Clamp", "Discard"], "Discard"),
      selectParam("repeatType", "Reverse mirror", ["Default", "Horizontal", "Vertical", "Both", "Either"], "Default"),
      boolParam("useMotionBlur", "Motion blur", false),
      param("motionBlurLength", "Blur spread", 0, 20, 8, undefined, 0.1),
      param("motionBlurIterations", "Blur copies", 1, 100, 8, undefined, 1),
      layerParam("targetLayer", "Blend with"),
      selectParam("blendEquation", "Blend equation", ["Add", "Subtract", "Reverse subtract", "Min", "Max"], "Add"),
      selectParam(
        "srcBlending",
        "Source blend factor",
        [
          "Zero",
          "One",
          "SrcColor",
          "OneMinusSrcColor",
          "SrcAlpha",
          "OneMinusSrcAlpha",
          "DstAlpha",
          "OneMinusDstAlpha",
          "DstColor",
          "OneMinusDstColor",
        ],
        "One",
      ),
      selectParam(
        "dstBlending",
        "Destination blend factor",
        [
          "Zero",
          "One",
          "SrcColor",
          "OneMinusSrcColor",
          "SrcAlpha",
          "OneMinusSrcAlpha",
          "DstAlpha",
          "OneMinusDstAlpha",
          "DstColor",
          "OneMinusDstColor",
        ],
        "OneMinusSrcAlpha",
      ),
    ],
  },
  {
    // Decompiled from Vizzy module 1319.
    type: "kaleidoscope",
    name: "Kaleidoscope",
    category: "Stylize",
    implemented: true,
    params: [
      param("segments", "Segments", 1, 30, 1, undefined, 1),
      param("offset", "Offset", 0, 400, 0, undefined, 1),
      boolParam("preserveAspect", "Preserve aspect ratio", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1304.
    type: "crop",
    name: "Crop",
    category: "Other",
    implemented: true,
    params: [
      param("tCrop", "Top", 0, 100, 10, undefined, 1),
      param("bCrop", "Bottom", 0, 100, 10, undefined, 1),
      param("lCrop", "Left", 0, 100, 10, undefined, 1),
      param("rCrop", "Right", 0, 100, 10, undefined, 1),
      boolParam("invertCrop", "Inner crop", false),
      boolParam("clampEdges", "Clamp edges", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1335.
    type: "twirl",
    name: "Twirl",
    category: "Distortion",
    implemented: true,
    params: [
      param("amount", "Amount", 0, 5, 2.5, undefined, 0.1),
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1332.
    type: "skew",
    name: "Skew",
    category: "Distortion",
    implemented: true,
    params: [
      param("skewX", "Skew X", -2, 2, 0, undefined, 0.01),
      param("skewY", "Skew Y", -2, 2, 0, undefined, 0.01),
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1321.
    type: "mirror",
    name: "Mirror",
    category: "Stylize",
    implemented: true,
    params: [
      param("pos", "Position", 0, 1, 0.5, undefined, 0.01),
      boolParam("left", "Mirror left", true),
      boolParam("right", "Mirror right", false),
      boolParam("top", "Mirror top", false),
      boolParam("bottom", "Mirror bottom", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1309.
    type: "fisheye-2",
    name: "Fish eye 2",
    category: "Distortion",
    implemented: true,
    params: [
      param("a", "Horizontal", 0, 4, 2, undefined, 0.01),
      param("b", "Vertical", 0, 4, 3, undefined, 0.01),
      param("F", "Curvature", 0, 4, 3, undefined, 0.01),
      param("scale", "Scale", 0, 4, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1308.
    type: "fisheye",
    name: "Fish eye",
    category: "Distortion",
    implemented: true,
    params: [
      param("amount", "Amount", -10, 40, 1, undefined, 0.01),
      param("preScale", "Pre scale", -10, 10, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1324.
    type: "polar-coordinates",
    name: "Polar Coordinates",
    category: "Distortion",
    implemented: true,
    params: [param("curvature", "Curvature", -1, 1, 1, undefined, 0.01)],
  },
  {
    // Decompiled from Vizzy module 1296.
    type: "bulge-pinch",
    name: "Bulge/Pinch",
    category: "Distortion",
    implemented: true,
    params: [
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
      param("radius", "Radius", 0, 1, 0.25, undefined, 0.01),
      param("strength", "Strength", -1, 1, 0.5, undefined, 0.01),
      param("smoothEdge", "Smooth edge", 0, 1, 0.01, undefined, 0.01),
    ],
  },
  {
    // Decompiled from the Tilt shift class and its horizontal/vertical passes.
    type: "tilt-shift",
    name: "Tilt shift",
    category: "Blur",
    implemented: true,
    params: [
      param("amount", "Amount", 0, 100, 20, undefined, 1),
      param("nrPasses", "Passes", 1, 10, 1, undefined, 1),
      param("focusPosition", "Focus position", 0, 1, 0.5, undefined, 0.01),
      param("focusRange", "Focus range", 0, 1, 0.1, undefined, 0.01),
      param("rotation", "Rotation", 0, 360, 0, "°", 1),
    ],
  },
  {
    // Decompiled from Vizzy module 1338.
    type: "zoom-blur",
    name: "Zoom blur",
    category: "Blur",
    implemented: true,
    params: [
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
      param("strength", "Strength", 0, 10, 1, undefined, 0.1),
      param("innerRadius", "Inner radius", 0, 1000, 50, undefined, 1),
      param("passes", "Passes", 0, 100, 25, undefined, 1),
      param("gradientLength", "Gradient length", 0, 10, 5, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy module 1286 and the blend-mode shader in module 324.
    type: "blending",
    name: "Blending",
    category: "Blending",
    implemented: true,
    params: [
      layerParam("blendWith", "Blend with"),
      selectParam("blendFunc", "Blend mode", [...BLEND_MODES], "normal"),
      param("blendGamma", "Blend gamma", 0, 4, 2.2, undefined, 0.01),
      param("opacity", "Opacity", 0, 1, 1, undefined, 0.01),
    ],
  },
  {
    // Decompiled from Vizzy modules 496 (shader) and the Trail effect class.
    type: "trail",
    name: "Trail",
    category: "Motion",
    implemented: true,
    params: [param("amount", "Amount", 0, 1, 0.5, undefined, 0.01)],
  },
  {
    // Decompiled from Vizzy module 1295 (custom aperture texture omitted).
    type: "bokeh-blur",
    name: "Bokeh blur",
    category: "Blur",
    implemented: true,
    params: [
      param("amount", "Blur Amount", 0, 50, 10, undefined, 1),
      param("bokehScale", "Bokeh Scale", 0.1, 3, 1, undefined, 0.1),
      selectParam("shapeType", "Aperture Shape", ["Circle", "Hexagon", "Star"], "Circle"),
      param("samples", "Samples", 8, 24, 24, undefined, 1),
      selectParam("smoothMode", "Smooth mode", ["Grainy", "Smooth"], "Grainy"),
      boolParam("useCustomTexture", "Use custom aperture", false),
      imageParam("imageSrc", "Custom aperture image"),
    ],
  },
  {
    // Decompiled from Vizzy module 1337.
    type: "vignette",
    name: "Vignette",
    category: "Stylize",
    implemented: true,
    params: [
      param("size", "Size", 0, 1, 0.5, undefined, 0.01),
      param("smoothness", "Smoothness", 0, 2, 0.5, undefined, 0.01),
      param("roundness", "Roundness", 0.1, 5, 1, undefined, 0.01),
      param("centerX", "Center X", 0, 1, 0.5, undefined, 0.01),
      param("centerY", "Center Y", 0, 1, 0.5, undefined, 0.01),
      colorParam("vignetteColor", "Color", "#000000"),
      param("opacity", "Opacity", 0, 1, 1, undefined, 0.01),
      param("dither", "Dither noise", 0, 1, 0.1, undefined, 0.01),
      boolParam("moveNoise", "Animate noise", false),
      boolParam("useAlpha", "Transparent", false),
      boolParam("useScreenAspect", "Use screen aspect ratio", false),
    ],
  },
  {
    // Decompiled from Vizzy module 1302.
    type: "color-correction",
    name: "Color correction",
    category: "Color",
    implemented: true,
    params: [
      param("brightness", "Brightness", 0, 2, 1, undefined, 0.01),
      param("contrast", "Contrast", 0, 2, 1, undefined, 0.01),
      param("hueAmount", "Hue rotation", 0, 360, 0, undefined, 1),
      param("vibrance", "Vibrance", -10, 10, 0, undefined, 0.01),
      param("saturation", "Saturation", 0, 10, 1, undefined, 0.01),
      param("shadows", "Shadows", 0, 10, 0, undefined, 0.01),
      param("highlights", "Highlights", 0, 1, 0, undefined, 0.01),
      boolParam("invert", "Invert", false),
      param("addR", "Red add", -1, 1, 0, undefined, 0.01),
      param("mulR", "Red multiply", 0, 10, 1, undefined, 0.01),
      param("addG", "Green add", -1, 1, 0, undefined, 0.01),
      param("mulG", "Green multiply", 0, 10, 1, undefined, 0.01),
      param("addB", "Blue add", -1, 1, 0, undefined, 0.01),
      param("mulB", "Blue multiply", 0, 10, 1, undefined, 0.01),
    ],
  },
];

/** Catalogue entries without implementations yet, so the browser is complete. */
const CATALOGUE_ONLY: Array<[string, EffectCategory]> = [
  ["Alpha", "Other"],
  ["Advanced Outline", "Advanced Outline"],
  ["Advanced Shadow", "Advanced Shadow"],
  ["Blending", "Blending"],
  ["Bokeh blur", "Blur"],
  ["Bulge/Pinch", "Distortion"],
  ["Camera Shake", "Motion"],
  ["Channel blur", "Blur"],
  ["Chroma key", "Color"],
  ["Chroma Shift", "Color"],
  ["Color correction", "Color"],
  ["Crop", "Other"],
  ["Directional blur", "Blur"],
  ["Displacement", "Distortion"],
  ["Distance Field", "Stylize"],
  ["Edge detection", "Stylize"],
  ["FidelityFX CAS", "Stylize"],
  ["Flicker", "Motion"],
  ["FXAA", "Other"],
  ["Glitch", "Stylize"],
  ["God rays", "Lighting"],
  ["Gradient map", "Color"],
  ["Gray scale", "Color"],
  ["Horizontal blur", "Blur"],
  ["Impact Ripple", "Distortion"],
  ["Kaleidoscope", "Stylize"],
  ["Liquify", "Distortion"],
  ["Mirror", "Stylize"],
  ["Morphing fractal", "Stylize"],
  ["Polar Coordinates", "Distortion"],
  ["Premultiply alpha", "Blending"],
  ["Radial blur", "Blur"],
  ["Render layer", "Other"],
];

export const EFFECT_CATALOGUE: EffectDefinition[] = [
  ...IMPLEMENTED_EFFECTS,
  ...CATALOGUE_ONLY.map(([name, category]) => ({
    type: name.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
    name,
    category,
    implemented: false,
    params: [] as EffectParam[],
  })).filter((entry) => !IMPLEMENTED_EFFECTS.some((item) => item.type === entry.type)),
];

export const EFFECT_CATEGORIES: EffectCategory[] = [
  "Color",
  "Blending",
  "Other",
  "Blur",
  "Lighting",
  "Distortion",
  "Motion",
  "Stylize",
  "Advanced Outline",
  "Advanced Shadow",
];

export function definitionsFor(type: string): EffectDefinition | undefined {
  return EFFECT_CATALOGUE.find((definition) => definition.type === type);
}

export function createEffect(
  type: string,
  targets: readonly string[],
  idFactory: () => string,
): EffectInstance | null {
  const definition = definitionsFor(type);
  if (!definition || !definition.implemented) return null;
  const params: Record<string, EffectValue> = {};
  for (const spec of definition.params) params[spec.key] = spec.default;
  return {
    id: idFactory(),
    type: definition.type,
    name: definition.name,
    // Deduplicate: the same connection listed twice would render twice.
    targets: [...new Set(targets)],
    enabled: true,
    time: null,
    ignoreTimeSpan: true,
    params,
    orderByTarget: {},
  };
}
