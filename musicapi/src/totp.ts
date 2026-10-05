/**
 * Minimal RFC 6238 TOTP (SHA-1, 30s, 6 digits) for admin 2FA. Implemented with
 * Node's crypto only, so it adds no dependency. Secrets are RFC 4648 base32.
 */
import { createHmac, randomBytes } from "node:crypto";

const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

/** Encode bytes to RFC 4648 base32 (no padding). */
export function base32Encode(buf: Buffer): string {
  let bits = 0;
  let value = 0;
  let output = "";
  for (const byte of buf) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      output += BASE32_ALPHABET[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) output += BASE32_ALPHABET[(value << (5 - bits)) & 31];
  return output;
}

/** Decode an RFC 4648 base32 string (padding and separators tolerated). */
export function base32Decode(input: string): Buffer {
  const clean = input
    .replace(/=+$/g, "")
    .replace(/[\s-]/g, "")
    .toUpperCase();
  let bits = 0;
  let value = 0;
  const bytes: number[] = [];
  for (const ch of clean) {
    const idx = BASE32_ALPHABET.indexOf(ch);
    if (idx === -1) throw new Error(`Invalid base32 character: ${ch}`);
    value = (value << 5) | idx;
    bits += 5;
    if (bits >= 8) {
      bytes.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(bytes);
}

/** Generate a new random base32 secret (default 20 bytes / 160 bits). */
export function generateTotpSecret(bytes = 20): string {
  return base32Encode(randomBytes(bytes));
}

/** HOTP: RFC 4226 truncated HMAC value for a counter. */
export function hotp(secret: Buffer, counter: number, digits = 6): string {
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const hmac = createHmac("sha1", secret).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const code =
    ((hmac[offset] & 0x7f) << 24) |
    ((hmac[offset + 1] & 0xff) << 16) |
    ((hmac[offset + 2] & 0xff) << 8) |
    (hmac[offset + 3] & 0xff);
  return (code % 10 ** digits).toString().padStart(digits, "0");
}

export interface VerifyOptions {
  digits?: number;
  stepSeconds?: number;
  /** Steps of clock skew allowed either side of the current step. */
  window?: number;
  now?: number;
}

/** Verify a TOTP code, allowing `window` steps of clock skew either side. */
export function verifyTotp(secret: string, token: string, opts: VerifyOptions = {}): boolean {
  const digits = opts.digits ?? 6;
  const step = opts.stepSeconds ?? 30;
  const window = opts.window ?? 1;
  const now = opts.now ?? Date.now();
  const normalized = (token ?? "").replace(/\s+/g, "");
  if (!/^\d+$/.test(normalized) || normalized.length !== digits) return false;
  let key: Buffer;
  try {
    key = base32Decode(secret);
  } catch {
    return false;
  }
  const counter = Math.floor(now / 1000 / step);
  for (let i = -window; i <= window; i++) {
    if (hotp(key, counter + i, digits) === normalized) return true;
  }
  return false;
}

/** Build an otpauth:// URI for authenticator apps. */
export function otpauthUrl(opts: { secret: string; label: string; issuer?: string }): string {
  const issuer = opts.issuer ?? "Camxora";
  const label = encodeURIComponent(`${issuer}:${opts.label}`);
  const params = new URLSearchParams({
    secret: opts.secret,
    issuer,
    algorithm: "SHA1",
    digits: "6",
    period: "30",
  });
  return `otpauth://totp/${label}?${params.toString()}`;
}
