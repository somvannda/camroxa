import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
const userData = path.join(artifacts, "e2e-update");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(userData, { recursive: true, force: true });

const server = http.createServer((request, response) => {
  if (request.url !== "/release.json") {
    response.writeHead(404).end();
    return;
  }
  const body = JSON.stringify({
    version: "2.0.1",
    mandatory: true,
    notes: "Security update for the desktop client.",
    url: "https://example.com/camxora-2.0.1.exe",
  });
  response.writeHead(200, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;

function launch(extraEnv) {
  return electron.launch({
    args: ["dist-electron/main.cjs"],
    cwd: root,
    env: {
      ...process.env,
      CAMXORA_DEV_AUTH: "1",
      CAMXORA_USER_DATA_DIR: userData,
      ...extraEnv,
    },
  });
}

async function expectGate(extraEnv, label) {
  const app = await launch(extraEnv);
  try {
    const window = await app.firstWindow();
    await window.waitForLoadState("domcontentloaded");
    await window.getByRole("heading", { name: "Update required" }).waitFor({ timeout: 10_000 });
    const text = await window.locator("body").innerText();
    if (!text.includes("2.0.1") || !text.includes("Security update")) {
      throw new Error(`${label}: mandatory gate did not render the stored offer`);
    }
    return true;
  } finally {
    await app.close();
  }
}

try {
  // 1. A mandatory offer blocks the app and is persisted.
  const first = await launch({
    CAMXORA_UPDATE_MANIFEST_URL: `http://127.0.0.1:${port}/release.json`,
    CAMXORA_UPDATE_ALLOW_HTTP: "1",
  });
  try {
    const window = await first.firstWindow();
    await window.waitForLoadState("domcontentloaded");
    await window.getByRole("heading", { name: "Update required" }).waitFor({ timeout: 10_000 });
    const text = await window.locator("body").innerText();
    await window.screenshot({ path: path.join(artifacts, "update-required.png"), fullPage: true });
    console.log(
      JSON.stringify({
        mandatoryUpdate: true,
        hasVersion: text.includes("2.0.1"),
        hasNotes: text.includes("Security update"),
      }),
    );
    if (!text.includes("2.0.1") || !text.includes("Security update")) {
      throw new Error("Mandatory update gate did not render the manifest");
    }
  } finally {
    await first.close();
  }

  // 2. The stored gate survives an unreachable update service.
  await expectGate(
    { CAMXORA_API_BASE_URL: "http://127.0.0.1:59998/api/v1" },
    "offline persistence",
  );
  console.log(JSON.stringify({ persistedOffline: true }));

  // 3. A confirmed 404 withdraws the offer and clears the stored gate.
  const withdrawn = await launch({
    CAMXORA_API_BASE_URL: `http://127.0.0.1:${port}/api/v1`,
  });
  try {
    const window = await withdrawn.firstWindow();
    await window.waitForLoadState("domcontentloaded");
    await window.getByRole("heading", { name: "Dashboard" }).waitFor({ timeout: 10_000 });
    const gate = await window.getByRole("heading", { name: "Update required" }).count();
    if (gate !== 0) throw new Error("A withdrawn update must not block the app");
    console.log(JSON.stringify({ withdrawnCleared: true }));
  } finally {
    await withdrawn.close();
  }
} finally {
  server.close();
}
