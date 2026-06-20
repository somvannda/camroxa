import { promises as fs } from "node:fs";
import path from "node:path";
import { nativeImage } from "electron";
import type { ImageGenCostEstimate, ImageGenMeta } from "../../shared/app-types";

type OpenAiImageSize = "auto" | "1024x1024" | "1024x1536" | "1536x1024";

function toSquarePng1024(filePath: string) {
  const img = nativeImage.createFromPath(filePath);
  if (img.isEmpty()) return null;
  const resized = img.resize({ width: 1024, height: 1024, quality: "best" });
  const size = resized.getSize();
  const bitmap = resized.toBitmap();
  if (bitmap.length >= 4) {
    bitmap[3] = 254;
  }
  const rgba = nativeImage.createFromBitmap(bitmap, { width: size.width, height: size.height });
  const bytes = rgba.toPNG();
  return bytes.length ? bytes : null;
}

function transparentMaskPng1024() {
  const width = 1024;
  const height = 1024;
  const bitmap = Buffer.alloc(width * height * 4, 0);
  const img = nativeImage.createFromBitmap(bitmap, { width, height });
  const bytes = img.toPNG();
  return bytes.length ? bytes : null;
}

function toPngBytes(filePath: string) {
  const img = nativeImage.createFromPath(filePath);
  if (img.isEmpty()) return null;
  const bytes = img.toPNG();
  return bytes.length ? bytes : null;
}

export function scoreImageLumaStddev(input: { filePath: string; region?: { x0: number; y0: number; x1: number; y1: number } }) {
  const img = nativeImage.createFromPath(input.filePath);
  if (img.isEmpty()) return 0;
  const size = img.getSize();
  if (!size.width || !size.height) return 0;

  const rx0 = input.region?.x0 ?? 0.22;
  const ry0 = input.region?.y0 ?? 0.22;
  const rx1 = input.region?.x1 ?? 0.78;
  const ry1 = input.region?.y1 ?? 0.78;

  const x0 = Math.max(0, Math.min(size.width - 1, Math.floor(size.width * rx0)));
  const y0 = Math.max(0, Math.min(size.height - 1, Math.floor(size.height * ry0)));
  const x1 = Math.max(x0 + 1, Math.min(size.width, Math.floor(size.width * rx1)));
  const y1 = Math.max(y0 + 1, Math.min(size.height, Math.floor(size.height * ry1)));

  const cropped = img.crop({ x: x0, y: y0, width: x1 - x0, height: y1 - y0 });
  const csize = cropped.getSize();
  const bitmap = cropped.toBitmap();
  if (!bitmap.length || !csize.width || !csize.height) return 0;

  const stride = csize.width * 4;
  const step = 4;

  let n = 0;
  let sum = 0;
  let sum2 = 0;
  for (let y = 0; y < csize.height; y += step) {
    const row = y * stride;
    for (let x = 0; x < csize.width; x += step) {
      const i = row + x * 4;
      const r = bitmap[i] ?? 0;
      const g = bitmap[i + 1] ?? 0;
      const b = bitmap[i + 2] ?? 0;
      const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      n += 1;
      sum += l;
      sum2 += l * l;
    }
  }
  if (n <= 1) return 0;
  const mean = sum / n;
  const variance = Math.max(0, sum2 / n - mean * mean);
  return Math.sqrt(variance);
}

async function generateImageEditWithOpenAI(input: {
  apiKey: string;
  prompt: string;
  baseImagePath?: string;
  baseImageBytes?: Buffer;
  resolution: "1920x1080" | "1080x1920";
}) {
  const apiKey = String(input.apiKey || "").trim();
  if (!apiKey) throw new Error("OpenAI API key is not configured");

  const baseImageBytes = input.baseImageBytes;
  const baseImagePath = String(input.baseImagePath || "").trim();
  if (!baseImageBytes?.length && !baseImagePath) throw new Error("Base image is missing");

  const prompt = String(input.prompt || "").trim();

  const candidates: Array<{ model?: string; kind: "gpt" | "dalle2" }> = [
    { model: "gpt-image-1-mini", kind: "gpt" },
    { model: "gpt-image-1", kind: "gpt" },
    { model: "dall-e-2", kind: "dalle2" },
    { model: "gpt-image-1.5", kind: "gpt" },
  ];

  let lastErr: unknown = null;
  function estimateCost(model: string): ImageGenCostEstimate | undefined {
    if (model === "gpt-image-1-mini") return { minUsd: 0.005, maxUsd: 0.052 };
    return undefined;
  }

  let attempts = 0;
  for (const c of candidates) {
    attempts += 1;
    const size: OpenAiImageSize = c.kind === "dalle2" ? "1024x1024" : "auto";
    const mime = "image/png";
    const buf = baseImageBytes?.length
      ? baseImageBytes
      : c.kind === "dalle2"
        ? (toSquarePng1024(baseImagePath) ?? (await fs.readFile(baseImagePath)))
        : (toPngBytes(baseImagePath) ?? (await fs.readFile(baseImagePath)));

    const form = new FormData();
    if (c.model) form.append("model", c.model);
    form.append("prompt", prompt);
    form.append("size", size);
    form.append("image", new Blob([buf], { type: mime }), "input.png");
    if (c.kind === "dalle2") {
      const mask = transparentMaskPng1024();
      if (mask) form.append("mask", new Blob([mask], { type: "image/png" }), "mask.png");
    }

    const resp = await fetch("https://api.openai.com/v1/images/edits", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
      body: form,
    });

    const raw = await resp.text();
    if (!resp.ok) {
      let msg = `OpenAI image generation failed (${resp.status})`;
      try {
        const j = JSON.parse(raw) as { error?: { message?: string } };
        if (j?.error?.message) msg = j.error.message;
      } catch {
        if (raw.trim()) msg = raw.slice(0, 220);
      }

      const m = msg.toLowerCase();
      const retryable =
        resp.status === 404 ||
        m.includes("model") &&
          (m.includes("does not exist") ||
            m.includes("not found") ||
            m.includes("invalid value") ||
            m.includes("you do not have access") ||
            m.includes("not available") ||
            m.includes("unsupported") ||
            m.includes("only") && m.includes("supports"));

      lastErr = new Error(msg);
      if (retryable) continue;
      throw lastErr;
    }

    const json = JSON.parse(raw) as { data?: Array<{ b64_json?: string; url?: string }> };
    const row = json.data?.[0] ?? null;
    const b64 = row?.b64_json;
    const model = String(c.model || "").trim() || (c.kind === "dalle2" ? "dall-e-2" : "unknown");
    const meta: ImageGenMeta = {
      provider: "openai",
      endpoint: "images/edits",
      model,
      attempts,
      size,
      cost: estimateCost(model),
    };
    if (b64) return { pngBytes: Buffer.from(b64, "base64"), size, meta };

    const url = String(row?.url || "").trim();
    if (!url) throw new Error("OpenAI returned no image data");
    const imgResp = await fetch(url);
    if (!imgResp.ok) throw new Error(`Failed to download image (${imgResp.status})`);
    const ab = await imgResp.arrayBuffer();
    return { pngBytes: Buffer.from(ab), size, meta };
  }

  throw lastErr instanceof Error ? lastErr : new Error("OpenAI image generation failed");
}

