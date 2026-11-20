/**
 * P7 — batch orchestration with NO `/vizzy` route open.
 *
 * Boots the packaged Electron main with dev auth, seeds a saved video template
 * and three 2 s WAV files inside a run folder, then drives the pipeline through
 * IPC exactly like the Music trigger does:
 *   - enqueue two songs with merge on and start the batch,
 *   - assert the queue renders two validated MP4s with the hidden render host
 *     (the visible Vizzy view is never attached),
 *   - assert the merged MP4 with ffprobe,
 *   - assert the Progress "Video pipeline" rows and the honest empty state,
 *   - cancel a third render mid-flight and prove no partial file survives,
 *   - retry that row and assert only it runs.
 *
 * Requires `npm run build` and `npm run vizzy:build` first.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts", "vizzy");
const tempRoot = path.join(root, "artifacts", "pipeline-batch");
const userData = path.join(tempRoot, "user-data");
const templatesDir = path.join(userData, "templates");
const rendersDir = path.join(userData, "renders");
const runDir = path.join(tempRoot, "run");
const outDir = path.join(tempRoot, "out");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(tempRoot, { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });
fs.mkdirSync(runDir, { recursive: true });
fs.mkdirSync(outDir, { recursive: true });

const TEMPLATE_ID = "batch-test-template";
const TEMPLATE_NAME = "Batch Test Template";

function log(value) {
  console.log(JSON.stringify(value));
}

function fail(message) {
  throw new Error(message);
}

function step(name) {
  process.stdout.write(`[pipeline-batch] ${name}\n`);
}

const watchdog = setTimeout(() => {
  console.error("[pipeline-batch] timed out");
  process.exit(1);
}, 1_200_000);
watchdog.unref?.();

/** 2 s mono 16-bit WAV: the editor decodes this like a Suno download. */
function writeWav(filePath, seconds = 2, rate = 44_100, hz = 220) {
  const samples = Math.round(seconds * rate);
  const data = Buffer.alloc(samples * 2);
  for (let index = 0; index < samples; index += 1) {
    const value = Math.round(
      Math.sin((2 * Math.PI * hz * index) / rate) * 0.25 * 0x7fff,
    );
    data.writeInt16LE(value, index * 2);
  }
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(rate, 24);
  header.writeUInt32LE(rate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(data.length, 40);
  fs.writeFileSync(filePath, Buffer.concat([header, data]));
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
    videoCodec: video?.codec_name ?? null,
    width: video?.width ?? null,
    height: video?.height ?? null,
    audioCodec: audio?.codec_name ?? null,
    frames: Number(video?.nb_frames ?? 0),
  };
}

/** Seed a saved template exactly as "Save as video template" writes one. */
const fixture = path.join(root, "tests", "fixtures", "vizzy", "trap-motion.camxora-vizzy.json");
const templateDir = path.join(templatesDir, TEMPLATE_ID);
fs.mkdirSync(templateDir, { recursive: true });
fs.copyFileSync(fixture, path.join(templateDir, "template.json"));
fs.writeFileSync(
  path.join(templateDir, "pipeline.json"),
  JSON.stringify(
    {
      schemaVersion: 1,
      name: TEMPLATE_NAME,
      kind: "long",
      project: "template.json",
      output: { width: 320, height: 180, fps: 30 },
      duration: { mode: "audio" },
      bindings: { audio: { mode: "replace" } },
      requirements: { renderer: "vizzy", minVersion: "2.0.0", features: [] },
      createdAt: new Date().toISOString(),
    },
    null,
    2,
  ) + "\n",
);

writeWav(path.join(runDir, "1. Night Drive.wav"), 2, 44_100, 220);
writeWav(path.join(runDir, "2. Dawn Chorus.wav"), 2, 44_100, 330);
writeWav(path.join(runDir, "3. Solo Track.wav"), 2, 44_100, 440);

function mp4s(dir) {
  try {
    return fs
      .readdirSync(dir)
      .filter((name) => name.endsWith(".mp4"))
      .sort();
  } catch {
    return [];
  }
}

