import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

/**
 * Account pages E2E: Dashboard and Profile against a stub platform API.
 *
 * `CAMXORA_DEV_AUTH` bypass has no access token by design, so this spec signs
 * in through the real login IPC against a local fixture server. That keeps the
 * required/optional endpoint behaviour, the aggregated fetch, and the success,
 * empty and partial-failure states covered without inventing data in the app.
 */

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
  channel_profile_count: 3,
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
  usage_by_day: [
    { date: "2026-11-13", songs: 2, images: 1, videos: 0, studio_exports: 0, manual_exports: 0, youtube_uploads: 0 },
    { date: "2026-11-14", songs: 3, images: 0, videos: 1, studio_exports: 1, manual_exports: 0, youtube_uploads: 0 },
    { date: "2026-11-15", songs: 0, images: 2, videos: 0, studio_exports: 0, manual_exports: 0, youtube_uploads: 0 },
    { date: "2026-11-16", songs: 4, images: 1, videos: 0, studio_exports: 0, manual_exports: 1, youtube_uploads: 0 },
    { date: "2026-11-17", songs: 1, images: 0, videos: 1, studio_exports: 1, manual_exports: 0, youtube_uploads: 1 },
    { date: "2026-11-18", songs: 2, images: 2, videos: 0, studio_exports: 0, manual_exports: 0, youtube_uploads: 0 },
    { date: "2026-11-19", songs: 0, images: 0, videos: 1, studio_exports: 1, manual_exports: 0, youtube_uploads: 0 },
  ],
  recent_activity: [
    { timestamp: "2026-11-19T10:24:00Z", kind: "song", detail: "Album draft completed", status: "completed" },
    { timestamp: "2026-11-19T09:12:00Z", kind: "image", detail: "Thumbnail render failed", status: "failed" },
    { timestamp: "2026-11-18T21:03:00Z", kind: "video", detail: "Reel queued", status: "running" },
  ],
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
    image_config: { mode: "bg_only" },
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
    image_config: { mode: "thumb_only" },
    youtube_config: { visibility: "unlisted" },
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-02-02T00:00:00Z",
  },
];

const LICENSE = {
  plan_type: "studio-monthly",
  profile_allowance: 5,
  profile_addon_slots: 1,
  profile_addon_pending: 0,
  effective_profile_allowance: 6,
  monthly_song_quota: 120,
  songs_remaining: 76,
  monthly_image_quota: 40,
  images_remaining: 18,
  wallet_balance: 410,
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
};

