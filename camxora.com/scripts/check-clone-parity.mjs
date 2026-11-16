#!/usr/bin/env node
/**
 * Clone parity gate (docs/studio/CLONE_DEFINITION.md).
 *
 * Fails when a reference screen has no evidence, the reference metrics and the runtime
 * probe drift apart, a functional captured string disappears, or a pairing points at a
 * file that does not exist. Run with: npm run check:clone
 */

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..");
const REPO = resolve(APP, "..");
const DOCS = join(REPO, "docs", "studio");
const REFERENCE = join(DOCS, "reference");
const COMPARE = join(DOCS, "compare");
const E2E = join(APP, "tests", "e2e");

const problems = [];
const notes = [];

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function mustExist(path, label) {
  if (!existsSync(path)) {
    problems.push(`${label} does not exist: ${relative(REPO, path)}`);
    return false;
  }
  return true;
}

// ---------------------------------------------------------------- 1. coverage
const pairing = readJson(join(REFERENCE, "PAIRING.json")).screens;
const referenceScreens = [
  ...new Set(
    readdirSync(join(REFERENCE, "screens"))
      .filter((name) => name.endsWith(".jpeg"))
      .map((name) => {
        const base = name.replace(/\.jpeg$/, "");
        // S-ids are the first segment; captures without an S-number keep their full name.
        return /^S\d+$/.test(base.split("-")[0]) ? base.split("-")[0] : base;
      })
  ),
];

for (const id of referenceScreens) {
  if (!pairing[id]) problems.push(`reference screen ${id} has no PAIRING.json entry`);
}

