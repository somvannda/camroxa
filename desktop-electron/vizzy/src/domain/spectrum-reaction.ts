/**
 * Spectrum audio reaction, modelled the way the reference editor does it.
 *
 * Decompiled reference (modules 415 `Spectrum`, 310 `SkiaItem`, 682 `AudioImpact`):
 *
 *  - `Spectrum.update()` only turns analyser bands into path heights. It never
 *    scales or rotates the item itself:
 *
 *      const a = n[o];
 *      let r = t.audioAnalyzerData[a.audioAnalyzer];
 *      if (!r) continue;
 *      r = r.map(e => e > a.ceiling ? a.ceiling : e);
 *      const {points: s} = Object(y.d)(r.slice(), i, a.multiplier * this.settings.spectrumHeight);
 *
 *  - The item's audio-driven movement is an `audioImpact` automation bound to a
 *    transform controller. `SkiaItem.preScaling()` is what consumes it:
 *
 *      i.scale(this.scaleX * this.scaleMultiplier, this.scaleY * this.scaleMultiplier),
 *      this.scaleToAspect || 1 === s || i.scale(1 / s, 1), i.rotate(this._rotation, 0, 0);
 *
 *    and the reference's own projects animate exactly those rows. A shipped
 *    template carries:
 *
 *      connections: { "item:Spectrum:<id>": ["scaleMultiplier"] }
 *      settings:    { name: "Spectrum Scale", minValue: 1, maxValue: 1.15,
 *                     floorValue: 0, ceilingValue: 3000, sensitivity: 0,
 *                     smoothing: 0, isCumulative: false, deltaSmoothing: false,
 *                     deltaDecay: 0.01, deltaThreshold: 0,
 *                     audioAnalyzer: "analyzer:default" }
 *
 *    Twelve of the 91 shipped templates drive `scaleMultiplier` this way,
 *    three drive `scaleX`/`scaleY`, and `rotation` rows appear on the same
 *    automation kind (e.g. Camera Shake). `bunny-ears` also wires a second
 *    audio-impact row into the first one's `sensitivity`, which is why that
 *    literal `sensitivity` is 0.
 *
 *  - The image variant is not special-cased. `drawCircleImage()` draws at
 *    `imageSize * curRad * 1.96` inside the same `preScaling()` transform:
 *
 *      const e = a * this.curRad * 1.96;
 *      ... s.drawImageRect(this.image, n, t, this.imagePaint, !1);
 *
 *    so an audio-driven `scaleMultiplier` zooms the artwork and the ring
 *    together; only the ring's height comes from bands (`curRad + t[0]`).
 *
 *  - Inspector rows (module 682 `createControllerSetups`), which our group
 *    mirrors below, are: `Min value` (-1000..1000), `Max value` (-1000..1000),
 *    `Lower limit` (0..5000, step 1), `Upper limit` (0..3000, step 1),
 *    `Sensitivity` (0..1), `Smoothing` (0..1), `Cumulative`,
 *    `Delta smooth`, `Delta amount` (0..1), `Delta threshold` (0..1) and the
 *    shared `Audio analyzer` row.
 */
import type { AudioImpactSettings } from "./types";
import {
  scaleMultiplierFromReference,
  scaleMultiplierToReference,
} from "./reference-scale";

/** Reference `POSITION_SIZE` rows a spectrum's audio impact can drive. */
export const SPECTRUM_REACTION_PROPERTIES = [
  { id: "transform.scaleMultiplier", label: "Scale multiplier" },
  { id: "transform.rotation", label: "Rotation" },
] as const;

export type SpectrumReactionProperty = (typeof SPECTRUM_REACTION_PROPERTIES)[number]["id"];

export const DEFAULT_SPECTRUM_REACTION_PROPERTY: SpectrumReactionProperty =
  "transform.scaleMultiplier";

export function isSpectrumReactionProperty(id: string): id is SpectrumReactionProperty {
  return SPECTRUM_REACTION_PROPERTIES.some((entry) => entry.id === id);
}

/**
 * What the inspector needs to render one item's reaction. `value` is the
 * automation's current output in display units (the reference's read-only
 * `Value` oscilloscope row).
 */
export interface SpectrumReactionView {
  automationId: string;
  propertyId: SpectrumReactionProperty;
  enabled: boolean;
  analyzerId: string;
  impact: AudioImpactSettings;
  value: number;
}

export type SpectrumReactionChange =
  /** `Enabled` row: create the automation the first time it is ticked. */
  | { kind: "enabled"; enabled: boolean }
  /** Which transform row this automation drives. */
  | { kind: "property"; propertyId: SpectrumReactionProperty }
  | { kind: "analyzer"; analyzerId: string }
  | { kind: "impact"; patch: Partial<AudioImpactSettings> }
  /** Remove the automation entirely (header action). */
  | { kind: "remove" };

/**
 * Display units for `minValue`/`maxValue`.
 *
 * The reference stores them in the driven controller's units: the item's
 * `scaleMultiplier` is a 1x factor (`min -5, max 5`), rotation is degrees. Our
 * scale controller is calibrated to the drawn size, so the percent it stores
 * round-trips through `reference-scale` to the reference factor.
 */
export function reactionDisplayValue(
  propertyId: SpectrumReactionProperty,
  controllerValue: number,
): number {
  return propertyId === "transform.scaleMultiplier"
    ? scaleMultiplierToReference(controllerValue)
    : controllerValue;
}

export function reactionControllerValue(
  propertyId: SpectrumReactionProperty,
  displayValue: number,
): number {
  return propertyId === "transform.scaleMultiplier"
    ? scaleMultiplierFromReference(displayValue)
    : displayValue;
}

/**
 * Defaults for a freshly created reaction. The shipped rows all keep
 * `floorValue 0`, `ceilingValue 3000`, `deltaDecay 0.01` and
 * `deltaThreshold 0`; the range is a small forward pump from where the item
 * currently sits (a 35% zoom for scale, 15 degrees for rotation).
 */
export function defaultSpectrumReactionImpact(
  propertyId: SpectrumReactionProperty,
  currentControllerValue: number,
): AudioImpactSettings {
  const min = currentControllerValue;
  const max =
    propertyId === "transform.scaleMultiplier"
      ? currentControllerValue * 1.35
      : currentControllerValue + 15;
  return {
    min,
    max,
    sensitivity: 1,
    smoothing: 0,
    floor: 0,
    ceiling: 3000,
    cumulative: false,
    deltaSmoothing: false,
    deltaDecay: 0.01,
    deltaThreshold: 0,
  };
}

/** The automation's current output, in display units. */
export function spectrumReactionValue(
  node: { referenceScaleMultiplier: number; readNumber(path: string): number },
  propertyId: SpectrumReactionProperty,
): number {
  return propertyId === "transform.scaleMultiplier"
    ? node.referenceScaleMultiplier
    : node.readNumber(propertyId);
}
