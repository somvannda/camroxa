/**
 * Direct desktop → YouTube resumable upload (no storage copy), ported from
 * `camxora_python/shared/lib/youtube_direct.py`.
 *
 * The protocol is the documented `videos.insert` resumable flow:
 *   1. POST the snippet/status to open a session (Location = session URL);
 *   2. PUT `bytes * /total` to learn how much YouTube already has;
 *   3. PUT fixed-size chunks with `Content-Range`, honouring 308 + retry.
 *
 * The access token arrives as an argument and never leaves this call: it is not
 * returned, logged, or attached to any error message.
 */
import fs from "node:fs";
import path from "node:path";

export const DEFAULT_UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos";
export const DEFAULT_PLAYLIST_ENDPOINT = "https://www.googleapis.com/youtube/v3/playlistItems";
export const DEFAULT_CHUNK_BYTES = 16 * 1024 * 1024;
/** YouTube requires every non-final chunk to be a multiple of 256 KiB. */
export const MIN_CHUNK_BYTES = 256 * 1024;
export const MAX_ATTEMPTS = 3;

export type YoutubeErrorCode =
  | "YOUTUBE_AUTH"
  | "YOUTUBE_QUOTA"
  | "YOUTUBE_SESSION"
  | "YOUTUBE_HTTP"
  | "YOUTUBE_NETWORK"
  | "YOUTUBE_CANCELLED"
  | "YOUTUBE_NO_VIDEO_ID";

export class YoutubeUploadError extends Error {
  constructor(
    public readonly code: YoutubeErrorCode,
    message: string,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = "YoutubeUploadError";
  }
}

export interface YoutubeEndpoints {
  upload: string;
  playlist: string;
}

/**
 * Endpoints default to Google. Test harnesses point `CAMXORA_YOUTUBE_UPLOAD_URL`
 * / `CAMXORA_YOUTUBE_PLAYLIST_URL` at a local fake server; nothing else sets
 * them, so a packaged app always talks to Google.
 */
export function resolveYoutubeEndpoints(env: NodeJS.ProcessEnv = process.env): YoutubeEndpoints {
  const upload = String(env.CAMXORA_YOUTUBE_UPLOAD_URL ?? "").trim();
  const playlist = String(env.CAMXORA_YOUTUBE_PLAYLIST_URL ?? "").trim();
  return {
    upload: upload || DEFAULT_UPLOAD_ENDPOINT,
    playlist: playlist || DEFAULT_PLAYLIST_ENDPOINT,
  };
}

/** Test-only chunk override, clamped to YouTube's 256 KiB granularity. */
export function resolveChunkBytes(env: NodeJS.ProcessEnv = process.env): number {
  const raw = Number(env.CAMXORA_YOUTUBE_CHUNK_BYTES ?? "");
  if (!Number.isFinite(raw) || raw < MIN_CHUNK_BYTES) return DEFAULT_CHUNK_BYTES;
  return Math.floor(raw / MIN_CHUNK_BYTES) * MIN_CHUNK_BYTES;
}

export interface ChunkRange {
  start: number;
  end: number;
  length: number;
  /** `bytes <start>-<end>/<size>` */
  contentRange: string;
  /** The last chunk of the file. */
  final: boolean;
}

export function chunkRange(offset: number, size: number, chunkBytes: number): ChunkRange {
  const start = Math.max(0, Math.min(offset, size));
  const length = Math.max(0, Math.min(chunkBytes, size - start));
  const end = start + length - 1;
  return {
    start,
    end,
    length,
    contentRange: `bytes ${start}-${end}/${size}`,
    final: start + length >= size,
  };
}

/** `bytes=0-1048575` → 1048576; anything unusable falls back to the offset. */
export function parseRangeOffset(rangeHeader: string | null, fallbackOffset: number): number {
  const value = String(rangeHeader ?? "").trim();
  const match = /^bytes=(\d+)-(\d+)$/i.exec(value);
  if (!match) return Math.max(0, fallbackOffset);
  const end = Number(match[2]);
  if (!Number.isFinite(end) || end < 0) return Math.max(0, fallbackOffset);
  return end + 1;
}

export function isRetryableStatus(status: number): boolean {
  return status === 0 || status === 408 || status === 429 || status >= 500;
}

/** 1s, 2s, 4s … capped at 8s (attempt is 1-based). */
export function retryDelayMs(attempt: number): number {
  return Math.min(8000, 1000 * 2 ** Math.max(0, attempt - 1));
}

const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const BEARER = /Bearer\s+[A-Za-z0-9._~+/-]+=*/gi;

/** Error text from the provider, with any email/bearer scrubbed. */
export function safeProviderText(raw: string, limit = 240): string {
  return String(raw ?? "")
    .replace(BEARER, "Bearer [redacted]")
    .replace(EMAIL, "[redacted-email]")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, limit);
}

