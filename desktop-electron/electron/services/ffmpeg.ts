import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { app } from "electron";
import { logger } from "./logger";
import { parseProgressLine, progressPercent } from "./ffmpeg-utils";
import { getDevicePreferences } from "./device-settings";

export interface ProbeResult {
  durationSec: number;
  width: number | null;
  height: number | null;
  videoCodec: string | null;
  audioCodec: string | null;
  format: string | null;
}

export interface TranscodeRequest {
  input: string;
  output: string;
  width?: number;
  height?: number;
  fps?: number;
  crf?: number;
  durationSec?: number;
}

export interface FfmpegProgress {
  jobId: string;
  frame: number;
  fps: number;
  timeMs: number;
  percent: number;
  speed: string;
}

const jobs = new Map<string, ChildProcessWithoutNullStreams>();

function bundledTool(name: string): string | null {
  const file = process.platform === "win32" ? `${name}.exe` : name;
  let appPath = "";
  try {
    appPath = app.getAppPath();
  } catch {
    // Unit/integration tests import this module without an Electron app.
    appPath = "";
  }
  const candidates = [
    path.join(process.resourcesPath ?? "", "ffmpeg", file),
    ...(appPath ? [path.join(appPath, "resources", "ffmpeg", file)] : []),
    path.join(process.cwd(), "resources", "ffmpeg", file),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null;
}

function deviceTool(name: "ffmpeg" | "ffprobe"): string | null {
  const custom = getDevicePreferences().ffmpegPath;
  if (!custom || !path.isAbsolute(custom) || !fs.existsSync(custom)) return null;
  if (name === "ffmpeg") return custom;
  const sibling = path.join(
    path.dirname(custom),
    process.platform === "win32" ? "ffprobe.exe" : "ffprobe",
  );
  return fs.existsSync(sibling) ? sibling : null;
}

function resolveTool(name: "ffmpeg" | "ffprobe"): string {
  const fromEnv = process.env[name === "ffmpeg" ? "CAMXORA_FFMPEG_PATH" : "CAMXORA_FFPROBE_PATH"];
  if (fromEnv) return fromEnv;
  return deviceTool(name) ?? bundledTool(name) ?? name;
}

function runCapture(command: string, args: string[], timeoutMs = 30_000): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { windowsHide: true });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`${command} timed out`));
    }, timeoutMs);
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) resolve(stdout);
      else reject(new Error(stderr.trim() || `${command} exited with ${code}`));
    });
  });
}

/**
 * Accurate duration for an audio-only file, in seconds.
 *
 * ffprobe estimates MP3 duration from the bitrate when the file has no Xing
 * header (Suno's downloads do not carry one), which overstates a 4:27 track as
 * 4:55. Decoding to the null muxer runs at roughly 1000x realtime and reports
 * the real end, so pipeline renders stop exactly at the song's last sample.
 */
export function parseDecodedDuration(stdout: string): number {
  let latest = 0;
  for (const line of stdout.split(/\r?\n/)) {
    const match = /^out_time_(?:us|ms)=(\d+)\s*$/.exec(line.trim());
    if (!match) continue;
    // Both keys carry microseconds in ffmpeg's progress output.
    latest = Math.max(latest, Number(match[1]) / 1_000_000);
  }
  return latest;
}

async function decodedAudioDuration(filePath: string): Promise<number> {
  const stdout = await runCapture(
    resolveTool("ffmpeg"),
    [
      "-v",
      "error",
      "-progress",
      "pipe:1",
      "-nostats",
      "-i",
      filePath,
      "-map",
      "0:a:0",
      "-f",
      "null",
      "-",
    ],
    120_000,
  );
  return parseDecodedDuration(stdout);
}

