/**
 * Spectrum layers.
 *
 * Schema taken from the reference's project export: a Spectrum object owns N
 * layers, each with its own colour mode, transform, blur, shadow, analyzer and
 * enabled flag, keyed `spectrum_layer:<n>:<property>` in their values map.
 *
 * This module is the data scaffold for that model. The renderer still draws a
 * single layer today; wiring the array through the shader is the next slice.
 */

/**
 * The reference's layer colour modes. `From-to` mixes `colorFrom` -> `colorTo`
 * along `baseOn`; `Gradient` is our multi-stop variant.
 */
export type SpectrumColorType = "Solid" | "From-to" | "Gradient" | "Shader";

export interface SpectrumLayer {
  id: string;
  /** Amplitude scale applied to this layer. */
  multiplier: number;
  /** Upper clamp for band values. */
  ceiling: number;
  alpha: number;
  colorType: SpectrumColorType;
  color: string;
  colorFrom: string;
  colorTo: string;
  colorMix: number;
  colorGradient: string;
  /** What drives a `From-to` mix: Value, Y-Position, X-Position or distance. */
  baseOn: "Value" | "Y-Position" | "X-Position" | "Distance from center";
  /** Raw fragment shader source, used when colorType is "Shader". */
  shaderSrc: string;
  shadowAlpha: number;
  shadowColor: string;
  shadowScale: number;
  blurAmount: number;
  rotation: number;
  scale: number;
  enabled: boolean;
  /** Analyzer object driving this layer. */
  audioAnalyzer: string | null;
}

export function createSpectrumLayer(index: number, color = "#f72585"): SpectrumLayer {
  return {
    id: `spectrum_layer:${index}`,
    multiplier: 1,
    ceiling: 1000,
    alpha: 1,
    colorType: "Solid",
    color,
    colorFrom: "#FF0000",
    colorTo: "#000000",
    colorMix: 0.5,
    colorGradient: "#FF00FF:#FF00FF",
    baseOn: "Value",
    shaderSrc: "",
    shadowAlpha: 1,
    shadowColor: "#ffffff",
    shadowScale: 0.01,
    blurAmount: 0,
    rotation: 0,
    scale: 1,
    enabled: true,
    audioAnalyzer: null,
  };
}

/** Flatten a layer into the reference's `spectrum_layer:<n>:<property>` keys. */
export function serializeLayer(layer: SpectrumLayer, index: number): Record<string, unknown> {
  const prefix = `spectrum_layer:${index}`;
  return {
    [`${prefix}:multiplier`]: layer.multiplier,
    [`${prefix}:ceiling`]: layer.ceiling,
    [`${prefix}:alpha`]: layer.alpha,
    [`${prefix}:colorType`]: layer.colorType,
    [`${prefix}:color`]: layer.color,
    [`${prefix}:colorFrom`]: layer.colorFrom,
    [`${prefix}:colorTo`]: layer.colorTo,
    [`${prefix}:colorMix`]: layer.colorMix,
    [`${prefix}:colorGradient`]: layer.colorGradient,
    [`${prefix}:baseOn`]: layer.baseOn,
    [`${prefix}:shaderSrc`]: layer.shaderSrc,
    [`${prefix}:shadowAlpha`]: layer.shadowAlpha,
    [`${prefix}:shadowColor`]: layer.shadowColor,
    [`${prefix}:shadowScale`]: layer.shadowScale,
    [`${prefix}:blurAmount`]: layer.blurAmount,
    [`${prefix}:rotation`]: layer.rotation,
    [`${prefix}:scale`]: layer.scale,
    [`${prefix}:enabled`]: layer.enabled,
    [`${prefix}:audioAnalyzer`]: layer.audioAnalyzer,
  };
}

/** Read the reference's flat keys back into layers, for project imports. */
export function deserializeLayers(values: Record<string, unknown>): SpectrumLayer[] {
  const indexes = new Set<number>();
  for (const key of Object.keys(values)) {
    const match = key.match(/^spectrum_layer:(\d+):/);
    if (match) indexes.add(Number(match[1]));
  }
  return [...indexes]
    .sort((a, b) => a - b)
    .map((index) => {
      const base = createSpectrumLayer(index);
      const read = <T>(property: string, fallback: T): T => {
        const value = values[`spectrum_layer:${index}:${property}`];
        return (value === undefined ? fallback : (value as T));
      };
      return {
        ...base,
        multiplier: read("multiplier", base.multiplier),
        ceiling: read("ceiling", base.ceiling),
        alpha: read("alpha", base.alpha),
        colorType: read("colorType", base.colorType),
        color: read("color", base.color),
        colorFrom: read("colorFrom", base.colorFrom),
        colorTo: read("colorTo", base.colorTo),
        colorMix: read("colorMix", base.colorMix),
        colorGradient: read("colorGradient", base.colorGradient),
        baseOn: read("baseOn", base.baseOn),
        shaderSrc: read("shaderSrc", base.shaderSrc),
        shadowAlpha: read("shadowAlpha", base.shadowAlpha),
        shadowColor: read("shadowColor", base.shadowColor),
        shadowScale: read("shadowScale", base.shadowScale),
        blurAmount: read("blurAmount", base.blurAmount),
        rotation: read("rotation", base.rotation),
        scale: read("scale", base.scale),
        enabled: read("enabled", base.enabled),
        audioAnalyzer: read("audioAnalyzer", base.audioAnalyzer),
      };
    });
}
