import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  STARTER_SEED_MARKER,
  STARTER_TEMPLATES,
  seedStarterTemplates,
} from "../../electron/services/starter-templates";
import { listVideoTemplates, readVideoTemplate } from "../../electron/services/video-templates";

const sourceRoot = path.resolve(__dirname, "../../starter-templates");
const roots: string[] = [];

function tempRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-starters-"));
  roots.push(root);
  return root;
}

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe("starter templates", () => {
  it("seeds every starter with a loadable pipeline", () => {
    const root = tempRoot();
    const seeded = seedStarterTemplates(root, sourceRoot);
    expect(seeded).toEqual(STARTER_TEMPLATES.map((starter) => starter.id));

    for (const starter of STARTER_TEMPLATES) {
      expect(fs.existsSync(path.join(root, starter.id, "template.json"))).toBe(true);
      const detail = readVideoTemplate(root, starter.id);
      expect(detail.name).toBe(starter.name);
      expect(detail.pipeline.project).toBe("template.json");
      expect(detail.pipeline.duration.mode).toBe("audio");
      expect(JSON.parse(detail.projectJson).format).toBe("studio-project");
    }

    const listed = listVideoTemplates(root);
    expect(listed).toHaveLength(STARTER_TEMPLATES.length);
    expect(listed.find((entry) => entry.id === "neon-reel")?.kind).toBe("reel");
    expect(listed.find((entry) => entry.id === "neon-spectrum")?.kind).toBe("long");
  });

  it("does not re-seed once the marker is written", () => {
    const root = tempRoot();
    seedStarterTemplates(root, sourceRoot);
    const again = seedStarterTemplates(root, sourceRoot);
    expect(again).toEqual([]);
    expect(fs.existsSync(path.join(root, STARTER_SEED_MARKER))).toBe(true);
  });

  it("leaves a template the user already edited alone", () => {
    const root = tempRoot();
    const edited = path.join(root, "neon-spectrum");
    fs.mkdirSync(edited, { recursive: true });
    fs.writeFileSync(path.join(edited, "keep.txt"), "mine", "utf8");

    seedStarterTemplates(root, sourceRoot);
    expect(fs.readFileSync(path.join(edited, "keep.txt"), "utf8")).toBe("mine");
    expect(fs.existsSync(path.join(edited, "pipeline.json"))).toBe(false);
  });

  it("writes the marker even when the bundle is missing", () => {
    const root = tempRoot();
    const seeded = seedStarterTemplates(root, path.join(root, "does-not-exist"));
    expect(seeded).toEqual([]);
    expect(fs.existsSync(path.join(root, STARTER_SEED_MARKER))).toBe(true);
  });
});
