#!/usr/bin/env node
/**
 * Mine user-facing strings from the shipped client chunks: control labels, menu
 * items, dialog copy, error messages, keyboard hints.
 *
 * Emits derived text only (the labels themselves), never source structure.
 *
 *   node tools/suno-re/extract-ui-strings.mjs --chunks %TEMP%/suno-re/chunks-authed
 */
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const REPO = process.cwd();
const OUT_DIR = join(REPO, "docs", "studio", "reference");

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const chunkDir = arg("chunks", join(process.env.TEMP || "/tmp", "suno-re", "chunks-authed"));

const NOISE = [
  /^https?:/i, /^\/_next\//, /^[a-z0-9_\-]+\.[a-z]{2,5}$/i, /^\d+(\.\d+)?(px|rem|em|ms|s|%)?$/,
  /^[A-Z0-9_]+$/, /^[a-z]+([A-Z][a-z]+)+$/, /\b(fn|jsx|tsx|undefined|null)\b/i,
  /^[#.][\w-]+$/, /^Mozilla\//i, /^data:/i, /^application\//i, /^image\//i, /^audio\//i,
  /^\W+$/, /\\u[0-9a-f]{4}/i,
];

function looksLikeUiText(value) {
  const text = value.trim();
  if (text.length < 3 || text.length > 90) return false;
  if (!/[a-zA-Z]{2}/.test(text)) return false;
  if (NOISE.some((pattern) => pattern.test(text))) return false;
  if (/[{}$<>`]/.test(text)) return false;
  if (/^[a-z]+[-_][a-z-]+$/i.test(text)) return false; // css tokens / ids
  const spaces = (text.match(/\s/g) || []).length;
  const letters = (text.match(/[a-zA-Z]/g) || []).length;
  // Require either a space or an obvious label shape (Title Case / ending punctuation).
  return spaces > 0 || /^[A-Z][a-z]+$/.test(text) || /[.!?:]$/.test(text);
}

function main() {
  const files = readdirSync(chunkDir).filter((name) => name.endsWith(".js"));
  const byChunk = new Map();
  const all = new Map();

  for (const file of files) {
    let src;
    try {
      src = readFileSync(join(chunkDir, file), "utf8");
    } catch {
      continue;
    }
    const found = new Set();
    for (const match of src.matchAll(/(["'`])((?:(?!\1).){3,120}?)\1/g)) {
      const value = match[2];
      if (!looksLikeUiText(value)) continue;
      found.add(value.trim());
    }
    if (found.size) byChunk.set(file, [...found].sort());
    for (const value of found) all.set(value, (all.get(value) || 0) + 1);
  }

  const studioChunks = [...byChunk.keys()].filter((file) => {
    try {
      return readFileSync(join(chunkDir, file), "utf8").includes("/api/studio");
    } catch {
      return false;
    }
  });

  const studioStrings = new Set();
  for (const file of studioChunks) for (const value of byChunk.get(file) || []) studioStrings.add(value);

  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(
    join(OUT_DIR, "ui-strings.json"),
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        mode: "authenticated",
        chunks: files.length,
        studioChunks: studioChunks.length,
        uniqueStrings: all.size,
        studioStrings: studioStrings.size,
        strings: [...all.entries()]
          .sort((a, b) => b[1] - a[1])
          .map(([text, count]) => ({ text, count })),
      },
      null,
      2
    )
  );

  const lines = [
    "# Reference UI strings (derived)",
    "",
    `Generated ${new Date().toISOString()} from ${files.length} chunks (mode: **authenticated**).`,
    "",
    `- Unique candidate UI strings: **${all.size}**`,
    `- In chunks that reference \`/api/studio\`: **${studioStrings.size}**`,
    "",
    "> Labels only, deduplicated. No component structure or source is copied.",
    "> Use this as a checklist of controls to account for; decide independently how each behaves.",
    "",
    "## Studio-chunk strings",
    "",
    ...[...studioStrings].sort().map((text) => `- ${text}`),
    "",
  ];
  writeFileSync(join(OUT_DIR, "ui-strings.md"), lines.join("\n"));

  console.log(
    JSON.stringify({ chunks: files.length, studioChunks: studioChunks.length, unique: all.size, studio: studioStrings.size })
  );
}

main();
