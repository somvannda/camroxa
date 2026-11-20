/* global document, window */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import AdmZip from "adm-zip";
import { _electron as electron } from "playwright";

/**
 * Image + Marketplace E2E against a stub platform API.
 *
 * Covers the P5/P6 acceptance paths: image bootstrap, grouping, date filter,
 * selection previews, retry, clear queue, prompt autosave and poll lifecycle;
 * marketplace catalog filters/search/pagination, install, reinstall, installed
 * state across navigation, legacy policy, corrupt ZIP and zip-slip rejection.
 */

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
const outputs = path.join(artifacts, "e2e-image-outputs");
fs.mkdirSync(artifacts, { recursive: true });
fs.mkdirSync(outputs, { recursive: true });

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);
const PREVIEW_SVG = Buffer.from(
  `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
     <rect width="640" height="360" fill="#171b20"/>
     <rect x="0" y="238" width="640" height="122" fill="#1d2228"/>
     <rect x="48" y="180" width="196" height="10" rx="5" fill="#2b323b"/>
     <rect x="48" y="202" width="120" height="8" rx="4" fill="#252c34"/>
     <circle cx="520" cy="92" r="34" fill="#252c34"/>
     <rect x="48" y="60" width="86" height="86" rx="10" fill="#20262d"/>
   </svg>`,
  "utf8",
);
const TODAY_BG = path.join(outputs, "today-bg.svg");
const YESTERDAY_TH = path.join(outputs, "yesterday-th.svg");
fs.writeFileSync(TODAY_BG, PREVIEW_SVG);
fs.writeFileSync(YESTERDAY_TH, PREVIEW_SVG);

