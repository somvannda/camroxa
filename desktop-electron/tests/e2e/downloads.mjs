/* global document */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/**
 * P4 music download coordinator acceptance against a local HTTP server.
 *
 * Seeds pending targets, then asserts: real files with real bytes, live progress,
 * dedupe of a repeated pending item, automatic retry after a 500, a manual retry
 * after the attempt limit, cancel without a partial file, and rejection of a
 * traversal target.
 */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

const USER_DATA = path.join(artifacts, "e2e-downloads");
const DOWNLOAD_ROOT = path.join(USER_DATA, "downloads");
fs.rmSync(USER_DATA, { recursive: true, force: true });

const MP3_BYTES = Buffer.concat([Buffer.from("ID3"), Buffer.alloc(4096, 9)]);
const SLOW_CHUNKS = 24;
const SLOW_CHUNK_BYTES = 1024;

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
  credits_spent: 0,
  credits_remaining: 500,
  credits_total: 500,
  songs_generated: 0,
  songs_remaining: 120,
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
  songs_remaining: 120,
  monthly_image_quota: 40,
  images_remaining: 40,
  wallet_balance: 500,
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

function sendMp3(response, bytes = MP3_BYTES) {
  response.writeHead(200, {
    "content-type": "audio/mpeg",
    "content-length": bytes.length,
  });
  response.end(bytes);
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

function walk(directory) {
  if (!fs.existsSync(directory)) return [];
  const found = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) found.push(...walk(full));
    else found.push(full);
  }
  return found;
}

function target(relativePath) {
  return path.join(DOWNLOAD_ROOT, relativePath);
}

const counts = {
  alpha: 0,
  beta: 0,
  duplicate: 0,
  flaky: 0,
  slow: 0,
};

const synced = new Set();
const syncBodies = [];

const seedItems = [];

function pendingForServer() {
  const mark = (taskId, role, target) =>
    target
      ? { ...target, downloaded: target.downloaded === true || synced.has(`${taskId}:${role}`) }
      : target;
  return {
    items: seedItems.map((entry) => ({
      ...entry,
      primary: mark(entry.task_id, "primary", entry.primary),
      secondary: mark(entry.task_id, "secondary", entry.secondary),
    })),
  };
}

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
    json(response, 200, { rows: [], summary: "No runs", updated_at: "2026-11-19T10:00:00Z" }),
  "GET /music/downloads/pending": (_request, response) => json(response, 200, pendingForServer()),
  "POST /music/downloads/sync": (request, response) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      const parsed = JSON.parse(body || "{}");
      syncBodies.push(parsed);
      for (const entry of parsed.items ?? []) {
        if (entry.downloaded_primary) synced.add(`${entry.task_id}:primary`);
        if (entry.downloaded_secondary) synced.add(`${entry.task_id}:secondary`);
      }
      json(response, 200, { updated: parsed.items?.length ?? 0 });
    });
  },
  "GET /files/alpha.mp3": (_request, response) => {
    counts.alpha += 1;
    sendMp3(response);
  },
  "GET /files/beta.mp3": (_request, response) => {
    counts.beta += 1;
    sendMp3(response);
  },
  "GET /files/duplicate.mp3": (_request, response) => {
    counts.duplicate += 1;
    sendMp3(response);
  },
  "GET /files/flaky.mp3": (_request, response) => {
    counts.flaky += 1;
    if (counts.flaky <= 3) {
      json(response, 500, { detail: "Temporary download failure" });
      return;
    }
    sendMp3(response);
  },
  "GET /files/slow.mp3": (_request, response) => {
    counts.slow += 1;
    response.writeHead(200, {
      "content-type": "audio/mpeg",
      "content-length": SLOW_CHUNKS * SLOW_CHUNK_BYTES,
    });
    let sent = 0;
    const timer = setInterval(() => {
      if (sent >= SLOW_CHUNKS) {
        clearInterval(timer);
        response.end();
        return;
      }
      sent += 1;
      response.write(Buffer.alloc(SLOW_CHUNK_BYTES, 4));
    }, 120);
    response.on("close", () => clearInterval(timer));
  },
});

