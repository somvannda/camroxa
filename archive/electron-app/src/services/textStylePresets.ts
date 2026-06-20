export type TextStylePalette = {
  id: string;
  name: string;
  palettePrompt: string;
};

export type TextStylePreset = {
  id: string;
  name: string;
  line1: string;
  line2: string;
  line3: string;
  effects: string;
  accents: string;
  defaultOpacity: number;
  defaultPosition: "top" | "center" | "bottom";
};

export const TEXT_STYLE_PALETTES: TextStylePalette[] = [
  { id: "magenta-cyan", name: "Magenta Cyan", palettePrompt: "neon magenta, fuchsia, purple, electric blue, cyan" },
  { id: "pink-cyan-gradient", name: "Pink→Cyan", palettePrompt: "pink-to-cyan gradient with violet midtones" },
  { id: "cyan-lavender", name: "Cyan Lavender", palettePrompt: "cyan-to-lavender gradient with magenta highlights" },
  { id: "ultraviolet-aqua", name: "Ultraviolet Aqua", palettePrompt: "ultraviolet + aqua + rose glow" },
  { id: "teal-pink-chrome", name: "Teal Pink Chrome", palettePrompt: "teal + neon pink with chrome highlights" },
  { id: "prismatic-foil", name: "Prismatic Foil", palettePrompt: "prismatic rainbow foil on dark background" },
];

