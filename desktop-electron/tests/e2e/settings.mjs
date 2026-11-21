/* global HTMLInputElement, document, window */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/**
 * Settings E2E: Profiles, Publication and Preferences against a fixture API.
 *
 * Proves profile create/edit/delete round-trips, auto-slug, dirty guards,
 * save-all/discard, publication validation, preferences save, the P7/P8 notes,
 * the deep link `/settings?profile=<id>`, and the loading/empty/error states.
 */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

let currentStep = "boot";
function step(name) {
  currentStep = name;
  process.stdout.write(`[settings] ${name}\n`);
}
const watchdog = setTimeout(() => {
  console.error(`settings e2e timed out at step: ${currentStep}`);
  process.exit(1);
}, 600000);
watchdog.unref?.();

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
  channel_profile_count: 2,
  onboarding_paid: true,
  desktop_access: true,
  products: ["desktop"],
  pending_verification_code: null,
  verification_code_expires_at: null,
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

function profileFixture(overrides) {
  return {
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
    youtube_config: {
      visibility: "unlisted",
      category: "10",
      keywords: [],
      tags: [],
    },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

const PROFILES = [
  profileFixture({}),
  profileFixture({
    id: "profile-2",
    name: "Deep Focus",
    folder_name: "deep-focus",
    run_prefix: "DF",
    output_resolution: "1080x1920",
    image_config: { mode: "thumb_only" },
    youtube_config: {
      visibility: "scheduled",
      publish_at: "21:35",
      category: "10",
      description: "Deep focus sessions.",
      keywords: ["focus"],
      tags: ["instrumental"],
      playlist: "PL2",
      title_template: "{title} (Official Audio)",
      description_template: "{album} for {channel}",
      made_for_kids: false,
      ai_use: false,
    },
  }),
];

const CONNECTIONS = [
  {
    profile_id: "profile-1",
    profile_name: "Night Shift",
    status: "connected",
    channel_id: "UC-night",
    channel_title: "Night Shift Radio",
    session_id: null,
    channels: [],
    message: null,
  },
];

const SETTINGS = {
  ffmpegPath: "C:\\tools\\ffmpeg.exe",
  sunoOutputDir: "D:\\Suno",
  perfMusicWorkers: 1,
  perfImageWorkers: 4,
  perfExportWorkers: 2,
  perfMergeWorkers: 1,
  perfYouTubeWorkers: 1,
  youtubeUploadChunkSizeMb: 256,
  outputResolution: "1920x1080",
  styleStrength: 80,
  imageSourceMode: "ai",
  imageBackgroundSourceMode: "category",
  imageBackgroundPromptSource: "custom",
  imageThumbnailSourceMode: "category",
  imageThumbnailPromptSource: "custom",
  thumbnailReferenceMode: "background_text",
  imagePromptLibraryOnly: false,
  defaultDescriptionId: "desc-admin-1",
  defaultStructureId: "struct-admin-1",
  defaultMoodId: "mood-admin-1",
  sunoDefaultVersion: "v6",
  sunoMergeEnabled: false,
  sunoMergeGroupSize: 0,
  sunoTimeoutMs: 90000,
  sunoRetryCount: 3,
  // A key this build does not read: a settings patch must leave it alone.
  customSunoPreset: "keep-me",
};

function promptOption(id, name, owned, matchKey = null) {
  return { id, name, is_owned: owned, match_key: matchKey };
}

const PROMPT_WORKSPACE = {
  descriptions: [
    promptOption("desc-admin-1", "Camxora Anthem", false, "anthem"),
    promptOption("desc-admin-2", "Night Drive", false),
    promptOption("desc-user-1", "My Late Night", true),
  ],
  structures: [
    promptOption("struct-admin-1", "Radio Edit", false),
    promptOption("struct-user-1", "My Build", true),
  ],
  moods: [promptOption("mood-admin-1", "Cinematic", false), promptOption("mood-user-1", "Restless", true)],
};

function userPrompt(id, name, content) {
  return {
    id,
    name,
    content,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
  };
}

const MY_PROMPTS = {
  descriptions: [userPrompt("desc-user-1", "My Late Night", "Slow, warm, analog.")],
  structures: [userPrompt("struct-user-1", "My Build", "[Verse]\n[Chorus]")],
  moods: [userPrompt("mood-user-1", "Restless", "Anxious, driving energy.")],
};

function poolRows(kind, count) {
  return Array.from({ length: count }, (_, index) => {
    const id = count - index;
    if (kind === "openings") {
      return {
        id,
        text: `Opening line ${id}`,
        secondary_text: index % 3 === 0 ? `Response ${id}` : null,
        used_count: index < 20 ? 1 : 0,
        created_at: "2026-01-01T00:00:00Z",
      };
    }
    return {
      id,
      text: `${kind === "titles" ? "Title" : "Album"} ${id}`,
      used_count: 0,
      created_at: "2026-01-02T00:00:00Z",
    };
  });
}

const POOLS = {
  openings: poolRows("openings", 120),
  titles: poolRows("titles", 2),
  albums: [],
};


function json(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

function readJson(request) {
  return new Promise((resolve) => {
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk;
    });
    request.on("end", () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        resolve({});
      }
    });
  });
}

