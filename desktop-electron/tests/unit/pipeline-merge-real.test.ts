import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { ffmpegExecutable, probe } from "../../electron/services/ffmpeg";
import { mergeVideos, planConcat } from "../../electron/services/pipeline-merge";

const hasFfmpeg = spawnSync(ffmpegExecutable(), ["-version"], { windowsHide: true }).status === 0;
const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-merge-real-"));

afterAll(() => {
  fs.rmSync(root, { recursive: true, force: true });
});

function makeVideo(name: string, color: string): string {
  const file = path.join(root, name);
  const result = spawnSync(
    ffmpegExecutable(),
    [
      "-y",
      "-f",
      "lavfi",
      "-i",
      `color=c=${color}:s=160x90:d=0.5:r=30`,
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      file,
    ],
    { windowsHide: true, encoding: "utf8" },
  );
  if (result.status !== 0) {
    throw new Error(`fixture encode failed: ${result.stderr?.slice(-400)}`);
  }
  return file;
}

describe.skipIf(!hasFfmpeg)("real ffmpeg merge", () => {
  it("concatenates matching clips into one valid MP4", async () => {
    const first = makeVideo("first.mp4", "red");
    const second = makeVideo("second.mp4", "blue");
    const output = path.join(root, "merged.mp4");
    const plan = planConcat([first, second], output);
    const result = await mergeVideos(plan);
    expect(result.output).toBe(output);
    expect(result.bytes).toBeGreaterThan(0);
    expect(fs.existsSync(plan.listFile)).toBe(false);

    const metadata = await probe(output);
    expect(metadata.videoCodec).toBe("h264");
    expect(metadata.width).toBe(160);
    expect(metadata.height).toBe(90);
    expect(metadata.durationSec).toBeGreaterThan(0.8);
    expect(metadata.durationSec).toBeLessThan(1.4);
  }, 60_000);
});
