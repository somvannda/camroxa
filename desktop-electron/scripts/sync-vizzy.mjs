#!/usr/bin/env node
/**
 * Vendor the real Rea/Vizzy editor into `desktop-electron/vizzy/`.
 *
 * The Rea editor lives outside this repository (no remote), so the port vendors
 * a reviewed copy instead of using a submodule. This script is the only writer:
 * re-running it reproduces the tree byte-for-byte from the same source, applies
 * the documented patch set, and records the source path, date and a content hash
 * in `vizzy/UPSTREAM.md`.
 *
 * Usage:
 *   node scripts/sync-vizzy.mjs
 *   node scripts/sync-vizzy.mjs --source "G:/Developments/Rea/editor"
 *   node scripts/sync-vizzy.mjs --check     # verify the vendored hash only
 *
 * Layout after a run:
 *   vizzy/
 *     UPSTREAM.md          provenance + hash (generated)
 *     package.json         Rea deps, pinned by package-lock.json (generated)
 *     package-lock.json    copied verbatim
 *     index.html           copied, entry script repointed (patch)
 *     tsconfig.json        copied
 *     vite.config.ts       generated: base "./", outDir ../vizzy-dist
 *     src/**               copied; src/host/* comes from vizzy/patches
 *     public/**            pruned copy (no 265 MB reference corpus)
 *     patches/             the patch set, source of truth (never overwritten)
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");
const repoRoot = path.resolve(appRoot, "..");

const DEFAULT_SOURCE = "G:/Developments/Rea/editor";

/** Files copied from the Rea root, verbatim. */
const ROOT_FILES = ["index.html", "tsconfig.json", "package.json", "package-lock.json"];

/**
 * `public/` is 276 MB upstream; `creations/` alone is 265 MB of reference
 * captures that ship as test fixtures, not in the installer. Everything below is
 * what the editor loads at boot or from a first-party panel.
 */
const PUBLIC_DIRS = [
  "export",
  "fonts",
  "img",
  "lottie",
  "media",
  "models",
  "particles",
  "presets",
  "vendor",
];
const PUBLIC_FILES = ["favicon.svg"];

/** Files the sync script owns; `patches/` is authored here and never wiped. */

function parseArgs(argv) {
  const args = { check: false, source: process.env.VIZZY_SOURCE ?? DEFAULT_SOURCE };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--check") args.check = true;
    else if (arg === "--source") args.source = argv[(index += 1)];
    else if (arg.startsWith("--source=")) args.source = arg.slice("--source=".length);
    else if (arg === "--help" || arg === "-h") args.help = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  return args;
}

function usage() {
  process.stdout.write(
    [
      "Sync the Rea/Vizzy editor into desktop-electron/vizzy.",
      "",
      "  node scripts/sync-vizzy.mjs [--source <dir>] [--check]",
      "",
      "--source  Rea editor checkout (default: VIZZY_SOURCE or " + DEFAULT_SOURCE + ")",
      "--check   only verify the vendored tree hash recorded in UPSTREAM.md",
      "",
    ].join("\n"),
  );
}

function assertDirectory(directory, label) {
  if (!fs.existsSync(directory) || !fs.statSync(directory).isDirectory()) {
    throw new Error(`${label} is not a directory: ${directory}`);
  }
}

/** Refuse to write anywhere but <repo>/desktop-electron/vizzy. */
function assertTarget(target) {
  const parent = path.basename(path.dirname(target));
  if (path.basename(target) !== "vizzy" || parent !== "desktop-electron") {
    throw new Error(`Refusing to write to an unexpected target: ${target}`);
  }
}

function readText(file) {
  return fs.readFileSync(file, "utf8");
}

/**
 * Replace one anchored block. The anchor is written with LF; Rea files are
 * CRLF, so the CRLF form is tried too and the file's own endings are preserved.
 */
function replaceOnce(file, anchor, replacement, label) {
  const text = readText(file);
  const variants = [anchor, anchor.replaceAll("\n", "\r\n")];
  for (const variant of variants) {
    const count = text.split(variant).length - 1;
    if (count === 1) {
      const replacementText = replacement.replaceAll(
        "\n",
        variant.includes("\r\n") ? "\r\n" : "\n",
      );
      // Function form: the replacement contains `${...}` and `$` is special.
      fs.writeFileSync(file, text.replace(variant, () => replacementText));
      return;
    }
    if (count > 1) throw new Error(`${label}: anchor matched ${count} times in ${file}`);
  }
  throw new Error(`${label}: anchor not found in ${file}. Rea changed; update the patch set.`);
}

