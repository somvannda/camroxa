/**
 * Path containment for the manual YouTube upload.
 *
 * The renderer may only name a merged file; the main process decides whether
 * that file is uploadable. A file is accepted only when its real path sits
 * inside this run folder or inside the app-managed downloads/renders roots, so
 * `..\..\secret.mp4`, a symlink escape or a file picked from anywhere else is
 * refused before any byte leaves the machine.
 */
import fs from "node:fs";
import path from "node:path";
import { isPathInside } from "./media-utils";

export type UploadFileErrorCode =
  | "UPLOAD_FILE_MISSING"
  | "UPLOAD_FILE_NOT_VIDEO"
  | "UPLOAD_FILE_OUTSIDE_ROOTS"
  | "UPLOAD_FILE_EMPTY";

export class UploadFileError extends Error {
  constructor(
    public readonly code: UploadFileErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "UploadFileError";
  }
}

export interface ContainedFile {
  /** Canonical absolute path (symlinks resolved). */
  path: string;
  name: string;
  bytes: number;
}

export function isContainedIn(filePath: string, roots: Array<string | null | undefined>): boolean {
  const target = path.resolve(String(filePath ?? ""));
  for (const root of roots) {
    if (!root) continue;
    const base = path.resolve(String(root));
    if (isPathInside(base, target)) return true;
  }
  return false;
}

function realpathOrNull(value: string): string | null {
  try {
    return fs.realpathSync(value);
  } catch {
    return null;
  }
}

/**
 * Validates one candidate file against the run folder and managed roots.
 * Every comparison uses the canonical path, so a symlinked folder cannot be
 * used to read something outside the allowed area.
 */
export function resolveContainedVideo(input: {
  filePath: string;
  runDir?: string | null;
  managedRoots: string[];
}): ContainedFile {
  const requested = String(input.filePath ?? "").trim();
  if (!requested) {
    throw new UploadFileError("UPLOAD_FILE_MISSING", "No merged video was selected for this upload.");
  }
  const extension = path.extname(requested).toLowerCase();
  if (extension !== ".mp4") {
    throw new UploadFileError("UPLOAD_FILE_NOT_VIDEO", "Only an MP4 merged video can be uploaded.");
  }

  let resolved: string;
  try {
    resolved = fs.realpathSync(requested);
  } catch {
    throw new UploadFileError(
      "UPLOAD_FILE_MISSING",
      "The merged video is not on disk any more. Merge the run again, then upload.",
    );
  }

  let stat: fs.Stats;
  try {
    stat = fs.statSync(resolved);
  } catch {
    throw new UploadFileError(
      "UPLOAD_FILE_MISSING",
      "The merged video is not on disk any more. Merge the run again, then upload.",
    );
  }
  if (!stat.isFile()) {
    throw new UploadFileError("UPLOAD_FILE_MISSING", "That path is not a file.");
  }
  if (stat.size <= 0) {
    throw new UploadFileError("UPLOAD_FILE_EMPTY", "The merged video is empty. Merge the run again.");
  }

  const canonicalRoots: string[] = [];
  const runDir = String(input.runDir ?? "").trim();
  if (runDir) {
    const realRunDir = realpathOrNull(runDir);
    if (realRunDir) canonicalRoots.push(realRunDir);
  }
  for (const root of input.managedRoots) {
    if (!root) continue;
    const realRoot = realpathOrNull(root) ?? path.resolve(root);
    canonicalRoots.push(realRoot);
  }

  if (!isContainedIn(resolved, canonicalRoots)) {
    throw new UploadFileError(
      "UPLOAD_FILE_OUTSIDE_ROOTS",
      "That video is outside this run folder and the Camxora downloads/renders folders, so it cannot be uploaded.",
    );
  }

  return { path: resolved, name: path.basename(resolved), bytes: stat.size };
}

function newestMp4(directory: string, options: { excludeReel: boolean }): string | null {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(directory, { withFileTypes: true });
  } catch {
    return null;
  }
  let best: { filePath: string; mtime: number } | null = null;
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const name = entry.name;
    if (!/\.mp4$/i.test(name)) continue;
    if (options.excludeReel && /reel/i.test(name)) continue;
    const filePath = path.join(directory, name);
    try {
      const stat = fs.statSync(filePath);
      if (!stat.isFile() || stat.size <= 0) continue;
      if (!best || stat.mtimeMs > best.mtime) best = { filePath, mtime: stat.mtimeMs };
    } catch {
      // A file that vanished between readdir and stat is simply skipped.
    }
  }
  return best?.filePath ?? null;
}

/**
 * The newest long-form merge in a run folder. Mirrors the 1.7.1 rule: prefer a
 * `*-merged` / `MERGED_*` name, ignore reel variants, and only fall back to a
 * generic MP4 or a `merged/` subfolder when nothing else matches.
 */
export function discoverMergedFile(runDir: string): string | null {
  const directory = String(runDir ?? "").trim();
  if (!directory) return null;
  try {
    if (!fs.statSync(directory).isDirectory()) return null;
  } catch {
    return null;
  }

  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(directory, { withFileTypes: true });
  } catch {
    return null;
  }
  let merged: { filePath: string; mtime: number } | null = null;
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (!/merged.*\.mp4$/i.test(entry.name) || /reel/i.test(entry.name)) continue;
    const filePath = path.join(directory, entry.name);
    try {
      const stat = fs.statSync(filePath);
      if (!stat.isFile() || stat.size <= 0) continue;
      if (!merged || stat.mtimeMs > merged.mtime) merged = { filePath, mtime: stat.mtimeMs };
    } catch {
      // skipped
    }
  }
  if (merged) return merged.filePath;

  const fallback = newestMp4(directory, { excludeReel: true });
  if (fallback) return fallback;

  const sub = path.join(directory, "merged");
  try {
    if (fs.statSync(sub).isDirectory()) return newestMp4(sub, { excludeReel: true });
  } catch {
    return null;
  }
  return null;
}

/** `thumbnail-16x9.png` beside the merged file, when it exists inside the run. */
export function thumbnailBeside(videoPath: string): string | null {
  const candidate = path.join(path.dirname(videoPath), "thumbnail-16x9.png");
  try {
    const stat = fs.statSync(candidate);
    return stat.isFile() && stat.size > 0 ? candidate : null;
  } catch {
    return null;
  }
}