function ymd(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

const today = new Date();
const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
const TODAY = ymd(today);
const YESTERDAY = ymd(yesterday);

const ME = {
  id: "user-1",
  email: "operator@example.com",
  email_confirmed: true,
  display_name: "Night Operator",
  credit_balance: 500,
  plan_name: "studio-monthly",
  role: "user",
  onboarding_paid: true,
  desktop_access: true,
  channel_profile_count: 2,
};

const PROFILES = [
  { id: "profile-1", name: "Night Shift", folder_name: "night-shift", run_prefix: "NS" },
  { id: "profile-2", name: "Deep Focus", folder_name: "deep-focus", run_prefix: "DF" },
];

const BATCHES = [
  {
    batch_id: "b-today",
    status: "completed",
    song_count: 3,
    from_date: TODAY,
    to_date: TODAY,
    ok_album: "Night Drive",
    alt_album: "Night Drive II",
    created_at: `${TODAY}T08:00:00Z`,
    updated_at: `${TODAY}T09:00:00Z`,
    songs: [{ album: "Night Drive", title: "Opening" }],
  },
  {
    batch_id: "b-yesterday",
    status: "completed",
    song_count: 1,
    from_date: YESTERDAY,
    to_date: YESTERDAY,
    ok_album: "Deep Focus",
    alt_album: "Deep Focus II",
    created_at: `${YESTERDAY}T08:00:00Z`,
    updated_at: `${YESTERDAY}T09:00:00Z`,
    songs: [{ album: "Deep Focus", title: "Still" }],
  },
];

function makeJobs() {
  return [
    {
      id: "job-bg-ok",
      batch_id: "b-today",
      song_id: "song-1",
      profile_id: "profile-1",
      kind: "background",
      channel_role: "ok",
      prompt: "night highway",
      status: "success",
      attempt_count: 1,
      input_image_path: "C:/samples/sample-a.png",
      style_reference_path: null,
      output_image_path: TODAY_BG,
      error: null,
      created_at: `${TODAY}T08:10:00Z`,
      updated_at: `${TODAY}T08:20:00Z`,
    },
    {
      id: "job-th-fail",
      batch_id: "b-today",
      song_id: "song-1",
      profile_id: "profile-1",
      kind: "thumbnail",
      channel_role: "ok",
      prompt: "night highway",
      status: "failed",
      attempt_count: 1,
      input_image_path: null,
      style_reference_path: "C:/samples/style-a.png",
      output_image_path: null,
      error: "provider timeout",
      created_at: `${TODAY}T08:10:00Z`,
      updated_at: `${TODAY}T08:30:00Z`,
    },
    {
      id: "job-bg-pending",
      batch_id: "b-yesterday",
      song_id: "song-2",
      profile_id: "profile-2",
      kind: "background",
      channel_role: "alt",
      prompt: "deep focus",
      status: "pending",
      attempt_count: 0,
      input_image_path: null,
      style_reference_path: null,
      output_image_path: null,
      error: null,
      created_at: `${YESTERDAY}T08:10:00Z`,
      updated_at: `${YESTERDAY}T08:15:00Z`,
    },
    {
      id: "job-th-ok",
      batch_id: "b-yesterday",
      song_id: "song-2",
      profile_id: "profile-2",
      kind: "thumbnail",
      channel_role: "alt",
      prompt: "deep focus",
      status: "success",
      attempt_count: 1,
      input_image_path: null,
      style_reference_path: null,
      output_image_path: YESTERDAY_TH,
      error: null,
      created_at: `${YESTERDAY}T08:10:00Z`,
      updated_at: `${YESTERDAY}T08:25:00Z`,
    },
  ];
}

function catalogItems() {
  const items = [];
  for (let index = 1; index <= 45; index += 1) {
    const reel = index > 30;
    const night = index === 2 || index === 12 || index === 22;
    items.push({
      id: `item-${index}`,
      name: night ? `Night Drive ${index}` : `Template ${String(index).padStart(2, "0")}`,
      description: night
        ? "Long-form night template with a quiet palette"
        : `Catalog template ${index}`,
      version: "1.0.0",
      author: index % 2 === 0 ? "Camxora" : "Night Shift Studio",
      kind: reel ? "reel" : "video",
      tags: night ? ["night", "moody"] : ["ambient"],
      status: "enabled",
      price: index % 5 === 0 ? 12.5 : 0,
      preview_url: `/marketplace/items/item-${index}/preview`,
      created_at: "2026-11-01T00:00:00Z",
    });
  }
  items[1].tags = ["legacy"];
  return items;
}

const CATALOG = catalogItems();

function validZip() {
  const zip = new AdmZip();
  zip.addFile(
    "template.json",
    Buffer.from(JSON.stringify({ name: "Installed Template", schema: "vizzy", objects: [] }), "utf8"),
  );
  zip.addFile(
    "manifest.json",
    Buffer.from(JSON.stringify({ name: "Installed Template", kind: "video", schema: "vizzy" }), "utf8"),
  );
  zip.addFile("assets/logo.png", PNG);
  zip.addFile("thumbnail.png", PNG);
  return zip.toBuffer();
}

function legacyZip() {
  const zip = new AdmZip();
  zip.addFile("template.json", Buffer.from(JSON.stringify({ name: "Old Camxora" }), "utf8"));
  zip.addFile(
    "manifest.json",
    Buffer.from(JSON.stringify({ name: "Old Camxora", kind: "video", schema: "legacy" }), "utf8"),
  );
  return zip.toBuffer();
}

function slipZip() {
  const zip = new AdmZip();
  zip.addFile(
    "template.json",
    Buffer.from(JSON.stringify({ name: "Slip", schema: "vizzy" }), "utf8"),
  );
  zip.addFile(
    "manifest.json",
    Buffer.from(JSON.stringify({ name: "Slip", kind: "video", schema: "vizzy" }), "utf8"),
  );
  zip.addFile("escape.txt", Buffer.from("owned", "utf8"));
  const entry = zip.getEntry("escape.txt");
  if (entry) {
    entry.entryName = "../escape.txt";
    entry.header.name = "../escape.txt";
  }
  return zip.toBuffer();
}

const VALID_ZIP = validZip();
const LEGACY_ZIP = legacyZip();
const SLIP_ZIP = slipZip();

function json(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

function sendBuffer(response, status, contentType, buffer) {
  response.writeHead(status, {
    "content-type": contentType,
    "content-length": buffer.length,
  });
  response.end(buffer);
}

function startApi(routes) {
  const hits = [];
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const path = url.pathname.replace(/^\/api\/v3/, "");
    const route = `${request.method} ${path}`;
    hits.push({ at: Date.now(), method: request.method ?? "GET", path, search: url.search });
    const handler = routes[route] ?? routes["*"];
    if (!handler) {
      json(response, 404, { detail: "Not found" });
      return;
    }
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk;
    });
    request.on("end", () => {
      handler(request, response, url, raw ? JSON.parse(raw) : undefined);
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, port: server.address().port, hits });
    });
  });
}

