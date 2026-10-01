import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { config } from "./config.js";

const ALGORITHM = "aes-256-gcm";
const IV_BYTES = 12;
const TAG_BYTES = 16;
/** Version prefix so encrypted rows are distinguishable from legacy plaintext. */
const PREFIX = "enc:v1:";

export function isEncryptedCookie(value: string): boolean {
  return value.startsWith(PREFIX);
}

/**
 * Encrypt a Suno `client_cookie` for storage in `suno_accounts`. Already
 * encrypted input is returned unchanged so re-running migrations is safe.
 */
export function encryptCookie(plain: string): string {
  if (isEncryptedCookie(plain)) return plain;
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv(ALGORITHM, config.cookieEncryptionKey, iv);
  const ciphertext = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  return PREFIX + Buffer.concat([iv, cipher.getAuthTag(), ciphertext]).toString("base64");
}

/**
 * Decrypt a stored `client_cookie`. Values without the version prefix are
 * returned unchanged so rows written before encryption was introduced keep
 * working; run `scripts/migrate-cookie-encryption.ts` to encrypt them.
 */
export function decryptCookie(stored: string): string {
  if (!isEncryptedCookie(stored)) return stored;
  const payload = Buffer.from(stored.slice(PREFIX.length), "base64");
  if (payload.length < IV_BYTES + TAG_BYTES) {
    throw new Error("Stored client_cookie is malformed.");
  }
  const iv = payload.subarray(0, IV_BYTES);
  const tag = payload.subarray(IV_BYTES, IV_BYTES + TAG_BYTES);
  const ciphertext = payload.subarray(IV_BYTES + TAG_BYTES);
  const decipher = createDecipheriv(ALGORITHM, config.cookieEncryptionKey, iv);
  decipher.setAuthTag(tag);
  try {
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf8");
  } catch {
    // GCM auth failure almost always means COOKIE_ENCRYPTION_KEY no longer
    // matches the key the row was written with (e.g. a new worktree generated
    // its own key, or a rotation happened without re-encrypting).
    throw new Error(
      "Failed to decrypt a stored Suno client_cookie: COOKIE_ENCRYPTION_KEY does not match the key " +
        "these rows were encrypted with. Use the same key as the database that holds them, or " +
        "rotate per docs/production-readiness-plan.md §1.8.",
    );
  }
}
