/**
 * Bitmap-font parsing and layout, ported from the three-bmfont-text modules the
 * reference Animated Text item uses (`load-bmfont`, 1648, 1649, 1651, 1655).
 */
import * as THREE from "three";

export interface BmFontGlyph {
  id: number;
  x: number;
  y: number;
  width: number;
  height: number;
  xoffset: number;
  yoffset: number;
  xadvance: number;
  page: number;
  chnl: number;
}

export interface BmFont {
  info: Record<string, string | number>;
  common: {
    lineHeight: number;
    base: number;
    scaleW: number;
    scaleH: number;
    pages: number;
    [key: string]: number;
  };
  chars: BmFontGlyph[];
  kernings: Array<{ first: number; second: number; amount: number }>;
}

function parseValue(raw: string): string | number {
  if (raw.startsWith('"') && raw.endsWith('"')) return raw.slice(1, -1);
  const number = Number(raw);
  return Number.isNaN(number) ? raw : number;
}

/** Parses the BMFont text format returned by Vizzy's DejaVu-sdf.fnt. */
export function parseBmFont(text: string): BmFont {
  const font: BmFont = {
    info: {},
    common: { lineHeight: 0, base: 0, scaleW: 1, scaleH: 1, pages: 1 },
    chars: [],
    kernings: [],
  };
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const [tag, ...rest] = line.split(/\s+/);
    const values: Record<string, string | number> = {};
    for (const part of rest) {
      const index = part.indexOf("=");
      if (index < 0) continue;
      values[part.slice(0, index)] = parseValue(part.slice(index + 1));
    }
    if (tag === "info") Object.assign(font.info, values);
    else if (tag === "common") Object.assign(font.common, values);
    else if (tag === "char") font.chars.push(values as unknown as BmFontGlyph);
    else if (tag === "kerning") font.kernings.push(values as unknown as (typeof font.kernings)[number]);
  }
  return font;
}

interface GlyphPlacement {
  position: [number, number];
  data: BmFontGlyph;
  index: number;
  line: number;
}

interface LayoutOptions {
  text: string;
  width: number;
  align: "left" | "center" | "right";
  letterSpacing: number;
  lineHeight?: number | null;
  mode?: string;
}

interface LineRange {
  start: number;
  end: number;
  width: number;
}

const TAB = 9;
const SPACE = 32;

export class BmFontLayout {
  readonly glyphs: GlyphPlacement[] = [];
  width = 0;
  height = 0;
  baseline = 0;
  descender = 0;
  lineHeight = 0;
  linesTotal = 0;
  private fallbackSpace: BmFontGlyph | null = null;
  private fallbackTab: BmFontGlyph | null = null;
  private options!: LayoutOptions;
  private font!: BmFont;

  update(font: BmFont, options: LayoutOptions): void {
    this.font = font;
    this.options = options;
    this.setupSpaceGlyphs();
    this.glyphs.length = 0;

    const lines = this.wrapLines(options.text, options.width);
    const lineHeight = options.lineHeight ?? font.common.lineHeight;
    const base = font.common.base;
    const descender = lineHeight - base;
    const align = options.align === "center" ? 1 : options.align === "right" ? 2 : 0;
    const maxWidth = lines.reduce((max, line) => Math.max(max, line.width, options.width), 0);
    let startY = -(lineHeight * lines.length - descender);
    this.width = maxWidth;
    this.height = lineHeight * lines.length - descender;
    this.descender = descender;
    this.baseline = base;
    this.lineHeight = lineHeight;
    this.linesTotal = lines.length;

    let x = 0;
    let previous: BmFontGlyph | null = null;
    lines.forEach((line, lineIndex) => {
      for (let index = line.start; index < line.end; index += 1) {
        const glyph = this.getGlyph(options.text.charCodeAt(index));
        if (!glyph) continue;
        if (previous) x += this.kerning(previous.id, glyph.id);
        let position = x;
        if (align === 1) position += (maxWidth - line.width) / 2;
        else if (align === 2) position += maxWidth - line.width;
        this.glyphs.push({
          position: [position, startY],
          data: glyph,
          index,
          line: lineIndex,
        });
        x += glyph.xadvance + (options.letterSpacing || 0);
        previous = glyph;
      }
      startY += lineHeight;
      x = 0;
      previous = null;
    });
  }

  private findChar(id: number): BmFontGlyph | null {
    return this.font.chars.find((glyph) => glyph.id === id) ?? null;
  }

  private setupSpaceGlyphs(): void {
    this.fallbackSpace = null;
    this.fallbackTab = null;
    const chars = this.font.chars;
    if (!chars.length) return;
    const space =
      this.findChar(SPACE) ||
      this.findChar("m".charCodeAt(0)) ||
      this.findChar("w".charCodeAt(0)) ||
      chars[0];
    this.fallbackSpace = space;
    this.fallbackTab = { ...space, id: TAB, xadvance: 4 * space.xadvance, width: 0, height: 0, x: 0, y: 0, xoffset: 0, yoffset: 0 };
  }

