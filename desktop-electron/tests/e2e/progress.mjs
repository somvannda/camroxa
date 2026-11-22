/* global document, window */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/**
 * P3 Progress acceptance against a fixture platform API.
 *
 * Covers PG-T1…PG-T8: filters, stat counts, the operational table, row detail,
 * manual asset recovery (with real files on disk), the download queue, empty,
 * stale-after-error and 200-row rendering.
 */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

const RUN_READY = path.join(artifacts, "progress-run-ready");
const RUN_MISSING = path.join(artifacts, "progress-run-missing");
fs.rmSync(RUN_READY, { recursive: true, force: true });
fs.rmSync(RUN_MISSING, { recursive: true, force: true });
fs.mkdirSync(RUN_READY, { recursive: true });

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);
for (const name of [
  "background-16x9.png",
  "background-9x16.png",
  "thumbnail-16x9.png",
  "thumbnail-9x16.png",
]) {
  fs.writeFileSync(path.join(RUN_READY, name), PNG);
}

const ME = {
  id: "user-1",
  email: "operator@example.com",
  email_confirmed: true,
  display_name: "Night Operator",
  avatar_url: null,
  role: "user",
  status: "active",
  suspension_reason: null,
  credit_balance: 500,
  plan_name: "studio-monthly",
  music_credits_remaining: null,
  music_credits_limit: null,
  credits_burned: null,
  profile_allowance: 5,
  profile_addon_slots: 1,
  profile_addon_pending: 0,
  effective_profile_allowance: 6,
  effective_quota_channels: null,
  channel_profile_count: 1,
  onboarding_paid: true,
  desktop_access: true,
  products: ["desktop"],
  pending_verification_code: null,
  verification_code_expires_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: null,
};

const STATS = {
  credits_spent: 10,
  credits_remaining: 490,
  credits_total: 500,
  songs_generated: 4,
  songs_remaining: 116,
  songs_quota: 120,
  images_remaining: null,
  images_quota: null,
  drafts_remaining: null,
  drafts_quota: null,
  images_generated: 2,
  studio_exports: 1,
  manual_exports: 0,
  youtube_uploads: 0,
  videos_generated: 1,
  videos_uploaded: 0,
  usage_by_day: [
    { date: "2026-11-19", songs: 4, images: 2, videos: 1, studio_exports: 1, manual_exports: 0, youtube_uploads: 0 },
  ],
  recent_activity: [],
};

function progressRow(index, overrides = {}) {
  const batch = `NS-26${String(index).padStart(2, "0")}`;
  const base = {
    batch,
    run_date: "2026-11-19",
    channel: "Night Shift",
    album: "Night Drive",
    status: "running",
    music: "12/12",
    image: "4/4",
    converter: "",
    merge: "",
    youtube: "",
    stage: "music",
    notes: "",
    updated: "just now",
    meta: {
      batch_id: batch,
      profile_id: "profile-1",
      role: "OK",
      run_dir: null,
      source_mode: "manual",
      background_16x9_path: null,
      background_9x16_path: null,
      thumbnail_16x9_path: null,
      thumbnail_9x16_path: null,
      expected: 12,
      saved: 12,
      download_pending: 0,
      download_ready: 12,
      bg_ready: 4,
      bg_total: 4,
      th_ready: 4,
      th_total: 4,
      bg_status: "READY",
      th_status: "READY",
      youtube_status: "",
      youtube_url: null,
      youtube_success: 0,
      youtube_pending: 0,
      youtube_failed: 0,
      long_ready: false,
      reel_ready: false,
      pipeline_complete: false,
      auto_upload_youtube: null,
      updated_at: "2026-11-19T10:00:00Z",
      draft_failed_song_ids: [],
      suno_failed_song_ids: [],
    },
  };
  return {
    ...base,
    ...overrides,
    meta: { ...base.meta, ...(overrides.meta ?? {}) },
  };
}

