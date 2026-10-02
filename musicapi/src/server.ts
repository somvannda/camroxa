import Fastify, { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import rateLimit from "@fastify/rate-limit";
import { createHash, createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { AccountPool, RoutingPolicy } from "./pool.js";
import { SunoClient } from "./client.js";
import { query, queryOne, withTransaction } from "./db.js";
import { PoolClient } from "pg";
import { hashPassword, verifyPassword, signToken, verifyToken, UserPayload, SESSION_COOKIE, serializeSessionCookie, serializeClearedSessionCookie, readCookie } from "./appAuth.js";
import { OAuth2Client } from "google-auth-library";
import { config } from "./config.js";
import { Job, saveJob, loadJob, refundJobCredits } from "./jobs.js";
import { checkCallbackUrl } from "./ssrf.js";
import { encryptSecret } from "./crypto.js";
import { captchaRequired } from "./captcha.js";

// Fallback credit costs when the `pricing` table has no row for an endpoint.
// Real costs are read from the DB and configurable in the admin panel.
const DEFAULT_COSTS: Record<string, number> = {
  lyrics: 2,
  music: 9,
  extend: 9,
  cover: 9,
  stems: 9,
  sounds: 9,
  remaster: 9,
  mashup: 9,
  add_vocals: 9,
  add_instrumental: 9,
  replace_section: 9,
  cover_image: 5,
  persona: 9,
  wav: 1,
  upload_extend: 9,
  upload_cover: 9,
  upload_init: 1,
  upload_register: 1,
  recovery_audio: 9,
  mp4_generate: 5,
  boost_style: 9,
  midi_generate: 9,
  voice_phrase: 9,
  voice_validate: 1,
  voice_record: 1,
  voice_generate: 9,
  voice_apply: 9,
  voice_extend: 9,
  lyrics_detail: 1,
  wav_detail: 1,
  stems_detail: 1,
  video_detail: 1,
  cover_detail: 1,
  subtitle_detail: 1,
  recovery_detail: 1,
  mp4_detail: 1,
  midi_detail: 1,
  timestamped_lyrics_detail: 1,
};

export interface ApiKey {
  key: string;
  name: string;
  credits: number;
}

interface DbApiKey {
  id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  credits: number;
  safe_spend_limit: number | null;
  safe_spend_hourly: number | null;
  safe_spend_daily: number | null;
  safe_spend_total: number | null;
  ip_whitelist: string[];
  is_active: boolean;
}

interface DbUser {
  id: string;
  email: string;
  password_hash: string | null;
  google_id: string | null;
  role: "user" | "admin";
  name: string | null;
  status: string;
}

export interface ServerDeps {
  pool: AccountPool;
}

export function loadApiKeys(path: string): ApiKey[] {
  return JSON.parse(readFileSync(path, "utf8")) as ApiKey[];
}

/**
 * Credits-per-USD rate from the cheapest active credit pack — the same rate the
 * user-facing `/me/usage` and the admin `/admin/analytics` endpoint use, so every
 * revenue figure in the product agrees. Falls back to 200 credits/$1 when no
 * active pack is configured.
 */
async function creditsPerUsdRate(): Promise<number> {
  const pack = await queryOne<{ amount: string; price: string }>(
    "SELECT amount::text, price::text FROM credit_packs WHERE is_active = true ORDER BY amount LIMIT 1",
  );
  return pack && Number(pack.amount) > 0 && Number(pack.price) > 0
    ? Number(pack.amount) / Number(pack.price)
    : 200;
}

/**
 * Operator-managed panel branding and support links (REQUIREMENTS §4.10).
 * Stored as a JSONB document under the `brand` key of `app_settings`.
 */
export interface BrandSettings {
  name: string;
  docs_url: string;
  support_telegram_url: string;
  languages: string[];
}

/**
 * Thresholds/switches for the three alerts the admin panel surfaces
 * (REQUIREMENTS §4.10): Suno accounts running low on credits, Suno demanding a
 * captcha, and a spike in the job failure rate.
 */
export interface AlertSettings {
  enabled: boolean;
  low_credits_threshold: number;
  captcha_locked: boolean;
  failure_rate_threshold: number;
  failure_rate_min_requests: number;
  window_minutes: number;
}

const DEFAULT_BRAND: BrandSettings = {
  name: "Camxora Music API",
  docs_url: "",
  support_telegram_url: "",
  languages: ["en"],
};

const DEFAULT_ALERTS: AlertSettings = {
  enabled: true,
  low_credits_threshold: 50,
  captcha_locked: true,
  failure_rate_threshold: 0.25,
  failure_rate_min_requests: 20,
  window_minutes: 60,
};

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

function clampInt(value: unknown, fallback: number, min: number, max: number): number {
  return Math.round(clampNumber(value, fallback, min, max));
}

/**
 * Normalize a stored/upstream `brand` document, falling back to defaults per
 * field so a hand-edited row can never break the settings endpoint.
 */
function coerceBrand(value: unknown): BrandSettings {
  const o = (value ?? {}) as Record<string, unknown>;
  const languages = Array.isArray(o.languages)
    ? o.languages.filter((l): l is string => typeof l === "string" && l.trim() !== "").map((l) => l.trim())
    : [];
  return {
    name: typeof o.name === "string" && o.name.trim() ? o.name.trim() : DEFAULT_BRAND.name,
    docs_url: typeof o.docs_url === "string" ? o.docs_url.trim() : DEFAULT_BRAND.docs_url,
    support_telegram_url:
      typeof o.support_telegram_url === "string" ? o.support_telegram_url.trim() : DEFAULT_BRAND.support_telegram_url,
    languages: languages.length ? languages : [...DEFAULT_BRAND.languages],
  };
}

/** Normalize a stored/upstream `alerts` document with the same defensiveness. */
function coerceAlerts(value: unknown): AlertSettings {
  const o = (value ?? {}) as Record<string, unknown>;
  return {
    enabled: typeof o.enabled === "boolean" ? o.enabled : DEFAULT_ALERTS.enabled,
    low_credits_threshold: clampInt(o.low_credits_threshold, DEFAULT_ALERTS.low_credits_threshold, 0, 1_000_000),
    captcha_locked: typeof o.captcha_locked === "boolean" ? o.captcha_locked : DEFAULT_ALERTS.captcha_locked,
    failure_rate_threshold: clampNumber(o.failure_rate_threshold, DEFAULT_ALERTS.failure_rate_threshold, 0, 1),
    failure_rate_min_requests: clampInt(
      o.failure_rate_min_requests,
      DEFAULT_ALERTS.failure_rate_min_requests,
      1,
      1_000_000,
    ),
    window_minutes: clampInt(o.window_minutes, DEFAULT_ALERTS.window_minutes, 5, 1440),
  };
}

/** Merge an admin-supplied `brand` patch onto the current values, validating types. */
function mergeBrand(
  current: BrandSettings,
  patch: unknown,
): { ok: true; value: BrandSettings } | { ok: false; error: string } {
  if (typeof patch !== "object" || patch === null) return { ok: false, error: "brand must be an object." };
  const o = patch as Record<string, unknown>;
  const next: BrandSettings = { ...current, languages: [...current.languages] };
  if (o.name !== undefined) {
    if (typeof o.name !== "string" || !o.name.trim()) {
      return { ok: false, error: "brand.name must be a non-empty string." };
    }
    next.name = o.name.trim();
  }
  if (o.docs_url !== undefined) {
    if (typeof o.docs_url !== "string") return { ok: false, error: "brand.docs_url must be a string." };
    next.docs_url = o.docs_url.trim();
  }
  if (o.support_telegram_url !== undefined) {
    if (typeof o.support_telegram_url !== "string") {
      return { ok: false, error: "brand.support_telegram_url must be a string." };
    }
    next.support_telegram_url = o.support_telegram_url.trim();
  }
  if (o.languages !== undefined) {
    if (!Array.isArray(o.languages) || !o.languages.every((l) => typeof l === "string" && l.trim())) {
      return { ok: false, error: "brand.languages must be an array of non-empty strings." };
    }
    next.languages = o.languages.map((l) => (l as string).trim());
  }
  return { ok: true, value: next };
}

/** Merge an admin-supplied `alerts` patch onto the current values, validating types. */
function mergeAlerts(
  current: AlertSettings,
  patch: unknown,
): { ok: true; value: AlertSettings } | { ok: false; error: string } {
  if (typeof patch !== "object" || patch === null) return { ok: false, error: "alerts must be an object." };
  const o = patch as Record<string, unknown>;
  const next: AlertSettings = { ...current };
  for (const key of ["enabled", "captcha_locked"] as const) {
    if (o[key] !== undefined) {
      if (typeof o[key] !== "boolean") return { ok: false, error: `alerts.${key} must be a boolean.` };
      next[key] = o[key] as boolean;
    }
  }
  const numeric: Array<[keyof AlertSettings, number, number]> = [
    ["low_credits_threshold", 0, 1_000_000],
    ["failure_rate_threshold", 0, 1],
    ["failure_rate_min_requests", 1, 1_000_000],
    ["window_minutes", 5, 1440],
  ];
  for (const [key, min, max] of numeric) {
    if (o[key] === undefined) continue;
    const value = o[key];
    if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) {
      return { ok: false, error: `alerts.${key} must be a number between ${min} and ${max}.` };
    }
    (next[key] as number) = key === "failure_rate_threshold" ? value : Math.round(value);
  }
  return { ok: true, value: next };
}

export async function buildServer({ pool }: ServerDeps): Promise<FastifyInstance> {
  const app = Fastify({
    // JSON logs with request ids. Header redaction is defense-in-depth: Fastify's
    // default serializers omit headers, but anything that logs a raw request
    // (our own `app.log` calls included) must not leak credentials.
    logger: {
      level: config.logLevel,
      redact: {
        paths: ["req.headers.authorization", "req.headers.cookie", "res.headers.set-cookie"],
        censor: "[redacted]",
      },
    },
    trustProxy: config.trustProxy,
    requestTimeout: 600_000,
    connectionTimeout: 600_000,
    keepAliveTimeout: 600_000,
  });
  const jobs = new Map<string, Job>();

  // The in-memory job cache exists only for fast status reads. Every job is also
  // persisted to Postgres (see saveJob/loadJob), so entries can always be evicted
  // safely — `jobs.get(id) ?? loadJob(id)` transparently reloads them. Bound the
  // cache so a long-running process cannot grow without limit: finished jobs are
  // dropped after a short TTL, and if live jobs alone exceed the cap the oldest
  // finished jobs are evicted first (never a pending/running/streaming job).
  const JOB_TTL_MS = Number(process.env.JOB_CACHE_TTL_MS) || 10 * 60 * 1000;
  const MAX_JOBS_IN_MEMORY = Number(process.env.JOB_CACHE_MAX) || 5_000;
  const isTerminal = (j: Job): boolean => j.status === "complete" || j.status === "error";
  function evictJobs(now = Date.now()): void {
    for (const [id, job] of jobs) {
      if (isTerminal(job) && job.finishedAt && now - job.finishedAt > JOB_TTL_MS) jobs.delete(id);
    }
    if (jobs.size <= MAX_JOBS_IN_MEMORY) return;
    const finished = [...jobs.values()]
      .filter(isTerminal)
      .sort((a, b) => (a.finishedAt ?? a.createdAt) - (b.finishedAt ?? b.createdAt));
    for (const job of finished) {
      if (jobs.size <= MAX_JOBS_IN_MEMORY) break;
      jobs.delete(job.id);
    }
  }
  const evictionTimer = setInterval(() => evictJobs(), 60_000);
  evictionTimer.unref();
  app.addHook("onClose", () => { clearInterval(evictionTimer); });

  // Capture the raw request bytes for JSON bodies so webhook HMAC signatures
  // can be verified against the exact payload the gateway signed. Behaviour is
  // otherwise identical to Fastify's default JSON parser.
  app.addContentTypeParser(
    "application/json",
    { parseAs: "buffer" },
    (req: FastifyRequest & { rawBody?: Buffer }, body: Buffer, done) => {
      req.rawBody = body;
      try {
        done(null, body.length ? JSON.parse(body.toString("utf8")) : {});
      } catch (err) {
        (err as { statusCode?: number }).statusCode = 400;
        done(err as Error, undefined);
      }
    },
  );

  // These must be registered before any route is declared: @fastify/rate-limit
  // and @fastify/cors attach per-route hooks at registration time, so routes
  // added earlier would silently miss them. That is why buildServer is async.
  // Security headers. This is a JSON API (no HTML documents are served), so CSP
  // has nothing to protect; public `/v1` responses are meant to be read from any
  // origin (see CORS below), which `cross-origin` lets browsers do.
  await app.register(helmet, {
    contentSecurityPolicy: false,
    crossOriginResourcePolicy: { policy: "cross-origin" },
  });

  // CORS has two audiences:
  //   * Public API (`/v1/*`, `/api/v1/*`) — authenticated with a Bearer API key
  //     and never with cookies, so any origin may call it.
  //   * Cookie routes (`sunosession` session) — only the configured frontends may
  //     call them with credentials, so a hostile page can't ride a user's session.
  //     The panels reach these same-origin through the nginx `/backend` proxy, so
  //     the list is defense-in-depth rather than a functional requirement.
  const credentialOrigins = [...config.frontendOrigins, ...config.apiCorsOrigins];
  await app.register(cors, {
    delegator: (req, cb) => {
      const isPublicApi = req.url.startsWith("/v1/") || req.url.startsWith("/api/v1/");
      cb(null, isPublicApi ? { origin: "*" } : { origin: credentialOrigins, credentials: true });
    },
  });

  // Per-client-IP rate limiting (in-memory; no per-request DB writes). The key is
  // `req.ip`, which is only the real client address when TRUST_PROXY trusts the
  // nginx hop — otherwise every proxied caller shares the proxy's address.
  await app.register(rateLimit, {
    global: true,
    max: config.rateLimit.max,
    timeWindow: config.rateLimit.windowMs,
  });

  // Edge request counters for the admin `/metrics` snapshot. In-memory and reset
  // on restart, which is all a single-process deployment needs.
  const requestCounters = { total: 0, clientErrors: 0, serverErrors: 0 };
  app.addHook("onResponse", async (_req, reply) => {
    requestCounters.total += 1;
    if (reply.statusCode >= 500) requestCounters.serverErrors += 1;
    else if (reply.statusCode >= 400) requestCounters.clientErrors += 1;
  });

  // Alert evaluator state (REQUIREMENTS §4.10). `alertState` maps an alert id to a
  // fingerprint of its last-notified content so the Telegram push only fires on a
  // state change (new alert, changed message, or recovery) — the same "notify
  // once" behaviour the ops healthcheck script keeps in a state file, held in
  // memory here because this process owns the alert lifecycle.
  const alertState = new Map<string, string>();
  let alertTimer: ReturnType<typeof setInterval> | null = null;

  // Start the periodic alert evaluator once routes are live and stop it on
  // shutdown. A non-positive ALERT_CHECK_INTERVAL_MS disables the loop (the admin
  // endpoints keep working, so opening the panel still acts as a manual check).
  app.addHook("onReady", async () => {
    startAlertLoop();
  });
  app.addHook("onClose", () => {
    stopAlertLoop();
  });

  // --- Google OAuth ---------------------------------------------------------
  const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID ?? "";
  const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET ?? "";
  // Register BOTH of these in the Google Cloud Console under "Authorized redirect URIs":
  //   http://localhost:4001/auth/callback  (user-facing workspace)
  //   http://localhost:4002/auth/callback  (admin console)
  // For production, replace with your real domains, e.g.:
  //   https://app.yourdomain.com/auth/callback
  //   https://admin.yourdomain.com/auth/callback
  const GOOGLE_REDIRECT_ALLOWLIST: string[] = [
    process.env.GOOGLE_REDIRECT_URI_USER ?? "http://localhost:4001/auth/callback",
    process.env.GOOGLE_REDIRECT_URI_ADMIN ?? "http://localhost:4002/auth/callback",
  ];
  const googleConfigured = Boolean(GOOGLE_CLIENT_ID && GOOGLE_CLIENT_SECRET);

  function resolveGoogleClient(redirectUri: string | undefined): {
    client: OAuth2Client | null;
    redirectUri: string;
  } {
    // Pick the requested redirect_uri if it's on the allowlist,
    // otherwise fall back to the user-facing default.
    const defaultUri = GOOGLE_REDIRECT_ALLOWLIST[0];
    const chosen =
      redirectUri && GOOGLE_REDIRECT_ALLOWLIST.includes(redirectUri)
        ? redirectUri
        : defaultUri;
    if (!googleConfigured) return { client: null, redirectUri: chosen };
    // Build a fresh client per request: `redirectUri` is not settable on a
    // shared client, and a per-request instance avoids concurrent Google
    // flows cross-wiring each other's redirect URI.
    const client = new OAuth2Client({
      clientId: GOOGLE_CLIENT_ID,
      clientSecret: GOOGLE_CLIENT_SECRET,
      redirectUri: chosen,
    });
    return { client, redirectUri: chosen };
  }

  // --- auth helpers --------------------------------------------------------
  /**
   * Mint a stateless, HMAC-signed OAuth `state`. It binds the requested
   * redirect_uri to this server and carries a timestamp so a replayed or
   * forged state (CSRF/login-CSRF) is rejected. Signature uses the JWT secret.
   */
  function signOAuthState(redirectUri: string): string {
    const payload = Buffer.from(
      JSON.stringify({ r: redirectUri, t: Date.now(), n: randomUUID() }),
    ).toString("base64url");
    const sig = createHmac("sha256", config.jwtSecret).update(payload).digest("base64url");
    return `${payload}.${sig}`;
  }

  /** Verify a signed state; returns the embedded redirect_uri or null. */
  function verifyOAuthState(state: string, maxAgeMs = 10 * 60 * 1000): string | null {
    const dot = state.indexOf(".");
    if (dot <= 0) return null;
    const payload = state.slice(0, dot);
    const sig = state.slice(dot + 1);
    const expected = createHmac("sha256", config.jwtSecret).update(payload).digest("base64url");
    const a = Buffer.from(expected, "utf8");
    const b = Buffer.from(sig, "utf8");
    if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
    try {
      const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as {
        r?: string;
        t?: number;
      };
      if (!data.r || typeof data.t !== "number") return null;
      if (Date.now() - data.t > maxAgeMs) return null;
      if (!GOOGLE_REDIRECT_ALLOWLIST.includes(data.r)) return null;
      return data.r;
    } catch {
      return null;
    }
  }

  function hashKey(token: string): string {
    return createHash("sha256").update(token).digest("hex");
  }

  async function findKey(token: string): Promise<DbApiKey | null> {
    return queryOne<DbApiKey>(
      `SELECT id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active
       FROM api_keys WHERE key_hash = $1 AND is_active = true`,
      [hashKey(token)],
    );
  }

  async function requireKey(req: FastifyRequest, reply: FastifyReply): Promise<DbApiKey | null> {
    const auth = req.headers.authorization ?? "";
    const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    if (!token) {
      reply.code(401).send({ error: "Invalid or missing API key." });
      return null;
    }
    const key = await findKey(token);
    if (!key) {
      reply.code(401).send({ error: "Invalid or missing API key." });
      return null;
    }
    if (key.ip_whitelist && key.ip_whitelist.length > 0 && !key.ip_whitelist.includes(req.ip)) {
      reply.code(403).send({ error: "IP not allowed for this API key." });
      return null;
    }
    if (config.rateLimit.perUserEnabled && !(await enforceUserRateLimit(key.user_id, reply))) {
      return null;
    }
    return key;
  }

  // --- per-user rate limiting ----------------------------------------------
  // Limits live in the `rate_limits` table (req/min, req/day) and are enforced
  // per *user*, so every key a user holds shares one budget. Rows are read
  // lazily and cached briefly so the hot request path doesn't hit the DB each
  // time. Counters are in-memory fixed windows, matching the edge limiter
  // (a single-process deployment doesn't need a shared store).
  interface UserRateLimits {
    perMinute: number | null;
    perDay: number | null;
  }

  const DAY_MS = 86_400_000;
  const rateLimitCache = new Map<string, { limits: UserRateLimits | null; at: number }>();
  const minuteWindows = new Map<string, { start: number; count: number }>();
  const dayWindows = new Map<string, { start: number; count: number }>();
  const RATE_LIMIT_MAP_CAP = Number(process.env.RATE_LIMIT_MAP_CAP ?? 20_000);

  async function loadUserRateLimits(userId: string): Promise<UserRateLimits | null> {
    const now = Date.now();
    const cached = rateLimitCache.get(userId);
    if (cached && now - cached.at < config.rateLimit.perUserCacheMs) return cached.limits;
    const row = await queryOne<{ requests_per_minute: number | null; requests_per_day: number | null }>(
      "SELECT requests_per_minute, requests_per_day FROM rate_limits WHERE user_id = $1 LIMIT 1",
      [userId],
    );
    const limits =
      row && (row.requests_per_minute != null || row.requests_per_day != null)
        ? { perMinute: row.requests_per_minute, perDay: row.requests_per_day }
        : null;
    // Bound the cache: drop entries that no longer match the current window.
    if (rateLimitCache.size > RATE_LIMIT_MAP_CAP) {
      for (const [id, entry] of rateLimitCache) {
        if (now - entry.at >= config.rateLimit.perUserCacheMs) rateLimitCache.delete(id);
      }
    }
    rateLimitCache.set(userId, { limits, at: now });
    return limits;
  }

  /** Increment the counter for `key` in the fixed window starting at `start`. */
  function bumpWindow(
    windows: Map<string, { start: number; count: number }>,
    key: string,
    start: number,
  ): number {
    const existing = windows.get(key);
    const current = existing && existing.start === start ? existing : { start, count: 0 };
    current.count += 1;
    windows.set(key, current);
    return current.count;
  }

  interface UserRateResult {
    allowed: boolean;
    exceeded: "minute" | "day" | null;
    retryAfterSec: number;
    minuteRemaining: number | null;
    dayRemaining: number | null;
  }

  function checkUserRateLimit(userId: string, limits: UserRateLimits): UserRateResult {
    const now = Date.now();
    const windowMs = config.rateLimit.windowMs;
    const minuteStart = now - (now % windowMs);
    const day = new Date(now);
    const dayStart = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate());
    let minuteRemaining: number | null = null;
    let dayRemaining: number | null = null;

    if (limits.perMinute != null) {
      if (minuteWindows.size > RATE_LIMIT_MAP_CAP) {
        for (const [id, w] of minuteWindows) if (w.start !== minuteStart) minuteWindows.delete(id);
      }
      const count = bumpWindow(minuteWindows, userId, minuteStart);
      minuteRemaining = Math.max(0, limits.perMinute - count);
      if (count > limits.perMinute) {
        return {
          allowed: false,
          exceeded: "minute",
          retryAfterSec: Math.max(1, Math.ceil((minuteStart + windowMs - now) / 1000)),
          minuteRemaining: 0,
          dayRemaining,
        };
      }
    }
    if (limits.perDay != null) {
      if (dayWindows.size > RATE_LIMIT_MAP_CAP) {
        for (const [id, w] of dayWindows) if (w.start !== dayStart) dayWindows.delete(id);
      }
      const count = bumpWindow(dayWindows, userId, dayStart);
      dayRemaining = Math.max(0, limits.perDay - count);
      if (count > limits.perDay) {
        return {
          allowed: false,
          exceeded: "day",
          retryAfterSec: Math.max(1, Math.ceil((dayStart + DAY_MS - now) / 1000)),
          minuteRemaining,
          dayRemaining: 0,
        };
      }
    }
    return { allowed: true, exceeded: null, retryAfterSec: 0, minuteRemaining, dayRemaining };
  }

  /**
   * Enforce the calling user's `rate_limits` row. Returns `true` when the request
   * may proceed (also advertising the remaining budget), or sends a 429 and
   * returns `false` when a limit is exceeded.
   */
  async function enforceUserRateLimit(userId: string, reply: FastifyReply): Promise<boolean> {
    const limits = await loadUserRateLimits(userId);
    if (!limits) return true;
    const result = checkUserRateLimit(userId, limits);
    if (limits.perMinute != null) {
      reply.header("x-user-rate-limit", String(limits.perMinute));
      reply.header("x-user-rate-remaining", String(result.minuteRemaining ?? 0));
    }
    if (limits.perDay != null) {
      reply.header("x-user-rate-limit-day", String(limits.perDay));
      reply.header("x-user-rate-remaining-day", String(result.dayRemaining ?? 0));
    }
    if (result.allowed) return true;
    reply.header("retry-after", String(result.retryAfterSec));
    reply.code(429).send({
      error:
        result.exceeded === "day"
          ? `Daily request limit exceeded (${limits.perDay}/day).`
          : `Request rate limit exceeded (${limits.perMinute}/min).`,
    });
    return false;
  }

  /**
   * Debit `amount` credits from the key, enforcing both the balance and the
   * per-key safe-spend limits. The limit checks, the balance decrement and the
   * spend-ledger row all run in one transaction with the key row locked
   * (`FOR UPDATE`), so concurrent requests for the same key serialize and can
   * neither overspend a limit nor run a job they did not pay for.
   */
  async function charge(key: DbApiKey, amount: number): Promise<boolean> {
    if (amount <= 0) return true;
    return withTransaction(async (tx) => {
      // Lock the key row and read its current limits/credits in one shot; a
      // concurrent charge for the same key blocks here until we commit.
      const locked = await tx.query<{
        credits: number;
        safe_spend_limit: number | null;
        safe_spend_hourly: number | null;
        safe_spend_daily: number | null;
        safe_spend_total: number | null;
      }>(
        `SELECT credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total
         FROM api_keys WHERE id = $1 FOR UPDATE`,
        [key.id],
      );
      const row = locked.rows[0];
      if (!row) return false;

      const effectiveTotalLimit = row.safe_spend_total ?? row.safe_spend_limit ?? null;

      if (effectiveTotalLimit != null) {
        const spent = await tx.query<{ sum: string }>(
          "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1",
          [key.id],
        );
        if (Number(spent.rows[0]?.sum ?? 0) + amount > effectiveTotalLimit) return false;
      }

      if (row.safe_spend_hourly != null) {
        const spent = await tx.query<{ sum: string }>(
          "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND created_at >= now() - interval '1 hour'",
          [key.id],
        );
        if (Number(spent.rows[0]?.sum ?? 0) + amount > row.safe_spend_hourly) return false;
      }

      if (row.safe_spend_daily != null) {
        const spent = await tx.query<{ sum: string }>(
          "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND created_at >= now() - interval '1 day'",
          [key.id],
        );
        if (Number(spent.rows[0]?.sum ?? 0) + amount > row.safe_spend_daily) return false;
      }

      const updated = await tx.query<{ credits: number }>(
        "UPDATE api_keys SET credits = credits - $1, last_used_at = now() WHERE id = $2 AND credits >= $1 RETURNING credits",
        [amount, key.id],
      );
      if (updated.rows.length === 0) return false;

      // Ledger row (negative = outflow). A later refund writes a matching
      // positive 'refund' row, so the ledger nets out for failed jobs.
      await tx.query(
        "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'spend', $3)",
        [key.user_id, -amount, `Spend (${amount} credits)`],
      );

      key.credits = updated.rows[0].credits;
      return true;
    });
  }

  async function pickUserKey(userId: string, amount: number): Promise<DbApiKey | null> {
    const rows = await query<DbApiKey>(
      `SELECT id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active
       FROM api_keys WHERE user_id = $1 AND is_active = true AND credits >= $2
       ORDER BY created_at ASC LIMIT 1`,
      [userId, amount],
    );
    return rows[0] ?? null;
  }

  /** Credit cost for an endpoint, read from the `pricing` table (admin-configurable). */
  async function costFor(endpoint: string): Promise<number> {
    const row = await queryOne<{ credit_cost: number }>(
      "SELECT credit_cost FROM pricing WHERE endpoint = $1 AND model IS NULL LIMIT 1",
      [endpoint],
    );
    return row?.credit_cost ?? DEFAULT_COSTS[endpoint] ?? 9;
  }

  /** Routing policy for a model: admin override from `routing_rules`, else defaults. */
  async function routingPolicy(model?: string): Promise<"prefer_free" | "paid_only" | "any"> {
    if (model) {
      const row = await queryOne<{ policy: string }>(
        "SELECT policy FROM routing_rules WHERE model = $1 LIMIT 1",
        [model],
      );
      if (row?.policy === "prefer_free" || row?.policy === "paid_only" || row?.policy === "any") {
        return row.policy;
      }
    }
    if (model === "chirp-auk-turbo") return "prefer_free";
    if (model === "chirp-crow" || model === "chirp-fenix") return "paid_only";
    return "any";
  }

  function requireAuth(req: FastifyRequest, reply: FastifyReply): UserPayload | null {
    const cookieToken = readCookie(req.headers.cookie, SESSION_COOKIE);
    const auth = req.headers.authorization ?? "";
    const bearerToken = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    const token = cookieToken ?? bearerToken;
    const user = token ? verifyToken(token) : null;
    if (!user) {
      reply.code(401).send({ error: "Unauthorized." });
      return null;
    }
    // Cookie-authenticated requests get an extra cross-origin check on top of
    // the cookie's SameSite=Lax. A browser only attaches `Origin` to a
    // same-origin request when the method is unsafe (POST/PUT/PATCH/DELETE) or
    // when the request is cross-origin, so a present-but-mismatched Origin
    // always means another site drove the call. Checking regardless of method
    // also protects state-changing work reachable over GET (e.g. the
    // credit-spending /me/download routes) that a method-only check would let
    // through.
    if (cookieToken && !bearerToken) {
      const origin = req.headers.origin;
      if (origin && !config.frontendOrigins.includes(origin.replace(/\/$/, ""))) {
        reply.code(403).send({ error: "Cross-origin request blocked." });
        return null;
      }
    }
    return user;
  }

  async function requireAdmin(req: FastifyRequest, reply: FastifyReply): Promise<UserPayload | null> {
    const user = requireAuth(req, reply);
    if (!user) return null;
    if (user.role !== "admin") {
      reply.code(403).send({ error: "Admin only." });
      return null;
    }
    return user;
  }

  // Append-only trail of privileged actions. Best-effort: an audit write must
  // never break (or roll back) the action it records, so failures are logged and
  // swallowed. `actor_email` is a snapshot so the entry survives a user rename;
  // `actor_id` is ON DELETE SET NULL so it also survives a user deletion.
  async function recordAudit(args: {
    actor: UserPayload;
    action: string;
    targetType?: string;
    targetId?: string | null;
    details?: Record<string, unknown> | null;
    req: FastifyRequest;
  }): Promise<void> {
    try {
      await query(
        `INSERT INTO audit_logs (actor_id, actor_email, action, target_type, target_id, details, ip)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [
          args.actor.id,
          args.actor.email,
          args.action,
          args.targetType ?? null,
          args.targetId ?? null,
          args.details ? JSON.stringify(args.details) : null,
          args.req.ip ?? null,
        ],
      );
    } catch (err) {
      app.log.warn({ err, action: args.action }, "failed to record audit log");
    }
  }

  async function recordUsage(args: {
    userId: string;
    apiKeyId: string;
    endpoint: string;
    model?: string;
    prompt?: string;
    status: string;
    credits: number;
    taskId: string;
    result?: unknown;
  }): Promise<void> {
    await query(
      `INSERT INTO usage_logs (user_id, api_key_id, endpoint, model, prompt, status, credits_consumed, task_id, result_json)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [
        args.userId,
        args.apiKeyId,
        args.endpoint,
        args.model ?? null,
        args.prompt ?? null,
        args.status,
        args.credits,
        args.taskId,
        args.result ? JSON.stringify(args.result) : null,
      ],
    );
  }

  function newJob(type: Job["type"], callbackUrl?: string): Job {
    const job: Job = {
      id: randomUUID(),
      type,
      status: "pending",
      callbackUrl,
      createdAt: Date.now(),
    };
    if (!job.createdAt) job.createdAt = Date.now();
    if (jobs.size >= MAX_JOBS_IN_MEMORY) evictJobs();
    jobs.set(job.id, job);
    return job;
  }

  function slug(s: string): string {
    return s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "clip";
  }

  function meDetailRoute(
    path: string,
    type: Job["type"],
    getter: (c: SunoClient, id: string) => Promise<unknown>,
  ) {
    app.get(path, async (req, reply) => {
      const u = requireAuth(req, reply);
      if (!u) return;
      const { id } = req.params as { id: string };
      if (!id) return reply.code(400).send({ error: "id is required." });
      let cost = 0;
      try {
        cost = await costFor(type);
      } catch {
        cost = 0;
      }
      const key = cost > 0 ? await pickUserKey(u.id, cost) : null;
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      if (key && cost > 0) {
        if (!(await charge(key, cost))) {
          return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
        }
      }
      const job = newJob(type);
      job.userId = u.id;
      if (key) job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      void runResultJobWithRetry(job, (client) => getter(client, id));
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  async function notify(job: Job): Promise<void> {
    if (!job.callbackUrl) return;
    const blocked = await checkCallbackUrl(job.callbackUrl);
    if (blocked) {
      console.error(`Blocked callback for job ${job.id}: ${blocked}`);
      return;
    }
    try {
      await fetch(job.callbackUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          job_id: job.id,
          type: job.type,
          status: job.status,
          account_id: job.accountId,
          result: job.result,
          error: job.error,
        }),
        // Never follow redirects: a public URL could otherwise bounce the
        // request into an internal address and bypass the SSRF guard above.
        redirect: "manual",
      });
    } catch {
      // callback failures are non-fatal
    }
  }

  // --- background workers --------------------------------------------------
  /** Best-effort job persistence: a storage failure must not break job execution. */
  async function persistJob(job: Job): Promise<void> {
    try {
      await saveJob(job);
    } catch (e) {
      console.error(`Failed to persist job ${job.id}:`, e);
    }
  }

  async function finalizeJob(job: Job): Promise<void> {
    job.finishedAt = Date.now();
    const refundable = job.status === "error" && (job.credits ?? 0) > 0;
    if (job.userId && job.apiKeyId) {
      await recordUsage({
        userId: job.userId,
        apiKeyId: job.apiKeyId,
        endpoint: job.endpoint ?? job.type,
        model: job.model,
        prompt: job.prompt,
        status: job.status,
        // Failed jobs are refunded below, so they must not count as spend.
        credits: refundable ? 0 : (job.credits ?? 0),
        taskId: job.id,
        result: job.result,
      });
    }
    // Persist the terminal state before refunding: if the process dies in
    // between, an already-terminal job is never picked up by boot recovery,
    // so a refund can be missed but never issued twice.
    await persistJob(job);
    if (refundable) {
      try {
        await refundJobCredits(job, "Job failed");
      } catch (e) {
        console.error(`Failed to refund job ${job.id}:`, e);
      }
    }
    await notify(job);
  }

  const RETRYABLE_ERROR = /captcha|timeout|timed out|rate limit|5\d{2}|no healthy|No healthy/i;

  interface RetryOptions {
    model?: string;
    policy?: RoutingPolicy;
  }

  async function executeClipJob(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<import("./client.js").Clip[]>,
    options?: RetryOptions,
  ): Promise<void> {
    await persistJob(job);
    const excludeAttemptedIds: string[] = [];
    const maxAttempts = Math.min(3, pool.size);
    const errors: string[] = [];

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      let client: SunoClient;
      try {
        client = await pool.pickExcept(excludeAttemptedIds, options?.model, options?.policy ?? "any");
      } catch (e) {
        errors.push(e instanceof Error ? e.message : String(e));
        break;
      }
      excludeAttemptedIds.push(client.account.id);

      job.status = "running";
      job.accountId = client.account.id;
      try {
        const clips = await submitFactory(client);
        const ids = clips.map((c) => c.id);
        let done = clips;
        if (ids.length) done = await client.pollClips(ids);
        job.result = { clips: done };
        job.status = "complete";
        await finalizeJob(job);
        return;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        errors.push(msg);
        if (!RETRYABLE_ERROR.test(msg)) {
          job.status = "error";
          job.error = msg;
          await finalizeJob(job);
          return;
        }
      }
    }

    job.status = "error";
    job.error = `All ${errors.length} attempts failed: ${errors.join("; ")}`;
    await finalizeJob(job);
  }

  /** Run an operation that returns a raw result (not clips to poll), with cross-account retry. */
  async function executeResultJob(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<unknown>,
    options?: RetryOptions,
  ): Promise<void> {
    await persistJob(job);
    const excludeAttemptedIds: string[] = [];
    const maxAttempts = Math.min(3, pool.size);
    const errors: string[] = [];

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      let client: SunoClient;
      try {
        client = await pool.pickExcept(excludeAttemptedIds, options?.model, options?.policy ?? "any");
      } catch (e) {
        errors.push(e instanceof Error ? e.message : String(e));
        break;
      }
      excludeAttemptedIds.push(client.account.id);

      job.status = "running";
      job.accountId = client.account.id;
      try {
        job.result = await submitFactory(client);
        job.status = "complete";
        await finalizeJob(job);
        return;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        errors.push(msg);
        if (!RETRYABLE_ERROR.test(msg)) {
          job.status = "error";
          job.error = msg;
          await finalizeJob(job);
          return;
        }
      }
    }

    job.status = "error";
    job.error = `All ${errors.length} attempts failed: ${errors.join("; ")}`;
    await finalizeJob(job);
  }

  // --- detached worker lifecycle -------------------------------------------
  // Every job runs detached (`void runClipJobWithRetry(...)`), so nothing awaits
  // its promise. Track in-flight workers here so (a) a rejected worker can never
  // surface as an unhandled rejection that crashes the process, and (b) graceful
  // shutdown can briefly wait for in-flight work to reach its terminal state.
  let inflightWorkers = 0;
  const drainWaiters: Array<() => void> = [];
  function endWorker(): void {
    inflightWorkers = Math.max(0, inflightWorkers - 1);
    if (inflightWorkers === 0) {
      while (drainWaiters.length) drainWaiters.pop()?.();
    }
  }
  /** Resolve once every in-flight worker has settled, or after `timeoutMs`. */
  async function drainWorkers(timeoutMs: number): Promise<void> {
    if (inflightWorkers === 0) return;
    await Promise.race([
      new Promise<void>((resolve) => drainWaiters.push(resolve)),
      new Promise<void>((resolve) => {
        setTimeout(resolve, timeoutMs).unref();
      }),
    ]);
  }
  /** Record an unexpected worker rejection as a failed job; persistence is best-effort. */
  async function failJob(job: Job, e: unknown): Promise<void> {
    console.error(`Background worker for job ${job.id} failed:`, e);
    if (job.status !== "complete") {
      job.status = "error";
      if (!job.error) job.error = e instanceof Error ? e.message : String(e);
      await persistJob(job);
    }
  }
  function runDetached(job: Job, run: () => Promise<void>): void {
    inflightWorkers += 1;
    void run()
      .catch((e) => failJob(job, e))
      .finally(() => endWorker());
  }

  /** Run a clip-producing job in the background. Never rejects. */
  function runClipJobWithRetry(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<import("./client.js").Clip[]>,
    options?: RetryOptions,
  ): void {
    runDetached(job, () => executeClipJob(job, submitFactory, options));
  }

  /** Run a result-producing job in the background. Never rejects. */
  function runResultJobWithRetry(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<unknown>,
    options?: RetryOptions,
  ): void {
    runDetached(job, () => executeResultJob(job, submitFactory, options));
  }

  // Graceful shutdown: wait (bounded) for detached workers so an in-flight
  // generation can persist its terminal state before the process exits.
  const DRAIN_TIMEOUT_MS = Number(process.env.SHUTDOWN_DRAIN_MS) || 25_000;
  app.addHook("onClose", async () => {
    await drainWorkers(DRAIN_TIMEOUT_MS);
  });

  function processMusicSubmit(params: Record<string, unknown>) {
    const gen = {
      gptDescriptionPrompt: (params.gpt_description_prompt ?? params.prompt) as string | undefined,
      prompt: params.prompt as string | undefined,
      tags: params.tags as string | undefined,
      title: params.title as string | undefined,
      negativeTags: params.negative_tags as string | undefined,
      instrumental: Boolean(params.instrumental ?? params.make_instrumental),
      model: params.model as string | undefined,
      captchaToken: params.captcha_token as string | undefined,
      personaId: (params.persona_id ?? params.personaId) as string | undefined,
      personaModel: (params.persona_model ?? params.personaModel) as string | undefined,
      duration:
        params.duration != null
          ? Number(params.duration)
          : undefined,
      vocalGender: (params.vocal_gender ?? params.vocalGender) as string | undefined,
      styleWeight:
        params.style_weight != null
          ? Number(params.style_weight)
          : params.styleWeight != null
            ? Number(params.styleWeight)
            : undefined,
      weirdnessConstraint:
        params.weirdness_constraint != null
          ? Number(params.weirdness_constraint)
          : params.weirdnessConstraint != null
            ? Number(params.weirdnessConstraint)
            : undefined,
      audioWeight:
        params.audio_weight != null
          ? Number(params.audio_weight)
          : params.audioWeight != null
            ? Number(params.audioWeight)
            : undefined,
    };
    return (client: SunoClient) => client.generateMusic(gen);
  }

  function processSoundsSubmit(params: Record<string, unknown>) {
    const p = {
      prompt: (params.prompt as string) ?? "",
      model: params.model as string | undefined,
      loop: Boolean(params.loop),
      tempo: params.tempo ? Number(params.tempo) : null,
      key: (params.key as string) || null,
    };
    return (client: SunoClient) => client.generateSounds(p);
  }

  function processLyricsSubmit(prompt: string) {
    return async (client: SunoClient): Promise<unknown> => {
      const id = await client.generateLyrics(prompt);
      let result: Record<string, unknown> = {};
      for (let i = 0; i < 60; i++) {
        result = await client.getLyrics(id);
        if (result.status === "complete" || result.status === "error") break;
        await new Promise((r) => setTimeout(r, 3_000));
      }
      return result;
    };
  }

  function processClipOpSubmit(submit: () => Promise<unknown>, poll = true) {
    if (poll) return submit as (client: SunoClient) => Promise<import("./client.js").Clip[]>;
    return submit as (client: SunoClient) => Promise<unknown>;
  }

  // --- routes --------------------------------------------------------------
  app.get("/health", async () => ({
    ok: true,
    accounts: pool.size,
    jobs: jobs.size,
  }));

  /**
   * Admin-only JSON snapshot for ops. This deployment has no Prometheus/scrape
   * stack, so counters are served as JSON behind the admin session rather than
   * exposing an unauthenticated metrics surface.
   */
  app.get("/metrics", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const byStatus: Record<string, number> = {};
    for (const job of jobs.values()) {
      byStatus[job.status] = (byStatus[job.status] ?? 0) + 1;
    }
    return {
      uptimeSeconds: Math.round(process.uptime()),
      requests: { ...requestCounters },
      jobs: { total: jobs.size, byStatus },
      accounts: pool.size,
    };
  });

  // --- auth routes ---------------------------------------------------------
  // Self-service registration disabled — Google sign-in is the only user onboarding path.
  // Admins are seeded directly into the `users` table via scripts/seed.ts or SQL.
  // Both credential endpoints get a tighter budget than the global limit to blunt
  // password/credential stuffing.
  const authRateLimit = {
    rateLimit: { max: config.rateLimit.authMax, timeWindow: config.rateLimit.windowMs },
  };
  app.post("/auth/register", { config: authRateLimit }, async (_req, reply) => {
    return reply.code(405).send({ error: "Self-registration is disabled. Please sign in with Google." });
  });

  // Email/password login is ADMIN-ONLY.
  // Non-admin users (created via Google sign-in) have password_hash=NULL and cannot use this route.
  // Defense-in-depth: even if a non-admin somehow had a password set, they are explicitly denied here.
  app.post("/auth/login", { config: authRateLimit }, async (req, reply) => {
    const { email, password } = (req.body ?? {}) as { email?: string; password?: string };
    if (!email || !password) return reply.code(400).send({ error: "email and password are required." });
    const user = await queryOne<DbUser>("SELECT * FROM users WHERE email = $1", [email.toLowerCase()]);
    if (!user || !user.password_hash || !(await verifyPassword(password, user.password_hash))) {
      return reply.code(401).send({ error: "Invalid email or password." });
    }
    if (user.role !== "admin") {
      return reply.code(403).send({ error: "This login method is restricted to administrators." });
    }
    if (user.status !== "active") return reply.code(403).send({ error: "Account suspended." });
    const token = signToken({ id: user.id, email: user.email, role: user.role });
    // Also set the browser session cookie; the token in the body stays for
    // non-browser/API clients.
    reply.header("set-cookie", serializeSessionCookie(token, config.sessionCookieSecure));
    return {
      token,
      user: { id: user.id, email: user.email, role: user.role, name: user.name },
    };
  });

  // Clear the httpOnly session cookie server-side. Idempotent — works with no
  // session and always returns 200 so the client can drop local state too.
  app.post("/auth/logout", async (_req, reply) => {
    reply.header("set-cookie", serializeClearedSessionCookie(config.sessionCookieSecure));
    return { ok: true };
  });

  app.get("/auth/me", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    return queryOne<DbUser>("SELECT id, email, role, name, status FROM users WHERE id = $1", [u.id]);
  });

  // --- Google OAuth (for frontend) -----------------------------------------
  // Step 1: Fetch the URL to redirect user to for Google sign-in consent
  //         Pass ?redirect_uri=http://localhost:4002/auth/callback for admin,
  //         or omit for user-facing default (4001).
  app.get("/auth/google/url", (req, reply) => {
    const { redirect_uri } = (req.query ?? {}) as { redirect_uri?: string };
    const { client, redirectUri } = resolveGoogleClient(redirect_uri);
    if (!client) {
      return reply.code(503).send({
        error:
          "Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables and restart.",
      });
    }
    const state = signOAuthState(redirectUri);
    const url = client.generateAuthUrl({
      access_type: "offline",
      scope: ["openid", "email", "profile"],
      prompt: "select_account",
      state,
    });
    return { url, state };
  });

  // Step 2: Exchange the code Google returned → id_token → upsert user → return session token
  //         Body: { code, state } — state must be the signed value from Step 1.
  app.post("/auth/google/callback", async (req, reply) => {
    const { code, state } = (req.body ?? {}) as { code?: string; state?: string };
    // The redirect_uri is taken from the signed state (never from the request
    // body) so a forged callback cannot redirect the code exchange elsewhere.
    const redirectUri = state ? verifyOAuthState(state) : null;
    if (!redirectUri) {
      return reply.code(400).send({ error: "Invalid or expired sign-in state. Please try again." });
    }
    const { client } = resolveGoogleClient(redirectUri);
    if (!client) {
      return reply.code(503).send({ error: "Google sign-in is not configured." });
    }
    if (!code) return reply.code(400).send({ error: "code is required." });
    try {
      const { tokens } = await client.getToken(code);
      const idToken = tokens.id_token;
      if (!idToken) return reply.code(400).send({ error: "Google did not return an id_token." });
      const ticket = await client.verifyIdToken({ idToken, audience: GOOGLE_CLIENT_ID });
      const payload = ticket.getPayload();
      if (!payload || !payload.email || !payload.sub) {
        return reply.code(400).send({ error: "Google did not return a valid profile." });
      }
      // Only trust an email Google has verified — the email is used below to
      // merge/link an existing account, so an unverified address could
      // otherwise be used to take over that account.
      if (payload.email_verified !== true) {
        return reply.code(403).send({ error: "Your Google email address is not verified." });
      }
      const googleId = payload.sub;
      const email = payload.email.toLowerCase();
      const name = (payload.name as string | undefined) ?? null;

      // Find by google_id, else by email (merge existing account)
      let user = await queryOne<DbUser>("SELECT * FROM users WHERE google_id = $1", [googleId]);
      if (!user) {
        const byEmail = await queryOne<DbUser>("SELECT * FROM users WHERE email = $1", [email]);
        if (byEmail) {
          // Link existing account to Google (preserves role e.g. admin)
          const rows = await query<DbUser>(
            "UPDATE users SET google_id = $1, name = COALESCE($2, name) WHERE id = $3 RETURNING *",
            [googleId, name, byEmail.id],
          );
          user = rows[0];
        } else {
          // Create new Google-only user (no password, role defaults to "user")
          const rows = await query<DbUser>(
            "INSERT INTO users (email, password_hash, google_id, name) VALUES ($1, NULL, $2, $3) RETURNING *",
            [email, googleId, name],
          );
          user = rows[0];
        }
      }
      if (!user) return reply.code(500).send({ error: "Failed to create or find user." });
      if (user.status !== "active") return reply.code(403).send({ error: "Account suspended." });

      const token = signToken({ id: user.id, email: user.email, role: user.role });
      reply.header("set-cookie", serializeSessionCookie(token, config.sessionCookieSecure));
      return reply.code(200).send({
        token,
        user: { id: user.id, email: user.email, role: user.role, name: user.name },
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return reply.code(400).send({ error: `Google auth failed: ${msg}` });
    }
  });

  // --- user API key management --------------------------------------------
  app.get("/me/keys", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    return query<DbApiKey>(
      "SELECT id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active, created_at, last_used_at FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC",
      [u.id],
    );
  });

  app.post("/me/keys", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { name } = (req.body ?? {}) as { name?: string };
    const raw = `sk_${randomUUID().replace(/-/g, "")}`;
    await query(
      "INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits) VALUES ($1, $2, $3, $4, 0)",
      [u.id, name ?? "default", hashKey(raw), raw.slice(0, 8)],
    );
    return reply.code(201).send({ key: raw, name: name ?? "default" });
  });

  app.put("/me/keys/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    const body = (req.body ?? {}) as {
      name?: string;
      safe_spend_limit?: number | null;
      safe_spend_hourly?: number | null;
      safe_spend_daily?: number | null;
      safe_spend_total?: number | null;
      ip_whitelist?: string[];
    };
    const key = await queryOne<{ id: string }>("SELECT id FROM api_keys WHERE id = $1 AND user_id = $2", [id, u.id]);
    if (!key) return reply.code(404).send({ error: "Key not found." });
    const sets: string[] = [];
    const vals: unknown[] = [];
    if (body.name !== undefined) { sets.push(`name = $${sets.length + 1}`); vals.push(body.name); }
    if (body.safe_spend_limit !== undefined) { sets.push(`safe_spend_limit = $${sets.length + 1}`); vals.push(body.safe_spend_limit); }
    if (body.safe_spend_hourly !== undefined) { sets.push(`safe_spend_hourly = $${sets.length + 1}`); vals.push(body.safe_spend_hourly); }
    if (body.safe_spend_daily !== undefined) { sets.push(`safe_spend_daily = $${sets.length + 1}`); vals.push(body.safe_spend_daily); }
    if (body.safe_spend_total !== undefined) { sets.push(`safe_spend_total = $${sets.length + 1}`); vals.push(body.safe_spend_total); }
    if (body.ip_whitelist !== undefined) { sets.push(`ip_whitelist = $${sets.length + 1}`); vals.push(body.ip_whitelist); }
    if (sets.length) {
      vals.push(id);
      await query(`UPDATE api_keys SET ${sets.join(", ")} WHERE id = $${sets.length + 1}`, vals);
    }
    return { ok: true };
  });

  app.post("/me/generate", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const type = body.type === "lyrics" ? "lyrics" : body.type === "sounds" ? "sounds" : "music";

    if (type === "lyrics" && !body.prompt) {
      return reply.code(400).send({ error: "prompt is required." });
    }
    if (type === "music" && !body.gpt_description_prompt && !body.prompt) {
      return reply.code(400).send({ error: "gpt_description_prompt or prompt is required." });
    }
    if (type === "sounds" && !body.prompt) {
      return reply.code(400).send({ error: "prompt is required." });
    }

    const cost = await costFor(type);
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }

    if (type === "lyrics") {
      const prompt = body.prompt as string;
      const job = newJob("lyrics");
      job.userId = u.id;
      job.apiKeyId = key.id;
      job.endpoint = "lyrics";
      job.prompt = prompt;
      job.credits = cost;
      void runResultJobWithRetry(job, processLyricsSubmit(prompt));
      return reply.code(202).send({ job_id: job.id, status: job.status });
    }

    if (type === "sounds") {
      const job = newJob("sounds");
      job.userId = u.id;
      job.apiKeyId = key.id;
      job.endpoint = "sounds";
      job.model = (body.model as string) || undefined;
      job.prompt = body.prompt as string;
      job.credits = cost;
      const spolicy = await routingPolicy((body.model as string) || undefined);
      void runClipJobWithRetry(job, processSoundsSubmit(body), {
        model: (body.model as string) || undefined,
        policy: spolicy,
      });
      return reply.code(202).send({ job_id: job.id, status: job.status });
    }

    const job = newJob("music");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "music";
    job.model = (body.model as string) || undefined;
    job.prompt = (body.gpt_description_prompt ?? body.prompt) as string;
    job.credits = cost;
    const mpolicy = await routingPolicy((body.model as string) || undefined);
    void runClipJobWithRetry(job, processMusicSubmit(body), {
      model: (body.model as string) || undefined,
      policy: mpolicy,
    });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // ---------- /me/* playground routes (user auth, not API key) ----------

  app.post("/me/recovery", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.sunoTaskId || body.clip_id || body.task_id;
    if (!clipId || typeof clipId !== "string") {
      return reply.code(400).send({ error: "sunoTaskId is required." });
    }
    const cost = await costFor("recovery_audio");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("recovery_audio", (body.callBackUrl || body.callback_url) as string | undefined);
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "recovery_audio";
    job.credits = cost;
    const prompt = (body.prompt as string) || "";
    void runClipJobWithRetry(job, (client) => client.generateRecoveryAudio(clipId, prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/stems", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (body.taskId || body.audioId || body.clip_id || body.task_id) as string | undefined;
    if (!clipId) return reply.code(400).send({ error: "taskId is required." });
    const cost = await costFor("stems");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const separationType = (body.separationType || "vocal") as "vocal" | "stems" | "advanced" | string;
    const jobType: Job["type"] =
      separationType === "stems" || separationType === "advanced" ? "stems" : "stems";
    const job = newJob(jobType);
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "stems";
    job.credits = cost;
    job.prompt = separationType === "advanced" ? (body.trackName as string) || "stem" : undefined;
    void runClipJobWithRetry(job, (client) => client.stems(clipId));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/replace-section", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (body.taskId || body.clip_id || body.task_id) as string | undefined;
    const lyrics = (body.fullLyrics || body.lyrics) as string | undefined;
    const startS = Number(body.infillStartS ?? body.start_s ?? body.startS);
    const endS = Number(body.infillEndS ?? body.end_s ?? body.endS);
    if (!clipId || !lyrics || !Number.isFinite(startS) || !Number.isFinite(endS) || endS - startS < 10) {
      return reply.code(400).send({
        error:
          "taskId, fullLyrics, infillStartS, infillEndS are required (duration must be at least 10 seconds).",
      });
    }
    const cost = await costFor("replace_section");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("replace_section");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "replace_section";
    job.credits = cost;
    job.prompt = lyrics;
    void runClipJobWithRetry(job, (client) =>
      client.replaceSection(clipId, { startS, endS, lyrics }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/persona-create", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (body.taskId || body.clip_id || body.clipId) as string | undefined;
    const name = (body.voiceName || body.name) as string | undefined;
    if (!clipId || !name) return reply.code(400).send({ error: "taskId and voiceName are required." });
    const styles = ((body.style as string) || undefined);
    const cost = await costFor("persona");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("persona");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "persona";
    job.credits = cost;
    job.prompt = name;
    void runResultJobWithRetry(
      job,
      (client) => client.createPersona(clipId, name, styles),
      { policy: "paid_only" },
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/voice-generate", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (body.taskId || body.clip_id || body.clipId) as string | undefined;
    const name = (body.voiceName || body.name) as string | undefined;
    if (!clipId || !name) return reply.code(400).send({ error: "taskId and voiceName are required." });
    const styles = (body.style as string) || undefined;
    const cost = await costFor("voice_generate");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_generate");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_generate";
    job.credits = cost;
    job.prompt = name;
    void runResultJobWithRetry(
      job,
      (client) => client.voiceGenerate({ clipId, name, styles }),
      { policy: "paid_only" },
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/voice-validate", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const uploadId = (body.upload_id || body.uploadId) as string | undefined;
    const audioUrl = (body.audio_url || body.audioUrl || body.validationAudioUrl) as string | undefined;
    if (!uploadId && !audioUrl) {
      return reply.code(400).send({ error: "upload_id or audio_url is required." });
    }
    const cost = await costFor("voice_validate");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_validate");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_validate";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceValidate({ uploadId, audioUrl }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/voice-phrase", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const prompt = (body.prompt as string) || "";
    const cost = await costFor("voice_phrase");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_phrase");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_phrase";
    job.credits = cost;
    job.prompt = prompt;
    void runResultJobWithRetry(job, (client) => client.voicePhrase(prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/voice-record", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const extension = (body.extension as string) || "wav";
    const cost = await costFor("voice_record");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_record");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_record";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceRecord(extension));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  function normalizeClips(raw: unknown) {
    if (!raw || typeof raw !== "object") return [] as any[];
    const o = raw as any;
    const list: any[] = Array.isArray(o.clips) ? o.clips : (Array.isArray(o) ? o : []);
    return list.map((c) => {
      if (!c || typeof c !== "object") return c;
      const clip: any = { ...c };
      if (!clip.audio_url || /forbidden|undefined|null/i.test(String(clip.audio_url))) {
        const mu = Array.isArray(clip.media_urls) ? clip.media_urls : [];
        const progressive = mu.find((m: any) => m && m.delivery === "progressive") ?? mu[0];
        if (progressive?.url) clip.audio_url = progressive.url;
      }
      if (clip.media_urls) clip.media_urls = clip.media_urls;
      if (clip.metadata && !clip.duration) clip.duration = (clip.metadata as any).duration ?? undefined;
      return clip;
    });
  }
  app.get("/me/task/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    const job = jobs.get(id);
    if (job && job.userId === u.id) {
      const clips = normalizeClips(job.result);
      return {
        job_id: job.id,
        task_id: job.id,
        type: job.type,
        endpoint: job.endpoint,
        status: job.status,
        credits: job.credits,
        result: job.result,
        clips,
        error: job.error,
      };
    }
    const row = await queryOne<{
      user_id: string;
      status: string;
      result_json: unknown;
      task_id: string;
      endpoint: string;
      credits_consumed: number;
      model: string | null;
      prompt: string | null;
    }>(
      "SELECT user_id, status, result_json, task_id, endpoint, credits_consumed, model, prompt FROM usage_logs WHERE task_id = $1 LIMIT 1",
      [id],
    );
    if (!row || row.user_id !== u.id) {
      return reply.code(404).send({ error: "Task not found." });
    }
    const clips = normalizeClips(row.result_json);
    return {
      job_id: row.task_id,
      task_id: row.task_id,
      type: row.endpoint,
      endpoint: row.endpoint,
      status: row.status,
      credits: row.credits_consumed,
      model: row.model,
      prompt: row.prompt,
      result: row.result_json,
      clips,
      error: row.status === "error" || row.status === "failed"
        ? (typeof row.result_json === "object" && row.result_json && "error" in (row.result_json as any) ? (row.result_json as any).error : "Task failed.")
        : undefined,
    };
  });

  app.get("/me/usage", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const daysParam = Number((req.query as { days?: string })?.days ?? 30);
    const days = Math.min(90, Math.max(7, daysParam || 30));
    const total = await queryOne<{ count: string }>(
      "SELECT count(*)::text AS count FROM usage_logs WHERE user_id = $1 AND created_at > now() - interval '24 hours'",
      [u.id],
    );
    const success = await queryOne<{ count: string }>(
      "SELECT count(*)::text AS count FROM usage_logs WHERE user_id = $1 AND status = 'complete' AND created_at > now() - interval '24 hours'",
      [u.id],
    );
    const failed = await queryOne<{ count: string }>(
      "SELECT count(*)::text AS count FROM usage_logs WHERE user_id = $1 AND status = 'error' AND created_at > now() - interval '24 hours'",
      [u.id],
    );
    const series = await query<{ day: string; count: string; credits: string }>(
      `SELECT to_char(created_at, 'YYYY-MM-DD') AS day, count(*)::text AS count, COALESCE(sum(credits_consumed),0)::text AS credits FROM usage_logs WHERE user_id = $1 AND created_at > now() - interval '${days} days' GROUP BY day ORDER BY day`,
      [u.id],
    );
    const totalCreditsRow = await queryOne<{ sum: string }>(
      `SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE user_id = $1 AND created_at > now() - interval '${days} days'`,
      [u.id],
    );
    const creditsPerUsd = await creditsPerUsdRate();
    const totalCredits = Number(totalCreditsRow?.sum ?? 0);
    const totalSpend = totalCredits / creditsPerUsd;
    return {
      total_24h: Number(total?.count ?? 0),
      success_24h: Number(success?.count ?? 0),
      failed_24h: Number(failed?.count ?? 0),
      total_credits: totalCredits,
      total_spend: totalSpend,
      credits_per_usd: creditsPerUsd,
      series: series.map((s) => ({
        day: s.day,
        count: Number(s.count),
        credits: Number(s.credits),
        spend: Number(s.credits) / creditsPerUsd,
      })),
    };
  });

  app.get("/me/logs", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const q = req.query as { task_id?: string; endpoint?: string; limit?: string };
    const clauses: string[] = ["user_id = $1"];
    const params: unknown[] = [u.id];
    if (q.task_id && typeof q.task_id === "string" && q.task_id.trim()) {
      params.push(`%${q.task_id.trim()}%`);
      clauses.push(`(CAST(task_id AS text) ILIKE $${params.length} OR CAST(id AS text) ILIKE $${params.length})`);
    }
    if (q.endpoint && typeof q.endpoint === "string" && q.endpoint.trim()) {
      const patterns = q.endpoint.split(",").map((p) => p.trim()).filter(Boolean);
      if (patterns.length > 0) {
        const orGroup: string[] = [];
        for (const p of patterns) {
          params.push(`%${p}%`);
          orGroup.push(`endpoint ILIKE $${params.length}`);
        }
        clauses.push(`(${orGroup.join(" OR ")})`);
      }
    }
    const limitRaw = Number(q.limit ?? 0) || 0;
    const limit = limitRaw > 0 ? Math.min(limitRaw, 500) : 100;
    const where = clauses.length > 0 ? `WHERE ${clauses.join(" AND ")}` : "";
    const hydrate = (rows: Record<string, unknown>[]) => rows.map((r) => {
      const clips = normalizeClips(r.result_json);
      return { ...r, clips };
    });
    try {
      const rows = await query<Record<string, unknown>>(
        `SELECT id, endpoint, model, prompt, status, credits_consumed, task_id, result_json, created_at FROM usage_logs ${where} ORDER BY created_at DESC LIMIT ${limit}`,
        params,
      );
      return hydrate(rows);
    } catch {
      try {
        const rows = await query<Record<string, unknown>>(
          "SELECT id, endpoint, model, prompt, status, credits_consumed, task_id, result_json, created_at FROM usage_logs WHERE user_id = $1 ORDER BY created_at DESC LIMIT 100",
          [u.id],
        );
        return hydrate(rows);
      } catch {
        return [];
      }
    }
  });

  app.get("/me/usage/by-endpoint", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const daysParam = Number((req.query as { days?: string })?.days ?? 30);
    const days = Math.min(90, Math.max(7, daysParam || 30));
    const pack = await queryOne<{ amount: string; price: string }>(
      "SELECT amount::text, price::text FROM credit_packs WHERE is_active = true ORDER BY amount LIMIT 1",
    );
    const creditsPerUsd = pack && Number(pack.amount) > 0 && Number(pack.price) > 0
      ? Number(pack.amount) / Number(pack.price)
      : 200;
    const rows = await query<{ endpoint: string; count: string; credits: string }>(
      `SELECT endpoint, count(*)::text AS count, COALESCE(sum(credits_consumed),0)::text AS credits FROM usage_logs WHERE user_id = $1 AND created_at > now() - interval '${days} days' GROUP BY endpoint ORDER BY credits DESC NULLS LAST, count DESC`,
      [u.id],
    );
    const endpoints = rows.map((r) => r.endpoint);
    const seriesRows = endpoints.length > 0
      ? await query<{ endpoint: string; day: string; count: string; credits: string }>(
          `SELECT endpoint, to_char(created_at, 'YYYY-MM-DD') AS day, count(*)::text AS count, COALESCE(sum(credits_consumed),0)::text AS credits FROM usage_logs WHERE user_id = $1 AND endpoint = ANY($2::text[]) AND created_at > now() - interval '${days} days' GROUP BY endpoint, day`,
          [u.id, endpoints],
        )
      : [];
    const seriesByEndpoint: Record<string, Array<{ day: string; count: number; credits: number; spend: number }>> = {};
    for (const row of seriesRows) {
      if (!seriesByEndpoint[row.endpoint]) seriesByEndpoint[row.endpoint] = [];
      seriesByEndpoint[row.endpoint].push({
        day: row.day,
        count: Number(row.count),
        credits: Number(row.credits),
        spend: Number(row.credits) / creditsPerUsd,
      });
    }
    for (const ep of Object.keys(seriesByEndpoint)) seriesByEndpoint[ep].sort((a, b) => a.day.localeCompare(b.day));
    return rows.map((r) => ({
      endpoint: r.endpoint,
      count: Number(r.count),
      credits: Number(r.credits),
      spend: Number(r.credits) / creditsPerUsd,
      series: seriesByEndpoint[r.endpoint] ?? [],
    }));
  });

  app.get("/me/billing", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const packs = await query<{ id: string; amount: number; price: string; currency: string }>(
      "SELECT id, amount, price, currency FROM credit_packs WHERE is_active = true ORDER BY amount",
    );
    const credits = await queryOne<{ sum: string }>(
      "SELECT COALESCE(sum(credits),0)::text AS sum FROM api_keys WHERE user_id = $1",
      [u.id],
    );
    return {
      credits: Number(credits?.sum ?? 0),
      packs: packs.map((p) => ({ id: p.id, amount: p.amount, price: Number(p.price), currency: p.currency })),
    };
  });

  // T4: GET /me/download — calls Suno 3-step (authorize → poll /download/clip → ready) → stream real MP3/WAV bytes from S3
  app.get("/me/download", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const q = (req.query ?? {}) as { clip_id?: string; format?: string; force_download?: string };
    const clipId = q.clip_id;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const formatRaw = (q.format as string) || "mp3";
    const format = formatRaw === "wav" ? "wav" : "mp3";
    try {
      try {
        const cost = await costFor("download").catch(() => 0);
        if (cost > 0) {
          const key = await pickUserKey(u.id, cost).catch(() => null);
          if (key) await charge(key, cost).catch(() => {});
        }
      } catch {
        /* ignore charge errors — user can still download if billing fails */
      }
      const client = await pool.pick();
      const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36";
      let primaryBuffer: Buffer | null = null;
      let primaryCt: string | null = null;
      try {
        const { buffer, contentType } = await (client as any).downloadBuffer(clipId, format);
        if (buffer && buffer.length > 400) {
          primaryBuffer = buffer;
          primaryCt = contentType || (format === "wav" ? "audio/wav" : "audio/mpeg");
        }
      } catch {
        primaryBuffer = null;
      }
      const sunoLike = /^[0-9a-fA-F-]{8,}$/.test(clipId);
      const fallbackCandidates: string[] = [];
      if (sunoLike) {
        fallbackCandidates.push(`https://cdn1.suno.ai/${clipId}.${format}`);
        fallbackCandidates.push(`https://d2lwuy8qc234o3.cloudfront.net/1/clip/${clipId}.m4a`);
        fallbackCandidates.push(`https://cdn1.suno.ai/${clipId}.mp3`);
        fallbackCandidates.push(`https://cdn1.suno.ai/${clipId}.wav`);
      }
      const correctCt = format === "wav" ? "audio/wav" : "audio/mpeg";
      if (primaryBuffer) {
        let finalCt = primaryCt;
        if (!finalCt || /text|html|json|xml|plain/.test(finalCt)) finalCt = correctCt;
        reply.header("Content-Type", finalCt);
        reply.header("Content-Length", String(primaryBuffer.length));
        reply.header("Accept-Ranges", "bytes");
        if (q.force_download === "1") {
          const filename = `${slug(clipId).replace(/^-+|-+$/g, "") || "download"}.${format}`;
          const encoded = encodeURIComponent(filename);
          reply.header(
            "Content-Disposition",
            `attachment; filename="${filename}"; filename*=UTF-8''${encoded}`,
          );
        }
        return reply.send(primaryBuffer);
      }
      const fetchOpts = {
        headers: {
          "user-agent": ua,
          accept: format === "wav" ? "audio/wav,audio/*,*/*;q=0.8" : "audio/mpeg,audio/mp3,audio/mp4,audio/*;q=0.9,*/*;q=0.8",
          "accept-language": "en-US,en;q=0.9",
        },
        redirect: "follow" as const,
      };
      let lastResp: Response | null = null;
      for (const cand of fallbackCandidates) {
        try {
          const resp = await fetch(cand, fetchOpts);
          if (resp.ok && resp.body) {
            lastResp = resp;
            let contentType = resp.headers.get("content-type") || "";
            if (!contentType || /text|html|json|xml|plain/.test(contentType)) contentType = correctCt;
            const contentLength = resp.headers.get("content-length");
            const acceptRanges = resp.headers.get("accept-ranges");
            const contentRange = resp.headers.get("content-range");
            reply.header("Content-Type", contentType);
            if (contentLength) reply.header("Content-Length", contentLength);
            if (acceptRanges) reply.header("Accept-Ranges", acceptRanges);
            if (contentRange) reply.header("Content-Range", contentRange);
            if (q.force_download === "1") {
              const filename = `${slug(clipId).replace(/^-+|-+$/g, "") || "download"}.${format}`;
              const encoded = encodeURIComponent(filename);
              reply.header(
                "Content-Disposition",
                `attachment; filename="${filename}"; filename*=UTF-8''${encoded}`,
              );
            }
            return resp.body;
          } else {
            lastResp = resp;
          }
        } catch {
          continue;
        }
      }
      return reply.code(502).send({ error: "Audio not available. The clip may have expired or the media server is unreachable." });
    } catch (e: any) {
      return reply.code(500).send({ error: e?.message ?? "Download failed" });
    }
  });

  // T5: GET /me/jobs/running
  app.get("/me/jobs/running", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const live = Array.from(jobs.values()).filter(
      (j) => j.userId === u.id && ["pending", "running", "streaming"].includes(j.status),
    );
    return live.map((j) => ({
      job_id: j.id,
      type: j.type,
      status: j.status,
      endpoint: j.endpoint,
      prompt: j.prompt,
      model: j.model,
      credits: j.credits,
      created_at: j.createdAt,
    }));
  });

  // T3: POST /me/music and POST /me/sounds aliases for /me/generate
  app.post("/me/music", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    body.type = "music";
    req.body = body;
    return app.inject({
      method: "POST",
      url: "/me/generate",
      headers: req.headers,
      body,
    }).then((r) => reply.code(r.statusCode).send(r.json()));
  });

  app.post("/me/sounds", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    body.type = "sounds";
    req.body = body;
    return app.inject({
      method: "POST",
      url: "/me/generate",
      headers: req.headers,
      body,
    }).then((r) => reply.code(r.statusCode).send(r.json()));
  });

  // T3: Helper for standard /me clip routes
  function meClipRoute(
    path: string,
    type: Job["type"],
    makeSubmit: (
      body: Record<string, unknown>,
    ) => (client: SunoClient) => Promise<import("./client.js").Clip[]>,
    validate?: (body: Record<string, unknown>) => string | null,
    modelField?: string,
  ) {
    app.post(path, async (req, reply) => {
      const u = requireAuth(req, reply);
      if (!u) return;
      const body = (req.body ?? {}) as Record<string, unknown>;
      if (validate) {
        const err = validate(body);
        if (err) return reply.code(400).send({ error: err });
      }
      const cost = await costFor(type);
      const key = await pickUserKey(u.id, cost);
      if (!key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      if (!(await charge(key, cost))) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      const job = newJob(type, (body.callback_url as string) || undefined);
      job.userId = u.id;
      job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      if (body.prompt) job.prompt = body.prompt as string;
      const model = modelField ? (body[modelField] as string) || undefined : undefined;
      if (model) job.model = model;
      const policy = model ? await routingPolicy(model) : "any";
      void runClipJobWithRetry(job, makeSubmit(body), { model, policy });
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  function meResultRoute(
    path: string,
    type: Job["type"],
    makeSubmit: (body: Record<string, unknown>) => (client: SunoClient) => Promise<unknown>,
    validate?: (body: Record<string, unknown>) => string | null,
  ) {
    app.post(path, async (req, reply) => {
      const u = requireAuth(req, reply);
      if (!u) return;
      const body = (req.body ?? {}) as Record<string, unknown>;
      if (validate) {
        const err = validate(body);
        if (err) return reply.code(400).send({ error: err });
      }
      const cost = await costFor(type);
      const key = await pickUserKey(u.id, cost);
      if (!key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      if (!(await charge(key, cost))) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      const job = newJob(type, (body.callback_url as string) || undefined);
      job.userId = u.id;
      job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      if (body.prompt) job.prompt = body.prompt as string;
      void runResultJobWithRetry(job, makeSubmit(body));
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  // POST /me/music/extend
  meClipRoute(
    "/me/music/extend",
    "extend",
    (body) => (client) =>
      client.extendMusic(body.clip_id as string, {
        continueAt: Number(body.continue_at ?? 170),
      }),
    (body) => (body.clip_id ? null : "clip_id is required."),
  );

  // POST /me/music/cover
  meClipRoute(
    "/me/music/cover",
    "cover",
    (body) => (client) => client.coverMusic(body.clip_id as string, body.prompt as string | undefined),
    (body) => (body.clip_id ? null : "clip_id is required."),
  );

  // POST /me/music/remaster
  meClipRoute(
    "/me/music/remaster",
    "remaster",
    (body) => (client) => client.remaster(body.clip_id as string, body.model as string | undefined),
    (body) => (body.clip_id ? null : "clip_id is required."),
    "model",
  );

  // POST /me/music/add-vocals
  meClipRoute(
    "/me/music/add-vocals",
    "add_vocals",
    (body) => (client) => client.addVocals(body.clip_id as string, body.prompt as string),
    (body) => {
      if (!body.clip_id) return "clip_id is required.";
      if (!body.prompt) return "prompt is required for add_vocals.";
      return null;
    },
  );

  // POST /me/music/add-instrumental
  meClipRoute(
    "/me/music/add-instrumental",
    "add_instrumental",
    (body) => (client) => client.addInstrumental(body.clip_id as string, body.prompt as string),
    (body) => {
      if (!body.clip_id) return "clip_id is required.";
      if (!body.prompt) return "prompt is required for add_instrumental.";
      return null;
    },
  );

  // POST /me/music/mashup
  meClipRoute(
    "/me/music/mashup",
    "mashup",
    (body) => (client) =>
      client.mashup(body.clip_ids as string[], body.prompt as string | undefined),
    (body) => {
      const ids = body.clip_ids as string[] | undefined;
      if (!ids || !Array.isArray(ids) || ids.length < 2) {
        return "clip_ids (array of 2+) is required.";
      }
      return null;
    },
  );

  // POST /me/music/cover-image (result job)
  meResultRoute(
    "/me/music/cover-image",
    "cover_image",
    (body) => (client) => client.generateCoverImage(body.clip_id as string, body.prompt as string),
    (body) => {
      if (!body.clip_id || !body.prompt) return "clip_id and prompt are required.";
      return null;
    },
  );

  // POST /me/music/wav (result job - downloadUrl)
  meResultRoute(
    "/me/music/wav",
    "wav",
    (body) => (client) => client.downloadUrl(body.clip_id as string, (body.format as string) || "wav"),
    (body) => (body.clip_id ? null : "clip_id is required."),
  );

  // POST /me/music/midi
  meClipRoute(
    "/me/music/midi",
    "midi_generate",
    (body) => (client) => client.generateMIDI(body.clip_id as string, body.prompt as string | undefined),
    (body) => (body.clip_id ? null : "clip_id is required."),
  );

  // POST /me/generate/upload-extend
  meClipRoute(
    "/me/generate/upload-extend",
    "upload_extend",
    (body) => (client) =>
      client.uploadExtendMusic({
        uploadedClipId: body.uploaded_clip_id as string | undefined,
        audioUrl: body.audio_url as string | undefined,
        continueAt: body.continue_at ? Number(body.continue_at) : undefined,
        prompt: body.prompt as string | undefined,
        title: body.title as string | undefined,
        tags: body.tags as string | undefined,
      }),
    (body) => {
      if (!body.uploaded_clip_id && !body.audio_url) {
        return "uploaded_clip_id or audio_url is required.";
      }
      return null;
    },
  );

  // POST /me/generate/upload-cover
  meClipRoute(
    "/me/generate/upload-cover",
    "upload_cover",
    (body) => (client) =>
      client.uploadCoverMusic({
        uploadedClipId: body.uploaded_clip_id as string | undefined,
        audioUrl: body.audio_url as string | undefined,
        coverStartS: body.cover_start_s ? Number(body.cover_start_s) : undefined,
        coverEndS: body.cover_end_s ? Number(body.cover_end_s) : undefined,
        prompt: body.prompt as string | undefined,
        title: body.title as string | undefined,
        tags: body.tags as string | undefined,
      }),
    (body) => {
      if (!body.uploaded_clip_id && !body.audio_url) {
        return "uploaded_clip_id or audio_url is required.";
      }
      return null;
    },
  );

  // POST /me/generate/boost
  meClipRoute(
    "/me/generate/boost",
    "boost_style",
    (body) => (client) =>
      client.boostStyle(
        body.clip_id as string,
        body.style_prompt as string,
        {
          startS: body.start_s ? Number(body.start_s) : undefined,
          endS: body.end_s ? Number(body.end_s) : undefined,
        },
      ),
    (body) => {
      if (!body.clip_id || !body.style_prompt) {
        return "clip_id and style_prompt are required.";
      }
      return null;
    },
  );

  // POST /me/upload/init (result job)
  meResultRoute(
    "/me/upload/init",
    "upload_init",
    (body) => (client) =>
      client.createAudioUpload({
        extension: body.extension as string,
        uploadType: (body.upload_type as "file_upload" | "voice_recording" | "song_demo") || undefined,
        lastUploadId: body.last_upload_id as string | undefined,
      }),
    (body) => (body.extension ? null : "extension is required (e.g. mp3, wav, m4a)."),
  );

  // POST /me/upload/register (result job)
  meResultRoute(
    "/me/upload/register",
    "upload_register",
    (body) => (client) =>
      client.registerAudioUpload(body.upload_id as string, {
        uploadType: body.upload_type as string,
        uploadFilename: body.upload_filename as string,
        uploadTitle: body.upload_title as string | undefined,
      }),
    (body) => {
      if (!body.upload_id || !body.upload_type || !body.upload_filename) {
        return "upload_id, upload_type and upload_filename are required.";
      }
      return null;
    },
  );

  // GET /me/upload/status/:id (no job, proxy directly)
  app.get("/me/upload/status/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    const client = await pool.pick();
    try {
      const data = await client.getAudioUploadStatus(id);
      return data;
    } catch (e) {
      return reply.code(502).send({ error: e instanceof Error ? e.message : String(e) });
    }
  });

  // POST /me/music/replace-section (alias for /me/replace-section, snake_case params match v1/music/replace-section)
  app.post("/me/music/replace-section", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (body.clip_id || body.taskId || body.task_id) as string | undefined;
    const lyrics = (body.lyrics || body.fullLyrics) as string | undefined;
    const startS = Number(body.start_s ?? body.infillStartS ?? body.startS);
    const endS = Number(body.end_s ?? body.infillEndS ?? body.endS);
    if (!clipId || !lyrics || !Number.isFinite(startS) || !Number.isFinite(endS) || endS <= startS) {
      return reply
        .code(400)
        .send({ error: "clip_id, lyrics, start_s, end_s are required (end_s > start_s)." });
    }
    const cost = await costFor("replace_section");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("replace_section", (body.callback_url as string) || undefined);
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "replace_section";
    job.credits = cost;
    job.prompt = lyrics;
    void runClipJobWithRetry(job, (client) => client.replaceSection(clipId, { startS, endS, lyrics }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // POST /me/music/recovery (alias of /me/recovery but with clip_id field)
  app.post("/me/music/recovery", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string | undefined;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const cost = await costFor("recovery_audio");
    const key = await pickUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("recovery_audio", (body.callback_url as string) || undefined);
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "recovery_audio";
    job.credits = cost;
    const prompt = (body.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) => client.generateRecoveryAudio(clipId, prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // GET /me/lyrics/:id
  app.get("/me/lyrics/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    const cost = await costFor("timestamped_lyrics_detail");
    const key = await pickUserKey(u.id, cost);
    if (!key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    if (!(await charge(key, cost))) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("timestamped_lyrics_detail");
    job.userId = u.id;
    job.apiKeyId = key.id;
    job.endpoint = "timestamped_lyrics_detail";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.lyricsDetail(id));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // Detail GET routes (T3 - meDetailRoute)
  meDetailRoute("/me/music/wav/:id", "wav_detail", (c, id) => c.wavDetail(id, "wav"));
  meDetailRoute("/me/music/stems/:id", "stems_detail", (c, id) => c.stemsDetail(id));
  meDetailRoute("/me/music/video/:id", "video_detail", (c, id) => c.videoDetail(id));
  meDetailRoute("/me/music/cover/:id", "cover_detail", (c, id) => c.coverDetail(id));
  meDetailRoute("/me/music/subtitle/:id", "subtitle_detail", (c, id) => c.subtitleDetail(id));
  meDetailRoute("/me/music/recovery/:id", "recovery_detail", (c, id) => c.recoveryDetail(id));
  meDetailRoute("/me/mp4/:id", "mp4_detail", (c, id) => c.mp4Detail(id));
  meDetailRoute("/me/music/midi/:id", "midi_detail", (c, id) => c.midiDetail(id));
  meDetailRoute("/me/clip/:id", "lyrics_detail", (c, id) => c.getClipDetail(id));

  // POST /me/mp4/generate (result job)
  meResultRoute(
    "/me/mp4/generate",
    "mp4_generate",
    (body) => (client) =>
      client.generateMP4(body.clip_id as string, {
        prompt: body.prompt as string | undefined,
        quantity: body.quantity ? Number(body.quantity) : undefined,
        aspectRatio: body.aspect_ratio as string | undefined,
      }),
    (body) => (body.clip_id ? null : "clip_id is required."),
  );

  // POST /me/voice/apply
  meClipRoute(
    "/me/voice/apply",
    "voice_apply",
    (body) => (client) =>
      client.voiceApply({
        personaId: body.persona_id as string | undefined,
        clipId: body.clip_id as string | undefined,
        prompt: body.prompt as string | undefined,
        title: body.title as string | undefined,
        tags: body.tags as string | undefined,
        model: body.model as string | undefined,
      }),
    (body) => {
      if (!body.persona_id && !body.clip_id) {
        return "persona_id or clip_id is required.";
      }
      return null;
    },
    "model",
  );

  // POST /me/voice/extend
  meClipRoute(
    "/me/voice/extend",
    "voice_extend",
    (body) => (client) =>
      client.voiceExtend({
        personaId: body.persona_id as string | undefined,
        clipId: body.clip_id as string | undefined,
        continueAt: body.continue_at ? Number(body.continue_at) : undefined,
        prompt: body.prompt as string | undefined,
      }),
    (body) => {
      if (!body.persona_id && !body.clip_id) {
        return "persona_id or clip_id is required.";
      }
      return null;
    },
  );

  app.get("/updates", async () => {
    return query<{ id: string; title: string; slug: string; content: string; created_at: string }>(
      "SELECT id, title, slug, content, created_at FROM blog_posts WHERE published = true ORDER BY created_at DESC",
    );
  });

  app.get("/pricing", async () => {
    const pricing = await query<{ endpoint: string; model: string | null; credit_cost: number }>(
      "SELECT endpoint, model, credit_cost FROM pricing ORDER BY endpoint, model NULLS LAST",
    );
    const packs = await query<{ id: string; amount: number; price: string; currency: string }>(
      "SELECT id, amount, price, currency FROM credit_packs WHERE is_active = true ORDER BY amount",
    );
    return {
      pricing: pricing.map((p) => ({ endpoint: p.endpoint, model: p.model, credit_cost: p.credit_cost })),
      packs: packs.map((p) => ({ id: p.id, amount: p.amount, price: Number(p.price), currency: p.currency })),
    };
  });

  // --- settings + alerts (REQUIREMENTS §4.10) ------------------------------
  // Operator-managed settings live in `app_settings` as one JSONB document per
  // logical group (`brand`, `alerts`). Reads run the stored value through the
  // same validators used on write, so a hand-edited row can never break a caller.
  async function readSettingsValue(key: string): Promise<unknown> {
    const row = await queryOne<{ value: unknown }>("SELECT value FROM app_settings WHERE key = $1", [key]);
    return row?.value ?? null;
  }

  async function writeSettingsValue(key: string, value: unknown, updatedBy: string): Promise<void> {
    await query(
      `INSERT INTO app_settings (key, value, updated_at, updated_by)
       VALUES ($1, $2, now(), $3)
       ON CONFLICT (key) DO UPDATE
         SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by`,
      [key, JSON.stringify(value), updatedBy],
    );
  }

  async function loadBrandSettings(): Promise<BrandSettings> {
    return coerceBrand(await readSettingsValue("brand"));
  }

  async function loadAlertSettings(): Promise<AlertSettings> {
    return coerceAlerts(await readSettingsValue("alerts"));
  }

  type AlertType = "low_credits" | "captcha_locked" | "failure_rate";

  interface AlertItem {
    id: AlertType;
    type: AlertType;
    severity: "warning" | "critical";
    message: string;
    details: Record<string, unknown>;
  }

  interface AlertReport {
    enabled: boolean;
    checked_at: string;
    thresholds: AlertSettings;
    alerts: AlertItem[];
    summary: {
      low_credits: number;
      captcha_locked: boolean;
      failure_rate: number | null;
      requests: number;
      failures: number;
    };
  }

  /**
   * Evaluate the three §4.10 alert conditions against live state. Pure read — it
   * never delivers anything — so both the admin endpoint and the background loop
   * can call it freely; `syncAlertState` is what decides whether to notify.
   */
  async function evaluateAlerts(): Promise<AlertReport> {
    const thresholds = await loadAlertSettings();
    const checkedAt = new Date().toISOString();
    const summary: AlertReport["summary"] = {
      low_credits: 0,
      captcha_locked: false,
      failure_rate: null,
      requests: 0,
      failures: 0,
    };
    if (!thresholds.enabled) {
      return { enabled: false, checked_at: checkedAt, thresholds, alerts: [], summary };
    }

    const alerts: AlertItem[] = [];

    // 1. Suno accounts whose live credit balance is at or below the threshold.
    const health = await pool.listHealth().catch(() => [] as Awaited<ReturnType<AccountPool["listHealth"]>>);
    const low = health.filter((h) => h.credits <= thresholds.low_credits_threshold);
    summary.low_credits = low.length;
    if (low.length > 0) {
      alerts.push({
        id: "low_credits",
        type: "low_credits",
        severity: low.some((h) => h.credits <= 0) ? "critical" : "warning",
        message: `${low.length} Suno account(s) at or below ${thresholds.low_credits_threshold} credits: ${low
          .map((h) => `${h.id} (${h.credits})`)
          .join(", ")}.`,
        details: { accounts: low.map((h) => ({ id: h.id, credits: h.credits })) },
      });
    }

    // 2. Suno currently demanding a captcha for generation.
    if (thresholds.captcha_locked) {
      const required = await captchaRequired();
      summary.captcha_locked = required;
      if (required) {
        alerts.push({
          id: "captcha_locked",
          type: "captcha_locked",
          severity: "warning",
          message: "Suno is requiring a captcha for generation (captcha-locked).",
          details: {},
        });
      }
    }

    // 3. Failure-rate spike over the configured sliding window.
    const row = await queryOne<{ total: string; failed: string }>(
      `SELECT count(*)::text AS total,
              count(*) FILTER (WHERE status <> 'complete')::text AS failed
       FROM usage_logs
       WHERE created_at > now() - ($1 || ' minutes')::interval`,
      [String(thresholds.window_minutes)],
    );
    const total = Number(row?.total ?? 0);
    const failed = Number(row?.failed ?? 0);
    summary.requests = total;
    summary.failures = failed;
    if (total >= thresholds.failure_rate_min_requests) {
      const rate = total > 0 ? failed / total : 0;
      summary.failure_rate = rate;
      if (rate >= thresholds.failure_rate_threshold) {
        alerts.push({
          id: "failure_rate",
          type: "failure_rate",
          severity: rate >= 0.5 ? "critical" : "warning",
          message: `Job failure rate ${(rate * 100).toFixed(1)}% over the last ${
            thresholds.window_minutes
          } min (${failed}/${total}), above the ${(thresholds.failure_rate_threshold * 100).toFixed(1)}% threshold.`,
          details: { rate, failed, total, window_minutes: thresholds.window_minutes },
        });
      }
    }

    return { enabled: true, checked_at: checkedAt, thresholds, alerts, summary };
  }

  /** Deliver one Telegram message; false when creds are unset or delivery fails. */
  async function sendTelegram(text: string): Promise<boolean> {
    const { telegramBotToken, telegramChatId } = config.alerts;
    if (!telegramBotToken || !telegramChatId) return false;
    try {
      const res = await fetch(`https://api.telegram.org/bot${telegramBotToken}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        signal: AbortSignal.timeout(10_000),
        body: JSON.stringify({ chat_id: telegramChatId, text, disable_web_page_preview: true }),
      });
      if (!res.ok) {
        app.log.warn({ status: res.status }, "telegram alert delivery failed");
        return false;
      }
      return true;
    } catch (err) {
      app.log.warn({ err }, "telegram alert delivery error");
      return false;
    }
  }

  /**
   * Diff a fresh report against the last notified state and push only the
   * differences: one message per newly-raised or changed alert, one per alert
   * that has since cleared. Keeps the channel quiet while nothing changes.
   */
  async function syncAlertState(report: AlertReport): Promise<void> {
    const current = new Map<string, string>();
    for (const a of report.alerts) current.set(a.id, `${a.severity}|${a.message}`);
    for (const alert of report.alerts) {
      if (alertState.get(alert.id) !== current.get(alert.id)) {
        if (await sendTelegram(`[ALERT] Camxora Music API — ${alert.type}\n${alert.message}`)) {
          app.log.warn({ alert: alert.id }, "alert notification sent");
        }
      }
    }
    for (const id of [...alertState.keys()]) {
      if (!current.has(id)) {
        if (await sendTelegram(`[RESOLVED] Camxora Music API — ${id} cleared.`)) {
          app.log.info({ alert: id }, "alert recovery notification sent");
        }
      }
    }
    alertState.clear();
    for (const [id, fingerprint] of current) alertState.set(id, fingerprint);
  }

  /** Start the periodic evaluator; a non-positive interval leaves it disabled. */
  function startAlertLoop(): void {
    const intervalMs = config.alerts.checkIntervalMs;
    if (!(intervalMs > 0) || alertTimer) return;
    alertTimer = setInterval(() => {
      void evaluateAlerts()
        .then((report) => syncAlertState(report))
        .catch((err) => app.log.warn({ err }, "alert evaluator failed"));
    }, intervalMs);
    alertTimer.unref?.();
    app.log.info({ intervalMs }, "alert evaluator loop started");
  }

  function stopAlertLoop(): void {
    if (!alertTimer) return;
    clearInterval(alertTimer);
    alertTimer = null;
  }

  // --- admin routes --------------------------------------------------------
  app.get("/admin/keys", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      `SELECT k.id, k.name, k.key_prefix, k.credits, k.is_active, u.email
       FROM api_keys k JOIN users u ON u.id = k.user_id ORDER BY k.created_at DESC`,
    );
  });

  app.get("/admin/accounts", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const dbRows = await query<{
      id: string;
      label: string;
      type: string;
      plan: string | null;
      credits_left: number | null;
      is_active: boolean;
      created_at: string;
    }>("SELECT id, label, type, plan, credits_left, is_active, created_at FROM suno_accounts ORDER BY created_at");
    const [live, alerts] = await Promise.all([
      pool.listHealth().catch(() => [] as Awaited<ReturnType<AccountPool["listHealth"]>>),
      loadAlertSettings(),
    ]);
    const lowThreshold = alerts.low_credits_threshold;
    const liveById = new Map(live.map((l) => [l.id, l]));
    const accounts = dbRows.map((row) => {
      const l = liveById.get(row.label);
      const liveCredits = l?.credits ?? row.credits_left ?? 0;
      return {
        id: row.id,
        label: row.label,
        type: row.type,
        is_active: row.is_active,
        created_at: row.created_at,
        live_plan: l?.plan ?? row.plan ?? "unknown",
        live_credits: liveCredits,
        live_models: l?.models ?? [],
        // Operator-facing health flags (REQUIREMENTS §4.2). `low_credits` uses the
        // same threshold as the §4.10 alert so the badge and the alert never disagree.
        health: {
          disabled: !row.is_active,
          low_credits: liveCredits <= lowThreshold,
          captcha_required: l?.captchaRequired ?? false,
        },
      };
    });
    return { accounts };
  });

  app.post("/admin/accounts", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { label, type, client_cookie, device_id } = (req.body ?? {}) as {
      label?: string;
      type?: string;
      client_cookie?: string;
      device_id?: string;
    };
    if (!label || !client_cookie || !device_id) {
      return reply.code(400).send({ error: "label, client_cookie and device_id are required." });
    }
    // The label is the pool's account identity (src/pool.ts keys clients by it),
    // so a duplicate silently merges two accounts in routing and health views.
    const clash = await queryOne<{ id: string }>("SELECT id FROM suno_accounts WHERE label = $1", [label]);
    if (clash) return reply.code(409).send({ error: "An account with that label already exists." });
    const t = type === "paid" ? "paid" : "free";
    const rows = await query<{ id: string }>(
      "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, $2, $3, $4) RETURNING id",
      [label, t, encryptSecret(client_cookie), device_id],
    );
    // Make the new account routable immediately (the pool is built once at boot).
    await pool.reload().catch((err) => app.log.warn({ err }, "account pool reload failed"));
    await recordAudit({
      actor: admin,
      action: "account.create",
      targetType: "suno_account",
      targetId: rows[0].id,
      details: { label, type: t },
      req,
    });
    return reply.code(201).send({ id: rows[0].id });
  });

  app.patch("/admin/accounts/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const body = (req.body ?? {}) as {
      label?: unknown;
      type?: unknown;
      client_cookie?: unknown;
      device_id?: unknown;
      is_active?: unknown;
    };

    const sets: string[] = [];
    const params: unknown[] = [];
    const details: Record<string, unknown> = {};

    if (body.label !== undefined) {
      if (typeof body.label !== "string" || !body.label.trim()) {
        return reply.code(400).send({ error: "label must be a non-empty string." });
      }
      const nextLabel = body.label.trim();
      const clash = await queryOne<{ id: string }>(
        "SELECT id FROM suno_accounts WHERE label = $1 AND id <> $2",
        [nextLabel, id],
      );
      if (clash) return reply.code(409).send({ error: "An account with that label already exists." });
      params.push(nextLabel);
      sets.push(`label = $${params.length}`);
      details.label = nextLabel;
    }
    if (body.type !== undefined) {
      if (body.type !== "free" && body.type !== "paid") {
        return reply.code(400).send({ error: "type must be free or paid." });
      }
      params.push(body.type);
      sets.push(`type = $${params.length}`);
      details.type = body.type;
    }
    if (body.client_cookie !== undefined) {
      if (typeof body.client_cookie !== "string" || !body.client_cookie.trim()) {
        return reply.code(400).send({ error: "client_cookie must be a non-empty string." });
      }
      params.push(encryptSecret(body.client_cookie));
      sets.push(`client_cookie = $${params.length}`);
      details.client_cookie = "(updated)";
    }
    if (body.device_id !== undefined) {
      if (typeof body.device_id !== "string" || !body.device_id.trim()) {
        return reply.code(400).send({ error: "device_id must be a non-empty string." });
      }
      params.push(body.device_id.trim());
      sets.push(`device_id = $${params.length}`);
      details.device_id = body.device_id.trim();
    }
    if (body.is_active !== undefined) {
      if (typeof body.is_active !== "boolean") {
        return reply.code(400).send({ error: "is_active must be a boolean." });
      }
      params.push(body.is_active);
      sets.push(`is_active = $${params.length}`);
      details.is_active = body.is_active;
    }
    if (sets.length === 0) {
      return reply.code(400).send({ error: "No editable fields supplied." });
    }

    // The pool only loads active accounts, so deactivating the last one would
    // leave every generation request with no Suno client to route to.
    if (body.is_active === false) {
      const current = await queryOne<{ is_active: boolean }>("SELECT is_active FROM suno_accounts WHERE id = $1", [id]);
      if (!current) return reply.code(404).send({ error: "Account not found." });
      if (current.is_active) {
        const remaining = await queryOne<{ n: string }>(
          "SELECT count(*)::text AS n FROM suno_accounts WHERE is_active = true AND id <> $1",
          [id],
        );
        if (remaining?.n === "0") {
          return reply
            .code(409)
            .send({ error: "This is the last active Suno account. Add another account before deactivating it." });
        }
      }
    }

    params.push(id);
    const rows = await query<{ id: string }>(
      `UPDATE suno_accounts SET ${sets.join(", ")} WHERE id = $${params.length} RETURNING id`,
      params,
    );
    if (rows.length === 0) return reply.code(404).send({ error: "Account not found." });
    await pool.reload().catch((err) => app.log.warn({ err }, "account pool reload failed"));
    await recordAudit({
      actor: admin,
      action: "account.update",
      targetType: "suno_account",
      targetId: id,
      details,
      req,
    });
    return { ok: true, id };
  });

  app.delete("/admin/accounts/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    // The pool only loads active accounts, so deleting the last active one would
    // leave every generation request with no Suno client to route to.
    const current = await queryOne<{ is_active: boolean }>("SELECT is_active FROM suno_accounts WHERE id = $1", [id]);
    if (!current) return reply.code(404).send({ error: "Account not found." });
    if (current.is_active) {
      const remaining = await queryOne<{ n: string }>(
        "SELECT count(*)::text AS n FROM suno_accounts WHERE is_active = true AND id <> $1",
        [id],
      );
      if (remaining?.n === "0") {
        return reply
          .code(409)
          .send({ error: "This is the last active Suno account. Add another account before deleting it." });
      }
    }
    const rows = await query<{ id: string; label: string }>(
      "DELETE FROM suno_accounts WHERE id = $1 RETURNING id, label",
      [id],
    );
    if (rows.length === 0) return reply.code(404).send({ error: "Account not found." });
    await pool.reload().catch((err) => app.log.warn({ err }, "account pool reload failed"));
    await recordAudit({
      actor: admin,
      action: "account.delete",
      targetType: "suno_account",
      targetId: id,
      details: { label: rows[0].label },
      req,
    });
    return { ok: true, id };
  });

  app.get("/admin/stats", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const users = await queryOne<{ count: string }>("SELECT count(*)::text AS count FROM users");
    const keys = await queryOne<{ count: string }>("SELECT count(*)::text AS count FROM api_keys");
    const logs = await queryOne<{ count: string }>("SELECT count(*)::text AS count FROM usage_logs");
    const credits = await queryOne<{ sum: string }>("SELECT COALESCE(sum(credits),0)::text AS sum FROM api_keys");
    const spent = await queryOne<{ sum: string }>(
      "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs",
    );
    const series = await query<{ day: string; count: string }>(
      "SELECT to_char(created_at, 'YYYY-MM-DD') AS day, count(*)::text AS count FROM usage_logs WHERE created_at > now() - interval '30 days' GROUP BY day ORDER BY day",
    );
    return {
      users: Number(users?.count ?? 0),
      keys: Number(keys?.count ?? 0),
      requests: Number(logs?.count ?? 0),
      credits: Number(credits?.sum ?? 0),
      spent: Number(spent?.sum ?? 0),
      accounts: pool.size,
      series: series.map((s) => ({ day: s.day, count: Number(s.count) })),
    };
  });

  // Usage analytics (task 5.4, REQUIREMENTS §4.7): per-endpoint, per-model and
  // per-user breakdowns plus success/failure counts and revenue trends, all
  // derived from usage_logs. Revenue is credits_consumed converted to USD using
  // the same cheapest-active-pack rate the user-facing /me/usage reports use, so
  // the two views never disagree.
  app.get("/admin/analytics", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const daysParam = Number((req.query as { days?: string })?.days ?? 30);
    const days = Math.min(90, Math.max(7, daysParam || 30));

    const creditsPerUsd = await creditsPerUsdRate();

    // A log row is a success when its job reached "complete" and a failure
    // otherwise, so the two buckets always add up to the total.
    const AGG = `count(*)::text AS count,
                 count(*) FILTER (WHERE status = 'complete')::text AS success,
                 count(*) FILTER (WHERE status <> 'complete')::text AS failed,
                 COALESCE(sum(credits_consumed),0)::text AS credits`;

    interface AggRow { count: string; success: string; failed: string; credits: string }
    const shape = (r: AggRow) => ({
      count: Number(r.count),
      success: Number(r.success),
      failed: Number(r.failed),
      credits: Number(r.credits),
      revenue: Number(r.credits) / creditsPerUsd,
    });

    const totals = await queryOne<AggRow>(
      `SELECT ${AGG} FROM usage_logs WHERE created_at > now() - interval '${days} days'`,
    );
    const byEndpoint = await query<AggRow & { endpoint: string }>(
      `SELECT COALESCE(endpoint, '(none)') AS endpoint, ${AGG} FROM usage_logs
       WHERE created_at > now() - interval '${days} days'
       GROUP BY endpoint ORDER BY sum(credits_consumed) DESC NULLS LAST, count(*) DESC`,
    );
    const byModel = await query<AggRow & { model: string }>(
      `SELECT COALESCE(model, '(unset)') AS model, ${AGG} FROM usage_logs
       WHERE created_at > now() - interval '${days} days'
       GROUP BY model ORDER BY sum(credits_consumed) DESC NULLS LAST, count(*) DESC`,
    );
    const byUser = await query<AggRow & { user_id: string; email: string }>(
      `SELECT l.user_id, u.email, count(*)::text AS count,
              count(*) FILTER (WHERE l.status = 'complete')::text AS success,
              count(*) FILTER (WHERE l.status <> 'complete')::text AS failed,
              COALESCE(sum(l.credits_consumed),0)::text AS credits
       FROM usage_logs l JOIN users u ON u.id = l.user_id
       WHERE l.created_at > now() - interval '${days} days'
       GROUP BY l.user_id, u.email ORDER BY count(*) DESC LIMIT 50`,
    );
    const series = await query<AggRow & { day: string }>(
      `SELECT to_char(created_at, 'YYYY-MM-DD') AS day, ${AGG} FROM usage_logs
       WHERE created_at > now() - interval '${days} days'
       GROUP BY day ORDER BY day`,
    );

    return {
      range: { days },
      credits_per_usd: creditsPerUsd,
      totals: totals ? shape(totals) : { count: 0, success: 0, failed: 0, credits: 0, revenue: 0 },
      by_endpoint: byEndpoint.map((r) => ({ endpoint: r.endpoint, ...shape(r) })),
      by_model: byModel.map((r) => ({ model: r.model, ...shape(r) })),
      by_user: byUser.map((r) => ({ user_id: r.user_id, email: r.email, ...shape(r) })),
      series: series.map((r) => ({ day: r.day, ...shape(r) })),
    };
  });

  app.get("/admin/users", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      `SELECT u.id, u.email, u.name, u.role, u.status, u.created_at,
              (SELECT COALESCE(sum(k.credits),0) FROM api_keys k WHERE k.user_id = u.id) AS credits,
              (SELECT count(*) FROM api_keys k WHERE k.user_id = u.id) AS key_count,
              (SELECT count(*) FROM usage_logs l WHERE l.user_id = u.id) AS request_count
       FROM users u ORDER BY u.created_at DESC`,
    );
  });

  app.patch("/admin/users/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const { status } = (req.body ?? {}) as { status?: string };
    if (status !== "active" && status !== "suspended") {
      return reply.code(400).send({ error: "status must be active or suspended." });
    }
    await query("UPDATE users SET status = $1 WHERE id = $2", [status, id]);
    await recordAudit({
      actor: admin,
      action: "user.status",
      targetType: "user",
      targetId: id,
      details: { status },
      req,
    });
    return { ok: true };
  });

  app.post("/admin/users/:id/credits", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const { amount } = (req.body ?? {}) as { amount?: number };
    if (typeof amount !== "number" || amount === 0) {
      return reply.code(400).send({ error: "amount is required and non-zero." });
    }
    // Increment in-place (credits = credits + amount) rather than writing an
    // absolute value read earlier, and do it with the ledger row in one
    // transaction so concurrent adjustments cannot lose an update.
    const newCredits = await withTransaction(async (client) => {
      const existing = await client.query<{ id: string }>(
        "SELECT id FROM api_keys WHERE user_id = $1 ORDER BY created_at ASC LIMIT 1 FOR UPDATE",
        [id],
      );
      let keyId = existing.rows[0]?.id;
      if (!keyId) {
        const raw = `sk_${randomUUID().replace(/-/g, "")}`;
        const inserted = await client.query<{ id: string }>(
          "INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits) VALUES ($1, 'default', $2, $3, 0) RETURNING id",
          [id, hashKey(raw), raw.slice(0, 8)],
        );
        keyId = inserted.rows[0].id;
      }
      const updated = await client.query<{ credits: number }>(
        "UPDATE api_keys SET credits = GREATEST(0, credits + $1) WHERE id = $2 RETURNING credits",
        [amount, keyId],
      );
      await client.query(
        "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'adjust', $3)",
        [id, amount, "Admin credit adjustment"],
      );
      return updated.rows[0].credits;
    });
    await recordAudit({
      actor: admin,
      action: "user.credits",
      targetType: "user",
      targetId: id,
      details: { amount, resulting_credits: newCredits },
      req,
    });
    return { ok: true, credits: newCredits };
  });

  app.get("/admin/users/:id/rate-limits", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { id } = req.params as { id: string };
    const row = await queryOne<{ requests_per_minute: number | null; requests_per_day: number | null }>(
      "SELECT requests_per_minute, requests_per_day FROM rate_limits WHERE user_id = $1 LIMIT 1",
      [id],
    );
    return {
      user_id: id,
      requests_per_minute: row?.requests_per_minute ?? null,
      requests_per_day: row?.requests_per_day ?? null,
    };
  });

  app.put("/admin/users/:id/rate-limits", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const body = (req.body ?? {}) as {
      requests_per_minute?: number | null;
      requests_per_day?: number | null;
    };
    // A limit is a positive integer, or null to clear it.
    const parseLimit = (value: unknown): { ok: true; value: number | null } | { ok: false } => {
      if (value === null || value === undefined) return { ok: true, value: null };
      if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) return { ok: false };
      return { ok: true, value };
    };
    const perMinute = parseLimit(body.requests_per_minute);
    const perDay = parseLimit(body.requests_per_day);
    if (!perMinute.ok || !perDay.ok) {
      return reply
        .code(400)
        .send({ error: "requests_per_minute/requests_per_day must be positive integers or null." });
    }
    const user = await queryOne<{ id: string }>("SELECT id FROM users WHERE id = $1", [id]);
    if (!user) return reply.code(404).send({ error: "User not found." });
    if (perMinute.value === null && perDay.value === null) {
      await query("DELETE FROM rate_limits WHERE user_id = $1", [id]);
    } else {
      await query(
        `INSERT INTO rate_limits (user_id, requests_per_minute, requests_per_day)
         VALUES ($1, $2, $3)
         ON CONFLICT (user_id) DO UPDATE SET
           requests_per_minute = EXCLUDED.requests_per_minute,
           requests_per_day = EXCLUDED.requests_per_day`,
        [id, perMinute.value, perDay.value],
      );
    }
    // Drop the cached row so the new limits apply on the next request.
    rateLimitCache.delete(id);
    await recordAudit({
      actor: admin,
      action: "user.rate_limits",
      targetType: "user",
      targetId: id,
      details: { requests_per_minute: perMinute.value, requests_per_day: perDay.value },
      req,
    });
    return {
      ok: true,
      user_id: id,
      requests_per_minute: perMinute.value,
      requests_per_day: perDay.value,
    };
  });

  app.get("/admin/pricing", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      "SELECT id, endpoint, model, credit_cost FROM pricing ORDER BY endpoint, model NULLS LAST",
    );
  });

  app.post("/admin/pricing", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { endpoint, model, credit_cost } = (req.body ?? {}) as {
      endpoint?: string;
      model?: string | null;
      credit_cost?: number;
    };
    if (!endpoint || typeof credit_cost !== "number") {
      return reply.code(400).send({ error: "endpoint and credit_cost are required." });
    }
    const existing = await queryOne<{ id: string }>(
      "SELECT id FROM pricing WHERE endpoint = $1 AND model IS NOT DISTINCT FROM $2 LIMIT 1",
      [endpoint, model ?? null],
    );
    if (existing) {
      await query("UPDATE pricing SET credit_cost = $1 WHERE id = $2", [credit_cost, existing.id]);
      await recordAudit({
        actor: admin,
        action: "pricing.upsert",
        targetType: "pricing",
        targetId: existing.id,
        details: { endpoint, model: model ?? null, credit_cost, updated: true },
        req,
      });
      return { id: existing.id, updated: true };
    }
    const rows = await query<{ id: string }>(
      "INSERT INTO pricing (endpoint, model, credit_cost) VALUES ($1, $2, $3) RETURNING id",
      [endpoint, model ?? null, credit_cost],
    );
    await recordAudit({
      actor: admin,
      action: "pricing.upsert",
      targetType: "pricing",
      targetId: rows[0].id,
      details: { endpoint, model: model ?? null, credit_cost, updated: false },
      req,
    });
    return reply.code(201).send({ id: rows[0].id, updated: false });
  });

  app.put("/admin/pricing/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const { endpoint, model, credit_cost } = (req.body ?? {}) as {
      endpoint?: string;
      model?: string | null;
      credit_cost?: number;
    };
    if (!endpoint || typeof credit_cost !== "number") {
      return reply.code(400).send({ error: "endpoint and credit_cost are required." });
    }
    const updated = await query<{ id: string }>(
      "UPDATE pricing SET endpoint = $1, model = $2, credit_cost = $3 WHERE id = $4 RETURNING id",
      [endpoint, model ?? null, credit_cost, id],
    );
    if (!updated.length) return reply.code(404).send({ error: "Pricing row not found." });
    // Two rows sharing (endpoint, model) make costFor pick an arbitrary row, so
    // after the update drop any other row that now collides with this one.
    await query(
      "DELETE FROM pricing WHERE endpoint = $1 AND model IS NOT DISTINCT FROM $2 AND id <> $3",
      [endpoint, model ?? null, id],
    );
    await recordAudit({
      actor: admin,
      action: "pricing.update",
      targetType: "pricing",
      targetId: id,
      details: { endpoint, model: model ?? null, credit_cost },
      req,
    });
    return { ok: true };
  });

  app.delete("/admin/pricing/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM pricing WHERE id = $1", [id]);
    await recordAudit({
      actor: admin,
      action: "pricing.delete",
      targetType: "pricing",
      targetId: id,
      req,
    });
    return { ok: true };
  });

  app.get("/admin/routing", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      "SELECT id, model, policy FROM routing_rules ORDER BY model",
    );
  });

  app.post("/admin/routing", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { model, policy } = (req.body ?? {}) as { model?: string; policy?: string };
    if (!model || !policy) return reply.code(400).send({ error: "model and policy are required." });
    if (policy !== "prefer_free" && policy !== "paid_only" && policy !== "any") {
      return reply.code(400).send({ error: "policy must be prefer_free, paid_only, or any." });
    }
    const existing = await queryOne<{ id: string }>("SELECT id FROM routing_rules WHERE model = $1 LIMIT 1", [model]);
    if (existing) {
      await query("UPDATE routing_rules SET policy = $1 WHERE id = $2", [policy, existing.id]);
      await recordAudit({
        actor: admin,
        action: "routing.upsert",
        targetType: "routing_rule",
        targetId: existing.id,
        details: { model, policy, updated: true },
        req,
      });
      return { id: existing.id, updated: true };
    }
    const rows = await query<{ id: string }>(
      "INSERT INTO routing_rules (model, policy) VALUES ($1, $2) RETURNING id",
      [model, policy],
    );
    await recordAudit({
      actor: admin,
      action: "routing.upsert",
      targetType: "routing_rule",
      targetId: rows[0].id,
      details: { model, policy, updated: false },
      req,
    });
    return reply.code(201).send({ id: rows[0].id, updated: false });
  });

  app.delete("/admin/routing/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM routing_rules WHERE id = $1", [id]);
    await recordAudit({
      actor: admin,
      action: "routing.delete",
      targetType: "routing_rule",
      targetId: id,
      req,
    });
    return { ok: true };
  });

  // Credit packs (task 5.3, REQUIREMENTS §4.5): the admin sets the packs users
  // can buy. Unlike the public reads, the admin list includes inactive packs so
  // they can be edited/reactivated.
  app.get("/admin/credit-packs", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      "SELECT id, amount, price, currency, is_active FROM credit_packs ORDER BY amount",
    );
  });

  app.post("/admin/credit-packs", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { amount, price, currency, is_active } = (req.body ?? {}) as {
      amount?: number;
      price?: number;
      currency?: string;
      is_active?: boolean;
    };
    if (!Number.isInteger(amount) || (amount as number) <= 0 || typeof price !== "number" || price < 0) {
      return reply
        .code(400)
        .send({ error: "amount (positive integer) and price (non-negative number) are required." });
    }
    const cur = (currency ?? "USD").toUpperCase();
    const active = is_active ?? true;
    // Two active packs of the same size make the "cheapest active pack" rate
    // helper pick arbitrarily, so refuse the duplicate instead of storing it.
    if (active) {
      const clash = await queryOne<{ id: string }>(
        "SELECT id FROM credit_packs WHERE amount = $1 AND currency = $2 AND is_active = true",
        [amount, cur],
      );
      if (clash) {
        return reply.code(409).send({ error: `An active ${cur} pack of ${amount} credits already exists.` });
      }
    }
    const rows = await query<{ id: string }>(
      "INSERT INTO credit_packs (amount, price, currency, is_active) VALUES ($1, $2, $3, $4) RETURNING id",
      [amount, price, cur, active],
    );
    await recordAudit({
      actor: admin,
      action: "credit_pack.create",
      targetType: "credit_pack",
      targetId: rows[0].id,
      details: { amount, price, currency: cur, is_active: active },
      req,
    });
    return reply.code(201).send({ id: rows[0].id });
  });

  app.put("/admin/credit-packs/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const { amount, price, currency, is_active } = (req.body ?? {}) as {
      amount?: number;
      price?: number;
      currency?: string;
      is_active?: boolean;
    };
    if (!Number.isInteger(amount) || (amount as number) <= 0 || typeof price !== "number" || price < 0) {
      return reply
        .code(400)
        .send({ error: "amount (positive integer) and price (non-negative number) are required." });
    }
    const cur = (currency ?? "USD").toUpperCase();
    const active = is_active ?? true;
    // Same rule as create: an edit must not land on a size another active pack owns.
    if (active) {
      const clash = await queryOne<{ id: string }>(
        "SELECT id FROM credit_packs WHERE amount = $1 AND currency = $2 AND is_active = true AND id <> $3",
        [amount, cur, id],
      );
      if (clash) {
        return reply.code(409).send({ error: `An active ${cur} pack of ${amount} credits already exists.` });
      }
    }
    const updated = await query<{ id: string }>(
      "UPDATE credit_packs SET amount = $1, price = $2, currency = $3, is_active = $4 WHERE id = $5 RETURNING id",
      [amount, price, cur, active, id],
    );
    if (!updated.length) return reply.code(404).send({ error: "Credit pack not found." });
    await recordAudit({
      actor: admin,
      action: "credit_pack.update",
      targetType: "credit_pack",
      targetId: id,
      details: { amount, price, currency: cur, is_active: active },
      req,
    });
    return { ok: true };
  });

  app.delete("/admin/credit-packs/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM credit_packs WHERE id = $1", [id]);
    await recordAudit({
      actor: admin,
      action: "credit_pack.delete",
      targetType: "credit_pack",
      targetId: id,
      req,
    });
    return { ok: true };
  });

  app.get("/admin/logs", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      `SELECT l.id, l.endpoint, l.model, l.prompt, l.status, l.credits_consumed, l.task_id, l.created_at, u.email
       FROM usage_logs l JOIN users u ON u.id = l.user_id
       ORDER BY l.created_at DESC LIMIT 200`,
    );
  });

  app.get("/admin/content", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      "SELECT id, title, slug, content, published, created_at FROM blog_posts ORDER BY created_at DESC",
    );
  });

  app.post("/admin/content", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { title, slug, content, published } = (req.body ?? {}) as {
      title?: string;
      slug?: string;
      content?: string;
      published?: boolean;
    };
    if (!title || !content) return reply.code(400).send({ error: "title and content are required." });
    const s = slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const rows = await query<{ id: string }>(
      "INSERT INTO blog_posts (title, slug, content, published) VALUES ($1, $2, $3, $4) RETURNING id",
      [title, s, content, Boolean(published)],
    );
    await recordAudit({
      actor: admin,
      action: "content.create",
      targetType: "blog_post",
      targetId: rows[0].id,
      details: { title, slug: s, published: Boolean(published) },
      req,
    });
    return reply.code(201).send({ id: rows[0].id });
  });

  app.put("/admin/content/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const { title, slug, content, published } = (req.body ?? {}) as {
      title?: string;
      slug?: string;
      content?: string;
      published?: boolean;
    };
    if (!title || !content) return reply.code(400).send({ error: "title and content are required." });
    const s = slug || title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(
      "UPDATE blog_posts SET title = $1, slug = $2, content = $3, published = $4 WHERE id = $5",
      [title, s, content, Boolean(published), id],
    );
    await recordAudit({
      actor: admin,
      action: "content.update",
      targetType: "blog_post",
      targetId: id,
      details: { title, slug: s, published: Boolean(published) },
      req,
    });
    return { ok: true };
  });

  app.delete("/admin/content/:id", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM blog_posts WHERE id = $1", [id]);
    await recordAudit({
      actor: admin,
      action: "content.delete",
      targetType: "blog_post",
      targetId: id,
      req,
    });
    return { ok: true };
  });

  // Read side of the audit trail (task 5.2, REQUIREMENTS §4.11). Newest first,
  // with optional `action` / `actor_id` filters and a bounded page size.
  app.get("/admin/audit", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const q = (req.query ?? {}) as { limit?: string; action?: string; actor_id?: string };
    const parsed = Number(q.limit ?? 200);
    const limit = Number.isInteger(parsed) && parsed > 0 ? Math.min(parsed, 500) : 200;
    const filters: string[] = [];
    const params: unknown[] = [];
    if (q.action) {
      params.push(q.action);
      filters.push(`action = $${params.length}`);
    }
    if (q.actor_id) {
      params.push(q.actor_id);
      filters.push(`actor_id = $${params.length}`);
    }
    params.push(limit);
    return query<Record<string, unknown>>(
      `SELECT id, actor_id, actor_email, action, target_type, target_id, details, ip, created_at
       FROM audit_logs
       ${filters.length ? `WHERE ${filters.join(" AND ")}` : ""}
       ORDER BY created_at DESC
       LIMIT $${params.length}`,
      params,
    );
  });

  // Operator-managed branding + alert thresholds (REQUIREMENTS §4.10). Both
  // groups are returned as-is with defaults filled in, so the panel never has to
  // special-case an empty store.
  app.get("/admin/settings", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const [brand, alerts] = await Promise.all([loadBrandSettings(), loadAlertSettings()]);
    return { brand, alerts };
  });

  app.put("/admin/settings", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const body = (req.body ?? {}) as { brand?: unknown; alerts?: unknown };
    if (body.brand === undefined && body.alerts === undefined) {
      return reply.code(400).send({ error: "Provide a brand and/or alerts patch." });
    }

    let brand = await loadBrandSettings();
    let alerts = await loadAlertSettings();
    const changed: string[] = [];

    if (body.brand !== undefined) {
      const merged = mergeBrand(brand, body.brand);
      if (!merged.ok) return reply.code(400).send({ error: merged.error });
      brand = merged.value;
      await writeSettingsValue("brand", brand, admin.id);
      changed.push("brand");
    }
    if (body.alerts !== undefined) {
      const merged = mergeAlerts(alerts, body.alerts);
      if (!merged.ok) return reply.code(400).send({ error: merged.error });
      alerts = merged.value;
      await writeSettingsValue("alerts", alerts, admin.id);
      changed.push("alerts");
    }

    await recordAudit({
      actor: admin,
      action: "settings.update",
      targetType: "settings",
      targetId: changed.join(","),
      details: { brand, alerts },
      req,
    });
    return { brand, alerts };
  });

  // Live alert report for the panel. Notifying Telegram is a side effect here so
  // that opening the panel acts as a manual check when the background loop is
  // disabled (`ALERT_CHECK_INTERVAL_MS=0`); when the loop is on it is harmless,
  // because `syncAlertState` only sends on an actual state change.
  app.get("/admin/alerts", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const report = await evaluateAlerts();
    await syncAlertState(report);
    return report;
  });

  // --- v1 API (DB-backed keys) --------------------------------------------
  app.get("/v1/credits", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    return { name: key.name, credits: key.credits };
  });

  app.post("/v1/lyrics", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { prompt, callback_url } = (req.body ?? {}) as { prompt?: string; callback_url?: string };
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const cost = await costFor("lyrics");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("lyrics", callback_url);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "lyrics";
    job.prompt = prompt;
    job.credits = cost;
    void runResultJobWithRetry(job, processLyricsSubmit(prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/music", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    if (!body.gpt_description_prompt && !body.prompt) {
      return reply.code(400).send({ error: "gpt_description_prompt or prompt is required." });
    }
    const cost = await costFor("music");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const callbackUrl = (body.callback_url as string) || undefined;
    const job = newJob("music", callbackUrl);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "music";
    job.model = (body.model as string) || undefined;
    job.prompt = (body.gpt_description_prompt ?? body.prompt) as string;
    job.credits = cost;
    const model = (body.model as string) || undefined;
    const policy = await routingPolicy(model);
    void runClipJobWithRetry(job, processMusicSubmit(body), { model, policy });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/sounds", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const prompt = body.prompt as string;
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const cost = await costFor("sounds");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("sounds", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "sounds";
    job.model = (body.model as string) || undefined;
    job.prompt = prompt;
    job.credits = cost;
    const spolicy = await routingPolicy((body.model as string) || undefined);
    void runClipJobWithRetry(job, processSoundsSubmit(body), {
      model: (body.model as string) || undefined,
      policy: spolicy,
    });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  function clipRoute(path: string, type: Job["type"]) {
    app.post(path, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const body = (req.body ?? {}) as Record<string, unknown>;
      const clipId = body.clip_id as string;
      if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
      const cost = await costFor(type);
      if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

      const job = newJob(type, body.callback_url as string | undefined);
      job.userId = key.user_id;
      job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      const submitFactory = (client: SunoClient) => {
        if (type === "extend") return client.extendMusic(clipId, { continueAt: Number(body.continue_at ?? 170) });
        if (type === "cover") return client.coverMusic(clipId, body.prompt as string | undefined);
        if (type === "remaster") return client.remaster(clipId, body.model as string | undefined);
        if (type === "add_vocals") {
          if (!body.prompt) throw new Error("prompt is required for add_vocals.");
          return client.addVocals(clipId, body.prompt as string);
        }
        if (type === "add_instrumental") {
          if (!body.prompt) throw new Error("prompt is required for add_instrumental.");
          return client.addInstrumental(clipId, body.prompt as string);
        }
        return client.stems(clipId);
      };
      void runClipJobWithRetry(job, submitFactory);
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  clipRoute("/v1/music/extend", "extend");
  clipRoute("/v1/music/cover", "cover");
  clipRoute("/v1/music/stems", "stems");
  clipRoute("/v1/music/remaster", "remaster");
  clipRoute("/v1/music/add-vocals", "add_vocals");
  clipRoute("/v1/music/add-instrumental", "add_instrumental");

  app.post("/v1/music/mashup", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipIds = body.clip_ids as string[] | undefined;
    if (!clipIds || !Array.isArray(clipIds) || clipIds.length < 2) {
      return reply.code(400).send({ error: "clip_ids (array of 2+) is required." });
    }
    const cost = await costFor("mashup");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("mashup", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "mashup";
    job.credits = cost;
    job.prompt = (body.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) =>
      client.mashup(clipIds, body.prompt as string | undefined),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/music/replace-section", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    const lyrics = body.lyrics as string;
    const startS = Number(body.start_s);
    const endS = Number(body.end_s);
    if (!clipId || !lyrics || !Number.isFinite(startS) || !Number.isFinite(endS) || endS <= startS) {
      return reply.code(400).send({ error: "clip_id, lyrics, start_s, end_s are required (end_s > start_s)." });
    }
    const cost = await costFor("replace_section");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("replace_section", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "replace_section";
    job.credits = cost;
    job.prompt = lyrics;
    void runClipJobWithRetry(job, (client) =>
      client.replaceSection(clipId, { startS, endS, lyrics }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/music/cover-image", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    const prompt = body.prompt as string;
    if (!clipId || !prompt) return reply.code(400).send({ error: "clip_id and prompt are required." });
    const cost = await costFor("cover_image");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("cover_image", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "cover_image";
    job.credits = cost;
    job.prompt = prompt;
    void runResultJobWithRetry(job, (client) => client.generateCoverImage(clipId, prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/persona/create", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    const name = body.name as string;
    if (!clipId || !name) return reply.code(400).send({ error: "clip_id and name are required." });
    const cost = await costFor("persona");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("persona", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "persona";
    job.credits = cost;
    job.prompt = name;
    void runResultJobWithRetry(
      job,
      (client) =>
        client.createPersona(clipId, name, body.styles as string | undefined),
      { policy: "paid_only" },
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/music/wav", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    const format = (body.format as string) || "wav";
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const cost = await costFor("wav");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("wav", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "wav";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.downloadUrl(clipId, format));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/generate/upload-extend", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const uploadedClipId = body.uploaded_clip_id as string | undefined;
    const audioUrl = body.audio_url as string | undefined;
    if (!uploadedClipId && !audioUrl) {
      return reply.code(400).send({ error: "uploaded_clip_id or audio_url is required." });
    }
    const cost = await costFor("upload_extend");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("upload_extend", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "upload_extend";
    job.model = (body.model as string) || undefined;
    job.prompt = (body.prompt as string) || undefined;
    job.credits = cost;
    void runClipJobWithRetry(job, (client) =>
      client.uploadExtendMusic({
        uploadedClipId,
        audioUrl,
        continueAt: body.continue_at ? Number(body.continue_at) : undefined,
        prompt: body.prompt as string | undefined,
        title: body.title as string | undefined,
        tags: body.tags as string | undefined,
      }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/generate/upload-cover", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const uploadedClipId = body.uploaded_clip_id as string | undefined;
    const audioUrl = body.audio_url as string | undefined;
    if (!uploadedClipId && !audioUrl) {
      return reply.code(400).send({ error: "uploaded_clip_id or audio_url is required." });
    }
    const cost = await costFor("upload_cover");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("upload_cover", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "upload_cover";
    job.model = (body.model as string) || undefined;
    job.prompt = (body.prompt as string) || undefined;
    job.credits = cost;
    void runClipJobWithRetry(job, (client) =>
      client.uploadCoverMusic({
        uploadedClipId,
        audioUrl,
        coverStartS: body.cover_start_s ? Number(body.cover_start_s) : undefined,
        coverEndS: body.cover_end_s ? Number(body.cover_end_s) : undefined,
        prompt: body.prompt as string | undefined,
        title: body.title as string | undefined,
        tags: body.tags as string | undefined,
      }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.get("/v1/task/:id", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    const job = jobs.get(id) ?? (await loadJob(id));
    if (!job) return reply.code(404).send({ error: "Task not found." });
    return {
      job_id: job.id,
      type: job.type,
      status: job.status,
      account_id: job.accountId,
      result: job.result,
      error: job.error,
    };
  });

  // -------- Upload 2-step flow (init + register) --------
  app.post("/v1/upload/init", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const extension = body.extension as string;
    if (!extension) return reply.code(400).send({ error: "extension is required (e.g. mp3, wav, m4a)." });
    const cost = await costFor("upload_init");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("upload_init", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "upload_init";
    job.credits = cost;
    const uploadType = (body.upload_type as "file_upload" | "voice_recording" | "song_demo") || undefined;
    const lastUploadId = body.last_upload_id as string | undefined;
    void runResultJobWithRetry(job, (client) =>
      client.createAudioUpload({ extension, uploadType, lastUploadId }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/upload/register", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const uploadId = body.upload_id as string;
    const uploadType = body.upload_type as string;
    const uploadFilename = body.upload_filename as string;
    if (!uploadId || !uploadType || !uploadFilename) {
      return reply.code(400).send({ error: "upload_id, upload_type and upload_filename are required." });
    }
    const cost = await costFor("upload_register");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("upload_register", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "upload_register";
    job.credits = cost;
    const uploadTitle = body.upload_title as string | undefined;
    void runResultJobWithRetry(job, (client) =>
      client.registerAudioUpload(uploadId, { uploadType, uploadFilename, uploadTitle }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.get("/v1/upload/status/:id", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    const client = await pool.pick();
    try {
      const data = await client.getAudioUploadStatus(id);
      return data;
    } catch (e) {
      return reply.code(502).send({ error: e instanceof Error ? e.message : String(e) });
    }
  });

  // -------- Recovery audio --------
  app.post("/v1/music/recovery", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const cost = await costFor("recovery_audio");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("recovery_audio", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "recovery_audio";
    job.credits = cost;
    const prompt = body.prompt as string | undefined;
    void runClipJobWithRetry(job, (client) => client.generateRecoveryAudio(clipId, prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- Timestamped lyrics + Lyrics detail --------
  app.get("/v1/lyrics/:id", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    const cost = await costFor("timestamped_lyrics_detail");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("timestamped_lyrics_detail");
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "timestamped_lyrics_detail";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.lyricsDetail(id));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- Detail GET routes for clip assets (all 1-credit details) --------
  function detailRoute(path: string, type: Job["type"], getter: (c: SunoClient, id: string) => Promise<unknown>) {
    app.get(path, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const { id } = req.params as { id: string };
      if (!id) return reply.code(400).send({ error: "id is required." });
      const cost = await costFor(type);
      if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

      const job = newJob(type);
      job.userId = key.user_id;
      job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      void runResultJobWithRetry(job, (client) => getter(client, id));
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  detailRoute("/v1/music/wav/:id", "wav_detail", (c, id) => c.wavDetail(id, "wav"));
  detailRoute("/v1/music/stems/:id", "stems_detail", (c, id) => c.stemsDetail(id));
  detailRoute("/v1/music/video/:id", "video_detail", (c, id) => c.videoDetail(id));
  detailRoute("/v1/music/cover/:id", "cover_detail", (c, id) => c.coverDetail(id));
  detailRoute("/v1/music/subtitle/:id", "subtitle_detail", (c, id) => c.subtitleDetail(id));
  detailRoute("/v1/music/recovery/:id", "recovery_detail", (c, id) => c.recoveryDetail(id));
  detailRoute("/v1/mp4/:id", "mp4_detail", (c, id) => c.mp4Detail(id));
  detailRoute("/v1/music/midi/:id", "midi_detail", (c, id) => c.midiDetail(id));
  detailRoute("/v1/clip/:id", "lyrics_detail", (c, id) => c.getClipDetail(id));

  // -------- MP4 generate POST + detail --------
  app.post("/v1/mp4/generate", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const cost = await costFor("mp4_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("mp4_generate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "mp4_generate";
    job.credits = cost;
    job.prompt = (body.prompt as string) || undefined;
    const prompt = body.prompt as string | undefined;
    const quantity = body.quantity ? Number(body.quantity) : undefined;
    const aspectRatio = body.aspect_ratio as string | undefined;
    void runResultJobWithRetry(job, (client) => client.generateMP4(clipId, { prompt, quantity, aspectRatio }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- Boost music style --------
  app.post("/v1/generate/boost", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    const stylePrompt = body.style_prompt as string;
    if (!clipId || !stylePrompt) {
      return reply.code(400).send({ error: "clip_id and style_prompt are required." });
    }
    const cost = await costFor("boost_style");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("boost_style", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "boost_style";
    job.credits = cost;
    job.prompt = stylePrompt;
    const startS = body.start_s ? Number(body.start_s) : undefined;
    const endS = body.end_s ? Number(body.end_s) : undefined;
    void runClipJobWithRetry(job, (client) => client.boostStyle(clipId, stylePrompt, { startS, endS }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- MIDI generate --------
  app.post("/v1/music/midi", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const cost = await costFor("midi_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("midi_generate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "midi_generate";
    job.credits = cost;
    const prompt = body.prompt as string | undefined;
    void runClipJobWithRetry(job, (client) => client.generateMIDI(clipId, prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- Suno Voice 6 operations --------
  app.post("/v1/voice/phrase", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const prompt = body.prompt as string;
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const cost = await costFor("voice_phrase");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_phrase", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_phrase";
    job.credits = cost;
    job.prompt = prompt;
    void runResultJobWithRetry(job, (client) => client.voicePhrase(prompt));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/voice/validate", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const uploadId = body.upload_id as string | undefined;
    const audioUrl = body.audio_url as string | undefined;
    if (!uploadId && !audioUrl) {
      return reply.code(400).send({ error: "upload_id or audio_url is required." });
    }
    const cost = await costFor("voice_validate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_validate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_validate";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceValidate({ uploadId, audioUrl }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/voice/record", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const extension = body.extension as string | undefined;
    if (!extension) return reply.code(400).send({ error: "extension is required (e.g. wav, mp3, m4a)." });
    const cost = await costFor("voice_record");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_record", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_record";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceRecord(extension));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/voice/generate", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    const name = body.name as string;
    if (!clipId || !name) return reply.code(400).send({ error: "clip_id and name are required." });
    const cost = await costFor("voice_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_generate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_generate";
    job.credits = cost;
    job.prompt = name;
    const styles = body.styles as string | undefined;
    void runResultJobWithRetry(
      job,
      (client) => client.voiceGenerate({ clipId, name, styles }),
      { policy: "paid_only" },
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/voice/apply", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const personaId = body.persona_id as string | undefined;
    const clipId = body.clip_id as string | undefined;
    if (!personaId && !clipId) {
      return reply.code(400).send({ error: "persona_id or clip_id is required." });
    }
    const cost = await costFor("voice_apply");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_apply", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_apply";
    job.credits = cost;
    job.prompt = (body.prompt as string) || undefined;
    const model = body.model as string | undefined;
    const vpolicy = model ? await routingPolicy(model) : "any";
    void runClipJobWithRetry(
      job,
      (client) =>
        client.voiceApply({
          personaId,
          clipId,
          prompt: body.prompt as string | undefined,
          title: body.title as string | undefined,
          tags: body.tags as string | undefined,
          model,
        }),
      { model, policy: vpolicy },
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/voice/extend", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const personaId = body.persona_id as string | undefined;
    const clipId = body.clip_id as string | undefined;
    if (!personaId && !clipId) {
      return reply.code(400).send({ error: "persona_id or clip_id is required." });
    }
    const cost = await costFor("voice_extend");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_extend", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_extend";
    job.credits = cost;
    job.prompt = (body.prompt as string) || undefined;
    const continueAt = body.continue_at ? Number(body.continue_at) : undefined;
    void runClipJobWithRetry(job, (client) =>
      client.voiceExtend({
        personaId,
        clipId,
        continueAt,
        prompt: body.prompt as string | undefined,
      }),
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // --- /api/v1/* Aliases ---------------------------------------------------
  // Exact URL-shape + payload parity with docs.sunoapi.org. Incoming requests
  // using `/api/v1/generate`, `/api/v1/get-credits`, etc. are transparently
  // translated to the same cost / job machinery used by our canonical `/v1/*`
  // surface above, so we 100% match both URL layout AND request body shapes
  // documented at docs.sunoapi.org (camelCase params, callBackUrl, etc.)
  const PREFIX = "/api/v1";

  function callbackUrl(in_: Record<string, unknown>): string | undefined {
    return ((in_.callBackUrl as string) || (in_.callback_url as string)) || undefined;
  }
  function translateBodyToMusic(
    in_: Record<string, unknown>,
  ): Record<string, unknown> {
    const prompt = (in_.prompt as string) || "";
    const customMode = Boolean(in_.customMode ?? in_.custom_mode ?? in_.defaultParamFlag);
    const style = ((in_.style as string) || (in_.tags as string)) || "";
    const title = (in_.title as string) || "";
    const out: Record<string, unknown> = {
      callback_url: callbackUrl(in_),
      model: (in_.model as string) || undefined,
      instrumental: Boolean(in_.instrumental ?? false),
      negative_tags:
        ((in_.negativeTags as string) || (in_.negative_tags as string)) || undefined,
      persona_id: ((in_.personaId as string) || (in_.persona_id as string)) || undefined,
      persona_model:
        ((in_.personaModel as string) || (in_.persona_model as string)) || undefined,
      duration: in_.duration != null ? Number(in_.duration) : undefined,
      vocal_gender: ((in_.vocalGender as string) || (in_.vocal_gender as string)) || undefined,
      style_weight:
        in_.styleWeight != null
          ? Number(in_.styleWeight)
          : in_.style_weight != null
            ? Number(in_.style_weight)
            : undefined,
      weirdness_constraint:
        in_.weirdnessConstraint != null
          ? Number(in_.weirdnessConstraint)
          : in_.weirdness_constraint != null
            ? Number(in_.weirdness_constraint)
            : undefined,
      audio_weight:
        in_.audioWeight != null
          ? Number(in_.audioWeight)
          : in_.audio_weight != null
            ? Number(in_.audio_weight)
            : undefined,
    };
    if (customMode) {
      out.prompt = prompt;
      out.tags = style;
      out.title = title;
    } else {
      const parts: string[] = [];
      if (title) parts.push(title);
      if (style) parts.push(`[genre: ${style}]`);
      if (prompt) parts.push(prompt);
      out.gpt_description_prompt = parts.join(" ") || prompt || undefined;
    }
    return out;
  }

  // GET /api/v1/get-credits
  app.get(`${PREFIX}/get-credits`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    return { code: 200, msg: "success", data: { credits: key.credits, name: key.name } };
  });
  // Alias: /v1/get-credits so both work
  app.get(`/v1/get-credits`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    return { code: 200, msg: "success", data: { credits: key.credits, name: key.name } };
  });

  // POST /api/v1/generate -> /v1/music (with payload translation)
  app.post(`${PREFIX}/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const inBody = (req.body ?? {}) as Record<string, unknown>;
    const body = translateBodyToMusic(inBody);
    if (!body.gpt_description_prompt && !body.prompt) {
      return reply.code(400).send({ error: "prompt is required." });
    }
    const cost = await costFor("music");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const callbackUrl = body.callback_url as string | undefined;
    const job = newJob("music", callbackUrl);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "music";
    job.model = (body.model as string) || undefined;
    job.prompt = (body.gpt_description_prompt ?? body.prompt) as string;
    job.credits = cost;
    const model = (body.model as string) || undefined;
    const policy = await routingPolicy(model);
    void runClipJobWithRetry(job, processMusicSubmit(body), { model, policy });
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/lyrics -> /v1/lyrics
  app.post(`${PREFIX}/lyrics`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { prompt, callBackUrl, callback_url } = (req.body ?? {}) as {
      prompt?: string;
      callBackUrl?: string;
      callback_url?: string;
    };
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const cost = await costFor("lyrics");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const job = newJob("lyrics", callBackUrl || callback_url);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "lyrics"; job.prompt = prompt; job.credits = cost;
    void runResultJobWithRetry(job, processLyricsSubmit(prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/extend -> /v1/music/extend
  app.post(`${PREFIX}/generate/extend`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const continue_at = in_.continueAt != null ? Number(in_.continueAt) : (in_.continue_at as number | undefined);
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("extend");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const callbackUrl = (in_.callBackUrl as string) || (in_.callback_url as string) || undefined;
    const job = newJob("extend", callbackUrl);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "extend"; job.credits = cost;
    void runClipJobWithRetry(job, (client) => client.extendMusic(clip_id, { continueAt: continue_at }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/vocal-removal/generate -> /v1/music/stems
  app.post(`${PREFIX}/vocal-removal/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("stems");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const job = newJob("stems", (in_.callBackUrl as string) || (in_.callback_url as string) || undefined);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "stems"; job.credits = cost;
    void runClipJobWithRetry(job, (client) => client.stems(clip_id));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // GET /api/v1/generate/record-info?taskId= -> /v1/task/:id
  function sunoRecordInfo(job: Job) {
    let status: "PENDING" | "GENERATING" | "SUCCESS" | "FAILED";
    if (job.status === "complete") status = "SUCCESS";
    else if (job.status === "error") status = "FAILED";
    else if (job.status === "running") status = "GENERATING";
    else status = "PENDING";
    return {
      code: 200,
      msg: "success",
      data: {
        taskId: job.id,
        status,
        errorMessage: job.error || undefined,
        response: job.result ? { data: Array.isArray(job.result) ? job.result : [job.result] } : undefined,
      },
    };
  }

  function recordInfoRoute(sunoPath: string) {
    app.get(`${PREFIX}${sunoPath}`, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const q = (req.query ?? {}) as { taskId?: string; task_id?: string };
      const id = q.taskId || q.task_id;
      if (!id) return reply.code(400).send({ error: "taskId is required." });
      const job = jobs.get(id) ?? (await loadJob(id));
      if (!job) return reply.code(404).send({ error: "task not found." });
      if (job.userId && job.userId !== key.user_id) return reply.code(403).send({ error: "forbidden." });
      return sunoRecordInfo(job);
    });
  }

  recordInfoRoute("/generate/record-info");
  recordInfoRoute("/cover-suno/record-info");
  recordInfoRoute("/cover/record-info");
  recordInfoRoute("/extend-upload/record-info");
  recordInfoRoute("/add-vocals/record-info");
  recordInfoRoute("/add-instrumental/record-info");
  recordInfoRoute("/music-remaster/record-info");
  recordInfoRoute("/convert-to-wav/record-info");
  recordInfoRoute("/vocal-removal/record-info");
  recordInfoRoute("/create-music-video/record-info");
  recordInfoRoute("/lyrics/record-info");
  recordInfoRoute("/generate-persona/record-info");
  recordInfoRoute("/generate/upload-cover/record-info");
  recordInfoRoute("/generate/upload-extend/record-info");
  recordInfoRoute("/generate/add-vocals/record-info");
  recordInfoRoute("/generate/add-instrumental/record-info");
  recordInfoRoute("/generate/boost/record-info");
  recordInfoRoute("/generate/mashup/record-info");
  recordInfoRoute("/generate/midi/record-info");
  recordInfoRoute("/generate/cover/record-info");
  recordInfoRoute("/generate/cover-image/record-info");
  recordInfoRoute("/generate/recovery/record-info");
  recordInfoRoute("/voice/record-info");

  // ============================================================
  // POST aliases for /api/v1/generate/* sub-paths
  // ============================================================

  // POST /api/v1/generate/upload-cover -> /v1/generate/upload-cover
  app.post(`${PREFIX}/generate/upload-cover`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const uploadedClipId = (in_.audioId as string) || (in_.uploaded_clip_id as string) || undefined;
    const audioUrl = (in_.audioUrl as string) || (in_.audio_url as string) || (in_.uploadUrl as string) || undefined;
    if (!uploadedClipId && !audioUrl) {
      return reply.code(400).send({ error: "audioId, uploaded_clip_id, audioUrl, or uploadUrl is required." });
    }
    const cost = await costFor("upload_cover");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("upload_cover", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "upload_cover"; job.credits = cost;
    job.model = (in_.model as string) || undefined;
    job.prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) =>
      client.uploadCoverMusic({
        uploadedClipId,
        audioUrl,
        coverStartS: in_.cover_start_s != null ? Number(in_.cover_start_s) : (in_.coverStartS as number | undefined),
        coverEndS: in_.cover_end_s != null ? Number(in_.cover_end_s) : (in_.coverEndS as number | undefined),
        prompt: (in_.prompt as string) || undefined,
        title: (in_.title as string) || undefined,
        tags: ((in_.style as string) || (in_.tags as string)) || undefined,
      }),
    );
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/upload-extend -> /v1/generate/upload-extend
  app.post(`${PREFIX}/generate/upload-extend`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const uploadedClipId = (in_.audioId as string) || (in_.uploaded_clip_id as string) || undefined;
    const audioUrl = (in_.audioUrl as string) || (in_.audio_url as string) || (in_.uploadUrl as string) || undefined;
    if (!uploadedClipId && !audioUrl) {
      return reply.code(400).send({ error: "audioId, uploaded_clip_id, audioUrl, or uploadUrl is required." });
    }
    const cost = await costFor("upload_extend");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("upload_extend", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "upload_extend"; job.credits = cost;
    job.model = (in_.model as string) || undefined;
    job.prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) =>
      client.uploadExtendMusic({
        uploadedClipId,
        audioUrl,
        continueAt: in_.continueAt != null ? Number(in_.continueAt) : (in_.continue_at as number | undefined),
        prompt: (in_.prompt as string) || undefined,
        title: (in_.title as string) || undefined,
        tags: ((in_.style as string) || (in_.tags as string)) || undefined,
      }),
    );
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/add-vocals -> /v1/music/add-vocals (uploadUrl-based variant)
  app.post(`${PREFIX}/generate/add-vocals`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || (in_.lyrics as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    if (!prompt) return reply.code(400).send({ error: "prompt (lyrics) is required for add-vocals." });
    const cost = await costFor("add_vocals");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("add_vocals", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "add_vocals"; job.credits = cost; job.prompt = prompt;
    void runClipJobWithRetry(job, (client) => client.addVocals(clip_id, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/add-instrumental -> /v1/music/add-instrumental
  app.post(`${PREFIX}/generate/add-instrumental`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || (in_.style as string) || (in_.tags as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    if (!prompt) return reply.code(400).send({ error: "prompt (style/tags) is required for add-instrumental." });
    const cost = await costFor("add_instrumental");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("add_instrumental", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "add_instrumental"; job.credits = cost; job.prompt = prompt;
    void runClipJobWithRetry(job, (client) => client.addInstrumental(clip_id, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/generate-persona -> /v1/persona/create
  app.post(`${PREFIX}/generate/generate-persona`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const name = (in_.name as string) || undefined;
    if (!clipId || !name) {
      return reply.code(400).send({ error: "audioId (clip_id) and name are required." });
    }
    const cost = await costFor("persona");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("persona", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "persona"; job.credits = cost; job.prompt = name;
    const description = (in_.description as string) || undefined;
    const styles = (in_.style as string) || undefined;
    const vocalStartS = in_.vocalStart != null
      ? Number(in_.vocalStart)
      : in_.vocalStartS != null
        ? Number(in_.vocalStartS)
        : in_.vocal_start_s != null
          ? Number(in_.vocal_start_s)
          : undefined;
    const vocalEndS = in_.vocalEnd != null
      ? Number(in_.vocalEnd)
      : in_.vocalEndS != null
        ? Number(in_.vocalEndS)
        : in_.vocal_end_s != null
          ? Number(in_.vocal_end_s)
          : undefined;
    void runResultJobWithRetry(job, (client) =>
      client.createPersona(clipId, name, styles, { description, vocalStartS, vocalEndS }),
    { policy: "paid_only" });
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/cover -> /v1/music/cover (style cover, NOT upload-cover)
  app.post(`${PREFIX}/generate/cover`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("cover");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("cover", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "cover"; job.credits = cost; job.prompt = prompt;
    void runClipJobWithRetry(job, (client) => client.coverMusic(clip_id, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/cover-image -> /v1/music/cover-image
  app.post(`${PREFIX}/generate/cover-image`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || undefined;
    if (!clipId || !prompt) return reply.code(400).send({ error: "audioId (clip_id) and prompt are required." });
    const cost = await costFor("cover_image");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("cover_image", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "cover_image"; job.credits = cost; job.prompt = prompt;
    void runResultJobWithRetry(job, (client) => client.generateCoverImage(clipId, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/convert-wav -> /v1/music/wav
  app.post(`${PREFIX}/generate/convert-wav`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("wav");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("wav", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "wav"; job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.downloadUrl(clip_id, (in_.format as string) || "wav"));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/boost -> /v1/generate/boost
  app.post(`${PREFIX}/generate/boost`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const stylePrompt = (in_.style_prompt as string) || (in_.prompt as string) || (in_.style as string) || undefined;
    if (!clipId || !stylePrompt) {
      return reply.code(400).send({ error: "audioId (clip_id) and style_prompt (prompt/style) are required." });
    }
    const cost = await costFor("boost_style");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("boost_style", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "boost_style"; job.credits = cost; job.prompt = stylePrompt;
    const startS = in_.start_s != null ? Number(in_.start_s) : (in_.startS as number | undefined);
    const endS = in_.end_s != null ? Number(in_.end_s) : (in_.endS as number | undefined);
    void runClipJobWithRetry(job, (client) => client.boostStyle(clipId, stylePrompt, { startS, endS }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/music-video -> /v1/mp4/generate
  app.post(`${PREFIX}/generate/music-video`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("mp4_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("mp4_generate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "mp4_generate"; job.credits = cost;
    const prompt = ((in_.style as string) || "") + ((in_.prompt as string) || "") || undefined;
    const quantity = in_.quantity != null ? Number(in_.quantity) : undefined;
    const aspectRatio = (in_.aspectRatio as string) || (in_.aspect_ratio as string) || undefined;
    void runResultJobWithRetry(job, (client) => client.generateMP4(clip_id, { prompt, quantity, aspectRatio }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/mashup -> /v1/music/mashup
  app.post(`${PREFIX}/generate/mashup`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipIds = in_.clip_ids as string[] | undefined;
    const audioIds = in_.audio_ids as string[] | undefined;
    const ids = clipIds ?? audioIds;
    if (!ids || !Array.isArray(ids) || ids.length < 2) {
      return reply.code(400).send({ error: "clip_ids (or audio_ids) array of 2+ is required." });
    }
    const cost = await costFor("mashup");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("mashup", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "mashup"; job.credits = cost;
    job.prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) => client.mashup(ids, (in_.prompt as string) || undefined));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/midi -> /v1/music/midi
  app.post(`${PREFIX}/generate/midi`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clipId) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("midi_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("midi_generate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "midi_generate"; job.credits = cost;
    const prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) => client.generateMIDI(clipId, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/recovery -> /v1/music/recovery
  app.post(`${PREFIX}/generate/recovery`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clipId) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("recovery_audio");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("recovery_audio", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "recovery_audio"; job.credits = cost;
    const prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) => client.generateRecoveryAudio(clipId, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // ============================================================
  // Existing /cover-suno/... and other alternate-shape routes below
  // ============================================================

  // POST /api/v1/cover-suno/generate -> /v1/music/cover (Cover Music)
  app.post(`${PREFIX}/cover-suno/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("cover");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("cover", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "cover"; job.credits = cost; job.prompt = prompt;
    void runClipJobWithRetry(job, (client) => client.coverMusic(clip_id, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/cover/generate -> /v1/generate/upload-cover (Upload and Cover Audio)
  app.post(`${PREFIX}/cover/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const uploadedClipId = (in_.audioId as string) || (in_.uploaded_clip_id as string) || undefined;
    const audioUrl = (in_.audioUrl as string) || (in_.audio_url as string) || undefined;
    if (!uploadedClipId && !audioUrl) {
      return reply.code(400).send({ error: "audioId or audioUrl is required." });
    }
    const cost = await costFor("upload_cover");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("upload_cover", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "upload_cover"; job.credits = cost;
    job.prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) =>
      client.uploadCoverMusic({
        uploadedClipId,
        audioUrl,
        coverStartS: in_.cover_start_s != null ? Number(in_.cover_start_s) : (in_.coverStartS as number | undefined),
        coverEndS: in_.cover_end_s != null ? Number(in_.cover_end_s) : (in_.coverEndS as number | undefined),
        prompt: (in_.prompt as string) || undefined,
        title: (in_.title as string) || undefined,
        tags: ((in_.style as string) || (in_.tags as string)) || undefined,
      }),
    );
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/extend-upload -> /v1/generate/upload-extend (Upload and Extend Audio)
  app.post(`${PREFIX}/extend-upload`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const uploadedClipId = (in_.audioId as string) || (in_.uploaded_clip_id as string) || undefined;
    const audioUrl = (in_.audioUrl as string) || (in_.audio_url as string) || undefined;
    if (!uploadedClipId && !audioUrl) {
      return reply.code(400).send({ error: "audioId or audioUrl is required." });
    }
    const cost = await costFor("upload_extend");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("upload_extend", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "upload_extend"; job.credits = cost;
    job.model = (in_.model as string) || undefined;
    job.prompt = (in_.prompt as string) || undefined;
    void runClipJobWithRetry(job, (client) =>
      client.uploadExtendMusic({
        uploadedClipId,
        audioUrl,
        continueAt: in_.continueAt != null ? Number(in_.continueAt) : (in_.continue_at as number | undefined),
        prompt: (in_.prompt as string) || undefined,
        title: (in_.title as string) || undefined,
        tags: ((in_.style as string) || (in_.tags as string)) || undefined,
      }),
    );
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/add-vocals/generate -> /v1/music/add-vocals
  app.post(`${PREFIX}/add-vocals/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || (in_.lyrics as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    if (!prompt) return reply.code(400).send({ error: "prompt (lyrics) is required for add-vocals." });
    const cost = await costFor("add_vocals");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("add_vocals", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "add_vocals"; job.credits = cost; job.prompt = prompt;
    void runClipJobWithRetry(job, (client) => client.addVocals(clip_id, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/add-instrumental/generate -> /v1/music/add-instrumental
  app.post(`${PREFIX}/add-instrumental/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const prompt = (in_.prompt as string) || (in_.style as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    if (!prompt) return reply.code(400).send({ error: "prompt (style) is required for add-instrumental." });
    const cost = await costFor("add_instrumental");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("add_instrumental", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "add_instrumental"; job.credits = cost; job.prompt = prompt;
    void runClipJobWithRetry(job, (client) => client.addInstrumental(clip_id, prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/music-remaster/generate -> /v1/music/remaster
  app.post(`${PREFIX}/music-remaster/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("remaster");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("remaster", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "remaster"; job.credits = cost;
    void runClipJobWithRetry(job, (client) => client.remaster(clip_id, (in_.model as string) || undefined));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/convert-to-wav/generate -> /v1/music/wav
  app.post(`${PREFIX}/convert-to-wav/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("wav");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("wav", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "wav"; job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.downloadUrl(clip_id, (in_.format as string) || "wav"));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/create-music-video/generate -> /v1/mp4/generate
  app.post(`${PREFIX}/create-music-video/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clip_id = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!clip_id) return reply.code(400).send({ error: "audioId (clip_id) is required." });
    const cost = await costFor("mp4_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("mp4_generate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "mp4_generate"; job.credits = cost;
    const prompt = ((in_.style as string) || "") + ((in_.prompt as string) || "") || undefined;
    const quantity = in_.quantity != null ? Number(in_.quantity) : undefined;
    const aspectRatio = (in_.aspectRatio as string) || (in_.aspect_ratio as string) || undefined;
    void runResultJobWithRetry(job, (client) => client.generateMP4(clip_id, { prompt, quantity, aspectRatio }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/lyrics/generate -> /v1/lyrics (secondary alias for sunoapi.org shape)
  app.post(`${PREFIX}/lyrics/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const prompt = in_.prompt as string | undefined;
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const cost = await costFor("lyrics");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("lyrics", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "lyrics"; job.prompt = prompt; job.credits = cost;
    void runResultJobWithRetry(job, processLyricsSubmit(prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // ============================================================
  // Upload 3-step aliases under /api/v1/
  // ============================================================

  // POST /api/v1/upload/init -> /v1/upload/init
  app.post(`${PREFIX}/upload/init`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const extension = in_.extension as string;
    if (!extension) return reply.code(400).send({ error: "extension is required (e.g. mp3, wav, m4a)." });
    const cost = await costFor("upload_init");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("upload_init", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "upload_init"; job.credits = cost;
    const uploadType = (in_.upload_type as "file_upload" | "voice_recording" | "song_demo") || undefined;
    const lastUploadId = (in_.last_upload_id as string) || (in_.lastUploadId as string) || undefined;
    void runResultJobWithRetry(job, (client) => client.createAudioUpload({ extension, uploadType, lastUploadId }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/upload/register -> /v1/upload/register
  app.post(`${PREFIX}/upload/register`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const uploadId = (in_.upload_id as string) || (in_.uploadId as string) || undefined;
    const uploadType = (in_.upload_type as string) || (in_.uploadType as string) || undefined;
    const uploadFilename = (in_.upload_filename as string) || (in_.uploadFilename as string) || undefined;
    if (!uploadId || !uploadType || !uploadFilename) {
      return reply.code(400).send({ error: "upload_id, upload_type and upload_filename are required." });
    }
    const cost = await costFor("upload_register");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("upload_register", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "upload_register"; job.credits = cost;
    const uploadTitle = ((in_.upload_title as string) || (in_.uploadTitle as string)) || undefined;
    void runResultJobWithRetry(job, (client) =>
      client.registerAudioUpload(uploadId, { uploadType, uploadFilename, uploadTitle }),
    );
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // GET /api/v1/upload/status/:id -> /v1/upload/status/:id (no job — direct proxy, allowed)
  app.get(`${PREFIX}/upload/status/:id`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    const client = await pool.pick();
    try {
      const data = await client.getAudioUploadStatus(id);
      return { code: 200, msg: "success", data };
    } catch (e) {
      return reply.code(502).send({ error: e instanceof Error ? e.message : String(e) });
    }
  });

  // GET /api/v1/lyrics/:id -> /v1/lyrics/:id (timestamped lyrics detail)
  app.get(`${PREFIX}/lyrics/:id`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });
    const cost = await costFor("timestamped_lyrics_detail");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const job = newJob("timestamped_lyrics_detail");
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "timestamped_lyrics_detail"; job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.lyricsDetail(id));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // ============================================================
  // Suno Voice aliases: /api/v1/voice/*
  // ============================================================

  // POST /api/v1/voice/phrase -> /v1/voice/phrase
  app.post(`${PREFIX}/voice/phrase`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const prompt = (in_.prompt as string) || undefined;
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const cost = await costFor("voice_phrase");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_phrase", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_phrase"; job.credits = cost; job.prompt = prompt;
    void runResultJobWithRetry(job, (client) => client.voicePhrase(prompt));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/voice/validate -> /v1/voice/validate
  app.post(`${PREFIX}/voice/validate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const uploadId = (in_.upload_id as string) || (in_.uploadId as string) || undefined;
    const audioUrl = (in_.audio_url as string) || (in_.audioUrl as string) || (in_.verifyUrl as string) || undefined;
    if (!uploadId && !audioUrl) {
      return reply.code(400).send({ error: "upload_id or audioUrl is required." });
    }
    const cost = await costFor("voice_validate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_validate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_validate"; job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceValidate({ uploadId, audioUrl }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/voice/record -> /v1/voice/record
  app.post(`${PREFIX}/voice/record`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const extension = (in_.extension as string) || undefined;
    if (!extension) return reply.code(400).send({ error: "extension is required (e.g. wav, mp3, m4a)." });
    const cost = await costFor("voice_record");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_record", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_record"; job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceRecord(extension));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/voice/generate -> /v1/voice/generate
  app.post(`${PREFIX}/voice/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId =
      (in_.clip_id as string) ||
      (in_.clipId as string) ||
      (in_.audio_id as string) ||
      (in_.audioId as string) ||
      undefined;
    const name = (in_.name as string) || (in_.voiceName as string) || undefined;
    if (!clipId || !name) return reply.code(400).send({ error: "clip_id (audioId) and name (voiceName) are required." });
    const cost = await costFor("voice_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_generate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_generate"; job.credits = cost; job.prompt = name;
    const styles = (in_.style as string) || (in_.styles as string) || undefined;
    const description = (in_.description as string) || undefined;
    const vocalStartS = in_.vocalStartS != null
      ? Number(in_.vocalStartS)
      : in_.vocal_start_s != null
        ? Number(in_.vocal_start_s)
        : undefined;
    const vocalEndS = in_.vocalEndS != null
      ? Number(in_.vocalEndS)
      : in_.vocal_end_s != null
        ? Number(in_.vocal_end_s)
        : undefined;
    void runResultJobWithRetry(job, (client) =>
      client.voiceGenerate({ clipId, name, styles, description, vocalStartS, vocalEndS }),
    { policy: "paid_only" });
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/voice/apply -> /v1/voice/apply
  app.post(`${PREFIX}/voice/apply`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const personaId = (in_.persona_id as string) || (in_.personaId as string) || undefined;
    const clipId = (in_.clip_id as string) || (in_.clipId as string) || undefined;
    if (!personaId && !clipId) return reply.code(400).send({ error: "persona_id or clip_id is required." });
    const cost = await costFor("voice_apply");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_apply", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_apply"; job.credits = cost;
    job.prompt = (in_.prompt as string) || undefined;
    const model = (in_.model as string) || undefined;
    const policy = model ? await routingPolicy(model) : "any";
    void runClipJobWithRetry(job, (client) =>
      client.voiceApply({
        personaId,
        clipId,
        prompt: in_.prompt as string | undefined,
        title: in_.title as string | undefined,
        tags: ((in_.style as string) || (in_.tags as string)) || undefined,
        model,
      }),
    { model, policy });
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/voice/extend -> /v1/voice/extend
  app.post(`${PREFIX}/voice/extend`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const personaId = (in_.persona_id as string) || (in_.personaId as string) || undefined;
    const clipId = (in_.clip_id as string) || (in_.clipId as string) || undefined;
    if (!personaId && !clipId) return reply.code(400).send({ error: "persona_id or clip_id is required." });
    const cost = await costFor("voice_extend");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_extend", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_extend"; job.credits = cost;
    job.prompt = (in_.prompt as string) || undefined;
    const continueAt = in_.continueAt != null
      ? Number(in_.continueAt)
      : in_.continue_at != null
        ? Number(in_.continue_at)
        : undefined;
    void runClipJobWithRetry(job, (client) =>
      client.voiceExtend({
        personaId,
        clipId,
        continueAt,
        prompt: in_.prompt as string | undefined,
      }),
    );
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // ============================================================
  // KHQR / Bakong Payment Endpoints
  // ============================================================

  function md5(str: string): string {
    return createHash("md5").update(str).digest("hex");
  }

  async function khqrGenerate(params: {
    amount: number;
    currency: "KHR" | "USD";
    billNumber: string;
    terminalLabel?: string;
    storeLabel?: string;
  }): Promise<{ qr: string; md5: string; deeplink?: string; mock: boolean }> {
    const { bakong } = config;
    const hasCreds = !!bakong.apiToken && !!bakong.accountId;

    if (!hasCreds) {
      const fakeQr = `00020101021229180014${bakong.accountId || "dev@bakong"}520459995303${params.currency === "KHR" ? "116" : "840"}540${String(params.amount).length}${params.amount}5802KH59${bakong.merchantName.length.toString().padStart(2, "0")}${bakong.merchantName}60${bakong.merchantCity.length.toString().padStart(2, "0")}${bakong.merchantCity}62${(2 + params.billNumber.length).toString().padStart(2, "0")}01${params.billNumber.length.toString().padStart(2, "0")}${params.billNumber}99170013${Date.now()}63040000`;
      return {
        qr: fakeQr,
        md5: md5(fakeQr),
        deeplink: `https://bakong.page.link/mock?qr=${encodeURIComponent(fakeQr)}`,
        mock: true,
      };
    }

    try {
      const mod = await import("bakong-khqr-npm");
      const KHQR = (mod as { KHQR: new (t: string) => unknown }).KHQR;
      const khqr = new KHQR(bakong.apiToken) as {
        create_qr: (p: Record<string, unknown>) => string;
        generate_md5: (qr: string) => string;
        generate_deeplink: (qr: string, cb: string, icon: string, name: string) => Promise<string>;
      };
      const qr = khqr.create_qr({
        bank_account: bakong.accountId,
        merchant_name: bakong.merchantName,
        merchant_city: bakong.merchantCity,
        amount: params.amount,
        currency: params.currency,
        store_label: params.storeLabel || "Camxora",
        phone_number: "",
        bill_number: params.billNumber,
        terminal_label: params.terminalLabel || "web",
        static: false,
      });
      const hash = khqr.generate_md5(qr);
      let deeplink: string | undefined;
      try {
        deeplink = await khqr.generate_deeplink(
          qr,
          typeof window !== "undefined" ? window.location.origin : "",
          "",
          "Camxora",
        );
      } catch {
        /* ignore */
      }
      return { qr, md5: hash, deeplink, mock: false };
    } catch (e) {
      const fakeQr = `00020101021229180014${bakong.accountId}520459995303${params.currency === "KHR" ? "116" : "840"}540${String(params.amount).length}${params.amount}5802KH59${bakong.merchantName.length.toString().padStart(2, "0")}${bakong.merchantName}60${bakong.merchantCity.length.toString().padStart(2, "0")}${bakong.merchantCity}62${(2 + params.billNumber.length).toString().padStart(2, "0")}01${params.billNumber.length.toString().padStart(2, "0")}${params.billNumber}99170013${Date.now()}63040000`;
      return {
        qr: fakeQr,
        md5: md5(fakeQr),
        mock: true,
      };
    }
  }

  async function khqrCheck(hash: string): Promise<"PAID" | "UNPAID" | "EXPIRED"> {
    const { bakong } = config;
    const hasCreds = !!bakong.apiToken;
    if (!hasCreds) return "UNPAID";
    try {
      const mod = await import("bakong-khqr-npm");
      const KHQR = (mod as { KHQR: new (t: string) => unknown }).KHQR;
      const khqr = new KHQR(bakong.apiToken) as {
        check_payment: (md5: string) => Promise<string>;
      };
      const status = await khqr.check_payment(hash);
      if (status === "PAID") return "PAID";
      if (status === "UNPAID") return "UNPAID";
      return "UNPAID";
    } catch {
      return "UNPAID";
    }
  }

  async function creditUser(
    user: UserPayload,
    amount: number,
    apiKeyId?: string,
    txId?: string,
    source = "KHQR",
    client?: PoolClient,
  ): Promise<void> {
    // Run every statement on the caller's transaction client when supplied, so
    // the credit increment and its ledger row commit (or roll back) together.
    const run = async <T>(text: string, params: unknown[] = []): Promise<T[]> => {
      if (client) {
        const res = await client.query(text, params);
        return res.rows as T[];
      }
      return query<T>(text, params);
    };
    if (apiKeyId) {
      await run(
        "UPDATE api_keys SET credits = credits + $1 WHERE id = $2 AND user_id = $3",
        [amount, apiKeyId, user.id],
      );
    } else {
      const keys = await run<{ id: string }>(
        "SELECT id FROM api_keys WHERE user_id = $1 AND is_active = true ORDER BY created_at ASC LIMIT 1",
        [user.id],
      );
      if (keys.length === 0) {
        await run(
          `INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits) VALUES ($1, $2, $3, $4, $5)`,
          [user.id, "Auto-Created Key", md5(randomUUID() + Date.now()), "auto_" + randomUUID().slice(0, 5), amount],
        );
      } else {
        await run(
          "UPDATE api_keys SET credits = credits + $1 WHERE id = $2",
          [amount, keys[0].id],
        );
      }
    }
    await run(
      `INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'purchase', $3)`,
      [user.id, amount, txId ? `${source} top-up (ref: ${txId})` : `${source} top-up`],
    );
  }

  /**
   * Idempotently mark a KHQR transaction paid and credit the buyer. The
   * conditional UPDATE claims the pending→paid transition atomically, and the
   * credit + ledger write run on the same transaction, so concurrent status
   * polls (or a poll racing the dev confirm-mock) can never double-credit.
   * Returns false when the payment was already settled (or is no longer pending).
   * On credit failure the whole transaction (including the claim) rolls back and
   * the error is rethrown for the caller to record.
   */
  async function fulfillKhqr(tx: {
    id: string; user_id: string; credit_amount: number; api_key_target_id: string | null;
  }): Promise<boolean> {
    return withTransaction(async (client) => {
      const claimed = await client.query<{ id: string }>(
        `UPDATE payment_transactions SET status = 'paid', paid_at = now()
         WHERE id = $1 AND status = 'pending' RETURNING id`,
        [tx.id],
      );
      if (claimed.rows.length === 0) return false;
      await creditUser(
        { id: tx.user_id, email: "", role: "user" },
        tx.credit_amount,
        tx.api_key_target_id ?? undefined,
        tx.id,
        "KHQR",
        client,
      );
      return true;
    });
  }

  // GET /me/transactions — list payment transactions
  app.get("/me/transactions", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const rows = await query(
      `SELECT id, credit_amount, currency, amount, payment_method, status, bill_number, md5_hash, paid_at, expires_at, created_at
       FROM payment_transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50`,
      [u.id],
    );
    return rows;
  });

  // POST /payments/khqr/create — create a KHQR payment for a credit pack
  app.post("/payments/khqr/create", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const packId = in_.pack_id as string | undefined;
    const currency = ((in_.currency as string) || "KHR").toUpperCase() as "KHR" | "USD";
    const targetKeyId = in_.api_key_id as string | undefined;

    if (!packId) return reply.code(400).send({ error: "pack_id is required." });

    const pack = await queryOne<{ id: string; amount: number; price: string; currency: string }>(
      "SELECT id, amount, price, currency FROM credit_packs WHERE id = $1 AND is_active = true",
      [packId],
    );
    if (!pack) return reply.code(404).send({ error: "Pack not found or unavailable." });

    const priceAmount = currency === pack.currency
      ? Number(pack.price)
      : currency === "KHR"
        ? Math.round(Number(pack.price) * 4100) // approx 1 USD = 4100 KHR
        : Math.round((Number(pack.price) * 4100)) / 4100;

    if (!priceAmount || priceAmount <= 0) return reply.code(400).send({ error: "Invalid price for selected currency." });

    const billNumber = `CMX${Date.now().toString(36).toUpperCase()}${randomUUID().slice(0, 4).toUpperCase()}`;

    const generated = await khqrGenerate({
      amount: priceAmount,
      currency,
      billNumber,
      storeLabel: "Camxora",
      terminalLabel: "web",
    });

    const expiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();

    const inserted = await queryOne<{ id: string }>(
      `INSERT INTO payment_transactions
         (user_id, pack_id, credit_amount, currency, amount, payment_method, md5_hash, qr_string, deeplink, status, api_key_target_id, bill_number, expires_at)
       VALUES ($1, $2, $3, $4, $5, 'khqr', $6, $7, $8, 'pending', $9, $10, $11)
       RETURNING id`,
      [u.id, packId, pack.amount, currency, priceAmount, generated.md5, generated.qr, generated.deeplink || null, targetKeyId || null, billNumber, expiresAt],
    );

    return {
      transaction_id: inserted?.id,
      bill_number: billNumber,
      credits: pack.amount,
      currency,
      amount: priceAmount,
      qr: generated.qr,
      md5: generated.md5,
      deeplink: generated.deeplink || null,
      expires_at: expiresAt,
      mock: generated.mock,
      merchant_name: config.bakong.merchantName,
      merchant_city: config.bakong.merchantCity,
    };
  });

  // GET /payments/khqr/status/:id — check KHQR payment status and credit user if paid
  app.get("/payments/khqr/status/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });

    const tx = await queryOne<{
      id: string; user_id: string; status: string; md5_hash: string | null; expires_at: string; credit_amount: number;
      api_key_target_id: string | null; error_message: string | null; paid_at: string | null;
      amount: string; currency: string; bill_number: string;
    }>(
      `SELECT id, user_id, status, md5_hash, expires_at, credit_amount, api_key_target_id, error_message, paid_at, amount, currency, bill_number
       FROM payment_transactions WHERE id = $1 AND user_id = $2`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });

    let currentStatus = tx.status;
    const expired = new Date(tx.expires_at).getTime() < Date.now();

    if (currentStatus === "pending") {
      if (expired) {
        await query("UPDATE payment_transactions SET status = 'expired' WHERE id = $1", [tx.id]);
        currentStatus = "expired";
      } else if (tx.md5_hash) {
        const bakongStatus = await khqrCheck(tx.md5_hash);
        if (bakongStatus === "PAID") {
          try {
            const settled = await fulfillKhqr(tx);
            if (settled) {
              currentStatus = "paid";
            } else {
              // A concurrent poll already claimed the transition — report the
              // persisted state instead of this stale "pending" snapshot.
              const fresh = await queryOne<{ status: string; paid_at: string | null }>(
                "SELECT status, paid_at FROM payment_transactions WHERE id = $1",
                [tx.id],
              );
              currentStatus = fresh?.status ?? currentStatus;
              tx.paid_at = fresh?.paid_at ?? tx.paid_at;
            }
          } catch (e) {
            const err = e instanceof Error ? e.message : String(e);
            await query(
              "UPDATE payment_transactions SET status = 'failed', error_message = $1 WHERE id = $2",
              [err, tx.id],
            );
            currentStatus = "failed";
          }
        }
      }
    }

    return {
      transaction_id: tx.id,
      status: currentStatus,
      bill_number: tx.bill_number,
      credits: tx.credit_amount,
      currency: tx.currency,
      amount: Number(tx.amount),
      paid_at: tx.paid_at,
      expires_at: tx.expires_at,
      error: tx.error_message,
      expired: currentStatus === "expired" ? true : expired && currentStatus === "pending",
    };
  });

  // POST /payments/khqr/confirm-mock/:id — DEV-ONLY: force-complete a pending
  // payment. Disabled outside NODE_ENV=development so it can never mint free
  // credits in production (previously it activated whenever Bakong was unset).
  app.post("/payments/khqr/confirm-mock/:id", async (req, reply) => {
    if (process.env.NODE_ENV !== "development") {
      return reply.code(404).send({ error: "Not found." });
    }
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });

    const tx = await queryOne<{
      id: string; user_id: string; status: string; credit_amount: number; api_key_target_id: string | null;
    }>(
      `SELECT id, user_id, status, credit_amount, api_key_target_id FROM payment_transactions WHERE id = $1 AND user_id = $2`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });
    if (tx.status !== "pending") return reply.code(409).send({ error: `Transaction already ${tx.status}.` });
    try {
      const settled = await fulfillKhqr(tx);
      if (!settled) return reply.code(409).send({ error: "Transaction already settled." });
      return { ok: true, status: "paid" };
    } catch (e) {
      return reply.code(500).send({ error: e instanceof Error ? e.message : String(e) });
    }
  });

  // ============================================================
  // ChmabaPay Checkout Gateway Endpoints (https://pay.chmaba.com)
  // ============================================================

  const CHAMPAPAY_PAID_STATUSES = new Set(["paid", "completed", "approved", "succeeded", "success"]);
  const CHAMPAPAY_FAILED_STATUSES = new Set(["failed", "cancelled", "canceled", "declined"]);
  // `superseded` is a code replaced by a reissue — dead and never payable.
  // `reversed` is a settled payment that was refunded (bookkeeping only).
  const CHAMPAPAY_EXPIRED_STATUSES = new Set(["expired", "superseded"]);

  async function champapayRequest<T>(path: string, method: string, body?: unknown): Promise<T> {
    const base = config.champapay.apiBaseUrl.replace(/\/+$/, "");
    const res = await fetch(`${base}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${config.champapay.apiKey}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let json: unknown = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      /* non-JSON response */
    }
    if (!res.ok) {
      const detail = json as { error?: string; message?: string } | null;
      const msg = detail?.error ?? detail?.message ?? `ChmabaPay request failed (${res.status}).`;
      throw new Error(typeof msg === "string" ? msg : `ChmabaPay request failed (${res.status}).`);
    }
    return json as T;
  }

  /** Verify `X-ChmabaPay-Signature: t=<unix>,v1=<hex>` over the raw request body. */
  function verifyChampapaySignature(raw: Buffer, header: string, secret: string): boolean {
    let timestamp = "";
    let signature = "";
    for (const part of header.split(",")) {
      const idx = part.indexOf("=");
      if (idx === -1) continue;
      const key = part.slice(0, idx).trim();
      const val = part.slice(idx + 1).trim();
      if (key === "t") timestamp = val;
      else if (key === "v1") signature = val;
    }
    if (!timestamp || !signature) return false;
    const ts = Number(timestamp);
    if (!Number.isFinite(ts) || Math.abs(Date.now() / 1000 - ts) > 300) return false;
    const expected = createHmac("sha256", secret).update(`${timestamp}.`).update(raw).digest("hex");
    const a = Buffer.from(expected, "utf8");
    const b = Buffer.from(signature, "utf8");
    return a.length === b.length && timingSafeEqual(a, b);
  }

  /**
   * Idempotently mark a transaction paid and credit the buyer. The conditional
   * UPDATE claims the transition atomically so duplicate webhooks/polls cannot
   * double-credit. Returns false when the payment was already settled.
   */
  async function fulfillChampapay(
    tx: { id: string; user_id: string; credit_amount: number; api_key_target_id: string | null },
    eventId?: string,
  ): Promise<boolean> {
    const claimed = await queryOne<{ id: string }>(
      `UPDATE payment_transactions
         SET status = 'paid', paid_at = now(), webhook_event_id = COALESCE($2::text, webhook_event_id)
       WHERE id = $1 AND status <> 'paid'
       RETURNING id`,
      [tx.id, eventId ?? null],
    );
    if (!claimed) return false;
    try {
      await creditUser(
        { id: tx.user_id, email: "", role: "user" },
        tx.credit_amount,
        tx.api_key_target_id ?? undefined,
        tx.id,
        "ChmabaPay",
      );
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      await query("UPDATE payment_transactions SET status = 'failed', error_message = $1 WHERE id = $2", [err, tx.id]);
      throw e;
    }
    return true;
  }

  // POST /payments/champapay/create — create a checkout via the gateway
  app.post("/payments/champapay/create", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    if (!config.champapay.apiKey || !config.champapay.storeId) {
      return reply.code(503).send({ error: "ChmabaPay is not configured." });
    }
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const packId = in_.pack_id as string | undefined;
    const targetKeyId = in_.api_key_id as string | undefined;

    if (!packId) return reply.code(400).send({ error: "pack_id is required." });

    const pack = await queryOne<{ id: string; amount: number; price: string; currency: string }>(
      "SELECT id, amount, price, currency FROM credit_packs WHERE id = $1 AND is_active = true",
      [packId],
    );
    if (!pack) return reply.code(404).send({ error: "Pack not found or unavailable." });

    // The gateway settles in USD; convert KHR packs at the same fixed rate the
    // KHQR flow uses (approx 1 USD = 4100 KHR).
    const usdAmount = pack.currency.toUpperCase() === "USD"
      ? Number(pack.price)
      : Math.round((Number(pack.price) / 4100) * 100) / 100;
    if (!usdAmount || usdAmount < 0.01) {
      return reply.code(400).send({ error: "Pack price is below the gateway minimum (0.01 USD)." });
    }

    const referenceId = `cmx:musicapi:${u.id}:${randomUUID().slice(0, 12)}`;

    let payment: {
      id?: string; status?: string; qr_string?: string; checkout_url?: string;
      url?: string; expires_at?: string;
    };
    try {
      payment = await champapayRequest("/v1/payments", "POST", {
        amount: usdAmount,
        reference_id: referenceId,
        idempotency_key: referenceId,
        store: config.champapay.storeId,
        metadata: {
          user_id: u.id,
          pack_id: pack.id,
          credits: String(pack.amount),
          api_key_id: targetKeyId ?? "",
        },
      });
    } catch (e) {
      return reply.code(502).send({ error: e instanceof Error ? e.message : String(e) });
    }

    if (!payment.id) return reply.code(502).send({ error: "ChmabaPay did not return a payment id." });

    const checkoutUrl = payment.checkout_url ?? payment.url ?? null;
    const expiresAt = payment.expires_at
      ? new Date(payment.expires_at).toISOString()
      : new Date(Date.now() + 10 * 60 * 1000).toISOString();

    const inserted = await queryOne<{ id: string }>(
      `INSERT INTO payment_transactions
         (user_id, pack_id, credit_amount, currency, amount, payment_method, qr_string, deeplink, status, api_key_target_id, bill_number, expires_at, gateway_payment_id)
       VALUES ($1, $2, $3, 'USD', $4, 'champapay', $5, $6, 'pending', $7, $8, $9, $10)
       RETURNING id`,
      [u.id, pack.id, pack.amount, usdAmount, payment.qr_string ?? null, checkoutUrl, targetKeyId ?? null, referenceId, expiresAt, payment.id],
    );

    return {
      transaction_id: inserted?.id,
      reference_id: referenceId,
      bill_number: referenceId,
      credits: pack.amount,
      currency: "USD",
      amount: usdAmount,
      qr: payment.qr_string ?? null,
      checkout_url: checkoutUrl,
      status: payment.status ?? "pending",
      expires_at: expiresAt,
      gateway_payment_id: payment.id,
    };
  });

  // GET /payments/champapay/status/:id — poll the gateway and credit if paid
  app.get("/payments/champapay/status/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });

    const tx = await queryOne<{
      id: string; user_id: string; status: string; gateway_payment_id: string | null; expires_at: string;
      credit_amount: number; api_key_target_id: string | null; error_message: string | null; paid_at: string | null;
      amount: string; currency: string; bill_number: string;
    }>(
      `SELECT id, user_id, status, gateway_payment_id, expires_at, credit_amount, api_key_target_id, error_message, paid_at, amount, currency, bill_number
       FROM payment_transactions WHERE id = $1 AND user_id = $2 AND payment_method = 'champapay'`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });

    let currentStatus = tx.status;
    const expired = new Date(tx.expires_at).getTime() < Date.now();

    if (currentStatus === "pending") {
      if (expired) {
        await query("UPDATE payment_transactions SET status = 'expired' WHERE id = $1 AND status = 'pending'", [tx.id]);
        currentStatus = "expired";
      } else if (tx.gateway_payment_id && config.champapay.apiKey) {
        try {
          const remote = await champapayRequest<{ status?: string }>(
            `/v1/payments/${encodeURIComponent(tx.gateway_payment_id)}`,
            "GET",
          );
          const remoteStatus = (remote.status ?? "").toLowerCase();
          if (CHAMPAPAY_PAID_STATUSES.has(remoteStatus)) {
            await fulfillChampapay(tx);
            currentStatus = "paid";
          } else if (CHAMPAPAY_FAILED_STATUSES.has(remoteStatus)) {
            await query("UPDATE payment_transactions SET status = 'failed' WHERE id = $1 AND status = 'pending'", [tx.id]);
            currentStatus = "failed";
          } else if (CHAMPAPAY_EXPIRED_STATUSES.has(remoteStatus)) {
            await query("UPDATE payment_transactions SET status = 'expired' WHERE id = $1 AND status = 'pending'", [tx.id]);
            currentStatus = "expired";
          }
        } catch {
          /* transient gateway error — leave the transaction pending */
        }
      }
    }

    return {
      transaction_id: tx.id,
      status: currentStatus,
      bill_number: tx.bill_number,
      credits: tx.credit_amount,
      currency: tx.currency,
      amount: Number(tx.amount),
      paid_at: tx.paid_at,
      expires_at: tx.expires_at,
      error: tx.error_message,
      expired: currentStatus === "expired",
    };
  });

  // POST /payments/champapay/webhook — signature-verified, idempotent fulfillment
  app.post("/payments/champapay/webhook", async (req, reply) => {
    const secret = config.champapay.webhookSecret;
    if (!secret) return reply.code(503).send({ error: "ChmabaPay webhook is not configured." });

    const raw = (req as FastifyRequest & { rawBody?: Buffer }).rawBody
      ?? Buffer.from(JSON.stringify(req.body ?? {}), "utf8");
    const signatureHeader = String(req.headers["x-chmabapay-signature"] ?? "");
    const eventHeader = String(req.headers["x-chmabapay-event"] ?? "");

    if (!verifyChampapaySignature(raw, signatureHeader, secret)) {
      return reply.code(401).send({ error: "Invalid signature." });
    }

    const payload = (req.body ?? {}) as {
      id?: string;
      type?: string;
      data?: { payment?: { id?: string; status?: string; reference_id?: string } };
    };
    const payment = payload.data?.payment ?? {};
    const eventType = (eventHeader || payload.type || "").toLowerCase();
    const gatewayId = payment.id;
    const referenceId = payment.reference_id;

    if (!gatewayId && !referenceId) return { ok: true, ignored: true };

    const tx = await queryOne<{
      id: string; user_id: string; status: string; credit_amount: number; api_key_target_id: string | null;
    }>(
      `SELECT id, user_id, status, credit_amount, api_key_target_id
       FROM payment_transactions
       WHERE gateway_payment_id = $1 OR bill_number = $2
       ORDER BY created_at DESC LIMIT 1`,
      [gatewayId ?? null, referenceId ?? null],
    );
    if (!tx) return { ok: true, ignored: true };

    const status = (payment.status ?? "").toLowerCase();
    const isPaid = eventType === "payment.completed" || CHAMPAPAY_PAID_STATUSES.has(status);
    const isFailed = eventType === "payment.failed" || CHAMPAPAY_FAILED_STATUSES.has(status);
    const isExpired = eventType === "payment.expired" || CHAMPAPAY_EXPIRED_STATUSES.has(status);
    const isReversed = eventType === "payment.reversed" || status === "reversed";

    if (isPaid) {
      try {
        await fulfillChampapay(tx, payload.id);
      } catch (e) {
        return reply.code(500).send({ error: e instanceof Error ? e.message : String(e) });
      }
    } else if (isFailed) {
      await query("UPDATE payment_transactions SET status = 'failed' WHERE id = $1 AND status = 'pending'", [tx.id]);
    } else if (isExpired) {
      await query("UPDATE payment_transactions SET status = 'expired' WHERE id = $1 AND status = 'pending'", [tx.id]);
    } else if (isReversed) {
      await query("UPDATE payment_transactions SET status = 'refunded' WHERE id = $1 AND status = 'paid'", [tx.id]);
    }

    return { ok: true };
  });

  return app;
}
