import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  MAX_EXPORT_CHUNK_BYTES,
  RenderChunkWriter,
  defaultExportBitrate,
  deleteRenderFile,
  isInsideRenders,
  isRenderFileName,
  listRenderFiles,
  managedRenderPath,
  normaliseFormat,
  renderFileName,
  renderTimestamp,
  resolveExportSettings,
  uniqueRenderPath,
  validateChunkRange,
} from "../../electron/vizzy-host/renders";

let directory: string;

beforeEach(() => {
  directory = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-vizzy-renders-"));
});

afterEach(() => {
  fs.rmSync(directory, { recursive: true, force: true });
});

const PROJECT = {
  name: "Trap Motion",
  width: 1920,
  height: 1080,
  fps: 30,
  duration: 12,
};

describe("vizzy export settings", () => {
  it("defaults to 1920x1080/30/h264 when nothing is known", () => {
    const settings = resolveExportSettings(null, null);
    expect(settings).toMatchObject({
      width: 1920,
      height: 1080,
      fps: 30,
      format: "mp4",
      codec: "h264",
      start: 0,
      end: 10,
      duration: 10,
    });
    expect(settings.bitrate).toBe(25);
  });

  it("falls back to the project composition", () => {
    const settings = resolveExportSettings({}, PROJECT);
    expect(settings).toMatchObject({ width: 1920, height: 1080, fps: 30, end: 12 });
  });

  it("uses the request over the project", () => {
    const settings = resolveExportSettings(
      { width: 480, height: 270, fps: 24, start: 2, end: 4 },
      PROJECT,
    );
    expect(settings).toMatchObject({ width: 480, height: 270, fps: 24, start: 2, end: 4 });
    expect(settings.duration).toBe(2);
  });

  it("keeps dimensions even and inside the encoder range", () => {
    expect(resolveExportSettings({ width: 481, height: 271 }, PROJECT)).toMatchObject({
      width: 482,
      height: 272,
    });
    expect(resolveExportSettings({ width: 1, height: 20_000 }, PROJECT)).toMatchObject({
      width: 16,
      height: 7680,
    });
  });

  it("clamps fps, start, end and duration", () => {
    const settings = resolveExportSettings({ fps: 500, start: 30, end: -4 }, PROJECT);
    expect(settings.fps).toBe(120);
    expect(settings.start).toBe(12);
    expect(settings.end).toBeCloseTo(12.1, 5);
    expect(settings.duration).toBeCloseTo(0.1, 5);

    const negative = resolveExportSettings({ start: -5 }, PROJECT);
    expect(negative.start).toBe(0);
    expect(negative.end).toBe(12);
  });

  it("maps the container to a codec", () => {
    expect(normaliseFormat("webm")).toBe("webm");
    expect(normaliseFormat("mkv")).toBe("mp4");
    expect(resolveExportSettings({ format: "mp4", codec: "vp9" }, PROJECT).codec).toBe("h264");
    expect(resolveExportSettings({ format: "webm" }, PROJECT).codec).toBe("vp9");
    expect(resolveExportSettings({ format: "webm", codec: "vp8" }, PROJECT).codec).toBe("vp8");
    expect(resolveExportSettings({ format: "webm", codec: "h264" }, PROJECT).codec).toBe("vp9");
  });

  it("tracks the bitrate to the height and clamps crf", () => {
    expect(defaultExportBitrate(360)).toBe(5);
    expect(defaultExportBitrate(720)).toBe(15);
    expect(defaultExportBitrate(1080)).toBe(25);
    expect(resolveExportSettings({ height: 720 }, PROJECT).bitrate).toBe(15);
    expect(resolveExportSettings({ bitrate: 999, crf: 99 }, PROJECT)).toMatchObject({
      bitrate: 200,
      crf: 51,
    });
    expect(resolveExportSettings({ bitrate: -2, crf: -2 }, PROJECT)).toMatchObject({
      bitrate: 0,
      crf: 0,
    });
  });
});

describe("vizzy render names", () => {
  const when = new Date(2026, 10, 19, 14, 25, 30);

  it("formats a sortable local timestamp", () => {
    expect(renderTimestamp(when)).toBe("20261119-142530");
  });

  it("builds <slug>-<timestamp>.<ext> from the project name only", () => {
    expect(renderFileName("Trap Motion", "mp4", when)).toBe("trap-motion-20261119-142530.mp4");
    expect(renderFileName("", "webm", when)).toBe("untitled-project-20261119-142530.webm");
    expect(renderFileName("user@example.com", "mp4", when)).toBe(
      "user-example-com-20261119-142530.mp4",
    );
  });

  it("only accepts names the exporter produced", () => {
    expect(isRenderFileName("trap-motion-20261119-142530.mp4")).toBe(true);
    expect(isRenderFileName("trap-motion-20261119-142530-2.webm")).toBe(true);
    expect(isRenderFileName("../../secret.mp4")).toBe(false);
    expect(isRenderFileName("C:\\secret.mp4")).toBe(false);
    expect(isRenderFileName("trap-motion.mp4")).toBe(false);
    expect(isRenderFileName("trap-motion-20261119-142530.mkv")).toBe(false);
    expect(isRenderFileName("Trap-Motion-20261119-142530.mp4")).toBe(false);
    expect(isRenderFileName("")).toBe(false);
    expect(isRenderFileName(null)).toBe(false);
  });

  it("picks a free name instead of overwriting", () => {
    const first = path.join(directory, "a-20261119-142530.mp4");
    fs.writeFileSync(first, "x");
    expect(path.basename(uniqueRenderPath(directory, "a-20261119-142530.mp4"))).toBe(
      "a-20261119-142530-2.mp4",
    );
  });

  it("resolves only paths strictly inside renders/", () => {
    expect(isInsideRenders(directory, path.join(directory, "a.mp4"))).toBe(true);
    expect(isInsideRenders(directory, directory)).toBe(false);
    expect(isInsideRenders(directory, path.join(directory, "..", "a.mp4"))).toBe(false);
    expect(managedRenderPath(directory, "../a-20261119-142530.mp4")).toBeNull();
    expect(managedRenderPath(directory, "a-20261119-142530.mp4")).toBe(
      path.join(path.resolve(directory), "a-20261119-142530.mp4"),
    );
  });
});