const baseRoutes = {
  "POST /auth/login": (_request, response) =>
    json(response, 200, { access_token: "e2e-token", refresh_token: "e2e-refresh", expires_in: 3600 }),
  "GET /users/me": (_request, response) => json(response, 200, ME),
  "GET /profiles": (_request, response) => json(response, 200, PROFILES),
  "GET /progress": (_request, response) => json(response, 200, { items: [] }),
  "GET /image-jobs": (_request, response) => json(response, 200, { items: makeJobs() }),
  "GET /music/history": (_request, response) =>
    json(response, 200, { batches: BATCHES, summary: "", updated_at: `${TODAY}T00:00:00Z` }),
  "GET /settings": (_request, response) =>
    json(response, 200, {
      imagePrompt: "legacy shared prompt",
      imageThumbnailPrompt: "shared thumbnail prompt",
    }),
  "GET /marketplace/catalog": (_request, response, url) => {
    const page = Number(url.searchParams.get("page") ?? 1);
    const size = Number(url.searchParams.get("page_size") ?? 20);
    const kind = url.searchParams.get("kind");
    const search = (url.searchParams.get("search") ?? "").toLowerCase();
    let items = CATALOG;
    if (kind) items = items.filter((item) => item.kind === kind);
    if (search) items = items.filter((item) => item.name.toLowerCase().includes(search));
    const start = (page - 1) * size;
    json(response, 200, {
      items: items.slice(start, start + size),
      total: items.length,
      page,
      page_size: size,
    });
  },
  "*": (request, response, url) => {
    if (request.method === "GET" && /^\/marketplace\/items\/[^/]+\/preview$/.test(url.pathname)) {
      sendBuffer(response, 200, "image/svg+xml", PREVIEW_SVG);
      return;
    }
    json(response, 404, { detail: "Not found" });
  },
};

async function openApp(name, apiPort) {
  const userData = path.join(artifacts, `e2e-image-market-${name}`);
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
  await page.waitForTimeout(500);
  const onboarding = page.getByRole("button", { name: "Open studio anyway" });
  if (await onboarding.isVisible().catch(() => false)) await onboarding.click();
  return { app, page, userData };
}

async function resize(app, width, height) {
  await app.evaluate(async ({ BrowserWindow }, size) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (window) window.setSize(size.width, size.height);
  }, { width, height });
}

async function capture(app, page, file) {
  await resize(app, 1440, 900);
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(artifacts, `${file}-1440.png`), fullPage: true });
  await resize(app, 1280, 800);
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(artifacts, `${file}-1280.png`), fullPage: true });
  await resize(app, 1440, 900);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function openImage(page) {
  await page.getByRole("link", { name: "Image" }).click();
  await page.getByTestId("image-workspace").waitFor({ timeout: 15000 });
  await page.waitForFunction(
    () => {
      const value = document.querySelector('[data-testid="image-stat-batches"]')?.textContent?.trim();
      return Boolean(value) && value !== "--";
    },
    undefined,
    { timeout: 15000 },
  );
}

