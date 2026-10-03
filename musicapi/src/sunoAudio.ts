/**
 * Suno "mango" DRM audio decryption.
 *
 * Since Suno v5.5 the progressive stream (`media_urls[].url`, an `.m4a` on
 * CloudFront) is AES-CTR encrypted, so it cannot be transcoded directly and the
 * entitlement-gated `/api/download/clip` pipeline is unavailable on free/limited
 * accounts. The Suno web player fetches a license from its own server and
 * decrypts client-side; we reproduce exactly that flow server-side:
 *
 *   1. POST /api/mango/rights  ({content_params:{content_id,content_type}})  → { key, iv }
 *   2. userKey    = SHA-256(authToken)                        (AES-256-GCM)
 *   3. contentKey = AES-256-GCM-decrypt(base64(key), aad=clipId)  → AES-128 key
 *      contentIv  = AES-256-GCM-decrypt(base64(iv),  aad=clipId)  → 16-byte counter
 *   4. audio      = AES-128-CTR-decrypt(<clip>.m4a, contentKey, contentIv)
 *
 * Step 1 is authenticated with the account's own Suno token, so the license is
 * wrapped with a key only we (the account) can derive — no third party involved.
 * The decrypted bytes are a normal MP4/AAC container (Opus in `m4a-opus`) that
 * ffmpeg can transcode to MP3/WAV, and that a browser can play progressively.
 */
import { createDecipheriv, createHash } from "node:crypto";
import { Readable, Transform, type Readable as NodeReadable } from "node:stream";
import type { SunoClient } from "./client.js";

/** Progressive CloudFront host that serves the encrypted clip audio. */
export const ENCRYPTED_AUDIO_BASE = "https://d2lwuy8qc234o3.cloudfront.net/1/clip/";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36";

export function encryptedAudioUrl(clipId: string): string {
  return `${ENCRYPTED_AUDIO_BASE}${encodeURIComponent(clipId)}.m4a`;
}

/**
 * Unwrap a base64 AES-256-GCM blob (iv ‖ ciphertext ‖ tag) using the
 * token-derived user key, binding it to the clip id via additional data.
 */