function createBackend(options = {}) {
  const state = {
    profiles: (options.profiles ?? PROFILES).map((item) => structuredClone(item)),
    settings: { ...(options.settings ?? SETTINGS) },
    connections: (options.connections ?? CONNECTIONS).map((item) => structuredClone(item)),
    promptWorkspace: structuredClone(options.promptWorkspace ?? PROMPT_WORKSPACE),
    myPrompts: structuredClone(options.myPrompts ?? MY_PROMPTS),
    pools: structuredClone(options.pools ?? POOLS),
    playlists: [
      { id: "PL1", title: "Night Mixes" },
      { id: "PL2", title: "Focus Deep" },
    ],
    calls: [],
    failures: options.failures ?? {},
  };

  async function handle(request, response, pathname) {
    const method = request.method ?? "GET";
    const route = `${method} ${pathname}`;
    if (state.failures[route]) {
      json(response, 500, { detail: `${route} failed` });
      return;
    }
    if (options.slow && (route === "GET /profiles" || route === "GET /settings")) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }

    if (route === "POST /auth/login") {
      json(response, 200, { access_token: "e2e-token", refresh_token: "e2e-refresh", expires_in: 3600 });
      return;
    }
    if (route === "GET /users/me") return json(response, 200, ME);
    if (route === "GET /stats/dashboard") return json(response, 200, STATS);
    if (route === "GET /licenses/validate") return json(response, 404, { detail: "No licence" });

    if (route === "GET /profiles") return json(response, 200, state.profiles);
    if (route === "POST /profiles") {
      const body = await readJson(request);
      state.calls.push({ method, path: pathname, body });
      const now = new Date().toISOString();
      const created = {
        id: `profile-created-${state.profiles.length + 1}`,
        user_id: "user-1",
        name: body.name,
        folder_name: body.folder_name ?? "profile",
        run_prefix: body.run_prefix ?? "",
        logo_path: body.logo_base64 ? "uploads/logos/created.png" : null,
        video_template_id: null,
        reel_template_id: null,
        output_resolution: body.output_resolution ?? "1920x1080",
        image_config: body.image_config ?? {},
        youtube_config: {},
        created_at: now,
        updated_at: now,
      };
      state.profiles.push(created);
      json(response, 201, created);
      return;
    }

    const profileMatch = pathname.match(/^\/profiles\/([^/]+)$/);
    if (profileMatch && method === "PUT") {
      const body = await readJson(request);
      state.calls.push({ method, path: pathname, body });
      const current = state.profiles.find((item) => item.id === profileMatch[1]);
      if (!current) return json(response, 404, { detail: "Profile not found" });
      for (const key of ["name", "folder_name", "run_prefix", "output_resolution"]) {
        if (body[key] !== undefined) current[key] = body[key];
      }
      if (body.image_config) {
        current.image_config = { ...current.image_config, ...body.image_config };
      }
      if (body.youtube_config) {
        current.youtube_config = { ...current.youtube_config, ...body.youtube_config };
      }
      if (body.video_template_id !== undefined) current.video_template_id = body.video_template_id;
      if (body.reel_template_id !== undefined) current.reel_template_id = body.reel_template_id;
      if (body.logo_base64) current.logo_path = `uploads/logos/${current.id}.png`;
      if (Array.isArray(body.cover_images) && body.cover_images.length > 0) {
        current.image_config = {
          ...current.image_config,
          cover_paths: [`uploads/covers/${current.id}.png`],
        };
      }
      current.updated_at = new Date().toISOString();
      json(response, 200, current);
      return;
    }
    if (profileMatch && method === "DELETE") {
      state.calls.push({ method, path: pathname });
      state.profiles = state.profiles.filter((item) => item.id !== profileMatch[1]);
      state.connections = state.connections.filter((item) => item.profile_id !== profileMatch[1]);
      json(response, 200, { message: "Profile deleted." });
      return;
    }

    if (route === "GET /settings") return json(response, 200, state.settings);
    if (route === "PATCH /settings") {
      const body = await readJson(request);
      state.calls.push({ method, path: pathname, body });
      state.settings = { ...state.settings, ...body };
      json(response, 200, state.settings);
      return;
    }

    const workspaceMatch = pathname.match(/^\/prompts\/(descriptions|structures|moods)\/workspace$/);
    if (workspaceMatch && method === "GET") {
      return json(response, 200, state.promptWorkspace[workspaceMatch[1]] ?? []);
    }

    const myPromptsMatch = pathname.match(/^\/prompts\/me\/(descriptions|structures|moods)$/);
    if (myPromptsMatch && method === "GET") {
      return json(response, 200, state.myPrompts[myPromptsMatch[1]] ?? []);
    }
    if (myPromptsMatch && method === "POST") {
      const kind = myPromptsMatch[1];
      const body = await readJson(request);
      state.calls.push({ method, path: pathname, body });
      const created = userPrompt(`created-${kind}-${state.myPrompts[kind].length + 1}`, body.name, body.content);
      state.myPrompts[kind].push(created);
      state.promptWorkspace[kind].push(promptOption(created.id, created.name, true));
      json(response, 201, created);
      return;
    }

    const myPromptMatch = pathname.match(/^\/prompts\/me\/(descriptions|structures|moods)\/([^/]+)$/);
    if (myPromptMatch && method === "PUT") {
      const kind = myPromptMatch[1];
      const id = decodeURIComponent(myPromptMatch[2]);
      const body = await readJson(request);
      state.calls.push({ method, path: pathname, body });
      const current = state.myPrompts[kind].find((item) => item.id === id);
      if (!current) return json(response, 404, { detail: "Prompt not found" });
      current.name = body.name;
      current.content = body.content;
      current.updated_at = new Date().toISOString();
      const option = state.promptWorkspace[kind].find((item) => item.id === id);
      if (option) option.name = body.name;
      json(response, 200, current);
      return;
    }
    if (myPromptMatch && method === "DELETE") {
      const kind = myPromptMatch[1];
      const id = decodeURIComponent(myPromptMatch[2]);
      state.calls.push({ method, path: pathname });
      state.myPrompts[kind] = state.myPrompts[kind].filter((item) => item.id !== id);
      state.promptWorkspace[kind] = state.promptWorkspace[kind].filter((item) => item.id !== id);
      json(response, 200, { message: "Prompt archived." });
      return;
    }

    if (route === "GET /content-pools/stats") {
      const stat = (kind) => ({
        total: state.pools[kind].length,
        unused: state.pools[kind].filter((item) => item.used_count === 0).length,
      });
      return json(response, 200, {
        openings: stat("openings"),
        titles: stat("titles"),
        albums: stat("albums"),
      });
    }
    const poolMatch = pathname.match(/^\/content-pools\/(openings|titles|albums)$/);
    if (poolMatch && method === "GET") {
      const kind = poolMatch[1];
      const url = new URL(request.url ?? "/", "http://127.0.0.1");
      const limit = Number(url.searchParams.get("limit") ?? 100);
      const offset = Number(url.searchParams.get("offset") ?? 0);
      state.calls.push({ method, path: pathname, query: { limit, offset } });
      const rows = state.pools[kind];
      json(response, 200, {
        kind,
        total: rows.length,
        limit,
        offset,
        items: rows.slice(offset, offset + limit),
      });
      return;
    }

    if (route === "GET /youtube/connections") {
      return json(response, 200, { connections: state.connections });
    }
    const connectionMatch = pathname.match(/^\/youtube\/profiles\/([^/]+)\/connection$/);
    if (connectionMatch && method === "DELETE") {
      state.calls.push({ method, path: pathname });
      state.connections = state.connections.filter((item) => item.profile_id !== connectionMatch[1]);
      json(response, 200, { message: "Disconnected." });
      return;
    }

    const playlistsMatch = pathname.match(/^\/youtube\/profiles\/([^/]+)\/playlists$/);
    if (playlistsMatch && method === "GET") {
      const connected = state.connections.some(
        (item) => item.profile_id === playlistsMatch[1] && item.status === "connected",
      );
      if (!connected) return json(response, 400, { detail: "No channel connected" });
      return json(response, 200, { playlists: state.playlists });
    }
    if (playlistsMatch && method === "POST") {
      const body = await readJson(request);
      state.calls.push({ method, path: pathname, body });
      const created = { id: `PL${state.playlists.length + 1}`, title: body.title };
      state.playlists.push(created);
      json(response, 201, created);
      return;
    }

    json(response, 404, { detail: `No fixture for ${route}` });
  }

  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const pathname = url.pathname.replace(/^\/api\/v3/, "");
    void handle(request, response, pathname).catch((error) => {
      json(response, 500, { detail: String(error) });
    });
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, state, port: server.address().port });
    });
  });
}

async function openApp(name, apiPort, options = {}) {
  const userData = path.join(artifacts, `e2e-settings-${name}`);
  fs.rmSync(userData, { recursive: true, force: true });
  if (options.seedTemplates) {
    const fixture = path.join(root, "tests", "fixtures", "vizzy", "trap-motion.camxora-vizzy.json");
    for (const [id, kind, width, height, label] of [
      ["night-drive-long", "long", 1920, 1080, "Night Drive Long"],
      ["night-drive-reel", "reel", 1080, 1920, "Night Drive Reel"],
    ]) {
      const dir = path.join(userData, "templates", id);
      fs.mkdirSync(dir, { recursive: true });
      fs.copyFileSync(fixture, path.join(dir, "template.json"));
      fs.writeFileSync(
        path.join(dir, "pipeline.json"),
        JSON.stringify(
          {
            schemaVersion: 1,
            name: label,
            kind,
            project: "template.json",
            output: { width, height, fps: 30 },
            duration: { mode: "audio" },
            bindings: { audio: { mode: "replace" } },
            requirements: { renderer: "vizzy", minVersion: "2.0.0", features: ["audio-analysis"] },
            createdAt: "2026-11-19T00:00:00.000Z",
          },
          null,
          2,
        ) + "\n",
      );
    }
  }
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
  page.setDefaultTimeout(8000);
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
  return { app, page };
}

