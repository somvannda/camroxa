import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/**
 * Music workspace E2E against a stub platform API.
 *
 * Covers: bootstrap, the settings strip and autosave, cost parity labels,
 * draft with content-pool seeds, polish + undo, history row load and filters,
 * Generate fan-out with manual run directories, partial failure, empty and
 * load-error states, and token/email hygiene.
 */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });
const runRoot = path.join(artifacts, `music-runs-${Date.now()}`);

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
  onboarding_paid: true,
  desktop_access: true,
  channel_profile_count: 2,
  products: ["desktop"],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: null,
};

const STATS = {
  credits_spent: 1234,
  credits_remaining: 750,
  credits_total: 2000,
  songs_generated: 12,
  songs_remaining: 76,
  songs_quota: 120,
  images_remaining: null,
  images_quota: null,
  drafts_remaining: null,
  drafts_quota: null,
  images_generated: 5,
  studio_exports: 3,
  manual_exports: 2,
  youtube_uploads: 1,
  videos_generated: 3,
  videos_uploaded: 1,
  usage_by_day: [],
  recent_activity: [],
};

const PROFILES = [
  {
    id: "profile-1",
    user_id: "user-1",
    name: "Night Shift",
    folder_name: "night-shift",
    run_prefix: "NS",
    logo_path: null,
    video_template_id: null,
    reel_template_id: null,
    output_resolution: "1920x1080",
    image_config: { mode: "bg_thumb" },
    youtube_config: { visibility: "public" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
  },
  {
    id: "profile-2",
    user_id: "user-1",
    name: "Deep Focus",
    folder_name: "deep-focus",
    run_prefix: "DF",
    logo_path: null,
    video_template_id: null,
    reel_template_id: null,
    output_resolution: "1080x1920",
    image_config: { mode: "bg_thumb" },
    youtube_config: { visibility: "unlisted" },
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-02-02T00:00:00Z",
  },
];

const DESCRIPTIONS = [
  { id: "desc-1", name: "Bedroom pop", match_key: "bedroom-pop" },
  { id: "desc-2", name: "Arena synth", match_key: "arena-synth" },
];

const STRUCTURES = [
  { id: "struct-1", name: "Verse chorus" },
  { id: "struct-2", name: "Full song" },
];

const HISTORY = {
  summary: "2 batches · 2 songs",
  updated_at: "2026-11-19T11:00:00Z",
  batches: [
    {
      batch_id: "b2",
      status: "completed",
      song_count: 1,
      from_date: "2026-11-18",
      to_date: "2026-11-18",
      planned_days: 1,
      ok_profile_id: "profile-1",
      ok_profile_name: "Night Shift",
      alt_profile_id: "profile-2",
      alt_profile_name: "Deep Focus",
      ok_album: "Night Album",
      alt_album: "Night Album",
      created_at: "2026-11-18T10:00:00Z",
      updated_at: "2026-11-18T10:20:00Z",
      songs: [
        {
          song_id: "song-1",
          batch_index: 0,
          title: "First Light",
          album: "Night Album",
          lyrics: "[verse]\nOpening line\nSecond line",
          description_id: "desc-1",
          description_name: "Bedroom pop",
          structure_id: "struct-1",
          structure_name: "Verse chorus",
          output_dir_ok: "C:\\Runs\\Night\\2026-11-18",
          output_dir_alt: "",
          status: "completed",
          suno_status: "completed",
          created_at: "2026-11-18T10:05:00Z",
          updated_at: "2026-11-18T10:10:00Z",
        },
      ],
    },
    {
      batch_id: "b1",
      status: "completed",
      song_count: 1,
      from_date: "2026-11-17",
      to_date: "2026-11-17",
      planned_days: 1,
      ok_profile_id: "profile-1",
      ok_profile_name: "Night Shift",
      alt_profile_id: "profile-2",
      alt_profile_name: "Deep Focus",
      created_at: "2026-11-17T10:00:00Z",
      updated_at: "2026-11-17T10:20:00Z",
      songs: [
        {
          song_id: "song-9",
          batch_index: 0,
          title: "Older Light",
          album: "Older Album",
          lyrics: "[verse]\nOld opening",
          description_id: "desc-1",
          description_name: "Bedroom pop",
          structure_id: "struct-1",
          structure_name: "Verse chorus",
          status: "completed",
          suno_status: "completed",
          created_at: "2026-11-17T10:05:00Z",
          updated_at: "2026-11-17T10:10:00Z",
        },
      ],
    },
  ],
};

const COSTS = {
  items: [
    { operation_type: "lyric", credits_per_operation: 3, available: true },
    { operation_type: "title", credits_per_operation: 0, available: true },
    { operation_type: "album", credits_per_operation: 0, available: true },
    { operation_type: "music", credits_per_operation: 7, available: true },
    { operation_type: "background_image", credits_per_operation: 5, available: true },
    { operation_type: "video", credits_per_operation: 3, available: true },
    { operation_type: "video_merge", credits_per_operation: 10, available: true },
    { operation_type: "publish", credits_per_operation: 2, available: true },
  ],
};

function settings() {
  return {
    language: "en",
    creativity: 55,
    uniqueOpening: false,
    useContentPools: false,
    strictLevel: 3,
    uniquenessHistoryWindow: 100,
    defaultSongCount: 4,
    autoGenImage: false,
    autoGSuno: false,
    autoVideoAfterSuno: false,
    autoMergeAfterVideo: false,
    autoReelAfterVideo: false,
    autoUploadYouTube: false,
    lyricsPolishStrength: 85,
    imageSourceMode: "ai",
  };
}

function json(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

function startApi(routes) {
  const calls = [];
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const route = `${request.method} ${url.pathname.replace(/^\/api\/v3/, "")}`;
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk;
    });
    request.on("end", () => {
      let body;
      try {
        body = raw ? JSON.parse(raw) : undefined;
      } catch {
        body = raw;
      }
      calls.push({ route, body, query: Object.fromEntries(url.searchParams) });
      const handler = routes[route];
      if (!handler) {
        json(response, 404, { detail: "Not found", route });
        return;
      }
      handler(request, response, url, body);
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, port: server.address().port, calls });
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
  "GET /licenses/validate": (_request, response) =>
    json(response, 200, { plan_type: "studio-monthly", expiration_date: "2026-12-31" }),
  "GET /profiles": (_request, response) => json(response, 200, PROFILES),
  "GET /prompts/descriptions/public": (_request, response) => json(response, 200, DESCRIPTIONS),
  "GET /prompts/structures/public": (_request, response) => json(response, 200, STRUCTURES),
  "GET /music/history": (_request, response) => json(response, 200, HISTORY),
  "GET /credits/operation-costs": (_request, response) => json(response, 200, COSTS),
};

