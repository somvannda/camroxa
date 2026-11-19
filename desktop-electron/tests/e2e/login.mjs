import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
const userData = path.join(artifacts, "e2e-login");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(userData, { recursive: true, force: true });

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "0",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_API_BASE_URL: process.env.CAMXORA_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  },
});

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.waitForTimeout(900);

  const text = await window.locator("body").innerText();
  await window.screenshot({ path: path.join(artifacts, "login.png"), fullPage: true });

  console.log(
    JSON.stringify({
      title: await window.title(),
      hasLogin: text.includes("Sign in to continue"),
      hasEmail: text.includes("Email"),
    }),
  );
  if (!text.includes("Sign in to continue")) {
    throw new Error("Login page did not render");
  }
} finally {
  await app.close();
}