function parseResolution(resolution: "1920x1080" | "1080x1920") {
  const m = String(resolution).match(/^(\d+)x(\d+)$/);
  const w = m ? Math.max(1, Number(m[1])) : 1920;
  const h = m ? Math.max(1, Number(m[2])) : 1080;
  return { w, h };
}

function toCoverPngBytes(input: { pngBytes: Buffer; width: number; height: number }) {
  const img = nativeImage.createFromBuffer(input.pngBytes);
  if (img.isEmpty()) return input.pngBytes;
  const size = img.getSize();
  if (!size.width || !size.height) return input.pngBytes;

  const scale = Math.max(input.width / size.width, input.height / size.height);
  const rw = Math.max(1, Math.round(size.width * scale));
  const rh = Math.max(1, Math.round(size.height * scale));
  const resized = img.resize({ width: rw, height: rh, quality: "best" });
  const rsize = resized.getSize();
  if (!rsize.width || !rsize.height) return input.pngBytes;

  const x = Math.max(0, Math.floor((rsize.width - input.width) / 2));
  const y = Math.max(0, Math.floor((rsize.height - input.height) / 2));
  const cropW = Math.min(input.width, rsize.width);
  const cropH = Math.min(input.height, rsize.height);
  const cropped = resized.crop({ x, y, width: cropW, height: cropH });
  const out = cropped.toPNG();
  return out.length ? out : input.pngBytes;
}

export async function generateBackgroundWithOpenAI(input: {
  apiKey: string;
  prompt: string;
  sampleFilePath: string;
  resolution: "1920x1080" | "1080x1920";
  outputDir: string;
}) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");

  const { pngBytes, meta } = await generateImageEditWithOpenAI({
    apiKey: input.apiKey,
    prompt: input.prompt,
    baseImagePath: input.sampleFilePath,
    resolution: input.resolution,
  });

  const target = parseResolution(input.resolution);
  const outBytes = toCoverPngBytes({ pngBytes, width: target.w, height: target.h });

  const outDir = path.join(outRoot, "backgrounds");
  await fs.mkdir(outDir, { recursive: true });
  const safeSize = input.resolution;
  const outPath = path.join(outDir, `background_${Date.now()}_${safeSize}.png`);
  await fs.writeFile(outPath, outBytes);

  return { filePath: outPath, meta };
}

export async function generateThumbnailWithOpenAI(input: {
  apiKey: string;
  prompt: string;
  backgroundFilePath: string;
  resolution: "1920x1080" | "1080x1920";
  outputDir: string;
}) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");

  const { pngBytes, meta } = await generateImageEditWithOpenAI({
    apiKey: input.apiKey,
    prompt: input.prompt,
    baseImagePath: input.backgroundFilePath,
    resolution: input.resolution,
  });

  const target = parseResolution(input.resolution);
  const outBytes = toCoverPngBytes({ pngBytes, width: target.w, height: target.h });

  const outDir = path.join(outRoot, "thumbnails");
  await fs.mkdir(outDir, { recursive: true });
  const safeSize = input.resolution;
  const outPath = path.join(outDir, `thumbnail_${Date.now()}_${safeSize}.png`);
  await fs.writeFile(outPath, outBytes);

  return { filePath: outPath, meta };
}

export async function generateBackgroundFromPromptWithOpenAI(input: {
  apiKey: string;
  prompt: string;
  resolution: "1920x1080" | "1080x1920";
  outputDir: string;
}) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");

  const blank = transparentMaskPng1024();
  if (!blank) throw new Error("Failed to create blank image");

  const { pngBytes, meta } = await generateImageEditWithOpenAI({
    apiKey: input.apiKey,
    prompt: input.prompt,
    baseImageBytes: blank,
    resolution: input.resolution,
  });

  const target = parseResolution(input.resolution);
  const outBytes = toCoverPngBytes({ pngBytes, width: target.w, height: target.h });

  const outDir = path.join(outRoot, "backgrounds");
  await fs.mkdir(outDir, { recursive: true });
  const safeSize = input.resolution;
  const outPath = path.join(outDir, `background_prompt_${Date.now()}_${safeSize}.png`);
  await fs.writeFile(outPath, outBytes);

  return { filePath: outPath, meta };
}