  private getGlyph(id: number): BmFontGlyph | null {
    return (
      this.findChar(id) ||
      (id === TAB ? this.fallbackTab : id === SPACE ? this.fallbackSpace : null)
    );
  }

  private kerning(first: number, second: number): number {
    return this.font.kernings.find((entry) => entry.first === first && entry.second === second)?.amount ?? 0;
  }

  private measure(start: number, end: number, maxWidth: number): LineRange {
    const text = this.options.text;
    const spacing = this.options.letterSpacing || 0;
    let x = 0;
    let width = 0;
    let count = 0;
    let previous: BmFontGlyph | null = null;
    const limit = Math.min(text.length, end);
    for (let index = start; index < limit; index += 1) {
      const glyph = this.getGlyph(text.charCodeAt(index));
      if (glyph) {
        if (previous) x += this.kerning(previous.id, glyph.id);
        const advance = x + glyph.xadvance + spacing;
        const right = x + glyph.width;
        if (right >= maxWidth || advance >= maxWidth) break;
        x = advance;
        width = right;
        previous = glyph;
      }
      count += 1;
    }
    if (previous) width += previous.xoffset;
    return { start, end: start + count, width };
  }

  private wrapLines(text: string, width: number): LineRange[] {
    if (width === 0 && this.options.mode !== "nowrap") return [];
    const limit = Number.isFinite(width) ? width : Number.MAX_VALUE;
    const maxWidth = this.options.mode === "nowrap" ? Number.MAX_VALUE : limit;
    const measured: LineRange[] = [];
    const measure = (start: number, end: number) => this.measure(start, end, maxWidth);
    let index = 0;
    while (index < text.length) {
      let newline = text.indexOf("\n", index);
      if (newline < 0) newline = text.length;
      while (index < newline && /\s/.test(text.charAt(index))) index += 1;
      const range = measure(index, newline);
      let lineEnd = index + (range.end - range.start);
      let next = lineEnd + 1;
      if (lineEnd < newline) {
        while (lineEnd > index && !/\s/.test(text.charAt(lineEnd))) lineEnd -= 1;
        if (lineEnd === index) {
          if (next > index + 1) next -= 1;
          lineEnd = next;
        } else {
          next = lineEnd;
          while (lineEnd > index && /\s/.test(text.charAt(lineEnd - 1))) lineEnd -= 1;
        }
      }
      if (lineEnd >= index) measured.push(measure(index, lineEnd));
      index = next;
    }
    return measured;
  }
}

/** Builds the reference Animated Text geometry from a layout. */
export function buildBmFontGeometry(
  layout: BmFontLayout,
  font: BmFont,
  letterSpacing: number,
): THREE.BufferGeometry {
  void letterSpacing;
  const visible = layout.glyphs.filter((glyph) => glyph.data.width * glyph.data.height > 0);
  layout.glyphs.splice(0, layout.glyphs.length, ...visible);

  const positions = new Float32Array(visible.length * 4 * 2);
  const uvs = new Float32Array(visible.length * 4 * 2);
  const lines = new Float32Array(visible.length * 4);
  const indices = new Uint16Array(visible.length * 6);
  const scaleW = font.common.scaleW;
  const scaleH = font.common.scaleH;
  const maxLine = Math.max(0, ...visible.map((glyph) => glyph.line));
  let p = 0;
  let u = 0;
  let l = 0;
  let i = 0;

  visible.forEach((glyph, order) => {
    const data = glyph.data;
    const x = glyph.position[0] + data.xoffset;
    const y = glyph.position[1] + data.yoffset;
    const right = x + data.width;
    const bottom = y + data.height;
    positions[p++] = x;
    positions[p++] = y;
    positions[p++] = x;
    positions[p++] = bottom;
    positions[p++] = right;
    positions[p++] = bottom;
    positions[p++] = right;
    positions[p++] = y;

    const leftU = data.x / scaleW;
    const rightU = (data.x + data.width) / scaleW;
    const topV = (scaleH - data.y) / scaleH;
    const bottomV = (scaleH - (data.y + data.height)) / scaleH;
    uvs[u++] = leftU;
    uvs[u++] = topV;
    uvs[u++] = leftU;
    uvs[u++] = bottomV;
    uvs[u++] = rightU;
    uvs[u++] = bottomV;
    uvs[u++] = rightU;
    uvs[u++] = topV;

    const line = maxLine <= 1 ? 1 : glyph.line / (maxLine - 1);
    lines[l++] = line;
    lines[l++] = line;
    lines[l++] = line;
    lines[l++] = line;

    const base = order * 4;
    indices[i++] = base;
    indices[i++] = base + 2;
    indices[i++] = base + 3;
    indices[i++] = base + 2;
    indices[i++] = base + 1;
    indices[i++] = base + 3;
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 2));
  geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
  geometry.setAttribute("line", new THREE.BufferAttribute(lines, 1));
  // The reference keeps the billboard always visible; the default 3-component
  // bounding-sphere pass cannot read a 2-component position attribute and would
  // produce a NaN radius.
  geometry.computeBoundingSphere = () => {
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 1e6);
  };
  geometry.computeBoundingBox = () => {
    geometry.boundingBox = null;
  };
  return geometry;
}