const origin = `http://127.0.0.1:${port}`;

function pendingItem(id, fields) {
  return {
    task_id: id,
    song_id: `song-${id}`,
    batch_id: "NS-7001",
    track_number: 1,
    primary: {
      download_url: fields.url,
      downloaded: false,
      output_dir: DOWNLOAD_ROOT,
      target_path: fields.target,
    },
    ...fields,
  };
}

const duplicateItem = pendingItem("task-dup", {
  title: "Duplicate Song",
  url: `${origin}/files/duplicate.mp3`,
  target: target("c/03 Duplicate Song.mp3"),
});

seedItems.push(
  pendingItem("task-a", {
    title: "Alpha Song",
    url: `${origin}/files/alpha.mp3`,
    target: target("a/01 Alpha Song.mp3"),
  }),
  pendingItem("task-b", {
    title: "Beta Song",
    url: `${origin}/files/beta.mp3`,
    target: target("b/02 Beta Song.mp3"),
  }),
  duplicateItem,
  // The server repeats the same target: it must be fetched once.
  duplicateItem,
  pendingItem("task-flaky", {
    title: "Flaky Song",
    url: `${origin}/files/flaky.mp3`,
    target: target("f/04 Flaky Song.mp3"),
  }),
  pendingItem("task-slow", {
    title: "Slow Song",
    url: `${origin}/files/slow.mp3`,
    target: target("s/05 Slow Song.mp3"),
  }),
  pendingItem("task-escape", {
    title: "Escape Song",
    url: `${origin}/files/alpha.mp3`,
    target: `${DOWNLOAD_ROOT}/../escape.mp3`,
  }),
  pendingItem("task-nourl", {
    title: "No Link Song",
    url: null,
    target: target("n/06 No Link Song.mp3"),
  }),
);

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "0",
    CAMXORA_E2E: "1",
    CAMXORA_USER_DATA_DIR: USER_DATA,
    CAMXORA_API_BASE_URL: `${origin}/api/v3`,
  },
});