function successRows() {
  return [
    progressRow(1, {
      stage: "music",
      status: "running",
      music: "6/12",
      meta: {
        run_dir: RUN_MISSING,
        saved: 6,
        download_pending: 5,
        download_ready: 1,
        draft_failed_song_ids: ["song-draft-1"],
        suno_failed_song_ids: ["song-suno-1"],
      },
    }),
    progressRow(2, {
      stage: "converter",
      status: "converting",
      converter: "Long 4/8",
      image: "4/4",
    }),
    progressRow(3, {
      stage: "image",
      status: "waiting",
      run_dir: RUN_MISSING,
      image: "0/4",
      meta: { run_dir: RUN_MISSING, bg_ready: 0, th_ready: 0, bg_status: "PENDING", th_status: "PENDING" },
    }),
    progressRow(4, {
      stage: "image",
      status: "waiting",
      run_dir: RUN_READY,
      image: "4/4",
      meta: {
        run_dir: RUN_READY,
        background_16x9_path: path.join(RUN_READY, "background-16x9.png"),
        background_9x16_path: path.join(RUN_READY, "background-9x16.png"),
        thumbnail_16x9_path: path.join(RUN_READY, "thumbnail-16x9.png"),
        thumbnail_9x16_path: path.join(RUN_READY, "thumbnail-9x16.png"),
      },
    }),
    progressRow(5, {
      stage: "done",
      status: "completed",
      meta: { long_ready: true, reel_ready: true, pipeline_complete: true },
    }),
    progressRow(6, {
      stage: "error",
      status: "failed",
      notes: "Merge failed: ffmpeg exited with code 1",
      converter: "Long 4/8",
      meta: { long_ready: false },
    }),
    progressRow(7, {
      stage: "youtube",
      status: "uploading",
      youtube: "Uploading",
      meta: {
        youtube_pending: 1,
        youtube_status: "UPLOADING",
        youtube_url: "https://youtube.com/watch?v=e2e",
      },
    }),
  ];
}

const MP3_BYTES = Buffer.concat([Buffer.from("ID3"), Buffer.alloc(2048, 7)]);

function downloadsFor(root, origin) {
  return {
    items: [
      {
        task_id: "task-1",
        song_id: "song-1",
        batch_id: "NS-2601",
        title: "Night Drive",
        track_number: 2,
        primary: {
          download_url: `${origin}/downloads/1.mp3`,
          downloaded: false,
          output_dir: root,
          target_path: path.join(root, "01 Night Drive.mp3"),
        },
        secondary: {
          download_url: null,
          downloaded: false,
          output_dir: root,
          target_path: path.join(root, "02 Night Drive.mp3"),
        },
      },
      {
        task_id: "task-2",
        song_id: "song-2",
        batch_id: "NS-2602",
        title: "After Hours",
        track_number: 1,
        primary: {
          download_url: `${origin}/downloads/2.mp3`,
          downloaded: true,
          output_dir: root,
          target_path: path.join(root, "01 After Hours.mp3"),
        },
      },
    ],
  };
}

const PROFILE = {
  id: "profile-1",
  user_id: "user-1",
  name: "Night Shift",
  folder_name: "night-shift",
  run_prefix: "NS",
  logo_path: null,
  video_template_id: null,
  reel_template_id: null,
  output_resolution: "1920x1080",
  image_config: { mode: "manual" },
  youtube_config: { visibility: "public" },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-02-01T00:00:00Z",
};

const LICENSE = {
  plan_type: "studio-monthly",
  profile_allowance: 5,
  profile_addon_slots: 1,
  profile_addon_pending: 0,
  effective_profile_allowance: 6,
  monthly_song_quota: 120,
  songs_remaining: 116,
  monthly_image_quota: 40,
  images_remaining: 38,
  wallet_balance: 490,
  expiration_date: "2026-12-31",
};

function json(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

function startApi(routes) {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const route = `${request.method} ${url.pathname.replace(/^\/api\/v3/, "")}`;
    const handler = routes[route];
    if (!handler) {
      json(response, 404, { detail: "Not found" });
      return;
    }
    handler(request, response, url);
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, port: server.address().port });
    });
  });
}

const baseRoutes = {
  "POST /auth/login": (_request, response) =>
    json(response, 200, {
      access_token: "e2e-token",
      refresh_token: "e2e-refresh",
      expires_in: 3600,
    }),
  "GET /users/me": (_request, response) => json(response, 200, ME),
  "GET /stats/dashboard": (_request, response) => json(response, 200, STATS),
  "GET /profiles": (_request, response) => json(response, 200, [PROFILE]),
  "GET /licenses/validate": (_request, response) => json(response, 200, LICENSE),
  "GET /settings": (_request, response) =>
    json(response, 200, {
      imageSourceMode: "manual",
      sunoOutputDir: RUN_READY,
      downloadsDir: RUN_READY,
    }),
};

