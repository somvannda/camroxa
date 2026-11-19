import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import AdmZip from "adm-zip";
import type { TemplateSchema } from "../shared/types";

/**
 * Marketplace template archive handling.
 *
 * Everything here is pure Node (no Electron imports) so the validation rules can
 * be unit tested directly. The install flow always validates the whole archive
 * before a single byte is written, which is what keeps a corrupt or hostile ZIP
 * from leaving a partial template on disk.
 */

export const MAX_ARCHIVE_BYTES = 200 * 1024 * 1024;
export const MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024;
export const MAX_ENTRY_COUNT = 4000;

export type TemplateArchiveCode =
  | "CORRUPT_ZIP"
  | "MISSING_TEMPLATE"
  | "INVALID_TEMPLATE"
  | "UNSAFE_ARCHIVE"
  | "ARCHIVE_TOO_LARGE";

export class TemplateArchiveError extends Error {
  constructor(
    public readonly code: TemplateArchiveCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateArchiveError";
  }
}

export interface TemplateArchive {
  template: Record<string, unknown>;
  manifest: Record<string, unknown>;
  name: string;
  kind: string;
  schema: TemplateSchema;
  schemaVersion: number;
  thumbnailEntry: string | null;
  entries: Array<{ entryName: string; normalized: string }>;
}

