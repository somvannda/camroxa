/**
 * Audio format handling for durable delivery.
 *
 * Suno's progressive CDN URL (the `media_urls[].url` on a clip) serves the full
 * track as a plain, publicly-fetchable file with no download entitlement. We use
 * it as the source of truth and re-encode to the requested container with the
 * bundled `ffmpeg-static` binary, so MP3/WAV delivery does not depend on Suno's
 * paid download pipeline (which 401s when `is_download_unlocked` is false).
 *
 * Transcoding is fully streamed through pipes (stdin → stdout) so no scratch
 * files are ever written to the VPS disk.
 */
import { spawn } from "node:child_process";
import ffmpegPath from "ffmpeg-static";

export type AudioFormat = "mp3" | "wav";

function ffmpegBin(): string {
  const bin = ffmpegPath as unknown as string | null;
  if (!bin) throw new Error("ffmpeg binary is unavailable (ffmpeg-static not installed).");
  return bin;
}

/**
 * ffmpeg cannot seek on a pipe, so a streamed WAV gets placeholder RIFF/data
 * sizes. Patch them in memory using the actual byte length (audio data begins
 * right after the `data` chunk header).
 */
function fixStreamedWavSizes(buf: Buffer): Buffer {
  const dataIdx = buf.indexOf("data");
  if (dataIdx < 0) return buf;
  const dataSize = buf.length - (dataIdx + 8);
  if (dataSize < 0) return buf;
  buf.writeUInt32LE(buf.length - 8, 4);
  buf.writeUInt32LE(dataSize, dataIdx + 4);
  return buf;
}

/** Transcode arbitrary audio bytes into the requested container (no disk I/O). */
export async function transcodeAudio(bytes: Buffer, format: AudioFormat): Promise<Buffer> {
  if (!bytes || bytes.length === 0) throw new Error("empty audio buffer");
  const args = [
    "-hide_banner",
    "-loglevel",
    "error",
    "-i",
    "pipe:0",
    "-vn",
    ...(format === "wav"
      ? ["-acodec", "pcm_s16le", "-f", "wav", "pipe:1"]
      : ["-acodec", "libmp3lame", "-q:a", "2", "-f", "mp3", "pipe:1"]),
  ];
  const out = await new Promise<Buffer>((resolve, reject) => {
    const proc = spawn(ffmpegBin(), args, { stdio: ["pipe", "pipe", "pipe"] });
    const chunks: Buffer[] = [];
    let stderr = "";
    proc.stdout.on("data", (c: Buffer) => chunks.push(c));
    proc.stderr.on("data", (c: Buffer) => {
      stderr += c.toString();
      if (stderr.length > 4000) stderr = stderr.slice(-4000);
    });
    proc.on("error", reject);
    proc.on("close", (code) => {
      if (code === 0) resolve(Buffer.concat(chunks));
      else reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(-300)}`));
    });
    // ffmpeg may close stdin early on malformed input; ignore the EPIPE.
    proc.stdin.on("error", () => undefined);
    proc.stdin.end(bytes);
  });
  if (out.length < 400) throw new Error(`ffmpeg produced too little output (${out.length} bytes)`);
  return format === "wav" ? fixStreamedWavSizes(out) : out;
}

/** True when a URL is Suno's non-playable placeholder rather than media. */
function isForbidden(url: string): boolean {
  return /\/api\/forbidden\b/i.test(url);
}

/**
 * Find a publicly fetchable progressive audio URL on a clip object. Prefers
 * `media_urls[].url` (the CDN progressive file), then the stream URLs, then the
 * plain audio URL — skipping Suno's `/api/forbidden` placeholder. Note the
 * progressive file is DRM-encrypted; callers must decrypt it first
 * (see `sunoAudio.ts`).
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