async function openApp(name, apiPort) {
  const userData = path.join(artifacts, `e2e-progress-${name}`);
  fs.rmSync(userData, { recursive: true, force: true });
  const app = await electron.launch({
    args: ["dist-electron/main.cjs"],
    cwd: root,
    env: {
      ...process.env,
      CAMXORA_DEV_AUTH: "0",
      CAMXORA_E2E: "1",
      CAMXORA_USER_DATA_DIR: userData,
      CAMXORA_API_BASE_URL: `http://127.0.0.1:${apiPort}/api/v3`,
    },
  });
  const page = await app.firstWindow();
  await page.waitForLoadState("domcontentloaded");
  await page.locator("#email").fill("operator@example.com");
  await page.locator("#password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForTimeout(500);
  const onboarding = page.getByRole("button", { name: "Open studio anyway" });
  if (await onboarding.isVisible().catch(() => false)) {
    await onboarding.click();
  }
  await page.getByRole("heading", { name: "Weekly Usage" }).waitFor({ timeout: 15000 });
  await page.getByRole("link", { name: "Progress" }).click();
  await page.getByRole("heading", { name: "Progress" }).waitFor({ timeout: 10000 });
  return { app, page };
}

async function resize(app, page, width, height) {
  await app.evaluate(
    async ({ BrowserWindow }, size) => {
      const window = BrowserWindow.getAllWindows()[0];
      if (window) window.setSize(size.width, size.height);
    },
    { width, height },
  );
  await page.waitForTimeout(250);
}

async function capture(app, page, file) {
  await resize(app, page, 1440, 900);
  await page.screenshot({ path: path.join(artifacts, `${file}-1440.png`), fullPage: true });
  await resize(app, page, 1280, 800);
  await page.screenshot({ path: path.join(artifacts, `${file}-1280.png`), fullPage: true });
  await resize(app, page, 1440, 900);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function chooseOption(page, target, value) {
  const trigger = typeof target === "string" ? page.locator(target) : target;
  await trigger.click();
  await page.locator(`[data-value="${value}"]`).click();
}

async function stat(page, name) {
  return page.locator(`[data-testid="progress-stat-${name}"]`).innerText();
}

async function successWithManualRecovery() {
  let progressRequests = 0;
  const syncBodies = [];
  const menuCalls = [];
  const recoveryDir = path.join(artifacts, "e2e-progress-success", "recovered");
  fs.rmSync(recoveryDir, { recursive: true, force: true });
  let recoveryUrl = "";
  const rows = successRows();
  let pendingDownloads = { items: [] };
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /progress": (_request, response) => {
      progressRequests += 1;
      json(response, 200, {
        rows,
        summary: "Operational scan ready",
        updated_at: "2026-11-19T10:00:00Z",
      });
    },
    "GET /music/downloads/pending": (_request, response) => json(response, 200, pendingDownloads),
    "POST /music/downloads/sync": (_request, response) => json(response, 200, { updated: 0 }),
    "GET /downloads/1.mp3": (_request, response) => {
      response.writeHead(200, {
        "content-type": "audio/mpeg",
        "content-length": MP3_BYTES.length,
      });
      response.end(MP3_BYTES);
    },
    "POST /image-jobs/sync-manual": (request, response) => {
      let body = "";
      request.on("data", (chunk) => {
        body += chunk;
      });
      request.on("end", () => {
        syncBodies.push(JSON.parse(body || "{}"));
        json(response, 200, { updated: 1 });
      });
    },
    "POST /image-jobs/retry": (request, response) => {
      menuCalls.push("image-retry");
      json(response, 200, { updated: 1 });
    },
    "POST /music/downloads/batch-redownload-plan": (_request, response) => {
      menuCalls.push("redownload-plan");
      json(response, 200, {
        items: [
          {
            task_id: "recover-1",
            title: "Recovered",
            download_url: recoveryUrl,
            fallback_download_url: null,
            target_path: path.join(recoveryDir, "1. Recovered.mp3"),
          },
        ],
      });
    },
    "POST /batches/NS-2601/songs/song-draft-1/retry-draft": (_request, response) => {
      menuCalls.push("retry-draft");
      json(response, 202, { batch_id: "NS-2601", song_id: "song-draft-1", status: "retrying" });
    },
    "POST /batches/NS-2601/songs/song-suno-1/retry-suno": (_request, response) => {
      menuCalls.push("retry-suno");
      json(response, 202, { batch_id: "NS-2601", song_id: "song-suno-1", status: "retrying" });
    },
    "POST /progress/sync-local": (_request, response) => {
      menuCalls.push("sync-local");
      json(response, 200, { updated: 1 });
    },
  });
  const downloadsRoot = path.join(artifacts, "e2e-progress-success", "downloads");
  pendingDownloads = downloadsFor(downloadsRoot, `http://127.0.0.1:${port}`);
  recoveryUrl = `http://127.0.0.1:${port}/downloads/1.mp3`;

  const { app, page } = await openApp("success", port);
  try {
    await page.locator('[data-testid="progress-row"]').first().waitFor({ timeout: 10000 });

    assert(await page.locator('[data-testid="progress-manual-notice"]').isVisible(), "Manual notice missing");
    const mainText = await page.locator("main").innerText();
    assert(!mainText.includes("operator@example.com"), "Progress must not render the account email");
    assert(!mainText.includes("e2e-token"), "Progress must not render the access token");
    const headers = await page.locator("thead th").allInnerTexts();
    for (const header of [
      "Run Date",
      "Channel",
      "Album",
      "Stage",
      "Progress",
      "Music",
      "Image",
      "Video (Render)",
      "Merge",
      "YouTube",
      "Updated",
    ]) {
      assert(headers.includes(header), `Missing column ${header}`);
    }

    assert((await stat(page, "active")).includes("5"), "Active stat must be 5");
    assert((await stat(page, "video")).includes("1"), "Converter/merge stat must be 1");
    assert((await stat(page, "waiting")).includes("1"), "Waiting stat must be 1");
    assert((await stat(page, "failed")).includes("1"), "Failed stat must be 1");

    const rowsLocator = page.locator('[data-testid="progress-row"]');
    const targetRow = rowsLocator.filter({ hasText: "NS-2601" }).first();
    await targetRow.waitFor({ timeout: 10_000 });

    // Right-click menu keeps the operational actions reachable from a row.
    await targetRow.click({ button: "right" });
    const rowMenu = page.getByTestId("progress-row-menu");
    await rowMenu.waitFor({ timeout: 5_000 });
    const menuText = await rowMenu.innerText();
    for (const label of [
      "Open run folder",
      "Reveal rendered video",
      "Copy batch ID",
      "Copy album",
      "Retry images",
      "Cancel video render",
      "Continue video render",
      "Retry failed render",
      "Force regenerate MP4s",
      "Repair missing/broken MP4s",
      "Change run folder & resume",
      "Upload to YouTube",
    ]) {
      assert(menuText.includes(label), `Row menu missing "${label}"`);
    }
    await rowMenu.getByRole("menuitem", { name: "Copy batch ID" }).click();
    await rowMenu.waitFor({ state: "detached", timeout: 5_000 });

    const openRowMenu = async () => {
      await targetRow.click({ button: "right" });
      await rowMenu.waitFor({ timeout: 5_000 });
      return rowMenu;
    };

    await (
      await openRowMenu()
    )
      .getByRole("menuitem", { name: /Retry failed drafts/ })
      .click();
    await page.waitForTimeout(500);
    assert(menuCalls.includes("retry-draft"), "Retry failed drafts did not call the batch endpoint");

    await (
      await openRowMenu()
    )
      .getByRole("menuitem", { name: /Retry failed Suno/ })
      .click();
    await page.waitForTimeout(500);
    assert(menuCalls.includes("retry-suno"), "Retry failed Suno did not call the batch endpoint");

    await (await openRowMenu()).getByRole("menuitem", { name: "Retry images" }).click();
    await page.waitForTimeout(500);
    assert(menuCalls.includes("image-retry"), "Retry images did not call the image endpoint");

    await (
      await openRowMenu()
    )
      .getByRole("menuitem", { name: /Download missing MP3s/ })
      .click();
    await page.waitForTimeout(800);
    assert(
      menuCalls.includes("redownload-plan") && menuCalls.includes("sync-local"),
      "Download missing MP3s did not plan and persist the recovery",
    );
    const recoveredFile = path.join(recoveryDir, "1. Recovered.mp3");
    assert(fs.existsSync(recoveredFile), "Download missing MP3s did not write the file");
    assert(fs.statSync(recoveredFile).size === MP3_BYTES.length, "Recovered MP3 has the wrong size");

    assert((await rowsLocator.count()) === 7, "Expected seven operational rows");

    // The main-process coordinator polls independently, so wait for its first
    // snapshot before reading the download count.
    await page.waitForFunction(
      () => document.querySelectorAll('[data-testid="progress-download-row"]').length === 2,
      undefined,
      { timeout: 30000 },
    );
    const downloadRows = page.locator('[data-testid="progress-download-row"]');
    assert((await downloadRows.count()) === 2, "Download queue must show two targets");
    let downloadText = await page.locator('[data-testid="progress-download-card"]').innerText();
    assert(downloadText.includes("Night Drive") && downloadText.includes("Night Shift"), "Download identity missing");
    assert(downloadText.includes("Saving to"), "Download root is not shown");
    assert(!downloadText.includes("P4"), "Placeholder copy must be gone");
    assert((await page.getByRole("button", { name: "Pause" }).count()) === 1, "Pause control missing");

    // The coordinator downloads the real file; the target with no URL is a
    // specific failure rather than a silent skip.
    const downloadTarget = path.join(downloadsRoot, "01 Night Drive.mp3");
    await page.waitForFunction(
      () => document.querySelector('[data-testid="progress-download-card"]')?.textContent?.includes("Done"),
      undefined,
      { timeout: 30000 },
    );
    await page.waitForTimeout(200);
    assert(fs.existsSync(downloadTarget), "The coordinator did not write the MP3");
    assert(fs.statSync(downloadTarget).size === MP3_BYTES.length, "The downloaded file has the wrong size");
    assert(
      !fs.readdirSync(downloadsRoot).some((name) => name.includes(".camxora-part-")),
      "A partial file was left behind",
    );
    downloadText = await page.locator('[data-testid="progress-download-card"]').innerText();
    assert(downloadText.includes("Done"), "Download state did not reach Done");
    assert(
      downloadText.includes("The server did not provide a download link"),
      "A missing URL must be reported specifically",
    );
    assert(
      await page.getByRole("button", { name: "Retry" }).first().isDisabled(),
      "Retry must stay disabled when there is nothing to retry",
    );
    await page.locator('[data-testid="progress-download-card"]').scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await capture(app, page, "progress-downloads");

    await capture(app, page, "progress-success");

    await resize(app, page, 1440, 900);
    const fit = await page.locator('[data-testid="progress-table-card"] table').evaluate((table) => {
      const scroller = table.parentElement;
      if (!scroller) return { scrollWidth: 0, clientWidth: 0, scrollLeft: 0 };
      scroller.scrollLeft = 0;
      return {
        scrollWidth: scroller.scrollWidth,
        clientWidth: scroller.clientWidth,
        scrollLeft: scroller.scrollLeft,
      };
    });
    assert(
      fit.scrollWidth <= fit.clientWidth + 1,
      `All eleven columns must fit at 1440 (scroll ${fit.scrollWidth} vs ${fit.clientWidth})`,
    );

    // Failed row: stage retry stays disabled and explains why.
    const failedRow = page.locator('[data-testid="progress-row"]', { hasText: "NS-2606" });
    await failedRow.click();
    await page.locator('[data-testid="progress-detail"]').waitFor();
    const retry = page.locator('[data-testid="progress-retry-stage"]');
    assert(await retry.isDisabled(), "Non-image retry must be disabled");
    assert(
      (await retry.getAttribute("title") ?? "").toLowerCase().includes("not available"),
      "Retry must explain why the stage cannot be retried",
    );
    const failureText = await page.locator('[data-testid="progress-detail"]').innerText();
    assert(failureText.includes("Merge failed"), "Failure note missing from detail");
    await page.locator('[aria-label="Close row detail"]').click();

    // Missing manual assets: Continue is disabled and the hint names the files.
    const missingRow = page.locator('[data-testid="progress-row"]', { hasText: "NS-2603" });
    await missingRow.click();
    const manual = page.locator('[data-testid="progress-manual"]');
    await manual.waitFor();
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-testid="progress-manual"]');
      return Boolean(node && node.textContent?.includes("0/4 ready"));
    });
    assert(await page.locator('[data-testid="progress-continue-pipeline"]').isDisabled(), "Continue must be disabled while files are missing");
    assert((await manual.innerText()).includes("Missing BG 16:9"), "Missing file hint absent");
    await page.locator('[aria-label="Close row detail"]').click();

    // Ready manual assets: check files, copy run id, continue pipeline.
    const readyRow = page.locator('[data-testid="progress-row"]', { hasText: "NS-2604" });
    await readyRow.click();
    await page.waitForFunction(() => {
      const node = document.querySelector('[data-testid="progress-manual"]');
      return Boolean(node && node.textContent?.includes("4/4 ready"));
    });
    const continueButton = page.locator('[data-testid="progress-continue-pipeline"]');
    assert(!(await continueButton.isDisabled()), "Continue must be enabled when all files exist");
    assert(
      (await page.getByRole("button", { name: "Open folder" }).count()) >= 1,
      "Run folder action missing",
    );
    assert(
      (await page.getByRole("button", { name: "Reveal" }).count()) >= 1,
      "File reveal action missing",
    );
    await page.getByRole("button", { name: "Copy run id" }).click();
    await page.getByText("Copied", { exact: true }).waitFor({ timeout: 3000 });
    await page.locator('[data-testid="progress-detail"]').scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await capture(app, page, "progress-row-detail");
    await page.locator('[data-testid="progress-manual"]').scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await capture(app, page, "progress-manual");

    await continueButton.click();
    await page.waitForFunction(() =>
      document.body.innerText.includes("Manual assets synced for NS-2604"),
    );
    assert(syncBodies.length === 1, "sync-manual was not called");
    assert(syncBodies[0].batch_id === "NS-2604", "sync-manual used the wrong batch");
    await page.locator('[aria-label="Close row detail"]').click();

    // PG-T1: stage filter, active only, and limit.
    await chooseOption(page, '[data-testid="progress-stage"]', "error");
    await page.waitForTimeout(150);
    assert((await rowsLocator.count()) === 1, "Error stage filter must show one row");
    await chooseOption(page, '[data-testid="progress-stage"]', "all");
    await page.locator('[data-testid="progress-active"]').check();
    await page.waitForTimeout(150);
    assert((await rowsLocator.count()) === 6, "Active only must hide the completed run but keep the failed run");
    await page.locator('[data-testid="progress-active"]').uncheck();
    await chooseOption(page, '[data-testid="progress-limit"]', "25");
    await page.waitForTimeout(150);
    assert((await rowsLocator.count()) === 7, "Limit 25 must keep all seven rows");
    await chooseOption(page, '[data-testid="progress-limit"]', "50");

    // PG-T1/PG-07: an invalid range blocks the request.
    const beforeInvalid = progressRequests;
    await page.locator('[data-testid="progress-to"]').fill("2026-11-18");
    await page.locator('[data-testid="progress-from"]').fill("2026-11-20");
    await page.locator('[data-testid="progress-range-error"]').waitFor();
    await page.waitForTimeout(700);
    assert(progressRequests === beforeInvalid, "Invalid range must not fetch");
    assert(
      await page.locator('[data-testid="progress-refresh"]').isDisabled(),
      "Refresh must be disabled for an invalid range",
    );
    await page.locator('[data-testid="progress-from"]').fill("2026-11-18");
    await page.locator('[data-testid="progress-to"]').fill("2026-11-19");
    await page.waitForTimeout(400);
  } finally {
    await app.close();
    server.close();
  }
}

