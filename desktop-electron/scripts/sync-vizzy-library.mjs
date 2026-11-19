#!/usr/bin/env node
/**
 * Stages the 91 Vizzy templates for the desktop app.
 *
 * Usage:
 *   node scripts/sync-vizzy-library.mjs [--source <editor-root>] [--out <dir>] [--check]
 *
 * Copies `public/creations/templates/*.json`, `assets/templates/<slug>/…` and
 * `thumbs/<slug>.jpg` from the Rea editor into `desktop-electron/vizzy-library/`
 * and writes a manifest the app reads at runtime.
 *
 * `vizzy-library/` is git-ignored: it is ~250 MB of template media. CI and fresh
 * checkouts must run this script (or use a release pack) before building a
 * package that ships the library.
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

function buildManifest() {
  const entries = [];
  for (const file of fs.readdirSync(sourceTemplates).filter((f) => f.endsWith(".json")).sort()) {
    const slug = file.replace(/\.json$/, "");
    const raw = fs.readFileSync(path.join(sourceTemplates, file), "utf8");
    let project = {};
    try {
      project = JSON.parse(raw);
    } catch (error) {
      throw new Error(`${file} is not valid JSON: ${error.message}`);
    }
    const assetDir = path.join(sourceAssets, slug);
    entries.push({
      slug,
      name: typeof project.name === "string" && project.name.trim() ? project.name.trim() : slug,
      project: `templates/${file}`,
      thumbnail: thumbnailFor(slug),
      hasAssets: fs.existsSync(assetDir),
      jsonBytes: Buffer.byteLength(raw),
      assetBytes: directorySize(assetDir),
    });
  }
  return {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    source: "Rea editor public/creations",
    count: entries.length,
    templates: entries,
  };
}

const manifest = buildManifest();
const manifestPath = path.join(outDir, "manifest.json");

if (checkOnly) {
  if (!fs.existsSync(manifestPath)) {
    console.error(`No staged library at ${outDir}. Run without --check first.`);
    process.exit(1);
  }
  const staged = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const problems = [];
  if (staged.count !== manifest.count) problems.push(`count ${staged.count} != ${manifest.count}`);
  for (const entry of manifest.templates) {
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

fs.mkdirSync(path.join(outDir, "templates"), { recursive: true });
fs.mkdirSync(path.join(outDir, "thumbs"), { recursive: true });
fs.mkdirSync(path.join(outDir, "assets", "templates"), { recursive: true });

let copied = 0;
for (const file of fs.readdirSync(sourceTemplates).filter((f) => f.endsWith(".json"))) {
  fs.copyFileSync(path.join(sourceTemplates, file), path.join(outDir, "templates", file));
  copied += 1;
}

let assets = 0;
for (const entry of manifest.templates) {
  if (!entry.hasAssets) continue;
  const from = path.join(sourceAssets, entry.slug);
  const to = path.join(outDir, "assets", "templates", entry.slug);
  fs.rmSync(to, { recursive: true, force: true });
  fs.cpSync(from, to, { recursive: true });
  assets += 1;
}

let thumbs = 0;
for (const entry of manifest.templates) {
  if (!entry.thumbnail) continue;
  const name = path.basename(entry.thumbnail);
  fs.copyFileSync(path.join(sourceThumbs, name), path.join(outDir, "thumbs", name));
  thumbs += 1;
}

fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

const totalBytes = manifest.templates.reduce((sum, entry) => sum + entry.jsonBytes + entry.assetBytes, 0);
console.log(
  `staged ${manifest.count} templates, ${assets} asset folders, ${thumbs} thumbnails (${(totalBytes / 1048576).toFixed(1)} MB) at ${outDir}`,
);
if (copied !== manifest.count) {
  console.error(`FAIL: copied ${copied} project files for ${manifest.count} manifest rows`);
  process.exit(1);
}
