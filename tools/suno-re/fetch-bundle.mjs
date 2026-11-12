#!/usr/bin/env node
/**
 * Download a public Suno route plus every JS chunk it references.
 *
 * Only public, unauthenticated assets: the route HTML and `/_next/static/**`.
 * Raw output goes to a temp directory and is never committed.
 *
 *   node tools/suno-re/fetch-bundle.mjs --url https://suno.com/studio --out %TEMP%/suno-re
 */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";

function arg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

const url = arg("url", "https://suno.com/studio");
const outDir = arg("out", join(process.env.TEMP || "/tmp", "suno-re"));
const concurrency = Number(arg("concurrency", "8"));

mkdirSync(outDir, { recursive: true });
const htmlPath = join(outDir, "route.html");

async function main() {
  if (!existsSync(htmlPath)) {
    const res = await fetch(url, { headers: { "user-agent": UA }, redirect: "follow" });
    const html = await res.text();
    writeFileSync(htmlPath, html);
    console.log(`html ${res.status} ${res.url} ${Math.round(html.length / 1024)}kb`);
  } else {
    console.log("html cached");
  }

  const html = readFileSync(htmlPath, "utf8");
  const chunkDir = join(outDir, "chunks");
  mkdirSync(chunkDir, { recursive: true });

  const assets = [
    ...new Set(
      [...html.matchAll(/(?:src|href)="(\/_next\/static\/[^"]+\.js[^"]*)"/g)].map((m) => m[1])
    ),
  ];

  let saved = 0;
  let bytes = 0;
  const queue = assets.slice();

  await Promise.all(
    Array.from({ length: concurrency }, async () => {
      while (queue.length) {
        const rel = queue.shift();
        const dest = join(chunkDir, rel.split("/").pop());
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
          /* skip a chunk, the extractor tolerates gaps */
        }
      }
    })
  );

  console.log(
    JSON.stringify({ assets: assets.length, saved, kb: Math.round(bytes / 1024), dir: chunkDir })
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
