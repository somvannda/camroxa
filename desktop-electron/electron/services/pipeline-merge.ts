import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { ffmpegExecutable } from "./ffmpeg";

export type MergeMode = "copy" | "reencode";

export interface MergePlan {
  inputs: string[];
  output: string;
  listFile: string;
  mode: MergeMode;
  args: string[];
}

export interface MergeResult {
  output: string;
  bytes: number;
  elapsedMs: number;
}

/** Escape a path for ffmpeg's concat demuxer list. */
export function concatListLine(filePath: string): string {
  return `file '${filePath.replace(/'/g, "'\\''")}'`;
}

export function planConcat(inputs: string[], output: string, mode: MergeMode = "copy"): MergePlan {
  if (!inputs.length) throw new Error("Nothing to merge.");
  for (const input of inputs) {
    if (!path.isAbsolute(input)) throw new Error(`Merge input must be absolute: ${input}`);
    if (!fs.existsSync(input)) throw new Error(`Merge input is missing: ${input}`);
  }
  const resolvedOutput = path.resolve(output);
  if (!/\.(mp4|webm)$/i.test(resolvedOutput)) {
    throw new Error("The merged output must be an MP4 or WebM file.");
  }
  if (inputs.some((input) => path.resolve(input) === resolvedOutput)) {
    throw new Error("The merged output cannot overwrite an input.");
  }
  const listFile = `${resolvedOutput}.concat.txt`;
  const encode =
    mode === "copy"
      ? ["-c", "copy"]
      : [
          "-c:v",
          "libx264",
          "-preset",
          "medium",
          "-crf",
          "18",
          "-pix_fmt",
          "yuv420p",
          "-c:a",
          "aac",
          "-b:a",
          "192k",
        ];
  return {
    inputs: inputs.map((input) => path.resolve(input)),
    output: resolvedOutput,
    listFile,
    mode,
    args: [
      "-y",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      listFile,
      ...encode,
      "-movflags",
      "+faststart",
      resolvedOutput,
    ],
  };
}

export function writeConcatList(plan: MergePlan): void {
  fs.mkdirSync(path.dirname(plan.listFile), { recursive: true });
  fs.writeFileSync(plan.listFile, plan.inputs.map(concatListLine).join("\n") + "\n", "utf8");
}

export function mergeVideos(plan: MergePlan, timeoutMs = 60 * 60 * 1000): Promise<MergeResult> {
  writeConcatList(plan);
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const child = spawn(ffmpegExecutable(), plan.args, { windowsHide: true });
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      cleanup();
      reject(new Error("The merge timed out."));
    }, timeoutMs);
    function cleanup() {
      clearTimeout(timer);
      try {
        fs.rmSync(plan.listFile, { force: true });
      } catch {
        /* best effort */
      }
      try {
        if (fs.existsSync(plan.output) && fs.statSync(plan.output).size === 0) {
          fs.rmSync(plan.output, { force: true });
        }
      } catch {
        /* best effort */
      }
    }
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
      if (stderr.length > 16_000) stderr = stderr.slice(-16_000);
    });
    child.on("error", (error) => {
      cleanup();
      reject(error);
    });
    child.on("close", (code) => {
      cleanup();
      if (code !== 0) {
        reject(new Error(stderr.trim() || `FFmpeg merge exited with ${code}`));
        return;
      }
      let bytes = 0;
      try {
        bytes = fs.statSync(plan.output).size;
      } catch {
        reject(new Error("The merged file was not written."));
        return;
      }
      if (bytes === 0) {
        reject(new Error("The merged file is empty."));
        return;
      }
      resolve({ output: plan.output, bytes, elapsedMs: Date.now() - started });
    });
  });
}

/** Long-form and reel names follow the pipeline contract. */
export function outputName(stem: string, branch: "long" | "reel"): string {
  const base = stem.replace(/[\\/:*?"<>|]+/g, "-").replace(/\.(mp3|wav|flac|m4a|ogg)$/i, "");
  return branch === "reel" ? `${base}_REEL.mp4` : `${base}.mp4`;
}
