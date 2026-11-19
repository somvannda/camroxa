import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  concatListLine,
  outputName,
  planConcat,
  writeConcatList,
} from "../../electron/services/pipeline-merge";

const roots: string[] = [];

function tempRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-merge-"));
  roots.push(root);
  return root;
}

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe("pipeline merge planning", () => {
  it("plans a copy concat with absolute inputs", () => {
    const root = tempRoot();
    const a = path.join(root, "a.mp4");
    const b = path.join(root, "b.mp4");
    fs.writeFileSync(a, "a");
    fs.writeFileSync(b, "b");
    const plan = planConcat([a, b], path.join(root, "merged.mp4"));
    expect(plan.mode).toBe("copy");
    expect(plan.inputs).toEqual([a, b]);
    expect(plan.args).toContain("-f");
    expect(plan.args).toContain("concat");
    expect(plan.args).toContain("-c");
    expect(plan.args).toContain("copy");
    expect(plan.args).toContain(plan.listFile);
    expect(plan.args.at(-1)).toBe(path.join(root, "merged.mp4"));
  });

  it("plans a re-encode when streams may differ", () => {
    const root = tempRoot();
    const a = path.join(root, "a.mp4");
    fs.writeFileSync(a, "a");
    const plan = planConcat([a], path.join(root, "merged.mp4"), "reencode");
    expect(plan.args).toContain("libx264");
    expect(plan.args).toContain("aac");
    expect(plan.args).not.toContain("copy");
  });

  it("writes a concat list with escaped quotes", () => {
    const root = tempRoot();
    const quoted = path.join(root, "it's.mp4");
    fs.writeFileSync(quoted, "a");
    const plan = planConcat([quoted], path.join(root, "out.mp4"));
    writeConcatList(plan);
    const list = fs.readFileSync(plan.listFile, "utf8");
    expect(list).toContain("file '");
    expect(concatListLine(quoted)).toContain("'\\''");
    expect(list.trim().split("\n")).toHaveLength(1);
  });

  it("rejects empty, relative, missing and self-overwriting inputs", () => {
    const root = tempRoot();
    expect(() => planConcat([], path.join(root, "out.mp4"))).toThrow(/nothing to merge/i);
    expect(() => planConcat(["a.mp4"], path.join(root, "out.mp4"))).toThrow(/absolute/i);
    expect(() => planConcat([path.join(root, "nope.mp4")], path.join(root, "out.mp4"))).toThrow(
      /missing/i,
    );
    const input = path.join(root, "same.mp4");
    fs.writeFileSync(input, "a");
    expect(() => planConcat([input], input)).toThrow(/cannot overwrite/i);
    expect(() => planConcat([input], path.join(root, "out.mkv"))).toThrow(/MP4 or WebM/i);
  });

  it("names long and reel outputs", () => {
    expect(outputName("Night Drive.mp3", "long")).toBe("Night Drive.mp4");
    expect(outputName("Night Drive.mp3", "reel")).toBe("Night Drive_REEL.mp4");
    expect(outputName("a/b:c", "long")).toBe("a-b-c.mp4");
  });
});