function unwrapGcm(b64: string, userKey: Buffer, aad: string): Buffer {
  const wrapped = Buffer.from(b64, "base64");
  if (wrapped.length < 28) throw new Error("mango rights: wrapped key/iv is too short");
  const iv = wrapped.subarray(0, 12);
  const tag = wrapped.subarray(wrapped.length - 16);
  const ciphertext = wrapped.subarray(12, wrapped.length - 16);
  const decipher = createDecipheriv("aes-256-gcm", userKey, iv);
  decipher.setAAD(Buffer.from(aad));
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

/**
 * Derive the AES-128-CTR content key + 16-byte counter for a clip from its
 * wrapped license and the account token.
 */
export function deriveContentKeys(opts: {
  jwt: string;
  rights: { key: string; iv: string };
  clipId: string;
}): { key: Buffer; iv: Buffer } {
  const userKey = createHash("sha256").update(opts.jwt).digest();
  const key = unwrapGcm(opts.rights.key, userKey, opts.clipId);
  const iv = unwrapGcm(opts.rights.iv, userKey, opts.clipId);
  if (key.length !== 16) throw new Error(`mango decrypt: unexpected content key length ${key.length}`);
  if (iv.length !== 16) throw new Error(`mango decrypt: unexpected content iv length ${iv.length}`);
  return { key, iv };
}

/** Add a block offset to the 128-bit big-endian counter (matches Suno's client). */
export function advanceCounter(iv: Buffer, blockOffset: number): Buffer {
  const counter = Buffer.from(iv);
  let value = 0n;
  for (let i = 0; i < counter.length; i++) value = (value << 8n) | BigInt(counter[i]);
  value += BigInt(blockOffset);
  for (let i = counter.length - 1; i >= 0; i--) {
    counter[i] = Number(value & 0xffn);
    value >>= 8n;
  }
  return counter;
}

/** Decrypt a fully-buffered encrypted m4a into playable MP4/AAC bytes. */
export function decryptMangoAudio(
  encrypted: Buffer,
  opts: { jwt: string; rights: { key: string; iv: string }; clipId: string },
): Buffer {
  const { key, iv } = deriveContentKeys(opts);
  const decipher = createDecipheriv("aes-128-ctr", key, iv);
  return Buffer.concat([decipher.update(encrypted), decipher.final()]);
}

async function fetchEncrypted(clipId: string, range?: string): Promise<Response> {
  const url = encryptedAudioUrl(clipId);
  const headers: Record<string, string> = { "user-agent": UA, accept: "audio/mp4,audio/*,*/*;q=0.8" };
  if (range) headers.range = range;
  for (let attempt = 0; attempt < 2; attempt++) {
    const resp = await fetch(url, { headers, redirect: "follow", signal: AbortSignal.timeout(120_000) });
    if (resp.ok) return resp;
    if (resp.status !== 404 || attempt === 1) {
      throw new Error(`mango decrypt: encrypted audio fetch failed (${resp.status})`);
    }
    await new Promise((r) => setTimeout(r, 800));
  }
  throw new Error("mango decrypt: encrypted audio unavailable");
}

/**
 * Resolve the license, download the encrypted stream and decrypt it into a
 * playable MP4/AAC (m4a) buffer.
 */
export async function decryptSunoClip(
  client: SunoClient,
  clipId: string,
  encryptedUrl: string = encryptedAudioUrl(clipId),
): Promise<Buffer> {
  const rights = await client.mangoRights(clipId, "clip");
  // Resolve after the rights call so the token here is exactly the one that
  // authenticated it (resolveJwt is cached, so this is the same string).
  const jwt = await client.resolveJwt();
  const resp = await fetch(encryptedUrl, {
    headers: { "user-agent": UA, accept: "audio/mp4,audio/*,*/*;q=0.8" },
    redirect: "follow",
    signal: AbortSignal.timeout(120_000),
  });
  if (!resp.ok) throw new Error(`mango decrypt: encrypted audio fetch failed (${resp.status})`);
  const encrypted = Buffer.from(await resp.arrayBuffer());
  const m4a = decryptMangoAudio(encrypted, { jwt, rights, clipId });
  if (m4a.length < 400) throw new Error("mango decrypt: decrypted audio was empty");
  return m4a;
}

export interface DecryptedM4aStream {
  stream: NodeReadable;
  contentType: "audio/mp4";
  /** First byte included in the stream (from the Range request, or 0). */
  rangeStart: number;
  /** Upstream total size when known. */
  totalBytes: number | null;
}

/** Drop the first `n` bytes of a stream (used to align a mid-block Range). */
function skipBytes(src: NodeReadable, n: number): NodeReadable {
  let remaining = n;
  const pass = new Transform({
    transform(chunk: Buffer, _enc, cb) {
      if (remaining > 0) {
        const take = Math.min(remaining, chunk.length);
        remaining -= take;
        if (take >= chunk.length) return cb();
        chunk = chunk.subarray(take);
      }
      cb(null, chunk);
    },
  });
  return src.pipe(pass);
}

/**
 * Open a decrypt-on-the-fly stream of a clip's m4a for progressive playback.
 * Supports `Range` by starting the AES-CTR counter at the requested block, so a
 * small VPS never needs to buffer or persist the whole file.
 */
export async function openDecryptedM4aStream(
  client: SunoClient,
  clipId: string,
  rangeHeader?: string,
): Promise<DecryptedM4aStream> {
  const rights = await client.mangoRights(clipId, "clip");
  const jwt = await client.resolveJwt();
  const { key, iv } = deriveContentKeys({ jwt, rights, clipId });

  let start = 0;
  if (rangeHeader) {
    const m = /bytes=(\d+)-/.exec(rangeHeader);
    if (m) start = Number(m[1]) || 0;
  }
  const alignedStart = Math.floor(start / 16) * 16;
  const skip = start - alignedStart;

  const resp = await fetchEncrypted(clipId, rangeHeader ? `bytes=${alignedStart}-` : undefined);
  if (!resp.body) throw new Error("mango stream: upstream returned no body");

  let totalBytes: number | null = null;
  const contentRange = resp.headers.get("content-range");
  if (contentRange) {
    const total = Number(contentRange.split("/")[1]);
    if (Number.isFinite(total)) totalBytes = total;
  }

  const counter = advanceCounter(iv, alignedStart / 16);
  const decipher = createDecipheriv("aes-128-ctr", key, counter);
  const node = Readable.fromWeb(resp.body as Parameters<typeof Readable.fromWeb>[0]);
  const decrypted = node.pipe(decipher);
  const stream = skip > 0 ? skipBytes(decrypted, skip) : decrypted;
  return { stream, contentType: "audio/mp4", rangeStart: start, totalBytes };
}
