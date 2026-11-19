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
  await window.screenshot({ path: path.join(artifacts, "foundation.png"), fullPage: true });

  console.log(
    JSON.stringify({
      title,
      version: info.version,
      sessionRestored: session.ok,
      ffmpeg: ffmpeg.ok ? ffmpeg.data.available : false,
      hasFoundation: text.includes("Foundation checks"),
    }),
  );
  if (!text.includes("Foundation checks")) {
    throw new Error("Foundation page did not render");
  }
  if (info.version !== "2.0.0") {
    throw new Error(`Unexpected app version: ${info.version}`);
  }
  if (!session.ok) {
    throw new Error("Session bridge failed");
  }
} finally {
  await app.close();
}
