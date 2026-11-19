import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  resolveVizzyAsset,
  vizzyAssetResponse,
  VIZZY_CONTENT_SECURITY_POLICY,
} from "../../electron/vizzy-host/assets";
import { startVizzyLoopbackServer } from "../../electron/vizzy-host/server";

let root: string;

beforeAll(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-vizzy-host-"));
  fs.writeFileSync(path.join(root, "index.html"), "<!doctype html><title>spike</title>", "utf8");
  fs.mkdirSync(path.join(root, "assets"));
  fs.writeFileSync(path.join(root, "assets", "worker.js"), "self.onmessage = () => {};", "utf8");
});

afterAll(() => {
  fs.rmSync(root, { recursive: true, force: true });
});

describe("vizzy host assets", () => {
  it("serves the index for the root path", () => {
    const lookup = resolveVizzyAsset(root, "/");
    expect(lookup.ok).toBe(true);
    if (!lookup.ok) return;
    expect(path.basename(lookup.asset.filePath)).toBe("index.html");
    expect(lookup.asset.mime).toBe("text/html; charset=utf-8");
  });

  it("maps script extensions to a JavaScript MIME type", () => {
    const lookup = resolveVizzyAsset(root, "/assets/worker.js");
    expect(lookup.ok).toBe(true);
    if (!lookup.ok) return;
    expect(lookup.asset.mime).toBe("text/javascript; charset=utf-8");
  });

  it("rejects traversal and encoded traversal", () => {
    expect(resolveVizzyAsset(root, "/../package.json")).toMatchObject({ ok: false, status: 403 });
    expect(resolveVizzyAsset(root, "/%2e%2e/package.json")).toMatchObject({ ok: false, status: 403 });
    expect(resolveVizzyAsset(root, "/%00.js")).toMatchObject({ ok: false, status: 400 });
  });

  it("returns 404 for a missing asset", () => {
    expect(resolveVizzyAsset(root, "/missing.js")).toMatchObject({ ok: false, status: 404 });
  });

  it("adds COOP, COEP, CORP and the CSP to every asset response", () => {
    const lookup = resolveVizzyAsset(root, "/");
    expect(lookup.ok).toBe(true);
    if (!lookup.ok) return;
    const response = vizzyAssetResponse(lookup.asset);
    expect(response.headers.get("cross-origin-opener-policy")).toBe("same-origin");
    expect(response.headers.get("cross-origin-embedder-policy")).toBe("require-corp");
    expect(response.headers.get("cross-origin-resource-policy")).toBe("cross-origin");
    expect(response.headers.get("content-security-policy")).toBe(VIZZY_CONTENT_SECURITY_POLICY);
    expect(VIZZY_CONTENT_SECURITY_POLICY).toContain("'wasm-unsafe-eval'");
  });
});

describe("vizzy host loopback server", () => {
  it("serves the tokenised page with isolation headers and rejects everything else", async () => {
    const server = await startVizzyLoopbackServer({ root, token: "test-token" });
    try {
      expect(server.pageUrl.startsWith("http://127.0.0.1:")).toBe(true);
      expect(server.pageUrl).toContain("/t/test-token/index.html");

      const page = await fetch(server.pageUrl);
      expect(page.status).toBe(200);
      expect(page.headers.get("cross-origin-opener-policy")).toBe("same-origin");
      expect(page.headers.get("cross-origin-embedder-policy")).toBe("require-corp");
      expect(page.headers.get("cross-origin-resource-policy")).toBe("cross-origin");
      expect(await page.text()).toContain("spike");

      const worker = await fetch(`${server.origin}/t/test-token/assets/worker.js`);
      expect(worker.status).toBe(200);
      expect(worker.headers.get("content-type")).toBe("text/javascript; charset=utf-8");

      const wrongToken = await fetch(`${server.origin}/t/other/index.html`);
      expect(wrongToken.status).toBe(404);

      const traversal = await fetch(`${server.origin}/t/test-token/%2e%2e/package.json`);
      // URL parsing normalises the dot segment, so the request loses the token
      // prefix and is rejected before the asset resolver runs.
      expect(traversal.status).toBe(404);

      const post = await fetch(server.pageUrl, { method: "POST" });
      expect(post.status).toBe(405);
    } finally {
      await server.close();
    }
  });
});
