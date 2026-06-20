import { promises as fs } from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import type { VideoExportSettings } from "../shared/app-types";

function nowStamp() {
  const d = new Date();
  const p = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`;
}

function isVideoFile(fileName: string) {
  const lower = fileName.toLowerCase();
  return lower.endsWith(".mp4");
}

function parseResolution(res: VideoExportSettings["resolution"]) {
  const [wRaw, hRaw] = res.split("x");
  const w = Number(wRaw);
  const h = Number(hRaw);
  if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) throw new Error("Invalid resolution");
  return { w: Math.floor(w), h: Math.floor(h) };
}

async function runFfmpeg(ffmpegPath: string, args: string[]) {
  await new Promise<void>((resolve, reject) => {
    const child = spawn(ffmpegPath, args, { windowsHide: true });
    let stderr = "";
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.trim() || `ffmpeg exited with code ${code ?? -1}`));
    });
  });
}

export async function mergeVideosInDirectory(input: { ffmpegPath: string; directory: string; exportSettings: VideoExportSettings }) {
  const directory = path.resolve(input.directory);
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const videos = entries
    .filter((e) => e.isFile())
    .map((e) => e.name)
    .filter(isVideoFile);

  if (!videos.length) {
    return { ok: false as const, message: "No video files found", outputPath: null as string | null, videoCount: 0 };
  }

  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  videos.sort((a, b) => collator.compare(a, b));

  const outDir = path.join(directory, "merged");
  await fs.mkdir(outDir, { recursive: true });

  const listContent = videos
    .map((name) => path.resolve(directory, name))
    .map((fullPath) => `file '${fullPath.replace(/'/g, "'\\''")}'`)
    .join("\n");
  const listFilePath = path.resolve(outDir, `concat_${nowStamp()}.txt`);
  await fs.writeFile(listFilePath, listContent, "utf-8");

  const stamp = nowStamp();
  const outPath = path.resolve(outDir, `merged_${stamp}.mp4`);

  const { w, h } = parseResolution(input.exportSettings.resolution);
  const fps = input.exportSettings.fps;
  const preset = input.exportSettings.preset;
  const crf = Math.max(10, Math.min(40, Math.floor(input.exportSettings.crf)));
  const audioBitrate = `${input.exportSettings.audioBitrateKbps}k`;

  const vf = `scale=${w}:${h}:force_original_aspect_ratio=decrease,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2,fps=${fps}`;

  await runFfmpeg(input.ffmpegPath, [
    "-hide_banner",
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    listFilePath,
    "-vf",
    vf,
    "-c:v",
    "libx264",
    "-preset",
    preset,
    "-crf",
    String(crf),
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-b:a",
    audioBitrate,
    "-movflags",
    "+faststart",
    outPath,
  ]);

  return { ok: true as const, message: "Merged", outputPath: outPath, videoCount: videos.length };
}