async function openApp(name, apiPort, heading = "Weekly Usage", expectLoading = false) {
  const userData = path.join(artifacts, `e2e-music-${name}`);
  fs.rmSync(userData, { recursive: true, force: true });
  const app = await electron.launch({
    args: ["dist-electron/main.cjs"],
    cwd: root,
    env: {
      ...process.env,
      CAMXORA_DEV_AUTH: "0",
      CAMXORA_USER_DATA_DIR: userData,
      CAMXORA_API_BASE_URL: `http://127.0.0.1:${apiPort}/api/v3`,
    },
  });
  const page = await app.firstWindow();
  await page.waitForLoadState("domcontentloaded");
  await page.locator("#email").fill("operator@example.com");
  await page.locator("#password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForTimeout(400);
  const onboarding = page.getByRole("button", { name: "Open studio anyway" });
  if (await onboarding.isVisible().catch(() => false)) {
    await onboarding.click();
  }
  await page.getByRole("heading", { name: heading }).waitFor({ timeout: 15000 });
  await page.getByRole("link", { name: "Music" }).click();
  if (expectLoading) {
    await page.locator('[data-testid="music-loading"]').waitFor({ timeout: 5000 });
    await page.locator('[data-testid="music-loading"]').waitFor({ state: "detached", timeout: 10000 });
  }
  await page.getByRole("heading", { name: "Music", exact: true }).waitFor({ timeout: 15000 });
  await page.waitForTimeout(500);
  return { app, page };
}

async function resize(app, page, width, height) {
  await app.evaluate(async ({ BrowserWindow }, size) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (window) window.setSize(size.width, size.height);
  }, { width, height });
  await page.waitForTimeout(250);
}

