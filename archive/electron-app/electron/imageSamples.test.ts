import { describe, expect, it } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fs } from "node:fs";
import { isSupportedImageFileName, listImagesInFolder } from "./imageSamples";

describe("imageSamples", () => {
  it("detects supported image extensions", () => {
    expect(isSupportedImageFileName("a.png")).toBe(true);
    expect(isSupportedImageFileName("b.JPG")).toBe(true);
    expect(isSupportedImageFileName("c.webp")).toBe(true);
    expect(isSupportedImageFileName("d.txt")).toBe(false);
  });

  it("lists images in folder sorted by name", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "mg-img-"));
    try {
      await fs.writeFile(path.join(dir, "b.png"), "x");
      await fs.writeFile(path.join(dir, "a.jpg"), "x");
      await fs.writeFile(path.join(dir, "z.txt"), "x");

      const items = await listImagesInFolder(dir);
      expect(items.map((x) => x.fileName)).toEqual(["a.jpg", "b.png"]);
      expect(items[0]?.fileUrl.startsWith("mgsamples://")).toBe(true);
    } finally {
      await fs.rm(dir, { recursive: true, force: true });
    }
  });
});
