/**
 * Video → representative frame extraction.
 *
 * Suno has no video input; the honest way to let a video influence generation is
 * to extract a still frame and feed it through the image (`agentic_thinking`)
 * flow. Uses the bundled `ffmpeg-static` binary so it works without a system
 * ffmpeg install.
 */
import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import ffmpegPath from "ffmpeg-static";

/** Extract one JPEG frame from a video buffer (default 1s in). */
export async function extractVideoFrame(bytes: Buffer, atSeconds = 1): Promise<Buffer> {
  const bin = ffmpegPath as unknown as string | null;
  if (!bin) throw new Error("ffmpeg binary is unavailable (ffmpeg-static not installed).");
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