async function emptyState() {
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /progress": (_request, response) =>
      json(response, 200, { rows: [], summary: "No runs", updated_at: "2026-11-19T10:00:00Z" }),
    "GET /music/downloads/pending": (_request, response) => json(response, 200, { items: [] }),
  });
  const { app, page } = await openApp("empty", port);
  try {
    await page.getByText("No runs match these filters.").waitFor({ timeout: 10000 });
    assert((await page.locator('[data-testid="progress-download-card"]').count()) === 0, "Download queue must hide when empty");
    assert((await stat(page, "active")).includes("0"), "Empty active stat must be zero");
    assert((await stat(page, "failed")).includes("0"), "Empty failed stat must be zero");
    await page.getByRole("button", { name: "Clear filters" }).waitFor();
    await capture(app, page, "progress-empty");
  } finally {
    await app.close();
    server.close();
  }
}

async function staleAfterError() {
  let calls = 0;
  const rows = successRows();
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /progress": (_request, response) => {
      calls += 1;
      if (calls === 1) {
        json(response, 200, { rows, summary: "Operational scan ready", updated_at: "2026-11-19T10:00:00Z" });
        return;
      }
      json(response, 503, { detail: "Progress unavailable" });
    },
    "GET /music/downloads/pending": (_request, response) => json(response, 200, { items: [] }),
  });
  const { app, page } = await openApp("stale", port);
  try {
    await page.locator('[data-testid="progress-row"]').first().waitFor({ timeout: 10000 });
    await page.locator('[data-testid="progress-refresh"]').click();
    await page.locator('[data-testid="progress-error-banner"]').waitFor({ timeout: 10000 });
    const banner = await page.locator('[data-testid="progress-error-banner"]').innerText();
    assert(banner.includes("last loaded rows are still shown"), "Stale retention copy missing");
    assert(banner.includes("Stale · last updated"), "Stale timestamp missing");
    assert((await page.locator('[data-testid="progress-row"]').count()) === 7, "Rows must remain after a poll failure");
    await capture(app, page, "progress-stale");
  } finally {
    await app.close();
    server.close();
  }
}

