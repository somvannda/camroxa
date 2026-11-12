#!/usr/bin/env node
/**
 * Download a list of public static assets (one path per line) from suno.com.
 *
 *   node tools/suno-re/fetch-list.mjs --list ass.txt --out %TEMP%/suno-re --dir chunks-authed
 */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const listFile = arg("list");
const outDir = arg("out", join(process.env.TEMP || "/tmp", "suno-re"));
const subDir = arg("dir", "chunks-authed");

if (!listFile) {
  console.error("--list is required");
  process.exit(1);
}

const target = join(outDir, subDir);
mkdirSync(target, { recursive: true });

const assets = readFileSync(listFile, "utf8")
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter(Boolean);

let saved = 0;
let bytes = 0;
const queue = assets.slice();

async function main() {
  await Promise.all(
    Array.from({ length: 8 }, async () => {
      while (queue.length) {
        const rel = queue.shift();
        const dest = join(target, rel.split("/").pop());
        if (existsSync(dest)) {
          saved += 1;
          continue;
        }
        try {
          const res = await fetch(`https://suno.com${rel}`, { headers: { "user-agent": UA } });
          if (!res.ok) continue;
          const text = await res.text();
          writeFileSync(dest, text);
          saved += 1;
          bytes += text.length;
        } catch {
          /* tolerate individual misses */
        }
      }
    })
  );
  console.log(JSON.stringify({ requested: assets.length, saved, kb: Math.round(bytes / 1024), dir: target }));
}

main();