export async function probe(filePath: string): Promise<ProbeResult> {
  if (!fs.existsSync(filePath)) throw new Error("Media file does not exist");
  const stdout = await runCapture(resolveTool("ffprobe"), [
    "-v",
    "error",
    "-print_format",
    "json",
    "-show_format",
    "-show_streams",
    filePath,
  ]);
  const payload = JSON.parse(stdout) as {
    format?: { duration?: string; format_name?: string };
    streams?: Array<{
      codec_type?: string;
      codec_name?: string;
      width?: number;
      height?: number;
    }>;
  };
  const video = payload.streams?.find((stream) => stream.codec_type === "video");
  const audio = payload.streams?.find((stream) => stream.codec_type === "audio");
  let durationSec = Number(payload.format?.duration ?? 0) || 0;
  if (!video && audio) {
    // A demuxer estimate is not good enough for a render's end frame.
    try {
      const exact = await decodedAudioDuration(filePath);
      if (exact > 0) durationSec = exact;
    } catch (error) {
      logger.warn("exact audio duration failed; using the container estimate", {
        file: path.basename(filePath),
        error: String(error),
      });
    }
  }
  return {
    durationSec,
    width: video?.width ?? null,
    height: video?.height ?? null,
    videoCodec: video?.codec_name ?? null,
    audioCodec: audio?.codec_name ?? null,
    format: payload.format?.format_name ?? null,
  };
}

export interface TranscodeCallbacks {
  onProgress: (progress: FfmpegProgress) => void;
  onDone?: (output: string) => void;
  onError?: (message: string) => void;
}

export function runTranscode(
  request: TranscodeRequest,
  callbacks: TranscodeCallbacks,
): string {
  if (!fs.existsSync(request.input)) throw new Error("Input file does not exist");
  fs.mkdirSync(path.dirname(request.output), { recursive: true });

  const jobId = randomUUID();
  const filters: string[] = [];
  if (request.width && request.height) {
    filters.push(`scale=${request.width}:${request.height}`);
  }

  const args = [
    "-y",
    "-i",
    request.input,
    ...(filters.length ? ["-vf", filters.join(",")] : []),
    ...(request.fps ? ["-r", String(request.fps)] : []),
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    String(request.crf ?? 23),
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-movflags",
    "+faststart",
    "-progress",
    "pipe:1",
    "-nostats",
    request.output,
  ];

  const child = spawn(resolveTool("ffmpeg"), args, { windowsHide: true });
  jobs.set(jobId, child);

  let frame = 0;
  let fps = 0;
  let timeMs = 0;
  let speed = "0x";
  let buffer = "";

  const emit = () => {
    callbacks.onProgress({
      jobId,
      frame,
      fps,
      timeMs,
      percent: progressPercent(timeMs, request.durationSec),
      speed,
    });
  };

  child.stdout.on("data", (chunk: Buffer) => {
    buffer += chunk.toString("utf8");
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const entry = parseProgressLine(line);
      if (!entry) continue;
      if (entry.key === "frame") frame = Number(entry.value) || frame;
      else if (entry.key === "fps") fps = Number(entry.value) || fps;
      else if (entry.key === "out_time_ms") timeMs = Number(entry.value) || timeMs;
      else if (entry.key === "speed") speed = entry.value;
      else if (entry.key === "progress") emit();
    }
  });

  let stderr = "";
  child.stderr.on("data", (chunk: Buffer) => {
    stderr += chunk.toString("utf8");
    if (stderr.length > 8000) stderr = stderr.slice(-8000);
  });

  child.on("error", (error) => {
    jobs.delete(jobId);
    logger.error("ffmpeg failed to start", { error: String(error) });
    callbacks.onError?.(String(error));
  });

  child.on("close", (code) => {
    jobs.delete(jobId);
    if (code === 0) {
      logger.info("ffmpeg job finished", { jobId, output: request.output });
      callbacks.onDone?.(request.output);
    } else {
      logger.warn("ffmpeg job failed", { jobId, code, stderr });
      callbacks.onError?.(stderr.trim() || `FFmpeg exited with ${code}`);
    }
  });

  return jobId;
}

export function cancelJob(jobId: string): boolean {
  const child = jobs.get(jobId);
  if (!child) return false;
  child.kill();
  jobs.delete(jobId);
  return true;
}

/** Resolve the effective ffmpeg binary (env → device setting → bundled → PATH). */
export function ffmpegExecutable(): string {
  return resolveTool("ffmpeg");
}

export function checkFfmpeg(): Promise<boolean> {  const tool = resolveTool("ffmpeg");
  if (path.isAbsolute(tool) && !fs.existsSync(tool)) return Promise.resolve(false);
  return new Promise((resolve) => {
    const child = spawn(tool, ["-version"], { windowsHide: true });
    const timer = setTimeout(() => {
      child.kill();
      resolve(false);
    }, 3000);
    child.on("error", () => {
      clearTimeout(timer);
      resolve(false);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve(code === 0);
    });
  });
}
