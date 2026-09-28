import "dotenv/config";
import { randomUUID } from "node:crypto";

/**
 * Resolve the JWT signing secret, refusing to start with a missing or weak
 * value. A hardcoded fallback would let anyone forge admin tokens in any
 * environment where JWT_SECRET was not set.
 */
function resolveJwtSecret(): string {
  const secret = process.env.JWT_SECRET ?? "";
  const isPlaceholder = secret === "dev-secret-change-me";
  if (!secret || isPlaceholder || secret.length < 32) {
    throw new Error(
      "JWT_SECRET must be set to a strong value (>= 32 characters) and must not be " +
        "the default placeholder. Generate one with: " +
        "node -e \"console.log(require('crypto').randomBytes(48).toString('hex'))\"",
    );
  }
  return secret;
}

/**
 * Resolve the AES-256 key used to encrypt Suno `client_cookie` values at rest.
 * Refuse to start when it is missing or the wrong size — silently falling back
 * would store account cookies in plaintext, defeating the point of encrypting.
 */
function resolveCookieEncryptionKey(): Buffer {
  const raw = process.env.COOKIE_ENCRYPTION_KEY ?? "";
  if (!/^[0-9a-fA-F]{64}$/.test(raw)) {
    throw new Error(
      "COOKIE_ENCRYPTION_KEY must be a 64-character hex string (32 bytes). Generate one with: " +
        "node -e \"console.log(require('crypto').randomBytes(32).toString('hex'))\"",
    );
  }
  return Buffer.from(raw, "hex");
}

export const config = {
  /** Full cookie header (optional, sent as `Cookie` on Clerk requests). */
  cookie: process.env.SUNO_COOKIE ?? "",
  /** Durable Clerk `__client` cookie value — used to mint/refresh JWTs. */
  clientCookie: process.env.SUNO_CLIENT_COOKIE ?? "",
  /** One-off JWT (simplest; expires ~1h). Mutually preferred if set. */
  jwt: process.env.SUNO_JWT ?? "",
  clerkUrl: process.env.SUNO_CLERK_URL ?? "https://auth.suno.com",
  apiUrl: process.env.SUNO_API_URL ?? "https://studio-api-prod.suno.com",
  model: process.env.SUNO_MODEL ?? "chirp-auk-turbo",
  captchaToken: process.env.SUNO_CAPTCHA_TOKEN ?? "",
  twoCaptchaKey: process.env.TWOCAPTCHA_KEY ?? "",
  // device-id is the browser's ajs_anonymous_id / suno_device_id value.
  deviceId: process.env.SUNO_DEVICE_ID ?? randomUUID(),
  databaseUrl:
    process.env.DATABASE_URL ?? "postgres://postgres:postgres@localhost:5432/sunoapi",
  jwtSecret: resolveJwtSecret(),
  /** AES-256-GCM key for `suno_accounts.client_cookie` at rest. */
  cookieEncryptionKey: resolveCookieEncryptionKey(),
  bakong: {
    apiToken: process.env.BAKONG_API_TOKEN ?? "",
    accountId: process.env.BAKONG_ACCOUNT_ID ?? "",
    merchantName: process.env.BAKONG_MERCHANT_NAME ?? "Camxora Music API",
    merchantCity: process.env.BAKONG_MERCHANT_CITY ?? "Phnom Penh",
    apiBaseUrl: process.env.BAKONG_API_BASE_URL ?? "https://api-bakong.nbc.gov.kh",
    useSit: (process.env.BAKONG_USE_SIT ?? "false") === "true",
  },
};
