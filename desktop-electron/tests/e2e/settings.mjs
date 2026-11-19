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
}, 300000);
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

async function openApp(name, apiPort) {
  const userData = path.join(artifacts, `e2e-settings-${name}`);
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
    await app.close();
    server.close();
  }
}

async function settingsSuccess() {
  step("success: start");
  const { server, state, port } = await createBackend();
  const { app, page } = await openApp("success", port);
  try {
    // Deep link selects the requested profile on mount.
    await openSettings(page, "profile-1");
    step("success: opened settings");
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Night Shift",
      "Deep link must select the requested profile",
    );

    // Shell: three live tabs, P8 note, no P8 tabs.
    assert((await page.getByRole("tab").count()) === 3, "Settings must render three live tabs");
    const tabNames = (await page.getByRole("tab").allInnerTexts()).map((text) => text.trim());
    assert(
      tabNames.join("|") === "Profiles|Publication|Preferences",
      `Only the three live tabs may render, got: ${tabNames.join("|")}`,
    );
    const navText = await page.getByRole("tablist", { name: "Settings sections" }).innerText();
    assert(
      navText.includes("Descriptions, Structures, Moods, Pools and Suno arrive in P8"),
      "P8 note missing",
    );

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
      (await page.locator("#settings-profile-resolution").inputValue()) === "1080x1920",
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
    await page.locator("#settings-profile-resolution").selectOption("1080x1920");
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
    assert(
      (await page.locator('[data-testid="settings-profile-templates"]').innerText()).includes(
        "Vizzy pipeline templates arrive in P7",
      ),
      "Template card must show the P7 note",
    );
    assert(
      (await page.locator('[data-testid="settings-profile-templates"] select').count()) === 0,
      "Template card must not show a template picker",
    );

    await capture(app, page, "settings-profiles");
    step("success: captured profiles");

    // Publication: defaults, schedule, save, validation.
    await page.getByRole("tab", { name: /Publication/ }).click();
    await page.locator('[data-testid="settings-publication-tab"]').waitFor();
    await pause(page);
    assert(
      (await page.locator("#settings-publication-profile-select").inputValue()) === "profile-1",
      "Publication must default to the initially selected profile",
    );
    await page.waitForFunction(() => {
      const element = document.querySelector("#settings-publication-playlist");
      return element && !element.disabled;
    }, { timeout: 5000 });
    const firstPlaylistOptions = await page.locator("#settings-publication-playlist option").allTextContents();
    assert(
      firstPlaylistOptions.some((text) => text.includes("Night Mixes")),
      "Playlists must load for a connected profile",
    );

    // Profile switch loads that profile's publication defaults.
    await page.locator("#settings-publication-profile-select").selectOption("profile-2");
    await pause(page, 300);
    assert(
      (await page.locator("#settings-publication-visibility").inputValue()) === "scheduled",
      "Visibility must load for the selected profile",
    );
    assert((await page.locator("#settings-publication-hour").inputValue()) === "21", "Hour must load");
    assert((await page.locator("#settings-publication-minute").inputValue()) === "35", "Minute must load");
    assert(
      (await page.locator("#settings-publication-description").inputValue()).includes("Deep focus"),
      "Description must load",
    );

    await page.locator("#settings-publication-visibility").selectOption("public");
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
    await page.locator("#settings-publication-profile-select").selectOption("profile-1");
    await pause(page, 400);
    await page.waitForFunction(() => {
      const element = document.querySelector("#settings-publication-playlist");
      return element && !element.disabled;
    }, { timeout: 5000 });
    const playlistOptions = await page.locator("#settings-publication-playlist option").allTextContents();
    assert(playlistOptions.some((text) => text.includes("Night Mixes")), "Playlists must load");
    await page.locator("#settings-publication-playlist").selectOption("PL1");
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
      (await page.locator("#settings-publication-playlist").inputValue()).startsWith("PL"),
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
    await page.locator("#settings-preferences-image-source").selectOption("manual");
    await pause(page);
    assert(
      (await page.locator("#settings-preferences-background-source").count()) === 0,
      "User Provided must hide the reference controls",
    );
    await page.locator("#settings-preferences-image-source").selectOption("ai");
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

    // Save all changes in a deterministic order.
    await page.getByRole("tab", { name: /Profiles/ }).click();
    await pause(page);
    await page.locator("#settings-profile-prefix").fill("NS2");
    await page.getByRole("tab", { name: /Publication/ }).click();
    await pause(page);
    await page.locator("#settings-publication-category").selectOption("24");
    await page.getByRole("tab", { name: /Preferences/ }).click();
    await pause(page);
    await page.locator("#settings-preferences-music-workers").fill("2");
    await pause(page);
    step("success: edited all tabs");
    const dirtyFooter = await page.locator('[data-testid="settings-footer-status"]').innerText();
    assert(
      dirtyFooter.includes("3 tabs with unsaved changes") &&
        dirtyFooter.includes("Profiles, Publication, Preferences"),
      `Footer must list every dirty tab, got: ${dirtyFooter}`,
    );

    const callStart = state.calls.length;
    await page.getByRole("button", { name: "Save all changes" }).click();
    await page.getByText("Saved all changes.").waitFor({ timeout: 8000 });
    await pause(page, 300);
    const saveAllCalls = state.calls.slice(callStart).map((call) => `${call.method} ${call.path}`);
    assert(saveAllCalls[0] === "PUT /profiles/profile-1", `Save all order: ${saveAllCalls.join(", ")}`);
    assert(saveAllCalls[1] === "PUT /profiles/profile-1", `Save all publication: ${saveAllCalls.join(", ")}`);
    assert(saveAllCalls[2] === "PATCH /settings", `Save all preferences: ${saveAllCalls.join(", ")}`);
    assert(
      (await page.locator('[data-testid="settings-footer-status"]').innerText()).includes("All changes saved"),
      "Footer must report the save",
    );
    step("success: saved all");

    // Discard all reverts every draft.
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

    // Later `/settings?profile=` navigation switches the editor.
    await page.evaluate(() => {
      window.location.hash = "#/settings?profile=profile-2";
    });
    await pause(page, 400);
    assert(
      (await page.locator("#settings-profile-name").inputValue()) === "Deep Focus",
      "Query param navigation must select the profile",
    );

    // No credentials in the settings content.
    const settingsText = await page.locator("#settings-tabpanel").innerText();
    assert(!settingsText.includes("operator@example.com"), "Settings must not show the email");
    assert(!settingsText.includes("e2e-token"), "Settings must not show the token");
    const html = await page.content();
    assert(!html.includes("e2e-token"), "The access token must never reach the DOM");
    step("success: done");
  } finally {
    await app.close();
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
    await app.close();
    server.close();
  }
}

async function settingsEmpty() {
  step("empty: start");
  const { server, port } = await createBackend({ profiles: [], connections: [] });
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
    await page.getByRole("tab", { name: /Profiles/ }).click();
    await pause(page);
    await capture(app, page, "settings-empty");
    step("empty: done");
  } finally {
    await app.close();
    server.close();
  }
}

async function settingsErrors() {
  step("errors: start");
  const { server, port } = await createBackend({
    failures: { "GET /profiles": true, "GET /settings": true },
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
    await capture(app, page, "settings-error");
  } finally {
    await app.close();
    server.close();
  }
}

const only = process.env.SETTINGS_E2E_ONLY;
if (!only || only === "success") await settingsSuccess();
if (!only || only === "screens-publication") await settingsScreens("publication");
if (!only || only === "screens-preferences") await settingsScreens("preferences");
if (!only || only === "empty") await settingsEmpty();
if (!only || only === "errors") await settingsErrors();
if (!only || only === "loading") await settingsLoading();
console.log(JSON.stringify({ settings: "ok", artifacts }));