let captured = 0;
let speced = 0;
let negative = 0;
for (const [id, entry] of Object.entries(pairing)) {
  const hasCapture = typeof entry.capture === "string";
  const hasSpec = typeof entry.spec === "string";
  const isNegative = entry.negative === true;
  const provided = [hasCapture, hasSpec, isNegative].filter(Boolean).length;
  if (provided === 0) {
    problems.push(`${id} has no capture, spec or negative marker`);
    continue;
  }
  if (hasCapture) {
    captured += 1;
    mustExist(join(COMPARE, entry.capture), `${id} capture`);
  }
  if (hasSpec) {
    speced += 1;
    const specPath = join(E2E, entry.spec);
    const inApp = join(APP, "tests", entry.spec);
    const found = existsSync(specPath) ? specPath : existsSync(inApp) ? inApp : null;
    if (!found) {
      problems.push(`${id} spec does not exist: ${entry.spec}`);
    } else {
      // A spec that exists but is entirely skipped is not evidence. Count real
      // declarations only: `test(`/`it(` are runnable, `test.skip(`/`it.skip(` are not,
      // and in-body gates such as test.skip(condition) still leave the declaration.
      const specSource = readFileSync(found, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
      const runnable = (specSource.match(/(^|[\s;])(it|test)\(/gm) ?? []).length;
      if (runnable === 0) {
        problems.push(`${id} spec has no runnable test: ${entry.spec}`);
      }
    }
  }
  if (isNegative) {
    negative += 1;
    if (!entry.note) problems.push(`${id} is negative but has no note explaining why`);
  }
}

// ---------------------------------------------------------------- 1b. shared evidence
// One frame can evidence several surfaces that are all visible in it, but it must say
// so: every group of identical captures needs exactly one anchor (no `sharedWith`) and
// the rest must declare `sharedWith: "<anchor id>"`. Recycled evidence is then a
// declaration, never an accident.
const byDigest = new Map();
for (const [id, entry] of Object.entries(pairing)) {
  if (typeof entry.capture !== "string") continue;
  const capturePath = join(COMPARE, entry.capture);
  if (!existsSync(capturePath)) continue;
  const digest = createHash("sha256").update(readFileSync(capturePath)).digest("hex");
  byDigest.set(digest, [...(byDigest.get(digest) ?? []), id]);
}
for (const ids of byDigest.values()) {
  if (ids.length < 2) continue;
  const anchors = ids.filter((id) => !pairing[id].sharedWith);
  if (anchors.length !== 1) {
    problems.push(
      `one capture is paired with ${ids.join(", ")}; mark every screen but one sharedWith`
    );
    continue;
  }
  const [anchor] = anchors;
  for (const id of ids) {
    if (id !== anchor && pairing[id].sharedWith !== anchor) {
      problems.push(`${id} shares a capture with ${anchor} but does not declare sharedWith`);
    }
  }
}

// ---------------------------------------------------------------- 2. metrics
const metricsReference = readJson(join(REFERENCE, "METRICS.json"));
const metricsRuntime = readJson(join(APP, "public", "studio-metrics.json"));
if (JSON.stringify(metricsReference) !== JSON.stringify(metricsRuntime)) {
  problems.push("reference/METRICS.json and public/studio-metrics.json have drifted apart");
}
const pixelSpec = readFileSync(join(E2E, "studio-pixel.spec.ts"), "utf8");
const metricsSpecExists = existsSync(join(E2E, "studio-metrics.spec.ts"));
const probeSource = readFileSync(join(APP, "components", "studio", "StudioMetricsProbe.tsx"), "utf8");
// Metrics are asserted by the runtime probe (which reads the mirrored JSON) + its spec,
// not by hard-coded ids inside studio-pixel.
if (!metricsSpecExists) problems.push("tests/e2e/studio-metrics.spec.ts is missing");
if (!probeSource.includes("/studio-metrics.json")) {
  problems.push("StudioMetricsProbe no longer reads /studio-metrics.json");
}
if (!pixelSpec.includes("studio-metrics")) {
  notes.push("studio-pixel does not mount the metrics probe; studio-metrics.spec.ts owns it");
}

// ---------------------------------------------------------------- 3. strings
const functional = readJson(join(REFERENCE, "FUNCTIONAL_STRINGS.json")).strings;

/**
 * Remove comments with the TypeScript parser rather than a regex. A doc-comment above
 * the clip menu ("Download .WAV") used to satisfy the captured string while the button
 * read "Download WAV"; a regex stripper cannot be trusted because files contain glob
 * patterns and URLs that look like comment delimiters.
 */
function stripComments(text, fileName) {
  if (fileName.endsWith(".css")) return text;
  return ts.transpileModule(text, {
    fileName,
    compilerOptions: {
      target: ts.ScriptTarget.ESNext,
      module: ts.ModuleKind.ESNext,
      jsx: ts.JsxEmit.Preserve,
      removeComments: true,
    },
  }).outputText;
}

function collectSource(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const info = statSync(path);
    if (info.isDirectory()) {
      if (name === "node_modules" || name === ".next") continue;
      collectSource(path, out);
      continue;
    }
    if (/\.(tsx?|css)$/.test(name)) out.push(stripComments(readFileSync(path, "utf8"), name));
  }
  return out;
}
const source = [
  ...collectSource(join(APP, "components", "studio")),
  ...collectSource(join(APP, "components")),
  ...collectSource(join(APP, "lib")),
  ...collectSource(join(APP, "app", "studio")),
  ...collectSource(join(APP, "app", "(site)", "studio")),
].join("\n");

let missingStrings = 0;
for (const text of functional) {
  const candidates = [
    text,
    text.replace(/\u2026/g, "..."),
    text.replace(/&/g, "&amp;"),
    text.replace(/'/g, "&apos;"),
    text.replace(/'/g, "&#39;"),
    text.replace(/"/g, "&quot;"),
  ];
  if (!candidates.some((candidate) => source.includes(candidate))) {
    problems.push(`functional string missing from the UI: "${text}"`);
    missingStrings += 1;
  }
}

// ---------------------------------------------------------------- report
let evidenced = 0;
for (const entry of Object.values(pairing)) {
  if (entry.capture || entry.spec || entry.negative) evidenced += 1;
}
const total = Object.keys(pairing).length;
const pct = total ? Math.round((evidenced / total) * 100) : 0;
notes.push(
  `screens ${total}: ${evidenced} evidenced (${captured} paired captures, ${speced} spec-covered, ${negative} negative); ${pct}% covered`
);
notes.push(`metrics ${metricsReference.metrics.length} asserted at 0 tolerance`);
notes.push(`functional strings ${functional.length - missingStrings}/${functional.length} present`);

for (const note of notes) console.log(`  · ${note}`);
if (problems.length) {
  console.error(`\ncheck:clone — ${problems.length} problem(s):`);
  for (const problem of problems) console.error(`  ✗ ${problem}`);
  process.exit(1);
}
console.log("\ncheck:clone — the definition in docs/studio/CLONE_DEFINITION.md is satisfied.");