async function capture(app, page, file) {
  const dismiss = page.locator('.pointer-events-auto button[aria-label="Dismiss"]');
  while ((await dismiss.count()) > 0) {
    await dismiss.first().click();
  }
  const scrollTop = () => page.locator("main").evaluate((element) => element.scrollTo(0, 0));
  await scrollTop();
  await page.waitForTimeout(200);
  await resize(app, page, 1440, 900);
  await scrollTop();
  await page.screenshot({ path: path.join(artifacts, `${file}-1440.png`), fullPage: true });
  await resize(app, page, 1280, 800);
  await scrollTop();
  await page.screenshot({ path: path.join(artifacts, `${file}-1280.png`), fullPage: true });
  await resize(app, page, 1440, 900);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function ymd(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

async function readText(page, testId) {
  return page.locator(`[data-testid="${testId}"]`).innerText();
}

async function workspaceScenario() {
  const today = new Date();
  const todayText = ymd(today);
  const plusTwo = ymd(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 2));
  const tomorrow = ymd(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1));

  let draftBody = null;
  let polishBody = null;
  const routes = {
    ...baseRoutes,
    "GET /settings": (_request, response) => json(response, 200, settings()),
    "PATCH /settings": (_request, response, _url, body) =>
      json(response, 200, { ...settings(), ...body }),
    "POST /content-pools/titles/claim": (_request, response) =>
      json(response, 200, {
        kind: "titles",
        item: {
          id: 11,
          text: "Neon Road",
          used_count: 0,
          reservation_token: "res-token",
          reserved_by: "generation",
        },
      }),
    "POST /content-pools/albums/claim": (_request, response) =>
      json(response, 200, {
        kind: "albums",
        item: {
          id: 12,
          text: "After Hours",
          used_count: 0,
          reservation_token: "res-token",
          reserved_by: "generation",
        },
      }),
    "POST /content-pools/openings/claim": (_request, response) =>
      json(response, 200, {
        kind: "openings",
        item: {
          id: 13,
          text: "The city hums",
          secondary_text: "under sodium light",
          used_count: 0,
          reservation_token: "res-token",
          reserved_by: "generation",
        },
      }),
    "POST /content-pools/titles/finalize": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/albums/finalize": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/openings/finalize": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/titles/release": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/albums/release": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/openings/release": (_request, response) => json(response, 200, { ok: true }),
    "POST /generation/draft": (_request, response, _url, body) => {
      draftBody = body;
      json(response, 200, {
        title: "Neon Road",
        album: "After Hours",
        lyrics: "[verse]\nCity lights on the overpass\n[chorus]\nWe drive until the morning",
      });
    },
    "POST /generation/polish-lyrics": (_request, response, _url, body) => {
      polishBody = body;
      json(response, 200, {
        lyrics: "[verse]\nPolished line on the overpass\n[chorus]\nWe drive until the dawn",
        suno_queued: false,
      });
    },
  };

  const { server, port, calls } = await startApi(routes);
  const { app, page } = await openApp("workspace", port);
  try {
    const body = await page.locator("body").innerText();
    assert(body.includes("Run settings"), "Settings strip missing");
    assert(!body.includes("Loading music workspace..."), "Loading card must clear after bootstrap");
    assert(body.includes("Night Shift") && body.includes("Deep Focus"), "Profiles missing");
    assert(
      (await page.locator('[data-testid^="profile-toggle-primary-"]').count()) === 1 &&
        (await page.locator('[data-testid^="profile-toggle-secondary-"]').count()) === 1,
      "Each channel list must hide the channel already paired on the other side",
    );

    // Simple mode keeps Description + Songs per batch and hides the rest.
    assert(
      await page.locator('[data-testid="music-language"]').isVisible(),
      "Studio mode must show language",
    );
    await page.locator('[data-testid="music-simple-mode"]').click();
    await page.waitForTimeout(300);
    for (const testId of [
      "music-language",
      "music-creativity",
      "music-unique-opening",
      "music-strict",
      "music-history-window",
      "music-use-pools",
      "song-editor",
      "automation-structure",
    ]) {
      assert(
        (await page.locator(`[data-testid="${testId}"]`).count()) === 0,
        `${testId} must be hidden in simple mode`,
      );
    }
    assert(
      await page.locator('[data-testid="music-count"]').isVisible(),
      "Simple mode must keep Songs per batch",
    );
    assert(
      await page.locator('[data-testid="automation-description"]').isVisible(),
      "Simple mode must keep the Description prompt",
    );
    await page.locator('[data-testid="music-simple-mode"]').click();
    await page.waitForTimeout(300);

    // No save loop: applying API settings must not PATCH them back.
    await page.waitForTimeout(700);
    assert(
      calls.filter((call) => call.route === "PATCH /settings").length === 0,
      "Applying API settings must not trigger an autosave",
    );

    // Cost parity labels + default total.
    assert((await readText(page, "unit-cost-draft")).includes("Draft: 3 credits"), "Draft cost label");
    assert((await readText(page, "unit-cost-polish")).includes("Polish: 3 credits"), "Polish cost label");
    assert((await readText(page, "unit-cost-revisions")).includes("Revisions: 0 credits"), "Revisions label");
    assert((await readText(page, "unit-cost-suno")).includes("Suno: 7 credits"), "Suno label");
    assert((await readText(page, "unit-cost-image")).includes("Image: 5 credits"), "Image label");
    assert((await readText(page, "plan-line")).includes("1 day x 1 pair x 4 songs = 4 song jobs"), "Plan line");
    assert((await readText(page, "cost-total")) === "12", "Default total must be 12");
    assert(
      (await readText(page, "generate-button")).includes("Generate (12 credits)"),
      "Generate label must show 12 credits",
    );
    assert(
      await page.locator('[data-testid="toggle-auto-upload"]').isDisabled(),
      "Auto-Upload must stay disabled exactly as 1.7.1",
    );

    // Auto-Image → 92, image total 80.
    await page.locator('[data-testid="toggle-auto-image"]').click();
    await page.waitForTimeout(250);
    assert((await readText(page, "cost-total")) === "92", "Auto-Image total must be 92");
    assert((await readText(page, "cost-image")) === "80", "Auto-Image image total must be 80");
    await page.locator('[data-testid="toggle-auto-image"]').click();
    await page.waitForTimeout(250);

    // Auto-GSuno → 40 with 28 Suno.
    await page.locator('[data-testid="toggle-auto-gsuno"]').click();
    await page.waitForTimeout(250);
    assert((await readText(page, "cost-total")) === "40", "Auto-GSuno total must be 40");
    assert((await readText(page, "cost-suno")) === "28", "Auto-GSuno Suno total must be 28");

    // 3 days + GSuno → 120.
    await page.locator('[data-testid="music-to-date"]').fill(plusTwo);
    await page.waitForTimeout(250);
    assert((await readText(page, "planned-days")).includes("3 planned days"), "Planned days chip");
    assert((await readText(page, "cost-total")) === "120", "3-day GSuno total must be 120");
    assert((await readText(page, "generate-button")).includes("120 credits"), "3-day label");
    await page.locator('[data-testid="music-to-date"]').fill(todayText);
    await page.locator('[data-testid="toggle-auto-gsuno"]').click();
    await page.waitForTimeout(250);

    // Invalid range disables Generate.
    await page.locator('[data-testid="music-from-date"]').fill(tomorrow);
    await page.waitForTimeout(250);
    assert(
      (await readText(page, "planned-days")).includes("Choose a valid inclusive date range."),
      "Invalid range message missing",
    );
    assert(await page.locator('[data-testid="generate-button"]').isDisabled(), "Generate must disable");
    await page.locator('[data-testid="music-from-date"]').fill(todayText);
    await page.waitForTimeout(250);

    // Autosave: 400 ms debounce, one PATCH, Saved → idle, no loop.
    const range = page.locator('[data-testid="music-creativity"]');
    await range.focus();
    await range.press("End");
    await page.getByText("Saved", { exact: true }).waitFor({ timeout: 4000 });
    await page.waitForTimeout(900);
    const creativityPatches = calls.filter(
      (call) =>
        call.route === "PATCH /settings" && call.body && call.body.creativity === 100,
    );
    assert(
      creativityPatches.length === 1,
      `Autosave must PATCH exactly once per change (got ${creativityPatches.length}; all=${JSON.stringify(
        calls.filter((call) => call.route === "PATCH /settings").map((call) => call.body),
      )})`,
    );
    await page.waitForTimeout(3000);
    assert(
      (await readText(page, "save-status")).includes("Autosave on"),
      `Saved status must return to idle (got "${await readText(page, "save-status")}")`,
    );

    // Draft flow with pool seeds and avoid lists.
    await page.locator('[data-testid="music-use-pools"]').click();
    await page.locator('[data-testid="music-unique-opening"]').click();
    await page.waitForTimeout(600);
    await page.locator('[data-testid="draft-button"]').click();
    await page.waitForTimeout(700);
    assert((await page.inputValue('[data-testid="song-title"]')) === "Neon Road", "Draft title");
    assert(
      (await page.inputValue('[data-testid="song-album"]')) === "After Hours",
      "Draft album",
    );
    assert(
      (await readText(page, "seed-notice")).includes("Neon Road") &&
        (await readText(page, "seed-notice")).includes("The city hums"),
      "Seed notice missing pool seeds",
    );
    assert(draftBody, "Draft request missing");
    assert(
      String(draftBody.description).includes("Inspiration (do not copy words): Neon Road / After Hours"),
      "Draft description must carry the inspiration suffix",
    );
    assert(
      Array.isArray(draftBody.avoid_titles) && draftBody.avoid_titles.includes("First Light"),
      "Draft avoid list must include history titles",
    );
    assert(
      String(draftBody.forced_opening).includes("The city hums"),
      "Draft must pass the claimed opening",
    );
    assert(draftBody.channel_profile_id === "profile-1", "Draft must use the primary profile");
    assert(
      calls.filter((call) => call.route === "POST /content-pools/titles/finalize").length === 1,
      "Pool claims must finalize after success",
    );

    // Polish flow + undo.
    await page.locator('[data-testid="polish-button"]').click();
    await page.waitForTimeout(600);
    assert(
      (await page.inputValue('[data-testid="song-lyrics"]')).includes("Polished line"),
      "Polish must replace lyrics",
    );
    assert(polishBody && polishBody.strength === 85, "Polish strength must be sent");
    assert(polishBody.channel_profile_id === "profile-1", "Polish profile id missing");
    await page.locator('[data-testid="undo-polish"]').click();
    await page.waitForTimeout(200);
    assert(
      (await page.inputValue('[data-testid="song-lyrics"]')).includes("City lights"),
      "Undo must restore the previous lyrics",
    );

    // History row loads the composer and clears the seed notice.
    await page.locator('[data-testid="history-row-song-1"]').click();
    await page.waitForTimeout(300);
    assert(
      (await page.inputValue('[data-testid="song-title"]')) === "First Light",
      "History row title must load",
    );
    assert(
      (await page.inputValue('[data-testid="song-lyrics"]')).includes("Opening line"),
      "History row lyrics must load",
    );
    assert(
      (await page.inputValue('[data-testid="automation-description"]')) === "desc-1",
      "History row description id must load",
    );
    assert(
      (await page.inputValue('[data-testid="automation-structure"]')) === "struct-1",
      "History row structure id must load",
    );
    assert(
      (await page.locator('[data-testid="seed-notice"]').count()) === 0,
      "Seed notice must clear on row load",
    );

    // Copy actions use the system clipboard.
    await page.locator('[data-testid="copy-title"]').click();
    await page.waitForTimeout(150);
    const clipTitle = await app.evaluate(({ clipboard }) => clipboard.readText());
    assert(clipTitle === "First Light", `Copy title must write the clipboard (got "${clipTitle}")`);
    await page.locator('[data-testid="copy-both"]').click();
    await page.waitForTimeout(150);
    const clipBoth = await app.evaluate(({ clipboard }) => clipboard.readText());
    assert(
      clipBoth.replace(/\r\n/g, "\n").startsWith("First Light\n\n[verse]\nOpening line"),
      `Copy both must include the title and lyrics (got "${clipBoth}")`,
    );

    // History filters: last batch only, then an empty date range.
    await page.locator('[data-testid="history-last-batch"]').click();
    await page.waitForTimeout(200);
    assert(
      (await page.locator('[data-testid="history-row-song-1"]').count()) === 1 &&
        (await page.locator('[data-testid="history-row-song-9"]').count()) === 0,
      "Last batch only filter must hide older rows",
    );
    await page.locator('[data-testid="history-last-batch"]').click();
    await page.locator('[data-testid="history-from"]').fill("2026-11-01");
    await page.locator('[data-testid="history-to"]').fill("2026-11-01");
    await page.waitForTimeout(200);
    assert(
      (await readText(page, "history-empty")).includes("No history rows match the current filters."),
      "Empty history state missing",
    );
    await page.locator('[data-testid="history-from"]').fill("");
    await page.locator('[data-testid="history-to"]').fill("");
    await page.waitForTimeout(200);
    assert((await page.locator('[data-testid="history-row-song-1"]').count()) === 1, "History must restore");

    await capture(app, page, "music-workspace");

    await resize(app, page, 1440, 900);
    await page.locator("main").evaluate((element) => element.scrollTo(0, element.scrollHeight));
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(artifacts, "music-history-1440.png"),
      fullPage: true,
    });
    await resize(app, page, 1280, 800);
    await page.locator("main").evaluate((element) => element.scrollTo(0, element.scrollHeight));
    await page.waitForTimeout(200);
    await page.screenshot({
      path: path.join(artifacts, "music-history-1280.png"),
      fullPage: true,
    });
    await resize(app, page, 1440, 900);

    const text = await page.locator('[data-testid="music-page"]').innerText();
    assert(!text.includes("operator@example.com"), "Email must not leak into the music page");
    const bodyText = await page.locator("body").innerText();
    assert(!bodyText.includes("e2e-token"), "Access token must not leak into the page");
  } finally {
    await app.close();
    server.close();
  }
}