async function imageFlow() {
  const settingsRequests = [];
  let settings = {
    imagePrompt: "legacy shared prompt",
    imageThumbnailPrompt: "shared thumbnail prompt",
  };
  let jobs = makeJobs();

  const { server, port, hits } = await startApi({
    ...baseRoutes,
    "GET /image-jobs": (_request, response) => json(response, 200, { items: jobs }),
    "GET /settings": (_request, response) => json(response, 200, settings),
    "PATCH /settings": (_request, response, _url, body) => {
      settingsRequests.push(body);
      settings = { ...settings, ...body };
      json(response, 200, settings);
    },
    "POST /image-jobs/retry": (_request, response, _url, body) => {
      const ids = body?.job_ids ?? [];
      for (const job of jobs) {
        if (ids.includes(job.id)) {
          job.status = "pending";
          job.error = null;
          job.updated_at = new Date().toISOString();
        }
      }
      json(response, 200, { updated: ids.length });
    },
    "POST /image-jobs/clear": (_request, response, _url, body) => {
      const before = jobs.length;
      jobs = jobs.filter((job) => job.batch_id !== body?.batch_id);
      json(response, 200, { deleted: before - jobs.length });
    },
  });

  const { app, page } = await openApp("image", port);

  try {
    await openImage(page);
    await page.getByTestId("image-stat-batches").waitFor({ timeout: 15000 });
    await page.waitForTimeout(600);

    assert((await page.getByTestId("image-stat-batches").innerText()) === "1", "Today should match one batch");
    const summary = await page.getByTestId("image-summary").innerText();
    assert(summary === "Rows 1 · Pending 0 · Running 0 · Failed 1 · Ready 1", `Unexpected summary: ${summary}`);
    const row = page.getByTestId("image-row-b-today-profile-1-ok");
    await row.waitFor({ timeout: 5000 });
    const rowText = await row.innerText();
    assert(rowText.includes(TODAY) && rowText.includes("Night Shift") && rowText.includes("ok"), "Queue row metadata missing");
    assert(rowText.includes("success") && rowText.includes("failed"), "Status cells missing");
    assert(rowText.includes("today-bg.svg"), "Background file name missing");
    assert((await page.getByTestId("image-preview-background").locator("img").count()) === 1, "Background preview did not load");

    // Date range widens to include yesterday; both rows render.
    await page.getByTestId("image-from").fill(YESTERDAY);
    await page.waitForTimeout(300);
    assert((await page.getByTestId("image-stat-batches").innerText()) === "2", "Range must match both batches");
    await page.getByTestId("image-row-b-yesterday-profile-2-alt").click();
    await page.waitForTimeout(500);
    assert(
      (await page.getByTestId("image-preview-thumbnail").locator("img").count()) === 1,
      "Thumbnail preview did not load for the selected row",
    );
    await capture(app, page, "image-success");

    // Retry the failed thumbnail job by double-clicking the status chip.
    await page.getByTestId("image-row-b-today-profile-1-ok").click();
    const failedChip = page.locator('[data-testid="image-status-thumbnail"][data-job-id="job-th-fail"]');
    await failedChip.dblclick();
    await page.waitForFunction(
      () => document.querySelector('[data-testid="image-stat-status"]')?.textContent?.includes("Retry queued."),
      undefined,
      { timeout: 5000 },
    );
    await page.waitForTimeout(300);
    const afterRetry = await page.getByTestId("image-row-b-today-profile-1-ok").innerText();
    assert(afterRetry.includes("pending"), "Retried job must refetch as pending");

    // Right-click row menu mirrors the desktop app's recovery actions.
    await page.getByTestId("image-row-b-today-profile-1-ok").click({ button: "right" });
    const menu = page.getByTestId("image-row-menu");
    await menu.waitFor({ timeout: 3000 });
    assert((await menu.getByRole("menuitem").count()) === 5, "Row menu must offer five actions");
    assert((await menu.innerText()).includes("Regenerate both"), "Regenerate both missing");
    await page.mouse.click(5, 5);
    await menu.waitFor({ state: "detached", timeout: 3000 });

    // Prompt autosave: 350 ms debounce, PATCH /settings.
    const prompt = page.getByTestId("image-prompt-background");
    assert((await prompt.inputValue()) === "legacy shared prompt", "Legacy imagePrompt fallback missing");
    await prompt.fill("a quiet midnight highway");
    await page.waitForTimeout(700);
    assert(
      settings.imageBackgroundPrompt === "a quiet midnight highway",
      "Prompt autosave did not PATCH /settings",
    );
    assert(
      settings.imageThumbnailPrompt === "shared thumbnail prompt",
      "Thumbnail prompt must not be overwritten by the legacy fallback",
    );
    await page.getByTestId("image-save-state").waitFor({ timeout: 3000 });

    // Clear queue: one POST per matched batch, sum deleted.
    await page.getByTestId("image-clear").click();
    await page.getByRole("heading", { name: "Clear queue?" }).waitFor({ timeout: 3000 });
    const dialogText = await page.getByRole("dialog").innerText();
    assert(dialogText.includes("Generated files on disk are not deleted"), "Clear dialog safety copy missing");
    await page.getByTestId("image-clear-confirm").click();
    await page.waitForFunction(
      () => document.querySelector('[data-testid="image-stat-status"]')?.textContent?.includes("Queue cleared"),
      undefined,
      { timeout: 5000 },
    );
    const clearRequests = hits.filter(
      (hit) => hit.method === "POST" && hit.path === "/image-jobs/clear",
    );
    assert(clearRequests.length === 2, `Expected one clear call per batch, saw ${clearRequests.length}`);
    await page.waitForTimeout(500);
    const body = await page.locator("main").innerText();
    assert(body.includes("No image jobs yet."), "Cleared queue must show the empty copy");
    assert(!body.includes("operator@example.com"), "Image page must not leak the account email");
    assert(!body.includes("e2e-token"), "Image page must not leak the access token");
    assert((await page.getByRole("button", { name: "Generate now" }).count()) === 0, "No generate CTA allowed");

    await capture(app, page, "image-cleared");
  } finally {
    await app.close();
    server.close();
  }
}

