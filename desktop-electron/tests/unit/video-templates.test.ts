import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  deleteVideoTemplate,
  listVideoTemplates,
  readVideoTemplate,
  saveVideoTemplate,
} from "../../electron/services/video-templates";

const roots: string[] = [];
const fixture = fs.readFileSync(
  path.resolve(__dirname, "../fixtures/vizzy/trap-motion.camxora-vizzy.json"),
  "utf8",
);
const PNG = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  Buffer.from("fake"),
]);

function tempRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-templates-"));
  roots.push(root);
  return root;
}

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe("video templates", () => {
  it("saves a template atomically and lists it", () => {
    const root = tempRoot();
    const saved = saveVideoTemplate({
      root,
      name: "Trap Motion",
      snapshotJson: fixture,
      thumbnail: PNG,
      createdAt: "2026-11-19T00:00:00.000Z",
    });
    expect(saved.id).toBe("trap-motion");
    expect(saved.kind).toBe("long");
    expect(saved.thumbnailPath).toBe(path.join(root, "trap-motion", "thumbnail.png"));
    for (const file of ["template.json", "pipeline.json", "thumbnail.png"]) {
      expect(fs.existsSync(path.join(root, "trap-motion", file))).toBe(true);
    }
    const listed = listVideoTemplates(root);
    expect(listed).toHaveLength(1);
    expect(listed[0]?.name).toBe("Trap Motion");
    expect(listed[0]?.output).toEqual({ width: 1920, height: 1080, fps: 30 });
  });

  it("opens a saved template and returns the exact project", () => {
    const root = tempRoot();
    saveVideoTemplate({ root, name: "Trap Motion", snapshotJson: fixture, id: "trap" });
    const detail = readVideoTemplate(root, "trap");
    expect(detail.pipeline.project).toBe("template.json");
    expect(detail.pipeline.bindings.background?.nodeId).toBeTruthy();
    const parsed = JSON.parse(detail.projectJson);
    expect(parsed.format).toBe("studio-project");
    expect(Array.isArray(parsed.nodes)).toBe(true);
  });

  it("gives same-named templates distinct ids and rejects duplicate ids", () => {
    const root = tempRoot();
    const first = saveVideoTemplate({ root, name: "Same", snapshotJson: fixture });
    const second = saveVideoTemplate({ root, name: "Same", snapshotJson: fixture });
    expect(first.id).toBe("same");
    expect(second.id).toBe("same-2");
    expect(() =>
      saveVideoTemplate({ root, name: "Same", snapshotJson: fixture, id: first.id }),
    ).toThrow(/already exists/i);
  });

  it("overwrites an existing template in place when asked", () => {
    const root = tempRoot();
    const first = saveVideoTemplate({
      root,
      name: "Trap Motion",
      snapshotJson: fixture,
      thumbnail: PNG,
      createdAt: "2026-11-19T00:00:00.000Z",
    });
    const updated = saveVideoTemplate({
      root,
      id: first.id,
      overwrite: true,
      name: "Trap Motion Updated",
      snapshotJson: fixture,
    });
    expect(updated.id).toBe(first.id);
    expect(updated.name).toBe("Trap Motion Updated");
    const detail = readVideoTemplate(root, first.id);
    expect(detail.pipeline.name).toBe("Trap Motion Updated");
    expect(detail.pipeline.createdAt).toBe("2026-11-19T00:00:00.000Z");
    expect(listVideoTemplates(root)).toHaveLength(1);
    expect(fs.existsSync(path.join(root, first.id, "thumbnail.png"))).toBe(false);
    expect(fs.readdirSync(root).some((name) => name.startsWith(".bak-"))).toBe(false);
  });

  it("rejects invalid snapshots, thumbnails and ids", () => {
    const root = tempRoot();
    expect(() => saveVideoTemplate({ root, name: "Bad", snapshotJson: "{}" })).toThrow(
      /not a Camxora Vizzy project/i,
    );
    expect(() =>
      saveVideoTemplate({ root, name: "Bad", snapshotJson: fixture, thumbnail: Buffer.from("no") }),
    ).toThrow(/must be a PNG/i);
    expect(() =>
      saveVideoTemplate({ root, name: "Bad", snapshotJson: fixture, id: "../escape" }),
    ).toThrow(/not valid/i);
    expect(() => readVideoTemplate(root, "../escape")).toThrow(/not valid/i);
    expect(deleteVideoTemplate(root, "../escape")).toBe(false);
  });

  it("deletes a template and ignores junk directories", () => {
    const root = tempRoot();
    saveVideoTemplate({ root, name: "Trap Motion", snapshotJson: fixture, id: "trap" });
    fs.mkdirSync(path.join(root, "junk"), { recursive: true });
    fs.writeFileSync(path.join(root, "junk", "pipeline.json"), "{}");
    expect(listVideoTemplates(root).map((entry) => entry.id)).toEqual(["trap"]);
    expect(deleteVideoTemplate(root, "trap")).toBe(true);
    expect(listVideoTemplates(root)).toEqual([]);
  });
});
