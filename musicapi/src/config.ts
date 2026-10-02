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
 * Resolve the key used to encrypt secrets stored at rest (Suno account
 * cookies). Refuses to start with a weak/missing value so cookies are never
 * silently written in plaintext.
 */
function resolveCookieEncryptionKey(): string {
  const key = process.env.COOKIE_ENCRYPTION_KEY ?? "";
  if (!key || key.length < 32) {
    throw new Error(
      "COOKIE_ENCRYPTION_KEY must be set to a strong value (>= 32 characters). " +
        "It encrypts Suno account cookies at rest. Generate one with: " +
        "node -e \"console.log(require('crypto').randomBytes(48).toString('hex'))\"",
    );
  }
  return key;
}

/**
 * Resolve the Fastify `trustProxy` option. Behind a reverse proxy (nginx,
 * Cloudflare, a load balancer) the socket peer is the proxy, so `req.ip` would
 * report the proxy address and API-key IP whitelists would either never match
 * or match everyone. Setting TRUST_PROXY to the proxy's IP/CIDR list makes
 * `req.ip` reflect the real client (from X-Forwarded-For) for those peers only.
 * Accepted values: "false"/unset (off), "true" (trust all — only safe when the
 * app is unreachable except through the proxy), or a comma-separated IP/CIDR
 * list (recommended).
 */
function resolveTrustProxy(): boolean | string {
  const raw = (process.env.TRUST_PROXY ?? "").trim();
  if (!raw || raw === "false") return false;
  if (raw === "true") return true;
  return raw;
}

export const config = {
  /** Fastify trustProxy setting; controls how `req.ip` is derived. */
  trustProxy: resolveTrustProxy(),
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
  /** Key for encrypting secrets at rest (Suno account cookies). */
  cookieEncryptionKey: resolveCookieEncryptionKey(),
  /**
   * Origins allowed to drive cookie-authenticated state-changing requests
   * (CSRF defense-in-depth on top of the session cookie's SameSite=Lax).
   * Comma-separated; defaults to the two local dev frontends.
   */
  frontendOrigins: (process.env.FRONTEND_ORIGINS ?? "http://localhost:4001,http://localhost:4002")
    .split(",")
    .map((o) => o.trim().replace(/\/$/, ""))
    .filter(Boolean),
  /**
   * Whether the session cookie is marked `Secure` (only sent over HTTPS).
   * Defaults to on in production; set SESSION_COOKIE_SECURE=false to override
   * when the frontends are served over plain HTTP.
   */
  sessionCookieSecure:
    (process.env.SESSION_COOKIE_SECURE ?? String(process.env.NODE_ENV === "production")) === "true",
  /** Pino level for the Fastify logger (trace|debug|info|warn|error|fatal|silent). */
  logLevel: process.env.LOG_LEVEL ?? "info",
  /**
   * Extra browser origins allowed to send credentialed (cookie) requests, on
   * top of `frontendOrigins`. Comma-separated, empty by default: the panels
   * reach the API same-origin through the nginx `/backend` proxy, so nothing
   * needs to be listed unless a client calls the API cross-origin directly.
   */
  apiCorsOrigins: (process.env.API_CORS_ORIGINS ?? "")
    .split(",")
    .map((o) => o.trim().replace(/\/$/, ""))
    .filter(Boolean),
  /**
   * Edge rate limiting, keyed on `req.ip` per time window. `req.ip` is only the
   * real client address when `TRUST_PROXY` trusts the nginx hop, otherwise every
   * proxied caller shares the proxy's address.
   */
  rateLimit: {
    /** Requests per client per window across the whole API. */
    max: Number(process.env.RATE_LIMIT_MAX ?? 300),
    windowMs: Number(process.env.RATE_LIMIT_WINDOW_MS ?? 60_000),
    /** Stricter budget for credential endpoints (`/auth/login`, `/auth/register`). */
    authMax: Number(process.env.RATE_LIMIT_AUTH_MAX ?? 10),
    /**
     * Per-user limits (req/min, req/day) read from the `rate_limits` table and
     * enforced at the API-key choke point (`requireKey`), aggregated across all
     * of a user's keys. Set to `false` to disable the check entirely.
     */
    perUserEnabled: (process.env.RATE_LIMIT_PER_USER_ENABLED ?? "true") === "true",
    /** How long a user's `rate_limits` row is cached before re-reading the DB. */
    perUserCacheMs: Number(process.env.RATE_LIMIT_PER_USER_CACHE_MS ?? 30_000),
  },
  /**
   * Outbound alert delivery (REQUIREMENTS §4.10). Reuses the same Telegram bot
   * the ops health probe uses; leaving either value unset keeps the evaluator
   * running but silently skips delivery (alerts still surface in the admin
   * panel). `checkIntervalMs` drives the in-process evaluator loop; set it to 0
   * to disable the loop entirely (the admin endpoints keep working).
   */
  alerts: {
    telegramBotToken: process.env.ALERT_TELEGRAM_BOT_TOKEN ?? "",
    telegramChatId: process.env.ALERT_TELEGRAM_CHAT_ID ?? "",
    checkIntervalMs: Number(process.env.ALERT_CHECK_INTERVAL_MS ?? 300_000),
  },
  bakong: {
    apiToken: process.env.BAKONG_API_TOKEN ?? "",
    accountId: process.env.BAKONG_ACCOUNT_ID ?? "",
    merchantName: process.env.BAKONG_MERCHANT_NAME ?? "Camxora Music API",
    merchantCity: process.env.BAKONG_MERCHANT_CITY ?? "Phnom Penh",
    apiBaseUrl: process.env.BAKONG_API_BASE_URL ?? "https://api-bakong.nbc.gov.kh",
    useSit: (process.env.BAKONG_USE_SIT ?? "false") === "true",
  },
  // ChmabaPay (pay.chmaba.com) checkout gateway. One account key authenticates
  // every store on the account; payments target a single store. Webhook
  // signatures are verified against the endpoint's signing secret.
  champapay: {
    apiKey: process.env.CHAMPAPAY_API_KEY ?? "",
    webhookSecret: process.env.CHAMPAPAY_WEBHOOK_SECRET ?? "",
    storeId: process.env.CHAMPAPAY_STORE_ID ?? "",
    apiBaseUrl: process.env.CHAMPAPAY_API_BASE_URL ?? "https://pay.chmaba.com",
  },
};
