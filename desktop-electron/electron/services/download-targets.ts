/**
 * Where a pending Suno download may land, and which URLs may be fetched.
 *
 * The server sends absolute paths that were written on some machine; the shell
 * only honours a path that stays inside this device's output root. Everything
 * here is pure so the rules can be tested without Electron, the network or disk.
 */
import path from "node:path";
import { isPathInside } from "./media-utils";

export type DownloadTargetRole = "primary" | "secondary";

export interface PendingDownloadTarget {
  download_url?: string | null;
  downloaded?: boolean;
  output_dir?: string | null;
  target_path?: string | null;
}

export interface PendingDownloadItem {
  task_id: string;
  song_id?: string | null;
  batch_id?: string | null;
  title?: string | null;
  track_number?: number | null;
  primary?: PendingDownloadTarget | null;
  secondary?: PendingDownloadTarget | null;
}

export interface DownloadTargetInput {
  taskId: string;
  role: DownloadTargetRole;
  songId: string | null;
  batchId: string | null;
  title: string | null;
  trackNumber: number | null;
  url: string | null;
  targetPath: string | null;
  outputDir: string | null;
}

export interface ResolvedDownloadTarget {
  key: string;
  taskId: string;
  role: DownloadTargetRole;
  songId: string | null;
  batchId: string | null;
  title: string;
  trackNumber: number | null;
  url: string;
  /** Absolute file path inside the root. */
  path: string;
  root: string;
}

export type TargetResolution =
  | { ok: true; target: ResolvedDownloadTarget }
  | { ok: false; code: string; message: string };

export interface TargetResolutionOptions {
  /** Absolute output root; every target must stay inside it. */
  root: string;
  /** Loopback `http://` is only accepted when `CAMXORA_E2E=1`. */
  allowLoopbackHttp?: boolean;
}

export const DOWNLOAD_URL_MISSING_MESSAGE =
  "The server did not provide a download link for this song.";
export const DOWNLOAD_URL_GONE_MESSAGE = "The download link is no longer available.";
export const DOWNLOAD_URL_INVALID_MESSAGE = "The download link is not a supported address.";
export const DOWNLOAD_URL_FORBIDDEN_MESSAGE = "The server refused this download.";
export const DOWNLOAD_TARGET_UNSAFE_MESSAGE = "The target path escapes the output folder.";
export const DOWNLOAD_TARGET_OUTSIDE_MESSAGE =
  "The target path is outside this device's Suno output folder.";
export const DOWNLOAD_NOT_A_FILE_MESSAGE = "The target path is a folder, not a file.";

const AUDIO_EXTENSIONS = new Set([".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"]);
const INVALID_FILENAME_CHAR = /[<>:"/\\|?*]/;

function stripUnsafeFileNameCharacters(value: string): string {
  let output = "";
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0;
    if (code < 32 || code === 127) {
      output += "-";
      continue;
    }
    output += INVALID_FILENAME_CHAR.test(char) ? "-" : char;
  }
  return output;
}

export function targetKey(taskId: string, role: DownloadTargetRole): string {
  return `${taskId}::${role}`;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

/** Server items are data, never trusted to be well shaped. */
export function normalizePendingDownloads(payload: unknown): PendingDownloadItem[] {
  const root = (payload && typeof payload === "object" ? payload : {}) as { items?: unknown };
  const raw = Array.isArray(root.items) ? root.items : [];
  const items: PendingDownloadItem[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const record = entry as Record<string, unknown>;
    const taskId = stringValue(record.task_id);
    if (!taskId) continue;
    const track = typeof record.track_number === "number" ? record.track_number : null;
    items.push({
      task_id: taskId,
      song_id: stringValue(record.song_id),
      batch_id: stringValue(record.batch_id),
      title: stringValue(record.title),
      track_number: track,
      primary: targetOf(record.primary),
      secondary: targetOf(record.secondary),
    });
  }
  return items;
}

function targetOf(value: unknown): PendingDownloadTarget | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const target: PendingDownloadTarget = {
    download_url: stringValue(record.download_url),
    downloaded: record.downloaded === true,
    output_dir: stringValue(record.output_dir),
    target_path: stringValue(record.target_path),
  };
  if (typeof record.download_url === "string" && !target.download_url) target.download_url = "";
  return target;
}

/** True for absolute paths that leave the root, and for any `..` segment. */
export function hasTraversal(value: string): boolean {
  if (value.includes("\u0000")) return true;
  return value.split(/[\\/]+/).some((segment) => segment === "..");
}

function isLoopbackHost(hostname: string): boolean {
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (host === "::1" || host === "0:0:0:0:0:0:0:1") return true;
  return /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host);
}

export interface UrlCheck {
  ok: boolean;
  code?: string;
  message?: string;
}

/**
 * Only `http(s)` URLs are fetched. Credentials inside the URL are refused so a
 * malformed server value can never leak them into a request or a log line.
 */
