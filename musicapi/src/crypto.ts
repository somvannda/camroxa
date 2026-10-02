import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { config } from "./config.js";

/**
 * Versioned envelope for secrets stored at rest. The prefix lets us tell
 * encrypted values apart from legacy plaintext so the latter keep working
 * until they are backfilled.
 */
const PREFIX = "enc:v1:";
const IV_LEN = 12;

let cachedKey: Buffer | null = null;

function key(): Buffer {
  if (!cachedKey) {
    // The configured secret is high-entropy, so a single SHA-256 pass to reach
    // the 32 bytes AES-256 requires is sufficient.
    cachedKey = createHash("sha256").update(config.cookieEncryptionKey, "utf8").digest();
  }
  return cachedKey;
}

export function isEncrypted(value: string): boolean {
  return value.startsWith(PREFIX);
}

/** Encrypt a secret for storage at rest (AES-256-GCM, versioned envelope). */
export function encryptSecret(plain: string): string {
  const iv = randomBytes(IV_LEN);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  const ct = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `${PREFIX}${iv.toString("base64url")}:${tag.toString("base64url")}:${ct.toString("base64url")}`;
}

/**
 * Decrypt a stored secret. Values without the versioned prefix are returned
 * unchanged so legacy plaintext rows keep working until backfilled.
 */
export function decryptSecret(value: string): string {
  if (!isEncrypted(value)) return value;
  const [ivB64, tagB64, ctB64] = value.slice(PREFIX.length).split(":");
  if (!ivB64 || !tagB64 || !ctB64) throw new Error("Malformed encrypted secret.");
  const decipher = createDecipheriv("aes-256-gcm", key(), Buffer.from(ivB64, "base64url"));
  decipher.setAuthTag(Buffer.from(tagB64, "base64url"));
  return Buffer.concat([
    decipher.update(Buffer.from(ctB64, "base64url")),
    decipher.final(),
  ]).toString("utf8");
}
