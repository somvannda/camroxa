/* global document */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/**
 * Manual YouTube upload acceptance (PG-20 / PG-50, 2.0.0).
 *
 * A fixture platform API and a local fake Google upload endpoint prove the
 * whole manual flow: merged file -> publish job -> resumable chunks (308
 * resume) -> report -> complete -> video link. It also pins the safety edges:
 * nothing uploads before the click, cancel leaves the file and the publish job
 * untouched, Auto-Upload stays disabled, and no token or channel email reaches
 * the DOM or the logs.
 */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

const RUN_OK = path.join(artifacts, "2026-11-19_Night Drive");
const RUN_CANCEL = path.join(artifacts, "2026-11-19_After Hours");
const RUN_RETRY = path.join(artifacts, "2026-11-19_Last Light");
for (const runDir of [RUN_OK, RUN_CANCEL, RUN_RETRY]) {
  fs.rmSync(runDir, { recursive: true, force: true });
  fs.mkdirSync(runDir, { recursive: true });
}

const CHUNK = 256 * 1024;
const FILE_BYTES = CHUNK * 4;
const MERGED_OK = path.join(RUN_OK, "MERGED_Night Drive.mp4");
const MERGED_CANCEL = path.join(RUN_CANCEL, "MERGED_After Hours.mp4");
const MERGED_RETRY = path.join(RUN_RETRY, "MERGED_Last Light.mp4");
const TOKEN = "fake-access-token-do-not-leak";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

function writeVideo(filePath) {
  const buffer = Buffer.alloc(FILE_BYTES);
  for (let index = 0; index < buffer.length; index += 1) buffer[index] = index % 251;
  fs.writeFileSync(filePath, buffer);
}

writeVideo(MERGED_OK);
writeVideo(MERGED_CANCEL);
writeVideo(MERGED_RETRY);
for (const runDir of [RUN_OK, RUN_CANCEL, RUN_RETRY]) {
  fs.writeFileSync(path.join(runDir, "thumbnail-16x9.png"), PNG);
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
  profile_addon_slots: 0,
  profile_addon_pending: 0,
  effective_profile_allowance: 5,
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
  image_config: { mode: "auto" },
  youtube_config: {
    visibility: "public",
    title_template: "{title} — {channel}",
    description_template: "{album} from {channel}",
    tags: "Night Drive, chill",
    category: "10",
    playlist: "PL-night",
    ai_use: true,
    made_for_kids: false,
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-02-01T00:00:00Z",
};

const BATCH_OK = "11111111-1111-4111-8111-111111111111";
const BATCH_CANCEL = "22222222-2222-4222-8222-222222222222";
const BATCH_RETRY = "33333333-3333-4333-8333-333333333333";

function progressRow({ batch, runDir, mergedName, album = "Night Drive", stage = "done" }) {
  return {
    batch,
    run_date: "2026-11-19",
    channel: "Night Shift",
    album,
    status: "completed",
    music: "12/12",
    image: "4/4",
    converter: "Completed",
    merge: "Completed",
    youtube: "",
    stage,
    notes: "",
    updated: "just now",
    meta: {
      batch_id: batch,
      profile_id: "profile-1",
      role: "OK",
      run_dir: runDir,
      source_mode: "auto",
      background_16x9_path: path.join(runDir, "background-16x9.png"),
      background_9x16_path: null,
      thumbnail_16x9_path: path.join(runDir, "thumbnail-16x9.png"),
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
      long_ready: true,
      reel_ready: false,
      pipeline_complete: true,
      auto_upload_youtube: false,
      updated_at: "2026-11-19T10:00:00Z",
      draft_failed_song_ids: [],
      suno_failed_song_ids: [],
      merged_file: mergedName,
    },
  };
}

const ROWS = [
  progressRow({ batch: BATCH_OK, runDir: RUN_OK, mergedName: MERGED_OK }),
  progressRow({
    batch: BATCH_CANCEL,
    runDir: RUN_CANCEL,
    mergedName: MERGED_CANCEL,
    album: "After Hours",
  }),
  progressRow({
    batch: BATCH_RETRY,
    runDir: RUN_RETRY,
    mergedName: MERGED_RETRY,
    album: "Last Light",
  }),
];

const license = {
  plan_type: "studio-monthly",
  profile_allowance: 5,
  profile_addon_slots: 0,
  profile_addon_pending: 0,
  effective_profile_allowance: 5,
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

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const text = Buffer.concat(chunks).toString("utf8");
  return text ? JSON.parse(text) : {};
}

function startApi(routes) {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const route = `${request.method} ${url.pathname.replace(/^\/api\/v3/, "")}`;
    const handler = routes[route];
    if (!handler) {
      json(response, 404, { detail: `No fixture for ${route}` });
      return;
    }
    Promise.resolve(handler(request, response, url)).catch((error) => {
      try {
        json(response, 500, { detail: String(error) });
      } catch {
        // response already finished
      }
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, port: server.address().port });
    });
  });
}

