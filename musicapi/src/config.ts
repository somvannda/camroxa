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

/** Account-selection credit strategy (see `config.suno.creditStrategy`). */
export type CreditStrategy = "off" | "balanced" | "max_first";

/**
 * Parse `SUNO_CREDIT_STRATEGY`, falling back to `balanced` for an unset or
 * unrecognized value so a typo can never silently disable credit balancing.
 */
function resolveCreditStrategy(): CreditStrategy {
  const raw = (process.env.SUNO_CREDIT_STRATEGY ?? "balanced").trim().toLowerCase();
  return raw === "off" || raw === "max_first" || raw === "balanced" ? raw : "balanced";
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
  /** Default model when a request omits one — the live Suno default (v6). */
  model: process.env.SUNO_MODEL ?? "chirp-hawk",
  captchaToken: process.env.SUNO_CAPTCHA_TOKEN ?? "",
  twoCaptchaKey: process.env.TWOCAPTCHA_KEY ?? "",
  /** Cloudflare Turnstile sitekey Suno mounts on its generation gate. */
  turnstileSitekey: process.env.SUNO_TURNSTILE_SITEKEY ?? "0x4AAAAAADI7xDNyj-3LcIbi",
  /** Page URL the Turnstile widget is served on (sent to 2Captcha). */
  turnstilePageUrl: process.env.SUNO_TURNSTILE_PAGEURL ?? "https://suno.com/create",
  // device-id is the browser's ajs_anonymous_id / suno_device_id value.
  deviceId: process.env.SUNO_DEVICE_ID ?? randomUUID(),
  databaseUrl:
    process.env.DATABASE_URL ?? "postgres://postgres:postgres@localhost:5432/sunoapi",
  /**
   * Optional host allowlist for user-supplied webhook `callback_url`s, from a
   * comma-separated `CALLBACK_ALLOWED_HOSTS`. Empty means "any public host is
   * allowed" (private/internal targets are always blocked); when set, a
   * callback host must equal an entry or be a subdomain of one.
   */
  callbackAllowedHosts: (process.env.CALLBACK_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean),
  jwtSecret: resolveJwtSecret(),
  /** AES-256-GCM key for `suno_accounts.client_cookie` at rest. */
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
    /**
     * Window for the per-user `requests_per_window` budget, kept separate from
     * the global edge `windowMs` so a 10-second budget (sunoapi.org's 20/10s
     * shape) does not also loosen/tighten the whole-API edge limiter.
     */
    userWindowMs: Number(process.env.RATE_LIMIT_USER_WINDOW_MS ?? 10_000),
  },
  /**
   * Concurrency limits for Suno-backed work. A tiny account pool must not take
   * an unbounded burst: every job calls `pool.pick()` and submits in parallel,
   * so exceeding what the pool can absorb yields captcha/429 churn and wasted
   * credits. The gate admits at most `maxConcurrent` (explicit) or
   * `pool.size × concurrentPerAccount` jobs at once, and at most
   * `maxConcurrentPerUser` per user unless their `rate_limits` row overrides it.
   */
  suno: {
    /** Concurrent jobs to plan per pooled Suno account. */
    concurrentPerAccount: Math.max(1, Number(process.env.SUNO_CONCURRENT_PER_ACCOUNT ?? 4)),
    /** Explicit hard ceiling on concurrent jobs; null derives it from pool size. */
    maxConcurrent: process.env.SUNO_MAX_CONCURRENT
      ? Math.max(1, Number(process.env.SUNO_MAX_CONCURRENT))
      : null,
    /** Default per-user concurrent-job cap when `rate_limits` has no override. */
    maxConcurrentPerUser: Math.max(1, Number(process.env.SUNO_MAX_CONCURRENT_PER_USER ?? 2)),
    /**
     * Minimum live credit balance an account must keep to be eligible for new
     * work. Selection skips any account below this, so a nearly-drained account
     * cannot be handed a job it will fail to submit (`generate/v2` -> 402 "not
     * enough credits"). Accounts report a positive balance until they hit zero,
     * so a floor above one generation's cost is what actually prevents the 402s.
     * 0 restores the old "only skip exactly-empty accounts" behaviour.
     */
    minCredits: Math.max(0, Number(process.env.SUNO_MIN_CREDITS ?? 10)),
    /**
     * Per-account in-flight cap. Account selection is least-loaded-first, so a
     * burst spreads across the pool; an account already at this cap is used only
     * when no under-cap account is available. With a global cap of
     * `pool.size × concurrentPerAccount`, per-account load stays at or below this.
     */
    maxConcurrentPerAccount: Math.max(1, Number(process.env.SUNO_MAX_CONCURRENT_PER_ACCOUNT ?? 4)),
    /**
     * How many jobs may wait for a slot before new arrivals are rejected
     * (0 = unbounded). Bounds the detached-job backlog so a flood cannot grow
     * the in-memory promise queue without limit; a rejected job fails out with
     * a retryable error and its charge refunded.
     */
    maxQueue: Math.max(0, Number(process.env.SUNO_MAX_QUEUE ?? 1000)),
    /**
     * Per-account request pacing: at most `requestsPerAccount` calls within
     * `rateWindowMs`. Suno rate-limits an account at ~20 requests / 10s and
     * answers 429 past that, so the client suspends instead of bursting. 0
     * disables pacing.
     */
    requestsPerAccount: Math.max(0, Number(process.env.SUNO_REQUESTS_PER_ACCOUNT ?? 20)),
    rateWindowMs: Math.max(100, Number(process.env.SUNO_RATE_WINDOW_MS ?? 10_000)),
    /**
     * How long a Suno account sits out after answering 429, so retries and other
     * jobs don't immediately re-hit the throttled account. 0 disables.
     */
    rateLimitCooldownMs: Math.max(0, Number(process.env.SUNO_RATE_LIMIT_COOLDOWN_MS ?? 5_000)),
    /**
     * Credit-aware account selection (see `src/pool.ts` `orderForDispatch`).
     * `balanced` (default) prefers the highest-balance account and reserves the
     * estimated spend of every in-flight job against that balance, so concurrent
     * picks spread out and all accounts drain toward a common level.
     * `max_first` prefers the highest balance too but reserves nothing, so it
     * keeps drawing from the single richest account between billing refreshes.
     * `off` restores the legacy least-loaded-only ordering.
     */
    creditStrategy: resolveCreditStrategy(),
    /**
     * Suno credits to reserve against an account's cached balance for each
     * in-flight job. Suno debits a generation on submit, but the cached health
     * only refreshes every 30s, so without a reservation every concurrent pick
     * reads the same snapshot and dogpiles the same account. Estimate only;
     * cleared whenever a fresh `billing/info` arrives. 0 disables reservations.
     */
    creditReserve: Math.max(0, Number(process.env.SUNO_CREDIT_RESERVE ?? 10)),
  },
  /**
   * Customer-account credit floor. "Free" generation endpoints cost 0 credits
   * and are never charged, but they must not become a free tier for every
   * signed-in account: `minCredits` requires a funded balance before a
   * cost-0 generation run is admitted, so free is a perk for paying customers.
   * Paid endpoints are unaffected (their own cost already gates them), and
   * read/detail/download routes stay open. 0 disables the gate.
   */
  creditGate: {
    minCredits: Math.max(0, Number(process.env.USER_MIN_CREDITS ?? 10)),
  },
  /**
   * Generation-flow guard. When enabled, a derivative endpoint (extend, cover,
   * remaster, stems, cover-image, wav, midi, video, recovery, timestamped
   * lyrics, and the `*_detail` reads) requires the caller to own the referenced
   * asset AND for the job that produced it to have completed — so a clip can no
   * longer be requested without a prior generation. Off by default; turning it
   * on is a deliberate operator action.
   */
  flowGuard: {
    enforced: (process.env.FLOW_GUARD_ENFORCED ?? "false") === "true",
  },
  /**
   * Outbound alert delivery (task 5.5, REQUIREMENTS §4.10). Reuses the same
   * Telegram bot the ops health probe uses; leaving either value unset keeps the
   * evaluator running but silently skips delivery (alerts still surface in the
   * admin panel). `checkIntervalMs` drives the in-process evaluator loop; set it
   * to 0 to disable the loop entirely (the admin endpoints keep working).
   */
  alerts: {
    telegramBotToken: process.env.ALERT_TELEGRAM_BOT_TOKEN ?? "",
    telegramChatId: process.env.ALERT_TELEGRAM_CHAT_ID ?? "",
    checkIntervalMs: Number(process.env.ALERT_CHECK_INTERVAL_MS ?? 300_000),
  },
  /**
   * Outbound mail (Resend). Every message — receipts, credit alerts, campaigns,
   * automations — goes through the same ledger in `mail.ts`, so consent,
   * suppression and engagement live in one place.
   *
   * Two `from` identities are kept as separate fields even though both point at
   * the same verified domain today: `mail.camxora.com` is the only domain
   * verified in Resend, so receipts and campaigns share it. Splitting them later
   * is one string — verify music.camxora.com, then change `fromTransactional` —
   * and that is worth keeping cheap because a marketing complaint spike should
   * eventually not touch receipts.
   *
   * `publicBaseUrl` is the externally reachable origin used in tracking,
   * click-redirect and unsubscribe URLs; `appUrl` is the product site a CTA
   * links to. They are different hosts on purpose.
   */
  mail: {
    apiKey: process.env.RESEND_API_KEY ?? "",
    webhookSecret: process.env.RESEND_WEBHOOK_SECRET ?? "",
    fromTransactional:
      process.env.MAIL_FROM_TRANSACTIONAL ?? "CAMXORA <no-reply@mail.camxora.com>",
    fromCampaign: process.env.MAIL_FROM_CAMPAIGN ?? "CAMXORA <hello@mail.camxora.com>",
    /**
     * Where a CTA button sends the user. This is the product the recipient sees,
     * not the API: it must be the site that actually shows their credits and
     * checkout, or a "buy credits" button lands somewhere that cannot sell.
     */
    appUrl: (process.env.MAIL_APP_URL ?? "https://music.camxora.com").replace(/\/+$/, ""),
    replyTo: process.env.MAIL_REPLY_TO ?? "",
    publicBaseUrl: (process.env.MAIL_PUBLIC_BASE_URL ?? "").replace(/\/+$/, ""),
    /** Master switch; sending is also skipped whenever `apiKey` is empty. */
    enabled: (process.env.MAIL_ENABLED ?? "true") === "true",
    /** Resend limits concurrent requests per second; the sender paces to this. */
    ratePerSecond: Math.max(1, Number(process.env.MAIL_RATE_PER_SECOND ?? 2)),
    /** How often the queue is drained. 0 disables the in-process loop. */
    loopIntervalMs: Number(process.env.MAIL_LOOP_INTERVAL_MS ?? 15_000),
    /** Give up after this many delivery attempts. */
    maxAttempts: Math.max(1, Number(process.env.MAIL_MAX_ATTEMPTS ?? 3)),
    /** Marketing mail is capped per user to protect reputation. */
    marketingCooldownDays: Math.max(1, Number(process.env.MAIL_MARKETING_COOLDOWN_DAYS ?? 7)),
  },
  /**
   * Background job queue (roadmap R4). `driver: "memory"` is the default and
   * keeps the original behaviour: a job runs inline in the process that accepted
   * the request, and a restart fails out whatever was in flight. Setting
   * `QUEUE_DRIVER=redis` moves descriptor-backed jobs onto a Redis (BullMQ) work
   * list consumed by this process, so a job left behind by a crash is picked up
   * and re-run instead of being discarded — and a second node could consume the
   * same list. The Postgres `jobs` table stays the system of record either way.
   */
  queue: {
    driver: (process.env.QUEUE_DRIVER ?? "memory").trim().toLowerCase() === "redis" ? "redis" : "memory",
    redisUrl: process.env.REDIS_URL ?? "redis://127.0.0.1:6379",
    /** How many jobs one consumer may run at once. */
    concurrency: Math.max(1, Number(process.env.QUEUE_CONCURRENCY ?? 4)),
  },
  /**
   * Google OAuth for the user-facing sign-in (users sign in ONLY via Google).
   * Managed from the admin console; env is the fallback (see runtimeSettings).
   */
  google: {
    clientId: process.env.GOOGLE_CLIENT_ID ?? "",
    clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    redirectUriUser: process.env.GOOGLE_REDIRECT_URI_USER ?? "http://localhost:4001/auth/callback",
  },
  /**
   * ChmabaPay (https://pay.chmaba.com) — KHQR / ABA PayWay payment provider for
   * the user billing page (§3.7). There is no sandbox: every `ck_live_…` key
   * moves real money. Checkout stays disabled until `apiKey` + `storeId` are set,
   * and the webhook refuses any delivery it cannot verify with `webhookSecret`.
   */
  chmaba: {
    apiKey: process.env.CHMABA_API_KEY ?? "",
    webhookSecret: process.env.CHMABA_WEBHOOK_SECRET ?? "",
    storeId: process.env.CHMABA_STORE_ID ?? "",
    apiBaseUrl: process.env.CHMABA_API_BASE_URL ?? "https://pay.chmaba.com",
  },
  /**
   * Deployment environment. The remote installer writes `MUSICAPI_ENV`
   * (`sandbox` | `production`); local runs fall back to `NODE_ENV`. Used to keep
   * Telegram alert delivery production-only, because sandbox and production
   * share the same alert bot/chat and would otherwise post to the live channel.
   */
  environment: (process.env.MUSICAPI_ENV ?? process.env.NODE_ENV ?? "development")
    .trim()
    .toLowerCase(),
  /**
   * Durable object storage for generated media (Backblaze B2 via its S3 API).
   * Reuses the platform's `PLATFORM_STREAMING_B2_*` deploy secrets by default;
   * `MUSICAPI_B2_*` wins when set, so musicapi can be pointed at its own bucket
   * or key without touching the platform. Storage stays disabled (live streaming
   * from Suno) until key id + application key + bucket are all present.
   */
  storage: {
    endpoint:
      process.env.MUSICAPI_B2_ENDPOINT ??
      process.env.PLATFORM_STREAMING_B2_ENDPOINT ??
      "https://s3.us-east-005.backblazeb2.com",
    region:
      process.env.MUSICAPI_B2_REGION ??
      process.env.PLATFORM_STREAMING_B2_REGION ??
      "us-east-005",
    bucket: process.env.MUSICAPI_B2_BUCKET ?? process.env.PLATFORM_STREAMING_B2_BUCKET ?? "",
    keyId: process.env.MUSICAPI_B2_KEY_ID ?? process.env.PLATFORM_STREAMING_B2_KEY_ID ?? "",
    applicationKey:
      process.env.MUSICAPI_B2_APPLICATION_KEY ??
      process.env.PLATFORM_STREAMING_B2_APPLICATION_KEY ??
      "",
    /** Key prefix so musicapi objects never collide with platform ones. */
    prefix: (process.env.MUSICAPI_B2_PREFIX ?? "musicapi").replace(/^\/+|\/+$/g, ""),
    /**
     * Optional CDN base (e.g. Cloudflare) served instead of presigned URLs.
     * Without it every read is a freshly-signed URL pointing straight at the
     * bucket: no edge cache, a different signature per request, and a US
     * round-trip from Asia. Set this in production.
     */
    publicBaseUrl: (process.env.MUSICAPI_B2_PUBLIC_BASE_URL ?? "").replace(/\/+$/, ""),
    /** Signed GET URL lifetime for direct B2 reads. */
    urlTtlSeconds: Number(process.env.MUSICAPI_B2_URL_TTL_SECONDS ?? 7 * 24 * 3600),
    /**
     * `Cache-Control` written on every uploaded object. Without one the CDN
     * applies its own short default (Cloudflare: 120 minutes) and re-fetches
     * from the bucket far more often than it needs to. Keys are stable per
     * clip, but a clip's bytes *can* be rewritten by the repair/re-render
     * paths, so this is a long-but-finite TTL rather than `immutable`.
     */
    cacheControl:
      process.env.MUSICAPI_B2_CACHE_CONTROL ?? "public, max-age=604800, stale-while-revalidate=86400",
  },
};

/** True when object storage is fully configured (key, secret and bucket set). */
export function storageConfigured(): boolean {
  const s = config.storage;
  return Boolean(s.endpoint && s.bucket && s.keyId && s.applicationKey);
}

/**
 * True when this process targets production. Alert delivery is production-only:
 * sandbox and production share the same Telegram bot/chat, so sandbox must not
 * post to the live ops channel. Local/unknown environments return false.
 */
export function isProduction(): boolean {
  return config.environment === "production" || config.environment === "prod";
}