export const TEXT_STYLE_PRESETS: TextStylePreset[] = [
  {
    id: "neon-brush",
    name: "Neon Brush",
    line1: "thick brush-script, dramatic swashes, slight italic, neon gradient fill",
    line2: "cursive brush script, smaller, tight tracking, soft glow",
    line3: "ultra-bold italic display, rounded corners, metallic neon gradient",
    effects: "outer glow (pink/cyan), inner highlights, subtle shadow",
    accents: "paint-streak underline beneath line 3 extending left/right",
    defaultOpacity: 0.92,
    defaultPosition: "center",
  },
  {
    id: "chrome-bevel",
    name: "Chrome Bevel",
    line1: "retro brush logo, chrome bevel, reflective shine, cinematic glow",
    line2: "clean italic wordmark, soft neon rimlight",
    line3: "bold chrome numbers with gradient and drop shadow",
    effects: "chrome bevel, reflective shine, neon edge glow",
    accents: "glow halo behind line 1 and line 3",
    defaultOpacity: 0.93,
    defaultPosition: "center",
  },
  {
    id: "neon-tube-outline",
    name: "Neon Tube Outline",
    line1: "smooth modern script, neon tube outline effect, bright edge, hollow interior",
    line2: "handwritten neon sign style, thin stroke with glow",
    line3: "blocky neon display with motion streak underline and glow",
    effects: "volumetric glow, bloom, soft fog light spill",
    accents: "thin neon underline and motion streaks",
    defaultOpacity: 0.9,
    defaultPosition: "center",
  },
  {
    id: "glitch-rgb",
    name: "Glitch RGB",
    line1: "bold script with chromatic split edges, RGB offset, sharp highlight",
    line2: "condensed script, slightly slanted, satin glow",
    line3: "heavy sans display, forward-leaning, thick stroke, strong rim light",
    effects: "subtle grain, filmic glow, high contrast",
    accents: "chromatic aberration micro-edge and glossy highlight",
    defaultOpacity: 0.9,
    defaultPosition: "center",
  },
  {
    id: "graffiti-energy",
    name: "Graffiti Energy",
    line1: "thick graffiti-inspired brush, energetic strokes, glow bloom",
    line2: "simple cursive, pink-to-lilac gradient, soft shadow",
    line3: "chunky display numbers with paint streaks and spark particles",
    effects: "rimlight, spark particles, light streaks around text",
    accents: "subtle grunge edges + paint splatter micro-texture",
    defaultOpacity: 0.92,
    defaultPosition: "center",
  },
  {
    id: "lux-calligraphy",
    name: "Lux Calligraphy",
    line1: "luxury calligraphic script, glossy edges, elegant high contrast",
    line2: "elegant brush cursive, gentle gradient, minimal bloom",
    line3: "wide italic numbers, bevel highlight, neon rimlight",
    effects: "outer glow, subtle shadow, reflective shine",
    accents: "diagonal baseline slant rising left-to-right for line 1",
    defaultOpacity: 0.9,
    defaultPosition: "center",
  },
  {
    id: "clean-bold",
    name: "Clean Bold",
    line1: "bold italic sans, clean edges, high contrast, subtle glow",
    line2: "small caps sans, tight tracking, minimal glow",
    line3: "ultra-bold italic display, crisp stroke, drop shadow",
    effects: "subtle shadow, minimal bloom, sharp readability",
    accents: "neon stroke outline around line 1 and line 3",
    defaultOpacity: 0.88,
    defaultPosition: "bottom",
  },
  {
    id: "holo-gradient",
    name: "Holographic Gradient",
    line1: "smooth modern script, holographic gradient sheen, glossy highlight",
    line2: "smooth italic script, medium weight, subtle inner shine",
    line3: "thick futuristic numbers, glossy highlights, neon underglow",
    effects: "volumetric glow, bloom, soft light spill",
    accents: "glow halo behind line 1",
    defaultOpacity: 0.92,
    defaultPosition: "center",
  },
  {
    id: "laser-underline",
    name: "Laser Underline",
    line1: "hand-lettered brush, chunky strokes, neon rim glow",
    line2: "clean italic wordmark, soft neon rimlight",
    line3: "wide display numbers, crisp stroke, strong glow",
    effects: "outer glow, inner highlights, subtle shadow",
    accents: "thin neon underline beneath line 3",
    defaultOpacity: 0.9,
    defaultPosition: "center",
  },
  {
    id: "night-rider",
    name: "Night Rider",
    line1: "bold brush script, glossy highlights, deep shadow",
    line2: "handwritten neon sign style, thin stroke with glow",
    line3: "heavy sans display, forward-leaning, thick stroke",
    effects: "electric glow bloom, halo behind line 1",
    accents: "glow halo behind line 1 and line 3",
    defaultOpacity: 0.91,
    defaultPosition: "center",
  },
  {
    id: "vapor-sunset",
    name: "Vapor Sunset",
    line1: "retro brush logo, soft bloom, cinematic glow",
    line2: "simple cursive, gentle gradient, minimal bloom",
    line3: "blocky neon display with motion streak underline",
    effects: "volumetric glow, bloom, soft fog light spill",
    accents: "thin neon underline and motion streaks",
    defaultOpacity: 0.92,
    defaultPosition: "center",
  },
  {
    id: "steel-neon",
    name: "Steel Neon",
    line1: "brush lettering with sharp focus, chrome bevel edges, neon rimlight",
    line2: "condensed script, slightly slanted, satin glow",
    line3: "ultra-bold italic display, metallic gradient, rim glow",
    effects: "chrome bevel, reflective shine, neon edge glow",
    accents: "neon stroke outline around line 1 and line 3",
    defaultOpacity: 0.93,
    defaultPosition: "center",
  },
];

export function buildTextStylePrompt(input: { name: string; palettePrompt: string; preset: TextStylePreset }) {
  return (
    `Typography overlay style (${input.name}): ` +
    `Center-aligned 3-line stacked logo. ` +
    `Color palette: ${input.palettePrompt}. ` +
    `Line 1 ("BASS") style: ${input.preset.line1}. ` +
    `Line 2 ("Car Music") style: ${input.preset.line2}. ` +
    `Line 3 ("2026") style: ${input.preset.line3}. ` +
    `Effects: ${input.preset.effects}. ` +
    `Accents: ${input.preset.accents}. ` +
    `Keep text sharp, readable, neon glow, high contrast against dark background.`
  );
}

