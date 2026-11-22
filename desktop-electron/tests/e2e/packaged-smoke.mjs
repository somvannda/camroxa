/**
 * Smoke the packaged Windows app: it must boot against production without any
 * CAMXORA_* environment overrides.
 *
 * Run after `npm run package:win`:
 *   node tests/e2e/packaged-smoke.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const exe = path.join(root, "release", "win-unpacked", "Camxora.exe");
if (!fs.existsSync(exe)) {
  throw new Error(`Packaged app not found: ${exe}`);
}

const userData = path.join(root, "artifacts", "packaged-smoke", "user-data");
fs.rmSync(path.dirname(userData), { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });

const env = { ...process.env, CAMXORA_USER_DATA_DIR: userData };
for (const key of [
  "CAMXORA_API_BASE_URL",
  "CAMXORA_PORTAL_BASE_URL",
  "CAMXORA_BUILD_ENV",
  "CAMXORA_DEV_AUTH",
  "CAMXORA_E2E",
]) {
  delete env[key];
}

const app = await electron.launch({ executablePath: exe, args: [], env });
try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  const info = await window.evaluate(async () => window.camxora.app.info());
  if (!info) throw new Error("app:info returned nothing");
  const { env: buildEnv, apiBaseUrl, portalUrl, version } = info;
  if (buildEnv !== "production") {
    throw new Error(`Expected production env, got ${buildEnv} (${apiBaseUrl})`);
  }
  if (apiBaseUrl !== "https://api.camxora.com/api/v1") {
    throw new Error(`Unexpected API base: ${apiBaseUrl}`);
  }
  if (portalUrl !== "https://app.camxora.com") {
    throw new Error(`Unexpected portal base: ${portalUrl}`);
  }
  await window.getByText("Welcome back.", { exact: true }).waitFor({ timeout: 30_000 });
  console.log(
    JSON.stringify({
      packaged: true,
      version,
      env: buildEnv,
      apiBaseUrl,
      portalUrl,
      title: await window.title(),
    }),
  );
} finally {
  await app.close();
}
