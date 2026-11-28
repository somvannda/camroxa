import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { BrowserWindow } from "electron";
import { resolveApiBaseUrl } from "./endpoints";
import {
  type InstallTemplateRequest,
  type InstallTemplateResult,
  type InstalledTemplate,
  type TemplateChangedEvent,
  type TemplateSchema,
} from "../shared/types";
import { logger } from "./logger";
import { getAppPaths } from "./paths";
import { sessionStore } from "./session";
import { getStore } from "./store";
import type { TemplateRecord } from "./database";
import { writeTemplatePipeline } from "./video-templates";
import {
  extractTemplateArchive,
  MAX_ARCHIVE_BYTES,
  readTemplateArchive,
  TemplateArchiveError,
} from "./template-archive";

const DOWNLOAD_TIMEOUT_MS = 60_000;
const PREVIEW_TIMEOUT_MS = 20_000;
const MAX_PREVIEW_BYTES = 8 * 1024 * 1024;
const PREVIEW_CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export class TemplateInstallError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = "TemplateInstallError";
  }
}

function apiBaseUrl(): string {
  return resolveApiBaseUrl();
}

function authHeaders(accept: string): Record<string, string> {
  const token = sessionStore.load()?.accessToken;
  if (!token) {
    throw new TemplateInstallError("UNAUTHORIZED", "Sign in to install templates.");
  }
  return {
    Authorization: `Bearer ${token}`,
    Accept: accept,
    "X-Camxora-Client": "desktop",
  };
}

function statusMessage(status: number, action: string): string {
  if (status === 401) return "Session expired. Sign in again to install templates.";
  if (status === 403) return `${action} is not allowed for this account.`;
  if (status === 404) return "That template is no longer in the catalog.";
  if (status === 429) return "Too many requests. Wait a moment and try again.";
  if (status >= 500) return `${action} failed on the server (${status}). Try again later.`;
  return `${action} failed (${status}).`;
}

