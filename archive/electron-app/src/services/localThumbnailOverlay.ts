import type { TextStyle } from "../../shared/app-types";
import { TEXT_STYLE_PALETTES, TEXT_STYLE_PRESETS } from "./textStylePresets";

function parseResolution(resolution: "1920x1080" | "1080x1920") {
  const m = String(resolution).match(/^(\d+)x(\d+)$/);
  const w = m ? Math.max(1, Number(m[1])) : 1920;
  const h = m ? Math.max(1, Number(m[2])) : 1080;
  return { w, h };
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load image"));
    img.src = src;
  });
}

function fitFontSize(ctx: CanvasRenderingContext2D, text: string, baseSize: number, maxWidth: number) {
  let size = baseSize;
  for (let i = 0; i < 40; i += 1) {
    ctx.font = `800 ${size}px Arial Black, Arial, sans-serif`;
    const w = ctx.measureText(text).width;
    if (w <= maxWidth) break;
    size -= 4;
    if (size <= 14) break;
  }
  return size;
}

function paletteToColors(paletteId?: string) {
  const id = String(paletteId || "").trim();
  if (id === "pink-cyan-gradient") return ["#ff4dd8", "#00d4ff"];
  if (id === "cyan-lavender") return ["#00e5ff", "#b388ff"];
  if (id === "ultraviolet-aqua") return ["#7c4dff", "#00ffd5"];
  if (id === "teal-pink-chrome") return ["#00f5d4", "#ff2bd6"];
  if (id === "prismatic-foil") return ["#00d1ff", "#ff4dd8", "#b388ff"];
  return ["#ff2bd6", "#00d1ff"];
}

function presetToEffects(presetId?: string) {
  const id = String(presetId || "").trim();
  if (id === "chrome-bevel" || id === "steel-neon") return { strokeWidth: 10, glow: 18 };
  if (id === "neon-tube-outline") return { strokeWidth: 8, glow: 22 };
  if (id === "glitch-rgb") return { strokeWidth: 6, glow: 12 };
  if (id === "clean-bold") return { strokeWidth: 10, glow: 10 };
  return { strokeWidth: 8, glow: 18 };
}

function getPositionY(position: TextStyle["position"], height: number) {
  if (position === "top") return Math.round(height * 0.24);
  if (position === "bottom") return Math.round(height * 0.72);
  return Math.round(height * 0.5);
}

export async function renderLocalThumbnailDataUrl(input: {
  backgroundUrl: string;
  resolution: "1920x1080" | "1080x1920";
  textStyle: TextStyle;
}) {
  const { w, h } = parseResolution(input.resolution);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");

  const img = await loadImage(input.backgroundUrl);
  ctx.globalAlpha = 1;
  ctx.drawImage(img, 0, 0, w, h);

  const palette = TEXT_STYLE_PALETTES.find((p) => p.id === input.textStyle.paletteId) ?? null;
  const preset = TEXT_STYLE_PRESETS.find((p) => p.id === input.textStyle.presetId) ?? null;
  const colors = paletteToColors(palette?.id);
  const effects = presetToEffects(preset?.id);

  const title = String(input.textStyle.title || "").trim();
  const sub1 = String(input.textStyle.subtitle || "").trim();
  const sub2 = String(input.textStyle.subtitle2 || "").trim();
  const lines = [title, sub1, sub2].filter((x) => x.length > 0);
  if (!lines.length) return canvas.toDataURL("image/png");

  const centerX = Math.round(w / 2);
  const blockY = getPositionY(input.textStyle.position, h);
  const maxWidth = Math.round(w * 0.9);

  const baseTitle = Math.round(h * 0.16);
  const baseSub = Math.round(h * 0.085);
  const baseSub2 = Math.round(h * 0.11);

  const sizes = [
    fitFontSize(ctx, title || " ", baseTitle, maxWidth),
    fitFontSize(ctx, sub1 || " ", baseSub, maxWidth),
    fitFontSize(ctx, sub2 || " ", baseSub2, maxWidth),
  ];

  const gap = Math.max(8, Math.round(h * 0.015));
  const totalH =
    (lines[0] ? sizes[0] : 0) +
    (lines[1] ? sizes[1] : 0) +
    (lines[2] ? sizes[2] : 0) +
    (lines.length - 1) * gap;
  let y = Math.round(blockY - totalH / 2);

  ctx.textAlign = "center";
  ctx.textBaseline = "top";

  const gradient = ctx.createLinearGradient(centerX - maxWidth / 2, y, centerX + maxWidth / 2, y);
  if (colors.length === 2) {
    gradient.addColorStop(0, colors[0]!);
    gradient.addColorStop(1, colors[1]!);
  } else {
    const step = 1 / Math.max(1, colors.length - 1);
    colors.forEach((c, idx) => gradient.addColorStop(idx * step, c));
  }

  const opacity = Math.max(0, Math.min(1, Number(input.textStyle.opacity ?? 0.92)));
  for (let i = 0; i < lines.length; i += 1) {
    const text = lines[i]!;
    const size = sizes[i] ?? baseSub;
    ctx.font = `900 ${size}px Arial Black, Arial, sans-serif`;
    ctx.lineJoin = "round";
    ctx.miterLimit = 2;

    ctx.globalAlpha = Math.min(1, opacity * 0.9);
    ctx.strokeStyle = "rgba(0,0,0,0.75)";
    ctx.lineWidth = effects.strokeWidth;
    ctx.shadowColor = "rgba(0,0,0,0)";
    ctx.shadowBlur = 0;
    ctx.strokeText(text, centerX, y);

    ctx.globalAlpha = opacity;
    ctx.fillStyle = gradient;
    ctx.shadowColor = colors[0] ?? "#ff2bd6";
    ctx.shadowBlur = effects.glow;
    ctx.fillText(text, centerX, y);
    ctx.shadowBlur = 0;

    y += size + gap;
  }

  return canvas.toDataURL("image/png");
}

export async function renderCompositeThumbnailDataUrl(input: {
  backgroundUrl: string;
  overlayUrl: string;
  resolution: "1920x1080" | "1080x1920";
  opacity?: number;
  position?: TextStyle["position"];
}) {
  const { w, h } = parseResolution(input.resolution);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");

  const bg = await loadImage(input.backgroundUrl);
  ctx.globalAlpha = 1;
  ctx.drawImage(bg, 0, 0, w, h);

  const overlay = await loadImage(input.overlayUrl);
  const ow = overlay.naturalWidth || overlay.width || 1;
  const oh = overlay.naturalHeight || overlay.height || 1;
  const scale = Math.min(w / ow, h / oh);
  const rw = Math.max(1, Math.round(ow * scale));
  const rh = Math.max(1, Math.round(oh * scale));
  const x = Math.round((w - rw) / 2);
  const blockY = getPositionY(input.position ?? "center", h);
  const y = Math.round(blockY - rh / 2);

  ctx.globalAlpha = Math.max(0, Math.min(1, Number(input.opacity ?? 1)));
  ctx.drawImage(overlay, x, y, rw, rh);
  ctx.globalAlpha = 1;

  return canvas.toDataURL("image/png");
}