/**
 * Closing a window whose Settings tab has unsaved changes can be held by the
 * page's `beforeunload` handler, which leaves Playwright waiting forever.
 * Bound the graceful close and force-exit the app if it does not finish.
 */
async function closeApp(app) {
  try {
    await Promise.race([
      app.close(),
      new Promise((resolve) => setTimeout(resolve, 5000)),
    ]);
  } finally {
    try {
      await app.evaluate(({ app: electronApp }) => electronApp.exit(0));
    } catch {
      // Already closed.
    }
  }
}

async function resize(app, page, width, height) {
  await app.evaluate(async ({ BrowserWindow }, size) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (window) window.setSize(size.width, size.height);
  }, { width, height });
  await page.waitForTimeout(250);
}

async function capture(app, page, file) {
  step(`${file}: capture`);
  await page.evaluate(() => {
    const scroller = document.querySelector("main");
    if (scroller) scroller.scrollTop = 0;
  });
  await resize(app, page, 1440, 900);
  await page.screenshot({ path: path.join(artifacts, `${file}-1440.png`), timeout: 15000 });
  await resize(app, page, 1280, 800);
  await page.screenshot({ path: path.join(artifacts, `${file}-1280.png`), timeout: 15000 });
  await resize(app, page, 1440, 900);
}

async function chooseOption(scope, target, value) {
  const trigger = typeof target === "string" ? scope.locator(target) : target;
  await trigger.click();
  await scope.locator(`[data-value="${value}"]`).click();
}

