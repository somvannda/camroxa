/**
 * Video utilities.
 *
 * 1. `extractVideoFrame` — pull a representative still from an uploaded video.
 *    Suno has no video input; the honest way to let a video influence
 *    generation is to extract a frame and feed it through the image
 *    (`agentic_thinking`) flow.
 * 2. `renderMusicVideo` — render a cover-art + waveform MP4 for a track, since
 *    Suno exposes no video-generation API (we produce `videoUrl` ourselves).
 *
 * Both use the bundled `ffmpeg-static` binary so they work without a system
 * ffmpeg install.
 */
import { execFile, spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import ffmpegPath from "ffmpeg-static";

/** Extract one JPEG frame from a video buffer (default 1s in). */
export async function extractVideoFrame(bytes: Buffer, atSeconds = 1): Promise<Buffer> {
  const bin = ffmpegBin();
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "camxora-video-"));
  const inPath = path.join(dir, `${randomUUID()}.mp4`);
  const outPath = path.join(dir, "frame.jpg");
  try {
    await fs.writeFile(inPath, bytes);
    await new Promise<void>((resolve, reject) => {
      execFile(
        bin,
        ["-y", "-ss", String(atSeconds), "-i", inPath, "-frames:v", "1", "-q:v", "3", outPath],
        { timeout: 60_000 },
        (err) => (err ? reject(err) : resolve()),
      );
    });
    return await fs.readFile(outPath);
  } finally {
    await fs.rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

/**
 * Pull several representative stills from a video. Suno's public create flow
 * accepts video as a reference, but the upstream API still exposes image ids;
 * sending multiple frames is the closest durable approximation. Failed seeks
 * (e.g. a clip shorter than the requested timestamp) are skipped, and an
 * identical frame is only uploaded once.
 */
export async function extractVideoFrames(
  bytes: Buffer,
  atSeconds: number[] = [1, 4, 8],
): Promise<Buffer[]> {
  const frames: Buffer[] = [];
  for (const at of atSeconds) {
    try {
      const frame = await extractVideoFrame(bytes, at);
      if (frame.length > 0 && !frames.some((existing) => existing.equals(frame))) {
        frames.push(frame);
      }
    } catch {
      // The clip may be shorter than this timestamp; keep the frames we have.
    }
  }
  if (frames.length === 0) {
    frames.push(await extractVideoFrame(bytes));
  }
  return frames;
}

function ffmpegBin(): string {
  const bin = ffmpegPath as unknown as string | null;
  // Prefer the bundled binary but fall back to a system ffmpeg on PATH (see the
  // same helper in audio.ts: ffmpeg-static's binary can be missing after a
  // partial install, which otherwise fails every media ingest with ENOENT).
  if (bin && existsSync(bin)) return bin;
  return "ffmpeg";
}

export interface RenderVideoOptions {
  /** Source audio bytes (any ffmpeg-readable container). */
  audio: Buffer;
  /** Cover image bytes; when absent a solid brand background is used. */
  image?: Buffer | null;
  imageExt?: "jpg" | "png" | "webp";
  /** User-supplied background clip; when present it replaces the cover art. */
  backgroundVideo?: Buffer | null;
  backgroundVideoExt?: "mp4" | "mov" | "webm";
  audioExt?: "mp3" | "wav" | "m4a";
  /** Output size. 9:16 → 720×1280, 1:1 → 720×720, anything else → 1280×720. */
  aspect?: string;
}

function runFfmpeg(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(ffmpegBin(), args, { stdio: ["ignore", "ignore", "pipe"] });
    let stderr = "";
    proc.stderr.on("data", (c: Buffer) => {
      stderr += c.toString();
      if (stderr.length > 4000) stderr = stderr.slice(-4000);
    });
    proc.on("error", reject);
    proc.on("close", (code) =>
      code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(-300)}`)),
    );
  });
}

/**
 * Render a cover-art + waveform MP4 for the given audio. ffmpeg needs seekable
 * inputs and the `faststart` muxer, so this writes a scratch temp dir (always
 * removed afterwards) rather than streaming through pipes.
 */
export async function renderMusicVideo(opts: RenderVideoOptions): Promise<Buffer> {
  if (!opts.audio || opts.audio.length === 0) throw new Error("empty audio buffer");
  const aspect = opts.aspect ?? "16:9";
  const vertical = aspect === "9:16";
  const square = aspect === "1:1";
  const W = vertical ? 720 : square ? 720 : 1280;
  const H = vertical ? 1280 : 720;
  const waveH = vertical ? 280 : square ? 220 : 180;

  const dir = mkdtempSync(path.join(os.tmpdir(), "camxora-mv-"));
  try {
    const audioPath = path.join(dir, `audio.${opts.audioExt ?? "mp3"}`);
    writeFileSync(audioPath, opts.audio);

    let imageArgs: string[];
    let bgFilter: string;
    if (opts.backgroundVideo && opts.backgroundVideo.length > 0) {
      // User clip: loop it under the song, crop to fill the chosen aspect.
      const bgPath = path.join(dir, `bg.${opts.backgroundVideoExt ?? "mp4"}`);
      writeFileSync(bgPath, opts.backgroundVideo);
      imageArgs = ["-stream_loop", "-1", "-i", bgPath];
      bgFilter =
        `[0:v]scale=${W}:${H}:force_original_aspect_ratio=increase,` +
        `crop=${W}:${H},setsar=1[bg];`;
    } else if (opts.image && opts.image.length > 0) {
      const imgPath = path.join(dir, `cover.${opts.imageExt ?? "jpg"}`);
      writeFileSync(imgPath, opts.image);
      imageArgs = ["-loop", "1", "-i", imgPath];
      bgFilter =
        `[0:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,` +
        `pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x0a0e27,setsar=1[bg];`;
    } else {
      imageArgs = ["-f", "lavfi", "-i", `color=c=0x0a0e27:s=${W}x${H}`];
      bgFilter =
        `[0:v]scale=${W}:${H}:force_original_aspect_ratio=decrease,` +
        `pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=0x0a0e27,setsar=1[bg];`;
    }

    const filter =
      bgFilter +
      `[1:a]showwaves=s=${W}x${waveH}:mode=cline:colors=0x7466F1|0xA259FF,format=yuva420p[w];` +
      `[bg][w]overlay=(W-w)/2:H-h-36:format=auto[v]`;

    const outPath = path.join(dir, "out.mp4");
    await runFfmpeg([
      "-hide_banner",
      "-loglevel",
      "error",
      "-y",
      ...imageArgs,
      "-i",
      audioPath,
      "-filter_complex",
      filter,
      "-map",
      "[v]",
      "-map",
      "1:a",
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-crf",
      "24",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      "160k",
      "-shortest",
      "-movflags",
      "+faststart",
      outPath,
    ]);

    const out = readFileSync(outPath);
    if (out.length < 2000) throw new Error(`video render produced too little output (${out.length} bytes)`);
    return out;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}
