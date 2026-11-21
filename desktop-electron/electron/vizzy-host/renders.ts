/**
 * Render files produced by the hosted Vizzy editor.
 *
 * Everything here is pure Node so it can be unit-tested without Electron:
 * export settings normalisation, the `<slug>-<timestamp>.<ext>` name, the
 * `renders/` containment rules and the chunk writer that streams encoder output
 * to disk at absolute offsets.
 *
 * Files are the only durable artefact of an export. The host owns the file
 * handle; the editor never learns a path it can write to.
 */
import fs from "node:fs";
import path from "node:path";
import { slugifyProjectName } from "./project-store";

export const RENDER_DIR_NAME = "renders";
export const RENDER_EXTENSIONS = ["mp4", "webm"] as const;
export type RenderExtension = (typeof RENDER_EXTENSIONS)[number];
export type RenderFormat = RenderExtension;
export type RenderCodec = "h264" | "vp8" | "vp9";

/** A single IPC chunk. The editor flushes at most one segment at a time. */
export const MAX_EXPORT_CHUNK_BYTES = 64 * 1024 * 1024;
/** Guard against a runaway job filling the disk (and against bogus offsets). */
export const MAX_RENDER_BYTES = 8 * 1024 * 1024 * 1024;

export const DEFAULT_RENDER_WIDTH = 1920;
export const DEFAULT_RENDER_HEIGHT = 1080;
export const DEFAULT_RENDER_FPS = 30;
export const DEFAULT_RENDER_FORMAT: RenderFormat = "mp4";
export const DEFAULT_RENDER_CRF = 20;
/** Used when the editor cannot report a project duration yet. */
export const FALLBACK_DURATION_SEC = 10;

export interface VizzyProjectInfo {
  name: string;
  width: number;
  height: number;
  fps: number;
  duration: number;
}

export interface VizzyExportSettingsInput {
  width?: number;
  height?: number;
  fps?: number;
  format?: RenderFormat;
  codec?: RenderCodec;
  engine?: "wasm" | "webcodecs";
  /** Video bitrate in Mbps; 0 lets the encoder pick a CRF. */
  bitrate?: number;
  crf?: number;
  preset?: string;
  profile?: string;
  audioBitrate?: number;
  start?: number;
  end?: number;
}

export interface ResolvedVizzyExportSettings {
  width: number;
  height: number;
  fps: number;
  format: RenderFormat;
  codec: RenderCodec;
  engine: "wasm" | "webcodecs";
  bitrate: number;
  crf: number;
  preset: string;
  profile: string;
  audioBitrate: number;
  start: number;
  end: number;
  duration: number;
}

/** Reference defaults: the bitrate tracks the chosen height. */
export function defaultExportBitrate(height: number): number {
  if (height <= 480) return 5;
  if (height <= 720) return 15;
  if (height <= 1080) return 25;
  if (height <= 1440) return 50;
  if (height <= 2160) return 75;
  return 16;
}

