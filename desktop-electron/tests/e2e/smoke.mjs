import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
const userData = path.join(artifacts, "e2e-shell");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(userData, { recursive: true, force: true });

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_API_BASE_URL: process.env.CAMXORA_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  },
});

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.waitForTimeout(1200);

  const title = await window.title();
  const text = await window.locator("body").innerText();
  const info = await window.evaluate(async () => window.camxora.app.info());
  const session = await window.evaluate(async () => window.camxora.auth.restore());
  const ffmpeg = await window.evaluate(async () => window.camxora.ffmpeg.available());

  const hasDashboard = text.includes("Weekly Usage") && text.includes("Recent Activity");
  const hasDashboardError = text.includes(
    "Unable to load dashboard statistics right now",
  );
  const refreshButtons = await window
    .getByRole("button", { name: /^refresh/i })
    .count();
  await window.screenshot({ path: path.join(artifacts, "dashboard-error.png"), fullPage: true });

  await window.getByRole("link", { name: "Profile" }).click();
  await window.getByRole("heading", { name: "Channel Profiles" }).waitFor({ timeout: 5000 });
  const profileText = await window.locator("body").innerText();
  const hasProfile =
    profileText.includes("Credits & usage") &&
    profileText.includes("Channel Profiles") &&
    profileText.includes("Activity");
  await window.screenshot({ path: path.join(artifacts, "profile-error.png"), fullPage: true });

  console.log(
    JSON.stringify({
      title,
      version: info.version,
      sessionRestored: session.ok,
      ffmpeg: ffmpeg.ok ? ffmpeg.data.available : false,
      hasDashboard,
      hasDashboardError,
      hasProfile,
      refreshButtons,
    }),
  );
  if (info.version !== "2.0.0") {
    throw new Error(`Unexpected app version: ${info.version}`);
  }
  if (!session.ok) {
    throw new Error("Session bridge failed");
  }
  if (!hasDashboard) {
    throw new Error("Dashboard page did not render");
  }
  if (!hasDashboardError) {
    // The dev bypass has no token, so required endpoints fail and the page
    // must show its error state instead of inventing data.
    throw new Error("Dashboard error state did not render");
  }
  if (refreshButtons !== 0) {
    throw new Error("Dashboard must not expose a refresh button");
  }
  if (!hasProfile) {
    throw new Error("Profile page did not render");
  }
  const headerActions = await window.locator('[data-testid="notifications-button"]').count();
  const updateAction = await window.locator('[data-testid="update-button"]').count();
  if (headerActions !== 1 || updateAction !== 1) {
    throw new Error("Header actions did not render");
  }
  await window.locator('[data-testid="notifications-button"]').click();
  await window.locator('[data-testid="notifications-panel"]').waitFor({ timeout: 3000 });
  await window.screenshot({ path: path.join(artifacts, "notifications-panel.png") });
} finally {
  await app.close();
}