export function checkDownloadUrl(raw: string | null, allowLoopbackHttp: boolean): UrlCheck {
  const value = raw?.trim() ?? "";
  if (!value) return { ok: false, code: "DOWNLOAD_URL_MISSING", message: DOWNLOAD_URL_MISSING_MESSAGE };
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return { ok: false, code: "DOWNLOAD_URL_INVALID", message: DOWNLOAD_URL_INVALID_MESSAGE };
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { ok: false, code: "DOWNLOAD_URL_INVALID", message: DOWNLOAD_URL_INVALID_MESSAGE };
  }
  if (url.username || url.password) {
    return { ok: false, code: "DOWNLOAD_URL_INVALID", message: DOWNLOAD_URL_INVALID_MESSAGE };
  }
  if (url.protocol === "http:" && isLoopbackHost(url.hostname) && !allowLoopbackHttp) {
    return {
      ok: false,
      code: "DOWNLOAD_URL_INVALID",
      message: "Loopback download links are only allowed in end-to-end test runs.",
    };
  }
  return { ok: true };
}

export function sanitizeFileStem(value: string): string {
  const cleaned = stripUnsafeFileNameCharacters(value)
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[. ]+$/, "");
  return cleaned || "download";
}

export function defaultDownloadFileName(
  title: string | null,
  trackNumber: number | null,
  songId: string | null,
): string {
  const stem = sanitizeFileStem(title?.trim() || songId?.trim() || "download");
  const track =
    typeof trackNumber === "number" && Number.isFinite(trackNumber) && trackNumber > 0
      ? String(Math.trunc(trackNumber)).padStart(2, "0")
      : null;
  const name = track ? `${track} ${stem}` : stem;
  return `${name.slice(0, 150)}.mp3`;
}

function endsWithSeparator(value: string): boolean {
  return /[\\/]$/.test(value);
}

function looksLikeDirectory(value: string): boolean {
  if (endsWithSeparator(value)) return true;
  const base = path.basename(value);
  return !base || base === "." || base === "..";
}

function withExtension(filePath: string): string {
  const extension = path.extname(filePath);
  if (!extension) return `${filePath}.mp3`;
  return AUDIO_EXTENSIONS.has(extension.toLowerCase()) ? filePath : `${filePath}.mp3`;
}

function failure(code: string, message: string): TargetResolution {
  return { ok: false, code, message };
}

/**
 * Resolves one pending target into an absolute path under `root`.
 *
 * Rules, in order: URL must be http(s); the raw target may not contain `..`;
 * an absolute target must already be inside the root; a relative target is
 * joined to the root; a missing target uses `output_dir` (inside the root) or
 * the root plus a sanitised `<track> <title>.mp3`.
 */
export function resolveDownloadTarget(
  input: DownloadTargetInput,
  options: TargetResolutionOptions,
): TargetResolution {
  const urlCheck = checkDownloadUrl(input.url, options.allowLoopbackHttp === true);
  if (!urlCheck.ok) {
    return failure(urlCheck.code ?? "DOWNLOAD_URL_INVALID", urlCheck.message ?? DOWNLOAD_URL_INVALID_MESSAGE);
  }

  const root = path.resolve(options.root);
  const rawTarget = input.targetPath?.trim() ?? "";
  const rawOutput = input.outputDir?.trim() ?? "";
  const fallbackName = defaultDownloadFileName(input.title, input.trackNumber, input.songId);

  if (rawTarget && hasTraversal(rawTarget)) {
    return failure("DOWNLOAD_TARGET_UNSAFE", DOWNLOAD_TARGET_UNSAFE_MESSAGE);
  }
  if (rawOutput && hasTraversal(rawOutput)) {
    return failure("DOWNLOAD_TARGET_UNSAFE", DOWNLOAD_TARGET_UNSAFE_MESSAGE);
  }

  let candidate: string;
  if (rawTarget) {
    if (looksLikeDirectory(rawTarget)) {
      return failure("DOWNLOAD_NOT_A_FILE", DOWNLOAD_NOT_A_FILE_MESSAGE);
    }
    candidate = path.isAbsolute(rawTarget)
      ? path.resolve(rawTarget)
      : path.resolve(root, rawTarget);
  } else {
    let directory = root;
    if (rawOutput) {
      if (!path.isAbsolute(rawOutput)) {
        return failure("DOWNLOAD_TARGET_OUTSIDE", DOWNLOAD_TARGET_OUTSIDE_MESSAGE);
      }
      directory = path.resolve(rawOutput);
      if (!isPathInside(root, directory)) {
        return failure("DOWNLOAD_TARGET_OUTSIDE", DOWNLOAD_TARGET_OUTSIDE_MESSAGE);
      }
    }
    candidate = path.join(directory, fallbackName);
  }

  candidate = withExtension(candidate);
  if (!isPathInside(root, candidate)) {
    return failure("DOWNLOAD_TARGET_OUTSIDE", DOWNLOAD_TARGET_OUTSIDE_MESSAGE);
  }
  const filename = path.basename(candidate);
  if (!filename || filename === "." || filename === "..") {
    return failure("DOWNLOAD_NOT_A_FILE", DOWNLOAD_NOT_A_FILE_MESSAGE);
  }

  return {
    ok: true,
    target: {
      key: targetKey(input.taskId, input.role),
      taskId: input.taskId,
      role: input.role,
      songId: input.songId,
      batchId: input.batchId,
      title: input.title?.trim() || input.songId || input.taskId,
      trackNumber: input.trackNumber,
      url: (input.url ?? "").trim(),
      path: candidate,
      root,
    },
  };
}
