#!/usr/bin/env node
/**
 * Vizzy host spike runner.
 *
 * Bundles electron/vizzy-host/spike-main.ts on demand (esbuild is already a dev
 * dependency) and launches it under Playwright's Electron driver for each
 * transport:
 *
 *   protocol  camxora-vizzy://vizzy/index.html  (privileged custom scheme)
 *   loopback  http://127.0.0.1:<port>/t/<token>/index.html
 *
 * Usage:
 *   node scripts/vizzy-host-spike.mjs                  # both transports
 *   node scripts/vizzy-host-spike.mjs --mode=loopback  # one transport
 *   node scripts/vizzy-host-spike.mjs --out=artifacts/vizzy-host-spike/report.json
 *
 * Exits 0 only when every required measurement passes for every mode.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { _electron as electron } from "playwright";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const pageRoot = path.join(root, "electron", "vizzy-host", "page");

const modeArg = process.argv.find((arg) => arg.startsWith("--mode="))?.slice("--mode=".length) ?? "both";
const outArg = process.argv.find((arg) => arg.startsWith("--out="))?.slice("--out=".length);
const modes = modeArg === "both" ? ["protocol", "loopback"] : [modeArg];
if (modes.some((mode) => mode !== "protocol" && mode !== "loopback")) {
  console.error(`Unknown --mode=${modeArg}. Use protocol, loopback or both.`);
  process.exit(2);
}

const REQUIRED_CHECKS = [
  "crossOriginIsolated",
  "sharedArrayBuffer",
  "sharedMemoryWorks",
  "webgl2",
  "worker",
  "workerAtomics",
  "moduleWorker",
  "wasm",
  "wasmSimd",
];

function summarize(envelope) {
  const result = envelope && envelope.result ? envelope.result : null;
  return {
    crossOriginIsolated: result ? result.crossOriginIsolated === true : false,
    sharedArrayBuffer: result ? result.sharedArrayBuffer === true : false,
    sharedMemoryWorks: result ? result.sharedMemoryWorks === true : false,
    webgl2: Boolean(result && result.webgl2 && result.webgl2.ok),
    worker: Boolean(result && result.worker && result.worker.ok),
    workerAtomics: Boolean(
      result &&
        result.crossThread &&
        result.crossThread.classic === 42 &&
        result.crossThread.module === 7,
    ),
    moduleWorker: Boolean(result && result.moduleWorker && result.moduleWorker.ok),
    wasm: Boolean(result && result.wasm && result.wasm.validate),
    wasmSimd: Boolean(result && result.wasm && result.wasm.simdSupported),
  };
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function bundleSpikeMain() {
  // Bundle into dist-electron: git-ignored and already excluded from ESLint,
  // so a spike run never leaves a lintable generated file behind.
  const outDir = path.join(root, "dist-electron", "vizzy-host-spike");
  fs.mkdirSync(outDir, { recursive: true });
  const outfile = path.join(outDir, "spike-main.cjs");
  await build({
    entryPoints: [path.join(root, "electron", "vizzy-host", "spike-main.ts")],
    outfile,
    bundle: true,
    platform: "node",
    format: "cjs",
    target: "node22",
    external: ["electron"],
    sourcemap: "inline",
    logLevel: "silent",
  });
  return outfile;
}

async function runMode(mainFile, mode) {
  const startedAt = Date.now();
  // Disposable profile, kept out of the repository so `npm run lint` never
  // walks Chromium's cache files.
  const userData = path.join(os.tmpdir(), "camxora-vizzy-host-spike", mode);
  fs.rmSync(userData, { recursive: true, force: true });

  const app = await electron.launch({
    args: [mainFile],
    cwd: root,
    env: {
      ...process.env,
      VIZZY_SPIKE_MODE: mode,
      VIZZY_SPIKE_PAGE_ROOT: pageRoot,
      VIZZY_SPIKE_USER_DATA: userData,
    },
  });

  let envelope = null;
  try {
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      envelope = await app.evaluate(() => globalThis.__vizzySpike ?? null);
      if (envelope && envelope.status !== "running") break;
      await delay(200);
    }
  } finally {
    await app.close().catch(() => undefined);
  }

  if (!envelope || envelope.status === "running") {
    envelope = {
      status: "error",
      mode,
      url: envelope ? envelope.url : "",
      probeError: "timed out waiting for the page probe",
      result: null,
      versions: envelope ? envelope.versions : null,
    };
  }

  const result = envelope.result ?? null;
  return {
    mode,
    status: envelope.status,
    url: envelope.url,
    elapsedMs: Date.now() - startedAt,
    versions: envelope.versions ?? null,
    probeError: envelope.probeError ?? null,
    checks: summarize(envelope),
    headers: result ? result.responseHeaders : null,
    gpu: result && result.webgl2 ? result.webgl2.unmaskedRenderer ?? result.webgl2.renderer : null,
    workerReply: result ? result.worker : null,
    moduleWorkerReply: result ? result.moduleWorker : null,
    wasm: result ? result.wasm : null,
    page: result ? result.page : null,
    measurements: result,
  };
}

function collectFailures(modeResult) {
  const failures = [];
  if (modeResult.status !== "done") {
    failures.push(`${modeResult.mode}: probe did not finish (${modeResult.probeError ?? modeResult.status})`);
    return failures;
  }
  for (const check of REQUIRED_CHECKS) {
    if (!modeResult.checks[check]) failures.push(`${modeResult.mode}: ${check} failed`);
  }
  const headers = modeResult.headers ?? {};
  if (headers.coop !== "same-origin") failures.push(`${modeResult.mode}: missing COOP header`);
  if (headers.coep !== "require-corp") failures.push(`${modeResult.mode}: missing COEP header`);
  return failures;
}

const mainFile = await bundleSpikeMain();
const results = {};
const failures = [];

for (const mode of modes) {
  try {
    const modeResult = await runMode(mainFile, mode);
    results[mode] = modeResult;
    failures.push(...collectFailures(modeResult));
  } catch (error) {
    results[mode] = {
      mode,
      status: "error",
      url: "",
      elapsedMs: 0,
      probeError: error instanceof Error ? error.message : String(error),
      checks: summarize(null),
      headers: null,
    };
    failures.push(`${mode}: launch failed (${error instanceof Error ? error.message : String(error)})`);
  }
}

const first = Object.values(results)[0];
const report = {
  spike: "vizzy-host",
  checkedAt: new Date().toISOString(),
  host: first
    ? {
        electron: first.versions ? first.versions.electron : null,
        chrome: first.versions ? first.versions.chrome : null,
        node: first.versions ? first.versions.node : null,
        platform: process.platform,
        arch: process.arch,
      }
    : null,
  modes: results,
  requiredChecks: REQUIRED_CHECKS,
  ok: failures.length === 0,
  failures,
};

const json = JSON.stringify(report, null, 2);
console.log(json);

if (outArg) {
  const outPath = path.resolve(root, outArg);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, json + "\n", "utf8");
  console.error(`Wrote ${outPath}`);
}

if (failures.length > 0) {
  console.error(`VIZZY_HOST_SPIKE_FAILED\n- ${failures.join("\n- ")}`);
  process.exit(1);
}

console.error("VIZZY_HOST_SPIKE_OK");
process.exit(0);
