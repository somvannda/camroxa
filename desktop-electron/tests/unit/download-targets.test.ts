import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  checkDownloadUrl,
  defaultDownloadFileName,
  hasTraversal,
  normalizePendingDownloads,
  resolveDownloadTarget,
  sanitizeFileStem,
  targetKey,
} from "../../electron/services/download-targets";

const ROOT = path.resolve("/camxora-root/suno");
const URL_OK = "https://cdn.example.test/a.mp3";

function resolve(overrides: Partial<Parameters<typeof resolveDownloadTarget>[0]> = {}) {
  return resolveDownloadTarget(
    {
      taskId: "task-1",
      role: "primary",
      songId: "song-1",
      batchId: "batch-1",
      title: "Night Drive",
      trackNumber: 2,
      url: URL_OK,
      targetPath: null,
      outputDir: null,
      ...overrides,
    },
    { root: ROOT },
  );
}

describe("download target resolution", () => {
  it("accepts an absolute target inside the root", () => {
    const target = path.join(ROOT, "night", "01 Night Drive.mp3");
    const result = resolve({ targetPath: target });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.target.path).toBe(target);
    expect(result.target.key).toBe("task-1::primary");
  });

  it("joins a relative target under the root and creates the folder later", () => {
    const result = resolve({ targetPath: path.join("night", "01 Night Drive.mp3") });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.target.path).toBe(path.join(ROOT, "night", "01 Night Drive.mp3"));
  });

  it("uses the sanitised track and title when no target is reported", () => {
    const result = resolve({ title: "AC/DC: Live?", trackNumber: 3 });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.target.path).toBe(path.join(ROOT, "03 AC-DC- Live-.mp3"));
    expect(defaultDownloadFileName("AC/DC: Live?", 3, null)).toBe("03 AC-DC- Live-.mp3");
  });

  it("honours a server output folder only when it is inside the root", () => {
    const inside = resolve({ outputDir: path.join(ROOT, "night") });
    expect(inside.ok).toBe(true);
    if (inside.ok) {
      expect(inside.target.path).toBe(path.join(ROOT, "night", "02 Night Drive.mp3"));
    }

    const outside = resolve({ outputDir: path.resolve(ROOT, "..", "elsewhere") });
    expect(outside.ok).toBe(false);
    if (!outside.ok) expect(outside.code).toBe("DOWNLOAD_TARGET_OUTSIDE");
  });

  it("rejects traversal, absolute escapes and folder targets", () => {
    const traversal = resolve({ targetPath: `${ROOT}/../escape.mp3` });
    expect(traversal.ok).toBe(false);
    if (!traversal.ok) expect(traversal.code).toBe("DOWNLOAD_TARGET_UNSAFE");

    const escaped = resolve({ targetPath: path.resolve(ROOT, "..", "escape.mp3") });
    expect(escaped.ok).toBe(false);
    if (!escaped.ok) expect(escaped.code).toBe("DOWNLOAD_TARGET_OUTSIDE");

    const folder = resolve({ targetPath: `${ROOT}${path.sep}` });
    expect(folder.ok).toBe(false);
    if (!folder.ok) expect(folder.code).toBe("DOWNLOAD_NOT_A_FILE");

    expect(hasTraversal("..\\evil.mp3")).toBe(true);
    expect(hasTraversal("night/..hidden.mp3")).toBe(false);
    expect(hasTraversal("night/01.mp3")).toBe(false);
  });

  it("adds the mp3 extension only when the name has none", () => {
    const missing = resolve({ targetPath: path.join(ROOT, "track") });
    expect(missing.ok).toBe(true);
    if (missing.ok) expect(missing.target.path).toBe(path.join(ROOT, "track.mp3"));

    const wav = resolve({ targetPath: path.join(ROOT, "track.wav") });
    expect(wav.ok).toBe(true);
    if (wav.ok) expect(wav.target.path).toBe(path.join(ROOT, "track.wav"));
  });

  it("reports a missing URL as a specific failure", () => {
    const result = resolve({ url: null });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("DOWNLOAD_URL_MISSING");
    expect(resolve({ url: "   " }).ok).toBe(false);
  });
});

describe("download URL guard", () => {
  it("only allows http(s) and refuses embedded credentials", () => {
    expect(checkDownloadUrl(URL_OK, false).ok).toBe(true);
    expect(checkDownloadUrl("http://example.test/a.mp3", false).ok).toBe(true);
    expect(checkDownloadUrl("file:///C:/music/a.mp3", false).ok).toBe(false);
    expect(checkDownloadUrl("javascript:alert(1)", false).ok).toBe(false);
    expect(checkDownloadUrl("not a url", false).ok).toBe(false);
    expect(checkDownloadUrl("https://user:secret@example.test/a.mp3", false).ok).toBe(false);
    expect(checkDownloadUrl("", false).ok).toBe(false);
  });

  it("allows loopback http only for E2E runs", () => {
    for (const url of [
      "http://127.0.0.1:4100/a.mp3",
      "http://localhost:4100/a.mp3",
      "http://[::1]:4100/a.mp3",
    ]) {
      expect(checkDownloadUrl(url, false).ok).toBe(false);
      expect(checkDownloadUrl(url, true).ok).toBe(true);
    }
    expect(checkDownloadUrl("http://192.168.1.10/a.mp3", false).ok).toBe(true);
  });
});

describe("server payload normalisation", () => {
  it("keeps well-shaped items and drops noise", () => {
    const items = normalizePendingDownloads({
      items: [
        { task_id: "task-1", title: "Night Drive", track_number: 2, primary: { download_url: URL_OK } },
        { title: "no id" },
        null,
        "nope",
      ],
    });
    expect(items).toHaveLength(1);
    expect(items[0].task_id).toBe("task-1");
    expect(items[0].primary?.download_url).toBe(URL_OK);
    expect(normalizePendingDownloads(null)).toEqual([]);
    expect(normalizePendingDownloads({ items: "nope" })).toEqual([]);
  });

  it("keys targets by task and role, never by path", () => {
    expect(targetKey("task-1", "primary")).toBe("task-1::primary");
    expect(targetKey("task-1", "secondary")).toBe("task-1::secondary");
    expect(sanitizeFileStem("  a/b  ")).toBe("a-b");
    expect(sanitizeFileStem("")).toBe("download");
  });
});
