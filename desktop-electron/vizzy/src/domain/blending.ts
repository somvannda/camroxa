import * as THREE from "three";

/** Reference blend equation labels (Vizzy module 0 `e` enum). */
export const BLEND_EQUATIONS = [
  "Add",
  "Subtract",
  "Reverse subtract",
  "Min",
  "Max",
] as const;

/** Reference blend factor labels (Vizzy module 0 `f` enum). */
export const BLEND_FACTORS = [
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
] as const;

export const BLEND_EQUATION_VALUES: Record<string, THREE.BlendingEquation> = {
  Add: THREE.AddEquation,
  Subtract: THREE.SubtractEquation,
  "Reverse subtract": THREE.ReverseSubtractEquation,
  Min: THREE.MinEquation,
  Max: THREE.MaxEquation,
};

/**
 * The reference maps SrcColor and OneMinusDstAlpha onto the SrcAlpha factors;
 * keep that quirk so blending matches exactly.
 */
export const BLEND_FACTOR_VALUES: Record<string, THREE.BlendingDstFactor> = {
  Zero: THREE.ZeroFactor,
  One: THREE.OneFactor,
  SrcColor: THREE.SrcAlphaFactor,
  OneMinusSrcColor: THREE.OneMinusSrcColorFactor,
  SrcAlpha: THREE.SrcAlphaFactor,
  OneMinusSrcAlpha: THREE.OneMinusSrcAlphaFactor,
  DstAlpha: THREE.DstAlphaFactor,
  OneMinusDstAlpha: THREE.OneMinusSrcAlphaFactor,
  DstColor: THREE.DstColorFactor,
  OneMinusDstColor: THREE.OneMinusDstColorFactor,
};

export function applyBlending(
  material: THREE.Material,
  equation: string,
  src: string,
  dst: string,
): void {
  material.blending = THREE.CustomBlending;
  material.blendEquation = BLEND_EQUATION_VALUES[equation] ?? THREE.AddEquation;
  material.blendSrc =
    (BLEND_FACTOR_VALUES[src] as unknown as THREE.BlendingSrcFactor) ??
    THREE.SrcAlphaFactor;
  material.blendDst = BLEND_FACTOR_VALUES[dst] ?? THREE.OneMinusSrcAlphaFactor;
}