function readableFailure(status: number, rawBody: string): YoutubeUploadError {
  const body = safeProviderText(rawBody, 400);
  const lower = body.toLowerCase();
  if (status === 401) {
    return new YoutubeUploadError(
      "YOUTUBE_AUTH",
      "YouTube rejected the upload token. Reconnect the channel in Settings → Profiles, then upload again.",
    );
  }
  if (status === 403) {
    if (lower.includes("quota") || lower.includes("uploadlimitexceeded")) {
      return new YoutubeUploadError(
        "YOUTUBE_QUOTA",
        "YouTube's daily upload quota is reached for this app. Uploads resume tomorrow, or connect your own Google app in Settings.",
      );
    }
    return new YoutubeUploadError(
      "YOUTUBE_AUTH",
      `YouTube refused this upload (403). Check the connected channel's permissions.${body ? ` ${body}` : ""}`,
    );
  }
  if (status === 404) {
    return new YoutubeUploadError(
      "YOUTUBE_SESSION",
      "The YouTube upload session expired before it finished. Start the upload again.",
      true,
    );
  }
  if (status === 400 || status === 422) {
    return new YoutubeUploadError(
      "YOUTUBE_HTTP",
      `YouTube rejected the video metadata or file (${status}).${body ? ` ${body}` : ""}`,
    );
  }
  if (status === 429 || status >= 500) {
    return new YoutubeUploadError(
      "YOUTUBE_NETWORK",
      "YouTube is busy right now. Try the upload again in a minute.",
      true,
    );
  }
  return new YoutubeUploadError(
    "YOUTUBE_HTTP",
    `YouTube refused the upload (${status}).${body ? ` ${body}` : ""}`,
    isRetryableStatus(status),
  );
}

export interface YoutubeFetch {
  (input: string, init?: RequestInit): Promise<Response>;
}

