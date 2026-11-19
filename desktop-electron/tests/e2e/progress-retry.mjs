import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/** PG-31/PG-T9: an image-stage failure can be retried from the row detail. */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

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
  images_generated: 0,
  studio_exports: 0,
  manual_exports: 0,
  youtube_uploads: 0,
  videos_generated: 0,
  videos_uploaded: 0,
  usage_by_day: [],
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
  image_config: { mode: "bg_only" },
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

const ROW = {
  batch: "NS-9001",
  run_date: "2026-11-19",
  channel: "Night Shift",
  album: "Night Drive",
  status: "failed",
  music: "12/12",
  image: "BG 2/4 · TH 0/4",
  converter: "",
  merge: "",
  youtube: "",
  stage: "image",
  notes: "Background image generation failed",
  updated: "just now",
  meta: {
    batch_id: "NS-9001",
    profile_id: "profile-1",
    role: "OK",
    run_dir: null,
    source_mode: "ai",
    expected: 12,
    saved: 12,
    download_pending: 0,
    download_ready: 12,
    bg_ready: 2,
    bg_total: 4,
    th_ready: 0,
    th_total: 4,
    bg_status: "FAILED",
    th_status: "PENDING",
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

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const retryBodies = [];
const { server, port } = await startApi({
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
  "GET /settings": (_request, response) => json(response, 200, { imageSourceMode: "ai" }),
  "GET /progress": (_request, response) =>
    json(response, 200, { rows: [ROW], summary: "One run", updated_at: "2026-11-19T10:00:00Z" }),
  "GET /music/downloads/pending": (_request, response) => json(response, 200, { items: [] }),
  "POST /image-jobs/retry": (request, response) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      retryBodies.push(JSON.parse(body || "{}"));
      json(response, 200, { updated: 2 });
    });
  },
});

const userData = path.join(artifacts, "e2e-progress-retry");
fs.rmSync(userData, { recursive: true, force: true });
const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "0",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_API_BASE_URL: `http://127.0.0.1:${port}/api/v3`,
  },
});

try {
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

  await page.locator('[data-testid="progress-row"]').first().click();
  const retry = page.locator('[data-testid="progress-retry-stage"]');
  await retry.waitFor();
  assert(!(await retry.isDisabled()), "Image retry must be enabled for an image-stage failure");
  await retry.click();
  await page.getByRole("dialog").waitFor();
  await page.getByRole("dialog").getByRole("button", { name: "Retry image stage" }).click();
  await page.getByText("Re-queued image jobs for NS-9001 (2 updated).").waitFor({ timeout: 5000 });
  assert(retryBodies.length === 1, "image retry was not called");
  assert(retryBodies[0].batch_id === "NS-9001", "image retry used the wrong batch");
  assert(retryBodies[0].force === true, "image retry must force the failed stage");
} finally {
  await app.close();
  server.close();
}

console.log(JSON.stringify({ progressRetry: "ok", artifacts }));
