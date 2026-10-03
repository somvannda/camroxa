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
 * ffmpeg can transcode to MP3/WAV.
 */
import { createDecipheriv, createHash } from "node:crypto";
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

/** Decrypt encrypted m4a bytes with the unwrapped AES-128-CTR key + counter. */
export function decryptMangoAudio(
  encrypted: Buffer,
  opts: { jwt: string; rights: { key: string; iv: string }; clipId: string },
): Buffer {
  const userKey = createHash("sha256").update(opts.jwt).digest();
  const contentKey = unwrapGcm(opts.rights.key, userKey, opts.clipId);
  const contentIv = unwrapGcm(opts.rights.iv, userKey, opts.clipId);
  if (contentKey.length !== 16) {
    throw new Error(`mango decrypt: unexpected content key length ${contentKey.length}`);
  }
  if (contentIv.length !== 16) {
    throw new Error(`mango decrypt: unexpected content iv length ${contentIv.length}`);
  }
  const decipher = createDecipheriv("aes-128-ctr", contentKey, contentIv);
  return Buffer.concat([decipher.update(encrypted), decipher.final()]);
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