async function readBody(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

/** Opens the resumable session and returns its URL. */
export async function startResumableSession(input: {
  accessToken: string;
  body: unknown;
  sizeBytes: number;
  contentType?: string;
  endpoint?: string;
  fetchImpl?: YoutubeFetch;
  signal?: AbortSignal;
}): Promise<string> {
  const endpoint = input.endpoint ?? resolveYoutubeEndpoints().upload;
  const fetchImpl = input.fetchImpl ?? fetch;
  const url = new URL(endpoint);
  url.searchParams.set("uploadType", "resumable");
  url.searchParams.set("part", "snippet,status");

  let response: Response;
  try {
    response = await fetchImpl(url.toString(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${input.accessToken}`,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": input.contentType ?? "video/mp4",
        "X-Upload-Content-Length": String(input.sizeBytes),
      },
      body: JSON.stringify(input.body ?? {}),
      signal: input.signal,
    });
  } catch {
    // Never echo the request URL: it carries the session capability.
    throw new YoutubeUploadError(
      "YOUTUBE_NETWORK",
      "Cannot reach YouTube right now. Check your connection and try again.",
      true,
    );
  }

  if (!response.ok) {
    throw readableFailure(response.status, await readBody(response));
  }
  const location = response.headers.get("location") ?? response.headers.get("Location");
  if (!location) {
    throw new YoutubeUploadError(
      "YOUTUBE_SESSION",
      "YouTube did not return a resumable upload session.",
    );
  }
  return location;
}

export interface ResumableProgress {
  sentBytes: number;
  totalBytes: number;
}

export interface ResumableResult {
  videoId: string;
  body: Record<string, unknown>;
}

function cancelled(): YoutubeUploadError {
  return new YoutubeUploadError("YOUTUBE_CANCELLED", "Upload cancelled.");
}

function videoIdOf(body: Record<string, unknown>): string {
  const id = body.id;
  return typeof id === "string" ? id.trim() : "";
}

/**
 * Pushes the file in chunks. A 308 response names the last byte YouTube kept,
 * so a dropped connection resumes instead of restarting; a retryable status is
 * retried twice with backoff before the upload fails.
 */
export async function uploadResumable(input: {
  sessionUrl: string;
  filePath: string;
  chunkBytes?: number;
  onProgress?: (progress: ResumableProgress) => void;
  isCancelled?: () => boolean;
  signal?: AbortSignal;
  fetchImpl?: YoutubeFetch;
  sleepImpl?: (ms: number) => Promise<void>;
  maxAttempts?: number;
}): Promise<ResumableResult> {
  const fetchImpl = input.fetchImpl ?? fetch;
  const sleep = input.sleepImpl ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)));
  const maxAttempts = Math.max(1, input.maxAttempts ?? MAX_ATTEMPTS);
  const size = fs.statSync(input.filePath).size;
  const chunkBytes = Math.max(MIN_CHUNK_BYTES, input.chunkBytes ?? DEFAULT_CHUNK_BYTES);
  const report = (sentBytes: number): void => input.onProgress?.({ sentBytes, totalBytes: size });
  const checkCancelled = (): void => {
    if (input.isCancelled?.() || input.signal?.aborted) throw cancelled();
  };

  let offset = 0;
  checkCancelled();

  // Probe: YouTube answers 200/201 when the file is already complete, or 308
  // with a Range header naming the bytes it kept.
  const probe = await fetchImpl(input.sessionUrl, {
    method: "PUT",
    headers: {
      "Content-Range": `bytes */${size}`,
      "Content-Length": "0",
    },
    signal: input.signal,
  });
  if (probe.status === 200 || probe.status === 201) {
    const body = (await probe.json().catch(() => ({}))) as Record<string, unknown>;
    const videoId = videoIdOf(body);
    if (!videoId) throw new YoutubeUploadError("YOUTUBE_NO_VIDEO_ID", "YouTube returned no video id.");
    report(size);
    return { videoId, body };
  }
  if (probe.status === 308) {
    offset = Math.min(parseRangeOffset(probe.headers.get("range"), 0), size);
  } else {
    throw readableFailure(probe.status, await readBody(probe));
  }
  report(offset);

  const handle = fs.openSync(input.filePath, "r");
  try {
    while (offset < size) {
      checkCancelled();
      const range = chunkRange(offset, size, chunkBytes);
      const buffer = Buffer.alloc(range.length);
      fs.readSync(handle, buffer, 0, range.length, range.start);

      let attempt = 0;
      for (;;) {
        checkCancelled();
        attempt += 1;
        let response: Response;
        try {
          response = await fetchImpl(input.sessionUrl, {
            method: "PUT",
            headers: {
              "Content-Range": range.contentRange,
              "Content-Type": "video/mp4",
              "Content-Length": String(range.length),
            },
            body: buffer,
            signal: input.signal,
          });
        } catch {
          if (input.signal?.aborted || input.isCancelled?.()) throw cancelled();
          if (attempt >= maxAttempts) {
            throw new YoutubeUploadError(
              "YOUTUBE_NETWORK",
              `The upload stopped at ${percentLabel(offset, size)}. Check your connection and retry — the local file is untouched.`,
              true,
            );
          }
          await sleep(retryDelayMs(attempt));
          continue;
        }

        if (response.status === 200 || response.status === 201) {
          const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
          const videoId = videoIdOf(body);
          if (!videoId) {
            throw new YoutubeUploadError("YOUTUBE_NO_VIDEO_ID", "YouTube returned no video id.");
          }
          report(size);
          return { videoId, body };
        }

        if (response.status === 308) {
          const next = parseRangeOffset(response.headers.get("range"), range.start + range.length);
          offset = Math.min(Math.max(next, range.start), size);
          report(offset);
          break;
        }

        if (isRetryableStatus(response.status) && attempt < maxAttempts) {
          await readBody(response);
          await sleep(retryDelayMs(attempt));
          continue;
        }
        throw readableFailure(response.status, await readBody(response));
      }
    }
  } finally {
    fs.closeSync(handle);
  }

  throw new YoutubeUploadError(
    "YOUTUBE_NO_VIDEO_ID",
    "The upload ended without a video id. Check YouTube Studio before retrying.",
  );
}

function percentLabel(sent: number, total: number): string {
  const percent = total > 0 ? Math.floor((sent * 100) / total) : 0;
  return `${percent}%`;
}

/** Adds the finished video to the configured (or chosen) playlist. */
export async function addToPlaylist(input: {
  accessToken: string;
  playlistId: string;
  videoId: string;
  endpoint?: string;
  fetchImpl?: YoutubeFetch;
  signal?: AbortSignal;
}): Promise<void> {
  const endpoint = input.endpoint ?? resolveYoutubeEndpoints().playlist;
  const fetchImpl = input.fetchImpl ?? fetch;
  const url = new URL(endpoint);
  url.searchParams.set("part", "snippet");
  let response: Response;
  try {
    response = await fetchImpl(url.toString(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${input.accessToken}`,
        "Content-Type": "application/json; charset=UTF-8",
      },
      body: JSON.stringify({
        snippet: {
          playlistId: input.playlistId,
          resourceId: { kind: "youtube#video", videoId: input.videoId },
        },
      }),
      signal: input.signal,
    });
  } catch (error) {
    throw new YoutubeUploadError(
      "YOUTUBE_NETWORK",
      `The video uploaded, but adding it to the playlist failed. ${safeProviderText(String(error), 120)}`,
      true,
    );
  }
  if (!response.ok) {
    const error = readableFailure(response.status, await readBody(response));
    throw new YoutubeUploadError(
      error.code,
      `The video uploaded, but adding it to the playlist failed. ${error.message}`,
      error.retryable,
    );
  }
}

/** Mime type for the optional thumbnail upload. */
export function thumbnailMime(filePath: string): string {
  return path.extname(filePath).toLowerCase() === ".png" ? "image/png" : "image/jpeg";
}