describe("vizzy renders directory", () => {
  it("lists only managed video files, newest first", () => {
    const older = path.join(directory, "one-20261119-142530.mp4");
    const newer = path.join(directory, "two-20261119-142531.webm");
    fs.writeFileSync(older, "a");
    fs.writeFileSync(newer, "bb");
    fs.writeFileSync(path.join(directory, "notes.txt"), "ignore me");
    fs.mkdirSync(path.join(directory, "folder-20261119-142532.mp4"));
    // The filesystem may hand both files the same mtime; make the order explicit.
    fs.utimesSync(older, new Date(2026, 10, 19, 14, 25, 30), new Date(2026, 10, 19, 14, 25, 30));
    fs.utimesSync(newer, new Date(2026, 10, 19, 14, 26, 30), new Date(2026, 10, 19, 14, 26, 30));

    const listed = listRenderFiles(directory);
    expect(listed.map((item) => item.name)).toEqual([
      "two-20261119-142531.webm",
      "one-20261119-142530.mp4",
    ]);
    expect(listed[0].bytes).toBe(2);
    expect(listed[0].mtimeMs).toBeGreaterThan(0);
  });

  it("returns an empty list for a missing directory", () => {
    expect(listRenderFiles(path.join(directory, "missing"))).toEqual([]);
  });

  it("deletes a managed render and refuses everything else", () => {
    const name = "one-20261119-142530.mp4";
    const file = path.join(directory, name);
    fs.writeFileSync(file, "a");
    expect(deleteRenderFile(directory, "../one-20261119-142530.mp4")).toBe(false);
    expect(deleteRenderFile(directory, "notes.txt")).toBe(false);
    expect(fs.existsSync(file)).toBe(true);
    expect(deleteRenderFile(directory, name)).toBe(true);
    expect(fs.existsSync(file)).toBe(false);
    expect(deleteRenderFile(directory, name)).toBe(false);
  });
});

describe("vizzy render chunk writer", () => {
  it("validates positions and sizes", () => {
    expect(validateChunkRange(0, 16)).toEqual({ ok: true });
    expect(validateChunkRange(-1, 16).ok).toBe(false);
    expect(validateChunkRange(1.5, 16).ok).toBe(false);
    expect(validateChunkRange(0, 0).ok).toBe(false);
    expect(validateChunkRange(0, MAX_EXPORT_CHUNK_BYTES + 1).ok).toBe(false);
    expect(validateChunkRange(0, "16").ok).toBe(false);
  });

  it("writes at absolute offsets and tracks the highest byte", async () => {
    const writes: Array<{ position: number; bytes: number[] }> = [];
    let closed = 0;
    const writer = new RenderChunkWriter({
      writeAt: async (buffer, position) => {
        writes.push({ position, bytes: Array.from(buffer) });
      },
      close: async () => {
        closed += 1;
      },
    });

    await writer.write(4, new Uint8Array([5, 6]));
    await writer.write(0, new Uint8Array([1, 2, 3, 4]));
    expect(writes).toEqual([
      { position: 4, bytes: [5, 6] },
      { position: 0, bytes: [1, 2, 3, 4] },
    ]);
    expect(writer.bytes).toBe(6);

    await writer.close();
    await writer.close();
    expect(closed).toBe(1);
    await expect(writer.write(6, new Uint8Array([7]))).rejects.toThrow(/closed/i);
  });

  it("refuses an invalid chunk without touching the sink", async () => {
    let calls = 0;
    const writer = new RenderChunkWriter({
      writeAt: async () => {
        calls += 1;
      },
      close: async () => undefined,
    });
    await expect(writer.write(-4, new Uint8Array([1]))).rejects.toThrow(/position/i);
    expect(calls).toBe(0);
  });

  it("propagates a sink failure", async () => {
    const writer = new RenderChunkWriter({
      writeAt: async () => {
        throw new Error("disk full");
      },
      close: async () => undefined,
    });
    await expect(writer.write(0, new Uint8Array([1]))).rejects.toThrow("disk full");
    expect(writer.bytes).toBe(0);
  });
});