async function openApp(name, apiPort) {
  const userData = path.join(artifacts, `e2e-account-${name}`);
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
  if (await onboarding.isVisible().catch(() => false)) {
    await onboarding.click();
  }
  await page.getByRole("heading", { name: "Weekly Usage" }).waitFor({ timeout: 15000 });
  await page.waitForTimeout(400);
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
  await resize(app, page, 1440, 900);
  await page.screenshot({ path: path.join(artifacts, `${file}-1440.png`), fullPage: true });
  await resize(app, page, 1280, 800);
  await page.screenshot({ path: path.join(artifacts, `${file}-1280.png`), fullPage: true });
  await resize(app, page, 1440, 900);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function dashboardSuccess() {
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /users/me": (_request, response) => json(response, 200, ME),
    "GET /stats/dashboard": (_request, response) => json(response, 200, STATS),
    "GET /profiles": (_request, response) => json(response, 200, PROFILES),
    "GET /licenses/validate": (_request, response) => json(response, 200, LICENSE),
    "GET /topups/packs": (_request, response) =>
      json(response, 200, {
        packs: [
          {
            id: "pack-1",
            slug: "small",
            name: "Small Pack",
            description: "",
            total_credits: 1000,
            price_cents: 500,
            display_order: 1,
            songs_equivalent: 100,
          },
          {
            id: "pack-2",
            slug: "medium",
            name: "Medium Pack",
            description: "",
            total_credits: 2300,
            price_cents: 1000,
            display_order: 2,
            songs_equivalent: 230,
          },
          {
            id: "pack-3",
            slug: "pro",
            name: "Pro Pack",
            description: "",
            total_credits: 5500,
            price_cents: 2000,
            display_order: 3,
            songs_equivalent: 550,
          },
        ],
      }),
    "GET /topups/history": (_request, response) =>
      json(response, 200, { purchases: [], total: 0, limit: 12, offset: 0 }),
  });

  const { app, page } = await openApp("success", port);
  try {
    assert((await page.locator('[data-testid^="kpi-"]').count()) === 6, "Dashboard must show six KPI cards");
    const kpiText = await page.locator('[data-testid="kpi-spent"]').innerText();
    assert(kpiText.includes("1,234"), "Credits spent KPI must use grouping");
    const balanceText = await page.locator('[data-testid="kpi-balance"]').innerText();
    assert(balanceText.includes("750"), "Credit balance KPI must show the wallet");
    const weekly = await page.locator('[data-testid="weekly-usage"]').innerText();
    assert(weekly.includes("Songs") && weekly.includes("Images") && weekly.includes("Videos"), "Chart legend missing");
    assert(!weekly.includes("Current plan"), "The dashboard must not show a plan");
    assert((await page.locator('[data-testid="weekly-usage"] svg').count()) === 1, "Weekly chart must render as SVG");
    const balance = await page.locator('[data-testid="credit-balance"]').innerText();
    assert(balance.includes("Credits only"), "Credits-only badge missing");
    assert(balance.includes("1,234 of 2,000 credits used"), "Credit usage line missing");
    assert(balance.includes("Studio exports") && balance.includes("Manual exports"), "Export stats missing");
    assert(!balance.includes("Song quota") && !balance.includes("Image quota"), "Quota rows must be gone");
    const activity = await page.locator('[data-testid="recent-activity"]').innerText();
    assert(activity.includes("Album draft completed"), "Recent activity row missing");
    assert(activity.includes("completed") && activity.includes("failed"), "Status pills missing");
    assert((await page.getByRole("button", { name: /^refresh/i }).count()) === 0, "No refresh button allowed");
    assert((await page.getByRole("button", { name: "View data" }).count()) === 1, "View data alternative missing");

    await capture(app, page, "dashboard-success");

    await page.getByRole("link", { name: "Profile" }).click();
    await page.getByRole("heading", { name: "Channel Profiles" }).waitFor({ timeout: 5000 });
    const account = await page.locator('[data-testid="profile-account"]').innerText();
    assert(account.includes("Night Operator") && account.includes("operator@example.com"), "Account card missing identity");
    assert(account.includes("Verified") && account.includes("user-1"), "Account verification or id missing");
    const membership = await page.locator('[data-testid="profile-membership"]').innerText();
    assert(membership.includes("Profiles") && membership.includes("3 / 6"), "Membership profile metric missing");
    assert(membership.includes("1,234 / 2,000"), "Membership credit usage missing");
    assert(membership.includes("500"), "Membership credits balance missing");
    const channels = await page.locator('[data-testid="profile-channels"]').innerText();
    assert(channels.includes("Night Shift") && channels.includes("Deep Focus"), "Channel profile rows missing");
    assert(channels.includes("BG Only") && channels.includes("Public"), "Image mode or visibility missing");
    const profileActivity = await page.locator('[data-testid="profile-activity"]').innerText();
    assert(profileActivity.includes("1,234"), "Activity counters missing");
    await capture(app, page, "profile-success");

    await page.getByRole("link", { name: "Plan" }).click();
    await page.getByRole("heading", { name: "Plan", exact: true }).waitFor({ timeout: 5000 });
    await page.locator('[data-testid="plan-pack-small"]').waitFor({ timeout: 8000 });
    assert(
      (await page.locator('[data-testid^="plan-pack-"]').count()) === 3,
      "Plan must render every credit pack",
    );
    const planText = await page.locator('[data-testid="plan-page"]').innerText();
    assert(planText.includes("500") && planText.includes("Small Pack"), "Plan balance or pack missing");
    assert(planText.includes("$5.00") && planText.includes("$20.00"), "Pack prices missing");
    assert(planText.includes("No top-ups yet."), "Top-up history empty state missing");
    await capture(app, page, "plan-success");
  } finally {
    await app.close();
    server.close();
  }
}

