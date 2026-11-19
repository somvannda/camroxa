import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
const userData = path.join(artifacts, "e2e-media");
const imagesDir = path.join(userData, "images");
const filePath = path.join(imagesDir, "range-test.bin");
const bytes = Buffer.from(Array.from({ length: 256 }, (_value, index) => index));

fs.mkdirSync(imagesDir, { recursive: true });
fs.writeFileSync(filePath, bytes);

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_USER_DATA_DIR: userData,
  },
});

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.waitForTimeout(1200);

  const mediaUrl = await window.evaluate(async (target) => {
    const result = await window.camxora.media.url({ path: target });
    return result;
  }, filePath);

  if (!mediaUrl.ok) throw new Error(`media:url failed: ${JSON.stringify(mediaUrl)}`);

  const ranged = await window.evaluate(async (url) => {
    const response = await fetch(url, { headers: { Range: "bytes=10-19" } });
    const body = new Uint8Array(await response.arrayBuffer());
    return {
      status: response.status,
      contentRange: response.headers.get("content-range"),
      bytes: Array.from(body),
    };
  }, mediaUrl.data.url);

  const head = await window.evaluate(async (url) => {
    const response = await fetch(url, { method: "HEAD" });
    return {
      status: response.status,
      length: response.headers.get("content-length"),
      acceptRanges: response.headers.get("accept-ranges"),
    };
  }, mediaUrl.data.url);

  console.log(JSON.stringify({ ranged, head }));

  if (ranged.status !== 206) throw new Error(`Expected 206, got ${ranged.status}`);
  if (ranged.contentRange !== "bytes 10-19/256") {
    throw new Error(`Unexpected content-range: ${ranged.contentRange}`);
  }
  if (ranged.bytes.join(",") !== "10,11,12,13,14,15,16,17,18,19") {
    throw new Error(`Unexpected range bytes: ${ranged.bytes.join(",")}`);
  }
  if (head.status !== 200 || head.length !== "256" || head.acceptRanges !== "bytes") {
    throw new Error(`Unexpected HEAD response: ${JSON.stringify(head)}`);
  }
} finally {
  await app.close();
}
