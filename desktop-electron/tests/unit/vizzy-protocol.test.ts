import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  mimeForAsset,
  parseByteRange,
  resolveVizzyAsset,
  resolveVizzyRequest,
  vizzyAssetStreamResponse,
} from "../../electron/vizzy-host/assets";

let root: string;
let asset: { filePath: string; mime: string; size: number };

beforeAll(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-vizzy-range-"));
  const filePath = path.join(root, "asset.bin");
  fs.writeFileSync(filePath, "0123456789");
  asset = { filePath, mime: "application/octet-stream", size: 10 };
});

afterAll(() => {
  fs.rmSync(root, { recursive: true, force: true });
});

describe("byte ranges", () => {
  it("parses closed, open and suffix ranges", () => {
    expect(parseByteRange("bytes=0-3", 10)).toEqual({ start: 0, end: 3 });
    expect(parseByteRange("bytes=4-", 10)).toEqual({ start: 4, end: 9 });
    expect(parseByteRange("bytes=-3", 10)).toEqual({ start: 7, end: 9 });
  });

  it("clamps an end past the asset size", () => {
    expect(parseByteRange("bytes=5-99", 10)).toEqual({ start: 5, end: 9 });
  });

  it("ignores malformed, multi-range and out-of-bounds requests", () => {
    expect(parseByteRange(null, 10)).toBeNull();
    expect(parseByteRange("bytes=0-1,4-5", 10)).toBeNull();
    expect(parseByteRange("items=0-1", 10)).toBeNull();
    expect(parseByteRange("bytes=abc", 10)).toBeNull();
    expect(parseByteRange("bytes=10-12", 10)).toBeNull();
    expect(parseByteRange("bytes=-0", 10)).toBeNull();
  });
});

describe("streaming asset responses", () => {
  it("streams the whole file with isolation headers", async () => {
    const response = vizzyAssetStreamResponse(asset, null, "GET");
    expect(response.status).toBe(200);
    expect(response.headers.get("cross-origin-opener-policy")).toBe("same-origin");
    expect(response.headers.get("cross-origin-embedder-policy")).toBe("require-corp");
    expect(response.headers.get("content-length")).toBe("10");
    expect(response.headers.get("accept-ranges")).toBe("bytes");
    expect(await response.text()).toBe("0123456789");
  });

  it("answers a range with 206 and Content-Range", async () => {
    const response = vizzyAssetStreamResponse(asset, "bytes=2-5", "GET");
    expect(response.status).toBe(206);
    expect(response.headers.get("content-range")).toBe("bytes 2-5/10");
    expect(response.headers.get("content-length")).toBe("4");
    expect(await response.text()).toBe("2345");
  });

  it("answers HEAD without a body", async () => {
    const response = vizzyAssetStreamResponse(asset, null, "HEAD");
    expect(response.status).toBe(200);
    expect(response.headers.get("content-length")).toBe("10");
    expect(response.body).toBeNull();
  });
});

describe("asset resolution", () => {
  it("maps the built bundle's extensionless FNT/OBJ assets to readable types", () => {
    expect(mimeForAsset("fonts/DejaVu-sdf.fnt")).toContain("text/plain");
    expect(mimeForAsset("models/teapot.obj")).toContain("text/plain");
    expect(mimeForAsset("assets/worker-abc.js")).toBe("text/javascript; charset=utf-8");
    expect(mimeForAsset("assets/ffmpeg-core.wasm")).toBe("application/wasm");
  });

  it("resolves a nested file and rejects traversal", () => {
    expect(resolveVizzyAsset(root, "/asset.bin")).toMatchObject({ ok: true });
    expect(resolveVizzyAsset(root, "/../asset.bin")).toMatchObject({ ok: false, status: 403 });
  });
});

describe("staged template library routing", () => {
  let libraryRoot: string;

  beforeAll(() => {
    libraryRoot = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-vizzy-lib-"));
    fs.mkdirSync(path.join(libraryRoot, "creations", "templates"), { recursive: true });
    fs.mkdirSync(path.join(libraryRoot, "creations", "thumbs"), { recursive: true });
    fs.writeFileSync(path.join(libraryRoot, "creations", "manifest.json"), '{"creations":[]}');
    fs.writeFileSync(path.join(libraryRoot, "creations", "templates", "a.json"), "{}");
    fs.writeFileSync(path.join(libraryRoot, "creations", "thumbs", "a.jpg"), "jpg");
  });

  afterAll(() => {
    fs.rmSync(libraryRoot, { recursive: true, force: true });
  });

  it("serves /creations from the library when one is staged", () => {
    expect(resolveVizzyRequest(root, libraryRoot, "/creations/manifest.json")).toMatchObject({
      ok: true,
    });
    expect(resolveVizzyRequest(root, libraryRoot, "/creations/templates/a.json")).toMatchObject({
      ok: true,
    });
    expect(resolveVizzyRequest(root, libraryRoot, "/creations/thumbs/a.jpg")).toMatchObject({
      ok: true,
    });
  });

  it("keeps the editor bundle for non-library paths", () => {
    expect(resolveVizzyRequest(root, libraryRoot, "/asset.bin")).toMatchObject({ ok: true });
  });

  it("rejects traversal out of the library and falls back without one", () => {
    expect(resolveVizzyRequest(root, libraryRoot, "/creations/../asset.bin")).toMatchObject({
      ok: false,
      status: 403,
    });
    expect(resolveVizzyRequest(root, null, "/creations/manifest.json")).toMatchObject({
      ok: false,
      status: 404,
    });
  });
});