async function imagePollLifecycle() {
  const { server, port, hits } = await startApi({
    ...baseRoutes,
    "GET /image-jobs": (_request, response) => json(response, 200, { items: makeJobs() }),
    "GET /music/history": (_request, response) =>
      json(response, 200, { batches: BATCHES, summary: "", updated_at: `${TODAY}T00:00:00Z` }),
  });
  const { app, page } = await openApp("image-poll", port);
  const polls = () =>
    hits.filter((hit) => hit.method === "GET" && hit.path === "/image-jobs").map((hit) => hit.at);

  try {
    await openImage(page);
    await page.waitForTimeout(600);
    const before = polls().length;
    await page.waitForTimeout(4500);
    assert(polls().length > before, "Image workspace must poll every 4 s while active");

    // Leaving the route deactivates the page: no more image polls.
    await page.getByRole("link", { name: "Marketplace" }).click();
    await page.getByTestId("marketplace-grid").waitFor({ timeout: 10000 });
    await page.waitForTimeout(700);
    const deactivated = polls().length;
    await page.waitForTimeout(5200);
    assert(polls().length === deactivated, "Polling must stop when the page is deactivated");

    // Returning resumes polling.
    await page.getByRole("link", { name: "Image" }).click();
    await openImage(page);
    await page.waitForTimeout(4500);
    assert(polls().length > deactivated, "Polling must resume when the page is active again");
  } finally {
    await app.close();
    server.close();
  }
}