async function emptyAccount() {
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /users/me": (_request, response) =>
      json(response, 200, {
        ...ME,
        plan_name: null,
        channel_profile_count: 0,
        profile_allowance: 0,
        effective_profile_allowance: 0,
        credit_balance: 0,
      }),
    "GET /stats/dashboard": (_request, response) =>
      json(response, 200, {
        ...STATS,
        credits_spent: 0,
        credits_remaining: 0,
        credits_total: 0,
        songs_generated: 0,
        images_generated: 0,
        videos_generated: 0,
        songs_remaining: null,
        songs_quota: null,
        usage_by_day: [],
        recent_activity: [],
      }),
    "GET /profiles": (_request, response) => json(response, 200, []),
    "GET /licenses/validate": (_request, response) => json(response, 404, { detail: "No licence" }),
  });

  const { app, page } = await openApp("empty", port);
  try {
    const dashboard = await page.locator("body").innerText();
    assert(dashboard.includes("No usage data available yet."), "Empty chart copy missing");
    assert(dashboard.includes("No recent activity found."), "Empty activity copy missing");
    const kpiText = await page.locator('[data-testid="kpi-songs"]').innerText();
    assert(kpiText.includes("0"), "Empty account KPI must be zero");

    await capture(app, page, "dashboard-empty");

    await page.getByRole("link", { name: "Profile" }).click();
    await page.getByRole("heading", { name: "Channel Profiles" }).waitFor({ timeout: 5000 });
    const profileText = await page.locator("body").innerText();
    assert(profileText.includes("No channel profiles found yet."), "Empty profiles copy missing");
    assert(profileText.includes("Credits & usage"), "Credits card missing");
    assert(profileText.includes("credits available"), "Credits balance caption missing");
    await capture(app, page, "profile-empty");
  } finally {
    await app.close();
    server.close();
  }
}

async function optionalFailures() {
  const { server, port } = await startApi({
    ...baseRoutes,
    "GET /users/me": (_request, response) => json(response, 200, { ...ME, plan_name: "pro" }),
    "GET /stats/dashboard": (_request, response) => json(response, 200, STATS),
    "GET /profiles": (_request, response) => json(response, 500, { detail: "Profiles unavailable" }),
    "GET /licenses/validate": (_request, response) => json(response, 404, { detail: "No licence" }),
  });

  const { app, page } = await openApp("partial", port);
  try {
    const body = await page.locator("body").innerText();
    assert(!body.includes("Unable to load dashboard statistics right now"), "Optional failures must not fail the page");
    assert(body.includes("Credits only"), "Credits-only wallet must render without a licence");
    assert(body.includes("1,234 of 2,000 credits used"), "Credit usage must fall back to stats");
    await page.getByRole("link", { name: "Profile" }).click();
    await page.getByRole("heading", { name: "Channel Profiles" }).waitFor({ timeout: 5000 });
    const profileText = await page.locator("body").innerText();
    assert(profileText.includes("No channel profiles found yet."), "Optional profiles failure must render empty");
    assert(profileText.includes("500"), "Membership must fall back to the account credit balance");
  } finally {
    await app.close();
    server.close();
  }
}

await dashboardSuccess();
await emptyAccount();
await optionalFailures();
console.log(JSON.stringify({ accountPages: "ok", artifacts }));
