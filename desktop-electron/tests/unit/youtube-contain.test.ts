import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  discoverMergedFile,
  isContainedIn,
  resolveContainedVideo,
  thumbnailBeside,
  UploadFileError,
} from "../../electron/services/youtube-contain";

const roots: string[] = [];

function tempRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-yt-path-"));
  roots.push(root);
  return root;
}

function write(filePath: string, bytes = 16): string {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, Buffer.alloc(bytes, 1));
  return filePath;
}

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

function codeOf(fn: () => unknown): string {
  try {
    fn();
    return "none";
  } catch (error) {
    return error instanceof UploadFileError ? error.code : "unknown";
  }
}

describe("upload path containment", () => {
  it("accepts a merged MP4 inside the run folder", () => {
    const root = tempRoot();
    const runDir = path.join(root, "2026-11-19_Night Shift");
    const file = write(path.join(runDir, "NS-01-merged.mp4"), 2048);
    const resolved = resolveContainedVideo({
      filePath: file,
      runDir,
      managedRoots: [path.join(root, "downloads")],
    });
    expect(resolved.path).toBe(fs.realpathSync(file));
    expect(resolved.name).toBe("NS-01-merged.mp4");
    expect(resolved.bytes).toBe(2048);
  });

  it("accepts a file inside the managed downloads/renders roots", () => {
    const root = tempRoot();
    const renders = path.join(root, "renders");
    const file = write(path.join(renders, "export.mp4"));
    expect(
      resolveContainedVideo({ filePath: file, runDir: null, managedRoots: [renders] }).name,
    ).toBe("export.mp4");
  });

  it("refuses path traversal outside the run folder and managed roots", () => {
    const root = tempRoot();
    const runDir = path.join(root, "run");
    fs.mkdirSync(runDir, { recursive: true });
    const secret = write(path.join(root, "secret.mp4"));
    expect(
      codeOf(() =>
        resolveContainedVideo({
          filePath: path.join(runDir, "..", "secret.mp4"),
          runDir,
          managedRoots: [],
        }),
      ),
    ).toBe("UPLOAD_FILE_OUTSIDE_ROOTS");
    expect(
      codeOf(() => resolveContainedVideo({ filePath: secret, runDir, managedRoots: [] })),
    ).toBe("UPLOAD_FILE_OUTSIDE_ROOTS");
  });

  it("refuses a sibling folder that merely shares a prefix", () => {
    const root = tempRoot();
    const runDir = path.join(root, "run");
    fs.mkdirSync(runDir, { recursive: true });
    const sibling = write(path.join(root, "run-escape", "video.mp4"));
    expect(
      codeOf(() => resolveContainedVideo({ filePath: sibling, runDir, managedRoots: [] })),
    ).toBe("UPLOAD_FILE_OUTSIDE_ROOTS");
    expect(isContainedIn(sibling, [runDir])).toBe(false);
    expect(isContainedIn(path.join(runDir, "a.mp4"), [runDir])).toBe(true);
  });

  it("refuses a non-MP4, a missing file and an empty file", () => {
    const root = tempRoot();
    const runDir = path.join(root, "run");
    const text = write(path.join(runDir, "notes.txt"));
    expect(codeOf(() => resolveContainedVideo({ filePath: text, runDir, managedRoots: [] }))).toBe(
      "UPLOAD_FILE_NOT_VIDEO",
    );
    expect(
      codeOf(() =>
        resolveContainedVideo({ filePath: path.join(runDir, "gone.mp4"), runDir, managedRoots: [] }),
      ),
    ).toBe("UPLOAD_FILE_MISSING");
    const empty = write(path.join(runDir, "empty.mp4"), 0);
    expect(codeOf(() => resolveContainedVideo({ filePath: empty, runDir, managedRoots: [] }))).toBe(
      "UPLOAD_FILE_EMPTY",
    );
    expect(
      codeOf(() => resolveContainedVideo({ filePath: "", runDir: null, managedRoots: [] })),
    ).toBe("UPLOAD_FILE_MISSING");
  });
});

describe("merged-file discovery", () => {
  it("prefers the newest *-merged MP4 and ignores reel variants", () => {
    const runDir = tempRoot();
    const older = write(path.join(runDir, "batch-merged.mp4"), 32);
    fs.utimesSync(older, new Date(1000), new Date(1000));
    const newer = write(path.join(runDir, "batch-merged-2.mp4"), 64);
    write(path.join(runDir, "batch_REEL.mp4"), 16);
    expect(discoverMergedFile(runDir)).toBe(newer);
  });

  it("falls back to a merged/ subfolder", () => {
    const runDir = tempRoot();
    const nested = write(path.join(runDir, "merged", "output.mp4"), 8);
    expect(discoverMergedFile(runDir)).toBe(nested);
  });

  it("returns null without a run folder or a video", () => {
    expect(discoverMergedFile("")).toBeNull();
    expect(discoverMergedFile(path.join(os.tmpdir(), "camxora-does-not-exist"))).toBeNull();
    const emptyRun = tempRoot();
    write(path.join(emptyRun, "notes.txt"));
    expect(discoverMergedFile(emptyRun)).toBeNull();
  });

  it("finds a thumbnail beside the merge only when it is a real file", () => {
    const runDir = tempRoot();
    const merged = write(path.join(runDir, "x-merged.mp4"));
    expect(thumbnailBeside(merged)).toBeNull();
    const thumbnail = write(path.join(runDir, "thumbnail-16x9.png"), 8);
    expect(thumbnailBeside(merged)).toBe(thumbnail);
  });
});