async function imagePartialAndError() {
  const partial = await startApi({
    ...baseRoutes,
    "GET /music/history": (_request, response) => json(response, 500, { detail: "history down" }),
    "GET /settings": (_request, response) => json(response, 500, { detail: "settings down" }),
  });
  const partialApp = await openApp("image-partial", partial.port);
  try {
    await openImage(partialApp.page);
    await partialApp.page.waitForTimeout(800);
    const body = await partialApp.page.locator("body").innerText();
    assert(body.includes("Batch metadata is unavailable"), "Partial batch metadata fallback missing");
    assert(body.includes("Prompts could not be loaded"), "Partial settings fallback missing");
    assert(
      (await partialApp.page.getByTestId("image-row-b-today-profile-1-ok").count()) === 1,
      "Jobs must still render without batch metadata",
    );
  } finally {
    await partialApp.app.close();
    partial.server.close();
  }

  const failing = await startApi({
    ...baseRoutes,
    "GET /image-jobs": (_request, response) => json(response, 500, { detail: "queue down" }),
  });
  const failingApp = await openApp("image-error", failing.port);
  try {
    await failingApp.page.getByRole("link", { name: "Image" }).click();
    await failingApp.page.waitForTimeout(1000);
    const body = await failingApp.page.locator("body").innerText();
    assert(body.includes("Unable to load the Image workspace right now."), "Image error banner missing");
    await capture(failingApp.app, failingApp.page, "image-error");
  } finally {
    await failingApp.app.close();
    failing.server.close();
  }
}

