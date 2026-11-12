#!/usr/bin/env node
/**
 * Derive an API contract inventory from publicly shipped Suno client chunks.
 *
 * Output is facts only (paths, methods, field names). No minified source is copied
 * into the repository.
 *
 *   node tools/suno-re/extract-contracts.mjs --chunks %TEMP%/suno-re/chunks
 */
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";

const REPO = process.cwd();
const OUT_DIR = join(REPO, "docs", "studio", "reference");

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const chunkDir = arg("chunks", join(process.env.TEMP || "/tmp", "suno-re", "chunks"));

const JS_KEYWORDS = new Set([
  "if", "else", "return", "await", "new", "typeof", "function", "const", "let", "var",
  "true", "false", "null", "undefined", "catch", "try", "throw", "for", "while", "in",
  "of", "this", "case", "default", "break", "continue", "async", "yield", "delete",
  "void", "instanceof", "class", "extends", "super", "import", "export", "from",
]);

/** Skip a quoted string starting at `start`; returns the index after it. */
function skipString(src, start) {
  const quote = src[start];
  let i = start + 1;
  while (i < src.length) {
    if (src[i] === "\\") {
      i += 2;
      continue;
    }
    if (src[i] === quote) return i + 1;
    i += 1;
  }
  return i;
}

/**
 * Read the keys of the object literal starting at `start` (which must be `{`).
 * Only depth-1 keys are returned, which keeps the result close to the real payload.
 */