async function waitForFile(file, timeoutMs = 20000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (fs.existsSync(file) && fs.statSync(file).size === MP3_BYTES.length) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for ${file}`);
}

async function waitFor(predicate, timeoutMs = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Timed out waiting for a condition");
}

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

  const card = page.locator('[data-testid="progress-download-card"]');
  await card.waitFor({ timeout: 20000 });

  const rows = page.locator('[data-testid="progress-download-row"]');
  await page.waitForFunction(
    () => document.querySelectorAll('[data-testid="progress-download-row"]').length === 7,
    undefined,
    { timeout: 20000 },
  );
  assert((await rows.count()) === 7, "One row per pending target (the repeated item is deduped)");

  const slowRow = page.locator('[data-testid="progress-download-row"]', { hasText: "Slow Song" });
  await slowRow.getByText("Downloading").waitFor({ timeout: 20000 });
  const liveText = await slowRow.innerText();
  assert(liveText.includes("/") && liveText.includes("%"), `Live progress missing: ${liveText}`);
  await page.locator('[data-testid="progress-download-card"]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(artifacts, "downloads-progress.png"), fullPage: true });

  // Cancel the slow stream: no target file, no partial file left behind.
  await slowRow.getByRole("button", { name: "Cancel" }).click();
  await slowRow.getByText("Cancelled").waitFor({ timeout: 10000 });
  await page.waitForTimeout(300);
  assert(!fs.existsSync(target("s/05 Slow Song.mp3")), "Cancelled download wrote a file");
  assert(
    !walk(DOWNLOAD_ROOT).some((file) => path.basename(file).includes(".camxora-part-")),
    "Cancel left a partial file behind",
  );

  // The 500 is retried automatically three times, then a manual retry succeeds.
  const flakyRow = page.locator('[data-testid="progress-download-row"]', { hasText: "Flaky Song" });
  await flakyRow.getByText("Failed").waitFor({ timeout: 20000 });
  assert((await flakyRow.innerText()).includes("HTTP 500"), "The failure reason must name the status");
  const retry = flakyRow.getByRole("button", { name: "Retry" });
  assert(!(await retry.isDisabled()), "Retry must be enabled for a failed item with a URL");
  await retry.click();
  await flakyRow.getByText("Done").waitFor({ timeout: 20000 });
  assert(fs.existsSync(target("f/04 Flaky Song.mp3")), "Manual retry did not write the file");

  // Wait for the remaining items and assert real bytes.
  for (const file of [
    "a/01 Alpha Song.mp3",
    "b/02 Beta Song.mp3",
    "c/03 Duplicate Song.mp3",
    "f/04 Flaky Song.mp3",
  ]) {
    await waitForFile(target(file));
    const full = target(file);
    assert(fs.statSync(full).size === MP3_BYTES.length, `Wrong size for ${file}`);
  }

  assert(counts.duplicate === 1, `The repeated item was fetched ${counts.duplicate} times`);
  assert(counts.alpha === 1, `The traversal target still fetched its URL (${counts.alpha})`);
  assert(counts.beta === 1, "A completed item was fetched twice");

  // Completion is acknowledged to the server (1.7.1 parity): only real files,
  // never the cancelled, rejected or linkless rows.
  const reportedKeys = () => {
    const reported = new Set();
    for (const body of syncBodies) {
      for (const entry of body.items ?? []) {
        if (entry.downloaded_primary) reported.add(`${entry.task_id}:primary`);
        if (entry.downloaded_secondary) reported.add(`${entry.task_id}:secondary`);
      }
    }
    return reported;
  };
  const expectedSynced = ["task-a:primary", "task-b:primary", "task-dup:primary", "task-flaky:primary"];
  await waitFor(() => expectedSynced.every((key) => reportedKeys().has(key)));
  const reported = reportedKeys();
  assert(!reported.has("task-slow:primary"), "A cancelled download must not be reported");
  assert(!reported.has("task-escape:primary"), "A rejected target must not be reported");
  assert(!reported.has("task-nourl:primary"), "A row without a URL must not be reported");

  assert(!fs.existsSync(path.join(USER_DATA, "escape.mp3")), "A traversal target escaped the root");
  assert(
    !walk(DOWNLOAD_ROOT).some((file) => path.basename(file).includes(".camxora-part-")),
    "A partial file survived the run",
  );

  const escapeRow = page.locator('[data-testid="progress-download-row"]', { hasText: "Escape Song" });
  assert(
    (await escapeRow.innerText()).includes("escapes the output folder"),
    "The traversal target must be rejected with a readable reason",
  );
  const noUrlRow = page.locator('[data-testid="progress-download-row"]', { hasText: "No Link Song" });
  assert(
    (await noUrlRow.innerText()).includes("did not provide a download link"),
    "A missing URL must be a specific error",
  );
  assert(
    await noUrlRow.getByRole("button", { name: "Retry" }).isDisabled(),
    "Retry must be disabled when the item has no URL",
  );

  const mainText = await page.locator("main").innerText();
  assert(!mainText.includes("e2e-token"), "The access token must never reach the renderer");
  assert(!mainText.includes("operator@example.com"), "The account email must never be rendered");
  assert(!mainText.includes("/files/alpha.mp3"), "Download URLs must not be rendered");

  await page.locator('[data-testid="progress-download-card"]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(artifacts, "downloads-done.png"), fullPage: true });
} finally {
  await app.close();
  server.close();
}

// Quit deletes partial files; the completed files stay.
await new Promise((resolve) => setTimeout(resolve, 300));
assert(
  !walk(DOWNLOAD_ROOT).some((file) => path.basename(file).includes(".camxora-part-")),
  "Quitting left a partial file behind",
);

console.log(
  JSON.stringify({
    downloads: "ok",
    artifacts,
    root: DOWNLOAD_ROOT,
    counts,
  }),
);