async function marketplaceFlow() {
  const downloads = [];
  const { server, port, hits } = await startApi({
    ...baseRoutes,
    "GET /marketplace/items/item-1/download": (_request, response) => {
      downloads.push("item-1");
      sendBuffer(response, 200, "application/zip", VALID_ZIP);
    },
    "GET /marketplace/items/item-3/download": (_request, response) =>
      sendBuffer(response, 200, "application/zip", Buffer.from("not a zip at all")),
    "GET /marketplace/items/item-4/download": (_request, response) =>
      sendBuffer(response, 200, "application/zip", SLIP_ZIP),
    "GET /marketplace/items/item-2/download": (_request, response) =>
      sendBuffer(response, 200, "application/zip", LEGACY_ZIP),
    "GET /marketplace/items/item-5/download": (_request, response) => {
      downloads.push("item-5");
      sendBuffer(response, 200, "application/zip", VALID_ZIP);
    },
  });

  const { app, page, userData } = await openApp("marketplace", port);
  const templatesDir = path.join(userData, "templates");

  try {
    await page.getByRole("link", { name: "Marketplace" }).click();
    await page.getByTestId("marketplace-grid").waitFor({ timeout: 15000 });
    await page.waitForTimeout(500);

    assert((await page.getByTestId("marketplace-total").innerText()).includes("45"), "Total count missing");
    assert((await page.getByTestId("marketplace-page-label").innerText()) === "Page 1 of 3", "Page label wrong");
    assert((await page.locator('[data-testid^="marketplace-card-item-"]').count()) === 20, "Page size must be 20");
    assert(
      (await page.getByTestId("marketplace-prev").isDisabled()) === true,
      "Previous must be disabled on page 1",
    );

    await page.getByTestId("marketplace-next").click();
    await page.waitForFunction(
      () => document.querySelector('[data-testid="marketplace-page-label"]')?.textContent === "Page 2 of 3",
      undefined,
      { timeout: 5000 },
    );
    await page.getByTestId("marketplace-prev").click();
    await page.waitForFunction(
      () => document.querySelector('[data-testid="marketplace-page-label"]')?.textContent === "Page 1 of 3",
      undefined,
      { timeout: 5000 },
    );

    // Kind filter resets to page 1 and sends `kind`.
    await page.getByTestId("marketplace-kind-reel").click();
    await page.waitForTimeout(600);
    assert(
      hits.some(
        (hit) =>
          hit.path === "/marketplace/catalog" &&
          hit.search.includes("kind=reel") &&
          hit.search.includes("page=1"),
      ),
      "Kind filter must request kind=reel on page 1",
    );
    assert((await page.getByTestId("marketplace-total").innerText()).includes("15"), "Reel total wrong");
    assert((await page.getByTestId("marketplace-page-label").innerText()) === "Page 1 of 1", "Reel paging wrong");

    // Idle cards keep the install state set by a previous action.
    const legacyCard = page.getByTestId("marketplace-card-item-2");
    await page.getByTestId("marketplace-kind-all").click();
    await page.waitForTimeout(600);
    await legacyCard.waitFor({ timeout: 5000 });
    const legacyText = await legacyCard.innerText();
    assert(legacyText.includes("Legacy Camxora"), "Legacy schema label missing");
    assert(legacyText.includes("not supported in Camxora Desktop 2.0.0"), "Legacy policy copy missing");
    assert(
      (await page.getByTestId("marketplace-install-item-2").isDisabled()) === true,
      "Legacy install must be disabled",
    );
    assert(
      (await page.getByTestId("marketplace-install-item-2").innerText()).includes("Not supported"),
      "Legacy install button must say Not supported",
    );

    // Card detail states schema, licence and the 2.0.0 policy.
    await legacyCard.getByRole("button", { name: "View Night Drive 2" }).click();
    const detail = page.getByRole("dialog");
    await detail.waitFor({ timeout: 3000 });
    const detailText = await detail.innerText();
    assert(detailText.includes("Legacy Camxora"), "Detail schema label missing");
    assert(detailText.includes("Licence") && detailText.includes("Not listed"), "Detail licence missing");
    assert(detailText.includes("not supported in Camxora Desktop 2.0.0"), "Detail policy copy missing");
    await detail.getByRole("button", { name: "Close" }).last().click();
    await page.waitForTimeout(300);

    // Install validates the ZIP, extracts under templates/<uid> and flips state.
    await page.getByTestId("marketplace-install-item-1").click();
    await page.getByTestId("marketplace-installed-item-1").waitFor({ timeout: 10000 });
    assert(
      (await page.getByTestId("marketplace-install-item-1").innerText()).includes("Reinstall"),
      "Installed card must offer Reinstall",
    );
    const installed = await page.evaluate(async () => {
      const result = await window.camxora.templates.list();
      return result.ok ? result.data : [];
    });
    assert(installed.length === 1, `Expected one installed template, saw ${installed.length}`);
    assert(installed[0].marketplaceItemId === "item-1", "Installed record must keep the item id");
    const uid = installed[0].id;
    assert(fs.existsSync(path.join(templatesDir, uid, "template.json")), "template.json not extracted");
    assert(fs.existsSync(path.join(templatesDir, uid, "manifest.json")), "manifest.json not extracted");
    assert(fs.existsSync(path.join(templatesDir, uid, "assets", "logo.png")), "assets not extracted");

    // Reinstall prompts, then updates in place without duplicating records.
    await page.getByTestId("marketplace-install-item-1").click();
    await page
      .getByRole("heading", { name: "Template already installed" })
      .waitFor({ timeout: 3000 });
    const confirmText = await page.getByRole("dialog").innerText();
    assert(confirmText.includes("This template is already installed"), "Reinstall prompt copy missing");
    await page.getByRole("dialog").getByRole("button", { name: "Reinstall" }).click();
    await page.waitForTimeout(1200);
    const afterReinstall = await page.evaluate(async () => {
      const result = await window.camxora.templates.list();
      return result.ok ? result.data : [];
    });
    assert(afterReinstall.length === 1, "Reinstall must not duplicate the template record");
    assert(afterReinstall[0].id === uid, "Reinstall must preserve the local template identity");
    assert(downloads.filter((id) => id === "item-1").length === 2, "Reinstall must download again");

    // Installed state survives route changes.
    await page.getByRole("link", { name: "Image" }).click();
    await page.getByTestId("image-workspace").waitFor({ timeout: 10000 });
    await page.getByRole("link", { name: "Marketplace" }).click();
    await page.getByTestId("marketplace-grid").waitFor({ timeout: 10000 });
    await page.getByTestId("marketplace-installed-item-1").waitFor({ timeout: 8000 });

    // Corrupt ZIP: readable error, no partial folder.
    await page.getByTestId("marketplace-install-item-3").click();
    await page.waitForTimeout(1200);
    const corruptText = await page.locator("body").innerText();
    assert(corruptText.includes("corrupted"), "Corrupt ZIP error message missing");
    const entries = fs.existsSync(templatesDir) ? fs.readdirSync(templatesDir) : [];
    assert(!entries.some((entry) => entry.includes("item-3")), "Corrupt ZIP left a template folder");
    assert(entries.filter((entry) => !entry.startsWith(".")).length === 1, "Corrupt ZIP left extra files");

    // Zip-slip: rejected before extraction; nothing written outside the root.
    await page.getByTestId("marketplace-install-item-4").click();
    await page.waitForTimeout(1200);
    const slipText = await page.locator("body").innerText();
    assert(slipText.includes("path traversal"), "Zip-slip rejection message missing");
    assert(!fs.existsSync(path.join(userData, "escape.txt")), "Zip-slip wrote outside the template folder");
    assert(!fs.existsSync(path.join(path.dirname(templatesDir), "escape.txt")), "Zip-slip wrote outside the app data root");

    // Search is debounced, trimmed and resets the page.
    await page.getByTestId("marketplace-search").fill("  night  ");
    await page.waitForTimeout(700);
    const searchRequests = hits.filter(
      (hit) => hit.path === "/marketplace/catalog" && hit.search.includes("search=night"),
    );
    assert(searchRequests.length >= 1, "Search must send the trimmed query");
    assert(
      searchRequests.every((hit) => hit.search.includes("page=1")),
      "Search must reset to page 1",
    );
    assert((await page.locator('[data-testid^="marketplace-card-item-"]').count()) === 3, "Search result count wrong");
    assert((await page.getByTestId("marketplace-total").innerText()).includes("3"), "Search total wrong");

    await page.getByRole("button", { name: "Clear filters" }).first().click();
    await page.waitForTimeout(600);
    const dismiss = page.getByRole("button", { name: "Dismiss" }).first();
    if (await dismiss.isVisible().catch(() => false)) await dismiss.click();
    await page.waitForTimeout(4300);
    await capture(app, page, "marketplace-success");

    const body = await page.locator("main").innerText();
    assert(!body.includes("operator@example.com"), "Marketplace must not leak the account email");
    assert(!body.includes("e2e-token"), "Marketplace must not leak the access token");
  } finally {
    await app.close();
    server.close();
  }
}