const TEMPLATE_FILE = "template.json";
const MANIFEST_FILE = "manifest.json";
const THUMBNAIL_FILES = new Set([
  "thumbnail.png",
  "thumbnail.jpg",
  "thumbnail.jpeg",
  "thumbnail.webp",
  "preview.png",
  "preview.jpg",
  "preview.jpeg",
  "preview.webp",
  "cover.png",
  "cover.jpg",
  "cover.jpeg",
  "cover.webp",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function parseJson(buffer: Buffer, file: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(buffer.toString("utf8"));
  } catch {
    throw new TemplateArchiveError("INVALID_TEMPLATE", `Invalid JSON in ${file}.`);
  }
  if (!isRecord(parsed)) {
    throw new TemplateArchiveError("INVALID_TEMPLATE", `${file} must be a JSON object.`);
  }
  return parsed;
}

/** Rejects absolute paths, traversal, NUL bytes and Windows drive prefixes. */
export function normalizeArchiveEntry(rawName: string): string {
  if (!rawName || rawName.includes("\0")) {
    throw new TemplateArchiveError("UNSAFE_ARCHIVE", "The template archive contains an invalid path.");
  }
  const slashed = rawName.replace(/\\/g, "/");
  if (slashed.startsWith("/") || /^[a-zA-Z]:/.test(slashed)) {
    throw new TemplateArchiveError("UNSAFE_ARCHIVE", "The template archive contains an absolute path.");
  }
  const segments = slashed.split("/").filter((segment) => segment.length > 0 && segment !== ".");
  if (segments.some((segment) => segment === "..")) {
    throw new TemplateArchiveError("UNSAFE_ARCHIVE", "The template archive contains a path traversal.");
  }
  if (segments.length === 0) {
    throw new TemplateArchiveError("UNSAFE_ARCHIVE", "The template archive contains an empty path.");
  }
  return segments.join("/");
}

function depthOf(normalized: string): number {
  return normalized.split("/").length - 1;
}

function isSymlink(entry: AdmZip.IZipEntry): boolean {
  const attributes = entry.header?.attr ?? entry.attr ?? 0;
  // Unix mode lives in the high 16 bits; 0xA000 is S_IFLNK.
  const mode = (attributes >>> 16) & 0xf000;
  return mode === 0xa000;
}

function normalizeSchema(value: unknown): TemplateSchema | null {
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return null;
  if (["legacy", "camxora", "camxora-v1", "v1", "old-camxora", "old"].includes(text)) {
    return "legacy";
  }
  if (["vizzy", "pipeline", "vizzy-pipeline", "2", "2.0", "2.0.0"].includes(text)) {
    return "vizzy";
  }
  return null;
}

/** Reads schema markers from the manifest first, then the template body. */
export function detectTemplateSchema(
  template: Record<string, unknown>,
  manifest: Record<string, unknown>,
): TemplateSchema {
  const candidates = [
    manifest.schema,
    manifest.template_schema,
    manifest.templateSchema,
    template.schema,
    template.template_schema,
    template.templateSchema,
  ];
  for (const candidate of candidates) {
    const schema = normalizeSchema(candidate);
    if (schema) return schema;
  }
  const engine = String(manifest.engine ?? template.engine ?? "").trim().toLowerCase();
  if (engine === "camxora" || engine === "camxora-legacy") return "legacy";
  if (manifest.legacy === true || template.legacy === true) return "legacy";
  return "vizzy";
}

function readSchemaVersion(template: Record<string, unknown>, manifest: Record<string, unknown>): number {
  for (const candidate of [
    template.schema_version,
    template.schemaVersion,
    manifest.schema_version,
    manifest.schemaVersion,
  ]) {
    const value = Number(candidate);
    if (Number.isFinite(value) && value > 0) return Math.trunc(value);
  }
  return 2;
}

function openArchive(buffer: Buffer): AdmZip {
  if (buffer.length === 0) {
    throw new TemplateArchiveError("CORRUPT_ZIP", "The template download was empty.");
  }
  if (buffer.length > MAX_ARCHIVE_BYTES) {
    throw new TemplateArchiveError("ARCHIVE_TOO_LARGE", "The template download is too large to install.");
  }
  let zip: AdmZip;
  try {
    zip = new AdmZip(buffer);
    // getEntries() parses the central directory and throws on a broken archive.
    const entries = zip.getEntries();
    if (entries.length === 0) {
      throw new TemplateArchiveError("CORRUPT_ZIP", "The template archive is empty.");
    }
    if (entries.length > MAX_ENTRY_COUNT) {
      throw new TemplateArchiveError("ARCHIVE_TOO_LARGE", "The template archive has too many files.");
    }
  } catch (error) {
    if (error instanceof TemplateArchiveError) throw error;
    throw new TemplateArchiveError("CORRUPT_ZIP", "The template file is corrupted.");
  }
  return zip;
}

/**
 * Validates the whole archive and returns its metadata plus the safe entry map.
 * Nothing is written to disk here.
 */
export function readTemplateArchive(buffer: Buffer): TemplateArchive {
  const zip = openArchive(buffer);
  const entries: Array<{ entry: AdmZip.IZipEntry; entryName: string; normalized: string }> = [];
  const seen = new Set<string>();
  let totalBytes = 0;

  for (const entry of zip.getEntries()) {
    if (entry.isDirectory) {
      // Directory names are validated too: a traversal directory is a hostile archive.
      normalizeArchiveEntry(entry.entryName);
      continue;
    }
    if (isSymlink(entry)) {
      throw new TemplateArchiveError("UNSAFE_ARCHIVE", "The template archive contains a link.");
    }
    const normalized = normalizeArchiveEntry(entry.entryName);
    if (seen.has(normalized.toLowerCase())) {
      throw new TemplateArchiveError("CORRUPT_ZIP", "The template archive contains duplicate files.");
    }
    seen.add(normalized.toLowerCase());
    const size = Number(entry.header?.size ?? 0);
    if (Number.isFinite(size) && size > 0) totalBytes += size;
    if (totalBytes > MAX_UNCOMPRESSED_BYTES) {
      throw new TemplateArchiveError("ARCHIVE_TOO_LARGE", "The template archive is too large to install.");
    }
    entries.push({ entry, entryName: entry.entryName, normalized });
  }

  const pickShallowest = (basename: string): string | null => {
    let best: { depth: number; normalized: string } | null = null;
    for (const item of entries) {
      if (item.normalized.split("/").pop() !== basename) continue;
      const depth = depthOf(item.normalized);
      if (!best || depth < best.depth) best = { depth, normalized: item.normalized };
    }
    return best?.normalized ?? null;
  };

  const templateEntry = pickShallowest(TEMPLATE_FILE);
  const manifestEntry = pickShallowest(MANIFEST_FILE);
  if (!templateEntry || !manifestEntry) {
    throw new TemplateArchiveError(
      "MISSING_TEMPLATE",
      "The template archive is missing template.json or manifest.json.",
    );
  }

  const readEntry = (normalized: string): Buffer => {
    const match = entries.find((item) => item.normalized === normalized);
    if (!match) {
      throw new TemplateArchiveError("CORRUPT_ZIP", "The template file is corrupted.");
    }
    try {
      return match.entry.getData();
    } catch {
      throw new TemplateArchiveError("CORRUPT_ZIP", "The template file is corrupted.");
    }
  };

  const template = parseJson(readEntry(templateEntry), TEMPLATE_FILE);
  const manifest = parseJson(readEntry(manifestEntry), MANIFEST_FILE);

  let thumbnailEntry: string | null = null;
  for (const item of entries) {
    const basename = item.normalized.split("/").pop()?.toLowerCase() ?? "";
    if (!THUMBNAIL_FILES.has(basename)) continue;
    if (!thumbnailEntry || depthOf(item.normalized) < depthOf(thumbnailEntry)) {
      thumbnailEntry = item.normalized;
    }
  }

  const name = String(manifest.name ?? template.name ?? "").trim() || "Untitled template";
  const kind = String(manifest.kind ?? template.kind ?? "video").trim().toLowerCase() || "video";

  return {
    template,
    manifest,
    name,
    kind,
    schema: detectTemplateSchema(template, manifest),
    schemaVersion: readSchemaVersion(template, manifest),
    thumbnailEntry,
    entries: entries.map((item) => ({ entryName: item.entryName, normalized: item.normalized })),
  };
}

/**
 * Extracts a validated archive into `targetDir`.
 *
 * Paths are re-checked against the resolved target root, so a bug in the entry
 * normaliser cannot still escape the template folder.
 */
export function extractTemplateArchive(buffer: Buffer, targetDir: string): TemplateArchive {
  const archive = readTemplateArchive(buffer);
  const zip = openArchive(buffer);
  const root = path.resolve(targetDir);
  const rootPrefix = root.endsWith(path.sep) ? root : `${root}${path.sep}`;

  for (const entry of zip.getEntries()) {
    if (entry.isDirectory) continue;
    const normalized = normalizeArchiveEntry(entry.entryName);
    const destination = path.resolve(root, normalized);
    if (destination !== root && !destination.startsWith(rootPrefix)) {
      throw new TemplateArchiveError("UNSAFE_ARCHIVE", "The template archive contains a path traversal.");
    }
    fs.mkdirSync(path.dirname(destination), { recursive: true });
    fs.writeFileSync(destination, entry.getData(), { flag: "wx" });
  }

  return archive;
}

/** Deterministic digest used for preview cache keys. */
export function digest(value: string): string {
  return crypto.createHash("sha256").update(value).digest("hex").slice(0, 32);
}
