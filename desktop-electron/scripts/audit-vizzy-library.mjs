#!/usr/bin/env node
/**
 * Audits the Vizzy template library for offline readiness.
 *
 * Usage:
 *   node scripts/audit-vizzy-library.mjs [--source <editor-root>] [--out <csv>] [--allow-remote]
 *
 * The source is the Rea editor root (the folder that contains `public/creations`).
 * Defaults to CAMXORA_VIZZY_SOURCE, then G:/Developments/Rea/editor on Windows.
 *
 * Fails when a project references a missing local file, unless --allow-missing is passed.
 * Fails when a project still needs a remote font/image, unless --allow-remote is passed.
 */
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const source =
  option("--source", "") ||
  process.env.CAMXORA_VIZZY_SOURCE ||
  (process.platform === "win32" ? "G:/Developments/Rea/editor" : "");
const outFile = option("--out", "");
const allowRemote = flag("--allow-remote");
const allowMissing = flag("--allow-missing");

if (!source) {
  console.error("Provide --source <editor-root> or set CAMXORA_VIZZY_SOURCE.");
  process.exit(2);
}

const templatesDir = path.join(source, "public", "creations", "templates");
const assetsDir = path.join(source, "public", "creations", "assets", "templates");
const thumbsDir = path.join(source, "public", "creations", "thumbs");
const publicDir = path.join(source, "public");

if (!fs.existsSync(templatesDir)) {
  console.error(`No templates at ${templatesDir}`);
  process.exit(2);
}

const thumbnails = fs.existsSync(thumbsDir)
  ? new Set(
      fs
        .readdirSync(thumbsDir)
        .filter((file) => /\.(png|jpe?g|webp)$/i.test(file))
        .map((file) => file.replace(/\.[^.]+$/, "").toLowerCase()),
    )
  : new Set();

function directorySize(directory) {
  if (!fs.existsSync(directory)) return 0;
  let total = 0;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    total += entry.isDirectory() ? directorySize(full) : fs.statSync(full).size;
  }
  return total;
}

const rows = [];
for (const file of fs.readdirSync(templatesDir).filter((name) => name.endsWith(".json")).sort()) {
  const slug = file.replace(/\.json$/, "");
  const raw = fs.readFileSync(path.join(templatesDir, file), "utf8");
  const project = JSON.parse(raw);
  const refs = {
    local: new Set(),
    missing: new Set(),
    audio: new Set(),
    font: new Set(),
    image: new Set(),
    other: new Set(),
  };

  const walk = (value) => {
    if (typeof value === "string") {
      if (value.startsWith("/creations/")) {
        const local = path.join(publicDir, value.replace(/^\//, ""));
        (fs.existsSync(local) ? refs.local : refs.missing).add(value);
      } else if (/^https?:\/\//i.test(value)) {
        if (value === project.audioName || /audios%2F|\/audios\//i.test(value)) {
          refs.audio.add(value);
        } else if (/fonts%2F|\/fonts\//i.test(value) || /fonts\.gstatic\.com/i.test(value)) {
          refs.font.add(value);
        } else if (
          /images%2F|\/images\//i.test(value) ||
          /\.(png|jpe?g|webp|gif|avif)(\?|$)/i.test(value)
        ) {
          refs.image.add(value);
        } else {
          refs.other.add(value);
        }
      }
    } else if (value && typeof value === "object") {
      for (const key of Object.keys(value)) walk(value[key]);
    }
  };
  walk(project);

  rows.push({
    slug,
    json_kb: (Buffer.byteLength(raw) / 1024).toFixed(1),
    assets_mb: (directorySize(path.join(assetsDir, slug)) / 1048576).toFixed(1),
    asset_folder: fs.existsSync(path.join(assetsDir, slug)) ? "yes" : "no",
    local_refs: refs.local.size,
    missing_local: refs.missing.size,
    remote_audio: refs.audio.size,
    remote_font: refs.font.size,
    remote_image: refs.image.size,
    remote_other: refs.other.size,
    thumbnail: thumbnails.has(slug.toLowerCase()) ? "yes" : "no",
  });
}

const header = Object.keys(rows[0] ?? { slug: "" });
const quote = (value) => {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
const csv = [header.join(",")]
  .concat(rows.map((row) => header.map((key) => quote(row[key])).join(",")))
  .join("\n")
  .concat("\n");

if (outFile) {
  fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
  fs.writeFileSync(outFile, csv);
}

const total = (key) => rows.reduce((sum, row) => sum + Number(row[key]), 0);
const count = (key) => rows.filter((row) => Number(row[key]) > 0).length;
const missingThumbs = rows.filter((row) => row.thumbnail !== "yes").map((row) => row.slug);
const missingLocal = rows.filter((row) => Number(row.missing_local) > 0).map((row) => row.slug);
const remoteFonts = rows.filter((row) => Number(row.remote_font) > 0).map((row) => row.slug);
const remoteImages = rows.filter((row) => Number(row.remote_image) > 0).map((row) => row.slug);

console.log(`source: ${source}`);
console.log(`templates: ${rows.length}`);
console.log(`json: ${(total("json_kb") / 1024).toFixed(1)} MB`);
console.log(`assets: ${total("assets_mb").toFixed(1)} MB`);
console.log(`missing thumbnails: ${missingThumbs.length}${missingThumbs.length ? ` (${missingThumbs.join(", ")})` : ""}`);
console.log(`templates with missing local files: ${missingLocal.length}${missingLocal.length ? ` (${missingLocal.join(", ")})` : ""}`);
console.log(`remote audio: ${count("remote_audio")} templates / ${total("remote_audio")} urls (expected)`);
console.log(`remote fonts: ${count("remote_font")} templates / ${total("remote_font")} urls`);
console.log(`remote images: ${count("remote_image")} templates / ${total("remote_image")} urls`);
if (outFile) console.log(`wrote ${outFile}`);

const failures = [];
if (missingLocal.length && !allowMissing) failures.push("missing local files");
if ((remoteFonts.length || remoteImages.length) && !allowRemote) failures.push("remote fonts/images");
if (missingThumbs.length) failures.push("missing thumbnails");

if (failures.length) {
  console.error(`FAIL: ${failures.join(", ")}`);
  process.exit(1);
}
console.log(
  allowRemote && (remoteFonts.length || remoteImages.length)
    ? "OK: no local or thumbnail gaps (remote references allowed)."
    : "OK: the library renders offline.",
);
