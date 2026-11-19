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

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_UPDATE_MANIFEST_URL: `http://127.0.0.1:${port}/release.json`,
    CAMXORA_UPDATE_ALLOW_HTTP: "1",
  },
});

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  const heading = window.getByRole("heading", { name: "Update required" });
  await heading.waitFor({ timeout: 10_000 });
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
  await app.close();
  server.close();
}