function startFakeYoutube() {
  const state = {
    sessions: [],
    events: [],
    playlist: [],
    dataPuts: {},
    aborted: 0,
  };
  let origin = "http://127.0.0.1";
  const server = http.createServer((request, response) => {
    void (async () => {
      const url = new URL(request.url ?? "/", "http://127.0.0.1");
      const chunks = [];
      for await (const chunk of request) chunks.push(chunk);
      const body = Buffer.concat(chunks);

      if (request.method === "POST" && url.pathname === "/upload/youtube/v3/videos") {
        if (url.searchParams.get("uploadType") !== "resumable") {
          json(response, 400, { error: { message: "not resumable" } });
          return;
        }
        const session = {
          index: state.sessions.length + 1,
          auth: request.headers.authorization ?? "",
          metadata: body.length ? JSON.parse(body.toString("utf8")) : {},
          contentLength: request.headers["x-upload-content-length"],
        };
        state.sessions.push(session);
        state.events.push({ type: "session", index: session.index });
        response.writeHead(200, { location: `${origin}/session/${session.index}` });
        response.end();
        return;
      }

      if (request.method === "PUT" && url.pathname.startsWith("/session/")) {
        const index = Number(url.pathname.split("/").pop());
        const range = String(request.headers["content-range"] ?? "");
        const length = Number(request.headers["content-length"] ?? 0);
        state.events.push({ type: "put", index, range, length });
        if (index === 2) await new Promise((resolve) => setTimeout(resolve, 400));
        if (!length) {
          // Resume probe: pretend the first chunk already landed.
          response.writeHead(308, { range: `bytes=0-${CHUNK - 1}` });
          response.end();
          return;
        }
        state.dataPuts[index] = (state.dataPuts[index] ?? 0) + 1;
        if (index === 3 && state.dataPuts[index] === 1) {
          // First retry-suite attempt: the provider refuses on quota.
          json(response, 403, { error: { errors: [{ reason: "uploadLimitExceeded" }] } });
          return;
        }
        const match = /^bytes (\d+)-(\d+)\/(\d+)$/.exec(range);
        if (!match) {
          json(response, 400, { error: { message: "bad range" } });
          return;
        }
        const end = Number(match[2]);
        const total = Number(match[3]);
        if (end + 1 >= total) {
          const session = state.sessions[index - 1];
          state.events.push({ type: "completed", index });
          json(response, 200, {
            id: `yt-video-${index}`,
            snippet: { title: session?.metadata?.snippet?.title ?? "" },
          });
          return;
        }
        response.writeHead(308, { range: `bytes=0-${end}` });
        response.end();
        return;
      }

      if (request.method === "POST" && url.pathname === "/youtube/v3/playlistItems") {
        state.playlist.push(body.length ? JSON.parse(body.toString("utf8")) : {});
        state.events.push({ type: "playlist" });
        json(response, 200, { id: "playlist-item-1" });
        return;
      }

      json(response, 404, { error: { message: `unhandled ${request.method} ${url.pathname}` } });
    })().catch(() => {
      state.aborted += 1;
      try {
        if (!response.headersSent) response.writeHead(499);
        response.end();
      } catch {
        // client already gone (cancel)
      }
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      origin = `http://127.0.0.1:${port}`;
      resolve({ server, state, base: origin });
    });
  });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function openApp(apiPort, uploadUrl, playlistUrl, userData) {
  fs.rmSync(userData, { recursive: true, force: true });
  const app = await electron.launch({
    args: ["dist-electron/main.cjs"],
    cwd: root,
    env: {
      ...process.env,
      CAMXORA_DEV_AUTH: "0",
      CAMXORA_USER_DATA_DIR: userData,
      CAMXORA_API_BASE_URL: `http://127.0.0.1:${apiPort}/api/v3`,
      CAMXORA_YOUTUBE_UPLOAD_URL: uploadUrl,
      CAMXORA_YOUTUBE_PLAYLIST_URL: playlistUrl,
      CAMXORA_YOUTUBE_CHUNK_BYTES: String(CHUNK),
    },
  });
  const page = await app.firstWindow();
  await page.waitForLoadState("domcontentloaded");
  await page.locator("#email").fill("operator@example.com");
  await page.locator("#password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForTimeout(500);
  const onboarding = page.getByRole("button", { name: "Open studio anyway" });
  if (await onboarding.isVisible().catch(() => false)) await onboarding.click();
  await page.getByRole("heading", { name: "Weekly Usage" }).waitFor({ timeout: 15000 });
  await page.getByRole("link", { name: "Progress" }).click();
  await page.getByRole("heading", { name: "Progress" }).waitFor({ timeout: 10000 });
  return { app, page };
}

async function capture(app, page, name) {
  await app.evaluate(async ({ BrowserWindow }, size) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (window) window.setSize(size.width, size.height);
  }, { width: 1440, height: 900 });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(artifacts, `youtube-upload-${name}.png`), fullPage: true });
}

