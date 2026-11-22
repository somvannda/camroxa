/**
 * P7 — background auto-video.
 *
 * Boots the packaged Electron main with dev auth, seeds one saved long template,
 * a run folder with two 2 s WAVs and a real 16:9 background, then serves a
 * platform fixture where Video (16:9) and Merge Video are enabled. The main
 * process coordinator, not the page, must:
 *   - find the ready Progress row,
 *   - enqueue both songs with the generated background,
 *   - render them offscreen and merge the branch,
 *   - report its state in `pipeline.list().auto`.
 *
 * No `/vizzy` route is opened and no Music action is clicked.
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
const tempRoot = path.join(root, "artifacts", "auto-video");
const userData = path.join(tempRoot, "user-data");
const templatesDir = path.join(userData, "templates");
const runDir = path.join(tempRoot, "run");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(tempRoot, { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });
fs.mkdirSync(runDir, { recursive: true });

const TEMPLATE_ID = "auto-video-template";
const TEMPLATE_NAME = "Auto Video Template";
const BATCH_ID = "b-auto";
const PROFILE_ID = "p-auto";

function fail(message) {
  throw new Error(message);
}

function step(name) {
  process.stdout.write(`[auto-video] ${name}\n`);
}

const watchdog = setTimeout(() => {
  console.error("[auto-video] timed out");
  process.exit(1);
}, 600_000);
watchdog.unref?.();

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
  return {
    duration: Number(payload.format?.duration ?? 0),
    videoCodec: video?.codec_name ?? null,
    width: video?.width ?? null,
    height: video?.height ?? null,
    frames: Number(video?.nb_frames ?? 0),
  };
}

/* --- inputs ----------------------------------------------------------- */

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
      bindings: {
        audio: { mode: "replace" },
        background: { nodeId: "node_mwn7736t2", fit: "cover" },
      },
      requirements: { renderer: "vizzy", minVersion: "2.0.0", features: [] },
      createdAt: new Date().toISOString(),
    },
    null,
    2,
  ) + "\n",
);

const backgroundPath = path.join(runDir, "background-16x9.png");
fs.writeFileSync(
  backgroundPath,
  Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z1ZkAAAAASUVORK5CYII=",
    "base64",
  ),
);
writeWav(path.join(runDir, "1. Night Drive.wav"), 2, 44_100, 220);
writeWav(path.join(runDir, "2. Dawn Chorus.wav"), 2, 44_100, 330);

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

/* --- platform fixture ------------------------------------------------- */

