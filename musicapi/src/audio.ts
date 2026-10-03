/**
 * Audio format handling for durable delivery.
 *
 * Suno's progressive CDN URL (the `media_urls[].url` on a clip) serves the full
 * track as a plain, publicly-fetchable file with no download entitlement. We use
 * it as the source of truth and re-encode to the requested container with the
 * bundled `ffmpeg-static` binary, so MP3/WAV delivery does not depend on Suno's
 * paid download pipeline (which 401s when `is_download_unlocked` is false).
 */
import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import ffmpegPath from "ffmpeg-static";

export type AudioFormat = "mp3" | "wav";

function ffmpegBin(): string {
  const bin = ffmpegPath as unknown as string | null;
  if (!bin) throw new Error("ffmpeg binary is unavailable (ffmpeg-static not installed).");
  return bin;
}

/** Transcode arbitrary audio bytes into the requested container. */
export async function transcodeAudio(bytes: Buffer, format: AudioFormat): Promise<Buffer> {
  if (!bytes || bytes.length === 0) throw new Error("empty audio buffer");
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "camxora-audio-"));
  const inPath = path.join(dir, "in.bin");
  const outPath = path.join(dir, `out.${format}`);
  try {
    await fs.writeFile(inPath, bytes);
    const args =
      format === "wav"
        ? ["-y", "-i", inPath, "-vn", "-acodec", "pcm_s16le", outPath]
        : ["-y", "-i", inPath, "-vn", "-acodec", "libmp3lame", "-q:a", "2", outPath];
    await new Promise<void>((resolve, reject) => {
      execFile(ffmpegBin(), args, { timeout: 300_000 }, (err) => (err ? reject(err) : resolve()));
    });
    return await fs.readFile(outPath);
  } finally {
    await fs.rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

/** True when a URL is Suno's non-playable placeholder rather than media. */
function isForbidden(url: string): boolean {
  return /\/api\/forbidden\b/i.test(url);
}

/**
 * Find a publicly fetchable progressive audio URL on a clip object. Prefers
 * `media_urls[].url` (the CDN progressive file), then the stream URLs, then the
 * plain audio URL — skipping Suno's `/api/forbidden` placeholder.
 */
export function pickPublicAudioUrl(item: Record<string, unknown>): string | null {
  const candidates: unknown[] = [];
  const media = item.media_urls ?? item.mediaUrls;
  if (Array.isArray(media)) {
    for (const m of media) {
      if (m && typeof m === "object") {
        const o = m as Record<string, unknown>;
        candidates.push(o.url, o.audio_url, o.audioUrl);
      } else if (typeof m === "string") {
        candidates.push(m);
      }
    }
  }
  candidates.push(item.stream_audio_url, item.streamAudioUrl, item.audio_url, item.audioUrl);
  for (const c of candidates) {
    if (typeof c === "string" && /^https?:\/\//i.test(c) && !isForbidden(c)) return c;
  }
  return null;
}
