/**
 * Reference colour-shift helpers.
 *
 * Vizzy's Add layer generator takes the analyzer colour and brightens or
 * darkens it with `spectrumColorShift` (0..1) before creating the layer. The
 * same transform is applied to the layer's from/to and shadow colours.
 */

export type SpectrumColorMode = "lighten" | "darken";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function parseHex(hex: string): [number, number, number] | null {
  const raw = hex.trim().replace(/^#/, "");
  const full =
    raw.length === 3
      ? raw
          .split("")
          .map((char) => char + char)
          .join("")
      : raw;
  if (!/^[0-9a-f]{6}$/i.test(full)) return null;
  return [
    parseInt(full.slice(0, 2), 16) / 255,
    parseInt(full.slice(2, 4), 16) / 255,
    parseInt(full.slice(4, 6), 16) / 255,
  ];
}

function toHex(r: number, g: number, b: number): string {
  const byte = (value: number): string =>
    Math.round(clamp(value, 0, 1) * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${byte(r)}${byte(g)}${byte(b)}`;
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const delta = max - min;
  const s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min);
  let h: number;
  if (max === r) h = (g - b) / delta + (g < b ? 6 : 0);
  else if (max === g) h = (b - r) / delta + 2;
  else h = (r - g) / delta + 4;
  return [h / 6, s, l];
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  if (s === 0) return [l, l, l];
  const hue = (p: number, q: number, t: number): number => {
    let next = t;
    if (next < 0) next += 1;
    if (next > 1) next -= 1;
    if (next < 1 / 6) return p + (q - p) * 6 * next;
    if (next < 1 / 2) return q;
    if (next < 2 / 3) return p + (q - p) * (2 / 3 - next) * 6;
    return p;
  };
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  return [hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3)];
}

/** Brighten/darken a hex colour by 0..1, preserving hue and saturation. */
export function shiftHexColor(
  hex: string,
  mode: SpectrumColorMode,
  amount: number,
): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const [h, s, l] = rgbToHsl(...rgb);
  const ratio = clamp(amount, 0, 1);
  const lightness =
    mode === "darken" ? l * (1 - ratio) : l + (1 - l) * ratio;
  return toHex(...hslToRgb(h, s, clamp(lightness, 0, 1)));
}