function copyTree(source, target) {
  fs.cpSync(source, target, { recursive: true, force: true });
}

/**
 * Text stays LF in the vendored tree.
 *
 * The repository sets `core.autocrlf=true`, which would otherwise rewrite the
 * vendored bytes on checkout and invalidate the tree hash in UPSTREAM.md.
 * `vizzy/.gitattributes` sets `* -text` so git stores exactly these bytes.
 */
const TEXT_EXTENSIONS = new Set([
  ".ts",
  ".tsx",
  ".js",
  ".mjs",
  ".cjs",
  ".json",
  ".css",
  ".html",
  ".md",
  ".txt",
  ".fnt",
  ".obj",
  ".svg",
  ".map",
]);

function normaliseLineEndings(directory) {
  for (const relative of walk(directory)) {
    if (!TEXT_EXTENSIONS.has(path.extname(relative).toLowerCase())) continue;
    const full = path.join(directory, relative);
    const text = fs.readFileSync(full, "utf8");
    if (!text.includes("\r")) continue;
    fs.writeFileSync(full, text.replace(/\r\n/g, "\n").replace(/\r/g, "\n"));
  }
}

const GITATTRIBUTES = [
  "# Vendored Rea/Vizzy tree: git must not rewrite these bytes.",
  "# The repository uses core.autocrlf=true and UPSTREAM.md records a tree hash,",
  "# so line endings are fixed to LF by scripts/sync-vizzy.mjs.",
  "* -text",
  "",
].join("\n");

function walk(directory, base = directory) {
  const entries = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) entries.push(...walk(full, base));
    else if (entry.isFile()) entries.push(path.relative(base, full));
  }
  return entries;
}

/** Files that never belong to the vendored hash (generated or installed). */
const HASH_EXCLUDE = new Set(["UPSTREAM.md"]);

/** Stable content hash of a directory (sorted relative paths + bytes). */
function hashTree(directory) {
  const hash = crypto.createHash("sha256");
  for (const relative of walk(directory).sort()) {
    const posix = relative.split(path.sep).join("/");
    if (HASH_EXCLUDE.has(posix) || posix.startsWith("node_modules/")) continue;
    hash.update(posix);
    hash.update("\0");
    hash.update(fs.readFileSync(path.join(directory, relative)));
    hash.update("\0");
  }
  return hash.digest("hex");
}

function readRecordedHash(upstreamFile) {
  if (!fs.existsSync(upstreamFile)) return null;
  const match = readText(upstreamFile).match(/^Vendored tree sha256:\s*`([0-9a-f]{64})`/m);
  return match ? match[1] : null;
}

function writeGeneratedPackageJson(sourcePackage, target) {
  const source = JSON.parse(readText(sourcePackage));
  const generated = {
    name: "camxora-vizzy",
    private: true,
    version: source.version,
    description: "Camxora Desktop — vendored Rea/Vizzy editor. Generated by scripts/sync-vizzy.mjs.",
    type: "module",
    scripts: {
      dev: "vite",
      build: "vite build",
      preview: "vite preview",
    },
    dependencies: source.dependencies,
    devDependencies: source.devDependencies,
  };
  fs.writeFileSync(target, `${JSON.stringify(generated, null, 2)}\n`);
}

const VITE_CONFIG = `import { defineConfig } from "vite";

/**
 * Generated by scripts/sync-vizzy.mjs — edit the script, not this file.
 *
 * - \`base: "./"\` is the relative base the camxora-vizzy:// host was verified
 *   with (HOST-SPIKE.md §5.1).
 * - The bundle is a sibling of the app bundle (desktop-electron/vizzy-dist) so
 *   the main process can serve it from the custom protocol.
 * - COOP/COEP are delivered by the protocol handler, not by a dev server, and
 *   Rea's service worker is not shipped.
 */
export default defineConfig({
  base: "./",
  build: {
    target: "es2022",
    sourcemap: true,
    outDir: "../vizzy-dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 16384,
  },
  // The vendored tree sits inside desktop-electron/, whose postcss.config.js is
  // the Camxora app's Tailwind pipeline. Rea ships plain CSS and no PostCSS
  // config of its own, so an empty inline config keeps this build independent of
  // the parent directory.
  css: { postcss: {} },
  optimizeDeps: { exclude: ["@ffmpeg/ffmpeg", "@ffmpeg/util"] },
});
`;