async function generateScenario() {
  const batchBodies = [];
  const routes = {
    ...baseRoutes,
    "GET /settings": (_request, response) =>
      json(response, 200, {
        ...settings(),
        imageSourceMode: "manual",
        sunoOutputDir: runRoot,
      }),
    "PATCH /settings": (_request, response, _url, body) =>
      json(response, 200, { ...settings(), ...body }),
    "POST /batches": (_request, response, _url, body) => {
      batchBodies.push(body);
      if (body.from_date === "2026-11-19") {
        json(response, 500, { detail: "Batch service unavailable" });
        return;
      }
      json(response, 201, {
        batch_id: `batch-${body.from_date}`,
        status: "queued",
        song_count: body.song_count,
        from_date: body.from_date,
        to_date: body.to_date,
        planned_days: 1,
        ok_run_dir: null,
        alt_run_dir: null,
      });
    },
    "GET /batches/batch-2026-11-18": (_request, response) =>
      json(response, 200, {
        batch_id: "batch-2026-11-18",
        status: "completed",
        total_songs: 4,
        drafts_completed: 4,
        drafts_failed: 0,
        suno_submitted: 4,
        suno_completed: 4,
        suno_failed: 0,
        audio_downloaded: 4,
        images_completed: 0,
        ok_run_dir: null,
        alt_run_dir: null,
      }),
  };

  const { server, port } = await startApi(routes);
  const { app, page } = await openApp("generate", port);
  try {
    await page.locator('[data-testid="music-simple-mode"]').click();
    await page.waitForTimeout(300);
    await page.locator('[data-testid="music-from-date"]').fill("2026-11-17");
    await page.locator('[data-testid="music-to-date"]').fill("2026-11-19");
    await page.waitForTimeout(300);

    await page.locator('[data-testid="generate-button"]').click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor({ timeout: 3000 });
    assert((await dialog.innerText()).includes("3 planned days"), "Confirmation must name the plan");
    await dialog.getByRole("button", { name: "Generate", exact: true }).click();

    await page.locator('[data-testid="batch-summary"]').filter({ hasText: "Created 2 batch runs" }).waitFor({ timeout: 15000 });
    const summary = await readText(page, "batch-summary");
    assert(
      summary.includes("Created 2 batch runs across 3 planned days and 1 channel pair."),
      "Partial success summary must report created batches",
    );
    assert(summary.includes("2026-11-19"), "Partial failure must name the missing day");

    assert(batchBodies.length === 3, "Generate must POST one batch per day × pair");
    assert(
      batchBodies.map((body) => body.from_date).join(",") === "2026-11-17,2026-11-18,2026-11-19",
      "Batch calls must use consecutive run dates",
    );
    for (const body of batchBodies) {
      assert(body.pairing_mode === "match_key", "Pairing mode must be match_key");
      assert(body.ok_profile_id === "profile-1" && body.alt_profile_id === "profile-2", "Pair ids");
      assert(body.from_date === body.to_date, "Each batch must run on a single date");
      assert(body.structure_mode === "suno", "Simple mode must let Suno pick the structure");
      assert(body.structure_id === null, "Simple mode must not send a structure id");
      assert(body.language === "en", "Simple mode must ignore the language override");
      assert(body.creativity_level === 55, "Simple mode must use the default creativity");
      assert(
        body.auto_gen_image === false &&
          body.auto_gsuno === false &&
          body.auto_video_after_suno === false &&
          body.auto_upload_youtube === false,
        "Simple mode must not carry pipeline automation",
      );
      assert(
        body.ok_run_dir === path.join(runRoot, "night-shift", body.from_date),
        `OK run dir for ${body.from_date}`,
      );
      assert(
        body.alt_run_dir === path.join(runRoot, "deep-focus", body.from_date),
        `ALT run dir for ${body.from_date}`,
      );
    }
    for (const date of ["2026-11-17", "2026-11-18"]) {
      assert(
        fs.existsSync(path.join(runRoot, "night-shift", date)),
        `Manual OK directory must exist for ${date}`,
      );
      assert(
        fs.existsSync(path.join(runRoot, "deep-focus", date)),
        `Manual ALT directory must exist for ${date}`,
      );
    }

    await page.getByText(/completed · 4\/4 drafts/).waitFor({ timeout: 8000 });
    const status = await readText(page, "batch-status");
    assert(status.includes("completed · 4/4 drafts"), "Polled batch status must render");
  } finally {
    await app.close();
    server.close();
  }
}

