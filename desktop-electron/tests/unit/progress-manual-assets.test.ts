import { describe, expect, it } from "vitest";
import {
  inspectRunDirectory,
  joinRunPath,
  missingAssetHint,
} from "../../src/features/progress/manual-assets";

describe("manual asset inspection", () => {
  it("marks the run ready when all four expected images exist", async () => {
    const directory = "C:\\runs\\ok";
    const present = new Set([
      "C:\\runs\\ok\\background-16x9.png",
      "C:\\runs\\ok\\background-9x16.jpg",
      "C:\\runs\\ok\\thumbnail-16x9.jpeg",
      "C:\\runs\\ok\\thumbnail-9x16.webp",
    ]);
    const inspection = await inspectRunDirectory(directory, async (path) => present.has(path));
    expect(inspection.ready).toBe(true);
    expect(inspection.readyCount).toBe(4);
    expect(inspection.missing).toEqual([]);
    expect(inspection.files.map((file) => file.fileName)).toEqual([
      "background-16x9.png",
      "background-9x16.jpg",
      "thumbnail-16x9.jpeg",
      "thumbnail-9x16.webp",
    ]);
  });

  it("reports the missing labels and keeps Continue disabled", async () => {
    const directory = "C:\\runs\\partial";
    const inspection = await inspectRunDirectory(directory, async (path) =>
      path.endsWith("background-16x9.png"),
    );
    expect(inspection.ready).toBe(false);
    expect(inspection.readyCount).toBe(1);
    expect(inspection.missing).toEqual(["BG 9:16", "TH 16:9", "TH 9:16"]);
    expect(missingAssetHint(inspection.missing)).toContain("BG 9:16");
  });

  it("treats a probe error as not ready and surfaces the message", async () => {
    const inspection = await inspectRunDirectory("C:\\denied", async () => {
      throw new Error("Access is denied.");
    });
    expect(inspection.ready).toBe(false);
    expect(inspection.error).toBe("Access is denied.");
    expect(inspection.missing).toHaveLength(4);
  });

  it("explains a run with no folder on this device", async () => {
    const inspection = await inspectRunDirectory("", async () => true);
    expect(inspection.ready).toBe(false);
    expect(inspection.error).toBe("This run has no folder on this device.");
  });

  it("joins Windows and POSIX run folders with the matching separator", () => {
    expect(joinRunPath("C:\\runs\\ok", "a.png")).toBe("C:\\runs\\ok\\a.png");
    expect(joinRunPath("/runs/ok/", "a.png")).toBe("/runs/ok/a.png");
    expect(joinRunPath("", "a.png")).toBe("a.png");
  });
});