function finite(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/** Encoders need even dimensions for 4:2:0; clamp to a sane range. */
function evenDimension(value: unknown, fallback: number): number {
  const rounded = Math.round(finite(value, fallback) / 2) * 2;
  return Math.min(7680, Math.max(16, rounded));
}

function codecForFormat(format: RenderFormat, requested?: RenderCodec): RenderCodec {
  if (format === "mp4") return "h264";
  return requested === "vp8" ? "vp8" : "vp9";
}

export function normaliseFormat(value: unknown): RenderFormat {
  return value === "webm" ? "webm" : DEFAULT_RENDER_FORMAT;
}

/**
 * Resolve the request against the open project. Missing dimensions fall back to
 * the project, then to 1920x1080/30/h264 — never to the preview size.
 */
export function resolveExportSettings(
  input: VizzyExportSettingsInput | null | undefined,
  project: VizzyProjectInfo | null | undefined,
): ResolvedVizzyExportSettings {
  const request = input ?? {};
  const width = evenDimension(request.width ?? project?.width, project?.width || DEFAULT_RENDER_WIDTH);
  const height = evenDimension(
    request.height ?? project?.height,
    project?.height || DEFAULT_RENDER_HEIGHT,
  );
  const fps = Math.min(
    120,
    Math.max(1, Math.round(finite(request.fps ?? project?.fps, project?.fps || DEFAULT_RENDER_FPS))),
  );
  const format = normaliseFormat(request.format);
  const codec = codecForFormat(format, request.codec);
  const engine = request.engine === "webcodecs" ? "webcodecs" : "wasm";
  const bitrate = Math.max(0, Math.min(200, finite(request.bitrate, defaultExportBitrate(height))));
  const crf = Math.min(51, Math.max(0, Math.round(finite(request.crf, DEFAULT_RENDER_CRF))));
  const preset =
    typeof request.preset === "string" && request.preset.trim()
      ? request.preset.trim()
      : "veryfast";
  const profile =
    request.profile === "baseline" || request.profile === "main" || request.profile === "high"
      ? request.profile
      : "high";
  const audioBitrate = Math.min(
    320,
    Math.max(64, Math.round(finite(request.audioBitrate, 192))),
  );

  const projectDuration = Math.max(
    0,
    finite(project?.duration, 0) || FALLBACK_DURATION_SEC,
  );
  const rawStart = Math.max(0, Math.min(finite(request.start, 0), projectDuration));
  const rawEnd = Math.max(
    rawStart + 0.1,
    Math.min(finite(request.end, projectDuration), projectDuration),
  );
  const start = Number(rawStart.toFixed(3));
  const end = Number(Math.max(start + 0.1, rawEnd).toFixed(3));

  return {
    width,
    height,
    fps,
    format,
    codec,
    engine,
    bitrate,
    crf,
    preset,
    profile,
    audioBitrate,
    start,
    end,
    duration: Number(Math.max(0.1, end - start).toFixed(3)),
  };
}

/** `20261119-142530` in local time: sortable, filename-safe, no colons. */
export function renderTimestamp(date: Date = new Date()): string {
  const pad = (value: number): string => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  );
}

/** `<slug>-<timestamp>.<ext>` — generated from the project name only. */
export function renderFileName(
  projectName: string,
  extension: RenderExtension,
  date: Date = new Date(),
): string {
  return `${slugifyProjectName(projectName)}-${renderTimestamp(date)}.${extension}`;
}

/**
 * `<template-slug>-<timestamp>.<ext>` for a saved video template render. The
 * template id is already a slug; it is normalised again so a hand-edited
 * `pipeline.json` cannot choose a path.
 */
export function renderFileNameForTemplate(
  templateId: string,
  extension: RenderExtension,
  date: Date = new Date(),
): string {
  const slug = slugifyProjectName(templateId) || "template";
  return `${slug}-${renderTimestamp(date)}.${extension}`;
}

/** A bare managed render name: no separators, no traversal, known extension. */
export function isRenderFileName(name: unknown): name is string {
  if (typeof name !== "string" || name.length === 0 || name.length > 160) return false;
  if (name.includes("/") || name.includes("\\") || name.includes("..")) return false;
  return /^[a-z0-9][a-z0-9-]*-\d{8}-\d{6}(?:-\d{1,2})?\.(?:mp4|webm)$/.test(name);
}

export function ensureRendersDir(rendersDir: string): string {
  const resolved = path.resolve(rendersDir);
  fs.mkdirSync(resolved, { recursive: true });
  return resolved;
}

