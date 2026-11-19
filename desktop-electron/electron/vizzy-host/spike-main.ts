/**
 * Standalone main process for the Vizzy host spike.
 *
 * Bundled on demand by `scripts/vizzy-host-spike.mjs` into
 * `artifacts/vizzy-host-spike/spike-main.cjs` and launched with Playwright's
 * `_electron` (or directly with the electron binary). It is not part of the
 * app build and does not touch `electron/main.ts`.
 *
 * Env:
 * - `VIZZY_SPIKE_MODE`   `protocol` (default) | `loopback`
 * - `VIZZY_SPIKE_PAGE_ROOT` directory that contains `index.html`
 * - `VIZZY_SPIKE_USER_DATA` optional throwaway userData directory
 * - `VIZZY_SPIKE_JSON_OUT` optional path to write the result JSON
 * - `VIZZY_SPIKE_EXIT_ON_DONE=1` quit after reporting (direct-launch mode)
 */
import fs from "node:fs";
import path from "node:path";
import { app } from "electron";
import { VIZZY_INDEX_URL } from "./assets";
import { installVizzyProtocol, registerVizzyScheme } from "./protocol";
import { startVizzyLoopbackServer, type VizzyLoopbackServer } from "./server";
import {
  createVizzyHostWindow,
  waitForVizzySpikeResult,
  type VizzySpikeEnvelope,
  type VizzySpikeMode,
} from "./view";

const mode: VizzySpikeMode = process.env.VIZZY_SPIKE_MODE === "loopback" ? "loopback" : "protocol";
const pageRoot = process.env.VIZZY_SPIKE_PAGE_ROOT
  ? path.resolve(process.env.VIZZY_SPIKE_PAGE_ROOT)
  : path.join(process.cwd(), "electron", "vizzy-host", "page");

if (process.env.VIZZY_SPIKE_USER_DATA) {
  app.setPath("userData", path.resolve(process.env.VIZZY_SPIKE_USER_DATA));
}

declare global {
  var __vizzySpike: VizzySpikeEnvelope | undefined;
}

const versions = {
  electron: process.versions.electron ?? "",
  chrome: process.versions.chrome ?? "",
  node: process.versions.node ?? "",
};

function publish(envelope: VizzySpikeEnvelope): void {
  globalThis.__vizzySpike = envelope;
  const out = process.env.VIZZY_SPIKE_JSON_OUT;
  if (out) {
    fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
    fs.writeFileSync(path.resolve(out), JSON.stringify(envelope, null, 2), "utf8");
  }
}

function envelope(
  status: VizzySpikeEnvelope["status"],
  startedAt: number,
  fields: Partial<VizzySpikeEnvelope> = {},
): VizzySpikeEnvelope {
  return {
    status,
    mode,
    url: "",
    pageRoot,
    startedAt,
    elapsedMs: Date.now() - startedAt,
    versions,
    platform: `${process.platform}-${process.arch}`,
    ...fields,
  };
}

async function run(): Promise<void> {
  const startedAt = Date.now();
  publish(envelope("running", startedAt));

  await app.whenReady();

  let server: VizzyLoopbackServer | null = null;
  let pageUrl = VIZZY_INDEX_URL;
  if (mode === "loopback") {
    server = await startVizzyLoopbackServer({ root: pageRoot });
    pageUrl = server.pageUrl;
  } else {
    installVizzyProtocol({ root: pageRoot });
  }
  publish(envelope("running", startedAt, { url: pageUrl }));

  const { window, view } = createVizzyHostWindow({
    url: pageUrl,
    bounds: { x: 0, y: 0, width: 1024, height: 720 },
    title: `Vizzy host spike (${mode})`,
    onCrash: (details) => {
      publish(
        envelope("error", startedAt, {
          url: pageUrl,
          probeError: `renderer gone: ${details.reason} (${details.exitCode})`,
          result: null,
        }),
      );
    },
  });
  window.on("closed", () => {
    void server?.close().catch(() => undefined);
  });

  try {
    await view.webContents.loadURL(pageUrl);
    const result = await waitForVizzySpikeResult(view.webContents);
    const final = envelope(result ? "done" : "error", startedAt, {
      url: pageUrl,
      title: view.webContents.getTitle(),
      result,
      probeError: result ? null : "timed out waiting for window.__vizzySpikeResult",
    });
    publish(final);
    // Machine-readable line for the direct-launch path.
    console.log("VIZZY_SPIKE_RESULT " + JSON.stringify(final));
    if (process.env.VIZZY_SPIKE_EXIT_ON_DONE === "1") app.exit(result?.ok ? 0 : 1);
  } catch (error) {
    const final = envelope("error", startedAt, {
      url: pageUrl,
      result: null,
      probeError: error instanceof Error ? error.message : String(error),
    });
    publish(final);
    console.error("VIZZY_SPIKE_RESULT " + JSON.stringify(final));
    if (process.env.VIZZY_SPIKE_EXIT_ON_DONE === "1") app.exit(1);
  }
}

// The scheme has to be privileged before the app is ready.
if (mode === "protocol") registerVizzyScheme();

void run().catch((error) => {
  console.error("VIZZY_SPIKE_FAILED", error);
  publish(envelope("error", Date.now(), { probeError: String(error), result: null }));
  if (process.env.VIZZY_SPIKE_EXIT_ON_DONE === "1") app.exit(1);
});