async function main() {
  const createJobs = [];
  const reports = [];
  const completed = [];
  const retries = [];
  const cancelledJobs = [];
  const accessTokens = [];
  const progressRequests = [];

  const { server: apiServer, port: apiPort } = await startApi({
    "POST /auth/login": (_request, response) =>
      json(response, 200, { access_token: "e2e-token", refresh_token: "e2e-refresh", expires_in: 3600 }),
    "GET /users/me": (_request, response) => json(response, 200, ME),
    "GET /stats/dashboard": (_request, response) => json(response, 200, STATS),
    "GET /licenses/validate": (_request, response) => json(response, 200, license),
    "GET /profiles": (_request, response) => json(response, 200, [PROFILE]),
    "GET /settings": (_request, response) =>
      json(response, 200, { imageSourceMode: "auto", sunoOutputDir: RUN_OK, downloadsDir: RUN_OK }),
    "GET /youtube/connections": (_request, response) =>
      json(response, 200, {
        connections: [
          {
            profile_id: "profile-1",
            profile_name: "Night Shift",
            status: "connected",
            channel_id: "channel-1",
            channel_title: "Night Shift Radio",
            session_id: null,
            channels: [],
            message: null,
          },
        ],
      }),
    "GET /youtube/quota": (_request, response) =>
      json(response, 200, { limit: 6, used: 0, remaining: 6, resets_at: "2026-11-20T00:00:00Z" }),
    "GET /youtube/profiles/profile-1/playlists": (_request, response) =>
      json(response, 200, { playlists: [{ id: "PL-night", title: "Night Drive" }] }),
    "POST /youtube/profiles/profile-1/access-token": (_request, response) => {
      accessTokens.push(Date.now());
      json(response, 200, {
        access_token: TOKEN,
        expires_in: 3600,
        channel_id: "channel-1",
        channel_title: "Night Shift Radio",
      });
    },
    "GET /progress": (_request, response) => {
      progressRequests.push(Date.now());
      json(response, 200, { rows: ROWS, summary: "Operational scan ready", updated_at: "2026-11-19T10:00:00Z" });
    },
    "GET /music/downloads/pending": (_request, response) => json(response, 200, { items: [] }),
    "POST /publish/jobs": async (request, response) => {
      const body = await readJson(request);
      createJobs.push(body);
      json(response, 201, {
        job_uid: `job-${createJobs.length}`,
        status: "pending_upload",
        upload_url: null,
        upload_expires_at: null,
        media_url: null,
        thumbnail_upload_url: null,
        thumbnail_media_url: null,
        file_name: body.file_name ?? "",
        credits_per_upload: 2,
        platforms: ["youtube"],
        existing: false,
      });
    },
    "POST /publish/jobs/job-1/retry": (_request, response) => {
      retries.push("job-1");
      json(response, 200, { job_uid: "job-1", status: "pending_upload", upload_url: null, media_url: null });
    },
    "POST /publish/jobs/job-1/complete": async (request, response) => {
      completed.push({ job: "job-1", body: await readJson(request) });
      json(response, 200, { job_uid: "job-1", status: "success" });
    },
    "POST /publish/jobs/job-2/cancel": (_request, response) => {
      cancelledJobs.push("job-2");
      json(response, 200, { job_uid: "job-2", status: "cancelled" });
    },
    "POST /publish/jobs/job-3/retry": (_request, response) => {
      retries.push("job-3");
      json(response, 200, { job_uid: "job-3", status: "pending_upload", upload_url: null, media_url: null });
    },
    "POST /publish/jobs/job-3/complete": async (request, response) => {
      completed.push({ job: "job-3", body: await readJson(request) });
      json(response, 200, { job_uid: "job-3", status: "success" });
    },
    "POST /youtube/uploads/report": async (request, response) => {
      reports.push(await readJson(request));
      json(response, 200, { ok: true });
    },
    "GET /music/history": (_request, response) =>
      json(response, 200, { summary: "No batches yet", updated_at: null, batches: [] }),
    "GET /prompts/descriptions/public": (_request, response) =>
      json(response, 200, [{ id: "desc-1", name: "Bedroom pop", match_key: "bedroom-pop" }]),
    "GET /prompts/structures/public": (_request, response) =>
      json(response, 200, [{ id: "struct-1", name: "Verse chorus" }]),
    "GET /credits/operation-costs": (_request, response) =>
      json(response, 200, {
        items: [
          { operation_type: "lyric", credits_per_operation: 3, available: true },
          { operation_type: "music", credits_per_operation: 7, available: true },
          { operation_type: "video_merge", credits_per_operation: 10, available: true },
          { operation_type: "publish", credits_per_operation: 2, available: true },
        ],
      }),
  });

  const { server: youtubeServer, state: youtube, base: youtubeBase } = await startFakeYoutube();

  const userData = path.join(artifacts, "e2e-youtube-upload");
  const { app, page } = await openApp(
    apiPort,
    `${youtubeBase}/upload/youtube/v3/videos`,
    `${youtubeBase}/youtube/v3/playlistItems`,
    userData,
  );

  try {
    // --- 1. Readiness, with nothing sent yet -----------------------------
    await page.locator('[data-testid="progress-row"]').first().waitFor({ timeout: 15000 });
    await page.locator('[data-testid="progress-row-upload"]').first().waitFor({ timeout: 15000 });
    assert(progressRequests.length >= 1, "Progress rows were requested");
    assert(createJobs.length === 0, "No publish job may exist before the user clicks Upload");
    assert(accessTokens.length === 0, "No access token may be requested before the user clicks Upload");
    assert(youtube.sessions.length === 0, "No YouTube session may start automatically");

    // --- 2. Detail panel + confirmation ----------------------------------
    await page.locator(`[data-testid="progress-row"][data-row-key*="${BATCH_OK}"]`).click();
    await page.locator('[data-testid="progress-upload-panel"]').waitFor({ timeout: 10000 });
    const uploadButton = page.locator('[data-testid="progress-upload-youtube"]:not([disabled])');
    await uploadButton.waitFor({ timeout: 15000 });
    const panelText = await page.locator('[data-testid="progress-upload-panel"]').innerText();
    assert(panelText.includes("Night Shift Radio"), "Panel names the connected channel");
    assert(panelText.includes("Auto-Upload stays off"), "Panel states Auto-Upload stays off");

    await uploadButton.click();
    const confirmation = page.locator('[data-testid="youtube-upload-confirmation"]');
    await confirmation.waitFor({ timeout: 10000 });
    const line = (label) =>
      confirmation.locator("> div").filter({ has: page.getByText(label, { exact: true }) });
    assert((await line("Channel").innerText()).includes("Night Shift Radio"), "Confirmation shows the channel");
    assert(
      (await line("Title").innerText()).includes("Night Drive — Night Shift"),
      "Confirmation shows the rendered title",
    );
    assert((await line("Visibility").innerText()).includes("Public"), "Confirmation shows the visibility");
    assert((await line("Playlist").innerText()).includes("Night Drive"), "Confirmation shows the playlist");
    assert(
      (await line("File").innerText()).includes("MERGED_Night Drive.mp4"),
      "Confirmation shows the merged file",
    );
    assert(
      (await line("Disclosure").innerText()).includes("AI-generated content disclosed"),
      "Confirmation shows the AI disclosure",
    );
    await capture(app, page, "confirmation");

    await page.locator('[data-testid="youtube-upload-confirm"]').click();

    // --- 3. Publish job, resumable chunks, report, complete ---------------
    await page
      .locator('[data-testid="progress-upload-progress"]')
      .filter({ hasText: "Upload complete" })
      .waitFor({ timeout: 30000 });
    await page.locator('[data-testid="progress-upload-link"]').waitFor({ timeout: 10000 });
    const panelDone = await page.locator('[data-testid="progress-upload-message"]').innerText();
    assert(/Published to YouTube/.test(panelDone), `Panel reports success (got "${panelDone}")`);
    const progressbar = page.locator('[data-testid="progress-upload-progress"]');
    assert((await progressbar.innerText()).includes("Upload complete"), "Panel shows a completed progress bar");

    assert(createJobs.length === 1, "Exactly one publish job was created");
    const job = createJobs[0];
    assert(job.profile_id === "profile-1", "Job carries the profile");
    assert(job.batch_id === BATCH_OK, "Job carries the batch");
    assert(job.role === "OK", "Job carries the role");
    assert(job.platform === "youtube", "Job targets YouTube");
    assert(job.title === "Night Drive — Night Shift", `Job title rendered (got "${job.title}")`);
    assert(job.description === "Night Drive from Night Shift", "Job description rendered");
    assert(JSON.stringify(job.tags) === JSON.stringify(["Night Drive", "chill"]), "Job carries sanitised tags");
    assert(job.privacy_status === "public", "Job carries the visibility");
    assert(job.made_for_kids === false, "Job carries the audience setting");
    assert(job.contains_synthetic_media === true, "Job carries the AI disclosure");
    assert(job.file_name === "MERGED_Night Drive.mp4", "Job names the merged file");
    assert(job.file_size_bytes === FILE_BYTES, "Job carries the file size");
    assert(String(job.file_path).endsWith("MERGED_Night Drive.mp4"), "Job carries the contained path");

    assert(accessTokens.length === 1, "One short-lived token was requested for the upload");
    assert(youtube.sessions.length === 1, "One resumable session was opened");
    assert(youtube.sessions[0].auth === `Bearer ${TOKEN}`, "The session used the short-lived token");
    const metadata = youtube.sessions[0].metadata;
    assert(metadata.snippet.title === job.title, "YouTube received the same title");
    assert(metadata.status.privacyStatus === "public", "YouTube received the visibility");
    assert(metadata.status.containsSyntheticMedia === true, "YouTube received the AI disclosure");
    assert(youtube.sessions[0].contentLength === String(FILE_BYTES), "YouTube received the file length");

    const puts = youtube.events.filter((event) => event.type === "put");
    const dataPuts = puts.filter((event) => event.length > 0);
    assert(dataPuts.length === 3, `Upload was chunked (got ${dataPuts.length} data chunks)`);
    assert(dataPuts[0].range === `bytes ${CHUNK}-${CHUNK * 2 - 1}/${FILE_BYTES}`, "Resumed at the byte YouTube kept");
    assert(dataPuts.every((event) => event.length <= CHUNK), "Every chunk respects the chunk size");
    assert(
      dataPuts.at(-1).range === `bytes ${CHUNK * 3}-${FILE_BYTES - 1}/${FILE_BYTES}`,
      "The final chunk ends at the file length",
    );
    assert(youtube.events.some((event) => event.type === "completed" && event.index === 1), "YouTube confirmed the video");
    assert(youtube.playlist.length === 1, "The video was added to the profile playlist");
    assert(youtube.playlist[0].snippet.playlistId === "PL-night", "The playlist id came from the profile");
    assert(youtube.playlist[0].snippet.resourceId.videoId === "yt-video-1", "The playlist item points at the video");

    assert(reports.length === 1, "One upload report was sent");
    assert(reports[0].batch_id === BATCH_OK, "Report carries the batch");
    assert(reports[0].video_id === "yt-video-1", "Report carries the video id");
    assert(reports[0].video_url === "https://www.youtube.com/watch?v=yt-video-1", "Report carries the URL");
    assert(reports[0].status === "success", "Report marks the upload successful");
    assert(completed.length === 1 && completed[0].job === "job-1", "The publish job was completed");
    assert(completed[0].body && completed[0].body.checksum === null, "Completion carries the checksum field");

    const link = await page.locator('[data-testid="progress-upload-link"]').getAttribute("title");
    assert(link === "https://www.youtube.com/watch?v=yt-video-1", "The panel links to the video");
    await capture(app, page, "done");

    // --- 4. Cancel leaves the file and the publish job untouched ---------
    const beforeCancel = fs.readFileSync(MERGED_CANCEL);
    await page.locator(`[data-testid="progress-row"][data-row-key*="${BATCH_CANCEL}"]`).click();
    await page.locator('[data-testid="progress-upload-panel"]').waitFor({ timeout: 10000 });
    const cancelUploadButton = page.locator('[data-testid="progress-upload-youtube"]:not([disabled])');
    await cancelUploadButton.waitFor({ timeout: 15000 });
    await cancelUploadButton.click();
    await page.locator('[data-testid="youtube-upload-confirmation"]').waitFor({ timeout: 10000 });
    await page.locator('[data-testid="youtube-upload-confirm"]').click();

    const cancelButton = page.locator('[data-testid="progress-upload-cancel"]');
    await cancelButton.waitFor({ timeout: 10000 });
    await page.waitForTimeout(150);
    const rowCancelText = await page
      .locator(`[data-testid="progress-row"][data-row-key*="${BATCH_CANCEL}"]`)
      .innerText();
    assert(rowCancelText.includes("Uploading"), "The row's YouTube cell shows the live upload state");
    await cancelButton.click();
    await page.locator('[data-testid="progress-upload-message"]').filter({ hasText: "cancelled" }).waitFor({
      timeout: 15000,
    });
    await page.waitForTimeout(800);

    assert(createJobs.length === 2, "The cancelled attempt created its own publish job");
    assert(completed.length === 1, "A cancelled upload must not complete a publish job");
    assert(
      reports.every((report) => report.status !== "success" || report.batch_id === BATCH_OK),
      "No success report for the cancelled upload",
    );
    assert(
      !youtube.events.some((event) => event.type === "completed" && event.index === 2),
      "YouTube never finished the cancelled upload",
    );
    assert(cancelledJobs.includes("job-2"), "Cancel releases the reserved publish job");
    const afterCancel = fs.readFileSync(MERGED_CANCEL);
    assert(beforeCancel.equals(afterCancel), "Cancel leaves the local video byte-identical");
    assert(fs.existsSync(MERGED_CANCEL), "Cancel keeps the local video on disk");
    assert(
      (await page.locator('[data-testid="progress-upload-message"]').innerText()).includes("local video was kept"),
      "Panel says the local video was kept",
    );
    await capture(app, page, "cancelled");

    // --- 5. A provider failure is readable, keeps the file, then retries --
    const beforeRetry = fs.readFileSync(MERGED_RETRY);
    await page.locator(`[data-testid="progress-row"][data-row-key*="${BATCH_RETRY}"]`).click();
    await page.locator('[data-testid="progress-upload-panel"]').waitFor({ timeout: 10000 });
    const retryRowButton = page.locator('[data-testid="progress-upload-youtube"]:not([disabled])');
    await retryRowButton.waitFor({ timeout: 15000 });
    await retryRowButton.click();
    await page.locator('[data-testid="youtube-upload-confirmation"]').waitFor({ timeout: 10000 });
    await page.locator('[data-testid="youtube-upload-confirm"]').click();

    await page.locator('[data-testid="progress-upload-message"]').filter({ hasText: "quota" }).waitFor({
      timeout: 30000,
    });
    const failureText = await page.locator('[data-testid="progress-upload-message"]').innerText();
    assert(/quota/i.test(failureText), `Failure names the quota (got "${failureText}")`);
    assert(fs.readFileSync(MERGED_RETRY).equals(beforeRetry), "A failed upload leaves the local video byte-identical");
    assert(
      reports.some((report) => report.status === "failed" && report.batch_id === BATCH_RETRY),
      "A failed attempt is reported with its reason",
    );
    const failureReport = reports.find((report) => report.status === "failed" && report.batch_id === BATCH_RETRY);
    assert(/quota/i.test(String(failureReport?.error_message ?? "")), "The failure report carries the reason");
    assert(createJobs.length === 3, "The failed attempt used its own publish job");
    assert(completed.length === 1, "A failed upload must not complete its publish job");
    await capture(app, page, "failed");

    const retryButton = page.locator('[data-testid="progress-upload-retry"]');
    await retryButton.waitFor({ timeout: 15000 });
    await retryButton.click();
    await page.locator('[data-testid="youtube-upload-confirmation"]').waitFor({ timeout: 10000 });
    await page.locator('[data-testid="youtube-upload-confirm"]').click();
    await page
      .locator('[data-testid="progress-upload-progress"]')
      .filter({ hasText: "Upload complete" })
      .waitFor({ timeout: 30000 });

    assert(retries.includes("job-3"), "Retry reuses the failed publish job via /retry");
    assert(createJobs.length === 3, "Retry does not create a second publish job");
    assert(youtube.sessions.length === 4, "Retry opened a fresh resumable session");
    assert(youtube.events.some((event) => event.type === "completed" && event.index === 4), "The retry completed on YouTube");
    assert(completed.some((entry) => entry.job === "job-3"), "The retried publish job was completed");
    assert(
      reports.some((report) => report.status === "success" && report.batch_id === BATCH_RETRY),
      "The retry reported success",
    );
    assert(fs.readFileSync(MERGED_RETRY).equals(beforeRetry), "The retry leaves the local video unchanged");

    // The page body must never carry the token or an address.
    const mainText = await page.evaluate(() => document.querySelector("main")?.innerText ?? "");
    assert(!mainText.includes(TOKEN), "The access token must never reach the DOM");
    assert(!mainText.includes("access_token"), "No token field is rendered");
    assert(!mainText.includes("operator@example.com"), "No account email is rendered in the page body");

    // --- 6. Auto-Upload stays disabled and no secret reaches the logs ----
    await page.getByRole("link", { name: "Music", exact: true }).click();
    await page.getByRole("heading", { name: "Music" }).first().waitFor({ timeout: 15000 });
    const autoUpload = page.locator('[data-testid="toggle-auto-upload"]');
    await autoUpload.waitFor({ timeout: 15000 });
    assert(await autoUpload.isDisabled(), "Auto-Upload must stay disabled exactly as 1.7.1");
    const autoChecked = await autoUpload.evaluate(
      (element) => element.getAttribute("aria-checked") === "true" || element.hasAttribute("checked"),
    );
    assert(autoChecked === false, "Auto-Upload must stay unchecked");
    assert(createJobs.length === 3, "Nothing uploaded while visiting Music");

    const logDir = path.join(userData, "logs");
    const logs = fs.existsSync(logDir)
      ? fs.readdirSync(logDir).map((file) => fs.readFileSync(path.join(logDir, file), "utf8")).join("\n")
      : "";
    assert(!logs.includes(TOKEN), "The access token must never reach the logs");
    assert(!/Bearer\s+fake-access-token/i.test(logs), "No bearer token in the logs");
    assert(!logs.includes("operator@example.com"), "No account email in the logs");

    assert(progressRequests.length >= 1, "Progress polling stayed alive");

    process.stdout.write(
      `${JSON.stringify({
        youtubeUpload: "ok",
        chunks: dataPuts.length,
        resumedOffset: CHUNK,
        fileBytes: FILE_BYTES,
        reports: reports.length,
        completed: completed.length,
        retried: retries.length > 0,
        cancelled: true,
        autoUploadDisabled: true,
        artifacts,
      })}\n`,
    );
  } finally {
    await app.close();
    apiServer.close();
    youtubeServer.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error?.stack ?? error}\n`);
  process.exitCode = 1;
});
