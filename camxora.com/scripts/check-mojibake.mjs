#!/usr/bin/env node
/**
 * Mojibake gate: fails if UTF-8 text was ever decoded as CP1252 and re-saved.
 *
 * The tell-tale signatures are the byte sequences that survive such a round
 * trip: "â€¦" for an ellipsis, "â€”" for an em dash, "Â·" for a middle dot and
 * "Ã©" for an accented letter. U+FFFD (a replacement character written to disk)
 * is reported too, because that text can no longer be recovered automatically.
 *
 * Usage:
 *   node scripts/check-mojibake.mjs                # app, components, lib and tests
 *   node scripts/check-mojibake.mjs components     # one directory
 *   node scripts/check-mojibake.mjs app/globals.css tests/e2e/studio-pixel.spec.ts
 *
 * This file is skipped, because its own documentation has to quote the
 * signatures it looks for. Exits 1 when anything is found.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = process.cwd();
const SELF = "scripts/check-mojibake.mjs";
const DEFAULT_TARGETS = ["app", "components", "lib", "tests"];
const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "build", "out", "public", ".git"]);
const EXTENSIONS = /\.(tsx|ts|jsx|js|mjs|cjs|css|scss|md|json)$/;

// Longest first, so "â€¦" is reported before its "â€" prefix.
const SIGNATURES = ["â€œ", "â€\u009d", "â€”", "â€“", "â€¦", "â€™", "â€", "Â·", "Â°", "Ã", "Â", "\uFFFD"];
const LABELS = {
  "â€œ": "curly open quote", "â€\u009d": "curly close quote", "â€”": "em dash",
  "â€“": "en dash", "â€¦": "ellipsis", "â€™": "apostrophe", "â€": "broken UTF-8 punctuation",
  "Â·": "middle dot", "Â°": "degree sign", "Ã": "broken UTF-8 letter",
  "Â": "broken UTF-8 (Â)", "\uFFFD": "U+FFFD replacement character",
};

const collect = (target) => {
  const stat = statSync(target);
  if (!stat.isDirectory()) return [target];
  return readdirSync(target, { withFileTypes: true }).flatMap((entry) => {
    if (SKIP_DIRS.has(entry.name)) return [];
    const path = join(target, entry.name);
    return collect(path);
  });
};

const targets = process.argv.slice(2);
const files = (targets.length ? targets : DEFAULT_TARGETS)
  .flatMap((target) => (statSync(target).isDirectory() ? collect(target) : [target]))
  .filter((file) => EXTENSIONS.test(file) && relative(ROOT, file) !== SELF);

let findings = 0;
for (const file of files) {
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, index) => {
    const hits = SIGNATURES.filter((signature) => line.includes(signature));
    if (!hits.length) return;
    findings += hits.length;
    const label = [...new Set(hits.map((hit) => LABELS[hit]))].join(", ");
    console.log(`${relative(ROOT, file)}:${index + 1}: ${label}`);
    console.log(`  ${line.trim().slice(0, 160)}`);
  });
}

if (findings) {
  console.error(`\n${findings} mojibake signature(s) in ${files.length} file(s).`);
  process.exit(1);
}
console.log(`clean: no mojibake signatures in ${files.length} file(s).`);