async function hardError() {
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /progress": (_request, response) => json(response, 500, { detail: "Progress unavailable" }),
    "GET /music/downloads/pending": (_request, response) => json(response, 200, { items: [] }),
  });
  const { app, page } = await openApp("error", port);
  try {
    await page.locator('[data-testid="progress-error-banner"]').waitFor({ timeout: 10000 });
    const banner = await page.locator('[data-testid="progress-error-banner"]').innerText();
    assert(banner.includes("No rows are available yet"), "Hard error copy missing");
    assert((await page.locator('[data-testid="progress-row"]').count()) === 0, "Hard error must not invent rows");
    assert(await page.getByRole("button", { name: "Clear filters" }).isVisible(), "Empty action missing");
    await capture(app, page, "progress-error");
  } finally {
    await app.close();
    server.close();
  }
}

async function twoHundredRows() {
  const rows = Array.from({ length: 200 }, (_, index) =>
    progressRow(index + 1, {
      batch: `BULK-${String(index + 1).padStart(3, "0")}`,
      meta: { updated_at: `2026-11-19T10:${String(index % 60).padStart(2, "0")}:00Z` },
    }),
  );
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /progress": (_request, response) =>
      json(response, 200, { rows, summary: "200 runs", updated_at: "2026-11-19T10:00:00Z" }),
    "GET /music/downloads/pending": (_request, response) => json(response, 200, { items: [] }),
  });
  const { app, page } = await openApp("bulk", port);
  try {
    await page.locator('[data-testid="progress-row"]').first().waitFor({ timeout: 10000 });
    await chooseOption(page, '[data-testid="progress-limit"]', "200");
    await page.waitForFunction(
      () => document.querySelectorAll('[data-testid="progress-row"]').length === 200,
      undefined,
      { timeout: 15000 },
    );
    const heights = await page.locator('[data-testid="progress-row"]').evaluateAll((nodes) =>
      nodes.map((node) => Math.round(node.getBoundingClientRect().height)),
    );
    assert(new Set(heights).size === 1, "200 rows must keep one stable row height");
    const overflow = await page.evaluate(() => ({
      body: document.body.scrollWidth,
      window: window.innerWidth,
    }));
    assert(overflow.body <= overflow.window + 2, "Page must not overflow horizontally");
    await capture(app, page, "progress-200-rows");
  } finally {
    await app.close();
    server.close();
  }
}

await successWithManualRecovery();
await emptyState();
await staleAfterError();
await hardError();
await twoHundredRows();
console.log(JSON.stringify({ progressPage: "ok", artifacts }));
