#!/usr/bin/env node
/**
 * Stages the 91 Vizzy templates for the desktop app.
 *
 * Usage:
 *   node scripts/sync-vizzy-library.mjs [--source <editor-root>] [--out <dir>] [--check]
 *
 * Copies `public/creations/{templates,assets/templates,thumbs}` from the Rea editor
 * into `desktop-electron/vizzy-library/creations/` and writes:
 *
 *   vizzy-library/
 *     manifest.json                 Camxora metadata (slug, name, sizes, audio provenance)
 *     creations/manifest.json       Rea's creation browser manifest (`{ creations: [...] }`)
 *     creations/templates/*.json    project JSON with the licensed track stripped
 *     creations/assets/templates/** local template media
 *     creations/thumbs/**           thumbnails
 *
 * The staged project JSON keeps its original `/creations/...` asset paths, so the
 * `camxora-vizzy://` handler can serve the library under `/creations/` and the
 * editor's built-in Creations browser lists all 91 with no custom UI.
 *
 * `vizzy-library/` is git-ignored: it is ~260 MB of template media. CI and fresh
 * checkouts must run this script (or use a release pack) before packaging.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};
const has = (name) => args.includes(name);

const source =
  option("--source", "") ||
  process.env.CAMXORA_VIZZY_SOURCE ||
  (process.platform === "win32" ? "G:/Developments/Rea/editor" : "");
const outDir = path.resolve(option("--out", path.join(appRoot, "vizzy-library")));
const checkOnly = has("--check");

if (!source) {
  console.error("Provide --source <editor-root> or set CAMXORA_VIZZY_SOURCE.");
  process.exit(2);
}

const sourceTemplates = path.join(source, "public", "creations", "templates");
const sourceAssets = path.join(source, "public", "creations", "assets", "templates");
const sourceThumbs = path.join(source, "public", "creations", "thumbs");

if (!fs.existsSync(sourceTemplates)) {
  console.error(`No templates at ${sourceTemplates}`);
  process.exit(2);
}

function directorySize(directory) {
  if (!fs.existsSync(directory)) return 0;
  let total = 0;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    total += entry.isDirectory() ? directorySize(full) : fs.statSync(full).size;
  }
  return total;
}

function thumbnailFor(slug) {
  for (const ext of [".jpg", ".jpeg", ".png", ".webp"]) {
    const candidate = path.join(sourceThumbs, `${slug}${ext}`);
    if (fs.existsSync(candidate)) return `thumbs/${slug}${ext}`;
  }
  return null;
}

/** Remove the licensed reference track; the pipeline binds the run audio. */
function stripAudio(project) {
  const audioName = typeof project.audioName === "string" ? project.audioName : "";
  if (project.values && typeof project.values === "object" && project.values.Audio) {
    const audio = project.values.Audio;
    if (audio && typeof audio === "object") {
      audio.src = "";
    }
  }
  if ("audioName" in project) project.audioName = "";
  return audioName;
}

function buildLibrary() {
  const entries = [];
  const creations = [];
  for (const file of fs.readdirSync(sourceTemplates).filter((f) => f.endsWith(".json")).sort()) {
    const slug = file.replace(/\.json$/, "");
    const raw = fs.readFileSync(path.join(sourceTemplates, file), "utf8");
    let project;
    try {
      project = JSON.parse(raw);
    } catch (error) {
      throw new Error(`${file} is not valid JSON: ${error.message}`);
    }
    const audioName = stripAudio(project);
    const body = JSON.stringify(project, null, 2) + "\n";
    const assetDir = path.join(sourceAssets, slug);
    const thumbnail = thumbnailFor(slug);
    const name =
      typeof project.name === "string" && project.name.trim() ? project.name.trim() : slug;

    entries.push({
      slug,
      name,
      project: `creations/templates/${file}`,
      thumbnail: thumbnail ? `creations/${thumbnail}` : null,
      hasAssets: fs.existsSync(assetDir),
      jsonBytes: Buffer.byteLength(body),
      assetBytes: directorySize(assetDir),
      audioReference: audioName || null,
    });

    creations.push({
      id: slug,
      name,
      description: "Vizzy template",
      file: `/creations/templates/${file}`,
      thumbnail: thumbnail ? `/creations/${thumbnail}` : undefined,
    });
  }

  return {
    manifest: {
      schemaVersion: 1,
      generatedAt: new Date().toISOString(),
      source: "Rea editor public/creations",
      count: entries.length,
      templates: entries,
    },
    creations: { creations },
  };
}

const library = buildLibrary();
const manifestPath = path.join(outDir, "manifest.json");
const creationsManifestPath = path.join(outDir, "creations", "manifest.json");

if (checkOnly) {
  if (!fs.existsSync(manifestPath) || !fs.existsSync(creationsManifestPath)) {
    console.error(`No staged library at ${outDir}. Run without --check first.`);
    process.exit(1);
  }
  const staged = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const problems = [];
  if (staged.count !== library.manifest.count) {
    problems.push(`count ${staged.count} != ${library.manifest.count}`);
  }
  for (const entry of library.manifest.templates) {
    if (!fs.existsSync(path.join(outDir, entry.project))) problems.push(`missing ${entry.project}`);
    if (entry.thumbnail && !fs.existsSync(path.join(outDir, entry.thumbnail))) {
      problems.push(`missing ${entry.thumbnail}`);
    }
  }
  if (problems.length) {
    console.error(`FAIL: ${problems.slice(0, 8).join("; ")}${problems.length > 8 ? " …" : ""}`);
    process.exit(1);
  }
  console.log(`OK: ${staged.count} templates staged at ${outDir}`);
  process.exit(0);
}

fs.mkdirSync(path.join(outDir, "creations", "templates"), { recursive: true });
fs.mkdirSync(path.join(outDir, "creations", "thumbs"), { recursive: true });
fs.mkdirSync(path.join(outDir, "creations", "assets", "templates"), { recursive: true });

let assets = 0;
for (const entry of library.manifest.templates) {
  const project = JSON.parse(
    fs.readFileSync(path.join(source, "public", entry.project), "utf8"),
  );
  stripAudio(project);
  fs.writeFileSync(path.join(outDir, entry.project), JSON.stringify(project, null, 2) + "\n");
  if (!entry.hasAssets) continue;
  const from = path.join(sourceAssets, entry.slug);
  const to = path.join(outDir, "creations", "assets", "templates", entry.slug);
  fs.rmSync(to, { recursive: true, force: true });
  fs.cpSync(from, to, { recursive: true });
  assets += 1;
}

let thumbs = 0;
for (const entry of library.manifest.templates) {
  if (!entry.thumbnail) continue;
  fs.copyFileSync(
    path.join(source, "public", entry.thumbnail),
    path.join(outDir, entry.thumbnail),
  );
  thumbs += 1;
}

fs.writeFileSync(manifestPath, JSON.stringify(library.manifest, null, 2) + "\n");
fs.writeFileSync(creationsManifestPath, JSON.stringify(library.creations, null, 2) + "\n");

const totalBytes = library.manifest.templates.reduce(
  (sum, entry) => sum + entry.jsonBytes + entry.assetBytes,
  0,
);
console.log(
  `staged ${library.manifest.count} templates, ${assets} asset folders, ${thumbs} thumbnails (${(totalBytes / 1048576).toFixed(1)} MB) at ${outDir}`,
);