function readTopLevelKeys(src, start, limit = 2400) {
  if (src[start] !== "{") return [];
  const keys = [];
  let depth = 1;
  let i = start + 1;
  let token = "";
  let expectingKey = true;
  const end = Math.min(src.length, start + limit);
  while (i < end && depth > 0) {
    const ch = src[i];
    if (ch === '"' || ch === "'" || ch === "`") {
      const next = skipString(src, i);
      if (depth === 1 && expectingKey) {
        keys.push(src.slice(i + 1, next - 1));
        expectingKey = false;
      }
      i = next;
      continue;
    }
    if (ch === "{" || ch === "[" || ch === "(") {
      depth += 1;
      i += 1;
      continue;
    }
    if (ch === "}" || ch === "]" || ch === ")") {
      depth -= 1;
      i += 1;
      if (depth === 1) expectingKey = true;
      continue;
    }
    if (depth === 1) {
      if (ch === ",") {
        expectingKey = true;
        token = "";
        i += 1;
        continue;
      }
      if (ch === ":" && expectingKey) {
        const name = token.trim().replace(/^['"`]|['"`]$/g, "");
        if (name && !JS_KEYWORDS.has(name)) keys.push(name);
        expectingKey = false;
        token = "";
        i += 1;
        continue;
      }
      if (expectingKey) token += ch;
    }
    i += 1;
  }
  return [...new Set(keys.filter((key) => /^[A-Za-z_$][\w$]*$/.test(key)))];
}

/** Find the nearest HTTP method token before an endpoint literal. */
function nearestMethod(src, index) {
  const window = src.slice(Math.max(0, index - 320), index);
  const calls = [...window.matchAll(/\.(GET|POST|PUT|PATCH|DELETE)\s*\(/g)];
  if (calls.length) return calls[calls.length - 1][1];
  const literal = [...window.matchAll(/method\s*:\s*["'](GET|POST|PUT|PATCH|DELETE)["']/gi)];
  if (literal.length) return literal[literal.length - 1][1].toUpperCase();
  return "GET";
}

/** Keys that come from fetch/transport plumbing rather than a payload. */
const NOISE_KEYS = new Set(["data", "body", "params", "headers", "signal", "request", "options", "config", "init"]);

/** Collect `body:{...}`, `query:{...}` and path params near an endpoint. */
function nearbyShape(src, index, method, stopAt) {
  const end = Math.min(stopAt ?? src.length, index + 1600);
  const window = src.slice(index, end);
  const bodyHit = window.match(/body\s*:\s*\{/);
  const queryHit = window.match(/query\s*:\s*\{/);
  const clean = (keys) => keys.filter((key) => !NOISE_KEYS.has(key));
  const bodyKeys = method === "GET"
    ? []
    : clean(bodyHit ? readTopLevelKeys(window, window.indexOf("{", bodyHit.index)) : []);
  const queryKeys = method === "GET"
    ? clean(queryHit ? readTopLevelKeys(window, window.indexOf("{", queryHit.index)) : [])
    : [];
  return { bodyKeys, queryKeys };
}

function main() {
  const files = readdirSync(chunkDir).filter((name) => name.endsWith(".js"));
  const inventory = new Map();
  let occurrences = 0;

  for (const file of files) {
    let src;
    try {
      src = readFileSync(join(chunkDir, file), "utf8");
    } catch {
      continue;
    }
    const matches = [...src.matchAll(/["'`](\/api\/[A-Za-z0-9_\-./{}$:]{2,120})["'`]/g)];
    for (let position = 0; position < matches.length; position += 1) {
      const match = matches[position];
      const nextIndex = matches[position + 1]?.index ?? src.length;
      let path = match[1];
      if (path.includes("$")) continue;
      path = path.replace(/\/+$/, "");
      const index = match.index ?? 0;
      const method = nearestMethod(src, index);
      const { bodyKeys, queryKeys } = nearbyShape(src, index, method, nextIndex);
      const params = [...path.matchAll(/\{([A-Za-z0-9_]+)\}/g)].map((m) => m[1]);
      const key = `${method} ${path}`;
      occurrences += 1;

      const existing = inventory.get(key);
      if (existing) {
        for (const value of bodyKeys) if (!existing.bodyKeys.includes(value)) existing.bodyKeys.push(value);
        for (const value of queryKeys) if (!existing.queryKeys.includes(value)) existing.queryKeys.push(value);
        if (!existing.chunks.includes(file)) existing.chunks.push(file);
      } else {
        inventory.set(key, {
          method,
          path,
          params: [...new Set(params)],
          bodyKeys: [...new Set(bodyKeys)],
          queryKeys: [...new Set(queryKeys)],
          chunks: [file],
        });
      }
    }
  }

  const rows = [...inventory.values()].sort(
    (a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method)
  );

  const studio = rows.filter((row) => /studio|project_revision|clip|render|persona|stem/i.test(row.path));

  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(
    join(OUT_DIR, "endpoint-inventory.json"),
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        mode: "anonymous",
        source: "public /_next/static chunks referenced by the /studio marketing route",
        chunkCount: files.length,
        occurrenceCount: occurrences,
        endpointCount: rows.length,
        endpoints: rows,
      },
      null,
      2
    )
  );

  const lines = [
    "# Reference endpoint inventory",
    "",
    `Generated ${new Date().toISOString()} from ${files.length} public chunks (mode: **anonymous**).`,
    "",
    `- Unique endpoints: **${rows.length}** (${occurrences} occurrences)`,
    `- Studio-related endpoints: **${studio.length}**`,
    "",
    "> Derived facts only: paths, methods and field names. No source is copied.",
    "> This is a specification source, never a runtime dependency (D-002).",
    "",
    "## Studio-related endpoints",
    "",
    "| Method | Path | Body fields | Query fields | Params |",
    "|---|---|---|---|---|",
    ...studio.map(
      (row) =>
        `| ${row.method} | \`${row.path}\` | ${row.bodyKeys.map((k) => `\`${k}\``).join(", ") || "—"} | ${
          row.queryKeys.map((k) => `\`${k}\``).join(", ") || "—"
        } | ${row.params.map((k) => `\`${k}\``).join(", ") || "—"} |`
    ),
    "",
    "## All endpoints",
    "",
    "| Method | Path |",
    "|---|---|",
    ...rows.map((row) => `| ${row.method} | \`${row.path}\` |`),
    "",
  ];
  writeFileSync(join(OUT_DIR, "endpoint-inventory.md"), lines.join("\n"));

  console.log(
    JSON.stringify({
      chunks: files.length,
      occurrences,
      endpoints: rows.length,
      studioEndpoints: studio.length,
      out: OUT_DIR,
    })
  );
}

main();