async function readSelectOptions(scope, selector) {
  await scope.locator(selector).click();
  const texts = await scope.locator("[data-value]").allInnerTexts();
  await scope.keyboard.press("Escape");
  return texts;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function pause(page, ms = 150) {
  return page.waitForTimeout(ms);
}

async function openSettings(page, profileId) {
  const hash = profileId ? `#/settings?profile=${profileId}` : "#/settings";
  await page.evaluate((value) => {
    window.location.hash = value;
  }, hash);
  await page.getByRole("heading", { name: "Settings" }).waitFor({ timeout: 10000 });
  await pause(page, 400);
}

async function settingsLoading() {
  step("loading: start");
  const { server, port } = await createBackend({ slow: true });
  const { app, page } = await openApp("loading", port);
  try {
    await page.evaluate(() => {
      window.location.hash = "#/settings";
    });
    await page.getByRole("heading", { name: "Settings" }).waitFor({ timeout: 10000 });
    const skeleton = page.locator('[data-testid="settings-profiles-loading"]');
    await skeleton.waitFor({ timeout: 5000 });
    assert(await skeleton.isVisible(), "Profiles must show a per-tab skeleton while loading");
    await page.getByRole("tab", { name: /Preferences/ }).click();
    const preferencesSkeleton = page.locator('[data-testid="settings-preferences-loading"]');
    await preferencesSkeleton.waitFor({ timeout: 5000 });
    assert(await preferencesSkeleton.isVisible(), "Preferences must show a per-tab skeleton while loading");
    await page.locator("#settings-preferences-image-workers").waitFor({ timeout: 8000 });
    step("loading: done");
  } finally {
    await closeApp(app);
    server.close();
  }
}

async function settingsSuccess() {
  step("success: start");
  const { server, state, port } = await createBackend();
  const { app, page } = await openApp("success", port, { seedTemplates: true });
  try {
    // Deep link selects the requested profile on mount.
    await openSettings(page, "profile-1");
    step("success: opened settings");
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Night Shift",
      "Deep link must select the requested profile",
    );

    // Shell: all eight live tabs, immediate-action note, no placeholder copy.
    assert((await page.getByRole("tab").count()) === 8, "Settings must render eight live tabs");
    const tabNames = (await page.getByRole("tab").allInnerTexts()).map((text) => text.trim());
    assert(
      tabNames.join("|") ===
        "Profiles|Publication|Preferences|Descriptions|Structures|Moods|Pools|Suno",
      `All eight tabs must render, got: ${tabNames.join("|")}`,
    );
    const navText = await page.getByRole("tablist", { name: "Settings sections" }).innerText();
    const pageText = await page.locator("body").innerText();
    assert(
      pageText.includes("Defaults save with Save all") &&
        pageText.includes("pool refresh act immediately"),
      "Immediate-action note missing",
    );
    assert(!navText.includes("arrive in P8"), "The P8 placeholder note must be gone");

    // Search and select.
    const list = page.locator('[data-testid="settings-profile-list"]');
    await page.getByLabel("Search profiles").fill("deep");
    await pause(page);
    assert((await list.getByRole("button", { name: /Deep Focus/ }).count()) === 1, "Search must match the name");
    await page.getByLabel("Search profiles").fill("df");
    await pause(page);
    assert((await list.getByRole("button", { name: /Deep Focus/ }).count()) === 1, "Search must match the prefix");
    await page.getByLabel("Search profiles").fill("");
    await pause(page);

    await list.getByRole("button", { name: /Deep Focus/ }).click();
    await pause(page);
    step("success: search/select");
    assert((await page.locator("#settings-profile-name").inputValue()) === "Deep Focus", "Select must load the profile");
    assert((await page.locator("#settings-profile-folder").inputValue()) === "deep-focus", "Folder must load");
    assert(
      (await page.locator("#settings-profile-resolution").getAttribute("data-selected-value")) === "1080x1920",
      "Resolution must load",
    );

    // Dirty guard on profile switch.
    const guardPrefix = await page.locator("#settings-profile-prefix").inputValue();
    await page.locator("#settings-profile-prefix").fill("GUARD");
    await list.getByRole("button", { name: /Night Shift/ }).click();
    await page.getByRole("dialog").getByText("Discard unsaved profile changes?").waitFor();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
    assert(
      (await page.locator("#settings-profile-prefix").inputValue()) === "GUARD",
      "Cancel must keep the draft",
    );
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await pause(page);
    step("success: dirty guard");
    assert(
      (await page.locator("#settings-profile-prefix").inputValue()) === guardPrefix,
      "Cancel must revert the draft",
    );

    // New profile with auto-slug.
    await list.getByRole("button", { name: "New", exact: true }).click();
    await pause(page);
    await page.locator("#settings-profile-name").fill("Beattok Remixes");
    await pause(page);
    assert(
      (await page.locator("#settings-profile-folder").inputValue()) === "beattok-remixes",
      "Folder must auto-slug from the name",
    );
    await page.locator("#settings-profile-folder").fill("beattok-custom");
    await page.locator("#settings-profile-name").fill("Beattok Remixes Two");
    await pause(page);
    assert(
      (await page.locator("#settings-profile-folder").inputValue()) === "beattok-custom",
      "Folder must stay once edited",
    );
    await page.locator("#settings-profile-prefix").fill("BT");
    await chooseOption(page, "#settings-profile-resolution", "1080x1920");
    await page.getByRole("button", { name: "Create profile" }).click();
    await page.getByText("Created profile").waitFor({ timeout: 5000 });
    const createCall = state.calls.find((call) => call.method === "POST" && call.path === "/profiles");
    assert(Boolean(createCall), "Create must POST /profiles");
    assert(createCall.body.name === "Beattok Remixes Two", "Create must send the name");
    assert(createCall.body.folder_name === "beattok-custom", "Create must send the edited folder");
    assert(createCall.body.run_prefix === "BT", "Create must send the run prefix");
    step("success: created profile");
    assert(
      (await list.getByRole("button", { name: /Beattok Remixes Two/ }).count()) === 1,
      "Created profile must appear in the list",
    );

    // Edit and save.
    await page.locator("#settings-profile-prefix").fill("BTX");
    await pause(page);
    assert(
      (await page.locator('[data-testid="settings-footer-status"]').innerText()).includes("unsaved changes"),
      "Footer must show the dirty tab",
    );
    await page.getByRole("button", { name: "Save profile" }).click();
    await page.getByText("Profiles saved.").waitFor({ timeout: 5000 });
    await pause(page, 300);
    const updateCall = [...state.calls]
      .reverse()
      .find((call) => call.method === "PUT" && call.path.startsWith("/profiles/profile-created"));
    assert(Boolean(updateCall), "Save must PUT the profile");
    assert(updateCall.body.run_prefix === "BTX", "Save must send the edited prefix");
    step("success: saved profile");
    const savedFooter = await page.locator('[data-testid="settings-footer-status"]').innerText();
    assert(
      savedFooter.includes("No unsaved changes") || savedFooter.includes("All changes saved"),
      `Footer must clear after a save, got: ${savedFooter}`,
    );

    // Delete with confirmation.
    await page.getByRole("button", { name: "Delete profile" }).click();
    await page.getByRole("dialog").getByText("Delete Beattok Remixes Two?").waitFor();
    await page.getByRole("dialog").getByRole("button", { name: "Delete profile" }).click();
    await page.getByText("Deleted profile").waitFor({ timeout: 5000 });
    assert(
      state.calls.some(
        (call) => call.method === "DELETE" && call.path.startsWith("/profiles/profile-created"),
      ),
      "Delete must call DELETE /profiles/{id}",
    );
    assert(
      (await list.getByRole("button", { name: /Beattok Remixes Two/ }).count()) === 0,
      "Deleted profile must leave the list",
    );
    step("success: deleted profile");

    // YouTube card: connected status and disconnect guard.
    await list.getByRole("button", { name: /Night Shift/ }).click();
    await pause(page);
    const youtubeCard = page.locator('[data-testid="settings-profile-youtube"]');
    const youtubeText = await youtubeCard.innerText();
    assert(youtubeText.includes("Connected"), "YouTube card must show connected");
    assert(youtubeText.includes("Night Shift Radio"), "YouTube card must show the channel");
    await youtubeCard.getByRole("button", { name: "Disconnect" }).click();
    await page.getByRole("dialog").getByText("Disconnect YouTube?").waitFor();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
    assert(state.connections.length === 1, "Cancelling must keep the connection");
    const templateCardText = await page
      .locator('[data-testid="settings-profile-templates"]')
      .innerText();
    assert(
      templateCardText.includes("Night Drive Long") &&
        templateCardText.includes("Night Drive Reel"),
      "Saved templates must appear in the Profiles template card",
    );
    const templateSelect = page.locator("#settings-profile-video-template");
    await templateSelect.waitFor({ timeout: 5000 });
    const videoTemplateOptions = await readSelectOptions(page, "#settings-profile-video-template");
    assert(
      videoTemplateOptions.some((text) => text.includes("Night Drive Long")),
      "Saved long templates must appear in the Profiles picker",
    );
    const reelTemplateOptions = await readSelectOptions(page, "#settings-profile-reel-template");
    assert(
      reelTemplateOptions.some((text) => text.includes("Night Drive Reel")),
      "Saved reel templates must appear in the Profiles picker",
    );

    // Template selection round-trips through the profile itself.
    await chooseOption(page, "#settings-profile-video-template", "night-drive-long");
    await chooseOption(page, "#settings-profile-reel-template", "night-drive-reel");

    // Publication must still open while the profile draft is dirty.
    await page.getByRole("tab", { name: /Publication/ }).click();
    await page.locator('[data-testid="settings-publication-tab"]').waitFor({ timeout: 5000 });
    await page.getByRole("tab", { name: /Profiles/ }).click();
    await page.locator('[data-testid="settings-profile-templates"]').waitFor({ timeout: 5000 });

    await page.getByRole("button", { name: "Save profile" }).click();
    await page.getByText("Profiles saved.").first().waitFor({ timeout: 5000 });
    const templateCall = [...state.calls]
      .reverse()
      .find((call) => call.method === "PUT" && call.path === "/profiles/profile-1");
    assert(
      templateCall.body.video_template_id === "night-drive-long",
      "The long template id must be saved on the profile",
    );
    assert(
      templateCall.body.reel_template_id === "night-drive-reel",
      "The reel template id must be saved on the profile",
    );
    assert(
      (await page.locator("#settings-profile-video-template").getAttribute("data-selected-value")) ===
        "night-drive-long",
      "The long picker must keep the saved template after the round-trip",
    );
    assert(
      (await page.locator("#settings-profile-reel-template").getAttribute("data-selected-value")) ===
        "night-drive-reel",
      "The reel picker must keep the saved template after the round-trip",
    );

    await page.locator('[data-testid="settings-profile-templates"]').scrollIntoViewIfNeeded();
    await pause(page, 200);
    await page.screenshot({ path: path.join(artifacts, "settings-profile-templates-1440.png") });

    await capture(app, page, "settings-profiles");
    step("success: captured profiles");

    // Publication: defaults, schedule, save, validation.
    await page.getByRole("tab", { name: /Publication/ }).click();
    await page.locator('[data-testid="settings-publication-tab"]').waitFor();
    await pause(page);
    assert(
      (await page.locator("#settings-publication-profile-select").getAttribute("data-selected-value")) === "profile-1",
      "Publication must default to the initially selected profile",
    );
    await page.waitForFunction(() => {
      const element = document.querySelector("#settings-publication-playlist");
      return element && !element.disabled;
    }, { timeout: 5000 });
    const firstPlaylistOptions = await readSelectOptions(page, "#settings-publication-playlist");
    assert(
      firstPlaylistOptions.some((text) => text.includes("Night Mixes")),
      "Playlists must load for a connected profile",
    );

    // Profile switch loads that profile's publication defaults.
    await chooseOption(page, "#settings-publication-profile-select", "profile-2");
    await pause(page, 300);
    assert(
      (await page.locator("#settings-publication-visibility").getAttribute("data-selected-value")) === "scheduled",
      "Visibility must load for the selected profile",
    );
    assert(
      (await page.locator("#settings-publication-hour").getAttribute("data-selected-value")) === "21",
      "Hour must load",
    );
    assert(
      (await page.locator("#settings-publication-minute").getAttribute("data-selected-value")) === "35",
      "Minute must load",
    );
    assert(
      (await page.locator("#settings-publication-description").inputValue()).includes("Deep focus"),
      "Description must load",
    );

    await chooseOption(page, "#settings-publication-visibility", "public");
    await pause(page);
    assert(
      await page.locator("#settings-publication-hour").isDisabled(),
      "Hour must be disabled when not scheduled",
    );
    await page.getByRole("button", { name: "Save publication" }).click();
    await page.getByText("Publication saved.").first().waitFor({ timeout: 5000 });
    const publicationCall = [...state.calls]
      .reverse()
      .find((call) => call.method === "PUT" && call.path === "/profiles/profile-2");
    assert(publicationCall.body.youtube_config.visibility === "public", "Publication must save visibility");
    assert(publicationCall.body.youtube_config.publish_at === null, "Unscheduled uploads must clear publish_at");
    assert(publicationCall.body.youtube_config.category === "10", "Publication must keep the category");
    step("success: saved publication");

    // Playlist on a connected profile.
    await chooseOption(page, "#settings-publication-profile-select", "profile-1");
    await pause(page, 400);
    await page.waitForFunction(() => {
      const element = document.querySelector("#settings-publication-playlist");
      return element && !element.disabled;
    }, { timeout: 5000 });
    const playlistOptions = await readSelectOptions(page, "#settings-publication-playlist");
    assert(playlistOptions.some((text) => text.includes("Night Mixes")), "Playlists must load");
    await chooseOption(page, "#settings-publication-playlist", "PL1");
    await page.getByRole("button", { name: "Save publication" }).click();
    await page.getByText("Publication saved.").first().waitFor({ timeout: 5000 });
    const playlistCall = [...state.calls]
      .reverse()
      .find((call) => call.method === "PUT" && call.path === "/profiles/profile-1");
    assert(playlistCall.body.youtube_config.playlist === "PL1", "Playlist must save");

    await page.locator("#settings-publication-new-playlist").fill("Fresh Mixes");
    await page.getByRole("button", { name: "Create playlist" }).click();
    await page.getByText("Created playlist Fresh Mixes.").waitFor({ timeout: 5000 });
    const createPlaylistCall = state.calls.find(
      (call) => call.method === "POST" && call.path === "/youtube/profiles/profile-1/playlists",
    );
    assert(createPlaylistCall.body.title === "Fresh Mixes", "Create playlist must POST the title");
    assert(
      (await page.locator("#settings-publication-playlist").getAttribute("data-selected-value")).startsWith("PL"),
      "Created playlist must be selected",
    );

    // Validation blocks the save.
    await page.locator("#settings-publication-keywords").fill("k".repeat(520));
    const beforeInvalidSave = state.calls.length;
    await page.getByRole("button", { name: "Save publication" }).click();
    await pause(page, 300);
    assert(
      (await page.locator('[data-testid="settings-publication-tab"]').innerText()).includes(
        "Keywords exceed 500 characters",
      ),
      "Keywords validation must show inline",
    );
    assert(
      state.calls.length === beforeInvalidSave,
      "Invalid publication must not call the API",
    );
    await page.locator("#settings-publication-keywords").fill("lofi, night");
    await page.getByRole("button", { name: "Save publication" }).click();
    await page.getByText("Publication saved.").first().waitFor({ timeout: 5000 });

    await page.locator("#settings-publication-title-template").fill("{title} — {album}");
    await pause(page);
    const preview = await page.locator('[data-testid="settings-publication-tab"]').innerText();
    assert(preview.includes("Neon Skyline — Night Drive"), "Title preview must render tokens");
    step("success: publication validation/preview");

    // Publication screenshot is captured at the end of the scenario so the
    // session is not resized mid-flow (see the capture block below).

    // Preferences.
    await page.getByRole("tab", { name: /Preferences/ }).click({ timeout: 5000 });
    step("publication: preferences clicked");
    await page.locator('[data-testid="settings-preferences-tab"]').waitFor({ timeout: 8000 });
    step("publication: preferences rendered");
    await pause(page);
    const preferenceFieldCount = await page.locator("#settings-preferences-ffmpeg").count();
    if (preferenceFieldCount === 0) {
      const tabText = await page.locator('[data-testid="settings-preferences-tab"]').innerText();
      throw new Error(`Preferences fields missing. Tab shows: ${tabText.slice(0, 300)}`);
    }
    assert(
      (await page.locator("#settings-preferences-ffmpeg").inputValue()) === "C:\\tools\\ffmpeg.exe",
      "FFmpeg path must load",
    );
    assert(
      (await page.locator("#settings-preferences-suno").inputValue()) === "D:\\Suno",
      "Suno output dir must load",
    );
    assert(
      (await page.locator('[data-testid="settings-preferences-tab"]').innerText()).includes("2 GB · 30 days"),
      "Cache policy must be shown",
    );
    assert(
      (await page.getByRole("button", { name: "Clear audio cache" }).count()) === 0,
      "No dead cache control allowed",
    );

    await page.locator("#settings-preferences-image-workers").fill("2");
    await page.locator("#settings-preferences-style").evaluate((element) => {
      const input = element;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(input, "60");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await chooseOption(page, "#settings-preferences-image-source", "manual");
    await pause(page);
    assert(
      (await page.locator("#settings-preferences-background-source").count()) === 0,
      "User Provided must hide the reference controls",
    );
    await chooseOption(page, "#settings-preferences-image-source", "ai");
    await pause(page);
    await page.getByRole("button", { name: "Save preferences" }).click();
    await page.getByText("Preferences saved.").waitFor({ timeout: 5000 });
    const patchCall = [...state.calls]
      .reverse()
      .find((call) => call.method === "PATCH" && call.path === "/settings");
    assert(patchCall.body.perfImageWorkers === 2, "Preferences must patch image workers");
    assert(patchCall.body.styleStrength === 60, "Preferences must patch style strength");
    assert(!("ffmpegPath" in patchCall.body), "Unchanged paths must not be patched");

    // Diagnostics returns a local reference.
    await page.getByRole("button", { name: "Send diagnostics" }).click();
    await page.getByText("Prepared ·").waitFor({ timeout: 5000 });
    step("success: preferences saved");

    // Descriptions: catalog, paired structure, user CRUD, default selection.
    await page.getByRole("tab", { name: /Descriptions/ }).click();
    await page.locator('[data-testid="settings-descriptions-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator("#settings-descriptions-default-select").getAttribute("data-selected-value")) === "desc-admin-1",
      "The description default must load from account settings",
    );
    assert(
      (await page.locator("#settings-descriptions-default-structure").getAttribute("data-selected-value")) === "struct-admin-1",
      "The paired structure default must load from account settings",
    );
    const descriptionsText = await page.locator('[data-testid="settings-descriptions-tab"]').innerText();
    assert(descriptionsText.includes("Camxora Anthem"), "The Camxora catalog must be listed");
    assert(descriptionsText.includes("My Late Night"), "The user catalog must be listed");
    assert(descriptionsText.includes("Read-only"), "Admin entries must be labelled read-only");
    assert(descriptionsText.includes("Selected name"), "The selected entry name must be shown");
    assert(!descriptionsText.includes("operator@example.com"), "Descriptions must not show the email");
    assert(!descriptionsText.includes("e2e-token"), "Descriptions must not show the token");

    await page.getByTestId("settings-descriptions-new").click();
    await page.locator("#settings-descriptions-name").fill("E2E Description");
    await page.locator("#settings-descriptions-content").fill("A slow, warm opener.");
    await pause(page);
    assert(
      (await page.getByTestId("settings-descriptions-count").innerText()).includes("/ 5000"),
      "The editor must show a character count",
    );
    await page.getByTestId("settings-descriptions-save").click();
    await page.getByText("Created E2E Description.").waitFor({ timeout: 5000 });
    const createPromptCall = state.calls.find(
      (call) => call.method === "POST" && call.path === "/prompts/me/descriptions",
    );
    assert(Boolean(createPromptCall), "Create must POST /prompts/me/descriptions");
    assert(createPromptCall.body.name === "E2E Description", "Create must send the name");
    assert(createPromptCall.body.content === "A slow, warm opener.", "Create must send the content");
    assert(
      (await page.locator('[data-testid="settings-descriptions-list"]').innerText()).includes(
        "E2E Description",
      ),
      "The created prompt must appear in the user catalog",
    );

    await page.locator("#settings-descriptions-name").fill("E2E Description Edited");
    await page.getByTestId("settings-descriptions-save").click();
    await page.getByText("Saved E2E Description Edited.").waitFor({ timeout: 5000 });
    const updatePromptCall = [...state.calls]
      .reverse()
      .find(
        (call) => call.method === "PUT" && call.path.startsWith("/prompts/me/descriptions/"),
      );
    assert(Boolean(updatePromptCall), "Edit must PUT /prompts/me/descriptions/{id}");
    assert(updatePromptCall.body.name === "E2E Description Edited", "Edit must send the new name");

    const descriptionEditor = page.locator('[data-testid="settings-descriptions-editor"]');
    await descriptionEditor.getByRole("button", { name: "Use as default" }).click();
    await pause(page);
    assert(
      (await page.locator("#settings-descriptions-default-select").getAttribute("data-selected-value")).startsWith(
        "created-descriptions",
      ),
      "Use as default must select the saved prompt",
    );
    step("success: created and edited description");

    await descriptionEditor.getByRole("button", { name: "Delete" }).click();
    await page.getByRole("dialog").getByText("Delete E2E Description Edited?").waitFor();
    await page.getByRole("dialog").getByRole("button", { name: "Delete prompt" }).click();
    await page.getByText("Deleted E2E Description Edited.").waitFor({ timeout: 5000 });
    await pause(page);
    assert(
      state.calls.some(
        (call) => call.method === "DELETE" && call.path.startsWith("/prompts/me/descriptions/"),
      ),
      "Delete must call DELETE /prompts/me/descriptions/{id}",
    );
    assert(
      !(await page.locator('[data-testid="settings-descriptions-list"]').innerText()).includes(
        "E2E Description",
      ),
      "The deleted prompt must leave the catalog",
    );
    assert(
      (await page.locator("#settings-descriptions-default-select").getAttribute("data-selected-value")) === "",
      "Deleting the selected default must clear the draft",
    );
    step("success: deleted description");

    await chooseOption(page, "#settings-descriptions-default-select", "desc-admin-2");
    await chooseOption(page, "#settings-descriptions-default-structure", "struct-user-1");
    await pause(page);

    // Structures: same component, its own default.
    await page.getByRole("tab", { name: /^Structures/ }).click();
    await page.locator('[data-testid="settings-structures-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator("#settings-structures-default-select").getAttribute("data-selected-value")) === "struct-user-1",
      "The shared structure default must be reflected on the Structures tab",
    );
    assert(
      (await page.locator('[data-testid="settings-structures-tab"]').innerText()).includes(
        "My Build",
      ),
      "The user structure must be listed",
    );

    // Moods: same component, its own default.
    await page.getByRole("tab", { name: /^Moods/ }).click();
    await page.locator('[data-testid="settings-moods-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator("#settings-moods-default-select").getAttribute("data-selected-value")) === "mood-admin-1",
      "The mood default must load from account settings",
    );
    await chooseOption(page, "#settings-moods-default-select", "mood-user-1");
    await pause(page);
    step("success: structures and moods");

    // Pools: read-only stats, table, pager bounds, kind switch.
    await page.getByRole("tab", { name: /^Pools/ }).click();
    await page.locator('[data-testid="settings-pools-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 400);
    const poolsTab = page.locator('[data-testid="settings-pools-tab"]');
    const poolsText = await poolsTab.innerText();
    assert(poolsText.includes("Account-wide"), "The ownership summary must be shown");
    assert(poolsText.includes("Admin Portal"), "Pools must explain where editing happens");
    const statsText = await page.getByTestId("settings-pools-stats").innerText();
    assert(statsText.includes("120"), `Openings total missing: ${statsText}`);
    assert(statsText.includes("100"), `Openings unused count missing: ${statsText}`);
    assert(!poolsText.includes("operator@example.com"), "Pools must not show the email");
    assert(!poolsText.includes("e2e-token"), "Pools must not show the token");
    assert(
      (await poolsTab.locator("input, select, textarea").count()) === 0,
      "Pools must be read-only: no form controls",
    );
    assert(
      (await page.locator('[data-testid="settings-pools-table"] tbody tr').count()) === 50,
      "The first pool page must show 50 rows",
    );
    assert(
      (await page.getByTestId("settings-pools-page-label").innerText()).includes(
        "Page 1 of 3 · 1–50 of 120",
      ),
      "The first page label must state the range",
    );
    assert(await page.getByTestId("settings-pools-prev").isDisabled(), "Previous must be disabled on page 1");
    assert(!(await page.getByTestId("settings-pools-next").isDisabled()), "Next must be enabled on page 1");
    await page.getByTestId("settings-pools-next").click();
    await pause(page, 400);
    assert(
      (await page.getByTestId("settings-pools-page-label").innerText()).includes(
        "Page 2 of 3 · 51–100 of 120",
      ),
      "Next must load the second page",
    );
    assert(
      state.calls.some(
        (call) =>
          call.method === "GET" &&
          call.path === "/content-pools/openings" &&
          call.query?.offset === 50 &&
          call.query?.limit === 50,
      ),
      "The second page must request offset 50 with a 50-row page size",
    );
    await page.getByTestId("settings-pools-next").click();
    await pause(page, 400);
    assert(
      (await page.getByTestId("settings-pools-page-label").innerText()).includes(
        "Page 3 of 3 · 101–120 of 120",
      ),
      "The last page label must state the final range",
    );
    assert(
      (await page.getByTestId("settings-pools-table").locator("tbody tr").count()) === 20,
      "The last page must show the remaining rows",
    );
    assert(await page.getByTestId("settings-pools-next").isDisabled(), "Next must be disabled on the last page");
    assert(!(await page.getByTestId("settings-pools-prev").isDisabled()), "Previous must be enabled on page 3");
    await page.getByTestId("settings-pools-prev").click();
    await pause(page, 300);
    assert(
      (await page.getByTestId("settings-pools-page-label").innerText()).includes("Page 2 of 3"),
      "Previous must step back one page",
    );

    await page.locator('[data-pool-kind="titles"]').click();
    await pause(page, 400);
    assert(
      (await page.getByTestId("settings-pools-page-label").innerText()).includes("Page 1 of 1 · 1–2 of 2"),
      "Switching pool kind must reset to the first page",
    );
    assert(await page.getByTestId("settings-pools-next").isDisabled(), "A single page must disable Next");
    await page.locator('[data-pool-kind="albums"]').click();
    await pause(page, 400);
    assert(
      (await poolsTab.innerText()).includes("no entries yet"),
      "An empty pool must say so explicitly",
    );
    step("success: pools");

    // Suno: bounds block the save; a valid patch writes only changed keys.
    await page.getByRole("tab", { name: /^Suno/ }).click();
    await page.locator('[data-testid="settings-suno-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator("#settings-suno-version").getAttribute("data-selected-value")) === "v6",
      "The Suno version must load",
    );
    assert(
      (await page.locator("#settings-suno-timeout").inputValue()) === "90000",
      "The Suno timeout must load",
    );
    assert(
      (await page.locator('[data-testid="settings-suno-tab"]').innerText()).includes(
        "Only the supported Suno defaults are shown here",
      ),
      "The supported-defaults note must be shown",
    );
    assert(!(await page.locator('[data-testid="settings-suno-tab"]').innerText()).includes("e2e-token"));

    const beforeInvalidSuno = state.calls.length;
    await page.locator("#settings-suno-timeout").fill("100");
    await page.getByTestId("settings-suno-save").click();
    await pause(page, 400);
    assert(
      (await page.locator('[data-testid="settings-suno-tab"]').innerText()).includes(
        "Timeout must be between 1000 and 600000 ms.",
      ),
      "Out-of-bounds values must show a field error",
    );
    assert(
      state.calls.length === beforeInvalidSuno,
      "Invalid Suno defaults must not call the API",
    );

    await page.locator("#settings-suno-timeout").fill("120000");
    await page.locator("#settings-suno-retry").fill("6");
    await page.locator("#settings-suno-merge").check();
    await page.locator("#settings-suno-merge-group").fill("3");
    await chooseOption(page, "#settings-suno-version", "v5.5");
    await page.getByTestId("settings-suno-save").click();
    await page.getByText("Suno defaults saved.").waitFor({ timeout: 5000 });
    const sunoPatchCall = [...state.calls]
      .reverse()
      .find((call) => call.method === "PATCH" && call.path === "/settings");
    assert(sunoPatchCall.body.sunoDefaultVersion === "v5.5", "Suno must patch the version");
    assert(sunoPatchCall.body.sunoTimeoutMs === 120000, "Suno must patch the timeout");
    assert(sunoPatchCall.body.sunoRetryCount === 6, "Suno must patch the retry count");
    assert(sunoPatchCall.body.sunoMergeEnabled === true, "Suno must patch auto merge");
    assert(sunoPatchCall.body.sunoMergeGroupSize === 3, "Suno must patch the merge group size");
    assert(
      !("customSunoPreset" in sunoPatchCall.body),
      "Suno must not resend settings keys it does not own",
    );
    assert(state.settings.customSunoPreset === "keep-me", "Unknown settings keys must be preserved");
    step("success: suno bounds and patch");

    // Re-dirty Suno for the save-all order check.
    await page.locator("#settings-suno-retry").fill("4");
    await pause(page);

    // Save all changes in a deterministic order across every writable tab.
    await page.getByRole("tab", { name: /Profiles/ }).click();
    await pause(page);
    await page.locator("#settings-profile-prefix").fill("NS2");
    await page.getByRole("tab", { name: /Publication/ }).click();
    await pause(page);
    await chooseOption(page, "#settings-publication-category", "24");
    await page.getByRole("tab", { name: /Preferences/ }).click();
    await pause(page);
    await page.locator("#settings-preferences-music-workers").fill("2");
    await pause(page);
    step("success: edited all tabs");
    const dirtyFooter = await page.locator('[data-testid="settings-footer-status"]').innerText();
    assert(
      dirtyFooter.includes("7 tabs with unsaved changes") &&
        dirtyFooter.includes(
          "Profiles, Publication, Preferences, Descriptions, Structures, Moods, Suno",
        ),
      `Footer must list every dirty tab, got: ${dirtyFooter}`,
    );
    assert(
      !dirtyFooter.includes("Pools"),
      "The read-only Pools tab must never be dirty",
    );

    const callStart = state.calls.length;
    await page.getByRole("button", { name: "Save all changes" }).click();
    await page.getByText("Saved all changes.").waitFor({ timeout: 10000 });
    await pause(page, 400);
    const saveAllCalls = state.calls.slice(callStart);
    assert(
      saveAllCalls
        .map((call) => `${call.method} ${call.path}`)
        .join(" | ") ===
        [
          "PUT /profiles/profile-1",
          "PUT /profiles/profile-1",
          "PATCH /settings",
          "PATCH /settings",
          "PATCH /settings",
          "PATCH /settings",
          "PATCH /settings",
        ].join(" | "),
      `Save all order: ${saveAllCalls.map((call) => `${call.method} ${call.path}`).join(", ")}`,
    );
    const savesByTab = saveAllCalls.map((call) => call.body ?? {});
    assert(savesByTab[0].run_prefix === "NS2", "Profiles must save first");
    assert(savesByTab[1].youtube_config.category === "24", "Publication must save second");
    assert(savesByTab[2].perfMusicWorkers === 2, "Preferences must save third");
    assert(
      savesByTab[3].defaultDescriptionId === "desc-admin-2" &&
        !("defaultStructureId" in savesByTab[3]),
      `Descriptions must save its own default: ${JSON.stringify(savesByTab[3])}`,
    );
    assert(
      savesByTab[4].defaultStructureId === "struct-user-1",
      `Structures must save its default: ${JSON.stringify(savesByTab[4])}`,
    );
    assert(savesByTab[5].defaultMoodId === "mood-user-1", "Moods must save its default");
    assert(savesByTab[6].sunoRetryCount === 4, "Suno must save fourth");
    assert(
      !("customSunoPreset" in savesByTab[6]),
      "Save all must not resend unknown settings keys",
    );
    assert(
      (await page.locator('[data-testid="settings-footer-status"]').innerText()).includes("All changes saved"),
      "Footer must report the save",
    );
    step("success: saved all");

    // Discard all reverts every draft, including the new tabs.
    await page.getByRole("tab", { name: /^Suno/ }).click();
    await pause(page);
    await page.locator("#settings-suno-retry").fill("9");
    await pause(page);
    assert(
      (await page.locator('[data-testid="settings-footer-status"]').innerText()).includes("Suno"),
      "The Suno draft must be dirty before Discard",
    );
    await page.getByRole("tab", { name: /Profiles/ }).click();
    await pause(page);
    await page.locator("#settings-profile-name").fill("Renamed Draft");
    await page.getByRole("button", { name: "Discard", exact: true }).first().click();
    await page.getByRole("dialog").getByText("Discard all changes?").waitFor();
    await page.getByRole("dialog").getByRole("button", { name: "Discard changes" }).click();
    await pause(page);
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Night Shift",
      "Discard must revert the profile draft",
    );
    await page.getByRole("tab", { name: /^Suno/ }).click();
    await pause(page);
    assert(
      (await page.locator("#settings-suno-retry").inputValue()) === "4",
      "Discard must revert the Suno draft",
    );
    await page.getByRole("tab", { name: /Profiles/ }).click();
    await pause(page);

    // Later `/settings?profile=` navigation switches the editor.
    await page.evaluate(() => {
      window.location.hash = "#/settings?profile=profile-2";
    });
    await pause(page, 400);
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Deep Focus",
      "Query param navigation must select the profile",
    );

    // Sidebar navigation must not silently drop unsaved settings.
    await page.locator("#settings-profile-name").fill("Deep Focus Draft");
    await page.getByRole("link", { name: "Dashboard" }).click();
    await page.getByRole("alertdialog").getByText("Discard unsaved changes?").waitFor();
    await page.getByRole("alertdialog").getByRole("button", { name: "Stay" }).click();
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Deep Focus Draft",
      "Stay must keep the draft",
    );
    await page.getByRole("link", { name: "Dashboard" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Discard and leave" }).click();
    await page.waitForFunction(() => window.location.hash === "#/home");
    await page.evaluate(() => {
      window.location.hash = "#/settings";
    });
    await page.locator("#settings-tabpanel").waitFor({ timeout: 8000 });
    await pause(page);
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Deep Focus",
      "Discard and leave must revert the draft",
    );
    step("success: navigation guard");

    // No credentials in the settings content.
    const settingsText = await page.locator("#settings-tabpanel").innerText();
    assert(!settingsText.includes("operator@example.com"), "Settings must not show the email");
    assert(!settingsText.includes("e2e-token"), "Settings must not show the token");
    const html = await page.content();
    assert(!html.includes("e2e-token"), "The access token must never reach the DOM");
    step("success: done");
  } finally {
    await closeApp(app);
    server.close();
  }
}

async function settingsScreens(which) {
  step(`screens ${which}: start`);
  const { server, port } = await createBackend();
  const { app, page } = await openApp(`screens-${which}`, port);
  try {
    await openSettings(page);
    if (which === "publication") {
      await page.getByRole("tab", { name: /Publication/ }).click();
      await page.locator('[data-testid="settings-publication-tab"]').waitFor();
      await pause(page, 400);
      await capture(app, page, "settings-publication");
    } else {
      await page.getByRole("tab", { name: /Preferences/ }).click();
      await page.locator('[data-testid="settings-preferences-tab"]').waitFor();
      await page.locator("#settings-preferences-ffmpeg").waitFor();
      await pause(page, 300);
      await capture(app, page, "settings-preferences");
    }
    step(`screens ${which}: done`);
  } finally {
    await closeApp(app);
    server.close();
  }
}

async function settingsP8Screens() {
  step("screens p8: start");
  const { server, port } = await createBackend();
  const { app, page } = await openApp("screens-p8", port);
  const outDir = path.join(artifacts, "settings-p8");
  fs.mkdirSync(outDir, { recursive: true });
  const tabs = [
    ["descriptions", /^Descriptions/],
    ["structures", /^Structures/],
    ["moods", /^Moods/],
    ["pools", /^Pools/],
    ["suno", /^Suno/],
  ];
  try {
    await openSettings(page);
    await resize(app, page, 1440, 900);
    for (const [name, pattern] of tabs) {
      await page.getByRole("tab", { name: pattern }).click();
      await page.locator(`[data-testid="settings-${name}-tab"]`).waitFor({ timeout: 8000 });
      await pause(page, 500);
      await page.evaluate(() => {
        const scroller = document.querySelector("main");
        if (scroller) scroller.scrollTop = 0;
      });
      await page.screenshot({
        path: path.join(outDir, `settings-${name}-1440.png`),
        timeout: 15000,
      });
    }
    step("screens p8: done");
  } finally {
    await closeApp(app);
    server.close();
  }
}

async function settingsEmpty() {
  step("empty: start");
  const emptyPrompts = { descriptions: [], structures: [], moods: [] };
  const emptyPools = { openings: [], titles: [], albums: [] };
  const { server, port } = await createBackend({
    profiles: [],
    connections: [],
    promptWorkspace: emptyPrompts,
    myPrompts: emptyPrompts,
    pools: emptyPools,
  });
  const { app, page } = await openApp("empty", port);
  try {
    await openSettings(page);
    const profilesText = await page.locator('[data-testid="settings-profiles-tab"]').innerText();
    assert(profilesText.includes("No profiles yet."), "Empty state must be explicit");
    assert(profilesText.includes("New profile"), "Empty state must offer New profile");

    await page.getByRole("tab", { name: /Publication/ }).click();
    await pause(page);
    assert(
      (await page.locator('[data-testid="settings-publication-tab"]').innerText()).includes(
        "Create a channel profile",
      ),
      "Publication must explain the missing profile",
    );

    await page.getByRole("tab", { name: /Preferences/ }).click();
    await pause(page);
    assert(
      (await page.locator("#settings-preferences-image-workers").inputValue()) === "4",
      "Preferences must still load without profiles",
    );

    await page.getByRole("tab", { name: /^Descriptions/ }).click();
    await page.locator('[data-testid="settings-descriptions-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    const descriptionsText = await page.locator('[data-testid="settings-descriptions-tab"]').innerText();
    assert(descriptionsText.includes("No user descriptions yet."), "The prompt empty state must be explicit");
    assert(
      descriptionsText.includes("No Camxora descriptions are available."),
      "The empty Camxora catalog must be explicit",
    );

    await page.getByRole("tab", { name: /^Pools/ }).click();
    await page.locator('[data-testid="settings-pools-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator('[data-testid="settings-pools-tab"]').innerText()).includes("no entries yet"),
      "The empty pool state must be explicit",
    );
    assert(
      (await page.getByTestId("settings-pools-page-label").innerText()).includes("Page 1 of 1"),
      "An empty pool must still show a bounded pager",
    );

    await page.getByRole("tab", { name: /Profiles/ }).click();
    await pause(page);
    await capture(app, page, "settings-empty");
    step("empty: done");
  } finally {
    await closeApp(app);
    server.close();
  }
}

async function settingsErrors() {
  step("errors: start");
  const { server, port } = await createBackend({
    failures: {
      "GET /profiles": true,
      "GET /settings": true,
      "GET /prompts/descriptions/workspace": true,
      "GET /content-pools/stats": true,
    },
  });
  const { app, page } = await openApp("errors", port);
  try {
    await openSettings(page);
    const profilesText = await page.locator('[data-testid="settings-profiles-tab"]').innerText();
    assert(profilesText.includes("Unable to load channel profiles"), "Profiles error banner missing");
    assert(profilesText.includes("Retry"), "Profiles error must offer Retry");

    await page.getByRole("tab", { name: /Preferences/ }).click();
    await pause(page);
    assert(
      (await page.locator('[data-testid="settings-preferences-tab"]').innerText()).includes(
        "Unable to load preferences",
      ),
      "Preferences error banner missing",
    );

    await page.getByRole("tab", { name: /^Descriptions/ }).click();
    await page.locator('[data-testid="settings-descriptions-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator('[data-testid="settings-descriptions-tab"]').innerText()).includes(
        "Unable to load the description catalog.",
      ),
      "Prompt catalog error banner missing",
    );

    await page.getByRole("tab", { name: /^Pools/ }).click();
    await page.locator('[data-testid="settings-pools-tab"]').waitFor({ timeout: 8000 });
    await pause(page, 300);
    assert(
      (await page.locator('[data-testid="settings-pools-tab"]').innerText()).includes(
        "Pool counts are unavailable right now.",
      ),
      "Pool stats error banner missing",
    );

    await page.getByRole("tab", { name: /^Suno/ }).click();
    await pause(page);
    assert(
      (await page.locator('[data-testid="settings-suno-tab"]').innerText()).includes(
        "Unable to load Suno defaults.",
      ),
      "Suno error banner missing",
    );
    await capture(app, page, "settings-error");
  } finally {
    await closeApp(app);
    server.close();
  }
}

const only = process.env.SETTINGS_E2E_ONLY;
if (!only || only === "success") await settingsSuccess();
if (!only || only === "screens-publication") await settingsScreens("publication");
if (!only || only === "screens-preferences") await settingsScreens("preferences");
if (!only || only === "screens-p8") await settingsP8Screens();
if (!only || only === "empty") await settingsEmpty();
if (!only || only === "errors") await settingsErrors();
if (!only || only === "loading") await settingsLoading();
console.log(JSON.stringify({ settings: "ok", artifacts }));
