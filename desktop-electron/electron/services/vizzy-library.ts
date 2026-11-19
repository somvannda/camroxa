import fs from "node:fs";
import path from "node:path";

export interface VizzyLibraryEntry {
  slug: string;
  name: string;
  /** Absolute path to the project JSON. */
  projectPath: string;
  /** Absolute path to the thumbnail, when the manifest has one. */
  thumbnailPath: string | null;
  hasAssets: boolean;
  jsonBytes: number;
  assetBytes: number;
}

export interface VizzyLibrary {
  root: string;
  count: number;
  templates: VizzyLibraryEntry[];
}

interface ManifestEntry {
  slug?: unknown;
  name?: unknown;
  project?: unknown;
  thumbnail?: unknown;
  hasAssets?: unknown;
  jsonBytes?: unknown;
  assetBytes?: unknown;
}

interface Manifest {
  schemaVersion?: unknown;
  count?: unknown;
  templates?: unknown;
}

const MAX_MANIFEST_BYTES = 4 * 1024 * 1024;
const MAX_PROJECT_BYTES = 64 * 1024 * 1024;

/** Dev/packaged library root: env override, resources, then the app directory. */
export function resolveLibraryRoot(): string {
  const fromEnv = process.env.CAMXORA_VIZZY_LIBRARY_DIR;
  if (fromEnv) return path.resolve(fromEnv);
  const resources = process.resourcesPath
    ? path.join(process.resourcesPath, "vizzy-library")
    : "";
  if (resources && fs.existsSync(path.join(resources, "manifest.json"))) return resources;
  return path.join(process.cwd(), "vizzy-library");
}

function inside(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

export function readLibrary(root: string): VizzyLibrary {
  const manifestPath = path.join(root, "manifest.json");
  if (!fs.existsSync(manifestPath)) {
    throw new Error(`The Vizzy template library is not staged (${manifestPath}).`);
  }
  const stats = fs.statSync(manifestPath);
  if (stats.size > MAX_MANIFEST_BYTES) {
    throw new Error("The Vizzy library manifest is unexpectedly large.");
  }
  let raw: Manifest;
  try {
    raw = JSON.parse(fs.readFileSync(manifestPath, "utf8")) as Manifest;
  } catch (error) {
    throw new Error(`The Vizzy library manifest is not valid JSON: ${String(error)}`);
  }
  if (raw.schemaVersion !== 1 || !Array.isArray(raw.templates)) {
    throw new Error("The Vizzy library manifest has an unsupported schema.");
  }

  const templates: VizzyLibraryEntry[] = [];
  for (const item of raw.templates as ManifestEntry[]) {
    if (typeof item.slug !== "string" || !item.slug.trim()) continue;
    if (typeof item.project !== "string" || !item.project.trim()) continue;
    const projectPath = path.resolve(root, item.project);
    if (!inside(root, projectPath) || !fs.existsSync(projectPath)) {
      throw new Error(`Library template "${item.slug}" is missing its project file.`);
    }
    const thumbnailPath =
      typeof item.thumbnail === "string" && item.thumbnail.trim()
        ? path.resolve(root, item.thumbnail)
        : null;
    templates.push({
      slug: item.slug,
      name: typeof item.name === "string" && item.name.trim() ? item.name : item.slug,
      projectPath,
      thumbnailPath:
        thumbnailPath && inside(root, thumbnailPath) && fs.existsSync(thumbnailPath)
          ? thumbnailPath
          : null,
      hasAssets: item.hasAssets === true,
      jsonBytes: Number(item.jsonBytes) || 0,
      assetBytes: Number(item.assetBytes) || 0,
    });
  }

  if (typeof raw.count === "number" && raw.count !== templates.length) {
    throw new Error(`The Vizzy library manifest lists ${raw.count} templates but has ${templates.length}.`);
  }

  return { root, count: templates.length, templates };
}

export function findLibraryTemplate(root: string, slug: string): VizzyLibraryEntry | null {
  return readLibrary(root).templates.find((entry) => entry.slug === slug) ?? null;
}

/** Reads a library project by manifest slug; never accepts an arbitrary path. */
export function readLibraryProject(root: string, slug: string): { entry: VizzyLibraryEntry; json: string } {
  const entry = findLibraryTemplate(root, slug);
  if (!entry) throw new Error(`Unknown Vizzy template "${slug}".`);
  const stats = fs.statSync(entry.projectPath);
  if (stats.size > MAX_PROJECT_BYTES) {
    throw new Error("That Vizzy template is too large to open.");
  }
  return { entry, json: fs.readFileSync(entry.projectPath, "utf8") };
}