async function marketplaceStates() {
  const failing = await startApi({
    ...baseRoutes,
    "GET /marketplace/catalog": (_request, response) => json(response, 500, { detail: "catalog down" }),
  });
  const failingApp = await openApp("marketplace-error", failing.port);
  try {
    await failingApp.page.getByRole("link", { name: "Marketplace" }).click();
    await failingApp.page.waitForTimeout(1200);
    const body = await failingApp.page.locator("body").innerText();
    assert(body.includes("Unable to load the Marketplace right now."), "Marketplace error banner missing");
    assert(!body.includes("No templates match this filter."), "Error must not render as empty");
    await capture(failingApp.app, failingApp.page, "marketplace-error");
  } finally {
    await failingApp.app.close();
    failing.server.close();
  }

  const empty = await startApi({
    ...baseRoutes,
    "GET /marketplace/catalog": (_request, response) =>
      json(response, 200, { items: [], total: 0, page: 1, page_size: 20 }),
  });
  const emptyApp = await openApp("marketplace-empty", empty.port);
  try {
    await emptyApp.page.getByRole("link", { name: "Marketplace" }).click();
    await emptyApp.page.getByTestId("marketplace-empty").waitFor({ timeout: 10000 });
    assert(
      (await emptyApp.page.getByTestId("marketplace-empty").innerText()).includes("No templates match this filter."),
      "Empty copy missing",
    );
    await capture(emptyApp.app, emptyApp.page, "marketplace-empty");
  } finally {
    await emptyApp.app.close();
    empty.server.close();
  }
}

await imageFlow();
await imagePollLifecycle();
await imagePartialAndError();
await marketplaceFlow();
await marketplaceStates();
console.log(JSON.stringify({ imageMarketplace: "ok", artifacts }));