async function emptyScenario() {
  const routes = {
    ...baseRoutes,
    "GET /settings": (_request, response) => json(response, 200, settings()),
    "GET /profiles": (_request, response) => json(response, 200, []),
    "GET /music/history": (_request, response) =>
      json(response, 200, { batches: [], summary: "", updated_at: "" }),
    "GET /credits/operation-costs": (_request, response) =>
      json(response, 500, { detail: "Costs unavailable" }),
    "GET /prompts/descriptions/public": (_request, response) =>
      setTimeout(() => json(response, 200, DESCRIPTIONS), 1200),
  };
  const { server, port } = await startApi(routes);
  const { app, page } = await openApp("empty", port, "Weekly Usage", true);
  try {
    const body = await page.locator("body").innerText();
    assert(
      (body.match(/No profiles available yet\./g) ?? []).length === 2,
      "Both channel cards need the empty state",
    );
    assert(body.includes("No history rows match the current filters."), "History empty copy");
    assert(await page.locator('[data-testid="generate-button"]').isDisabled(), "Generate must disable");
    assert(
      (await readText(page, "unit-cost-draft")).includes("Draft: unavailable"),
      "Optional cost failures must degrade to an unavailable label",
    );
    assert(
      (await page.locator('[data-testid="music-error"]').count()) === 0,
      "Optional cost failures must not fail the workspace",
    );
    await capture(app, page, "music-empty");
  } finally {
    await app.close();
    server.close();
  }
}