async function fetchBytes(pathname: string, accept: string): Promise<Buffer> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${pathname}`, {
      headers: authHeaders(accept),
      signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
    });
  } catch {
    throw new TemplateInstallError(
      "NETWORK_ERROR",
      "Cannot reach Camxora. Check your connection and try again.",
      true,
    );
  }
  if (!response.ok) {
    throw new TemplateInstallError(
      response.status === 404 ? "NOT_FOUND" : `HTTP_${response.status}`,
      statusMessage(response.status, "Template download"),
      response.status === 408 || response.status === 429 || response.status >= 500,
    );
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  if (buffer.length === 0) {
    throw new TemplateInstallError("EMPTY_DOWNLOAD", "The template download was empty.");
  }
  if (buffer.length > MAX_ARCHIVE_BYTES) {
    throw new TemplateInstallError("ARCHIVE_TOO_LARGE", "The template download is too large to install.");
  }
  return buffer;
}

function fsErrorMessage(error: unknown): string {
  const code = (error as NodeJS.ErrnoException | undefined)?.code;
  if (code === "ENOSPC") return "Not enough disk space to install the template.";
  if (code === "EACCES" || code === "EPERM") {
    return "Permission denied. Camxora cannot write to the template folder.";
  }
  if (code === "EBUSY" || code === "ENOTEMPTY") {
    return "The template folder is in use. Close anything reading it and try again.";
  }
  return "Unable to write the template to disk.";
}

function schemaForRecord(schemaVersion: number, templatePath: string): TemplateSchema {
  try {
    const raw = JSON.parse(fs.readFileSync(templatePath, "utf8")) as Record<string, unknown>;
    const value = String(raw.schema ?? raw.template_schema ?? "").trim().toLowerCase();
    if (["legacy", "camxora", "camxora-v1", "v1"].includes(value)) return "legacy";
  } catch {
    // A missing template.json is handled by the archive validation on install;
    // for listing, treat unreadable metadata as the 2.0.0 pipeline schema.
  }
  return schemaVersion >= 2 ? "vizzy" : "legacy";
}

function toInstalled(record: TemplateRecord): InstalledTemplate {
  return {
    id: record.id,
    name: record.name,
    kind: record.kind,
    schemaVersion: record.schemaVersion,
    schema: schemaForRecord(record.schemaVersion, record.path),
    path: record.path,
    thumbnailPath: record.thumbnailPath,
    marketplaceItemId: record.marketplaceItemId ?? null,
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  };
}

export function listInstalledTemplates(): InstalledTemplate[] {
  return getStore().listTemplates().map(toInstalled);
}

/** Notifies every window so template pickers refresh without a restart. */
export function notifyTemplatesChanged(event: TemplateChangedEvent): void {
  for (const window of BrowserWindow.getAllWindows()) {
    window.webContents.send("templates:changed", event);
  }
}

function installRoot(): string {
  const directory = getAppPaths().templates;
  fs.mkdirSync(directory, { recursive: true });
  return directory;
}

export async function installTemplate(request: InstallTemplateRequest): Promise<InstallTemplateResult> {
  const store = getStore();
  const existing = store.findTemplateByMarketplaceItem(request.itemId);
  if (existing && !request.reinstall) {
    throw new TemplateInstallError("ALREADY_INSTALLED", "This template is already installed.");
  }

  const buffer = await fetchBytes(
    `/marketplace/items/${encodeURIComponent(request.itemId)}/download`,
    "application/zip",
  );

  let archive;
  try {
    archive = readTemplateArchive(buffer);
  } catch (error) {
    if (error instanceof TemplateArchiveError) {
      throw new TemplateInstallError(error.code, error.message);
    }
    throw error;
  }

  if (archive.schema === "legacy") {
    throw new TemplateInstallError(
      "LEGACY_TEMPLATE",
      "This is an old Camxora template. Legacy templates are not supported in Camxora Desktop 2.0.0.",
    );
  }

  const uid = existing?.id ?? crypto.randomUUID();
  const root = installRoot();
  const staging = path.join(root, `.staging-${crypto.randomUUID()}`);
  const destination = path.join(root, uid);
  const backup = path.join(root, `.backup-${crypto.randomUUID()}`);
  let movedExisting = false;

  try {
    fs.mkdirSync(staging, { recursive: true });
    extractTemplateArchive(buffer, staging);

    // Make the item a first-class Studio template immediately: the picker and
    // auto-video list folders that carry both template.json and pipeline.json.
    const pipeline = writeTemplatePipeline(staging, archive.name, {
      projectFile: archive.templateEntry,
    });
    if (pipeline && archive.templateEntry !== "template.json") {
      // A nested project has to exist at the folder root for the picker.
      fs.copyFileSync(
        path.join(staging, archive.templateEntry),
        path.join(staging, "template.json"),
      );
    }

    if (fs.existsSync(destination)) {
      fs.renameSync(destination, backup);
      movedExisting = true;
    }
    fs.renameSync(staging, destination);
  } catch (error) {
    fs.rmSync(staging, { recursive: true, force: true });
    if (movedExisting && !fs.existsSync(destination) && fs.existsSync(backup)) {
      try {
        fs.renameSync(backup, destination);
      } catch {
        // The original folder is kept under `.backup-*` rather than deleted.
      }
    }
    if (error instanceof TemplateArchiveError) {
      throw new TemplateInstallError(error.code, error.message);
    }
    throw new TemplateInstallError("WRITE_FAILED", fsErrorMessage(error));
  }

  if (movedExisting) {
    fs.rmSync(backup, { recursive: true, force: true });
  }

  const now = Date.now();
  const thumbnailPath = archive.thumbnailEntry
    ? path.join(destination, archive.thumbnailEntry)
    : null;

  store.upsertTemplate({
    id: uid,
    name: archive.name || request.name?.trim() || "Untitled template",
    kind: archive.kind || request.kind?.trim().toLowerCase() || "video",
    schemaVersion: archive.schemaVersion,
    path: path.join(destination, "template.json"),
    thumbnailPath,
    marketplaceItemId: request.itemId,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  });

  logger.info("template installed", {
    itemId: request.itemId,
    uid,
    schema: archive.schema,
    reinstalled: Boolean(existing),
  });
  notifyTemplatesChanged({ uid, itemId: request.itemId, reinstalled: Boolean(existing) });

  return {
    uid,
    name: archive.name,
    kind: archive.kind,
    schema: archive.schema,
    reinstalled: Boolean(existing),
  };
}

function resolvePreviewUrl(rawUrl: string, itemId: string): URL {
  let candidate = rawUrl.trim();
  if (!candidate) {
    candidate = `/marketplace/items/${encodeURIComponent(itemId)}/preview`;
  }

  let url: URL;
  if (/^https?:\/\//i.test(candidate)) {
    try {
      url = new URL(candidate);
    } catch {
      throw new TemplateInstallError("INVALID_PREVIEW", "The catalog returned an invalid preview address.");
    }
  } else {
    const base = new URL(apiBaseUrl());
    if (candidate.startsWith("/api/v1/") || candidate.startsWith("/api/v3/")) {
      url = new URL(candidate, base.origin);
    } else if (candidate.startsWith("/")) {
      url = new URL(candidate, apiBaseUrl());
    } else {
      url = new URL(`/marketplace/items/${encodeURIComponent(itemId)}/preview`, base.origin);
    }
  }

  // Never attach the session token to a host other than the configured API.
  if (url.origin !== new URL(apiBaseUrl()).origin) {
    throw new TemplateInstallError("INVALID_PREVIEW", "The catalog preview host is not allowed.");
  }
  return url;
}

function previewCacheDir(): string {
  const directory = path.join(getAppPaths().cache, "marketplace-previews");
  fs.mkdirSync(directory, { recursive: true });
  return directory;
}

function cacheKey(itemId: string, url: string): string {
  return crypto.createHash("sha256").update(`${itemId}\n${url}`).digest("hex").slice(0, 40);
}

function dataUrlFor(buffer: Buffer, contentType: string | null): string {
  const mime = contentType?.startsWith("image/")
    ? contentType.split(";")[0]
    : "image/png";
  return `data:${mime};base64,${buffer.toString("base64")}`;
}

/**
 * Fetches a marketplace preview through the main process and returns a data URL.
 * The renderer never talks to the remote host, so the session token stays here.
 */
export async function loadMarketplacePreview(itemId: string, previewUrl: string): Promise<string> {
  const url = resolvePreviewUrl(previewUrl, itemId);
  const key = cacheKey(itemId, url.toString());
  const file = path.join(previewCacheDir(), `${key}.img`);
  const metaFile = `${file}.json`;

  try {
    const stat = fs.statSync(file);
    if (Date.now() - stat.mtimeMs < PREVIEW_CACHE_TTL_MS) {
      const meta = JSON.parse(fs.readFileSync(metaFile, "utf8")) as { mime?: string };
      return dataUrlFor(fs.readFileSync(file), meta.mime ?? null);
    }
  } catch {
    // Cache miss: fall through to the network.
  }

  let response: Response;
  try {
    response = await fetch(url, {
      headers: authHeaders("image/*"),
      signal: AbortSignal.timeout(PREVIEW_TIMEOUT_MS),
    });
  } catch {
    throw new TemplateInstallError("NETWORK_ERROR", "Preview unavailable. Check your connection.");
  }
  if (!response.ok) {
    throw new TemplateInstallError(
      `HTTP_${response.status}`,
      `Preview unavailable (${response.status}).`,
    );
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  if (buffer.length === 0) {
    throw new TemplateInstallError("EMPTY_PREVIEW", "Preview unavailable.");
  }
  if (buffer.length > MAX_PREVIEW_BYTES) {
    throw new TemplateInstallError("PREVIEW_TOO_LARGE", "Preview unavailable.");
  }

  const contentType = response.headers.get("content-type");
  try {
    fs.writeFileSync(file, buffer);
    fs.writeFileSync(metaFile, JSON.stringify({ mime: contentType ?? "image/png" }));
  } catch {
    // Caching is best effort; the preview still renders this session.
  }
  return dataUrlFor(buffer, contentType);
}
