/* global document, HTMLVideoElement */
/**
 * P7 — native export + the Renders panel.
 *
 * Boots the packaged Electron main with dev auth, opens `/vizzy`, loads the
 * Trap Motion fixture through the native open-path flow, then:
 *   - exports a 480x270, 2 s H.264 clip through the shell's Export panel,
 *   - asserts the streamed progress events and a real, ffprobe-readable MP4,
 *   - opens the Renders panel, plays it inline, and deletes it with
 *     confirmation (the file must be gone from disk),
 *   - starts a longer export, cancels it, and proves no partial file is left.
 *
 * Requires `npm run build` and `npm run vizzy:build` first.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts", "vizzy");
const userData = path.join(root, "artifacts", "vizzy-export", "user-data");
const rendersDir = path.join(userData, "renders");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(path.join(root, "artifacts", "vizzy-export"), { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });

const fixture = path.join(root, "tests", "fixtures", "vizzy", "trap-motion.camxora-vizzy.json");

function log(value) {
  console.log(JSON.stringify(value));
}

function fail(message) {
  throw new Error(message);
}

function ffprobe(filePath) {
  const binary = process.env.CAMXORA_FFPROBE_PATH ?? "ffprobe";
  const result = spawnSync(
    binary,
    ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", filePath],
    { encoding: "utf8" },
  );
  if (result.error) fail(`ffprobe could not run (${result.error.message}); set CAMXORA_FFPROBE_PATH`);
  if (result.status !== 0) fail(`ffprobe failed: ${(result.stderr ?? "").trim()}`);
  const payload = JSON.parse(result.stdout);
  const video = payload.streams?.find((stream) => stream.codec_type === "video");
  const audio = payload.streams?.find((stream) => stream.codec_type === "audio");
  return {
    duration: Number(payload.format?.duration ?? 0),
    format: payload.format?.format_name ?? null,
    videoCodec: video?.codec_name ?? null,
    width: video?.width ?? null,
    height: video?.height ?? null,
    audioCodec: audio?.codec_name ?? null,
    frames: Number(video?.nb_frames ?? 0),
  };
}

function rendersOnDisk() {
  try {
    return fs.readdirSync(rendersDir).sort();
  } catch {
    return [];
  }
}

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_E2E: "1",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_API_BASE_URL: process.env.CAMXORA_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  },
});

async function poll(fn, label, timeoutMs = 60_000, intervalMs = 200) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    last = await fn();
    if (last) return last;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  fail(`Timed out waiting for ${label} (last: ${JSON.stringify(last)})`);
}

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.getByRole("link", { name: "Vizzy" }).click();
  await window.getByRole("button", { name: "Save", exact: true }).waitFor({ timeout: 15_000 });

  const state = await poll(async () => {
    const result = await window.evaluate(async () => window.camxora.vizzy.state());
    return result?.ok && result.data.attached && result.data.ready ? result.data : null;
  }, "the hosted editor to report ready");

  const opened = await window.evaluate(
    async (filePath) => window.camxora.vizzy.openPath(filePath),
    fixture,
  );
  if (!opened.ok) fail(`vizzy:open-path failed: ${opened.error.message}`);

  await window.evaluate(() => {
    window.__vizzyExportEvents = [];
    window.camxora.vizzy.onExportProgress((payload) => window.__vizzyExportEvents.push(payload));
  });

  // --- Export settings panel -------------------------------------------
  await window.getByTestId("vizzy-export-open").click();
  await window.getByTestId("vizzy-export-menu").waitFor({ timeout: 10_000 });
  await window.getByTestId("vizzy-export-width").fill("480");
  await window.getByTestId("vizzy-export-height").fill("270");
  await window.getByTestId("vizzy-export-fps").selectOption("30");
  await window.getByTestId("vizzy-export-format").selectOption("mp4");
  await window.getByTestId("vizzy-export-start").fill("0");
  await window.getByTestId("vizzy-export-end").fill("12");
  await window.screenshot({ path: path.join(artifacts, "export-settings.png") });

  // --- Cancel a long export: nothing may survive ------------------------
  await window.getByTestId("vizzy-export-submit").click();
  await window.getByTestId("vizzy-export-cancel").waitFor({ timeout: 30_000 });
  const cancelProgress = await poll(async () => {
    const events = await window.evaluate(() => window.__vizzyExportEvents);
    return events.find((event) => event.done >= 4) ?? null;
  }, "the cancelled export to report frames");

  await window.getByTestId("vizzy-export-cancel").click();
  await window.getByTestId("vizzy-export-error").waitFor({ timeout: 60_000 });
  const cancelMessage = await window.getByTestId("vizzy-export-error").innerText();
  const afterCancel = rendersOnDisk();
  if (afterCancel.length > 0) {
    fail(`A cancelled export left a file behind: ${JSON.stringify(afterCancel)}`);
  }

  // --- Export the short clip -------------------------------------------
  await window.evaluate(() => {
    window.__vizzyExportEvents = [];
  });
  await window.getByTestId("vizzy-export-width").fill("480");
  await window.getByTestId("vizzy-export-height").fill("270");
  await window.getByTestId("vizzy-export-start").fill("0");
  await window.getByTestId("vizzy-export-end").fill("2");
  const exportStarted = Date.now();
  await window.getByTestId("vizzy-export-submit").click();
  await window.getByTestId("vizzy-export-result").waitFor({ timeout: 180_000 });
  const exportMs = Date.now() - exportStarted;
  const resultText = await window.getByTestId("vizzy-export-result").innerText();

  const events = await window.evaluate(() => window.__vizzyExportEvents);
  const jobEvents = events.filter((event) => event.total > 0 && event.jobId);
  const progressed = jobEvents.filter((event) => event.done > 0 && event.percent > 0);
  const monotonic = jobEvents.every(
    (event, index) => index === 0 || event.done >= jobEvents[index - 1].done,
  );

  const listed = await window.evaluate(async () => window.camxora.vizzy.renders());
  if (!listed.ok) fail(`vizzy:renders failed: ${listed.error.message}`);
  if (listed.data.length !== 1) {
    fail(`Expected exactly one render, got ${JSON.stringify(listed.data)}`);
  }
  const render = listed.data[0];
  const filePath = path.join(rendersDir, render.name);
  if (!fs.existsSync(filePath)) fail(`The render is missing from disk: ${filePath}`);
  const bytes = fs.statSync(filePath).size;
  if (bytes <= 0) fail("The render is empty");
  if (bytes !== render.bytes) fail(`The listed size ${render.bytes} != ${bytes} on disk`);

  const probed = ffprobe(filePath);
  if (probed.videoCodec !== "h264") fail(`Expected h264, got ${probed.videoCodec}`);
  if (probed.width !== 480 || probed.height !== 270) {
    fail(`Expected 480x270, got ${probed.width}x${probed.height}`);
  }
  if (!(probed.duration > 1.6 && probed.duration < 2.4)) {
    fail(`Expected ~2 s, ffprobe says ${probed.duration}`);
  }
  if (!(probed.frames >= 55 && probed.frames <= 65)) {
    fail(`Expected ~60 frames, ffprobe says ${probed.frames}`);
  }

  // --- Renders panel: list, inline play, delete -------------------------
  await window.getByTestId("vizzy-renders-open").click();
  await window.getByTestId("vizzy-renders-panel").waitFor({ timeout: 10_000 });
  const row = window.getByTestId("vizzy-render-row").filter({ hasText: render.name });
  await row.waitFor({ timeout: 10_000 });
  await row.getByTestId("vizzy-render-play").click();
  const video = window.getByTestId("vizzy-render-video");
  await video.waitFor({ timeout: 10_000 });
  const videoSrc = await video.getAttribute("src");
  if (!videoSrc || !videoSrc.startsWith("camxora-media://")) {
    fail(`Inline playback did not use camxora-media://: ${videoSrc}`);
  }
  const videoReady = await poll(
    async () =>
      window.evaluate(() => {
        const element = document.querySelector('[data-testid="vizzy-render-video"]');
        return element instanceof HTMLVideoElement && element.readyState >= 1
          ? { readyState: element.readyState, duration: element.duration }
          : null;
      }),
    "the inline player to load metadata",
    15_000,
    250,
  );
  await window.screenshot({ path: path.join(artifacts, "renders.png") });

  await row.getByTestId("vizzy-render-delete").click();
  const confirm = row.getByTestId("vizzy-render-delete-confirm");
  await confirm.waitFor({ timeout: 5_000 });
  await confirm.click();
  await poll(
    async () => {
      const response = await window.evaluate(async () => window.camxora.vizzy.renders());
      return response.ok && response.data.length === 0 ? true : null;
    },
    "the deleted render to leave the list",
    15_000,
  );
  if (fs.existsSync(filePath)) fail("The deleted render still exists on disk");
  if (rendersOnDisk().length !== 0) fail(`Unexpected files in renders/: ${rendersOnDisk()}`);

  // The panel must not offer a delete for a path outside renders/.
  const traversal = await window.evaluate(async () =>
    window.camxora.vizzy.deleteRender("../export-settings.png"),
  );
  if (traversal.ok && traversal.data.deleted) fail("A traversal delete was accepted");

  log({
    state,
    opened: opened.data,
    cancel: { progress: cancelProgress, message: cancelMessage.trim(), files: afterCancel },
    export: {
      ms: exportMs,
      bytes,
      name: render.name,
      resultText: resultText.replace(/\n+/g, " | "),
      events: jobEvents.length,
      progressed: progressed.length,
      monotonic,
    },
    probe: probed,
    inline: { src: videoSrc, ...videoReady },
    traversal,
    artifacts,
  });

  if (jobEvents.length < 10) fail(`Expected streaming progress events, got ${jobEvents.length}`);
  if (progressed.length < 3) fail(`Expected intermediate progress, got ${progressed.length}`);
  if (!monotonic) fail("Export progress went backwards");
  if (!resultText.includes(render.name)) fail("The result panel does not name the render");
} finally {
  await app.close();
}
