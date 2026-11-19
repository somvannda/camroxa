import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  VIZZY_PROJECT_EXTENSION,
  atomicWriteText,
  isInsidePath,
  parseProjectText,
  projectFilePath,
  projectSemanticKey,
  projectsAreEquivalent,
  readProjectFile,
  serialiseProjectFile,
  slugifyProjectName,
} from "../../electron/vizzy-host/project-store";

let directory: string;

beforeEach(() => {
  directory = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-vizzy-project-"));
});

afterEach(() => {
  fs.rmSync(directory, { recursive: true, force: true });
});

function snapshot(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    format: "studio-project",
    version: 1,
    savedAt: "2026-11-19T00:00:00.000Z",
    project: { id: "project_1", name: "Demo", width: 1920, height: 1080 },
    nodes: [{ id: "node_1", kind: "spectrum", name: "Spectrum" }],
    layers: [{ id: "layer_1", name: "2D Visualizers", nodeIds: ["node_1"] }],
    automations: [],
    automationGroups: [],
    analyzers: [],
    effects: [],
    assets: [],
    ...overrides,
  });
}

describe("vizzy project names", () => {
  it("slugifies a project name into a file-safe stem", () => {
    expect(slugifyProjectName("My Night Drive!")).toBe("my-night-drive");
    expect(slugifyProjectName("  Trap__Motion  ")).toBe("trap-motion");
    expect(slugifyProjectName("Café Été")).toBe("cafe-ete");
  });

  it("falls back to a stable name for unusable input", () => {
    expect(slugifyProjectName("")).toBe("untitled-project");
    expect(slugifyProjectName("***")).toBe("untitled-project");
    expect(slugifyProjectName("...")).toBe("untitled-project");
  });

  it("caps the stem length", () => {
    expect(slugifyProjectName("a".repeat(200)).length).toBe(80);
  });

  it("builds projects/<slug>.camxora-vizzy.json", () => {
    const file = projectFilePath(directory, "My Night Drive");
    expect(file).toBe(path.join(directory, `my-night-drive${VIZZY_PROJECT_EXTENSION}`));
    expect(path.dirname(file)).toBe(path.resolve(directory));
  });
});

describe("vizzy path containment", () => {
  it("accepts a nested path", () => {
    expect(isInsidePath(directory, path.join(directory, "a", "b.json"))).toBe(true);
  });

  it("rejects the root itself", () => {
    expect(isInsidePath(directory, directory)).toBe(false);
  });

  it("rejects traversal and sibling prefixes", () => {
    expect(isInsidePath(directory, path.join(directory, "..", "escape.json"))).toBe(false);
    expect(isInsidePath(directory, `${directory}-evil${path.sep}x.json`)).toBe(false);
  });
});

describe("atomic project writes", () => {
  it("writes, then overwrites, leaving no temp files", () => {
    const file = projectFilePath(directory, "Demo");
    atomicWriteText(file, "first");
    expect(fs.readFileSync(file, "utf8")).toBe("first");

    atomicWriteText(file, "second");
    expect(fs.readFileSync(file, "utf8")).toBe("second");

    const leftovers = fs.readdirSync(directory).filter((entry) => entry.endsWith(".tmp"));
    expect(leftovers).toEqual([]);
  });

  it("creates missing directories", () => {
    const nested = path.join(directory, "deep", "deeper", "project.json");
    atomicWriteText(nested, "{}");
    expect(fs.existsSync(nested)).toBe(true);
  });
});

describe("project file validation", () => {
  it("accepts a studio-project snapshot", () => {
    const parsed = parseProjectText(snapshot());
    expect(parsed.ok).toBe(true);
  });

  it("rejects invalid JSON and foreign formats", () => {
    expect(parseProjectText("{")).toMatchObject({ ok: false, code: "PROJECT_INVALID_JSON" });
    expect(parseProjectText(JSON.stringify({ hello: "world" }))).toMatchObject({
      ok: false,
      code: "PROJECT_INVALID_FORMAT",
    });
    expect(
      parseProjectText(JSON.stringify({ format: "studio-project", project: {}, layers: [] })),
    ).toMatchObject({ ok: false, code: "PROJECT_INVALID" });
  });

  it("reads a file from disk and reports a missing one", () => {
    const file = projectFilePath(directory, "Demo");
    atomicWriteText(file, serialiseProjectFile(JSON.parse(snapshot())));
    const read = readProjectFile(file);
    expect(read.ok).toBe(true);
    if (read.ok) expect(read.text).toContain('"studio-project"');

    expect(readProjectFile(path.join(directory, "nope.json"))).toMatchObject({
      ok: false,
      code: "PROJECT_NOT_FOUND",
    });
    expect(readProjectFile(directory)).toMatchObject({
      ok: false,
      code: "PROJECT_NOT_A_FILE",
    });
  });
});

describe("semantic round-trip", () => {
  it("ignores savedAt and key order", () => {
    const a = snapshot({ savedAt: "2026-11-19T00:00:00.000Z" });
    const b = snapshot({ savedAt: "2026-12-01T10:11:12.000Z" });
    expect(projectsAreEquivalent(a, b)).toBe(true);
    expect(projectSemanticKey(a)).toBe(projectSemanticKey(b));
  });

  it("detects a real change", () => {
    const a = snapshot();
    const b = snapshot({ layers: [] });
    expect(projectsAreEquivalent(a, b)).toBe(false);
  });

  it("detects a changed node property", () => {
    const a = JSON.parse(snapshot());
    const b = JSON.parse(snapshot());
    b.nodes[0].name = "Renamed";
    expect(projectSemanticKey(a)).not.toBe(projectSemanticKey(b));
  });

  it("round-trips the committed fixture", () => {
    const fixture = path.join(
      process.cwd(),
      "tests",
      "fixtures",
      "vizzy",
      "trap-motion.camxora-vizzy.json",
    );
    const read = readProjectFile(fixture);
    expect(read.ok).toBe(true);
    if (!read.ok) return;

    expect(read.snapshot.nodes).toHaveLength(3);
    expect(read.snapshot.layers).toHaveLength(3);

    const rewritten = serialiseProjectFile(JSON.parse(read.text));
    expect(projectsAreEquivalent(read.text, rewritten)).toBe(true);
    expect(parseProjectText(rewritten).ok).toBe(true);
  });
});
