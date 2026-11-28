import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import {
  atomicWriteText,
  parseProjectText,
  serialiseProjectFile,
  slugifyProjectName,
} from "../vizzy-host/project-store";
import {
  buildPipelineTemplate,
  validatePipelineTemplate,
  type PipelineBindings,
  type PipelineKind,
  type PipelineTemplate,
} from "./pipeline-templates";

export interface VideoTemplateSummary {
  id: string;
  name: string;
  kind: PipelineKind;
  dir: string;
  output: PipelineTemplate["output"];
  createdAt: string;
  thumbnailPath: string | null;
}

export interface VideoTemplateDetail extends VideoTemplateSummary {
  projectJson: string;
  pipeline: PipelineTemplate;
}

const PIPELINE_FILE = "pipeline.json";
const PROJECT_FILE = "template.json";
const THUMBNAIL_FILE = "thumbnail.png";
/**
 * Thumbnails that can sit next to a template. Marketplace bundles ship a
 * `preview.png`, saved templates use `thumbnail.png`, so the picker accepts
 * every name the archive reader accepts.
 */
const THUMBNAIL_FILES = [
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
];
const MAX_THUMBNAIL_BYTES = 8 * 1024 * 1024;
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function ensureRoot(root: string): string {
  const resolved = path.resolve(root);
  fs.mkdirSync(resolved, { recursive: true });
  return resolved;
}

