/**
 * Guards the vendored Vizzy editor against silent drift from the decompiled
 * reference source.
 *
 * The port is intentionally 1:1 except for four shell patches. Any other
 * difference means an effect/analyzer/particle/shader file changed by accident.
 *
 * Usage:
 *   npm run vizzy:parity
 *   REA_EDITOR_SRC="D:/rea/editor/src" npm run vizzy:parity
 */
import fs from "node:fs";
import path from "node:path";

const currentRoot = path.join(process.cwd(), "vizzy", "src");
const referenceRoot =
  process.env.REA_EDITOR_SRC ?? path.resolve("G:/Developments/Rea/editor/src");

/** Files the Camxora host necessarily patches; none touch effect rendering. */
const PATCHED = new Set([
  "main.ts",
  "renderer/renderer.ts",
  "ui/inspector.ts",
  "ui/timeline.ts",
]);

/** Camxora-only host shims; they are not part of the decompiled editor. */
const EXTRAS = new Set(["host/boot.ts", "host/bridge.ts", "host/host-adapter.ts"]);

function walk(root, prefix = "") {
  const out = [];
  for (const entry of fs.readdirSync(path.join(root, prefix), { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) out.push(...walk(root, rel));
    else if (entry.isFile() && entry.name.endsWith(".ts")) out.push(rel);
  }
  return out;
}

function normalised(file) {
  return fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
}

if (!fs.existsSync(referenceRoot)) {
  console.log(`[vizzy-parity] reference source not found: ${referenceRoot}`);
  console.log("[vizzy-parity] set REA_EDITOR_SRC to the decompiled editor src/");
  process.exit(0);
}
if (!fs.existsSync(currentRoot)) {
  console.error(`[vizzy-parity] vendored editor missing: ${currentRoot}`);
  process.exit(1);
}

const current = new Set(walk(currentRoot));
const reference = new Set(walk(referenceRoot));
const drift = [];
const patched = [];
const missing = [];

for (const rel of [...reference].sort()) {
  if (!current.has(rel)) {
    missing.push(rel);
    continue;
  }
  const same = normalised(path.join(referenceRoot, rel)) === normalised(path.join(currentRoot, rel));
  if (!same) {
    if (PATCHED.has(rel)) patched.push(rel);
    else drift.push(rel);
  }
}

for (const rel of current) {
  if (!reference.has(rel) && !EXTRAS.has(rel)) drift.push(`extra:${rel}`);
}

console.log(`[vizzy-parity] reference: ${referenceRoot}`);
console.log(`[vizzy-parity] files: ${reference.size} reference / ${current.size} vendored`);
console.log(`[vizzy-parity] intentional patches: ${patched.join(", ") || "none"}`);
if (missing.length > 0) console.log(`[vizzy-parity] missing: ${missing.join(", ")}`);

if (drift.length > 0 || missing.length > 0) {
  console.error(`[vizzy-parity] DRIFT: ${[...missing, ...drift].join(", ")}`);
  process.exit(1);
}
console.log("[vizzy-parity] effects/analyzers/renderers match the decompile 1:1");
