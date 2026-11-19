import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { afterEach, describe, expect, it } from "vitest";
import {
  extractTemplateArchive,
  normalizeArchiveEntry,
  readTemplateArchive,
  TemplateArchiveError,
} from "../../electron/services/template-archive";

function buildZip(files: Record<string, string>): Buffer {
  const zip = new AdmZip();
  for (const [name, content] of Object.entries(files)) {
    zip.addFile(name, Buffer.from(content, "utf8"));
  }
  return zip.toBuffer();
}

const TEMPLATE = JSON.stringify({ name: "Night Drive", objects: [], schema: "vizzy" });
const MANIFEST = JSON.stringify({ name: "Night Drive", kind: "video", schema: "vizzy" });

const tempDirs: string[] = [];

function tempDir(): string {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-archive-"));
  tempDirs.push(directory);
  return directory;
}

afterEach(() => {
  for (const directory of tempDirs.splice(0)) {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

describe("template archive validation", () => {
  it("reads a valid archive and extracts it", () => {
    const buffer = buildZip({
      "template.json": TEMPLATE,
      "manifest.json": MANIFEST,
      "assets/logo.png": "png",
    });
    const archive = readTemplateArchive(buffer);
    expect(archive.name).toBe("Night Drive");
    expect(archive.kind).toBe("video");
    expect(archive.schema).toBe("vizzy");
    expect(archive.schemaVersion).toBe(2);

    const target = tempDir();
    extractTemplateArchive(buffer, target);
    expect(fs.readFileSync(path.join(target, "template.json"), "utf8")).toContain("Night Drive");
    expect(fs.existsSync(path.join(target, "assets", "logo.png"))).toBe(true);
  });

  it("finds the JSON files at the shallowest depth", () => {
    const buffer = buildZip({
      "bundle/template.json": TEMPLATE,
      "bundle/manifest.json": MANIFEST,
      "bundle/thumbnail.png": "png",
    });
    const archive = readTemplateArchive(buffer);
    expect(archive.thumbnailEntry).toBe("bundle/thumbnail.png");
    expect(archive.entries.map((entry) => entry.normalized)).toContain("bundle/template.json");
  });

  it("rejects a corrupt archive", () => {
    expect(() => readTemplateArchive(Buffer.from("not a zip"))).toThrow(TemplateArchiveError);
    expect(() => readTemplateArchive(Buffer.alloc(0))).toThrow(/empty/i);
  });

  it("rejects a zip missing template.json or manifest.json", () => {
    const withoutManifest = buildZip({ "template.json": TEMPLATE });
    expect(() => readTemplateArchive(withoutManifest)).toThrow(/missing template.json/i);
    const withoutTemplate = buildZip({ "manifest.json": MANIFEST });
    expect(() => readTemplateArchive(withoutTemplate)).toThrow(/missing template.json/i);
  });

  it("rejects invalid JSON inside the archive", () => {
    const buffer = buildZip({ "template.json": "{", "manifest.json": MANIFEST });
    expect(() => readTemplateArchive(buffer)).toThrow(/Invalid JSON/i);
  });

  it("rejects path traversal and absolute entries before writing anything", () => {
    // adm-zip sanitises names on add, so the hostile name is written straight
    // into the entry header to model a real malicious archive.
    const zip = new AdmZip();
    zip.addFile("template.json", Buffer.from(TEMPLATE, "utf8"));
    zip.addFile("manifest.json", Buffer.from(MANIFEST, "utf8"));
    zip.addFile("escape.txt", Buffer.from("owned", "utf8"));
    const hostile = zip.getEntry("escape.txt");
    if (hostile) {
      hostile.entryName = "../escape.txt";
      (hostile.header as unknown as { name: string }).name = "../escape.txt";
    }
    const buffer = zip.toBuffer();

    expect(() => readTemplateArchive(buffer)).toThrow(/path traversal/i);

    const target = tempDir();
    expect(() => extractTemplateArchive(buffer, target)).toThrow(TemplateArchiveError);
    expect(fs.existsSync(path.join(target, "..", "escape.txt"))).toBe(false);
    expect(fs.readdirSync(target)).toHaveLength(0);
  });

  it("normalises entries and blocks absolute or NUL paths", () => {
    expect(normalizeArchiveEntry("bundle\\template.json")).toBe("bundle/template.json");
    expect(() => normalizeArchiveEntry("/etc/passwd")).toThrow(/absolute/i);
    expect(() => normalizeArchiveEntry("C:/Windows/system32")).toThrow(/absolute/i);
    expect(() => normalizeArchiveEntry("a/../../b")).toThrow(/path traversal/i);
    expect(() => normalizeArchiveEntry("bad\0name")).toThrow(/invalid path/i);
  });

  it("detects legacy Camxora templates so they can be refused", () => {
    const buffer = buildZip({
      "template.json": JSON.stringify({ name: "Old", schema: "legacy" }),
      "manifest.json": JSON.stringify({ name: "Old", kind: "video" }),
    });
    expect(readTemplateArchive(buffer).schema).toBe("legacy");
  });

  it("detects an engine marker as legacy", () => {
    const buffer = buildZip({
      "template.json": JSON.stringify({ name: "Old" }),
      "manifest.json": JSON.stringify({ name: "Old", kind: "video", engine: "camxora" }),
    });
    expect(readTemplateArchive(buffer).schema).toBe("legacy");
  });
});
