/**
 * Native project files for the hosted Vizzy editor.
 *
 * The editor serialises its own `ProjectSnapshot` (`format: "studio-project"`);
 * Camxora owns only where the file lives and how it is written. Everything in
 * this module is pure Node so it can be unit-tested without Electron.
 */
import fs from "node:fs";
import path from "node:path";

export const VIZZY_PROJECT_FORMAT = "studio-project";
export const VIZZY_PROJECT_EXTENSION = ".camxora-vizzy.json";
export const VIZZY_PROJECT_MAX_BYTES = 64 * 1024 * 1024;

/** Default title when the editor has not named its project yet. */
const FALLBACK_NAME = "untitled-project";

/** Filesystem-safe slug; empty/dot-only names fall back to "untitled-project". */
export function slugifyProjectName(name: string): string {
  const slug = name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return slug.length > 0 ? slug : FALLBACK_NAME;
}

/** `projects/<slug>.camxora-vizzy.json` — a stable path per project name. */
export function projectFilePath(projectsDir: string, name: string): string {
  return path.join(path.resolve(projectsDir), `${slugifyProjectName(name)}${VIZZY_PROJECT_EXTENSION}`);
}

/** True only when `target` is strictly inside `root` (no traversal). */
export function isInsidePath(root: string, target: string): boolean {
  const resolvedRoot = path.resolve(root);
  const resolvedTarget = path.resolve(target);
  const relative = path.relative(resolvedRoot, resolvedTarget);
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

export function ensureProjectsDir(projectsDir: string): string {
  const resolved = path.resolve(projectsDir);
  fs.mkdirSync(resolved, { recursive: true });
  return resolved;
}

/**
 * Write through a sibling temp file and rename, so a crash mid-write cannot
 * leave a truncated project behind. The rename is atomic on NTFS and POSIX.
 */
export function atomicWriteText(filePath: string, contents: string): void {
  const directory = path.dirname(filePath);
  fs.mkdirSync(directory, { recursive: true });
  const tmp = path.join(
    directory,
    `.${path.basename(filePath)}.${process.pid}-${Date.now().toString(36)}.tmp`,
  );
  let fd: number | null = null;
  try {
    fd = fs.openSync(tmp, "wx");
    fs.writeFileSync(fd, contents, "utf8");
    fs.fsyncSync(fd);
  } catch (error) {
    if (fd !== null) {
      try {
        fs.closeSync(fd);
      } catch {
        /* already closed */
      }
      fd = null;
    }
    try {
      fs.unlinkSync(tmp);
    } catch {
      /* nothing to clean up */
    }
    throw error;
  } finally {
    if (fd !== null) fs.closeSync(fd);
  }
  fs.renameSync(tmp, filePath);
}

export type VizzyProjectRead =
  | { ok: true; text: string; snapshot: Record<string, unknown> }
  | { ok: false; code: string; message: string };

/**
 * Read and validate a project file. The snapshot shape check mirrors Rea's
 * `isProjectSnapshot` so a stray JSON file cannot be forced into the editor.
 */
export function readProjectFile(filePath: string): VizzyProjectRead {
  const resolved = path.resolve(filePath);
  let stat: fs.Stats;
  try {
    stat = fs.statSync(resolved);
  } catch {
    return { ok: false, code: "PROJECT_NOT_FOUND", message: "That project file does not exist." };
  }
  if (!stat.isFile()) {
    return { ok: false, code: "PROJECT_NOT_A_FILE", message: "That path is not a file." };
  }
  if (stat.size > VIZZY_PROJECT_MAX_BYTES) {
    return { ok: false, code: "PROJECT_TOO_LARGE", message: "That project file is too large." };
  }
  let text: string;
  try {
    text = fs.readFileSync(resolved, "utf8");
  } catch (error) {
    return {
      ok: false,
      code: "PROJECT_READ_FAILED",
      message: error instanceof Error ? error.message : "Could not read the project file.",
    };
  }
  return parseProjectText(text);
}

/** Validate the editor's snapshot JSON (shared by save, open and tests). */
export function parseProjectText(text: string): VizzyProjectRead {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return { ok: false, code: "PROJECT_INVALID_JSON", message: "That file is not valid JSON." };
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { ok: false, code: "PROJECT_INVALID", message: "That file is not a Vizzy project." };
  }
  const snapshot = value as Record<string, unknown>;
  if (snapshot.format !== VIZZY_PROJECT_FORMAT) {
    return {
      ok: false,
      code: "PROJECT_INVALID_FORMAT",
      message: "That JSON file is not a Camxora Vizzy project.",
    };
  }
  if (!snapshot.project || typeof snapshot.project !== "object" || Array.isArray(snapshot.project)) {
    return { ok: false, code: "PROJECT_INVALID", message: "The project header is missing." };
  }
  if (!Array.isArray(snapshot.nodes) || !Array.isArray(snapshot.layers)) {
    return { ok: false, code: "PROJECT_INVALID", message: "The project has no nodes or layers." };
  }
  return { ok: true, text, snapshot };
}

function canonicalise(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalise);
  if (value && typeof value === "object") {
    const source = value as Record<string, unknown>;
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(source).sort()) sorted[key] = canonicalise(source[key]);
    return sorted;
  }
  return value;
}

/**
 * Semantic key for round-trip checks: parsed, key-sorted, `savedAt` dropped.
 * A save/open/save cycle must produce the same key.
 */
export function projectSemanticKey(json: string | Record<string, unknown>): string {
  const parsed = typeof json === "string" ? (JSON.parse(json) as unknown) : json;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return "null";
  const rest = { ...(parsed as Record<string, unknown>) };
  // `savedAt` is the only field a save cycle is allowed to change.
  delete rest.savedAt;
  return JSON.stringify(canonicalise(rest));
}

export function projectsAreEquivalent(a: string | Record<string, unknown>, b: string | Record<string, unknown>): boolean {
  return projectSemanticKey(a) === projectSemanticKey(b);
}

/** Pretty JSON with a trailing newline: a stable, diffable project file. */
export function serialiseProjectFile(snapshot: Record<string, unknown>): string {
  return `${JSON.stringify(snapshot, null, 2)}\n`;
}