/** True only when `target` is strictly inside `root` (no traversal). */
export function isInsideRenders(rendersDir: string, target: string): boolean {
  const resolvedRoot = path.resolve(rendersDir);
  const relative = path.relative(resolvedRoot, path.resolve(target));
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

/** Resolve a managed render name to its absolute path, or null. */
export function managedRenderPath(rendersDir: string, name: string): string | null {
  if (!isRenderFileName(name)) return null;
  const resolved = path.resolve(rendersDir, name);
  return isInsideRenders(rendersDir, resolved) ? resolved : null;
}

/** First free `<name>` / `<name>-2` / `<name>-3` … inside `renders/`. */
export function uniqueRenderPath(rendersDir: string, fileName: string): string {
  const parsed = path.parse(fileName);
  let candidate = path.join(rendersDir, fileName);
  for (let index = 2; index < 100 && fs.existsSync(candidate); index += 1) {
    candidate = path.join(rendersDir, `${parsed.name}-${index}${parsed.ext}`);
  }
  return candidate;
}

export interface RenderSummary {
  name: string;
  bytes: number;
  mtimeMs: number;
}

/**
 * Managed renders, newest first. Symlinks and foreign files are ignored: only
 * the four path segments the exporter produces are ever listed.
 */
export function listRenderFiles(rendersDir: string): RenderSummary[] {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(rendersDir, { withFileTypes: true });
  } catch {
    return [];
  }
  const items: RenderSummary[] = [];
  for (const entry of entries) {
    if (!entry.isFile() || !isRenderFileName(entry.name)) continue;
    try {
      const stat = fs.statSync(path.join(rendersDir, entry.name));
      items.push({ name: entry.name, bytes: stat.size, mtimeMs: stat.mtimeMs });
    } catch {
      /* the file vanished between readdir and stat */
    }
  }
  return items.sort((a, b) => b.mtimeMs - a.mtimeMs);
}

/**
 * Delete one managed render. Returns false when the name is not a render this
 * app created or the file is already gone; never deletes outside `renders/`.
 */
export function deleteRenderFile(rendersDir: string, name: string): boolean {
  const resolved = managedRenderPath(rendersDir, name);
  if (!resolved) return false;
  let stat: fs.Stats;
  try {
    stat = fs.lstatSync(resolved);
  } catch {
    return false;
  }
  if (!stat.isFile()) return false;
  try {
    fs.unlinkSync(resolved);
    return true;
  } catch {
    return false;
  }
}

export interface ChunkValidation {
  ok: boolean;
  reason?: string;
}

/** Validate a chunk's absolute range before it reaches the disk. */
export function validateChunkRange(position: unknown, byteLength: unknown): ChunkValidation {
  if (typeof position !== "number" || !Number.isInteger(position) || position < 0) {
    return { ok: false, reason: "Chunk position must be a non-negative integer." };
  }
  if (
    typeof byteLength !== "number" ||
    !Number.isInteger(byteLength) ||
    byteLength <= 0 ||
    byteLength > MAX_EXPORT_CHUNK_BYTES
  ) {
    return { ok: false, reason: "Chunk size is outside the accepted range." };
  }
  if (position + byteLength > MAX_RENDER_BYTES) {
    return { ok: false, reason: "The render exceeds the managed size limit." };
  }
  return { ok: true };
}

/**
 * Streams encoder chunks to a file at absolute offsets.
 *
 * The reference MP4 encoder writes at absolute positions (it flushes the moov
 * atom last), so `position` is authoritative and the writer tracks the highest
 * byte written rather than the sum of chunk lengths.
 */
export class RenderChunkWriter {
  private written = 0;
  private closed = false;

  constructor(
    private readonly sink: {
      writeAt(buffer: Buffer, position: number): Promise<void>;
      close(): Promise<void>;
    },
  ) {}

  get bytes(): number {
    return this.written;
  }

  get isClosed(): boolean {
    return this.closed;
  }

  async write(position: number, data: Uint8Array): Promise<void> {
    if (this.closed) throw new Error("The render writer is already closed.");
    const check = validateChunkRange(position, data.byteLength);
    if (!check.ok) throw new Error(check.reason ?? "Invalid render chunk.");
    const buffer = Buffer.from(data.buffer, data.byteOffset, data.byteLength);
    await this.sink.writeAt(buffer, position);
    this.written = Math.max(this.written, position + data.byteLength);
  }

  async close(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    await this.sink.close();
  }
}
