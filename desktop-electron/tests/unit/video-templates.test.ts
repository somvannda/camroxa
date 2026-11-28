import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { afterEach, describe, expect, it } from "vitest";
import { extractTemplateArchive } from "../../electron/services/template-archive";
import {
  deleteVideoTemplate,
  listVideoTemplates,
  readVideoTemplate,
  saveVideoTemplate,
  writeTemplatePipeline,
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

  it("materialises a pipeline for an installed marketplace folder", () => {
    const root = tempRoot();
    const dir = path.join(root, "installed-item");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "template.json"), fixture, "utf8");
    fs.writeFileSync(path.join(dir, "manifest.json"), JSON.stringify({ name: "Neon" }), "utf8");

    const pipeline = writeTemplatePipeline(dir, "Neon Spectrum");
    expect(pipeline?.project).toBe("template.json");
    expect(pipeline?.name).toBe("Neon Spectrum");

    const listed = listVideoTemplates(root);
    expect(listed.map((entry) => entry.id)).toEqual(["installed-item"]);
    expect(listed[0]?.thumbnailPath).toBeNull();
    const detail = readVideoTemplate(root, "installed-item");
    expect(detail.name).toBe("Neon Spectrum");
    expect(JSON.parse(detail.projectJson)).toEqual(JSON.parse(fixture));
  });

  it("keeps marketplace thumbnails that are not PNG", () => {
    const root = tempRoot();
    const dir = path.join(root, "jpeg-item");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "template.json"), fixture, "utf8");
    fs.writeFileSync(path.join(dir, "thumbnail.jpg"), Buffer.from("jpeg"));
    writeTemplatePipeline(dir, "JPEG Template");
    expect(listVideoTemplates(root)[0]?.thumbnailPath).toBe(path.join(dir, "thumbnail.jpg"));
  });

  it("turns an extracted marketplace archive into a picker entry", () => {
    const root = tempRoot();
    const zip = new AdmZip();
    zip.addFile("template.json", Buffer.from(fixture, "utf8"));
    zip.addFile("manifest.json", Buffer.from(JSON.stringify({ name: "Neon" }), "utf8"));
    zip.addFile("preview.png", Buffer.concat([PNG, Buffer.from("preview")]));
    const archive = extractTemplateArchive(zip.toBuffer(), path.join(root, "item"));

    const pipeline = writeTemplatePipeline(path.join(root, "item"), archive.name, {
      projectFile: archive.templateEntry,
    });
    expect(pipeline?.kind).toBe("long");

    const listed = listVideoTemplates(root);
    expect(listed.map((entry) => entry.id)).toEqual(["item"]);
    expect(listed[0]?.thumbnailPath).toBe(path.join(root, "item", "preview.png"));
    expect(readVideoTemplate(root, "item").projectJson).toBe(fixture);
  });

  it("skips projects that are not Camxora studio projects", () => {    const root = tempRoot();
    const dir = path.join(root, "legacy-item");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(
      path.join(dir, "template.json"),
      JSON.stringify({ name: "Legacy", objects: {}, values: {} }),
      "utf8",
    );
    expect(writeTemplatePipeline(dir, "Legacy")).toBeNull();
    expect(listVideoTemplates(root)).toEqual([]);
  });
});
