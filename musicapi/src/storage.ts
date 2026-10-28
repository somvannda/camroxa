/**
 * Durable object storage for generated media — Backblaze B2 via its S3 API.
 *
 * Mirrors the platform's Python `StorageService` (boto3, path-style, SigV4) so
 * both halves of the product read/write the same bucket with the same
 * conventions. Generated MP3/WAV/image bytes are copied here on job completion
 * and served as stable URLs, instead of relying on Suno's expiring links.
 *
 * All functions are safe to call when storage is unconfigured: `storageConfigured()`
 * gates ingestion, and the URL helpers degrade to `null` so callers fall back to
 * the live Suno URL.
 */
import {
  GetObjectCommand,
  HeadObjectCommand,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { config, storageConfigured } from "./config.js";

export { storageConfigured };

let client: S3Client | null = null;

function getClient(): S3Client {
  if (!client) {
    client = new S3Client({
      endpoint: config.storage.endpoint,
      region: config.storage.region,
      credentials: {
        accessKeyId: config.storage.keyId,
        secretAccessKey: config.storage.applicationKey,
      },
      // Required by B2's S3-compatible endpoint.
      forcePathStyle: true,
    });
  }
  return client;
}

/** Drop the cached S3 client so a runtime credential change takes effect. */
export function resetStorageClient(): void {
  client = null;
}

/** Sanitise one path segment (no `/`, no surprises) and join under the prefix. */
export function objectKey(...parts: Array<string | number>): string {
  const clean = parts
    .map((p) => String(p).trim().replace(/[^a-zA-Z0-9._-]+/g, "_").replace(/^_+|_+$/g, ""))
    .filter(Boolean)
    .join("/");
  return config.storage.prefix ? `${config.storage.prefix}/${clean}` : clean;
}

/** Upload bytes, returning the stored key. Throws on failure (caller decides). */
export async function putObject(
  key: string,
  body: Buffer,
  contentType: string,
  opts: { cacheControl?: string } = {},
): Promise<string> {
  await getClient().send(
    new PutObjectCommand({
      Bucket: config.storage.bucket,
      Key: key,
      Body: body,
      ContentType: contentType,
      // Browsers and the CDN both need an explicit lifetime; Cloudflare only
      // caches ~120 minutes for a response that carries no Cache-Control.
      CacheControl: opts.cacheControl ?? config.storage.cacheControl,
    }),
  );
  return key;
}

/**
 * Resolve a stable, client-readable URL for an object: the CDN base when
 * configured (public, long-lived), otherwise a presigned B2 GET URL.
 * Returns `null` when storage is unconfigured.
 */
export async function getReadUrl(key: string): Promise<string | null> {
  if (!storageConfigured()) return null;
  if (config.storage.publicBaseUrl) {
    const encoded = key.split("/").map(encodeURIComponent).join("/");
    return `${config.storage.publicBaseUrl}/${encoded}`;
  }
  return getSignedUrl(
    getClient(),
    new GetObjectCommand({ Bucket: config.storage.bucket, Key: key }),
    { expiresIn: config.storage.urlTtlSeconds },
  );
}

/** Read an object's bytes back (server-side reads / fallbacks). */
export async function getObjectBytes(key: string): Promise<Buffer> {
  const res = await getClient().send(
    new GetObjectCommand({ Bucket: config.storage.bucket, Key: key }),
  );
  const arr = await res.Body!.transformToByteArray();
  return Buffer.from(arr);
}

/** Whether an object exists. Never throws. */
export async function objectExists(key: string): Promise<boolean> {
  if (!storageConfigured()) return false;
  try {
    await getClient().send(
      new HeadObjectCommand({ Bucket: config.storage.bucket, Key: key }),
    );
    return true;
  } catch {
    return false;
  }
}

/** Bucket/prefix descriptor for logs and /health (no secrets). */
export function storageInfo(): { configured: boolean; bucket: string; prefix: string; cdn: boolean } {
  return {
    configured: storageConfigured(),
    bucket: config.storage.bucket,
    prefix: config.storage.prefix,
    cdn: Boolean(config.storage.publicBaseUrl),
  };
}