const now = new Date().toISOString();
const apiServer = http.createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://127.0.0.1");
  const send = (body) => {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(body));
  };
  if (url.pathname.endsWith("/auth/login")) {
    return send({
      access_token: "e2e-token",
      refresh_token: "e2e-refresh",
      expires_in: 3600,
    });
  }
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
  if (url.pathname.endsWith("/settings")) {
    return send({
      autoVideoAfterSuno: true,
      autoReelAfterVideo: false,
      autoMergeAfterVideo: true,
      image_source_mode: "auto",
    });
  }
  if (url.pathname.endsWith("/profiles")) {
    return send([
      {
        id: PROFILE_ID,
        name: "Night Shift",
        folder_name: "Night Shift",
        video_template_id: TEMPLATE_ID,
        reel_template_id: null,
      },
    ]);
  }
  if (url.pathname.endsWith("/music/history")) {
    return send({
      batches: [
        {
          batch_id: BATCH_ID,
          status: "completed",
          song_count: 2,
          ok_album: "Night Drive",
          alt_album: "Night Drive Alt",
          ok_profile_id: PROFILE_ID,
          created_at: now,
          updated_at: now,
          songs: [
            {
              song_id: "song-1",
              batch_index: 0,
              title: "Night Drive",
              album: "Night Drive",
              output_dir_ok: runDir,
              downloaded_ok: true,
            },
            {
              song_id: "song-2",
              batch_index: 1,
              title: "Dawn Chorus",
              album: "Night Drive",
              output_dir_ok: runDir,
              downloaded_ok: true,
            },
          ],
        },
      ],
      summary: "1 batch · 2 songs",
      updated_at: now,
    });
  }
  if (url.pathname.endsWith("/progress")) {
    return send({
      rows: [
        {
          batch: BATCH_ID,
          run_date: "2026-11-20",
          channel: "Night Shift",
          album: "Night Drive",
          status: "Running",
          music: "2/2",
          image: "BG 2/2 · TH 2/2",
          converter: "",
          merge: "",
          youtube: "",
          stage: "Video",
          notes: "",
          updated: now,
          meta: {
            batch_id: BATCH_ID,
            profile_id: PROFILE_ID,
            role: "OK",
            run_dir: runDir,
            background_16x9_path: backgroundPath,
            expected: 2,
            saved: 2,
            download_pending: 0,
            download_ready: 2,
            long_ready: false,
            reel_ready: false,
            pipeline_complete: false,
            updated_at: now,
          },
        },
      ],
      summary: "1 run",
      updated_at: now,
    });
  }
  if (url.pathname.endsWith("/music/downloads/pending")) return send({ items: [] });
  if (url.pathname.endsWith("/credits/operation-costs")) return send([]);
  return send({});
});
await new Promise((resolve) => apiServer.listen(0, "127.0.0.1", resolve));
const apiPort = apiServer.address().port;

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "0",
    CAMXORA_E2E: "1",
    CAMXORA_AUTO_VIDEO: "1",
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

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");

  // The coordinator needs a main-process session; sign in once, then reload so
  // the same window renders the shell via auth.restore.
  const login = await window.evaluate(async () => window.camxora.auth.login("dev@camxora.local", "pw"));
  if (!login.ok || login.data.destination !== "app") {
    fail(`Dev sign-in failed: ${JSON.stringify(login)}`);
  }
  await window.reload();
  await window.waitForLoadState("domcontentloaded");
  await window.getByRole("link", { name: "Progress" }).first().waitFor({ timeout: 20_000 });

  // The coordinator polls every 12 s; the first signed-in tick runs on the next
  // interval.
  const snapshot = await poll(
    async () =>
      window.evaluate(async () => {
        const response = await window.camxora.pipeline.list();
        if (!response.ok) return null;
        const rows = response.data.jobs.filter((job) => job.batchId === "b-auto:long");
        if (rows.length !== 2) return null;
        if (!rows.every((job) => job.status === "done")) return null;
        const batch = response.data.batches.find((item) => item.batchId === "b-auto:long");
        return batch?.mergedOutput ? response.data : null;
      }),
    "two auto-video renders and their merge to finish",
    180_000,
  );

  step("two jobs rendered");
  const jobs = snapshot.jobs.filter((job) => job.batchId === "b-auto:long");
  if (jobs.length !== 2) fail(`Expected two long jobs, got ${jobs.length}`);
  if (!jobs.every((job) => job.backgroundPath === backgroundPath)) {
    fail(`Jobs must carry the generated background: ${JSON.stringify(jobs.map((job) => job.backgroundPath))}`);
  }
  for (const job of jobs) {
    if (!job.output || !fs.existsSync(job.output)) fail(`Missing output for ${job.title}`);
    const probe = ffprobe(job.output);
    if (probe.videoCodec !== "h264") fail(`${job.title}: expected h264, got ${probe.videoCodec}`);
    if (probe.width !== 320 || probe.height !== 180) {
      fail(`${job.title}: expected 320x180, got ${probe.width}x${probe.height}`);
    }
  }

  const batch = snapshot.batches.find((item) => item.batchId === "b-auto:long");
  if (!batch) fail("The long branch batch record is missing");
  if (!batch.mergedOutput) fail(`Expected a merged long output: ${JSON.stringify(batch)}`);
  if (!fs.existsSync(batch.mergedOutput)) fail(`Merged file missing: ${batch.mergedOutput}`);
  const mergedProbe = ffprobe(batch.mergedOutput);
  if (!(mergedProbe.duration > 3.4 && mergedProbe.duration < 5.2)) {
    fail(`Merged: expected ~4 s, ffprobe says ${mergedProbe.duration}`);
  }
  step("merged branch probed");

  if (!snapshot.auto) fail("pipeline.list() must expose the auto-video status");
  if (!["queued", "rendering", "waiting", "idle"].includes(snapshot.auto.state)) {
    fail(`Unexpected auto-video state: ${JSON.stringify(snapshot.auto)}`);
  }

  // The Progress surface reports the same state without a Music click.
  await window.getByRole("link", { name: "Progress" }).first().click();
  await window.getByRole("heading", { name: "Progress" }).waitFor({ timeout: 10_000 });
  await window.waitForTimeout(1_200);
  const autoLine = await window.locator('[data-testid="pipeline-auto-status"]').innerText();
  if (!autoLine.startsWith("Auto-video:")) fail(`Unexpected Progress auto line: ${autoLine}`);
  const videoCells = await window.getByTestId("progress-video").allInnerTexts();
  if (!videoCells.some((text) => /Merged|rendered/i.test(text))) {
    fail(`Operational rows did not show the local render state: ${JSON.stringify(videoCells)}`);
  }
  await window.locator('[data-testid="video-pipeline-status"]').scrollIntoViewIfNeeded();
  await window.waitForTimeout(250);
  await window.screenshot({ path: path.join(artifacts, "auto-video-progress.png") });

  console.log(
    JSON.stringify({
      autoVideo: "ok",
      batchId: batch.batchId,
      jobs: jobs.map((job) => ({ title: job.title, output: job.output, backgroundPath: job.backgroundPath })),
      merged: { path: batch.mergedOutput, probe: mergedProbe },
      status: snapshot.auto,
      renders: mp4s(path.join(userData, "renders")).length,
      artifacts,
    }),
  );
} finally {
  await app.close().catch(() => {});
  apiServer.close();
}