function sync(sourceRoot) {
  assertDirectory(sourceRoot, "Rea source");
  const sourceMain = path.join(sourceRoot, "src", "main.ts");
  const sourceIndex = path.join(sourceRoot, "index.html");
  if (!fs.existsSync(sourceMain) || !fs.existsSync(sourceIndex)) {
    throw new Error(`Not a Rea editor checkout (src/main.ts + index.html missing): ${sourceRoot}`);
  }

  const target = path.join(appRoot, "vizzy");
  assertTarget(target);
  fs.mkdirSync(target, { recursive: true });

  // Wipe only the generated parts; patches/ stays.
  for (const relative of ["src", "public"]) {
    const full = path.join(target, relative);
    if (fs.existsSync(full)) fs.rmSync(full, { recursive: true, force: true });
  }

  for (const file of ROOT_FILES) {
    const source = path.join(sourceRoot, file);
    if (!fs.existsSync(source)) throw new Error(`Missing upstream file: ${source}`);
    fs.copyFileSync(source, path.join(target, file));
  }
  copyTree(path.join(sourceRoot, "src"), path.join(target, "src"));

  const publicTarget = path.join(target, "public");
  fs.mkdirSync(publicTarget, { recursive: true });
  for (const directory of PUBLIC_DIRS) {
    const source = path.join(sourceRoot, "public", directory);
    if (!fs.existsSync(source)) continue;
    copyTree(source, path.join(publicTarget, directory));
  }
  for (const file of PUBLIC_FILES) {
    const source = path.join(sourceRoot, "public", file);
    if (fs.existsSync(source)) fs.copyFileSync(source, path.join(publicTarget, file));
  }

  // Deterministic bytes before anything is hashed or patched.
  normaliseLineEndings(path.join(target, "src"));
  normaliseLineEndings(publicTarget);
  for (const file of ROOT_FILES) {
    const full = path.join(target, file);
    const text = readText(full);
    if (text.includes("\r")) fs.writeFileSync(full, text.replace(/\r\n/g, "\n"));
  }
  fs.writeFileSync(path.join(target, ".gitattributes"), GITATTRIBUTES);

  // Patch 1: one entry module, editor first, host adapter second.
  replaceOnce(
    path.join(target, "index.html"),
    '<script type="module" src="/src/main.ts"></script>',
    '<script type="module" src="/src/host/boot.ts"></script>',
    "index.html entry",
  );

  // Patch 2: the editor's own Save goes through the native project store when
  // the desktop bridge is present. The browser fallback below stays untouched.
  const hostDirectory = path.join(target, "src", "host");
  fs.mkdirSync(hostDirectory, { recursive: true });
  for (const file of ["bridge.ts", "host-adapter.ts", "boot.ts"]) {
    const source = path.join(target, "patches", file);
    if (!fs.existsSync(source)) throw new Error(`Missing patch file: ${source}`);
    fs.copyFileSync(source, path.join(hostDirectory, file));
  }

  replaceOnce(
    path.join(target, "src", "main.ts"),
    [
      "async function saveProjectLocally(): Promise<void> {",
      "  const snapshot = serializeProject(project);",
      "  const thumbnail = captureProjectThumbnail();",
    ].join("\n"),
    [
      "async function saveProjectLocally(): Promise<void> {",
      "  const snapshot = serializeProject(project);",
      "  const thumbnail = captureProjectThumbnail();",
      "  // CAMXORA-PATCH (scripts/sync-vizzy.mjs): when the hosted desktop build",
      "  // injects window.camxoraVizzy, Save is owned by the native project store.",
      "  // The IndexedDB path below remains the browser fallback.",
      "  const vizzyHost = (",
      "    window as unknown as {",
      "      camxoraVizzy?: {",
      "        saveProject(name: string, json: string): Promise<{ path?: string } | null>;",
      "      };",
      "    }",
      "  ).camxoraVizzy;",
      "  if (vizzyHost) {",
      "    try {",
      "      const saved = await vizzyHost.saveProject(project.name, JSON.stringify(snapshot));",
      "      if (saved) {",
      "        $(\"#save-state\").textContent = `Saved ${new Date().toLocaleTimeString([], {",
      '          hour: "2-digit",',
      '          minute: "2-digit",',
      "        })}`;",
      "        setStatus(",
      '          `Saved "${project.name}" - ${project.nodes.length} items, ${project.layers.length} layers.`,',
      "        );",
      "        return;",
      "      }",
      "    } catch {",
      "      // Fall through to the local store so a host failure still keeps work.",
      "    }",
      "  }",
    ].join("\n"),
    "main.ts native save",
  );

  replaceOnce(
    path.join(target, "src", "main.ts"),
    "let exporting = false;",
    [
      "let exporting = false;",
      "// CAMXORA-PATCH (scripts/sync-vizzy.mjs): when the shell drives an export,",
      "// runExport() reports progress and checks the host's cancel flag here.",
      "let camxoraExportHooks: {",
      "  progress(done: number, total: number, stage: string): void;",
      "  cancelled(): boolean;",
      "} | null = null;",
    ].join("\n"),
    "main.ts export hooks",
  );

  replaceOnce(
    path.join(target, "src", "main.ts"),
    "      shouldCancel: () => progress.isCancelled(),",
    [
      "      shouldCancel: () =>",
      "        progress.isCancelled() || camxoraExportHooks?.cancelled() === true,",
    ].join("\n"),
    "main.ts export cancel",
  );

  replaceOnce(
    path.join(target, "src", "main.ts"),
    [
      "        progress.update(done, total, stage);",
      "      },",
    ].join("\n"),
    [
      "        progress.update(done, total, stage);",
      "        // CAMXORA-PATCH: stream progress to the desktop shell.",
      "        camxoraExportHooks?.progress(done, total, stage);",
      "      },",
    ].join("\n"),
    "main.ts export progress",
  );

  // Patch 5: the host-driven export runner. Reuses runExport() and the editor's
  // own encoders; chunks go straight to the host at absolute offsets.
  replaceOnce(
    path.join(target, "src", "main.ts"),
    "// This module owns the WebGL renderer, the editor DOM and the rAF loop. Vite's",
    [
      "/* CAMXORA-PATCH (scripts/sync-vizzy.mjs): host-driven native export.",
      " *",
      " * The shell owns the job, the destination file and cancellation. This block",
      " * calls the editor's own runExport() with a SaveFileHandle whose write()",
      " * forwards encoded chunks to the desktop process (structured clone, never",
      " * base64), reports progress through the bridge, and reports a terminal state",
      " * exactly once. The in-page export dialog above is unchanged and still works",
      " * as the browser fallback.",
      " */",
      "{",
      "  interface HostExportSettings {",
      "    width: number;",
      "    height: number;",
      "    fps: number;",
      "    format: \"mp4\" | \"webm\";",
      "    codec: \"h264\" | \"vp8\" | \"vp9\";",
      "    bitrate: number;",
      "    crf: number;",
      "    engine?: \"wasm\" | \"webcodecs\";",
      "    start: number;",
      "    end: number;",
      "  }",
      "  interface HostExportCommand {",
      "    v: 1;",
      "    type: string;",
      "    jobId?: string;",
      "    settings?: HostExportSettings;",
      "  }",
      "  interface HostExportBridge {",
      "    exportChunk(jobId: string, position: number, data: Uint8Array): Promise<{ bytes: number }>;",
      "    exportProgress(payload: {",
      "      jobId: string;",
      "      done: number;",
      "      total: number;",
      "      stage: string;",
      "    }): void;",
      "    exportFinished(payload: {",
      "      jobId: string;",
      "      ok: boolean;",
      "      cancelled: boolean;",
      "      frames: number;",
      "      error?: string;",
      "    }): void;",
      "    onCommand(handler: (command: HostExportCommand) => void): () => void;",
      "  }",
      "",
      "  const exportHost = (window as unknown as { camxoraVizzy?: HostExportBridge }).camxoraVizzy;",
      "  if (exportHost && typeof exportHost.onCommand === \"function\") {",
      "    let activeJobId: string | null = null;",
      "    let cancelRequested = false;",
      "",
      "    const isAbort = (reason: unknown): boolean =>",
      "      (reason instanceof DOMException && reason.name === \"AbortError\") ||",
      "      (reason instanceof Error && /cancel/i.test(reason.message)) ||",
      "      (typeof reason === \"string\" && /cancel/i.test(reason));",
      "",
      "    exportHost.onCommand((command) => {",
      "      if (command.type === \"export-cancel\") {",
      "        if (command.jobId && command.jobId === activeJobId) cancelRequested = true;",
      "        return;",
      "      }",
      "      if (command.type !== \"export-run\" || !command.jobId || !command.settings) return;",
      "      if (activeJobId) return;",
      "",
      "      const jobId = command.jobId;",
      "      const request = command.settings;",
      "      const format = request.format === \"webm\" ? \"webm\" : \"mp4\";",
      "      const codec: ExportCodec =",
      "        format === \"mp4\" ? \"h264\" : request.codec === \"vp8\" ? \"vp8\" : \"vp9\";",
      "      const settings: ExportSettings = {",
      "        ...defaultExportSettings(),",
      "        width: request.width,",
      "        height: request.height,",
      "        fps: request.fps,",
      "        start: request.start,",
      "        end: request.end,",
      "        codec,",
      "        bitrate: request.bitrate,",
      "        crf: request.crf,",
      "        // Honour the requested encoder. WebCodecs supports AVC/MP4 as well",
      "        // as VP8/VP9/WebM; the export dialog's choice must not be ignored.",
      "        engine:",
      "          request.engine === \"webcodecs\" && WebCodecsExporter.available()",
      "            ? \"webcodecs\"",
      "            : \"wasm\",",
      "      };",
      "      let framesTotal = Math.max(",
      "        1,",
      "        Math.round(Math.max(0.1, settings.end - settings.start) * Math.max(1, Math.round(settings.fps))),",
      "      );",
      "",
      "      activeJobId = jobId;",
      "      cancelRequested = false;",
      "      let reported = false;",
      "      let renderedFrames = 0;",
      "",
      "      const report = (payload: {",
      "        ok: boolean;",
      "        cancelled: boolean;",
      "        frames: number;",
      "        error?: string;",
      "      }): void => {",
      "        if (reported) return;",
      "        reported = true;",
      "        activeJobId = null;",
      "        camxoraExportHooks = null;",
      "        exportHost.exportFinished({ jobId, ...payload });",
      "      };",
      "",
      "      const handle: SaveFileHandle = {",
      "        name: `${jobId}.${format}`,",
      "        async createWritable() {",
      "          return {",
      "            async write(data) {",
      "              if (data && typeof data === \"object\" && \"type\" in data && data.type === \"write\") {",
      "                await exportHost.exportChunk(jobId, data.position, data.data);",
      "                return;",
      "              }",
      "              // Blob fallback (non-streaming wasm ladder): slice it so no IPC",
      "              // message ever carries the whole video.",
      "              const bytes = new Uint8Array(await (data as Blob).arrayBuffer());",
      "              const size = 4 * 1024 * 1024;",
      "              for (let offset = 0; offset < bytes.byteLength; offset += size) {",
      "                await exportHost.exportChunk(",
      "                  jobId,",
      "                  offset,",
      "                  bytes.subarray(offset, Math.min(bytes.byteLength, offset + size)),",
      "                );",
      "              }",
      "            },",
      "            async close() {",
      "              report({ ok: true, cancelled: false, frames: Math.max(renderedFrames, framesTotal) });",
      "            },",
      "            async abort(reason) {",
      "              report({",
      "                ok: false,",
      "                cancelled: cancelRequested || isAbort(reason),",
      "                frames: renderedFrames,",
      "                error:",
      "                  reason instanceof Error",
      "                    ? reason.message",
      "                    : String(reason ?? \"Export aborted\"),",
      "              });",
      "            },",
      "          };",
      "        },",
      "      };",
      "",
      "      camxoraExportHooks = {",
      "        progress(done: number, total: number, stage: string) {",
      "          renderedFrames = Math.max(renderedFrames, done);",
      "          if (total > 0) framesTotal = total;",
      "          exportHost.exportProgress({ jobId, done, total, stage });",
      "        },",
      "        cancelled: () => cancelRequested,",
      "      };",
      "",
      "      void (async () => {",
      "        try {",
      "          await runExport(settings, handle);",
      "        } finally {",
      "          if (!reported) {",
      "            report({",
      "              ok: false,",
      "              cancelled: cancelRequested,",
      "              frames: renderedFrames,",
      "              error: cancelRequested",
      "                ? \"The export was cancelled.\"",
      "                : \"The exporter finished without writing a file.\",",
      "            });",
      "          }",
      "          if (activeJobId === jobId) activeJobId = null;",
      "          camxoraExportHooks = null;",
      "        }",
      "      })();",
      "    });",
      "  }",
      "}",
      "",
      "// This module owns the WebGL renderer, the editor DOM and the rAF loop. Vite's",
    ].join("\n"),
    "main.ts host export",
  );

  // Patch set for Camxora's parity and performance fixes. Each anchor is
  // matched against the pristine Rea file; a Rea change fails the sync loudly.
  replaceOnce(
    path.join(target, "src", "audio", "spectrum.ts"),
    [
      "    if (!this.threaded) return;",
      "    while (this.busy) {",
      "      await new Promise((resolve) => setTimeout(resolve, 1));",
      "    }",
      "    this.busy = true;",
      "    try {",
      "      const result = await this.threaded.transform(this.samples.slice(), this.fftSize);",
      "      this.bins.set(result.magnitudes);",
      "      this.lastMs = result.elapsedMs;",
      "      this.mapBands(dt);",
      "    } catch (error) {",
      '      this.degrade("threads", String(error));',
      "      const result = this.sequential.transform(this.samples, this.fftSize);",
      "      this.bins.set(result.magnitudes);",
      "      this.lastMs = result.elapsedMs;",
      "      this.mapBands(dt);",
      "    } finally {",
      "      this.busy = false;",
      "    }",
    ].join("\n"),
    [
      "    if (!this.threaded) return;",
      "    // Export is not real time. A worker round-trip measured ~34 ms per frame",
      "    // here, while the same 2048-point transform runs in ~0.2 ms in-process, so",
      "    // run it on the calling thread and never stall the export loop on",
      "    // postMessage latency. Preview keeps the threaded tier above.",
      "    const result = this.sequential.transform(this.samples, this.fftSize);",
      "    this.bins.set(result.magnitudes);",
      "    this.lastMs = result.elapsedMs;",
      "    this.mapBands(dt);",
    ].join("\n"),
    "spectrum export fft",
  );

  replaceOnce(
    path.join(target, "src", "export", "webcodecs-exporter.ts"),
    ["        keyFrameInterval: 2,", "      });"].join("\n"),
    [
      "        keyFrameInterval: 2,",
      "        // Hardware encoders are idle by default (prefer-hardware measured",
      "        // 2.3x faster here); Chromium falls back when it cannot honour it.",
      '        hardwareAcceleration: "prefer-hardware",',
      "      });",
    ].join("\n"),
    "webcodecs hardware encoder",
  );

  replaceOnce(
    path.join(target, "src", "export", "webcodecs-exporter.ts"),
    [
      "      for (let frame = 0; frame < total; frame += 1) {",
      "        if (options.shouldCancel?.()) {",
      '          throw new DOMException("Export cancelled", "AbortError");',
      "        }",
      "        const time = (start + frame / options.fps) % Math.max(0.001, project.duration);",
      "        await options.beforeFrame?.(time);",
      "        renderer.render(time);",
      "        await video.add(frame / options.fps, 1 / options.fps);",
      '        options.onProgress(frame + 1, total, "encoding frames");',
      "      }",
    ].join("\n"),
    [
      "      let tickMs = 0;",
      "      let drawMs = 0;",
      "      let encodeMs = 0;",
      "      for (let frame = 0; frame < total; frame += 1) {",
      "        if (options.shouldCancel?.()) {",
      '          throw new DOMException("Export cancelled", "AbortError");',
      "        }",
      "        const time = (start + frame / options.fps) % Math.max(0.001, project.duration);",
      "        const beforeTick = performance.now();",
      "        await options.beforeFrame?.(time);",
      "        const beforeDraw = performance.now();",
      "        renderer.render(time);",
      "        const beforeEncode = performance.now();",
      "        await video.add(frame / options.fps, 1 / options.fps);",
      "        const afterEncode = performance.now();",
      "        tickMs += beforeDraw - beforeTick;",
      "        drawMs += beforeEncode - beforeDraw;",
      "        encodeMs += afterEncode - beforeEncode;",
      '        options.onProgress(frame + 1, total, "encoding frames");',
      "      }",
      '      console.warn(',
      '        "vizzy export profile",',
      "        JSON.stringify({",
      '          engine: "webcodecs",',
      "          frames: total,",
      "          tickMs: Math.round(tickMs / total),",
      "          drawMs: Math.round(drawMs / total),",
      "          encodeMs: Math.round(encodeMs / total),",
      "        }),",
      "      );",
    ].join("\n"),
    "webcodecs export profile",
  );

  replaceOnce(
    path.join(target, "src", "main.ts"),
    [
      "function newProject(): void {",
      '  if (!window.confirm("Start a new project? Unsaved changes will be lost.")) return;',
    ].join("\n"),
    [
      "function newProject(force = false): void {",
      '  if (!force && !window.confirm("Start a new project? Unsaved changes will be lost.")) return;',
    ].join("\n"),
    "main.ts new project force",
  );

  replaceOnce(
    path.join(target, "src", "main.ts"),
    "  editorOpenExportDialog: openExportDialog,",
    [
      "  editorOpenExportDialog: openExportDialog,",
      "  editorNewProject: (force = false) => newProject(force),",
    ].join("\n"),
    "main.ts new project hook",
  );

  replaceOnce(
    path.join(target, "src", "ui", "inspector.ts"),
    [
      "      if (row.impact) {",
      "        range.append(",
      '          makeInput(row.impact.from, "from", "from"),',
      '          makeInput(row.impact.to, "to", "to"),',
      "        );",
      "      } else {",
    ].join("\n"),
    [
      "      if (row.impact) {",
      "        const readout = document.createElement(\"span\");",
      '        readout.className = "value";',
      "        readout.textContent = `${axis} ${trimNumber(row.impact.from)} -> ${trimNumber(row.impact.to)}`;",
      "        range.append(",
      "          readout,",
      '          makeInput(row.impact.from, "from", "from"),',
      '          makeInput(row.impact.to, "to", "to"),',
      "        );",
      "      } else {",
    ].join("\n"),
    "inspector audio-impact readout",
  );

  replaceOnce(
    path.join(target, "src", "main.ts"),
    ['    ["1080x1350", "1080x1350 (Portrait)"],', "  ];"].join("\n"),
    [
      '    ["1080x1350", "1080x1350 (Portrait)"],',
      '    ["1080x2160", "1080x2160 (1:2)"],',
      "  ];",
    ].join("\n"),
    "main.ts 1:2 export preset",
  );

  replaceOnce(
    path.join(target, "src", "renderer", "renderer.ts"),
    "  private fullResolution = false;",
    [
      "  private fullResolution = false;",
      "  /** Explicit framebuffer while an export owns the renderer. */",
      "  private exportSize: { width: number; height: number } | null = null;",
    ].join("\n"),
    "renderer export size field",
  );

  replaceOnce(
    path.join(target, "src", "renderer", "renderer.ts"),
    ["  resize(): void {", "    const parent = this.canvas.parentElement;"].join("\n"),
    [
      "  resize(): void {",
      "    // During an export the renderer owns an explicit framebuffer size. A shell",
      "    // panel resize must not shrink it mid-render or frames use the wrong stride.",
      "    if (this.exportSize) {",
      "      this.renderer.setPixelRatio(1);",
      "      this.renderer.setSize(this.exportSize.width, this.exportSize.height, false);",
      "      return;",
      "    }",
      "",
      "    const parent = this.canvas.parentElement;",
    ].join("\n"),
    "renderer export size resize guard",
  );

  replaceOnce(
    path.join(target, "src", "renderer", "renderer.ts"),
    [
      "  setExportSize(width: number, height: number): () => void {",
      "    const previousRatio = this.renderer.getPixelRatio();",
      "    this.renderer.setPixelRatio(1);",
      "    this.renderer.setSize(width, height, false);",
      "    return () => {",
      "      this.renderer.setPixelRatio(previousRatio);",
    ].join("\n"),
    [
      "  setExportSize(width: number, height: number): () => void {",
      "    const previousRatio = this.renderer.getPixelRatio();",
      "    this.exportSize = { width, height };",
      "    this.renderer.setPixelRatio(1);",
      "    this.renderer.setSize(width, height, false);",
      "    return () => {",
      "      this.exportSize = null;",
      "      this.renderer.setPixelRatio(previousRatio);",
    ].join("\n"),
    "renderer export size setter",
  );

  replaceOnce(
    path.join(target, "src", "renderer", "post-processing.ts"),
    [
      "          // Alpha is carried through the chain so a layer's result can be",
      "          // composited over the frame beneath it.",
      "          transparent: true,",
      "        });",
    ].join("\n"),
    [
      "          // Alpha is carried through the chain so a layer's result can be",
      "          // composited over the frame beneath it.",
      "          transparent: true,",
      "          // The reference builds every effect material through",
      "          // `getBlendingParams()`: CustomBlending with src ONE and dst",
      "          // ONE_MINUS_SRC_ALPHA (ONE/ONE for a perspective layer). A pass may",
      "          // output alpha 0 and still contribute RGB; NormalBlending",
      "          // multiplied that RGB away, which cost `abnormal` 81.06 -> 45.24.",
      "          blending: THREE.CustomBlending,",
      "          blendEquation: THREE.AddEquation,",
      "          blendSrc: THREE.OneFactor,",
      "          blendDst: THREE.OneMinusSrcAlphaFactor,",
      "        });",
    ].join("\n"),
    "post-processing effect material premultiplied blending",
  );

  const themePatch = path.join(target, "patches", "theme.css");
  if (fs.existsSync(themePatch)) {
    fs.appendFileSync(
      path.join(target, "src", "styles.css"),
      "\n" + readText(themePatch).replace(/\r\n/g, "\n"),
    );
  }

  writeGeneratedPackageJson(path.join(target, "package.json"), path.join(target, "package.json"));
  fs.writeFileSync(path.join(target, "vite.config.ts"), VITE_CONFIG);

  const hash = hashTree(target);
  const files = walk(target).filter(
    (relative) =>
      relative !== "UPSTREAM.md" && !relative.split(path.sep).join("/").startsWith("node_modules/"),
  );

  const upstream = [
    "# Vendored Rea/Vizzy editor",
    "",
    "> Generated by `scripts/sync-vizzy.mjs`. Do not edit `src/`, `public/`, `index.html`,",
    "> `package.json`, `package-lock.json`, `tsconfig.json` or `vite.config.ts` by hand:",
    "> the next sync overwrites them. Host changes belong in `patches/`.",
    "",
    "| Field | Value |",
    "|---|---|",
    `| Source | \`${sourceRoot.replaceAll("\\", "/")}\` |`,
    `| Synced at | ${new Date().toISOString()} |`,
    `| Files vendored | ${files.length} |`,
    `| Public dirs | ${PUBLIC_DIRS.map((entry) => `\`${entry}/\``).join(", ")} (no \`creations/\`) |`,
    "",
    `Vendored tree sha256: \`${hash}\``,
    "",
    "## Patch set",
    "",
    "Applied by the sync script, with anchors that fail loudly when Rea moves:",
    "",
    "| Patch | Where | What |",
    "|---|---|---|",
    "| Boot entry | `index.html` | `/src/main.ts` → `/src/host/boot.ts` (editor first, adapter second) |",
    "| Host adapter | `src/host/host-adapter.ts` | `window.__vizzyTest`, dirty tracking, native open/save state |",
    "| Bridge contract | `src/host/bridge.ts` | `window.camxoraVizzy` types injected by `electron/vizzy-preload.ts` |",
    "| Native save | `src/main.ts` | `saveProjectLocally()` routes to the host when the bridge exists |",
    "| Native export hooks | `src/main.ts` | `runExport()` reports progress and honours the host's cancel flag |",
    "| Native export runner | `src/main.ts` | host `export-run` drives `runExport()` with a chunk-streaming save handle |",
    "",
    "## Rebuild",
    "",
    "```powershell",
    "node scripts/sync-vizzy.mjs --check    # verify the vendored hash",
    "npm --prefix vizzy ci",
    "npm --prefix vizzy run build           # → desktop-electron/vizzy-dist",
    "```",
    "",
    "## Not vendored",
    "",
    "`public/creations/` (265 MB reference captures), `.shots/`, `node_modules/`,",
    "`test-*.mjs`, `verify-*.mjs`, `audit-presets.mjs`, Rea docs and the coi service",
    "worker (`coi-sw.js`): the Electron host delivers COOP/COEP itself.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(target, "UPSTREAM.md"), upstream);

  return { target, hash, files: files.length };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    usage();
    return;
  }

  const target = path.join(appRoot, "vizzy");
  assertTarget(target);

  if (args.check) {
    const recorded = readRecordedHash(path.join(target, "UPSTREAM.md"));
    const actual = hashTree(target);
    if (!recorded) throw new Error("UPSTREAM.md is missing a recorded hash; run the sync first.");
    if (recorded !== actual) {
      throw new Error(
        `Vendored tree does not match UPSTREAM.md (recorded ${recorded}, actual ${actual}).`,
      );
    }
    process.stdout.write(`vizzy tree ok (${recorded.slice(0, 12)})\n`);
    return;
  }

  const source = path.resolve(args.source);
  const result = sync(source);
  process.stdout.write(
    `synced ${result.files} files from ${source} → ${path.relative(repoRoot, result.target)}\n` +
      `vendored sha256 ${result.hash}\n`,
  );
}

try {
  main();
} catch (error) {
  process.stderr.write(`sync-vizzy failed: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
