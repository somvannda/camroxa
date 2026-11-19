import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  findLibraryTemplate,
  readLibrary,
  readLibraryProject,
  resolveLibraryRoot,
} from "../../electron/services/vizzy-library";

const roots: string[] = [];

function makeLibrary(manifest: unknown, files: Record<string, string> = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-library-"));
  roots.push(root);
  fs.mkdirSync(path.join(root, "templates"), { recursive: true });
  fs.mkdirSync(path.join(root, "thumbs"), { recursive: true });
  for (const [name, body] of Object.entries(files)) {
    const target = path.join(root, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, body);
  }
  fs.writeFileSync(path.join(root, "manifest.json"), JSON.stringify(manifest));
  return root;
}

const twoTemplates = {
  schemaVersion: 1,
  count: 2,
  templates: [
    {
      slug: "alpha",
      name: "Alpha",
      project: "templates/alpha.json",
      thumbnail: "thumbs/alpha.jpg",
      hasAssets: true,
      jsonBytes: 12,
      assetBytes: 1024,
    },
    {
      slug: "beta",
      name: "Beta",
      project: "templates/beta.json",
      thumbnail: null,
      hasAssets: false,
      jsonBytes: 10,
      assetBytes: 0,
    },
  ],
};

const twoFiles = {
  "templates/alpha.json": '{"name":"Alpha"}',
  "templates/beta.json": '{"name":"Beta"}',
  "thumbs/alpha.jpg": "jpg",
};

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
  delete process.env.CAMXORA_VIZZY_LIBRARY_DIR;
});

describe("vizzy library", () => {
  it("reads the manifest and resolves files", () => {
    const root = makeLibrary(twoTemplates, twoFiles);
    const library = readLibrary(root);
    expect(library.count).toBe(2);
    expect(library.templates.map((entry) => entry.slug)).toEqual(["alpha", "beta"]);
    expect(library.templates[0]?.thumbnailPath).toBe(path.join(root, "thumbs", "alpha.jpg"));
    expect(library.templates[1]?.thumbnailPath).toBeNull();
    expect(library.templates[1]?.name).toBe("Beta");
  });

  it("rejects a missing manifest, bad schema and count drift", () => {
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-library-"));
    roots.push(empty);
    expect(() => readLibrary(empty)).toThrow(/not staged/i);

    const badSchema = makeLibrary({ schemaVersion: 2, templates: [] });
    expect(() => readLibrary(badSchema)).toThrow(/unsupported schema/i);

    const drifted = makeLibrary({ ...twoTemplates, count: 3 }, twoFiles);
    expect(() => readLibrary(drifted)).toThrow(/lists 3 templates but has 2/i);
  });

  it("rejects a manifest row whose project file is missing", () => {
    const root = makeLibrary(twoTemplates, { "templates/alpha.json": "{}" });
    expect(() => readLibrary(root)).toThrow(/missing its project file/i);
  });

  it("opens by slug and never by path", () => {
    const root = makeLibrary(twoTemplates, twoFiles);
    expect(readLibraryProject(root, "alpha").json).toBe('{"name":"Alpha"}');
    expect(findLibraryTemplate(root, "nope")).toBeNull();
    expect(() => readLibraryProject(root, "../manifest.json")).toThrow(/unknown vizzy template/i);
    expect(() => readLibraryProject(root, "..\\alpha")).toThrow(/unknown vizzy template/i);
  });

  it("honours the env override", () => {
    process.env.CAMXORA_VIZZY_LIBRARY_DIR = "G:/library";
    expect(resolveLibraryRoot()).toBe(path.resolve("G:/library"));
  });
});