async function errorScenario() {
  const routes = {
    ...baseRoutes,
    "GET /settings": (_request, response) => json(response, 200, settings()),
    "GET /profiles": (_request, response) => json(response, 500, { detail: "Profiles unavailable" }),
  };
  const { server, port } = await startApi(routes);
  const { app, page } = await openApp("error", port);
  try {
    await page.getByText("Unable to load the music workspace from the current backend contracts.").waitFor({
      timeout: 10000,
    });
    assert((await page.locator('[data-testid="music-error"]').count()) === 1, "Error banner missing");
    assert((await page.getByRole("button", { name: "Retry" }).count()) === 1, "Retry missing");
    await capture(app, page, "music-error");
  } finally {
    await app.close();
    server.close();
  }
}

async function failureScenario() {
  const routes = {
    ...baseRoutes,
    "GET /settings": (_request, response) =>
      json(response, 200, { ...settings(), useContentPools: true, uniqueOpening: true }),
    "PATCH /settings": (_request, response, _url, body) =>
      json(response, 200, { ...settings(), ...body }),
    "POST /content-pools/titles/claim": (_request, response) =>
      json(response, 200, {
        kind: "titles",
        item: { id: 21, text: "Seed Title", used_count: 0, reservation_token: "fail-token" },
      }),
    "POST /content-pools/albums/claim": (_request, response) =>
      json(response, 200, {
        kind: "albums",
        item: { id: 22, text: "Seed Album", used_count: 0, reservation_token: "fail-token" },
      }),
    "POST /content-pools/openings/claim": (_request, response) =>
      json(response, 200, {
        kind: "openings",
        item: {
          id: 23,
          text: "Seed opening",
          secondary_text: null,
          used_count: 0,
          reservation_token: "fail-token",
        },
      }),
    "POST /content-pools/titles/finalize": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/albums/finalize": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/openings/finalize": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/titles/release": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/albums/release": (_request, response) => json(response, 200, { ok: true }),
    "POST /content-pools/openings/release": (_request, response) => json(response, 200, { ok: true }),
    "POST /generation/draft": (_request, response) =>
      json(response, 500, { detail: "Draft provider unavailable" }),
    "POST /generation/polish-lyrics": (_request, response) =>
      json(response, 500, { detail: "Polish provider unavailable" }),
  };

  const { server, port, calls } = await startApi(routes);
  const { app, page } = await openApp("failure", port);
  try {
    await page.locator('[data-testid="draft-button"]').click();
    await page.getByText("Draft provider unavailable").waitFor({ timeout: 8000 });
    assert(
      (await page.inputValue('[data-testid="song-title"]')) === "",
      "A failed draft must not overwrite the composer",
    );
    assert(
      calls.filter((call) => call.route.endsWith("/release")).length === 3,
      "A failed draft must release every claimed pool item",
    );
    assert(
      calls.filter((call) => call.route.endsWith("/finalize")).length === 0,
      "A failed draft must not finalize claims",
    );
    assert(
      (await page.locator('[data-testid="seed-notice"]').count()) === 0,
      "A failed draft must not show a seed notice",
    );

    await page.locator('[data-testid="song-lyrics"]').fill("Keep these lines");
    await page.locator('[data-testid="polish-button"]').click();
    await page.getByText("Polish provider unavailable").waitFor({ timeout: 8000 });
    assert(
      (await page.inputValue('[data-testid="song-lyrics"]')) === "Keep these lines",
      "A failed polish must keep the original lyrics",
    );
    await capture(app, page, "music-failure");
  } finally {
    await app.close();
    server.close();
  }
}

fs.rmSync(runRoot, { recursive: true, force: true });

await workspaceScenario();
await generateScenario();
await emptyScenario();
await errorScenario();
await failureScenario();
console.log(JSON.stringify({ music: "ok", artifacts, runRoot }));