function inside(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

function uniqueId(root: string, name: string): string {
  const base = slugifyProjectName(name) || "template";
  let candidate = base;
  let suffix = 2;
  while (fs.existsSync(path.join(root, candidate))) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}

function summaryOf(root: string, id: string, pipeline: PipelineTemplate): VideoTemplateSummary {
  const dir = path.join(root, id);
  const thumbnailPath = THUMBNAIL_FILES.map((name) => path.join(dir, name)).find((candidate) =>
    fs.existsSync(candidate),
  );
  return {
    id,
    name: pipeline.name,
    kind: pipeline.kind,
    dir,
    output: pipeline.output,
    createdAt: pipeline.createdAt,
    thumbnailPath: thumbnailPath ?? null,
  };
}

/**
 * Materialise `pipeline.json` next to an existing `template.json`.
 *
 * A marketplace install already wrote a valid project into the templates
 * folder; the Studio picker and auto-video only list folders that also carry a
 * pipeline, so installing an item writes the same pipeline "Save as video
 * template" would have produced.
 *
 * Returns null when the body is not a Camxora studio project (for example a
 * legacy Vizzy export). Those items still install and stay usable from the
 * marketplace; they just do not appear in the Studio picker.
 */
export function writeTemplatePipeline(
  dir: string,
  name: string,
  options: { projectFile?: string; createdAt?: string } = {},
): PipelineTemplate | null {
  let text: string;
  try {
    text = fs.readFileSync(path.join(dir, options.projectFile ?? PROJECT_FILE), "utf8");
  } catch {
    return null;
  }
  const read = parseProjectText(text);
  if (!read.ok) return null;
  const pipeline = buildPipelineTemplate({
    name,
    snapshot: read.snapshot,
    createdAt: options.createdAt,
  });
  atomicWriteText(path.join(dir, PIPELINE_FILE), JSON.stringify(pipeline, null, 2) + "\n");
  return pipeline;
}

/** Validate a directory contains a complete, loadable template. */export function readVideoTemplate(root: string, id: string): VideoTemplateDetail {
  const resolvedRoot = path.resolve(root);
  if (!id || id.includes("/") || id.includes("\\") || id === "." || id === "..") {
    throw new Error("That template id is not valid.");
  }
  const dir = path.join(resolvedRoot, id);
  if (!inside(resolvedRoot, dir) || !fs.existsSync(dir)) {
    throw new Error("That video template does not exist.");
  }
  const pipelinePath = path.join(dir, PIPELINE_FILE);
  const projectPath = path.join(dir, PROJECT_FILE);
  if (!fs.existsSync(pipelinePath) || !fs.existsSync(projectPath)) {
    throw new Error("That video template is incomplete.");
  }
  const pipeline = validatePipelineTemplate(JSON.parse(fs.readFileSync(pipelinePath, "utf8")));
  const read = parseProjectText(fs.readFileSync(projectPath, "utf8"));
  if (!read.ok) throw new Error(read.message);
  return {
    ...summaryOf(resolvedRoot, id, pipeline),
    projectJson: read.text,
    pipeline,
  };
}

export function saveVideoTemplate(input: {
  root: string;
  name: string;
  /** The exact editor snapshot the user previewed. */
  snapshotJson: string;
  thumbnail?: Uint8Array | null;
  bindings?: PipelineBindings;
  kind?: PipelineKind;
  /** Export-dialog choices captured with the template. */
  exportSettings?: import("./pipeline-templates").PipelineExportSettings;
  /** Existing template id to replace when overwriting. */
  overwrite?: boolean;
  /** Test hook; normal saves get a unique slug id. */
  id?: string;
  createdAt?: string;
}): VideoTemplateSummary {
  const read = parseProjectText(input.snapshotJson);
  if (!read.ok) throw new Error(read.message);

  const root = ensureRoot(input.root);
  let existingCreatedAt: string | undefined;
  if (input.id && fs.existsSync(path.join(root, input.id, PIPELINE_FILE))) {
    try {
      const existing = validatePipelineTemplate(
        JSON.parse(fs.readFileSync(path.join(root, input.id, PIPELINE_FILE), "utf8")),
      );
      existingCreatedAt = existing.createdAt;
    } catch {
      // A broken existing template is replaced instead of blocking the save.
    }
  }
  const pipeline = buildPipelineTemplate({
    name: input.name,
    snapshot: read.snapshot,
    bindings: input.bindings,
    kind: input.kind,
    exportSettings: input.exportSettings,
    createdAt: input.createdAt ?? existingCreatedAt,
  });

  let thumbnail: Buffer | null = null;
  if (input.thumbnail && input.thumbnail.byteLength > 0) {
    thumbnail = Buffer.from(input.thumbnail);
    if (thumbnail.byteLength > MAX_THUMBNAIL_BYTES) throw new Error("The thumbnail is too large.");
    if (!thumbnail.subarray(0, 8).equals(PNG_SIGNATURE)) {
      throw new Error("The thumbnail must be a PNG image.");
    }
  }

  const id = input.id ?? uniqueId(root, pipeline.name);
  if (input.id && (!id || id.includes("/") || id.includes("\\") || id === "." || id === "..")) {
    throw new Error("That template id is not valid.");
  }
  const finalDir = path.join(root, id);
  if (!inside(root, finalDir)) throw new Error("That template path is outside the library.");
  const replacing = fs.existsSync(finalDir);
  if (replacing && input.overwrite !== true) {
    throw new Error("A video template with that id already exists.");
  }

  const tempDir = path.join(root, `.tmp-${crypto.randomUUID()}`);
  fs.mkdirSync(tempDir, { recursive: true });
  try {
    atomicWriteText(path.join(tempDir, PROJECT_FILE), serialiseProjectFile(read.snapshot));
    atomicWriteText(path.join(tempDir, PIPELINE_FILE), JSON.stringify(pipeline, null, 2) + "\n");
    if (thumbnail) fs.writeFileSync(path.join(tempDir, THUMBNAIL_FILE), thumbnail);
    if (replacing) {
      // Replace the whole folder: a fresh project, pipeline and (or no) thumbnail.
      const backup = path.join(root, `.bak-${crypto.randomUUID()}`);
      fs.renameSync(finalDir, backup);
      try {
        fs.renameSync(tempDir, finalDir);
        fs.rmSync(backup, { recursive: true, force: true });
      } catch (error) {
        fs.rmSync(finalDir, { recursive: true, force: true });
        if (fs.existsSync(backup)) fs.renameSync(backup, finalDir);
        throw error;
      }
    } else {
      fs.renameSync(tempDir, finalDir);
    }
  } catch (error) {
    fs.rmSync(tempDir, { recursive: true, force: true });
    throw error;
  }

  return summaryOf(root, id, pipeline);
}

export function listVideoTemplates(root: string): VideoTemplateSummary[] {
  const resolvedRoot = path.resolve(root);
  if (!fs.existsSync(resolvedRoot)) return [];
  const summaries: VideoTemplateSummary[] = [];
  for (const entry of fs.readdirSync(resolvedRoot, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
    try {
      const pipeline = validatePipelineTemplate(
        JSON.parse(fs.readFileSync(path.join(resolvedRoot, entry.name, PIPELINE_FILE), "utf8")),
      );
      if (!fs.existsSync(path.join(resolvedRoot, entry.name, PROJECT_FILE))) continue;
      summaries.push(summaryOf(resolvedRoot, entry.name, pipeline));
    } catch {
      // Ignore a directory that is not a valid template; never let one bad row
      // hide the rest of the library.
    }
  }
  return summaries.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function deleteVideoTemplate(root: string, id: string): boolean {
  const resolvedRoot = path.resolve(root);
  if (!id || id.includes("/") || id.includes("\\") || id === "." || id === "..") return false;
  const dir = path.join(resolvedRoot, id);
  if (!inside(resolvedRoot, dir) || !fs.existsSync(dir)) return false;
  fs.rmSync(dir, { recursive: true, force: true });
  return true;
}