/**
 * Minimal platform API fixture: the Progress page must load its own rows so the
 * screenshots show a healthy section next to the video pipeline, not an error.
 */
const apiServer = http.createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://127.0.0.1");
  const send = (body) => {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(body));
  };
  if (url.pathname.endsWith("/users/me")) {
    return send({
      id: "user-1",
      email: "dev@camxora.local",
      email_confirmed: true,
      display_name: "Development",
      credit_balance: 500,
      channel_profile_count: 1,
      onboarding_paid: true,
      desktop_access: true,
    });
  }
  if (url.pathname.endsWith("/settings")) return send({ image_source_mode: "auto" });
  if (url.pathname.endsWith("/progress")) {
    return send({ rows: [], summary: "No runs yet.", updated_at: "" });
  }
  if (url.pathname.endsWith("/music/downloads/pending")) return send({ items: [] });
  return send({});
});
await new Promise((resolve) => apiServer.listen(0, "127.0.0.1", resolve));
const apiPort = apiServer.address().port;

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_E2E: "1",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_API_BASE_URL: `http://127.0.0.1:${apiPort}/api/v3`,
  },
});

async function poll(fn, label, timeoutMs = 120_000, intervalMs = 300) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    last = await fn();
    if (last) return last;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  fail(`Timed out waiting for ${label} (last: ${JSON.stringify(last)})`);
}

