import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { Readable } from "node:stream";
import { protocol } from "electron";
import { getAppPaths } from "./paths";
import { isPathInside, mimeFor, parseRange } from "./media-utils";

const allowedFiles = new Set<string>();
const tokens = new Map<string, string>();

export function registerMediaScheme(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: "camxora-media",
      privileges: {
        standard: true,
        secure: true,
        supportFetchAPI: true,
        stream: true,
      },
    },
  ]);
}

function managedRoots(): string[] {
  const paths = getAppPaths();
  return [paths.downloads, paths.renders, paths.images, paths.templates, paths.projects, paths.cache];
}

function allowFile(filePath: string): string {
  const resolved = fs.realpathSync(filePath);
  const stat = fs.statSync(resolved);
  if (!stat.isFile()) throw new Error("Not a file");
  if (!managedRoots().some((root) => isPathInside(root, resolved)) && !allowedFiles.has(resolved)) {
    throw new Error("Path is outside the managed media roots");
  }
  allowedFiles.add(resolved);
  return resolved;
}

export function allowPickedFile(filePath: string): void {
  try {
    allowedFiles.add(fs.realpathSync(filePath));
  } catch {
    // Ignore a path that disappeared between the picker and this call.
  }
}

export function createMediaUrl(filePath: string): string {
  const resolved = allowFile(filePath);
  const token = randomUUID();
  tokens.set(token, resolved);
  return `camxora-media://local/${token}`;
}

export function resolveMediaToken(token: string): string | null {
  return tokens.get(token) ?? null;
}

export async function handleMediaRequest(request: Request): Promise<Response> {
  try {
    const url = new URL(request.url);
    const token = decodeURIComponent(url.pathname.replace(/^\/+/, ""));
    const filePath = resolveMediaToken(token);
    if (!filePath) return new Response("Not found", { status: 404 });

    const stat = fs.statSync(filePath);
    const range = parseRange(request.headers.get("range"), stat.size);
    if (range === "invalid") {
      return new Response("Range not satisfiable", {
        status: 416,
        headers: { "Content-Range": `bytes */${stat.size}` },
      });
    }

    const start = range?.start ?? 0;
    const end = range?.end ?? stat.size - 1;
    const headers: Record<string, string> = {
      "Content-Type": mimeFor(filePath),
      "Accept-Ranges": "bytes",
      "Content-Length": String(end - start + 1),
      "Cache-Control": "private, max-age=300",
    };
    if (range) headers["Content-Range"] = `bytes ${start}-${end}/${stat.size}`;

    if (request.method === "HEAD") {
      return new Response(null, { status: range ? 206 : 200, headers });
    }

    const stream = fs.createReadStream(filePath, { start, end });
    return new Response(Readable.toWeb(stream) as ReadableStream, {
      status: range ? 206 : 200,
      headers,
    });
  } catch {
    return new Response("Not available", { status: 404 });
  }
}

export function mediaFileNameForLog(filePath: string): string {
  return path.basename(filePath);
}
