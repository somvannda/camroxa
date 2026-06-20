import { promises as fs } from "node:fs";
import path from "node:path";
import { nativeImage } from "electron";
import type { ImageGenMeta } from "../../shared/app-types";

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

function toPngBytes(filePath: string) {
  const img = nativeImage.createFromPath(filePath);
  if (img.isEmpty()) return null;
  const bytes = img.toPNG();
  return bytes.length ? bytes : null;
}

function toDataUrl(input: { filePath: string; bytes?: Buffer }) {
  const ext = path.extname(input.filePath).toLowerCase();
  const mime = ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" : ext === ".webp" ? "image/webp" : "image/png";
  const bytes = input.bytes?.length ? input.bytes : null;
  if (!bytes) return null;
  return `data:${mime};base64,${bytes.toString("base64")}`;
}

async function generateWithSlai(input: {
  apiKey: string;
  model: string;
  prompt: string;
  imageFilePath: string;
  resolution: "1920x1080" | "1080x1920";
}) {
  const startedAt = Date.now();
  const apiKey = String(input.apiKey || "").trim();
  if (!apiKey) throw new Error("SLAI IMG API key is not configured");

  const model = String(input.model || "").trim() || "cgpt-web/gpt-5.5-pro";
  const prompt = String(input.prompt || "").trim();
  if (!prompt) throw new Error("Prompt is empty");

  const imageFilePath = String(input.imageFilePath || "").trim();
  if (!imageFilePath) throw new Error("Base image is missing");

  const bytes = toPngBytes(imageFilePath) ?? (await fs.readFile(imageFilePath));
  const imageUrl = toDataUrl({ filePath: imageFilePath, bytes });
  if (!imageUrl) throw new Error("Failed to read base image");

  const aspectRatio = input.resolution === "1080x1920" ? "9:16" : "16:9";
  const endpoints = ["https://api.slai.shop/v1/images/generations", "https://api-img.slai.shop/v1/images/generations"];

  console.log("[slaiImage] images/generations start", {
    model,
    aspectRatio,
    promptChars: prompt.length,
    imageFile: path.basename(imageFilePath),
    endpoints,
  });

  let raw = "";
  let lastStatus = 0;
  let lastUrl = endpoints[0] ?? "";
  let okResp: Response | null = null;

  for (const endpoint of endpoints) {
    lastUrl = endpoint;
    const t0 = Date.now();
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        prompt,
        image_url: imageUrl,
        aspect_ratio: aspectRatio,
      }),
    });

    lastStatus = resp.status;
    raw = await resp.text();
    console.log("[slaiImage] images/generations response", { endpoint, status: resp.status, ok: resp.ok, ms: Date.now() - t0 });
    if (resp.ok) {
      okResp = resp;
      break;
    }
    if (resp.status === 404 || resp.status === 405) continue;

    let msg = `SLAI image generation failed (${resp.status})`;
    try {
      const j = JSON.parse(raw) as { error?: { message?: string } };
      if (j?.error?.message) msg = j.error.message;
    } catch {
      if (raw.trim()) msg = raw.slice(0, 220);
    }
    console.log("[slaiImage] images/generations error body", { endpoint, status: resp.status, bodyPreview: raw.slice(0, 220) });
    throw new Error(msg);
  }

  if (!okResp) {
    let msg = `SLAI image generation failed (${lastStatus || "unknown"})`;
    try {
      const j = JSON.parse(raw) as { error?: { message?: string } };
      if (j?.error?.message) msg = j.error.message;
    } catch {
      if (raw.trim()) msg = raw.slice(0, 220);
    }
    console.log("[slaiImage] images/generations failed after fallbacks", { lastUrl, lastStatus, bodyPreview: raw.slice(0, 220) });
    throw new Error(`${msg} (endpoint: ${lastUrl})`);
  }

  let pngBytes: Buffer | null = null;
  let imageOutUrl = "";
  try {
    const j = JSON.parse(raw) as { data?: Array<{ b64_json?: string; url?: string }>; b64_json?: string; url?: string };
    const row = j.data?.[0] ?? null;
    const b64 = String(row?.b64_json ?? j.b64_json ?? "").trim();
    if (b64) pngBytes = Buffer.from(b64, "base64");
    imageOutUrl = String(row?.url ?? j.url ?? "").trim();
  } catch {
  }

  if (!pngBytes?.length && imageOutUrl) {
    const imgResp = await fetch(imageOutUrl);
    if (!imgResp.ok) throw new Error(`Failed to download image (${imgResp.status})`);
    const ab = await imgResp.arrayBuffer();
    pngBytes = Buffer.from(ab);
  }

  if (!pngBytes?.length) throw new Error("SLAI returned no image data");
  console.log("[slaiImage] images/generations done", { ms: Date.now() - startedAt, pngBytes: pngBytes.length });

  const meta: ImageGenMeta = {
    provider: "slai",
    endpoint: "images/generations",
    model,
    attempts: 1,
    size: aspectRatio,
  };

  return { pngBytes, meta };
}

export async function generateBackgroundWithSlai(input: {
  apiKey: string;
  model: string;
  prompt: string;
  sampleFilePath: string;
  resolution: "1920x1080" | "1080x1920";
  outputDir: string;
}) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");

  const { pngBytes, meta } = await generateWithSlai({
    apiKey: input.apiKey,
    model: input.model,
    prompt: input.prompt,
    imageFilePath: input.sampleFilePath,
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

export async function generateThumbnailWithSlai(input: {
  apiKey: string;
  model: string;
  prompt: string;
  backgroundFilePath: string;
  resolution: "1920x1080" | "1080x1920";
  outputDir: string;
}) {
  const outRoot = String(input.outputDir || "").trim();
  if (!outRoot) throw new Error("Image output folder is not configured");

  const { pngBytes, meta } = await generateWithSlai({
    apiKey: input.apiKey,
    model: input.model,
    prompt: input.prompt,
    imageFilePath: input.backgroundFilePath,
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