function snapshot(window) {
  return window.evaluate(async () => window.camxora.pipeline.list());
}

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.getByRole("link", { name: "Progress" }).click();
  await window.getByTestId("video-pipeline").waitFor({ timeout: 20_000 });
  await window.getByTestId("pipeline-empty").waitFor({ timeout: 20_000 });
  const emptyText = await window.getByTestId("pipeline-empty").innerText();
  if (!/No video renders yet/i.test(emptyText)) fail(`Unexpected empty state: ${emptyText}`);
  if (!/Video \(16:9\)/i.test(emptyText) || !/Music/i.test(emptyText)) {
    fail("The empty state must point at Music");
  }
  step("empty state verified");

  // --- Enqueue two songs with merge, no /vizzy route ---------------------
  const enqueued = await window.evaluate(
    async (request) => window.camxora.pipeline.enqueue(request),
    {
      batchId: "batch-main",
      outputDir: outDir,
      merge: true,
      mergeName: "batch-main-merged",
      jobs: [
        {
          branch: "long",
          templateId: TEMPLATE_ID,
          audioDir: runDir,
          audioBranch: "ok",
          title: "Night Drive",
          album: "Night",
        },
        {
          branch: "long",
          templateId: TEMPLATE_ID,
          audioDir: runDir,
          audioBranch: "ok",
          title: "Dawn Chorus",
          album: "Dawn",
        },
      ],
    },
  );
  if (!enqueued.ok) fail(`pipeline:enqueue failed: ${enqueued.error.message}`);
  if (enqueued.data.created !== 2) {
    fail(`Expected 2 queued rows, got ${JSON.stringify(enqueued.data)}`);
  }

  const vizzyState = await window.evaluate(async () => window.camxora.vizzy.state());
  if (!vizzyState.ok) fail("vizzy:state failed before the batch");
  if (vizzyState.data.attached) fail("The visible Vizzy editor must not be attached");

  const startedAt = Date.now();
  const started = await window.evaluate(async () => window.camxora.pipeline.start());
  if (!started.ok || !started.data.started) fail(`pipeline:start failed: ${JSON.stringify(started)}`);

  // The Progress rows come from the durable queue, so they appear immediately.
  await poll(
    async () => (await window.getByTestId("pipeline-row").count()) === 2,
    "the Progress pipeline rows",
    30_000,
  );
  await window.getByTestId("video-pipeline").scrollIntoViewIfNeeded();
  await window.waitForTimeout(250);
  await window.screenshot({ path: path.join(artifacts, "batch-progress.png") });
  step("progress rows visible");

  const finished = await poll(
    async () => {
      const response = await snapshot(window);
      if (!response.ok) return null;
      const { running, jobs } = response.data;
      const terminal = jobs.every(
        (job) => job.status === "done" || job.status === "failed" || job.status === "cancelled",
      );
      return !running && terminal && jobs.length >= 2 ? response.data : null;
    },
    "the batch to finish",
    600_000,
    400,
  );
  const batchMs = Date.now() - startedAt;

  const failedRows = finished.jobs.filter((job) => job.status !== "done");
  if (failedRows.length > 0) {
    fail(`Every row must be done, got ${JSON.stringify(failedRows.map((job) => [job.title, job.status, job.error]))}`);
  }
  const runningVizzy = await window.evaluate(async () => window.camxora.vizzy.state());
  if (!runningVizzy.ok) fail("vizzy:state failed after the batch");
  if (runningVizzy.data.attached) fail("The batch must not attach the visible editor");
  step(`batch finished in ${batchMs} ms`);

  // --- Two validated MP4s -------------------------------------------------
  const renders = mp4s(rendersDir);
  if (renders.length !== 2) fail(`Expected two renders, got ${JSON.stringify(renders)}`);
  const probes = renders.map((name) => ({ name, ...ffprobe(path.join(rendersDir, name)) }));
  for (const probe of probes) {
    if (probe.videoCodec !== "h264") fail(`${probe.name}: expected h264, got ${probe.videoCodec}`);
    if (probe.audioCodec !== "aac") fail(`${probe.name}: expected aac, got ${probe.audioCodec}`);
    if (probe.width !== 320 || probe.height !== 180) {
      fail(`${probe.name}: expected 320x180, got ${probe.width}x${probe.height}`);
    }
    if (!(probe.duration > 1.6 && probe.duration < 2.6)) {
      fail(`${probe.name}: expected ~2 s, ffprobe says ${probe.duration}`);
    }
    if (!(probe.frames >= 55 && probe.frames <= 66)) {
      fail(`${probe.name}: expected ~60 frames, ffprobe says ${probe.frames}`);
    }
  }
  // Each row points at a real file the Progress panel can reveal.
  for (const job of finished.jobs) {
    if (!job.output || !fs.existsSync(job.output)) fail(`Row ${job.title} has no output file`);
  }
  step("two renders probed");

  // --- The merged long-form file -----------------------------------------
  const batch = finished.batches.find((item) => item.batchId === "batch-main");
  if (!batch) fail("The batch record is missing");
  if (!batch.mergedOutput) fail(`Expected a merged output: ${JSON.stringify(batch)}`);
  if (!fs.existsSync(batch.mergedOutput)) fail(`Merged file missing: ${batch.mergedOutput}`);
  if (path.dirname(batch.mergedOutput) !== outDir) {
    fail(`Merged file must live in the run folder, got ${batch.mergedOutput}`);
  }
  const mergedProbe = ffprobe(batch.mergedOutput);
  if (mergedProbe.videoCodec !== "h264") fail(`Merged: expected h264, got ${mergedProbe.videoCodec}`);
  if (!(mergedProbe.duration > 3.4 && mergedProbe.duration < 5.2)) {
    fail(`Merged: expected ~4 s, ffprobe says ${mergedProbe.duration}`);
  }
  step("merged file probed");

  // --- Progress reflects the durable queue --------------------------------
  await poll(
    async () => {
      const statuses = await window
        .locator('[data-testid="pipeline-row"]')
        .evaluateAll((rows) => rows.map((row) => row.getAttribute("data-status")));
      return statuses.length === 2 && statuses.every((status) => status === "done")
        ? statuses
        : null;
    },
    "the Progress rows to show Done",
    60_000,
);
  await window.getByTestId("pipeline-merged-reveal").waitFor({ timeout: 20_000 });
  await window.getByTestId("video-pipeline").scrollIntoViewIfNeeded();
  await window.waitForTimeout(250);
  await window.screenshot({ path: path.join(artifacts, "batch-complete.png") });
  step("progress shows done + merged");

  // --- Cancel a third render: no partial file ----------------------------
  const beforeCancel = mp4s(rendersDir).length;
  const cancelEnqueue = await window.evaluate(
    async (request) => window.camxora.pipeline.enqueue(request),
    {
      batchId: "batch-cancel",
      outputDir: outDir,
      merge: false,
      jobs: [
        {
          branch: "long",
          templateId: TEMPLATE_ID,
          audioDir: runDir,
          audioBranch: "ok",
          title: "Solo Track",
        },
      ],
    },
  );
  if (!cancelEnqueue.ok) fail(`cancel enqueue failed: ${cancelEnqueue.error.message}`);
  if (cancelEnqueue.data.created !== 1) fail("Expected the cancel row to be queued");

  const cancelStart = await window.evaluate(async () => window.camxora.pipeline.start());
  if (!cancelStart.ok) fail(`cancel start failed: ${cancelStart.error.message}`);
  // Cancel through the real Progress control, not only through IPC.
  const cancelButton = window.getByTestId("pipeline-cancel-batch");
  await cancelButton.waitFor({ timeout: 120_000 });
  await poll(
    async () => {
      const response = await snapshot(window);
      if (!response.ok) return null;
      const job = response.data.jobs.find((item) => item.batchId === "batch-cancel");
      return job && job.status !== "queued" ? job : null;
    },
    "the cancel row to start",
    120_000,
    100,
  );
  await cancelButton.click();
  const afterCancel = await poll(
    async () => {
      const response = await snapshot(window);
      if (!response.ok) return null;
      const job = response.data.jobs.find((item) => item.batchId === "batch-cancel");
      return job && job.status === "cancelled" ? response.data : null;
    },
    "the cancelled row",
    120_000,
    200,
  );
  const cancelJob = afterCancel.jobs.find((item) => item.batchId === "batch-cancel");
  if (cancelJob?.output) fail("A cancelled row must not claim an output");
  const afterCancelFiles = mp4s(rendersDir).length;
  if (afterCancelFiles !== beforeCancel) {
    fail(`A cancelled render left a file behind (${beforeCancel} -> ${afterCancelFiles})`);
  }
  step("cancel left no partial output");

  // --- Retry runs only the failed/cancelled row --------------------------
  const retryButton = window.getByTestId("pipeline-retry");
  await retryButton.waitFor({ timeout: 60_000 });
  await retryButton.click();
  const retriedDone = await poll(
    async () => {
      const response = await snapshot(window);
      if (!response.ok) return null;
      const jobs = response.data.jobs.filter((item) => item.batchId === "batch-cancel");
      const queued = jobs.filter((item) => item.status === "queued").length;
      const done = jobs.filter((item) => item.status === "done").length;
      return !response.data.running && queued === 0 && done === 1 ? response.data : null;
    },
    "the retried row to finish",
    600_000,
    400,
  );
  const retriedJobs = retriedDone.jobs.filter((item) => item.batchId === "batch-cancel");
  if (retriedJobs.length !== 2) {
    fail(`Retry must add one row, got ${JSON.stringify(retriedJobs.map((job) => job.status))}`);
  }
  if (mp4s(rendersDir).length !== beforeCancel + 1) {
    fail(`Retry must produce exactly one new file, got ${JSON.stringify(mp4s(rendersDir))}`);
  }
  step("retry rendered only the cancelled row");

  for (const name of ["batch-progress.png", "batch-complete.png"]) {
    if (!fs.existsSync(path.join(artifacts, name))) fail(`Missing screenshot ${name}`);
  }

  log({
    template: { id: TEMPLATE_ID, name: TEMPLATE_NAME },
    batch: { ms: batchMs, rows: finished.jobs.length, merged: batch.mergedOutput },
    renders: probes,
    merged: { path: batch.mergedOutput, probe: mergedProbe },
    cancel: { status: cancelJob?.status, filesBefore: beforeCancel, filesAfter: afterCancelFiles },
    retry: retriedJobs.map((job) => ({ id: job.id, status: job.status, output: job.output })),
    vizzyAttached: runningVizzy.data.attached,
    artifacts,
  });
} finally {
  clearTimeout(watchdog);
  await app.close();
  await new Promise((resolve) => apiServer.close(resolve));
}
