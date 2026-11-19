/**
 * Pure helpers for the hosted Vizzy page.
 *
 * This module deliberately has no Electron import so it can be unit-tested in a
 * plain Node/vitest process. `protocol.ts` and `server.ts` wrap it.
 *
 * P7 adds the production response path: `vizzyAssetStreamResponse` streams from
 * disk and honours a single `Range` request, which the spike did not need.
 */
import fs from "node:fs";
import { Readable } from "node:stream";
import path from "node:path";

export const VIZZY_SCHEME = "camxora-vizzy";
export const VIZZY_HOST = "vizzy";
export const VIZZY_INDEX_PATH = "index.html";
export const VIZZY_INDEX_URL = `${VIZZY_SCHEME}://${VIZZY_HOST}/${VIZZY_INDEX_PATH}`;

/**
 * The isolation headers the real host must send. All three are required:
 * COOP + COEP make `crossOriginIsolated` true (and re-enable SharedArrayBuffer
 * and high-resolution timers); CORP keeps the document and its assets usable
 * as an embeddable resource while COEP is on.
 */
export const VIZZY_ISOLATION_HEADERS: Readonly<Record<string, string>> = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Cross-Origin-Resource-Policy": "cross-origin",
};

/**
 * CSP for the hosted editor. `wasm-unsafe-eval` is required for
 * WebAssembly.instantiate; shader compilation does not need `unsafe-eval`.
 */
export const VIZZY_CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self' 'wasm-unsafe-eval'",
  "worker-src 'self' blob:",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "media-src 'self' blob: camxora-media:",
  "connect-src 'self' blob: data:",
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".cjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".wasm": "application/wasm",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".ogg": "audio/ogg",
  ".flac": "audio/flac",
  ".fnt": "text/plain; charset=utf-8",
  ".obj": "text/plain; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

export function mimeForAsset(filePath: string): string {
  return MIME[path.extname(filePath).toLowerCase()] ?? "application/octet-stream";
}

export interface VizzyAsset {
  filePath: string;
  mime: string;
  size: number;
}

export type VizzyAssetLookup =
  | { ok: true; asset: VizzyAsset }
  | { ok: false; status: number; message: string };

function isInside(root: string, target: string): boolean {
  const relative = path.relative(root, target);
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

/**
 * Map a URL pathname to a file under `root`. Rejects traversal, NUL bytes,
 * encoded separators and anything that is not a regular file.
 */
export function resolveVizzyAsset(root: string, pathname: string): VizzyAssetLookup {  let decoded: string;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return { ok: false, status: 400, message: "Bad request" };
  }
  if (decoded.includes("\0")) return { ok: false, status: 400, message: "Bad request" };

  const relative = decoded.replace(/^[/\\]+/, "").replace(/\\/g, "/");
  const normalised = path.posix.normalize(relative === "" ? VIZZY_INDEX_PATH : relative);
  if (normalised === "." || normalised === ".." || normalised.startsWith("../")) {
    return { ok: false, status: 403, message: "Forbidden" };
  }

  const resolvedRoot = path.resolve(root);
  const filePath = path.resolve(resolvedRoot, normalised);
  if (!isInside(resolvedRoot, filePath)) return { ok: false, status: 403, message: "Forbidden" };

  let stat: fs.Stats;
  try {
    stat = fs.statSync(filePath);
  } catch {
    return { ok: false, status: 404, message: "Not found" };
  }
  if (!stat.isFile()) return { ok: false, status: 404, message: "Not found" };

  return { ok: true, asset: { filePath, mime: mimeForAsset(filePath), size: stat.size } };
}

/**
 * Resolve a hosted request. `/creations/*` comes from the staged template
 * library (when present); everything else comes from the built editor bundle.
 */
export function resolveVizzyRequest(
  root: string,
  libraryRoot: string | null,
  pathname: string,
): VizzyAssetLookup {
  if (libraryRoot && (pathname === "/creations" || pathname.startsWith("/creations/"))) {
    const creationsRoot = path.join(path.resolve(libraryRoot), "creations");
    return resolveVizzyAsset(creationsRoot, pathname.slice("/creations".length) || "/");
  }
  return resolveVizzyAsset(root, pathname);
}

/** Headers every response carries, including error responses. */
export function vizzyResponseHeaders(mime: string): Record<string, string> {
  return {
    ...VIZZY_ISOLATION_HEADERS,
    "Content-Type": mime,
    "Content-Security-Policy": VIZZY_CONTENT_SECURITY_POLICY,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Accept-Ranges": "bytes",
  };
}

export function vizzyAssetResponse(asset: VizzyAsset): Response {
  const bytes = fs.readFileSync(asset.filePath);
  return new Response(bytes, {
    status: 200,
    headers: {
      ...vizzyResponseHeaders(asset.mime),
      "Content-Length": String(bytes.byteLength),
    },
  });
}

export function vizzyErrorResponse(status: number, message: string): Response {
  return new Response(message, {
    status,
    headers: vizzyResponseHeaders("text/plain; charset=utf-8"),
  });
}

export interface VizzyByteRange {
  start: number;
  end: number;
}

/**
 * Parse a `Range` header for a single range. Multi-range and malformed values
 * are ignored (`null`), which makes the handler answer with the full body — the
 * safe behaviour for `<video>` and `WebAssembly.instantiateStreaming`.
 */
export function parseByteRange(header: string | null, size: number): VizzyByteRange | null {
  if (!header) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!match) return null;
  const [, rawStart, rawEnd] = match;
  if (rawStart === "" && rawEnd === "") return null;

  let start: number;
  let end: number;
  if (rawStart === "") {
    // Suffix range: the last N bytes.
    const length = Number(rawEnd);
    if (!Number.isFinite(length) || length <= 0) return null;
    start = Math.max(0, size - length);
    end = size - 1;
  } else {
    start = Number(rawStart);
    end = rawEnd === "" ? size - 1 : Number(rawEnd);
  }
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  if (start < 0 || end < start || start >= size) return null;
  return { start, end: Math.min(end, size - 1) };
}

/**
 * Production response: stream from disk, honour a single range, and keep every
 * header the isolation model needs.
 */
export function vizzyAssetStreamResponse(
  asset: VizzyAsset,
  rangeHeader: string | null,
  method: string,
): Response {
  const range = parseByteRange(rangeHeader, asset.size);
  const headers = vizzyResponseHeaders(asset.mime);

  if (method === "HEAD") {
    return new Response(null, {
      status: 200,
      headers: { ...headers, "Content-Length": String(asset.size) },
    });
  }

  if (range) {
    const length = range.end - range.start + 1;
    const stream = Readable.toWeb(
      fs.createReadStream(asset.filePath, { start: range.start, end: range.end }),
    ) as ReadableStream;
    return new Response(stream, {
      status: 206,
      headers: {
        ...headers,
        "Content-Length": String(length),
        "Content-Range": `bytes ${range.start}-${range.end}/${asset.size}`,
      },
    });
  }

  const stream = Readable.toWeb(fs.createReadStream(asset.filePath)) as ReadableStream;
  return new Response(stream, {
    status: 200,
    headers: { ...headers, "Content-Length": String(asset.size) },
  });
}
