import Fastify, { FastifyInstance, FastifyRequest, FastifyReply, FastifyServerOptions } from "fastify";
import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import rateLimit from "@fastify/rate-limit";
import multipart from "@fastify/multipart";
import { createHash, createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { AccountPool, RoutingPolicy } from "./pool.js";
import { SunoClient } from "./client.js";
import { encryptCookie } from "./cookieCrypto.js";
import { query, queryOne, withTransaction, type QueryFn } from "./db.js";
import { hashPassword, verifyPassword, signToken, verifyToken, signOAuthState, verifyOAuthState, UserPayload, SESSION_COOKIE_ADMIN, serializeSessionCookie, serializeClearedSessionCookie, readSessionCookie } from "./appAuth.js";
import { OAuth2Client } from "google-auth-library";
import { config, isProduction } from "./config.js";
import { maskedIntegrations, updateIntegrations } from "./runtimeSettings.js";
import { assertCallbackUrlAllowed, CallbackUrlError, isCallbackSentinel } from "./callbackUrl.js";
import { createJobQueue } from "./jobQueue.js";
import { ConcurrencyGate, QueueFullError } from "./concurrency.js";
import { defaultRoutingPolicy, normalizeModel } from "./models.js";
import { getObjectBytes, getReadUrl, objectExists, objectKey, putObject, storageConfigured } from "./storage.js";
import { extractVideoFrame } from "./video.js";
import { transcodeAudio, pickPublicAudioUrl } from "./audio.js";
import { renderMusicVideo } from "./video.js";
import { decryptSunoClip, openDecryptedM4aStream } from "./sunoAudio.js";
import { JOB_OPS, isRunnableDescriptor, type JobDescriptor } from "./jobOps.js";
import {
  alignedLinesToLrc,
  alignedWordsToLrc,
  parseAlignedWordsPayload,
  type AlignedLine,
  type AlignedWord,
} from "./lrc.js";

// Fallback credit costs when the `pricing` table has no row for an endpoint.
// Real costs are read from the DB and configurable in the admin panel.
const DEFAULT_COSTS: Record<string, number> = {
  lyrics: 0,
  music: 10,
  extend: 10,
  cover: 10,
  stems: 8,
  stems_split: 20,
  stems_advanced: 12,
  sounds: 3,
  remaster: 10,
  mashup: 10,
  add_vocals: 10,
  add_instrumental: 10,
  replace_section: 9,
  cover_image: 0,
  persona: 0,
  // WAV is download-only: the conversion routes only resolve a signed URL, and
  // the bytes are paid for by `wav_download` on GET /me/download.
  wav: 0,
  // Audio delivery via GET /me/download, priced per format at /admin/pricing.
  mp3_download: 0,
  wav_download: 0,
  upload_extend: 10,
  upload_cover: 10,
  upload_init: 1,
  upload_register: 1,
  recovery_audio: 10,
  mp4_generate: 2,
  boost_style: 0,
  midi_generate: 3,
  voice_phrase: 1,
  voice_validate: 1,
  voice_record: 1,
  voice_generate: 10,
  voice_apply: 10,
  voice_extend: 10,
  lyrics_detail: 0,
  wav_detail: 0,
  stems_detail: 0,
  video_detail: 0,
  cover_detail: 0,
  subtitle_detail: 0,
  recovery_detail: 0,
  mp4_detail: 0,
  midi_detail: 0,
  timestamped_lyrics_detail: 0,
};

export interface ApiKey {
  key: string;
  name: string;
  credits: number;
}

/**
 * Operator-managed panel branding and support links (task 5.5, REQUIREMENTS
 * §4.10). Stored as a JSONB document under the `brand` key of `app_settings`.
 */
export interface BrandSettings {
  name: string;
  docs_url: string;
  support_telegram_url: string;
  languages: string[];
}

/**
 * Thresholds/switches for the alerts the admin panel surfaces (task 5.5,
 * REQUIREMENTS §4.10): Suno accounts running low on credits, a captcha that
 * cannot actually be solved (no 2Captcha key, or a drained balance), a spike in
 * the job failure rate, and a backlog of jobs waiting for a Suno concurrency
 * slot. A captcha challenge is only an alert when it is actionable — while a
 * funded solver is configured, the worker solves it automatically at generation
 * time.
 */
export interface AlertSettings {
  enabled: boolean;
  low_credits_threshold: number;
  /** Alert when the 2Captcha balance (USD) is at or below this. 0 disables. */
  captcha_balance_threshold: number;
  failure_rate_threshold: number;
  failure_rate_min_requests: number;
  window_minutes: number;
  /**
   * Alert when this many jobs are waiting for a Suno slot. `0` disables the
   * check. Guards against the pool being saturated (a growing backlog means the
   * account pool can't keep up with demand).
   */
  queue_backlog_depth: number;
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
  captcha_balance_threshold: 1,
  failure_rate_threshold: 0.25,
  failure_rate_min_requests: 20,
  window_minutes: 60,
  queue_backlog_depth: 50,
};

/**
 * Error written when a job still `pending`/`running`/`streaming` at process
 * shutdown is failed out by `recoverJobs()` on the next boot. It is an
 * operator/deploy artifact (a deploy restarts the process; the memory queue
 * cannot re-run descriptor-less jobs), not a generation failure, so the
 * failure-rate alert excludes it — otherwise every deploy pages ops as the
 * interrupted jobs sit in the 60-minute window. The raw count is still recorded
 * in `usage_logs` and shown in the user/admin dashboards.
 */
const RESTART_INTERRUPT_ERROR = "Interrupted by server restart.";

/**
 * Normalize an operator-entered Telegram support value into an absolute https
 * URL. Operators commonly paste a bare handle (`@name` or `name`); used as an
 * `href` the browser resolves that relative to the panel origin, so "Get
 * Support" points back at the site (e.g. `/@name`) instead of Telegram. Accept
 * a full http(s) URL or scheme-less `t.me/...` as-is, otherwise treat the value
 * as a handle.
 */
function normalizeTelegramUrl(raw: string): string {
  const value = raw.trim();
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value;
  if (/^(t\.me|telegram\.me)\//i.test(value)) return `https://${value}`;
  const handle = value.replace(/^@+/, "").trim();
  return handle ? `https://t.me/${handle}` : "";
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
      typeof o.support_telegram_url === "string"
        ? normalizeTelegramUrl(o.support_telegram_url)
        : DEFAULT_BRAND.support_telegram_url,
    languages: languages.length ? languages : [...DEFAULT_BRAND.languages],
  };
}

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

function clampInt(value: unknown, fallback: number, min: number, max: number): number {
  return Math.round(clampNumber(value, fallback, min, max));
}

/** Normalize a stored/upstream `alerts` document with the same defensiveness. */
function coerceAlerts(value: unknown): AlertSettings {
  const o = (value ?? {}) as Record<string, unknown>;
  return {
    enabled: typeof o.enabled === "boolean" ? o.enabled : DEFAULT_ALERTS.enabled,
    low_credits_threshold: clampInt(o.low_credits_threshold, DEFAULT_ALERTS.low_credits_threshold, 0, 1_000_000),
    captcha_balance_threshold: clampNumber(
      o.captcha_balance_threshold,
      DEFAULT_ALERTS.captcha_balance_threshold,
      0,
      100_000,
    ),
    failure_rate_threshold: clampNumber(o.failure_rate_threshold, DEFAULT_ALERTS.failure_rate_threshold, 0, 1),
    failure_rate_min_requests: clampInt(
      o.failure_rate_min_requests,
      DEFAULT_ALERTS.failure_rate_min_requests,
      1,
      1_000_000,
    ),
    window_minutes: clampInt(o.window_minutes, DEFAULT_ALERTS.window_minutes, 5, 1440),
    queue_backlog_depth: clampInt(
      o.queue_backlog_depth,
      DEFAULT_ALERTS.queue_backlog_depth,
      0,
      1_000_000,
    ),
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
    next.support_telegram_url = normalizeTelegramUrl(o.support_telegram_url);
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
  for (const key of ["enabled"] as const) {
    if (o[key] !== undefined) {
      if (typeof o[key] !== "boolean") return { ok: false, error: `alerts.${key} must be a boolean.` };
      next[key] = o[key] as boolean;
    }
  }
  const numeric: Array<[keyof AlertSettings, number, number]> = [
    ["low_credits_threshold", 0, 1_000_000],
    ["captcha_balance_threshold", 0, 100_000],
    ["failure_rate_threshold", 0, 1],
    ["failure_rate_min_requests", 1, 1_000_000],
    ["window_minutes", 5, 1440],
    ["queue_backlog_depth", 0, 1_000_000],
  ];
  for (const [key, min, max] of numeric) {
    if (o[key] === undefined) continue;
    const value = o[key];
    if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) {
      return { ok: false, error: `alerts.${key} must be a number between ${min} and ${max}.` };
    }
    (next[key] as number) =
      key === "failure_rate_threshold" || key === "captcha_balance_threshold" ? value : Math.round(value);
  }
  return { ok: true, value: next };
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
  /** When the credit balance expires (12 months after the last grant). */
  credits_expire_at: string | null;
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

interface Job {
  id: string;
  type: "lyrics" | "music" | "extend" | "cover" | "stems" | "sounds" | "remaster" | "mashup" | "add_vocals" | "add_instrumental" | "replace_section" | "cover_image" | "persona" | "wav" | "upload_extend" | "upload_cover" | "upload_init" | "upload_register" | "recovery_audio" | "mp4_generate" | "boost_style" | "midi_generate" | "voice_phrase" | "voice_validate" | "voice_record" | "voice_generate" | "voice_apply" | "voice_extend" | "lyrics_detail" | "wav_detail" | "stems_detail" | "video_detail" | "cover_detail" | "subtitle_detail" | "recovery_detail" | "mp4_detail" | "midi_detail" | "timestamped_lyrics_detail";
  status: "pending" | "running" | "streaming" | "complete" | "error";
  accountId?: string;
  result?: unknown;
  error?: string;
  callbackUrl?: string;
  userId?: string;
  apiKeyId?: string;
  endpoint?: string;
  model?: string;
  prompt?: string;
  credits?: number;
  createdAt: number;
  /** When the job reached a terminal state (complete/error). Used for WAV `completeTime`. */
  completedAt?: number;
  /**
   * Serializable form of the submission (roadmap R4). Present only for jobs
   * whose op is in the registry, so a consumer — this process after a restart,
   * or another node — can rebuild and re-run them. Absent for the composite
   * music/sounds/lyrics builders, which keep the pre-R4 in-process behaviour.
   */
  payload?: JobDescriptor;
}

export interface ServerDeps {
  pool: AccountPool;
}

export function loadApiKeys(path: string): ApiKey[] {
  return JSON.parse(readFileSync(path, "utf8")) as ApiKey[];
}

/**
 * Resolve Fastify's `trustProxy` from `TRUST_PROXY` so `req.ip` is the real
 * client address behind a reverse proxy (the socket address would otherwise be
 * the proxy). Defaults to off: if the server is directly reachable, blindly
 * trusting `X-Forwarded-For` lets a caller spoof its IP and defeat an API key's
 * whitelist. Accepts "true"/"false", a hop count, or a comma-separated list of
 * trusted addresses/CIDRs.
 */
function trustProxyOption(): FastifyServerOptions["trustProxy"] {
  const raw = (process.env.TRUST_PROXY ?? "").trim();
  if (!raw || raw === "false" || raw === "0") return false;
  if (raw === "true") return true;
  // A bare number is the proxy hop count. proxy-addr honors it at runtime, but
  // Fastify's option type omits it, so it needs a cast.
  if (/^\d+$/.test(raw)) return Number(raw) as unknown as FastifyServerOptions["trustProxy"];
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
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
 * Self-describing OpenAPI 3.1 document for the public `/api/v1` surface, built
 * from the live route table so it can never drift from the implementation.
 */
function buildOpenApi(routes: Array<{ method: string; url: string }>) {
  const paths: Record<string, Record<string, unknown>> = {};
  const tagSet = new Set<string>();
  for (const r of routes) {
    const isV1 = r.url.startsWith("/api/v1/");
    const isFile = r.url.startsWith("/api/file-");
    if (!isV1 && !isFile) continue;
    const path = isV1 ? r.url.slice("/api/v1".length) || "/" : r.url;
    const method = r.method.toLowerCase();
    const tag = isV1 ? path.split("/").filter(Boolean)[0] ?? "root" : "file-upload";
    tagSet.add(tag);
    const operationId =
      `${method}${path}`
        .replace(/[^a-zA-Z0-9]+(.)?/g, (_m, c: string | undefined) => (c ? c.toUpperCase() : ""))
        .replace(/^[a-z]/, (c) => c.toUpperCase());
    (paths[path] ??= {})[method] = {
      tags: [tag],
      summary: `${r.method} ${path}`,
      operationId,
      // File-upload routes live at /api/file-* (not under /api/v1), so pin them
      // to the root server rather than the global /api/v1 base.
      ...(isFile ? { servers: [{ url: "/" }] } : {}),
      responses: {
        "200": {
          description: "Success",
          content: { "application/json": { schema: { $ref: "#/components/schemas/Envelope" } } },
        },
        "400": { description: "Bad request" },
        "401": { description: "Invalid or missing API key" },
        "402": { description: "Insufficient credits" },
      },
    };
  }
  return {
    openapi: "3.1.0",
    info: {
      title: "CAMXORA Music API",
      version: "1.0.0",
      description:
        "White-label AI music generation API, drop-in compatible with docs.sunoapi.org. " +
        "Every response uses the {code, msg, data} envelope; business errors travel in `code`.",
    },
    servers: [{ url: "/api/v1" }],
    security: [{ bearerAuth: [] }],
    tags: [...tagSet].map((name) => ({ name })),
    paths,
    components: {
      securitySchemes: { bearerAuth: { type: "http", scheme: "bearer" } },
      schemas: {
        Envelope: {
          type: "object",
          properties: {
            code: { type: "integer", example: 200 },
            msg: { type: "string", example: "success" },
            data: { description: "Endpoint-specific payload" },
          },
          required: ["code", "msg"],
        },
      },
    },
  };
}

/** LLM-friendly API guide served at /llms.txt (docs.sunoapi.org parity). */
function buildLlmsTxt(): string {
  return `# CAMXORA Music API

> White-label AI music generation REST API, drop-in compatible with docs.sunoapi.org.

## Base
- Base URL: /api/v1
- Auth: Authorization: Bearer <API_KEY>
- Envelope: every response is {"code":200,"msg":"success","data":...}; business errors use a non-200 code with HTTP 200.

## Core endpoints
- POST /api/v1/generate — submit a generation; returns data.taskId.
- GET /api/v1/generate/record-info?taskId= — poll status (PENDING | TEXT_SUCCESS | FIRST_SUCCESS | SUCCESS | *_FAILED); on SUCCESS, data.response.sunoData[] tracks carry a playable audio_url.
- GET /api/v1/get-credits — remaining credits.
- GET /api/v1/task/:id — task status (aliased shape).

## Notes for agents
- Pass callBackUrl for a webhook, or the sentinel "playground" to poll instead.
- callback_url must be an absolute public URL; private/internal hosts are rejected.
- Credits are debited per call; insufficient credits return HTTP 402 (code 402).

## Links
- Docs: /docs
- OpenAPI: /openapi.json
`;
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
    trustProxy: trustProxyOption(),
    requestTimeout: 600_000,
    connectionTimeout: 600_000,
    keepAliveTimeout: 600_000,
    // Reference media can arrive base64-inlined (e.g. the panel's data URLs);
    // 25MB accommodates a 10MB image plus encoding overhead.
    bodyLimit: Number(process.env.BODY_LIMIT_BYTES ?? 26_214_400),
  });

  // Keep the exact JSON bytes alongside the parsed body: ChmabaPay signs
  // `t=<unix>.<rawBody>`, so the webhook HMAC has to run over the bytes as
  // received rather than a re-serialised object. Overriding the default JSON
  // parser is the only way Fastify exposes the raw payload to a route.
  app.addContentTypeParser("application/json", { parseAs: "string" }, (req, body, done) => {
    const raw = body as string;
    (req as FastifyRequest & { rawBody?: string }).rawBody = raw;
    if (!raw || raw.trim() === "") return done(null, {});
    try {
      done(null, JSON.parse(raw));
    } catch (err) {
      done(err as Error, undefined);
    }
  });

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
      const isPublicApi =
        req.url.startsWith("/v1/") ||
        req.url.startsWith("/api/v1/") ||
        req.url.startsWith("/api/file-");
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

  // sunoapi.org File Upload API is multipart/form-data (`/api/file-stream-upload`).
  // 100MB cap to match the documented limit; only one file per request.
  await app.register(multipart, {
    limits: { fileSize: 100 * 1024 * 1024, files: 1 },
  });

  const jobs = new Map<string, Job>();

  // Job transport (roadmap R4). The default driver is a no-op: `queue.async` is
  // false, so `submitDescribedJob()` runs the work inline exactly as before.
  // `QUEUE_DRIVER=redis` hands descriptor-backed jobs to a BullMQ work list.
  const queue = await createJobQueue();

  // Caps how many Suno-backed jobs run at once, so a burst queues instead of
  // stampeding a small account pool (see `src/concurrency.ts`). The global
  // ceiling is re-evaluated per admission, so adding an account raises capacity
  // without a restart; `SUNO_MAX_CONCURRENT` pins it explicitly. The waiting
  // queue is bounded by `SUNO_MAX_QUEUE` so a flood cannot grow it without limit.
  const sunoSlots = new ConcurrencyGate(
    () => config.suno.maxConcurrent ?? Math.max(1, pool.size * config.suno.concurrentPerAccount),
    config.suno.maxQueue,
  );

  // In-flight jobs per Suno account. Account selection is least-loaded-first
  // (see `orderByLoad`), so a burst spreads across the pool instead of landing
  // on one account; an account at `maxConcurrentPerAccount` is used only when no
  // under-cap account is available. Counted per attempt, in-process.
  const accountInflight = new Map<string, number>();
  const accountLoad = (id: string): number => accountInflight.get(id) ?? 0;
  const markAccountStart = (id: string): void => {
    accountInflight.set(id, accountLoad(id) + 1);
  };
  const markAccountEnd = (id: string): void => {
    const next = accountLoad(id) - 1;
    if (next > 0) accountInflight.set(id, next);
    else accountInflight.delete(id);
  };

  // Edge request counters for the admin `/metrics` snapshot. In-memory and reset
  // on restart, which is all a single-process deployment needs.
  const requestCounters = { total: 0, clientErrors: 0, serverErrors: 0 };
  app.addHook("onResponse", async (_req, reply) => {
    requestCounters.total += 1;
    if (reply.statusCode >= 500) requestCounters.serverErrors += 1;
    else if (reply.statusCode >= 400) requestCounters.clientErrors += 1;
  });

  // sunoapi.org compatibility: their clients expect HTTP 200 for task creates
  // and HTTP 429 when credits are insufficient. Our canonical routes use 202
  // and 402; remap them only on the public /api/v1 surface so the panels and
  // the /v1 + /me routes keep their existing behaviour.
  app.addHook("onSend", async (req, reply, payload) => {
    const url = req.raw.url ?? "";
    if (url.startsWith("/api/v1/")) {
      if (reply.statusCode === 202) reply.code(200);
      else if (reply.statusCode === 402) reply.code(429);
    }
    return payload;
  });

  // Alert evaluator state (task 5.5, REQUIREMENTS §4.10). `alertState` maps an
  // alert id to a fingerprint of its last-notified content so the Telegram push
  // only fires on a state change (new alert, changed message, or recovery) — the
  // same "notify once" behaviour the ops healthcheck script keeps in a state
  // file, held in memory here because this process owns the alert lifecycle.
  const alertState = new Map<string, string>();
  let alertTimer: ReturnType<typeof setInterval> | null = null;
  let sessionTimer: ReturnType<typeof setInterval> | null = null;

  // Terminal jobs only need to survive long enough for the client to poll their
  // result, so the in-memory map is kept bounded: finished jobs older than the
  // TTL are dropped, and if the map is still over the entry cap the oldest
  // finished jobs are dropped first. In-flight jobs (pending/running/streaming)
  // are never evicted.
  const JOB_TTL_MS = Number(process.env.JOB_TTL_MS ?? 60 * 60_000);
  const JOB_MAX_ENTRIES = Number(process.env.JOB_MAX_ENTRIES ?? 5_000);

  function isTerminalJob(job: Job): boolean {
    return job.status === "complete" || job.status === "error";
  }

  function pruneJobs(): void {
    if (jobs.size === 0) return;
    const now = Date.now();
    for (const [id, job] of jobs) {
      if (isTerminalJob(job) && now - job.createdAt > JOB_TTL_MS) jobs.delete(id);
    }
    if (jobs.size <= JOB_MAX_ENTRIES) return;
    // Map preserves insertion (creation) order, so this drops the oldest
    // evictable jobs first.
    for (const [id, job] of jobs) {
      if (jobs.size <= JOB_MAX_ENTRIES) break;
      if (isTerminalJob(job)) jobs.delete(id);
    }
  }

  // Collect every registered route so /openapi.json describes itself without a
  // second source of truth (documentation only; never on the request path).
  const documentedRoutes: Array<{ method: string; url: string }> = [];
  app.addHook("onRoute", (routeOptions) => {
    const methods = Array.isArray(routeOptions.method) ? routeOptions.method : [routeOptions.method];
    for (const method of methods) {
      if (method === "HEAD" || method === "OPTIONS") continue;
      documentedRoutes.push({ method, url: routeOptions.url });
    }
  });

  // Reject unsafe caller-supplied webhook targets before any handler runs, so a
  // bad callback_url can't later reach the internal network — or, on routes that
  // charge first, cost the caller credits before failing.
  app.addHook("preHandler", async (req, reply) => {
    const body = req.body as Record<string, unknown> | undefined;
    if (!body || typeof body !== "object") return;
    for (const field of ["callback_url", "callBackUrl"]) {
      const value = body[field];
      if (typeof value !== "string" || !value.trim()) continue;
      if (isCallbackSentinel(value)) continue; // panel sentinel, e.g. "playground"
      try {
        await assertCallbackUrlAllowed(value);
      } catch (err) {
        reply.code(400).send({
          error: err instanceof CallbackUrlError ? err.message : "callback_url is not allowed.",
        });
        return;
      }
    }
  });

  // Session freshness: a session JWT is valid for 7 days, but the account it
  // represents can be suspended or deleted at any moment. Re-read the user on
  // every request that carries a session token so revocation takes effect on
  // the next call instead of lingering until the token expires. Requests with
  // no verifiable session token fall through to the route's own `requireAuth`;
  // API-key requests carry a non-JWT bearer that never verifies here.
  app.addHook("preHandler", async (req, reply) => {
    const cookieToken = readSessionCookie(req.headers.cookie);
    const auth = req.headers.authorization ?? "";
    const bearerToken = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    const token = cookieToken ?? bearerToken;
    if (!token) return;
    const payload = verifyToken(token);
    if (!payload) return;
    const row = await queryOne<{ status: string }>(
      "SELECT status FROM users WHERE id = $1",
      [payload.id],
    );
    if (!row || row.status !== "active") {
      reply.code(401).send({ error: "Session is no longer valid." });
    }
  });

  // --- Google OAuth ---------------------------------------------------------
  // Google config is admin-managed (env is the fallback); read it per request so
  // a settings change takes effect without a restart.
  // Google sign-in is enabled for the user-facing app ONLY. The admin console
  // authenticates with email/password exclusively, so its callback is
  // deliberately NOT allowlisted and any Google flow requesting it is rejected.
  function googleRedirectAllowlist(): string[] {
    return [config.google.redirectUriUser];
  }
  function googleConfigured(): boolean {
    return Boolean(config.google.clientId && config.google.clientSecret);
  }

  function resolveGoogleClient(redirectUri: string | undefined): {
    client: OAuth2Client | null;
    redirectUri: string;
  } {
    // Pick the requested redirect_uri if it's on the allowlist,
    // otherwise fall back to the user-facing default.
    const allowlist = googleRedirectAllowlist();
    const defaultUri = allowlist[0];
    const chosen =
      redirectUri && allowlist.includes(redirectUri) ? redirectUri : defaultUri;
    if (!googleConfigured()) return { client: null, redirectUri: chosen };
    // Build a fresh client per request: `redirectUri` is not settable on a
    // shared client, and a per-request instance avoids concurrent Google
    // flows cross-wiring each other's redirect URI.
    const client = new OAuth2Client({
      clientId: config.google.clientId,
      clientSecret: config.google.clientSecret,
      redirectUri: chosen,
    });
    return { client, redirectUri: chosen };
  }

  // --- auth helpers --------------------------------------------------------
  function hashKey(token: string): string {
    return createHash("sha256").update(token).digest("hex");
  }

  async function findKey(token: string): Promise<DbApiKey | null> {
    const key = await queryOne<DbApiKey>(
      `SELECT id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active, credits_expire_at
       FROM api_keys WHERE key_hash = $1 AND is_active = true`,
      [hashKey(token)],
    );
    if (key) await enforceCreditExpiry(key);
    return key;
  }

  /**
   * Purchased credits are valid for 12 months from the most recent grant. On
   * access an expired balance is zeroed once and can no longer be spent
   * (the spend statements also carry a `credits_expire_at` guard).
   */
  async function enforceCreditExpiry(key: DbApiKey): Promise<void> {
    if (!key.credits_expire_at) return;
    if (new Date(key.credits_expire_at).getTime() > Date.now()) return;
    await query(
      "UPDATE api_keys SET credits = 0, credits_expire_at = NULL WHERE id = $1 AND credits_expire_at IS NOT NULL AND credits_expire_at <= now()",
      [key.id],
    ).catch(() => {});
    key.credits = 0;
    key.credits_expire_at = null;
  }

  /**
   * The user's spendable balance, pooled across all their active keys (matching
   * how charges fall back across keys). Returns the earliest expiry among funded
   * keys so clients can show when the balance lapses.
   */
  async function accountCredits(userId: string): Promise<{ credits: number; credits_expire_at: string | null }> {
    const row = await queryOne<{ credits: string; expires: string | null }>(
      `SELECT COALESCE(sum(credits), 0)::text AS credits,
              min(credits_expire_at) FILTER (WHERE credits > 0 AND credits_expire_at IS NOT NULL) AS expires
       FROM api_keys WHERE user_id = $1 AND is_active = true`,
      [userId],
    );
    return { credits: Number(row?.credits ?? 0), credits_expire_at: row?.expires ?? null };
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
    /** Requests allowed per `config.rateLimit.userWindowMs` (sunoapi.org 20/10s shape). */
    perWindow: number | null;
    perMinute: number | null;
    perDay: number | null;
    /** Cap on this user's concurrently running Suno jobs; null = config default. */
    maxConcurrentJobs: number | null;
  }

  const DAY_MS = 86_400_000;
  const rateLimitCache = new Map<string, { limits: UserRateLimits | null; at: number }>();
  const windowWindows = new Map<string, { start: number; count: number }>();
  const minuteWindows = new Map<string, { start: number; count: number }>();
  const dayWindows = new Map<string, { start: number; count: number }>();
  const RATE_LIMIT_MAP_CAP = Number(process.env.RATE_LIMIT_MAP_CAP ?? 20_000);

  async function loadUserRateLimits(userId: string): Promise<UserRateLimits | null> {
    const now = Date.now();
    const cached = rateLimitCache.get(userId);
    if (cached && now - cached.at < config.rateLimit.perUserCacheMs) return cached.limits;
    const row = await queryOne<{
      requests_per_window: number | null;
      requests_per_minute: number | null;
      requests_per_day: number | null;
      max_concurrent_jobs: number | null;
    }>(
      "SELECT requests_per_window, requests_per_minute, requests_per_day, max_concurrent_jobs FROM rate_limits WHERE user_id = $1 LIMIT 1",
      [userId],
    );
    const limits =
      row &&
      (row.requests_per_window != null ||
        row.requests_per_minute != null ||
        row.requests_per_day != null ||
        row.max_concurrent_jobs != null)
        ? {
            perWindow: row.requests_per_window,
            perMinute: row.requests_per_minute,
            perDay: row.requests_per_day,
            maxConcurrentJobs: row.max_concurrent_jobs,
          }
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
    exceeded: "window" | "minute" | "day" | null;
    retryAfterSec: number;
    windowRemaining: number | null;
    minuteRemaining: number | null;
    dayRemaining: number | null;
  }

  function checkUserRateLimit(userId: string, limits: UserRateLimits): UserRateResult {
    const now = Date.now();
    const windowMs = config.rateLimit.windowMs;
    const userWindowMs = config.rateLimit.userWindowMs;
    const minuteStart = now - (now % windowMs);
    const userWindowStart = now - (now % userWindowMs);
    const day = new Date(now);
    const dayStart = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate());
    let windowRemaining: number | null = null;
    let minuteRemaining: number | null = null;
    let dayRemaining: number | null = null;

    // Short per-window budget first: it is the tightest and mirrors sunoapi.org.
    if (limits.perWindow != null) {
      if (windowWindows.size > RATE_LIMIT_MAP_CAP) {
        for (const [id, w] of windowWindows) if (w.start !== userWindowStart) windowWindows.delete(id);
      }
      const count = bumpWindow(windowWindows, userId, userWindowStart);
      windowRemaining = Math.max(0, limits.perWindow - count);
      if (count > limits.perWindow) {
        return {
          allowed: false,
          exceeded: "window",
          retryAfterSec: Math.max(1, Math.ceil((userWindowStart + userWindowMs - now) / 1000)),
          windowRemaining: 0,
          minuteRemaining,
          dayRemaining,
        };
      }
    }
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
          windowRemaining,
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
          windowRemaining,
          minuteRemaining,
          dayRemaining: 0,
        };
      }
    }
    return {
      allowed: true,
      exceeded: null,
      retryAfterSec: 0,
      windowRemaining,
      minuteRemaining,
      dayRemaining,
    };
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
    if (limits.perWindow != null) {
      reply.header("x-user-rate-limit-window", String(limits.perWindow));
      reply.header("x-user-rate-remaining-window", String(result.windowRemaining ?? 0));
    }
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
    const error =
      result.exceeded === "day"
        ? `Daily request limit exceeded (${limits.perDay}/day).`
        : result.exceeded === "window"
          ? `Request rate limit exceeded (${limits.perWindow} per ${Math.round(config.rateLimit.userWindowMs / 1000)}s).`
          : `Request rate limit exceeded (${limits.perMinute}/min).`;
    reply.code(429).send({ error });
    return false;
  }

  async function charge(key: DbApiKey, amount: number): Promise<boolean> {
    const effectiveTotalLimit =
      key.safe_spend_total ?? key.safe_spend_limit ?? null;

    if (effectiveTotalLimit != null) {
      const spent = await queryOne<{ sum: string }>(
        "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND status <> 'error'",
        [key.id],
      );
      if (Number(spent?.sum ?? 0) + amount > effectiveTotalLimit) return false;
    }

    if (key.safe_spend_hourly != null) {
      const spent = await queryOne<{ sum: string }>(
        "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND status <> 'error' AND created_at >= now() - interval '1 hour'",
        [key.id],
      );
      if (Number(spent?.sum ?? 0) + amount > key.safe_spend_hourly) return false;
    }

    if (key.safe_spend_daily != null) {
      const spent = await queryOne<{ sum: string }>(
        "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND status <> 'error' AND created_at >= now() - interval '1 day'",
        [key.id],
      );
      if (Number(spent?.sum ?? 0) + amount > key.safe_spend_daily) return false;
    }

    const rows = await query<{ credits: number }>(
      "UPDATE api_keys SET credits = credits - $1, last_used_at = now() WHERE id = $2 AND credits >= $1 AND (credits_expire_at IS NULL OR credits_expire_at > now()) RETURNING credits",
      [amount, key.id],
    );
    if (rows.length === 0) {
      // The authenticating key can't cover the charge. Credits are an
      // account-level balance — the session UI and /me/billing already treat
      // them that way (they spend from any funded key and report the sum) — but
      // an API key starts at 0, and a top-up made before a key existed parks
      // the credits on a hidden auto-created wallet key. Fall back to the
      // user's other funded keys so an API key draws on the same pooled
      // balance. `chargeUserKey` honours the paying key's own spend limits, and
      // the paying key replaces `key` so usage is attributed to — and refunds
      // are credited to — the key that actually paid. Only the balance check
      // falls through here; a spend-limit rejection above still returns false,
      // so a key's limit is never bypassed by spending from another key.
      const payer = await chargeUserKey(key.user_id, amount);
      if (!payer) return false;
      Object.assign(key, payer);
      return true;
    }
    key.credits = rows[0].credits;
    return true;
  }

  /**
   * Atomically pick the user's oldest key that can afford `amount` and deduct the
   * credits in a single statement, so concurrent requests can never both spend the
   * same balance. Returns the charged key (with its new balance) or null when the
   * user has no key that can pay. `amount <= 0` is a no-op and returns null.
   */
  async function chargeUserKey(userId: string, amount: number): Promise<DbApiKey | null> {
    if (amount <= 0) return null;
    const rows = await query<DbApiKey>(
      `WITH candidate AS (
         SELECT id FROM api_keys
         WHERE user_id = $1
           AND is_active = true
           AND credits >= $2
           AND (credits_expire_at IS NULL OR credits_expire_at > now())
           AND (COALESCE(safe_spend_total, safe_spend_limit) IS NULL
                OR (SELECT COALESCE(sum(credits_consumed), 0) FROM usage_logs WHERE api_key_id = api_keys.id AND status <> 'error') + $2
                   <= COALESCE(safe_spend_total, safe_spend_limit))
           AND (safe_spend_hourly IS NULL
                OR (SELECT COALESCE(sum(credits_consumed), 0) FROM usage_logs
                    WHERE api_key_id = api_keys.id AND status <> 'error' AND created_at >= now() - interval '1 hour') + $2 <= safe_spend_hourly)
           AND (safe_spend_daily IS NULL
                OR (SELECT COALESCE(sum(credits_consumed), 0) FROM usage_logs
                    WHERE api_key_id = api_keys.id AND status <> 'error' AND created_at >= now() - interval '1 day') + $2 <= safe_spend_daily)
         ORDER BY created_at ASC
         LIMIT 1
       )
       UPDATE api_keys SET credits = credits - $2, last_used_at = now()
       WHERE id IN (SELECT id FROM candidate) AND credits >= $2 AND (credits_expire_at IS NULL OR credits_expire_at > now())
       RETURNING id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active`,
      [userId, amount],
    );
    return rows[0] ?? null;
  }

  /**
   * Credit cost for an endpoint, read from the `pricing` table
   * (admin-configurable).
   *
   * A row scoped to the requested model wins over the endpoint-wide one, so an
   * admin can price one model differently (e.g. the cheaper mini model) without
   * touching the rest. With no model row (or no model asked for) the
   * endpoint-wide row applies.
   */
  async function costFor(endpoint: string, model?: string): Promise<number> {
    const row = await queryOne<{ credit_cost: number }>(
      `SELECT credit_cost FROM pricing
       WHERE endpoint = $1 AND (model IS NOT DISTINCT FROM $2 OR model IS NULL)
       ORDER BY model NULLS LAST
       LIMIT 1`,
      [endpoint, normalizeModel(model) ?? null],
    );
    return row?.credit_cost ?? DEFAULT_COSTS[endpoint] ?? 9;
  }

  /**
   * Routing policy for a model: an admin override from `routing_rules` (keyed
   * on the normalised model so retired aliases still match), else the built-in
   * default — chirp-goose prefers free accounts, every other model is paid-only.
   */
  async function routingPolicy(model?: string): Promise<"prefer_free" | "paid_only" | "any"> {
    const want = normalizeModel(model);
    if (want) {
      const row = await queryOne<{ policy: string }>(
        "SELECT policy FROM routing_rules WHERE model = $1 LIMIT 1",
        [want],
      );
      if (row?.policy === "prefer_free" || row?.policy === "paid_only" || row?.policy === "any") {
        return row.policy;
      }
    }
    return defaultRoutingPolicy(want);
  }

  function requireAuth(req: FastifyRequest, reply: FastifyReply): UserPayload | null {
    const cookieToken = readSessionCookie(req.headers.cookie);
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
    // also protects state-changing work reachable over GET — e.g. the
    // credit-spending /me/download and /me/* detail routes — which a
    // method-only check would let through.
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
    // Role is read from the DB, not the token: an account demoted from admin
    // must lose admin access on its next request, not when its JWT expires.
    const row = await queryOne<{ role: "user" | "admin" }>(
      "SELECT role FROM users WHERE id = $1",
      [user.id],
    );
    if (!row || row.role !== "admin") {
      reply.code(403).send({ error: "Admin only." });
      return null;
    }
    return { id: user.id, email: user.email, role: "admin" };
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
    apiKeyId: string | null;
    endpoint: string;
    model?: string;
    prompt?: string;
    status: string;
    credits: number;
    taskId: string;
    result?: unknown;
  }): Promise<void> {
    const insert = (apiKeyId: string | null) =>
      query(
        `INSERT INTO usage_logs (user_id, api_key_id, endpoint, model, prompt, status, credits_consumed, task_id, result_json)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
        [
          args.userId,
          apiKeyId,
          args.endpoint,
          args.model ?? null,
          args.prompt ?? null,
          args.status,
          args.credits,
          args.taskId,
          args.result ? JSON.stringify(args.result) : null,
        ],
      );
    try {
      await insert(args.apiKeyId);
    } catch (e) {
      // A job can outlive the API key that created it (the key was deleted before
      // the job finalized). `usage_logs.api_key_id` is `ON DELETE SET NULL`, so
      // retry without the stale id instead of failing the whole finalize step
      // (which would also skip the callback).
      if ((e as { code?: string }).code === "23503" && args.apiKeyId) {
        await insert(null);
      } else {
        throw e;
      }
    }
  }

  // --- job persistence -----------------------------------------------------
  // Live job state lives in the in-memory `jobs` map for fast handler reads, but
  // every transition is mirrored to the `jobs` table so an in-flight job survives
  // a restart. On boot `recoverJobs()` fails out anything left pending/running.
  async function saveJob(job: Job): Promise<void> {
    await query(
      `INSERT INTO jobs
         (id, type, status, account_id, result_json, error, callback_url,
          user_id, api_key_id, endpoint, model, prompt, credits, payload, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14, to_timestamp($15 / 1000.0), now())
       ON CONFLICT (id) DO UPDATE SET
         status = EXCLUDED.status,
         account_id = EXCLUDED.account_id,
         result_json = EXCLUDED.result_json,
         error = EXCLUDED.error,
         payload = EXCLUDED.payload,
         updated_at = now()`,
      [
        job.id,
        job.type,
        job.status,
        job.accountId ?? null,
        job.result === undefined ? null : JSON.stringify(job.result),
        job.error ?? null,
        job.callbackUrl ?? null,
        job.userId ?? null,
        job.apiKeyId ?? null,
        job.endpoint ?? null,
        job.model ?? null,
        job.prompt ?? null,
        job.credits ?? null,
        job.payload === undefined ? null : JSON.stringify(job.payload),
        job.createdAt,
      ],
    );
  }

  interface JobRow {
    id: string;
    type: Job["type"];
    status: Job["status"];
    account_id: string | null;
    result_json: unknown;
    error: string | null;
    callback_url: string | null;
    user_id: string | null;
    api_key_id: string | null;
    endpoint: string | null;
    model: string | null;
    prompt: string | null;
    credits: number | null;
    payload: unknown;
    created_at: Date;
  }

  const JOB_COLUMNS =
    "id, type, status, account_id, result_json, error, callback_url, user_id, api_key_id, endpoint, model, prompt, credits, payload, created_at";

  function rowToJob(row: JobRow): Job {
    return {
      id: row.id,
      type: row.type,
      status: row.status,
      accountId: row.account_id ?? undefined,
      result: row.result_json ?? undefined,
      error: row.error ?? undefined,
      callbackUrl: row.callback_url ?? undefined,
      userId: row.user_id ?? undefined,
      apiKeyId: row.api_key_id ?? undefined,
      endpoint: row.endpoint ?? undefined,
      model: row.model ?? undefined,
      prompt: row.prompt ?? undefined,
      credits: row.credits ?? undefined,
      payload:
        row.payload && typeof row.payload === "object" ? (row.payload as JobDescriptor) : undefined,
      createdAt: new Date(row.created_at).getTime(),
    };
  }

  /** Read a job from the in-memory cache, falling back to the persisted row. */
  // Job ids are always UUIDs (`newJob` uses randomUUID). Validate before the
  // lookup so a malformed id returns "not found" instead of letting Postgres
  // reject the `uuid` cast and surface a 500 to the caller.
  async function getJob(id: string): Promise<Job | null> {
    if (!UUID_RE.test(id)) return null;
    const cached = jobs.get(id);
    if (cached) return cached;
    const row = await queryOne<JobRow>(`SELECT ${JOB_COLUMNS} FROM jobs WHERE id = $1`, [id]);
    if (!row) return null;
    const job = rowToJob(row);
    jobs.set(job.id, job);
    return job;
  }

  /**
   * Settle jobs that were still pending/running when this process stopped.
   *
   * A descriptor-backed job is simply re-queued: its `payload` says exactly what
   * to run, so a consumer — this process on the next tick, or another node —
   * picks it up and runs it to completion. Nothing is settled at recovery time.
   * Anything else has no serializable submission, so the worker that would have
   * finished it is gone for good: mark it errored and finalize (usage log +
   * refund + callback) rather than leave clients polling a job the server no
   * longer knows about.
   */
  async function recoverJobs(): Promise<void> {
    // A crash between saveJob() and settleCredits() leaves an `error` job with
    // no refund. Settlement is idempotent, so re-settle any that are missing one.
    try {
      await reconcileMissingRefunds();
    } catch (e) {
      console.error("[jobs] refund reconcile sweep failed:", e instanceof Error ? e.message : e);
    }
    const rows = await query<JobRow>(
      `SELECT ${JOB_COLUMNS} FROM jobs WHERE status IN ('pending','running','streaming')`,
    );
    if (rows.length === 0) return;
    let requeued = 0;
    let interrupted = 0;
    for (const row of rows) {
      const job = rowToJob(row);
      jobs.set(job.id, job);
      if (queue.async && isRunnableDescriptor(job.payload)) {
        job.status = "pending";
        job.error = undefined;
        await saveJob(job);
        try {
          await queue.enqueue(job.id);
          requeued++;
          continue;
        } catch (e) {
          // Queue unavailable: fall through and fail the job out instead of
          // blocking startup on a backend that is already misbehaving.
          console.error(`[jobs] could not re-queue ${job.id}:`, e instanceof Error ? e.message : e);
        }
      }
      job.status = "error";
      job.error = RESTART_INTERRUPT_ERROR;
      await saveJob(job);
      await finalizeJob(job);
      interrupted++;
    }
    console.warn(
      `[jobs] recovered ${rows.length} interrupted job(s): ${requeued} re-queued, ${interrupted} failed out.`,
    );
  }

  /**
   * Refund failed jobs whose `refund` ledger row was never written.
   *
   * `finalizeJob` persists the job before `settleCredits` runs, so a crash in
   * between leaves an `error` job unrefunded; `recoverJobs` only re-processes
   * pending/running rows, so it would never be corrected. Re-settling is safe:
   * the partial unique index on (job_id, type) makes both rows idempotent.
   */
  async function reconcileMissingRefunds(): Promise<number> {
    const rows = await query<JobRow>(
      `SELECT ${JOB_COLUMNS} FROM jobs j
        WHERE j.status = 'error'
          AND j.user_id IS NOT NULL
          AND j.api_key_id IS NOT NULL
          AND COALESCE(j.credits, 0) > 0
          AND NOT EXISTS (
            SELECT 1 FROM credit_transactions ct
            WHERE ct.job_id = j.id AND ct.type = 'refund'
          )
        ORDER BY j.updated_at DESC
        LIMIT 500`,
    );
    if (rows.length === 0) return 0;
    let refunded = 0;
    for (const row of rows) {
      const job = rowToJob(row);
      try {
        await settleCredits(job);
        refunded++;
      } catch (e) {
        console.error(
          `[jobs] refund reconcile failed for ${job.id}:`,
          e instanceof Error ? e.message : e,
        );
      }
    }
    if (refunded > 0) {
      console.warn(`[jobs] refunded ${refunded} previously unsettled failed job(s).`);
    }
    return refunded;
  }

  // Bring the queue up once the server is ready (after the DB is reachable) and
  // before we start accepting requests, so a stranded job is re-queued straight
  // into a live consumer.
  app.addHook("onReady", async () => {
    await queue.ping();
    queue.start(consumeQueuedJob);
    await recoverJobs();
    startAlertLoop();
    startSessionKeepAlive();
  });

  function newJob(type: Job["type"], callbackUrl?: string): Job {
    const job: Job = {
      id: randomUUID(),
      type,
      status: "pending",
      callbackUrl,
      createdAt: Date.now(),
    };
    if (!job.createdAt) job.createdAt = Date.now();
    jobs.set(job.id, job);
    pruneJobs();
    return job;
  }

  // Timestamped lyrics are a *read* of a clip's stored alignment — deterministic
  // for a given clip. Every request used to mint a fresh job + `usage_logs` row,
  // so a client that polls until it sees timings (the desktop app retries on an
  // empty result) flooded the ledger and re-ran the expensive aligner for the
  // same song hundreds of times. Collapse repeated calls onto one job:
  //   - a usable (timed) result is reused for good — the alignment can't change;
  //   - an in-flight job is reused so concurrent calls don't duplicate the work;
  //   - an empty/failed result is reused only within a retry window, so a broken
  //     aligner can recover without the client retrying every few seconds.
  // Failures are cached briefly so a saturated aligner retries soon instead of
  // re-running on every poll; a usable result is cached for good (see below).
  const LYRICS_REUSE_TTL_MS = Number(process.env.LYRICS_REUSE_TTL_MS ?? 2 * 60_000);

  function isUsableLyricsResult(job: Job): boolean {
    if (job.status !== "complete") return false;
    const r = (job.result ?? {}) as Record<string, unknown>;
    return r.aligned === true && typeof r.lrc === "string" && r.lrc.length > 0;
  }

  async function reusableLyricsJob(clipId: string, userId: string): Promise<Job | null> {
    if (!clipId) return null;
    const floor = Date.now() - LYRICS_REUSE_TTL_MS;
    const isInflight = (job: Job) =>
      job.status === "pending" || job.status === "running" || job.status === "streaming";

    // In-memory map is authoritative while a job is live (inline jobs never hit
    // `jobs` until they settle); keep the newest of each preference class.
    let usable: Job | null = null;
    let inflight: Job | null = null;
    let recent: Job | null = null;
    for (const job of jobs.values()) {
      if (
        job.endpoint !== "timestamped_lyrics_detail" ||
        job.userId !== userId ||
        job.payload?.op !== "timestamped_lyrics_detail" ||
        (job.payload.args as Record<string, unknown> | undefined)?.id !== clipId
      ) {
        continue;
      }
      if (isUsableLyricsResult(job)) {
        if (!usable || job.createdAt > usable.createdAt) usable = job;
      } else if (isInflight(job)) {
        if (!inflight || job.createdAt > inflight.createdAt) inflight = job;
      } else if (job.createdAt >= floor) {
        if (!recent || job.createdAt > recent.createdAt) recent = job;
      }
    }
    if (usable) return usable;
    if (inflight) return inflight;
    if (recent) return recent;

    // Cache evicted it (or another node owns the work): consult the durable row.
    const base = `SELECT ${JOB_COLUMNS} FROM jobs
       WHERE endpoint = 'timestamped_lyrics_detail'
         AND user_id = $2
         AND payload->'args'->>'id' = $1`;
    const usableRow = await queryOne<JobRow>(
      `${base}
         AND status = 'complete'
         AND coalesce((result_json->>'aligned')::boolean, false) = true
         AND length(coalesce(result_json->>'lrc', '')) > 0
       ORDER BY created_at DESC
       LIMIT 1`,
      [clipId, userId],
    );
    if (usableRow) return rowToJob(usableRow);
    const fallbackRow = await queryOne<JobRow>(
      `${base}
         AND (status IN ('pending','running','streaming') OR created_at > to_timestamp($3 / 1000.0))
       ORDER BY created_at DESC
       LIMIT 1`,
      [clipId, userId, floor],
    );
    return fallbackRow ? rowToJob(fallbackRow) : null;
  }

  // sunoapi.org's timestamped-lyrics getters answer *synchronously* with
  // `data.alignedWords`. Suno provides those words directly (see
  // `client.getAlignedLyrics`); we normalise them to camelCase timings and, for
  // legacy results from the Whisper fallback, rebuild line tokens from
  // `aligned_lines`. Both carry newline-terminated words so the caller's
  // `aligned_words_to_lrc` reconstructs the lines.
  function normalizeSunoAlignedWords(raw: Array<Record<string, unknown>>): AlignedWord[] {
    const out: AlignedWord[] = [];
    for (const item of raw) {
      if (!item || typeof item !== "object") continue;
      const word = typeof item.word === "string" ? item.word : "";
      if (!word) continue;
      const startS = Number(item.start_s ?? item.startS ?? 0) || 0;
      const endS = Number(item.end_s ?? item.endS ?? startS) || startS;
      out.push({ word, startS, endS, success: item.success ?? true, palign: item.p_align ?? 0 });
    }
    return out;
  }

  function sunoAlignedWords(job: Job): Array<Record<string, unknown>> {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const stored = Array.isArray(res.aligned_words)
      ? (res.aligned_words as Array<Record<string, unknown>>)
      : [];
    if (stored.length > 0) {
      return stored.map((w) => ({
        word: w.word,
        startS: w.startS,
        endS: w.endS,
        success: w.success ?? true,
        palign: w.palign ?? 0,
      }));
    }
    const lines = Array.isArray(res.aligned_lines)
      ? (res.aligned_lines as Array<Record<string, unknown>>)
      : [];
    const words: Array<Record<string, unknown>> = [];
    for (const line of lines) {
      if (!line || typeof line !== "object") continue;
      const text = typeof line.text === "string" ? line.text.trim() : "";
      if (!text) continue;
      const start = Number(line.startS ?? 0) || 0;
      words.push({ word: `${text}\n`, startS: start, endS: Number(line.endS ?? start) || start });
    }
    return words;
  }

  function timestampedLyricsBody(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    return {
      code: 200,
      msg: "success",
      data: {
        taskId: job.id,
        aligned: res.aligned === true,
        lrc: typeof res.lrc === "string" ? res.lrc : "",
        alignedWords: sunoAlignedWords(job),
      },
    };
  }

  // The getters answer synchronously, but CPU faster-whisper alignment takes
  // tens of seconds — far longer than the caller's ~30s HTTP timeout — so they
  // must not hold the request for it. Start the job, wait only a short grace
  // period (covers a warm cache / an already-nearly-done job), then answer with
  // whatever is cached. Alignment finishes in the background and the caller's
  // next attempt is served the real timings from the cache.
  const LYRICS_SYNC_WAIT_MS = Number(process.env.LYRICS_SYNC_WAIT_MS ?? 3_000);

  async function awaitJobTerminal(job: Job, ms: number): Promise<void> {
    const running = () =>
      job.status === "pending" || job.status === "running" || job.status === "streaming";
    const deadline = Date.now() + ms;
    while (running() && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
  }

  function slug(s: string): string {
    return s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "clip";
  }

  /**
   * True when `clipId` is known to belong to a *different* user. Ownership is
   * derived from the clip ids stored in a job/usage result, so a readable clip
   * cannot be crossed between tenants. An id attributed to nobody (e.g. a legacy
   * row with no stored result) is allowed through, so this never regresses
   * legitimate access.
   */
  async function clipOwnedByOtherUser(userId: string, clipId: string): Promise<boolean> {
    if (!userId || !clipId) return false;
    const owns = await queryOne<{ one: number }>(
      `SELECT 1 AS one FROM jobs
         WHERE user_id = $1 AND result_json::text LIKE '%' || $2 || '%'
       UNION ALL
       SELECT 1 FROM usage_logs
         WHERE user_id = $1 AND result_json::text LIKE '%' || $2 || '%'
       LIMIT 1`,
      [userId, clipId],
    );
    if (owns) return false;
    const foreign = await queryOne<{ one: number }>(
      `SELECT 1 AS one FROM jobs
         WHERE user_id IS NOT NULL AND user_id <> $1
           AND result_json::text LIKE '%' || $2 || '%'
       UNION ALL
       SELECT 1 FROM usage_logs
         WHERE user_id IS NOT NULL AND user_id <> $1
           AND result_json::text LIKE '%' || $2 || '%'
       LIMIT 1`,
      [userId, clipId],
    );
    return Boolean(foreign);
  }

  function denyForeignClip(reply: FastifyReply): void {
    reply.code(403).send({ error: "This clip does not belong to your account." });
  }

  function meDetailRoute(path: string, type: Job["type"]) {
    app.get(path, async (req, reply) => {
      const u = requireAuth(req, reply);
      if (!u) return;
      const { id } = req.params as { id: string };
      if (!id) return reply.code(400).send({ error: "id is required." });
      if (await clipOwnedByOtherUser(u.id, id)) return denyForeignClip(reply);
      let cost = 0;
      try {
        cost = await costFor(type);
      } catch {
        cost = 0;
      }
      const key = await chargeUserKey(u.id, cost);
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      const job = newJob(type);
      job.userId = u.id;
      if (key) job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      void submitDescribedJob(job, { op: type, args: { id } });
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  async function notify(job: Job): Promise<void> {
    if (!job.callbackUrl || isCallbackSentinel(job.callbackUrl)) return;
    try {
      // Re-check at the sink as well: a public hostname accepted earlier can be
      // re-pointed at an internal address before the job finishes (DNS rebinding).
      await assertCallbackUrlAllowed(job.callbackUrl);
      // WAV conversion uses sunoapi.org's own callback envelope:
      // {code,msg,data:{audioWavUrl,task_id}}, not the track-list envelope below.
      if (job.type === "wav" || job.endpoint === "wav") {
        const ok = job.status === "complete";
        const res = (job.result ?? {}) as Record<string, unknown>;
        const wavUrl = ok
          ? ((res.download_url as string) ?? (res.wav_url as string) ?? null)
          : null;
        await fetch(job.callbackUrl, {
          method: "POST",
          headers: { "content-type": "application/json" },
          redirect: "manual",
          signal: AbortSignal.timeout(10_000),
          body: JSON.stringify({
            code: ok ? 200 : 400,
            msg: ok ? "success" : (job.error || "WAV format conversion failed"),
            data: { audioWavUrl: wavUrl, task_id: job.id },
          }),
        });
        return;
      }
      // Music video has its own callback envelope: {code,msg,data:{task_id,video_url}}.
      if (job.type === "mp4_generate" || job.endpoint === "mp4_generate") {
        const ok = job.status === "complete";
        const res = (job.result ?? {}) as Record<string, unknown>;
        const videoUrl = ok ? ((res.video_url as string) ?? null) : null;
        await fetch(job.callbackUrl, {
          method: "POST",
          headers: { "content-type": "application/json" },
          redirect: "manual",
          signal: AbortSignal.timeout(10_000),
          body: JSON.stringify({
            code: ok ? 200 : 400,
            msg: ok ? "MP4 generated successfully." : (job.error || "MP4 generation failed"),
            data: { task_id: job.id, video_url: videoUrl },
          }),
        });
        return;
      }
      // MIDI has its own callback envelope: {task_id,code,msg,data:{state,instruments}}.
      if (job.type === "midi_generate" || job.endpoint === "midi_generate") {
        const ok = job.status === "complete";
        const res = (job.result ?? {}) as Record<string, unknown>;
        await fetch(job.callbackUrl, {
          method: "POST",
          headers: { "content-type": "application/json" },
          redirect: "manual",
          signal: AbortSignal.timeout(10_000),
          body: JSON.stringify({
            task_id: job.id,
            code: ok ? 200 : 500,
            msg: ok ? "success" : (job.error || "MIDI generation failed"),
            data: ok ? (res.midi_data ?? null) : null,
          }),
        });
        return;
      }
      // Recovery has its own callback envelope: {code,msg,task_id,data[]}.
      if (job.type === "recovery_audio" || job.endpoint === "recovery_audio") {
        const res = (job.result ?? {}) as Record<string, unknown>;
        const tracks = Array.isArray(res.tracks) ? res.tracks : null;
        const ok = job.status === "complete";
        await fetch(job.callbackUrl, {
          method: "POST",
          headers: { "content-type": "application/json" },
          redirect: "manual",
          signal: AbortSignal.timeout(10_000),
          body: JSON.stringify({
            code: ok ? 200 : 500,
            msg: ok ? "success" : (job.error || "Recovery failed"),
            task_id: job.id,
            data: tracks,
          }),
        });
        return;
      }
      // sunoapi.org's callback envelope: {code,msg,data:{callbackType,task_id,data[]}}.
      // Our jobs finalize atomically, so we emit one terminal callback ("complete"
      // or "error") rather than their intermediate text/first stages.
      const tracks: Array<Record<string, unknown>> = [];
      collectClipObjects(job.result, tracks);
      const ok = job.status === "complete";
      const payload = {
        code: ok ? 200 : 400,
        msg: ok ? "All generated successfully." : (job.error || "Music generation failed"),
        data: {
          callbackType: ok ? "complete" : "error",
          task_id: job.id,
          data: ok ? tracks.map(sunoTrack) : null,
        },
      };
      await fetch(job.callbackUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        // Do not follow redirects — a 3xx to an internal address would otherwise
        // bypass the check above.
        redirect: "manual",
        signal: AbortSignal.timeout(10_000),
        body: JSON.stringify(payload),
      });
    } catch {
      // callback failures are non-fatal
    }
  }

  /**
   * Record the credit movement for a settled job in `credit_transactions` and, on
   * terminal failure, restore the charged amount to the API key.
   *
   * Every settled job writes a `spend` row (negative amount); a job that ends in
   * `error` additionally writes a positive `refund` row and the credits are added
   * back to `api_keys`. Both writes conflict on the partial unique index
   * `uq_credit_tx_job_type (job_id, type)`, so re-running settlement for the same
   * job is a no-op — a retried/duplicated finalize can never refund twice.
   */
  async function settleCredits(job: Job): Promise<void> {
    if (!job.userId || !job.apiKeyId) return;
    const amount = job.credits ?? 0;
    if (amount <= 0) return;

    // The spend row, the refund row and the credit restore must commit together:
    // otherwise a crash between the refund insert and the balance update would
    // lose the credits forever (the idempotency guard would skip the retry).
    await withTransaction(async (tx) => {
      await tx(
        `INSERT INTO credit_transactions (user_id, amount, type, description, job_id)
         VALUES ($1, $2, 'spend', $3, $4)
         ON CONFLICT (job_id, type) WHERE job_id IS NOT NULL DO NOTHING`,
        [job.userId, -amount, `${job.type} job (${job.status})`, job.id],
      );

      if (job.status !== "error") return;

      const refunded = await tx<{ id: string }>(
        `INSERT INTO credit_transactions (user_id, amount, type, description, job_id)
         VALUES ($1, $2, 'refund', $3, $4)
         ON CONFLICT (job_id, type) WHERE job_id IS NOT NULL DO NOTHING
         RETURNING id`,
        [job.userId, amount, `refund for failed ${job.type} job`, job.id],
      );
      if (refunded.length === 0) return; // already refunded
      await tx("UPDATE api_keys SET credits = credits + $1, credits_expire_at = now() + interval '12 months' WHERE id = $2", [amount, job.apiKeyId]);
    });
  }

  // --- background workers --------------------------------------------------
  // Job types whose result must carry a playable, durable audio URL on success.
  // Matching sunoapi.org's contract here is what lets clients treat musicapi as
  // a drop-in: no fabricated URLs, no recovery loop.
  const AUDIO_CLIP_JOB_TYPES = new Set<string>([
    "music",
    "extend",
    "cover",
    "remaster",
    "mashup",
    "add_vocals",
    "add_instrumental",
    "replace_section",
    "upload_extend",
    "upload_cover",
  ]);

  /**
   * Copy a completed job's clips into durable storage, and for audio jobs never
   * report `complete` with an empty audio_url. Best-effort ingest is retried a
   * couple of times, then the job fails with a refundable error instead of a
   * false success that clients would chase with recovery.
   */
  async function ensureDurableAudio(job: Job): Promise<void> {
    let clips: Array<Record<string, unknown>> = [];
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        await ingestMedia(job);
      } catch (e) {
        console.error("[storage] ingest failed:", e instanceof Error ? e.message : e);
      }
      clips = [];
      collectClipObjects(job.result, clips);
      if (clips.length === 0) break;
      if (clips.every((c) => typeof c.audio_storage_key === "string")) break;
      if (attempt < 3) await new Promise((r) => setTimeout(r, 1500 * attempt));
    }
    if (!AUDIO_CLIP_JOB_TYPES.has(job.type)) {
      job.status = "complete";
      return;
    }
    const missing = clips.filter((c) => typeof c.audio_storage_key !== "string");
    if (missing.length > 0) {
      job.status = "error";
      job.error = "audio_ingest_failed";
      console.error(
        `[storage] job ${job.id} (${job.type}) produced no durable audio for ${missing.length} clip(s); failing instead of reporting empty success.`,
      );
      return;
    }
    job.status = "complete";
  }

  async function finalizeJob(job: Job): Promise<void> {
    // Durable delivery FIRST: copy finished media into B2 and rewrite the result
    // to stable URLs. A terminal success always requires a real playable URL for
    // audio jobs, so nothing can report success with an empty audio_url.
    if (job.status === "complete") {
      // Lyrics detail reads a clip whose audio the originating music job already
      // stored; re-ingesting it here was slow and consumed a Suno slot on every
      // lookup. Skip durable-media handling for it (and fall through to the
      // storage-configured gate only for jobs that produce media).
      if (storageConfigured() && job.type !== "timestamped_lyrics_detail") {
        // Gate the terminal state on durable media: while we decrypt + copy to
        // B2, keep reporting the job as still-running so a poll never receives
        // an empty audio_url; it flips to complete only once the B2 copy exists.
        job.status = "running";
        await ensureDurableAudio(job);
      } else if (!storageConfigured() && AUDIO_CLIP_JOB_TYPES.has(job.type)) {
        // No storage => we cannot produce a durable, playable URL. Fail
        // (refundable) instead of a false success, matching sunoapi.org's
        // "success means a playable URL" contract.
        job.status = "error";
        job.error = "media_storage_not_configured";
        console.error(
          `[storage] job ${job.id} (${job.type}) cannot complete: object storage is not configured.`,
        );
      }
    }
    if (job.status === "complete" || job.status === "error") job.completedAt ??= Date.now();
    await saveJob(job);
    // Log every user-attributed job, not only key-charged ones: free endpoints
    // reached from the session UI (and any priced-at-0 row) carry a userId but
    // no apiKeyId, and would otherwise leave no usage trail. `settleCredits`
    // no-ops when there is nothing to charge or refund.
    if (job.userId) {
      await settleCredits(job);
      await recordUsage({
        userId: job.userId,
        apiKeyId: job.apiKeyId ?? null,
        endpoint: job.endpoint ?? job.type,
        model: job.model,
        prompt: job.prompt,
        status: job.status,
        // Net credits: a failed job is refunded, so it must not count as spend
        // (safe-spend limits sum usage_logs.credits_consumed) nor show as
        // charged in the dashboard. The gross charge stays in credit_transactions.
        credits: job.status === "error" ? 0 : (job.credits ?? 0),
        taskId: job.id,
        result: job.result,
      });
    }
    await notify(job);
  }

  /**
   * Copy a completed job's finished media into object storage (Backblaze B2),
   * storing the object key on each track and (re)writing stable read URLs.
   * Best-effort: any failure leaves the original Suno URLs in place, so a
   * storage outage degrades to live streaming rather than breaking the job.
   */
  async function ingestMedia(job: Job): Promise<void> {
    if (!storageConfigured()) return;
    const items: Array<Record<string, unknown>> = [];
    collectClipObjects(job.result, items);
    if (items.length === 0) return;

    let client: SunoClient | null = null;
    const accountClient = async (): Promise<SunoClient> => {
      if (client) return client;
      // Prefer the account that generated the clip; its license authorizes the
      // decrypt. Fall back to any healthy account.
      const owning = job.accountId ? pool.get(job.accountId) : null;
      client = owning ?? (await pool.pick());
      return client;
    };
    let changed = false;
    for (const item of items) {
      const clipId = typeof item.id === "string" ? item.id : undefined;
      if (!clipId) continue;

      // Audio: the progressive URL is AES-CTR encrypted (Suno "mango" DRM).
      // Fetch its license with the owning account and decrypt server-side, then
      // store a playable MP3 plus the decrypted m4a master (source for WAV).
      if (!item.audio_storage_key) {
        try {
          const encryptedUrl = pickPublicAudioUrl(item) ?? undefined;
          const m4a = await decryptSunoClip(await accountClient(), clipId, encryptedUrl);
          const mp3Key = objectKey("clips", `${clipId}.mp3`);
          const wavKey = objectKey("wav", `${clipId}.wav`);
          const masterKey = objectKey("masters", `${clipId}.m4a`);
          const mp3 = await transcodeAudio(m4a, "mp3");
          const wav = await transcodeAudio(m4a, "wav");
          await putObject(mp3Key, mp3, "audio/mpeg");
          await putObject(wavKey, wav, "audio/wav");
          await putObject(masterKey, m4a, "audio/mp4");
          item.audio_storage_key = mp3Key;
          item.master_storage_key = masterKey;
          changed = true;
        } catch (e) {
          console.error(`[storage] audio ingest failed for ${clipId}:`, e instanceof Error ? e.message : e);
        }
      }

      // Image: cover art is a public URL, mirror it directly.
      const imageUrl = (item.image_url as string) || (item.imageUrl as string);
      if (typeof imageUrl === "string" && /^https?:\/\//.test(imageUrl) && !item.image_storage_key) {
        try {
          const resp = await fetch(imageUrl, { signal: AbortSignal.timeout(30_000) });
          if (resp.ok) {
            const ct = resp.headers.get("content-type") || "image/jpeg";
            if (/^image\//.test(ct)) {
              const bytes = Buffer.from(await resp.arrayBuffer());
              const ext = ct.includes("png") ? "png" : ct.includes("webp") ? "webp" : "jpg";
              const key = objectKey("images", `${clipId}.${ext}`);
              await putObject(key, bytes, ct);
              item.image_storage_key = key;
              changed = true;
            }
          }
        } catch (e) {
          console.error(`[storage] image ingest failed for ${clipId}:`, e instanceof Error ? e.message : e);
        }
      }

      const audioKey = item.audio_storage_key;
      if (typeof audioKey === "string") {
        const url = await getReadUrl(audioKey);
        if (url) {
          item.audio_url = url;
          item.audioUrl = url;
          item.stream_audio_url = url;
          item.streamAudioUrl = url;
        }
      }
      const imageKey = item.image_storage_key;
      if (typeof imageKey === "string") {
        const url = await getReadUrl(imageKey);
        if (url) {
          item.image_url = url;
          item.imageUrl = url;
        }
      }
    }

    if (changed) {
      await saveJob(job).catch((e) =>
        console.error("[storage] persist failed:", e instanceof Error ? e.message : e),
      );
    }
  }

  /**
   * Ensure a durable, playable copy of a clip exists and return its object key.
   * MP3 comes straight from ingest; WAV is transcoded from the decrypted m4a
   * master (or a fresh decrypt when the master is missing). Returns null when
   * storage is off or the decrypt/transcode fails.
   */
  async function ensureAudio(
    clipId: string,
    format: "mp3" | "wav",
    accountId?: string | null,
  ): Promise<string | null> {
    if (!storageConfigured()) return null;
    const targetKey = objectKey(format === "wav" ? "wav" : "clips", `${clipId}.${format}`);
    if (await objectExists(targetKey)) return targetKey;

    const masterKey = objectKey("masters", `${clipId}.m4a`);
    let source: Buffer | null = null;
    if (await objectExists(masterKey)) {
      source = await getObjectBytes(masterKey);
    }
    if (!source) {
      try {
        // Prefer the account that generated the clip: its license authorizes
        // the decrypt. Fall back to any healthy account.
        const owning = accountId ? pool.get(accountId) : null;
        const client = owning ?? (await pool.pick());
        source = await decryptSunoClip(client, clipId);
        await putObject(masterKey, source, "audio/mp4");
      } catch (e) {
        console.error(`[me/download] decrypt failed for ${clipId}:`, e instanceof Error ? e.message : e);
        return null;
      }
    }
    if (!source) return null;
    const out = await transcodeAudio(source, format);
    await putObject(targetKey, out, format === "wav" ? "audio/wav" : "audio/mpeg");
    return targetKey;
  }

  /**
   * Complete an audio-delivery job (`wav` / `wav_detail`) from our own media
   * pipeline: reuse the durable B2 copy when present, otherwise decrypt the
   * clip's mango-encrypted stream and transcode it on demand (see
   * `ensureAudio`). This deliberately does NOT touch Suno's `/api/download/*`,
   * which is gated by a per-account monthly download quota and returns
   * `{ok:false, reason:"not_authorized"}` once spent. Serving from our own
   * storage is how sunoapi.org keeps downloads working regardless of the
   * upstream account's quota. 0-credit jobs, so they aren't queue-durable.
   */
  async function runAudioDeliveryJob(
    job: Job,
    clipId: string,
    format: "mp3" | "wav",
    musicIndex = 0,
  ): Promise<void> {
    try {
      if (!storageConfigured()) throw new Error("Media storage is not configured.");
      const key = await ensureAudio(clipId, format);
      if (!key) throw new Error(`Could not prepare the ${format.toUpperCase()} for this clip.`);
      const url = await getReadUrl(key);
      if (!url) throw new Error("Could not sign the media URL.");
      job.result = {
        clip_id: clipId,
        music_index: musicIndex,
        format,
        download_url: url,
        audio_url: url,
        url,
        ...(format === "wav" ? { wav_url: url } : {}),
      };
      job.status = "complete";
    } catch (e) {
      job.status = "error";
      job.error = e instanceof Error ? e.message : String(e);
    }
    await finalizeJob(job);
  }

  /**
   * Complete a music-video job from our own renderer: the track's cover art plus
   * a live waveform, encoded to MP4 and stored on B2. Suno exposes no video
   * API, so — like sunoapi.org, which returns its own `videoUrl` — we produce
   * the MP4 ourselves. 2-credit job; not queue-durable.
   */
  async function runMusicVideoJob(job: Job, clipId: string, aspect = "16:9"): Promise<void> {
    try {
      if (!storageConfigured()) throw new Error("Media storage is not configured.");
      const audioKey = await ensureAudio(clipId, "mp3");
      if (!audioKey) throw new Error("Could not prepare the audio for this video.");
      const audio = await getObjectBytes(audioKey);

      // Cover art: prefer our stored copy, else pull the live clip image.
      let image: Buffer | null = null;
      let imageExt: "jpg" | "png" | "webp" = "jpg";
      for (const ext of ["jpg", "png", "webp"] as const) {
        const key = objectKey("images", `${clipId}.${ext}`);
        if (await objectExists(key)) {
          image = await getObjectBytes(key);
          imageExt = ext;
          break;
        }
      }
      if (!image) {
        try {
          const client = await pool.pick();
          const clip = await client.getClipObject(clipId);
          const url = (clip.image_url as string) || (clip.imageUrl as string);
          if (typeof url === "string" && /^https?:\/\//.test(url)) {
            const resp = await fetch(url, { signal: AbortSignal.timeout(30_000) });
            if (resp.ok) {
              const ct = resp.headers.get("content-type") ?? "";
              image = Buffer.from(await resp.arrayBuffer());
              imageExt = ct.includes("png") ? "png" : ct.includes("webp") ? "webp" : "jpg";
            }
          }
        } catch {
          /* fall back to the solid background */
        }
      }

      const mp4 = await renderMusicVideo({ audio, image, imageExt, audioExt: "mp3", aspect });
      const key = objectKey("videos", `${clipId}.mp4`);
      await putObject(key, mp4, "video/mp4");
      const url = await getReadUrl(key);
      if (!url) throw new Error("Could not sign the video URL.");
      job.result = { clip_id: clipId, video_url: url, download_url: url, url };
      job.status = "complete";
    } catch (e) {
      job.status = "error";
      job.error = e instanceof Error ? e.message : String(e);
    }
    await finalizeJob(job);
  }

  /** Basic Pitch MIDI microservice (see `musicapi/midi-service`). */
  const MIDI_SERVICE_URL = process.env.MIDI_SERVICE_URL ?? "http://127.0.0.1:4010";
  const MIDI_SERVICE_TOKEN = (process.env.MIDI_SERVICE_TOKEN ?? "").trim();

  /** POST one stem's audio to the Basic Pitch service; returns its note events. */
  async function transcribeStem(
    audio: Buffer,
    name: string,
  ): Promise<{ name: string; notes: Array<Record<string, unknown>> }> {
    const res = await fetch(`${MIDI_SERVICE_URL}/transcribe`, {
      method: "POST",
      headers: {
        "content-type": "audio/mpeg",
        "x-stem-name": (name || "Instrument").slice(0, 80),
        ...(MIDI_SERVICE_TOKEN ? { "x-service-token": MIDI_SERVICE_TOKEN } : {}),
      },
      body: new Uint8Array(audio),
      signal: AbortSignal.timeout(300_000),
    });
    if (!res.ok) throw new Error(`midi-service HTTP ${res.status}`);
    const data = (await res.json()) as { ok?: boolean; error?: string; name?: string; notes?: unknown };
    if (!data.ok) throw new Error(`midi-service: ${data.error ?? "failed"}`);
    return {
      name: typeof data.name === "string" && data.name ? data.name : name || "Instrument",
      notes: Array.isArray(data.notes) ? (data.notes as Array<Record<string, unknown>>) : [],
    };
  }

  /** Read a stem clip's audio (stored B2 copy, else decrypt/transcode on demand). */
  async function stemAudio(clip: Record<string, unknown>): Promise<Buffer | null> {
    const key = clip.audio_storage_key;
    if (typeof key === "string") {
      try {
        return await getObjectBytes(key);
      } catch {
        /* fall through to on-demand */
      }
    }
    const id = typeof clip.id === "string" ? clip.id : null;
    if (!id) return null;
    const ensured = await ensureAudio(id, "mp3");
    if (!ensured) return null;
    return getObjectBytes(ensured);
  }

  /**
   * faster-whisper lyric-alignment microservice (see `musicapi/lrc-service`).
   * Suno's direct API returns lyric text but no timing; we compute it ourselves.
   * Set `LRC_SERVICE_ENABLED=0` to force the plain-lyrics fallback.
   */
  const LRC_SERVICE_URL = process.env.LRC_SERVICE_URL ?? "http://127.0.0.1:4011";
  const LRC_SERVICE_TOKEN = (process.env.LRC_SERVICE_TOKEN ?? "").trim();
  const LRC_ENABLED = process.env.LRC_SERVICE_ENABLED !== "0";
  // Suno provides the alignment for generated clips (see `client.getAlignedLyrics`),
  // so the local Whisper aligner is now only a fallback. It is opt-in: enabling it
  // by default risks the runaway decode / CPU burn it caused on the Khmer corpus.
  // Set `LRC_FALLBACK_ENABLED=1` to re-enable it for clips Suno has no alignment for.
  const LRC_FALLBACK_ENABLED = process.env.LRC_FALLBACK_ENABLED === "1";

  // The aligner serialises transcription on one CPU box, so only a couple of
  // requests should be in flight from this side: firing the whole batch at once
  // overflows it (503 / connection resets) and every failure re-queues, which is
  // a retry storm. A small in-process gate keeps the sidecar fed without
  // thrashing. Slots transfer directly to the next waiter on release.
  const LRC_MAX_CONCURRENT = Number(process.env.LRC_MAX_CONCURRENT ?? 2);
  let lrcActive = 0;
  const lrcWaiters: Array<() => void> = [];
  async function acquireLrcSlot(): Promise<void> {
    if (lrcActive < LRC_MAX_CONCURRENT) {
      lrcActive++;
      return;
    }
    await new Promise<void>((resolve) => lrcWaiters.push(resolve));
  }
  function releaseLrcSlot(): void {
    const next = lrcWaiters.shift();
    if (next) next();
    else lrcActive--;
  }

  interface LyricAlignment {
    lines: AlignedLine[];
    words: AlignedWord[];
    lrc: string;
  }

  /**
   * Align a clip's known lyric text against its own audio via the LRC service.
   * Returns `null` (never throws) when media storage, the service, or the
   * alignment itself is unavailable, so callers fall back to plain lyrics.
   */
  async function alignLyrics(clipId: string, lyrics: string): Promise<LyricAlignment | null> {
    if (!LRC_ENABLED || !lyrics.trim() || !storageConfigured()) return null;
    // Instrumentals and section-only prompts ("[Instrumental]", "[Verse]") carry
    // no words to time. Transcribing them burns ~a minute of CPU on the sidecar
    // and starves real vocal requests, so skip them (result: aligned:false).
    const wordTokens = lyrics.replace(/\[[^\]]*\]/g, " ").match(/[\p{L}\p{N}]+/gu) ?? [];
    if (wordTokens.length < 2) return null;
    const audioKey = await ensureAudio(clipId, "mp3");
    if (!audioKey) return null;

    const body: Record<string, unknown> = { lyrics };
    const url = await getReadUrl(audioKey);
    if (url) body.url = url;
    else body.audio_b64 = (await getObjectBytes(audioKey)).toString("base64");

    let res: Response | null = null;
    let lastError = "";
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        await acquireLrcSlot();
        try {
          res = await fetch(`${LRC_SERVICE_URL}/align`, {
            method: "POST",
            headers: {
              "content-type": "application/json",
              ...(LRC_SERVICE_TOKEN ? { "x-service-token": LRC_SERVICE_TOKEN } : {}),
            },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(600_000),
          });
        } finally {
          releaseLrcSlot();
        }
        if (res.ok) break;
        lastError = `HTTP ${res.status}`;
        res = null;
      } catch (e) {
        lastError = e instanceof Error ? e.message : String(e);
        res = null;
      }
      // A busy/reset aligner is transient: wait and retry before giving up, so
      // one 503 does not become a cached `aligned:false` + a fresh job.
      if (attempt < 3) await new Promise((r) => setTimeout(r, attempt * 1500));
    }
    if (!res) {
      console.error(`[lrc] align failed for ${clipId}: ${lastError}`);
      return null;
    }
    const data = (await res.json()) as {
      ok?: boolean;
      error?: string;
      lines?: unknown;
      words?: unknown;
      lrc?: unknown;
    };
    if (!data.ok) {
      console.error(`[lrc] align failed for ${clipId}: ${data.error ?? "unknown"}`);
      return null;
    }
    const lines = Array.isArray(data.lines) ? (data.lines as AlignedLine[]) : [];
    const words = Array.isArray(data.words)
      ? (data.words as AlignedWord[])
      : parseAlignedWordsPayload(data);
    if (lines.length === 0 && words.length === 0) return null;
    const lrc =
      typeof data.lrc === "string" && data.lrc
        ? data.lrc
        : lines.length
          ? alignedLinesToLrc(lines)
          : alignedWordsToLrc(words);
    return { lines, words, lrc };
  }

  /**
   * Complete a timestamped-lyrics job from our own alignment pipeline.
   *
   * The clip's lyric text is the transcript; the real audio is aligned against
   * it so `/me/lyrics/:id`, `/v1/lyrics/:id`, and
   * `POST /api/v1/generate/get-timestamped-lyrics` return line-level LRC plus
   * word/line timings. Falls back to plain lyrics (`aligned: false`) when the
   * microservice or media pipeline is unavailable — never fabricates timing.
   */
  async function runTimestampedLyricsJob(job: Job, clipId: string): Promise<void> {
    try {
      job.status = "running";
      const client = await pool.pick();
      const clip = await client.getClipObject(clipId);
      const meta = (clip.metadata ?? {}) as Record<string, unknown>;
      const lyrics = typeof meta.prompt === "string" ? meta.prompt : "";

      // Suno already computes word-level alignment for its karaoke player and
      // exposes it per clip — the same data sunoapi.org resells as
      // `alignedWords`. Use it first: instant and language-agnostic (works for
      // Khmer, where the local Whisper ASR ran away). Fall back to the Whisper
      // sidecar only when Suno has no alignment for this clip.
      let words: AlignedWord[] = [];
      try {
        words = normalizeSunoAlignedWords(await client.getAlignedLyrics(clipId));
      } catch (e) {
        console.error(`[suno] aligned_lyrics failed for ${clipId}:`, e instanceof Error ? e.message : e);
      }
      let alignment: LyricAlignment | null = words.length
        ? { lines: [], words, lrc: alignedWordsToLrc(words) }
        : null;
      if ((!alignment || !alignment.lrc) && LRC_FALLBACK_ENABLED && lyrics.trim()) {
        alignment = (await alignLyrics(clipId, lyrics)) ?? alignment;
      }
      job.result = {
        ...clip,
        lyrics,
        aligned: Boolean(alignment && (alignment.lrc || alignment.words.length > 0)),
        lrc: alignment?.lrc ?? "",
        lrc_format: alignment?.lrc ? "lrc" : null,
        aligned_lines: alignment?.lines ?? [],
        aligned_words: alignment?.words ?? [],
      };
      job.status = "complete";
    } catch (e) {
      job.status = "error";
      job.error = e instanceof Error ? e.message : String(e);
    }
    await finalizeJob(job);
  }

  /**
   * Complete a MIDI job by transcribing audio with the Basic Pitch service.
   * The source is a completed vocal-separation task (`sourceTaskId`, optionally
   * narrowed by `audioId`) or a single clip (`clipId`). Suno has no MIDI API, so
   * — like sunoapi.org — we transcribe the stems ourselves. 3-credit job.
   */
  async function runMidiJob(
    job: Job,
    params: { sourceTaskId?: string; audioId?: string; clipId?: string },
  ): Promise<void> {
    try {
      const instruments: Array<{ name: string; notes: Array<Record<string, unknown>> }> = [];

      if (params.sourceTaskId) {
        const parent = await getJob(params.sourceTaskId);
        if (!parent) throw new Error("Source separation task not found.");
        const clips: Array<Record<string, unknown>> = [];
        collectClipObjects(parent.result, clips);
        let selected = clips;
        if (params.audioId) {
          selected = clips.filter((c) => c.id === params.audioId);
          if (selected.length === 0) throw new Error("No separated audio for the requested audioId.");
        }
        for (const c of selected) {
          const meta = (c.metadata ?? {}) as Record<string, unknown>;
          const name =
            String(meta.stem_type_group_name ?? c.title ?? "Instrument")
              .replace(/[()]/g, "")
              .trim() || "Instrument";
          const audio = await stemAudio(c);
          if (audio) instruments.push(await transcribeStem(audio, name));
        }
        if (instruments.length === 0) throw new Error("No audio to transcribe.");
      } else if (params.clipId) {
        const key = await ensureAudio(params.clipId, "mp3");
        if (!key) throw new Error("Could not prepare audio for MIDI.");
        instruments.push(await transcribeStem(await getObjectBytes(key), "Instrument"));
      } else {
        throw new Error("taskId or clip_id is required.");
      }

      job.result = {
        midi_data: { state: "complete", instruments },
        audio_id: params.audioId ?? params.clipId ?? null,
        source_task_id: params.sourceTaskId ?? null,
      };
      job.status = "complete";
    } catch (e) {
      job.status = "error";
      job.error = e instanceof Error ? e.message : String(e);
    }
    await finalizeJob(job);
  }

  /**
   * Complete a recovery job: return fresh playable audio links for an existing
   * generation task (`sunoTaskId`) or a single clip — sunoapi.org's "Recovery
   * Audio" recovers links, it does not generate. We re-sign the durable B2 copy
   * (decrypting/transcoding on demand when it is missing). No credits spent on
   * Suno.
   */
  async function runRecoveryJob(
    job: Job,
    params: { sunoTaskId?: string; clipId?: string },
  ): Promise<void> {
    const tracks: Array<Record<string, unknown>> = [];
    try {
      let clips: Array<Record<string, unknown>> = [];
      let owningAccountId: string | null = null;
      if (params.sunoTaskId) {
        const src = await getJob(params.sunoTaskId);
        if (src) {
          if (typeof src.accountId === "string") owningAccountId = src.accountId;
          collectClipObjects(src.result, clips);
        }
      } else if (params.clipId) {
        clips = [{ id: params.clipId, title: "" }];
      }
      if (clips.length === 0) throw new Error("no_audio_id_mappings");

      for (const c of clips) {
        const id = typeof c.id === "string" ? c.id : null;
        const title = typeof c.title === "string" ? c.title : "";
        if (!id) {
          tracks.push({ id: null, audio_url: "", title, status: "failed", error: "no_audio_id_mappings" });
          continue;
        }
        try {
          let url: string | null = null;
          const key = c.audio_storage_key;
          // Only reuse a stored object that actually exists: getReadUrl()
          // synthesizes a URL without checking, so an absent object would be
          // reported as a successful recovery and re-probed forever.
          if (typeof key === "string" && (await objectExists(key))) {
            url = await getReadUrl(key);
          }
          if (!url) {
            const ensured = await ensureAudio(id, "mp3", owningAccountId);
            if (ensured) url = await getReadUrl(ensured);
          }
          tracks.push(
            url
              ? { id, audio_url: url, title, status: "success", error: "" }
              : { id, audio_url: "", title, status: "failed", error: "mango_transfer_failed" },
          );
        } catch (e) {
          tracks.push({
            id,
            audio_url: "",
            title,
            status: "failed",
            error: e instanceof Error ? e.message : "clip_error",
          });
        }
      }
      job.result = { tracks };
      if (tracks.some((t) => t.status === "success")) {
        job.status = "complete";
      } else {
        job.status = "error";
        job.error = "All tracks failed to recover.";
      }
    } catch (e) {
      job.status = "error";
      job.error = e instanceof Error ? e.message : String(e);
      job.result = { tracks };
    }
    await finalizeJob(job);
  }

  /**
   * Complete a custom-voice job: verify the user's recording of the validation
   * phrase against the source voice, matching sunoapi.org's voice/generate. The
   * `taskId` is the validation job (for its phrase_id + source voice_recording_id);
   * `verifyUrl` is the user's spoken recording. Requires a Voice-entitled account.
   */
  async function runCustomVoiceJob(
    job: Job,
    params: { validationTaskId: string; verifyUrl: string; voiceName?: string },
  ): Promise<void> {
    try {
      const src = await getJob(params.validationTaskId);
      if (!src) throw new Error("Validation task not found.");
      const sr = (src.result ?? {}) as Record<string, unknown>;
      const phraseId = typeof sr.phrase_id === "string" ? sr.phrase_id : undefined;
      const voiceRecordingId = typeof sr.voice_recording_id === "string" ? sr.voice_recording_id : undefined;
      if (!phraseId) throw new Error("Validation phrase is not ready for this task.");
      if (!voiceRecordingId) {
        throw new Error(
          "Source voice recording is unavailable — the source must be extracted on a Voice-entitled (Premier) account.",
        );
      }
      const client = await pool.pickFeature("studio");
      const resp = await fetch(params.verifyUrl, { signal: AbortSignal.timeout(60_000) });
      if (!resp.ok) throw new Error(`Could not download verifyUrl (${resp.status}).`);
      // Create the verification recording: upload the recording, then extract it
      // with recording_type="verification" (the field the create-voice UI sends).
      const uploadId = await client.uploadForVoice(Buffer.from(await resp.arrayBuffer()));
      const vstem = await client.voiceVoxStem(uploadId, "verification");
      const verificationRecordingId =
        (vstem.voice_recording_id as string) ?? (vstem.id as string) ?? "";
      if (!verificationRecordingId) throw new Error("Could not create the verification recording.");
      let verified = await client.verifyVoice({ phraseId, voiceRecordingId, verificationRecordingId });
      let status = typeof verified.status === "string" ? verified.status : "";
      if (status === "pending") {
        for (let i = 0; i < 40; i++) {
          await new Promise((r) => setTimeout(r, 1500));
          verified = await client.getVoiceVerification(String(verified.id));
          status = typeof verified.status === "string" ? verified.status : "";
          if (status && status !== "pending") break;
        }
      }
      if (status !== "approved") {
        throw new Error(
          `Voice verification ${status || "failed"}${verified.rejection_reason ? ` (${String(verified.rejection_reason)})` : ""}.`,
        );
      }
      job.result = {
        voice_verification: verified,
        voice_id: (verified.id as string) ?? null,
        voice_name: params.voiceName ?? null,
      };
      job.status = "complete";
    } catch (e) {
      job.status = "error";
      job.error = e instanceof Error ? e.message : String(e);
    }
    await finalizeJob(job);
  }

  /**
   * Index of a clip within its originating generation task (0 or 1), matching
   * sunoapi.org's `musicIndex`. Returns 0 when the task is unknown or the clip
   * isn't found, so the field is always present and sane.
   */
  async function clipIndexInTask(taskId: string | undefined, clipId: string): Promise<number> {
    if (!taskId) return 0;
    try {
      const parent = await getJob(taskId);
      if (!parent) return 0;
      const clips: Array<Record<string, unknown>> = [];
      collectClipObjects(parent.result, clips);
      const idx = clips.findIndex((c) => c.id === clipId);
      return idx > 0 ? idx : 0;
    } catch {
      return 0;
    }
  }

  const RETRYABLE_ERROR = /captcha|timeout|timed out|rate limit|5\d{2}|no healthy|No healthy/i;

  interface RetryOptions {
    model?: string;
    policy?: RoutingPolicy;
    /** Prefer an account advertising this capability (e.g. "studio" for Voice). */
    needFeature?: string;
  }

  // Detached job workers run outside any request lifecycle. Track them so
  // shutdown can drain in-flight work, and attach a `.catch()` so a rejected
  // worker (e.g. a DB error inside `finalizeJob`) can never crash the process as
  // an unhandled rejection.
  const inflight = new Set<Promise<void>>();
  function trackJob(p: Promise<void>): Promise<void> {
    const handled = p.catch((e) => {
      console.error("[jobs] worker rejected:", e instanceof Error ? e.stack ?? e.message : e);
    });
    inflight.add(handled);
    void handled.finally(() => inflight.delete(handled));
    return handled;
  }

  /** Await in-flight workers, bounded by `timeoutMs`, for graceful shutdown. */
  async function drainJobs(timeoutMs = 30_000): Promise<void> {
    if (inflight.size === 0) return;
    const pending = [...inflight];
    console.log(`[jobs] draining ${pending.length} in-flight job(s)...`);
    await Promise.race([
      Promise.allSettled(pending),
      new Promise((resolve) => setTimeout(resolve, timeoutMs)),
    ]);
  }

  app.addHook("onClose", async () => {
    stopAlertLoop();
    stopSessionKeepAlive();
    await drainJobs();
    // Queued jobs have their own drain: `worker.close()` resolves once the job
    // currently being consumed finishes, bounded so a stuck job cannot hang the
    // shutdown indefinitely.
    await queue.drain();
    await queue.close();
  });

  /**
   * Per-user concurrent-job cap: the user's `rate_limits.max_concurrent_jobs`
   * override, else the configured default. Jobs with no user share one
   * `"system"` owner bounded only by the global ceiling.
   */
  async function sunoUserCap(userId: string | undefined): Promise<number> {
    if (!userId) return Number.MAX_SAFE_INTEGER;
    const limits = await loadUserRateLimits(userId);
    return limits?.maxConcurrentJobs ?? config.suno.maxConcurrentPerUser;
  }

  /** Run `fn` while holding one global + one per-user Suno slot. */
  async function withSunoSlot<T>(job: Job, fn: () => Promise<T>): Promise<T | undefined> {
    const owner = job.userId ?? "system";
    let release: () => void;
    try {
      release = await sunoSlots.acquire(owner, await sunoUserCap(job.userId));
    } catch (e) {
      if (e instanceof QueueFullError) {
        // The backlog is at its bound: fail the job out (refund + callback)
        // with a retryable error rather than queueing it indefinitely.
        job.status = "error";
        job.error = "Server busy: too many queued jobs. Please retry shortly.";
        await finalizeJob(job);
        return undefined;
      }
      throw e;
    }
    try {
      return await fn();
    } finally {
      release();
    }
  }

  function runClipJobWithRetry(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<import("./client.js").Clip[]>,
    options?: RetryOptions,
  ): Promise<void> {
    return trackJob(withSunoSlot(job, () => runClipJobWithRetryImpl(job, submitFactory, options)));
  }

  async function runClipJobWithRetryImpl(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<import("./client.js").Clip[]>,
    options?: RetryOptions,
  ): Promise<void> {
    const excludeAttemptedIds: string[] = [];
    const maxAttempts = Math.min(3, pool.size);
    const errors: string[] = [];
    const accountOpts = { load: accountLoad, maxPerAccount: config.suno.maxConcurrentPerAccount };

    await saveJob(job);
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      let client: SunoClient;
      try {
        client = options?.needFeature
          ? await pool.pickFeatureExcept(options.needFeature, excludeAttemptedIds, options.model, options.policy ?? "any", accountOpts)
          : await pool.pickExcept(excludeAttemptedIds, options?.model, options?.policy ?? "any", accountOpts);
      } catch (e) {
        errors.push(e instanceof Error ? e.message : String(e));
        break;
      }
      excludeAttemptedIds.push(client.account.id);

      job.status = "running";
      job.accountId = client.account.id;
      await saveJob(job);
      markAccountStart(client.account.id);
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
      } finally {
        markAccountEnd(client.account.id);
      }
    }

    job.status = "error";
    job.error = `All ${errors.length} attempts failed: ${errors.join("; ")}`;
    await finalizeJob(job);
  }

  /** Run an operation that returns a raw result (not clips to poll), with cross-account retry. */
  function runResultJobWithRetry(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<unknown>,
    options?: RetryOptions,
  ): Promise<void> {
    return trackJob(withSunoSlot(job, () => runResultJobWithRetryImpl(job, submitFactory, options)));
  }

  async function runResultJobWithRetryImpl(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<unknown>,
    options?: RetryOptions,
  ): Promise<void> {
    const excludeAttemptedIds: string[] = [];
    const maxAttempts = Math.min(3, pool.size);
    const errors: string[] = [];
    const accountOpts = { load: accountLoad, maxPerAccount: config.suno.maxConcurrentPerAccount };

    await saveJob(job);
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      let client: SunoClient;
      try {
        client = options?.needFeature
          ? await pool.pickFeatureExcept(options.needFeature, excludeAttemptedIds, options.model, options.policy ?? "any", accountOpts)
          : await pool.pickExcept(excludeAttemptedIds, options?.model, options?.policy ?? "any", accountOpts);
      } catch (e) {
        errors.push(e instanceof Error ? e.message : String(e));
        break;
      }
      excludeAttemptedIds.push(client.account.id);

      job.status = "running";
      job.accountId = client.account.id;
      await saveJob(job);
      markAccountStart(client.account.id);
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
      } finally {
        markAccountEnd(client.account.id);
      }
    }

    job.status = "error";
    job.error = `All ${errors.length} attempts failed: ${errors.join("; ")}`;
    await finalizeJob(job);
  }

  /**
   * Run a submission from its descriptor, in this process.
   *
   * This is the single execution path for descriptor-backed jobs:
   * `submitDescribedJob` uses it inline, and `consumeQueuedJob` uses it for
   * anything that arrives over the queue — so a job behaves the same whether it
   * ran here or on another node.
   */
  async function runDescribedJob(job: Job, descriptor: JobDescriptor): Promise<void> {
    // Recovery re-signs an existing job's stored media and needs local helpers
    // (getJob/ensureAudio), not a Suno client call.
    if (descriptor.op === "recovery_audio") {
      const args = descriptor.args ?? {};
      await runRecoveryJob(job, {
        sunoTaskId: typeof args.sunoTaskId === "string" ? args.sunoTaskId : undefined,
        clipId: typeof args.clipId === "string" ? args.clipId : undefined,
      });
      return;
    }
    // Timestamped lyrics have no upstream alignment source on Suno's direct
    // API; when the LRC microservice is enabled we produce the timing ourselves
    // instead of running the plain-lyrics `JOB_OPS` fallback.
    if (descriptor.op === "timestamped_lyrics_detail" && LRC_ENABLED) {
      await runTimestampedLyricsJob(job, String((descriptor.args ?? {}).id ?? ""));
      return;
    }
    const op = JOB_OPS[descriptor.op];
    if (!op) {
      job.status = "error";
      job.error = `Unknown job operation: ${descriptor.op}`;
      await finalizeJob(job);
      return;
    }
    const args = descriptor.args ?? {};
    const options: RetryOptions = {
      model: descriptor.options?.model,
      policy: descriptor.options?.policy as RoutingPolicy | undefined,
    };
    if (op.mode === "clip") {
      await runClipJobWithRetry(
        job,
        (client) => op.run(client, args) as Promise<import("./client.js").Clip[]>,
        options,
      );
      return;
    }
    await runResultJobWithRetry(job, (client) => op.run(client, args), options);
  }

  /**
   * Submit a job whose work is fully described by a serializable descriptor.
   *
   * With the default in-memory driver this resolves the descriptor and runs it
   * inline, exactly like the closure it replaces. With `QUEUE_DRIVER=redis` the
   * descriptor is persisted to `jobs.payload` and the job id is queued, so a
   * consumer runs it and a crash mid-flight no longer loses the work.
   *
   * Never rejects: callers `void` it, and every failure path settles the job
   * (refund + callback) instead of escaping as an unhandled rejection.
   */
  async function submitDescribedJob(job: Job, descriptor: JobDescriptor): Promise<void> {
    job.payload = descriptor;
    if (!queue.async) {
      await runDescribedJob(job, descriptor);
      return;
    }
    try {
      // Persist before enqueuing: the consumer rebuilds the submission from this
      // row, so the descriptor must be visible before the id reaches Redis.
      await saveJob(job);
      await queue.enqueue(job.id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error(`[jobs] could not queue ${job.id}: ${msg}`);
      job.status = "error";
      job.error = `Could not queue job: ${msg}`;
      try {
        await finalizeJob(job);
      } catch (err) {
        console.error("[jobs] failed to settle unqueued job:", err instanceof Error ? err.message : err);
      }
    }
  }

  /**
   * Run one queued job, identified by its `jobs` row id. The row is the source
   * of truth: an id whose row is already terminal (another node finished it) is
   * a no-op, and a row with no runnable descriptor is failed out because the
   * process that could have run it no longer exists.
   */
  async function consumeQueuedJob(jobId: string): Promise<void> {
    if (!jobId) return;
    const job = await getJob(jobId);
    if (!job) return;
    if (job.status === "complete" || job.status === "error") return;
    if (!isRunnableDescriptor(job.payload)) {
      job.status = "error";
      job.error = "Interrupted before completion and has no resumable descriptor.";
      await finalizeJob(job);
      return;
    }
    await runDescribedJob(job, job.payload);
  }

  /** Whether a request carries any reference media (image/audio/video). */
  function hasReferenceMedia(params: Record<string, unknown>): boolean {
    const arrays = [
      params.imageUrls,
      params.image_urls,
      params.audioUrls,
      params.audio_urls,
      params.videoUrls,
      params.video_urls,
      params.images,
    ];
    return arrays.some((a) => Array.isArray(a) && a.length > 0);
  }

  function buildMusicGen(params: Record<string, unknown>) {
    const tags = params.tags as string | undefined;
    const prompt = params.prompt as string | undefined;
    return {
      // Custom mode carries the style in `tags` and the lyrics in `prompt`.
      // Only use `prompt` as Suno's song-description field when there is no
      // style (the non-custom "describe your song" case); otherwise the lyrics
      // leak into gpt_description_prompt and can override/dilute the style —
      // the sunoapi.org-compat alias sent the lyrics here.
      gptDescriptionPrompt: (params.gpt_description_prompt ?? (tags ? undefined : prompt)) as string | undefined,
      prompt,
      tags,
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
      variety:
        params.variety != null
          ? Number(params.variety)
          : undefined,
    };
  }

  function processMusicSubmit(params: Record<string, unknown>) {
    const gen = buildMusicGen(params);
    return (client: SunoClient) => client.generateMusic(gen);
  }

  /** Reference image URLs from a request body (camelCase or snake_case). */
  function referenceImageUrls(params: Record<string, unknown>): string[] {
    const raw = params.imageUrls ?? params.image_urls;
    return Array.isArray(raw)
      ? raw.filter((u): u is string => typeof u === "string" && /^https?:\/\//i.test(u))
      : [];
  }

  /** Fetch a reference image URL and upload it to Suno for the given account.
   *  Image ids are account-scoped, so this runs with the same client that will
   *  generate. */
  async function uploadReferenceImage(client: SunoClient, url: string): Promise<string> {
    const resp = await fetch(url, { signal: AbortSignal.timeout(30_000), redirect: "follow" });
    if (!resp.ok) throw new Error(`reference image fetch failed (${resp.status})`);
    const ct = (resp.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!ct.startsWith("image/")) throw new Error(`reference URL is not an image (${ct || "unknown"})`);
    const ext = ct.includes("png") ? "png" : ct.includes("webp") ? "webp" : "jpg";
    const bytes = Buffer.from(await resp.arrayBuffer());
    if (bytes.length > 10 * 1024 * 1024) throw new Error("reference image exceeds 10MB");
    return client.uploadImage(bytes, ext);
  }

  /**
   * Music submit that first uploads reference images to the generation account
   * (Suno's `uploadImage` 3-step) and passes `user_uploaded_image_ids` with the
   * `agentic_thinking` task — the flow suno.com's create form uses.
   */
  function processMusicSubmitWithImages(params: Record<string, unknown>, imageUrls: string[]) {
    const gen = buildMusicGen(params);
    return async (client: SunoClient): Promise<import("./client.js").Clip[]> => {
      const imageIds = await Promise.all(imageUrls.map((u) => uploadReferenceImage(client, u)));
      return client.generateMusic({ ...gen, imageIds, task: "agentic_thinking" });
    };
  }

  /** Decode a `data:image/...;base64,...` URL (or raw base64) to bytes + ext. */
  function decodeImageData(dataUrl: string): { bytes: Buffer; ext: string } {
    const m = dataUrl.match(/^data:image\/([a-z0-9.+-]+);base64,(.*)$/is);
    const mime = (m?.[1] ?? "").toLowerCase();
    const b64 = m?.[2] ?? dataUrl;
    const ext = mime.includes("png") ? "png" : mime.includes("webp") ? "webp" : "jpg";
    return { bytes: Buffer.from(b64, "base64"), ext };
  }

  /** Reference images supplied inline (panel upload) as data URLs. */
  function processMusicSubmitWithImageData(params: Record<string, unknown>, dataUrls: string[]) {
    const gen = buildMusicGen(params);
    return async (client: SunoClient): Promise<import("./client.js").Clip[]> => {
      const imageIds = await Promise.all(
        dataUrls.map((d) => {
          const { bytes, ext } = decodeImageData(d);
          return client.uploadImage(bytes, ext);
        }),
      );
      return client.generateMusic({ ...gen, imageIds, task: "agentic_thinking" });
    };
  }

  /** Reference audio URLs from a request body (camelCase or snake_case). */
  function referenceAudioUrls(params: Record<string, unknown>): string[] {
    const raw = params.audioUrls ?? params.audio_urls;
    return Array.isArray(raw)
      ? raw.filter((u): u is string => typeof u === "string" && /^https?:\/\//i.test(u))
      : [];
  }

  /** Fetch a reference audio URL and upload it to Suno, returning the resulting
   *  upload clip id (used as a cover source — Suno retains the melody). */
  async function uploadReferenceAudio(client: SunoClient, url: string): Promise<string> {
    const resp = await fetch(url, { signal: AbortSignal.timeout(60_000), redirect: "follow" });
    if (!resp.ok) throw new Error(`reference audio fetch failed (${resp.status})`);
    const ct = (resp.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!ct.startsWith("audio/") && !ct.includes("octet-stream")) {
      throw new Error(`reference URL is not audio (${ct || "unknown"})`);
    }
    const ext = ct.includes("wav") ? "wav" : ct.includes("ogg") ? "ogg" : ct.includes("flac") ? "flac" : ct.includes("mp4") ? "m4a" : "mp3";
    const bytes = Buffer.from(await resp.arrayBuffer());
    if (bytes.length > 50 * 1024 * 1024) throw new Error("reference audio exceeds 50MB");
    const session = await client.createAudioUpload({ extension: ext, uploadType: "file_upload" });
    const form = new FormData();
    for (const [k, v] of Object.entries(session.fields)) form.append(k, v);
    form.append("file", new Blob([new Uint8Array(bytes)], { type: session.fields["Content-Type"] || ct }), `${session.id}.${ext}`);
    const up = await fetch(session.url, { method: "POST", body: form });
    if (!up.ok && up.status !== 204) throw new Error(`audio S3 upload failed (${up.status})`);
    await client.registerAudioUpload(session.id, { uploadType: "file_upload", uploadFilename: `upload.${ext}` });
    // The upload id itself is the reference (Suno's agentic flow); there is no
    // separate clip id to wait for.
    return session.id;
  }

  /** Music submit from reference audio (upload -> user_uploaded_audio_ids,
   *  task agentic_thinking — the same flow as reference images). */
  function processMusicSubmitWithAudio(params: Record<string, unknown>, audioUrls: string[]) {
    const gen = buildMusicGen(params);
    return async (client: SunoClient): Promise<import("./client.js").Clip[]> => {
      const audioIds = await Promise.all(audioUrls.map((u) => uploadReferenceAudio(client, u)));
      return client.generateMusic({ ...gen, audioIds, task: "agentic_thinking" });
    };
  }

  /** Reference video URLs from a request body (camelCase or snake_case). */
  function referenceVideoUrls(params: Record<string, unknown>): string[] {
    const raw = params.videoUrls ?? params.video_urls;
    return Array.isArray(raw)
      ? raw.filter((u): u is string => typeof u === "string" && /^https?:\/\//i.test(u))
      : [];
  }

  /** Extract a frame from a reference video and upload it to Suno as an image
   *  (Suno has no video input, so a frame drives the image/agentic flow). */
  async function uploadReferenceVideo(client: SunoClient, url: string): Promise<string> {
    const resp = await fetch(url, { signal: AbortSignal.timeout(60_000), redirect: "follow" });
    if (!resp.ok) throw new Error(`reference video fetch failed (${resp.status})`);
    const bytes = Buffer.from(await resp.arrayBuffer());
    if (bytes.length > 100 * 1024 * 1024) throw new Error("reference video exceeds 100MB");
    const frame = await extractVideoFrame(bytes);
    return client.uploadImage(frame, "jpg");
  }

  function processMusicSubmitWithVideo(params: Record<string, unknown>, videoUrls: string[]) {
    const gen = buildMusicGen(params);
    return async (client: SunoClient): Promise<import("./client.js").Clip[]> => {
      const imageIds = await Promise.all(videoUrls.map((u) => uploadReferenceVideo(client, u)));
      return client.generateMusic({ ...gen, imageIds, task: "agentic_thinking" });
    };
  }

  /** Choose the music submit strategy from the request's reference inputs. */
  function musicSubmitFactory(params: Record<string, unknown>, inlineImages?: string[]) {
    if (inlineImages && inlineImages.length) return processMusicSubmitWithImageData(params, inlineImages);
    const imgs = referenceImageUrls(params);
    if (imgs.length) return processMusicSubmitWithImages(params, imgs);
    const vids = referenceVideoUrls(params);
    if (vids.length) return processMusicSubmitWithVideo(params, vids);
    const auds = referenceAudioUrls(params);
    if (auds.length) return processMusicSubmitWithAudio(params, auds);
    return processMusicSubmit(params);
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
      // Suno concurrency: `capacity` is the effective global ceiling, `active`
      // jobs currently holding a slot, `waiting` jobs queued behind them.
      suno: {
        ...sunoSlots.stats(),
        capacity:
          config.suno.maxConcurrent ?? Math.max(1, pool.size * config.suno.concurrentPerAccount),
        maxConcurrentPerUser: config.suno.maxConcurrentPerUser,
        maxConcurrentPerAccount: config.suno.maxConcurrentPerAccount,
        // In-flight jobs per Suno account (fairness view).
        byAccount: Object.fromEntries(accountInflight),
      },
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
    // Also set the httpOnly session cookie so browser clients never have to
    // store the JWT where scripts can read it. Admin uses a distinct cookie name
    // so it never collides with the user app's session on localhost.
    reply.header("set-cookie", serializeSessionCookie(token, config.sessionCookieSecure, SESSION_COOKIE_ADMIN));
    return {
      token,
      user: { id: user.id, email: user.email, role: user.role, name: user.name },
    };
  });

  // Clear the session cookie. Safe to call without a valid session.
  app.post("/auth/logout", async (_req, reply) => {
    // Clear both cookie names so logging out of either app clears its session.
    reply.header("set-cookie", [
      serializeClearedSessionCookie(config.sessionCookieSecure),
      serializeClearedSessionCookie(config.sessionCookieSecure, SESSION_COOKIE_ADMIN),
    ]);
    return { ok: true };
  });

  app.get("/auth/me", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    return queryOne<DbUser>("SELECT id, email, role, name, status FROM users WHERE id = $1", [u.id]);
  });

  // --- Google OAuth (user app only) ----------------------------------------
  // Step 1: Fetch the URL to redirect user to for Google sign-in consent.
  //         Admin must NOT use Google sign-in, so a non-allowlisted
  //         redirect_uri (e.g. the admin console's) is rejected outright
  //         instead of silently falling back.
  app.get("/auth/google/url", (req, reply) => {
    const { redirect_uri } = (req.query ?? {}) as { redirect_uri?: string };
    if (redirect_uri && !googleRedirectAllowlist().includes(redirect_uri)) {
      return reply.code(400).send({
        error: "Google sign-in is not enabled for this application.",
      });
    }
    const { client, redirectUri } = resolveGoogleClient(redirect_uri);
    if (!client) {
      return reply.code(503).send({
        error:
          "Google sign-in is not configured. Set the Google client id/secret in Admin → Settings → Integrations.",
      });
    }
    // Signed state carries the allowlisted redirect URI and is echoed back by
    // Google; the callback verifies it instead of trusting the client.
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
  //         Body: { code, state } — state is the signed value returned by Step 1.
  app.post("/auth/google/callback", async (req, reply) => {
    const { code, state } = (req.body ?? {}) as { code?: string; state?: string };
    if (!code) return reply.code(400).send({ error: "code is required." });
    if (!state) return reply.code(400).send({ error: "state is required." });
    const verifiedState = verifyOAuthState(state);
    if (!verifiedState) {
      return reply.code(400).send({ error: "Invalid or expired OAuth state." });
    }
    if (!googleRedirectAllowlist().includes(verifiedState.redirectUri)) {
      return reply
        .code(400)
        .send({ error: "Google sign-in is not enabled for this application." });
    }
    const { client } = resolveGoogleClient(verifiedState.redirectUri);
    if (!client) {
      return reply.code(503).send({ error: "Google sign-in is not configured." });
    }
    try {
      const { tokens } = await client.getToken(code);
      const idToken = tokens.id_token;
      if (!idToken) return reply.code(400).send({ error: "Google did not return an id_token." });
      const ticket = await client.verifyIdToken({ idToken, audience: config.google.clientId });
      const payload = ticket.getPayload();
      if (!payload || !payload.email || !payload.sub) {
        return reply.code(400).send({ error: "Google did not return a valid profile." });
      }
      // Never trust an unverified Google email: it is used to link/merge
      // accounts below, so an unverified address could take over a user.
      if (payload.email_verified !== true) {
        return reply.code(403).send({ error: "Google account email is not verified." });
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
      // Set the httpOnly session cookie alongside the (optional) body token.
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
      "SELECT id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active, created_at, last_used_at, credits_expire_at FROM api_keys WHERE user_id = $1 ORDER BY created_at DESC",
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

  app.delete("/me/keys/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    const key = await queryOne<{ id: string; credits: number }>(
      "SELECT id, credits FROM api_keys WHERE id = $1 AND user_id = $2",
      [id, u.id],
    );
    if (!key) return reply.code(404).send({ error: "Key not found." });

    // Credits are stored on keys but behave as an account-level balance (see the
    // pooled-spend fallback in `charge`). A revoked key must therefore not take
    // its balance with it: move it onto the user's oldest remaining key first.
    // With no other key left there is nowhere to move it, so refuse and tell the
    // caller to create a replacement — revocation stays possible and a balance
    // is never silently destroyed. `jobs`, `usage_logs` and `credit_transactions`
    // all reference the key `ON DELETE SET NULL`, so deleting keeps that history.
    if (key.credits > 0) {
      const next = await queryOne<{ id: string }>(
        "SELECT id FROM api_keys WHERE user_id = $1 AND id <> $2 AND is_active = true ORDER BY created_at ASC LIMIT 1",
        [u.id, id],
      );
      if (!next) {
        return reply.code(409).send({
          error: `This key holds ${key.credits} credits. Create another key first — the balance moves to it — then delete this one.`,
        });
      }
      await withTransaction(async (tx) => {
        await tx("UPDATE api_keys SET credits = credits + $1, credits_expire_at = now() + interval '12 months' WHERE id = $2", [key.credits, next.id]);
        await tx("DELETE FROM api_keys WHERE id = $1", [id]);
      });
    } else {
      await query("DELETE FROM api_keys WHERE id = $1", [id]);
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
    if (type === "music" && !body.gpt_description_prompt && !body.prompt && !hasReferenceMedia(body)) {
      return reply.code(400).send({ error: "gpt_description_prompt or prompt is required." });
    }
    if (type === "sounds" && !body.prompt) {
      return reply.code(400).send({ error: "prompt is required." });
    }

    const cost = await costFor(type, (body.model as string) || undefined);
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }

    if (type === "lyrics") {
      const prompt = body.prompt as string;
      const job = newJob("lyrics");
      job.userId = u.id;
      job.apiKeyId = key?.id;
      job.endpoint = "lyrics";
      job.prompt = prompt;
      job.credits = cost;
      void runResultJobWithRetry(job, processLyricsSubmit(prompt));
      return reply.code(202).send({ job_id: job.id, status: job.status });
    }

    if (type === "sounds") {
      const job = newJob("sounds");
      job.userId = u.id;
      job.apiKeyId = key?.id;
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
    job.apiKeyId = key?.id;
    job.endpoint = "music";
    job.model = (body.model as string) || undefined;
    job.prompt = (body.gpt_description_prompt ?? body.prompt) as string;
    job.credits = cost;
    const mpolicy = await routingPolicy((body.model as string) || undefined);
    const imageData = Array.isArray(body.images)
      ? (body.images as unknown[]).filter((d): d is string => typeof d === "string" && d.startsWith("data:image/"))
      : [];
    void runClipJobWithRetry(job, musicSubmitFactory(body, imageData), {
      model: (body.model as string) || undefined,
      policy: mpolicy,
    });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // ---------- /me/upload/reference — session-auth file upload for the panel ----------
  app.post("/me/upload/reference", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    if (!storageConfigured()) return reply.code(503).send({ error: "File storage is not configured." });
    const body = (req.body ?? {}) as { data?: string; kind?: string };
    const data = typeof body.data === "string" ? body.data : "";
    const kind = body.kind === "image" ? "image" : body.kind === "video" ? "video" : "audio";
    const m = data.match(/^data:([a-z0-9.+-]+\/[a-z0-9.+-]+);base64,(.*)$/is);
    if (!m) return reply.code(400).send({ error: "data must be a data: URL." });
    const mime = m[1].toLowerCase();
    const bytes = Buffer.from(m[2], "base64");
    const limitMb = kind === "video" ? 100 : kind === "audio" ? 50 : 10;
    if (bytes.length === 0) return reply.code(400).send({ error: "Empty file." });
    if (bytes.length > limitMb * 1024 * 1024) {
      return reply.code(413).send({ error: `${kind} exceeds ${limitMb}MB.` });
    }
    const ext = (mime.split("/")[1] || "bin").replace(/[^a-z0-9]/g, "").slice(0, 5) || "bin";
    const key = objectKey("uploads", u.id, `${randomUUID()}.${ext}`);
    try {
      await putObject(key, bytes, mime);
      return { url: await getReadUrl(key), key, bytes: bytes.length };
    } catch (e) {
      return reply.code(500).send({ error: e instanceof Error ? e.message : "Upload failed." });
    }
  });

  // ---------- /me/* playground routes (user auth, not API key) ----------

  app.post("/me/recovery", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const sunoTaskId =
      (body.sunoTaskId as string) || (body.task_id as string) || (body.taskId as string) || undefined;
    const clipId = typeof body.clip_id === "string" ? body.clip_id : undefined;
    if (!sunoTaskId && !clipId) {
      return reply.code(400).send({ error: "sunoTaskId or clip_id is required." });
    }
    const cost = await costFor("recovery_audio");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("recovery_audio", (body.callBackUrl || body.callback_url) as string | undefined);
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "recovery_audio";
    job.credits = cost;
    void submitDescribedJob(job, { op: "recovery_audio", args: { sunoTaskId, clipId } });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/stems", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (body.taskId || body.audioId || body.clip_id || body.task_id) as string | undefined;
    if (!clipId) return reply.code(400).send({ error: "taskId is required." });
    const separationType = (body.separationType || "vocal") as "vocal" | "stems" | "advanced" | string;
    const stemsKey = separationType === "advanced" ? "stems_advanced" : separationType === "stems" ? "stems_split" : "stems";
    const cost = await costFor(stemsKey);
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const jobType: Job["type"] =
      separationType === "stems" || separationType === "advanced" ? "stems" : "stems";
    const job = newJob(jobType);
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "stems";
    job.credits = cost;
    job.prompt = separationType === "advanced" ? (body.trackName as string) || "stem" : undefined;
    void submitDescribedJob(job, { op: "stems", args: { id: clipId, mode: separationType } });
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
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("replace_section");
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "replace_section";
    job.credits = cost;
    job.prompt = lyrics;
    const num = (v: unknown): number | undefined => (v != null && v !== "" ? Number(v) : undefined);
    void runClipJobWithRetry(job, (client) =>
      client.replaceSection(clipId, {
        startS,
        endS,
        lyrics,
        model: body.model as string | undefined,
        prompt: body.prompt as string | undefined,
        tags: body.tags as string | undefined,
        title: body.title as string | undefined,
        negativeTags: (body.negativeTags ?? body.negative_tags) as string | undefined,
        vocalGender: (body.vocalGender ?? body.vocal_gender) as string | undefined,
        styleWeight: num(body.styleWeight ?? body.style_weight),
        weirdnessConstraint: num(body.weirdnessConstraint ?? body.weirdness_constraint),
        audioWeight: num(body.audioWeight ?? body.audio_weight),
        personaId: (body.personaId ?? body.persona_id) as string | undefined,
        personaModel: (body.personaModel ?? body.persona_model) as string | undefined,
      }),
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
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("persona");
    job.userId = u.id;
    job.apiKeyId = key?.id;
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
    const description = (body.description as string) || undefined;
    const vocalStartS = body.vocalStartS != null ? Number(body.vocalStartS) : undefined;
    const vocalEndS = body.vocalEndS != null ? Number(body.vocalEndS) : undefined;
    const cost = await costFor("voice_generate");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_generate");
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "voice_generate";
    job.credits = cost;
    job.prompt = name;
    void runResultJobWithRetry(
      job,
      (client) => client.voiceGenerate({ clipId, name, styles, description, vocalStartS, vocalEndS }),
      { policy: "paid_only" },
    );
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/voice-validate", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const uploadId = (body.upload_id || body.uploadId || body.taskId) as string | undefined;
    const audioUrl = (body.audio_url || body.audioUrl || body.validationAudioUrl) as string | undefined;
    const voiceUrl = (body.voiceUrl || body.voice_url) as string | undefined;
    const language = (body.language as string) || undefined;
    const cost = await costFor("voice_validate");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_validate");
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "voice_validate";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceValidate({ uploadId, audioUrl, voiceUrl, language }), {
      needFeature: "studio",
    });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/me/voice-phrase", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const prompt = (body.prompt as string) || "";
    const cost = await costFor("voice_phrase");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_phrase");
    job.userId = u.id;
    job.apiKeyId = key?.id;
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
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("voice_record");
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "voice_record";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceRecord(extension));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // Upload a recorded/selected source sample to Suno and return a clip id usable
  // as the voice/persona root. The bytes never leave this process's trust: the
  // panel posts a data URL, we decode it and run Suno's upload pipeline.
  app.post("/me/voice-source", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as { data?: string; uploadType?: string };
    const data = typeof body.data === "string" ? body.data : "";
    const m = data.match(/^data:([a-z0-9.+-]+\/[a-z0-9.+-]+);base64,(.*)$/is);
    if (!m) return reply.code(400).send({ error: "data must be a data: URL." });
    const mime = m[1].toLowerCase();
    const bytes = Buffer.from(m[2], "base64");
    if (bytes.length === 0) return reply.code(400).send({ error: "Empty audio." });
    if (bytes.length > 25 * 1024 * 1024) return reply.code(413).send({ error: "Audio exceeds 25MB." });
    const ext = (mime.split("/")[1] || "wav").replace(/[^a-z0-9]/g, "").slice(0, 5) || "wav";
    const reqType = body.uploadType;
    const uploadType: "file_upload" | "voice_recording" | "song_demo" =
      reqType === "file_upload" ? "file_upload" : reqType === "song_demo" ? "song_demo" : "voice_recording";
    try {
      const client = await pool.pickExcept([], undefined, "paid_only");
      const clipId = await client.uploadAudio(bytes, ext, uploadType);
      return { clip_id: clipId };
    } catch (e) {
      return reply.code(502).send({ error: e instanceof Error ? e.message : "Upload failed." });
    }
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
    const job = await getJob(id);
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

  // --- user profile + public branding (REQUIREMENTS §3.9) ------------------
  // The user panel's Settings page edits the display name and preferred
  // language; the bottom sidebar needs the operator-managed support link and
  // the list of languages. `/settings` is public — it is non-sensitive branding
  // (also useful to signed-out pages) and mirrors the `brand` group of
  // `/admin/settings`, so the panel and the admin stay in sync.
  const PROFILE_COLUMNS = "id, email, name, language, role, status, email_subscription, credit_alert_thresholds, created_at";

  app.get("/settings", async () => ({ brand: await loadBrandSettings() }));

  // Self-describing docs for drop-in integrators and LLM crawlers.
  app.get("/openapi.json", async () => buildOpenApi(documentedRoutes));
  app.get("/llms.txt", async (_req, reply) => {
    reply.type("text/plain; charset=utf-8");
    return buildLlmsTxt();
  });

  app.get("/me/profile", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    return queryOne(
      `SELECT ${PROFILE_COLUMNS} FROM users WHERE id = $1`,
      [u.id],
    );
  });

  app.put("/me/profile", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as { name?: unknown; language?: unknown; email_subscription?: unknown; credit_alert_thresholds?: unknown };
    if (body.name === undefined && body.language === undefined && body.email_subscription === undefined && body.credit_alert_thresholds === undefined) {
      return reply.code(400).send({ error: "Provide a name, language, email_subscription, and/or credit_alert_thresholds." });
    }
    const sets: string[] = [];
    const params: unknown[] = [];
    if (body.name !== undefined) {
      if (body.name !== null && typeof body.name !== "string") {
        return reply.code(400).send({ error: "name must be a string or null." });
      }
      params.push(typeof body.name === "string" ? body.name.trim() || null : null);
      sets.push(`name = $${params.length}`);
    }
    if (body.email_subscription !== undefined) {
      if (typeof body.email_subscription !== "boolean") {
        return reply.code(400).send({ error: "email_subscription must be a boolean." });
      }
      params.push(body.email_subscription);
      sets.push(`email_subscription = $${params.length}`);
    }
    if (body.credit_alert_thresholds !== undefined) {
      if (!Array.isArray(body.credit_alert_thresholds) || body.credit_alert_thresholds.length > 3) {
        return reply.code(400).send({ error: "credit_alert_thresholds must be an array of at most 3 numbers." });
      }
      const nums = body.credit_alert_thresholds.map((n) => Number(n));
      if (nums.some((n) => !Number.isFinite(n) || n <= 0)) {
        return reply.code(400).send({ error: "Each credit alert threshold must be a positive number." });
      }
      params.push(nums);
      sets.push(`credit_alert_thresholds = $${params.length}`);
    }
    if (body.language !== undefined) {
      // Only languages the operator enabled are accepted, so the selector can
      // never persist a value the panel cannot render.
      const { languages } = await loadBrandSettings();
      if (typeof body.language !== "string" || !languages.includes(body.language)) {
        return reply.code(400).send({ error: `language must be one of: ${languages.join(", ")}.` });
      }
      params.push(body.language);
      sets.push(`language = $${params.length}`);
    }
    params.push(u.id);
    await query(`UPDATE users SET ${sets.join(", ")} WHERE id = $${params.length}`, params);
    return queryOne(
      `SELECT ${PROFILE_COLUMNS} FROM users WHERE id = $1`,
      [u.id],
    );
  });

  // Settings Danger Zone: permanently delete the account. Every dependent row
  // (keys, logs, transactions, jobs) cascades, and the session cookie is cleared.
  app.delete("/me/account", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    await query("DELETE FROM users WHERE id = $1", [u.id]);
    reply.header("set-cookie", [
      serializeClearedSessionCookie(config.sessionCookieSecure),
      serializeClearedSessionCookie(config.sessionCookieSecure, SESSION_COOKIE_ADMIN),
    ]);
    return { ok: true };
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
    // All-time totals (REQUIREMENTS §3.4): the user's lifetime spend in credits
    // and USD, so the figure is a true "total" rather than the reporting window.
    const totalCreditsRow = await queryOne<{ sum: string }>(
      "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE user_id = $1",
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
    const q = req.query as { task_id?: string; endpoint?: string; limit?: string; start?: string; end?: string };
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
    // Inclusive date window used by the usage export (YYYY-MM-DD).
    if (typeof q.start === "string" && /^\d{4}-\d{2}-\d{2}$/.test(q.start)) {
      params.push(q.start);
      clauses.push(`created_at >= $${params.length}::date`);
    }
    if (typeof q.end === "string" && /^\d{4}-\d{2}-\d{2}$/.test(q.end)) {
      params.push(q.end);
      clauses.push(`created_at < ($${params.length}::date + interval '1 day')`);
    }
    const limitRaw = Number(q.limit ?? 0) || 0;
    // A date-filtered query is the usage export, which must return the whole
    // window rather than the logs page's 500-row cap.
    const cap = q.start && q.end ? 5000 : 500;
    const limit = limitRaw > 0 ? Math.min(limitRaw, cap) : 100;
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

  // Paginated logs for the Logs page: date window + optional endpoint-type
  // filter, newest first. Mirrors sunoapi.org's server-side pagination.
  //
  // Records must be visible from submit through completion, the way
  // sunoapi.org's `record-info` is: a task shows `PENDING`/`RUNNING` right after
  // the request is accepted, then flips to `SUCCESS`/`FAILED` when it settles.
  // `usage_logs` is only written at finalize (after Suno and the B2 ingest), so
  // the settled ledger is UNIONed with the in-flight rows still in `jobs`; a job
  // drops out of the `jobs` half the moment it finalizes into `usage_logs`, so
  // there is exactly one row per task at any time.
  app.get("/me/logs/page", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const q = req.query as { task_id?: string; endpoint?: string; endpoints?: string; start?: string; end?: string; page?: string; page_size?: string };
    // Built twice — once per side of the UNION ALL — because the ledger
    // (`usage_logs`) and the job store (`jobs`) name some columns differently.
    // Both sides share the same positional params.
    const logClauses: string[] = ["ul.user_id = $1"];
    const jobClauses: string[] = ["j.user_id = $1"];
    const params: unknown[] = [u.id];
    if (q.task_id && typeof q.task_id === "string" && q.task_id.trim()) {
      params.push(`%${q.task_id.trim()}%`);
      logClauses.push(`(CAST(ul.task_id AS text) ILIKE $${params.length} OR CAST(ul.id AS text) ILIKE $${params.length})`);
      jobClauses.push(`CAST(j.id AS text) ILIKE $${params.length}`);
    }
    if (q.endpoint && typeof q.endpoint === "string" && q.endpoint.trim()) {
      const patterns = q.endpoint.split(",").map((p) => p.trim()).filter(Boolean);
      if (patterns.length > 0) {
        const logOr: string[] = [];
        const jobOr: string[] = [];
        for (const p of patterns) {
          params.push(`%${p}%`);
          logOr.push(`ul.endpoint ILIKE $${params.length}`);
          // A running job may not have stamped `endpoint` yet; fall back to
          // its `type` so it still lands on the right tab.
          jobOr.push(`COALESCE(j.endpoint, j.type) ILIKE $${params.length}`);
        }
        logClauses.push(`(${logOr.join(" OR ")})`);
        jobClauses.push(`(${jobOr.join(" OR ")})`);
      }
    }
    // Exact endpoint names (comma-separated). The Logs tabs send this instead of
    // the substring `endpoint` filter so overlapping names can't bleed across
    // tabs — e.g. `recovery_audio` must not match the `audio` tab, and
    // `mp4_generate`/`midi_generate`/`voice_generate` must not match an
    // `audio` pattern that contains "generate".
    if (q.endpoints && typeof q.endpoints === "string" && q.endpoints.trim()) {
      const names = q.endpoints.split(",").map((p) => p.trim()).filter(Boolean);
      if (names.length > 0) {
        params.push(names);
        const idx = params.length;
        logClauses.push(`ul.endpoint = ANY($${idx}::text[])`);
        jobClauses.push(`COALESCE(j.endpoint, j.type) = ANY($${idx}::text[])`);
      }
    }
    if (typeof q.start === "string" && /^\d{4}-\d{2}-\d{2}$/.test(q.start)) {
      params.push(q.start);
      logClauses.push(`ul.created_at >= $${params.length}::date`);
      jobClauses.push(`j.created_at >= $${params.length}::date`);
    }
    if (typeof q.end === "string" && /^\d{4}-\d{2}-\d{2}$/.test(q.end)) {
      params.push(q.end);
      logClauses.push(`ul.created_at < ($${params.length}::date + interval '1 day')`);
      jobClauses.push(`j.created_at < ($${params.length}::date + interval '1 day')`);
    }
    const pageSize = Math.min(100, Math.max(1, Number(q.page_size ?? 20) || 20));
    const requestedPage = Math.max(1, Number(q.page ?? 1) || 1);
    const combined = `
      SELECT ul.id::text AS id, ul.endpoint AS endpoint, ul.model AS model,
             ul.prompt AS prompt, ul.status AS status,
             ul.credits_consumed AS credits_consumed, ul.task_id AS task_id,
             ul.result_json AS result_json, ul.created_at AS created_at
      FROM usage_logs ul
      WHERE ${logClauses.join(" AND ")}
      UNION ALL
      SELECT j.id::text AS id, COALESCE(j.endpoint, j.type) AS endpoint, j.model AS model,
             j.prompt AS prompt, j.status AS status,
             COALESCE(j.credits, 0) AS credits_consumed, j.id::text AS task_id,
             j.result_json AS result_json, j.created_at AS created_at
      FROM jobs j
      WHERE ${jobClauses.join(" AND ")}
        AND j.status IN ('pending','running','streaming')
    `;
    const totalRow = await queryOne<{ count: string }>(`SELECT count(*)::text AS count FROM (${combined}) combined`, params);
    const total = Number(totalRow?.count ?? 0);
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const page = Math.min(requestedPage, pages);
    const offset = (page - 1) * pageSize;
    const rows = await query<Record<string, unknown>>(
      `SELECT * FROM (${combined}) combined ORDER BY created_at DESC LIMIT ${pageSize} OFFSET ${offset}`,
      params,
    );
    const hydrate = (rs: Record<string, unknown>[]) => rs.map((r) => ({ ...r, clips: normalizeClips(r.result_json) }));
    return { rows: hydrate(rows), total, page, page_size: pageSize, pages };
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

  // Sunoapi.org-shaped usage report for /dashboard/usage: one call returns the
  // overview daily series plus a per-model breakdown for a bounded date window.
  // Ranges are inclusive and capped at 31 days to match the panel's picker.
  app.get("/me/usage/page", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const q = req.query as { start?: string; end?: string };
    const iso = /^\d{4}-\d{2}-\d{2}$/;
    let end = typeof q.end === "string" && iso.test(q.end)
      ? q.end
      : new Date().toISOString().slice(0, 10);
    let start: string;
    if (typeof q.start === "string" && iso.test(q.start)) {
      start = q.start;
    } else {
      const d = new Date(`${end}T00:00:00Z`);
      d.setUTCDate(d.getUTCDate() - 13);
      start = d.toISOString().slice(0, 10);
    }
    if (start > end) [start, end] = [end, start];
    // Clamp to the 31-day maximum the UI enforces, anchoring on the end date.
    const span = Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000) + 1;
    if (!Number.isFinite(span) || span < 1) {
      return reply.code(400).send({ error: "Invalid date range." });
    }
    if (span > 31) {
      const d = new Date(`${end}T00:00:00Z`);
      d.setUTCDate(d.getUTCDate() - 30);
      start = d.toISOString().slice(0, 10);
    }
    const creditsPerUsd = await creditsPerUsdRate();
    const args = [u.id, start, end];
    const window = "created_at >= $2::date AND created_at < ($3::date + interval '1 day')";
    const nameExpr = "COALESCE(NULLIF(model, ''), endpoint)";

    const dayRows = await query<{ day: string; count: string; credits: string }>(
      `SELECT to_char(created_at, 'YYYY-MM-DD') AS day, count(*)::text AS count, COALESCE(sum(credits_consumed),0)::text AS credits
       FROM usage_logs WHERE user_id = $1 AND ${window} GROUP BY day ORDER BY day`,
      args,
    );
    const daily = (rows: Array<{ day: string; count: string; credits: string }>) =>
      rows.map((r) => ({
        day: r.day,
        count: Number(r.count),
        credits: Number(r.credits),
        spend: Number(r.credits) / creditsPerUsd,
      }));
    const overviewDaily = daily(dayRows);

    const modelRows = await query<{ name: string; count: string; credits: string }>(
      `SELECT ${nameExpr} AS name, count(*)::text AS count, COALESCE(sum(credits_consumed),0)::text AS credits
       FROM usage_logs WHERE user_id = $1 AND ${window} GROUP BY name ORDER BY sum(credits_consumed) DESC NULLS LAST, count(*) DESC`,
      args,
    );
    const names = modelRows.map((r) => r.name);
    const seriesRows = names.length
      ? await query<{ name: string; day: string; count: string; credits: string }>(
          `SELECT ${nameExpr} AS name, to_char(created_at, 'YYYY-MM-DD') AS day, count(*)::text AS count, COALESCE(sum(credits_consumed),0)::text AS credits
           FROM usage_logs WHERE user_id = $1 AND ${window} AND ${nameExpr} = ANY($4::text[]) GROUP BY name, day ORDER BY day`,
          [...args, names],
        )
      : [];
    const seriesByName = new Map<string, ReturnType<typeof daily>>();
    for (const r of seriesRows) {
      const bucket = seriesByName.get(r.name) ?? [];
      bucket.push({ day: r.day, count: Number(r.count), credits: Number(r.credits), spend: Number(r.credits) / creditsPerUsd });
      seriesByName.set(r.name, bucket);
    }
    return {
      start,
      end,
      credits_per_usd: creditsPerUsd,
      overview: {
        total_credits: overviewDaily.reduce((s, d) => s + d.credits, 0),
        total_spend: overviewDaily.reduce((s, d) => s + d.spend, 0),
        daily: overviewDaily,
      },
      models: modelRows.map((r) => ({
        name: r.name,
        count: Number(r.count),
        credits: Number(r.credits),
        spend: Number(r.credits) / creditsPerUsd,
        daily: seriesByName.get(r.name) ?? [],
      })),
    };
  });

  // Per-day success/failure/other counts for the dashboard's stacked bar chart.
  // Matches sunoapi.org: a trailing window of whole days ending yesterday.
  app.get("/me/dashboard/timeline", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const daysParam = Number((req.query as { days?: string })?.days ?? 14);
    const days = Math.min(30, Math.max(7, daysParam || 14));
    const rows = await query<{ day: string; success: string; failure: string; other: string }>(
      `SELECT to_char(created_at, 'YYYY-MM-DD') AS day,
              count(*) FILTER (WHERE status = 'complete')::text AS success,
              count(*) FILTER (WHERE status = 'error')::text AS failure,
              count(*) FILTER (WHERE status NOT IN ('complete','error'))::text AS other
       FROM usage_logs
       WHERE user_id = $1 AND created_at >= CURRENT_DATE - ($2::int) AND created_at < CURRENT_DATE
       GROUP BY day ORDER BY day`,
      [u.id, days],
    );
    const byDay = new Map(rows.map((r) => [r.day, r]));
    const pad = (n: number) => String(n).padStart(2, "0");
    const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - days);
    const end = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
    const daily: Array<{ date: string; success: number; failure: number; other: number }> = [];
    for (let i = 0; i < days; i++) {
      const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      const key = iso(d);
      const r = byDay.get(key);
      daily.push({
        date: key,
        success: Number(r?.success ?? 0),
        failure: Number(r?.failure ?? 0),
        other: Number(r?.other ?? 0),
      });
    }
    const total = daily.reduce((s, d) => s + d.success + d.failure + d.other, 0);
    return { start: iso(start), end: iso(end), total, daily };
  });

  // Per-minute success rate over the last 15 minutes for the dashboard's
  // real-time line chart. Timestamps are epoch milliseconds.
  app.get("/me/dashboard/success-rate", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const rows = await query<{ ts: string; total: string; success: string }>(
      `SELECT (extract(epoch from date_trunc('minute', created_at)) * 1000)::bigint::text AS ts,
              count(*)::text AS total,
              count(*) FILTER (WHERE status = 'complete')::text AS success
       FROM usage_logs
       WHERE user_id = $1 AND created_at > now() - interval '15 minutes'
       GROUP BY ts ORDER BY ts`,
      [u.id],
    );
    return rows.map((r) => {
      const total = Number(r.total);
      const success = Number(r.success);
      return {
        timestamp: Number(r.ts),
        total,
        success,
        success_rate: total > 0 ? Math.round((success / total) * 1000) / 10 : 100,
      };
    });
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

  // Progressive, decrypt-on-the-fly playback for a clip. Serves the durable B2
  // object when present, otherwise decrypts Suno's encrypted m4a in memory and
  // streams it, so playback starts while a clip is still generating. No VPS
  // buffering or scratch files.
  app.get("/me/stream", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const q = (req.query ?? {}) as { clip_id?: string; format?: string };
    const clipId = q.clip_id;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    if (await clipOwnedByOtherUser(u.id, clipId)) return denyForeignClip(reply);
    const format = q.format === "wav" ? "wav" : q.format === "m4a" ? "m4a" : "mp3";

    if (storageConfigured()) {
      try {
        const key = objectKey(format === "wav" ? "wav" : "clips", `${clipId}.${format}`);
        if (await objectExists(key)) {
          const url = await getReadUrl(key);
          if (url) return reply.redirect(url, 302);
        }
      } catch {
        /* fall through to the live decrypt stream */
      }
    }

    // Only the raw m4a streams directly (a browser plays AAC/Opus-in-MP4); mp3
    // and wav need a transcode and are served by the download route.
    if (format !== "m4a") {
      return reply.redirect(`/me/download?clip_id=${encodeURIComponent(clipId)}&format=${format}`, 302);
    }

    try {
      const client = await pool.pick();
      const range = typeof req.headers.range === "string" ? req.headers.range : undefined;
      const out = await openDecryptedM4aStream(client, clipId, range);
      reply.header("Content-Type", out.contentType);
      reply.header("Accept-Ranges", "bytes");
      reply.header("Cache-Control", "no-store");
      if (out.totalBytes != null) {
        reply.header("Content-Range", `bytes ${out.rangeStart}-${out.totalBytes - 1}/${out.totalBytes}`);
        reply.header("Content-Length", String(out.totalBytes - out.rangeStart));
        reply.code(206);
      }
      return reply.send(out.stream);
    } catch (e) {
      req.log.warn({ err: e, clipId }, "me/stream failed");
      return reply.code(502).send({ error: "Audio stream unavailable." });
    }
  });

  // T4: GET /me/download — calls Suno 3-step (authorize → poll /download/clip → ready) → stream real MP3/WAV bytes from S3
  app.get("/me/download", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const q = (req.query ?? {}) as { clip_id?: string; format?: string; force_download?: string };
    const clipId = q.clip_id;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    if (await clipOwnedByOtherUser(u.id, clipId)) return denyForeignClip(reply);
    const formatRaw = (q.format as string) || "mp3";

    // Music-video download. `runMusicVideoJob` stores the rendered render at
    // `videos/<clipId>.mp4`; the MP4 generation job already charged for it, so
    // re-fetching is free and bypasses the audio download-purchase ledger.
    if (formatRaw === "mp4") {
      if (!storageConfigured()) {
        return reply.code(404).send({ error: "Media storage is not configured." });
      }
      try {
        const videoKey = objectKey("videos", `${clipId}.mp4`);
        if (!(await objectExists(videoKey))) {
          return reply.code(404).send({ error: "No video found for this clip." });
        }
        const videoBytes = await getObjectBytes(videoKey);
        const videoName = `${slug(clipId).replace(/^-+|-+$/g, "") || "video"}.mp4`;
        const encoded = encodeURIComponent(videoName);
        reply.header("Content-Type", "video/mp4");
        reply.header("Content-Length", String(videoBytes.length));
        reply.header("Accept-Ranges", "bytes");
        reply.header(
          "Content-Disposition",
          `attachment; filename="${videoName}"; filename*=UTF-8''${encoded}`,
        );
        return reply.send(videoBytes);
      } catch (e) {
        return reply.code(500).send({ error: e instanceof Error ? e.message : "Video download failed" });
      }
    }

    const format = formatRaw === "wav" ? "wav" : "mp3";

    // A clip is bought once per format: the first download charges the pricing
    // row, later downloads of the same clip are free. The claim is written
    // before the charge so two concurrent first-downloads cannot both pay.
    // `refund` is declared out here so every failure path below can release the
    // claim and hand the credits back.
    let cost = 0;
    let purchaseId: string | null = null;
    let chargedKey: DbApiKey | null = null;
    const refund = async (): Promise<void> => {
      if (!purchaseId || !chargedKey) return;
      await query("DELETE FROM download_purchases WHERE id = $1", [purchaseId]).catch(() => {});
      await query("UPDATE api_keys SET credits = credits + $1, credits_expire_at = now() + interval '12 months' WHERE id = $2", [cost, chargedKey.id]).catch(() => {});
    };
    try {
      // Audio delivery is priced per format from the `pricing` table, like every
      // other endpoint, so both rows are editable at /admin/pricing.
      cost = await costFor(format === "wav" ? "wav_download" : "mp3_download").catch(() => 0);
      if (cost > 0) {
        const claim = await query<{ id: string }>(
          `INSERT INTO download_purchases (user_id, clip_id, format, credits)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (user_id, clip_id, format) DO NOTHING
           RETURNING id`,
          [u.id, clipId, format, cost],
        );
        if (claim.length > 0) {
          purchaseId = claim[0].id;
          chargedKey = await chargeUserKey(u.id, cost);
          if (!chargedKey) {
            await query("DELETE FROM download_purchases WHERE id = $1", [purchaseId]);
            purchaseId = null;
            return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
          }
        }
      }
      // Prefer our durable B2 copy when one exists. For inline playback we 302 to
      // the presigned object so the browser streams it directly (Range seeks)
      // instead of buffering the whole file through this process.
      if (storageConfigured()) {
        try {
          // Ensure a durable copy exists (decrypting + transcoding on demand for
          // clips that were never ingested); returns the object key or null.
          const key = await ensureAudio(clipId, format);
          if (key) {
            if (q.force_download === "1") {
              const stored = await getObjectBytes(key);
              if (stored && stored.length > 400) {
                reply.header("Content-Type", format === "wav" ? "audio/wav" : "audio/mpeg");
                reply.header("Content-Length", String(stored.length));
                reply.header("Accept-Ranges", "bytes");
                const filename = `${slug(clipId).replace(/^-+|-+$/g, "") || "download"}.${format}`;
                const encoded = encodeURIComponent(filename);
                reply.header(
                  "Content-Disposition",
                  `attachment; filename="${filename}"; filename*=UTF-8''${encoded}`,
                );
                return reply.send(stored);
              }
            } else {
              const url = await getReadUrl(key);
              if (url) return reply.redirect(url, 302);
            }
          }
        } catch {
          /* miss — fall through to the live Suno download */
        }
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
        fallbackCandidates.push(`https://cdn1.suno.ai/${clipId}.mp3`);
        fallbackCandidates.push(`https://cdn1.suno.ai/${clipId}.wav`);
      }
      const correctCt = format === "wav" ? "audio/wav" : "audio/mpeg";
      if (primaryBuffer) {
        // Cache the freshly-fetched bytes so the next play is instant (B2 redirect).
        if (storageConfigured() && q.force_download !== "1") {
          try {
            const key = objectKey(format === "wav" ? "wav" : "clips", `${clipId}.${format}`);
            await putObject(key, primaryBuffer, format === "wav" ? "audio/wav" : "audio/mpeg");
            const url = await getReadUrl(key);
            if (url) return reply.redirect(url, 302);
          } catch {
            /* fall through to sending the buffer */
          }
        }
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
          const resp = await fetch(cand, { ...fetchOpts, signal: AbortSignal.timeout(120_000) });
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
      await refund();
      return reply.code(502).send({ error: "Audio not available. The clip may have expired or the media server is unreachable." });
    } catch (e: any) {
      await refund();
      return reply.code(500).send({ error: e?.message ?? "Download failed" });
    }
  });

  // T5: GET /me/jobs/running
  app.get("/me/jobs/running", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const rows = await query<JobRow>(
      `SELECT ${JOB_COLUMNS} FROM jobs
       WHERE user_id = $1 AND status IN ('pending','running','streaming')
       ORDER BY created_at DESC`,
      [u.id],
    );
    return rows.map((row) => {
      const j = rowToJob(row);
      return {
        job_id: j.id,
        type: j.type,
        status: j.status,
        endpoint: j.endpoint,
        prompt: j.prompt,
        model: j.model,
        credits: j.credits,
        created_at: j.createdAt,
      };
    });
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
      const model = modelField ? (body[modelField] as string) || undefined : undefined;
      const cost = await costFor(type, model);
      // `chargeUserKey` returns null for a 0-credit request, so a free endpoint
      // must not be rejected just because no key could be charged.
      const key = await chargeUserKey(u.id, cost);
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      const job = newJob(type, (body.callback_url as string) || undefined);
      job.userId = u.id;
      job.apiKeyId = key?.id;
      job.endpoint = type;
      job.credits = cost;
      if (body.prompt) job.prompt = body.prompt as string;
      if (model) job.model = model;
      const policy = await routingPolicy(model);
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
      // See meClipRoute: a 0-credit request legitimately has no charged key.
      const key = await chargeUserKey(u.id, cost);
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      const job = newJob(type, (body.callback_url as string) || undefined);
      job.userId = u.id;
      job.apiKeyId = key?.id;
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

  // POST /me/music/wav — served from our own B2/decrypt pipeline
  // (runAudioDeliveryJob), not Suno's quota-gated download endpoint.
  app.post("/me/music/wav", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const format = (body.format as string) || "wav";
    const cost = await costFor("wav");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("wav", (body.callback_url as string) || undefined);
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "wav";
    job.credits = cost;
    const musicIndex = await clipIndexInTask((body.taskId as string) || (body.task_id as string) || undefined, clipId);
    void trackJob(runAudioDeliveryJob(job, clipId, format === "mp3" ? "mp3" : "wav", musicIndex));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // POST /me/music/midi — Basic Pitch transcription of a clip (or a separation task).
  app.post("/me/music/midi", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const sourceTaskId = (body.task_id as string) || (body.taskId as string) || undefined;
    const audioId = (body.audio_id as string) || (body.audioId as string) || undefined;
    const clipId = (body.clip_id as string) || (sourceTaskId ? undefined : audioId);
    if (!sourceTaskId && !clipId) {
      return reply.code(400).send({ error: "clip_id or task_id is required." });
    }
    const cost = await costFor("midi_generate");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("midi_generate", (body.callback_url as string) || undefined);
    job.userId = u.id;
    if (key) job.apiKeyId = key.id;
    job.endpoint = "midi_generate";
    job.credits = cost;
    void trackJob(runMidiJob(job, { sourceTaskId, audioId, clipId }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

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
      const data = await client.fetchAudioUploadStatus(id);
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
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("replace_section", (body.callback_url as string) || undefined);
    job.userId = u.id;
    job.apiKeyId = key?.id;
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
    const sunoTaskId =
      (body.sunoTaskId as string) || (body.task_id as string) || (body.taskId as string) || undefined;
    const clipId = body.clip_id as string | undefined;
    if (!sunoTaskId && !clipId) {
      return reply.code(400).send({ error: "clip_id or sunoTaskId is required." });
    }
    const cost = await costFor("recovery_audio");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("recovery_audio", (body.callback_url as string) || undefined);
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "recovery_audio";
    job.credits = cost;
    void submitDescribedJob(job, { op: "recovery_audio", args: { sunoTaskId, clipId } });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // GET /me/lyrics/:id
  app.get("/me/lyrics/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    if (await clipOwnedByOtherUser(u.id, id)) return denyForeignClip(reply);
    let job = await reusableLyricsJob(id, u.id);
    if (!job) {
      const cost = await costFor("timestamped_lyrics_detail");
      const key = await chargeUserKey(u.id, cost);
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
      }
      job = newJob("timestamped_lyrics_detail");
      job.userId = u.id;
      job.apiKeyId = key?.id;
      job.endpoint = "timestamped_lyrics_detail";
      job.credits = cost;
      void submitDescribedJob(job, { op: "timestamped_lyrics_detail", args: { id } });
    }
    await awaitJobTerminal(job, LYRICS_SYNC_WAIT_MS);
    return reply.send(timestampedLyricsBody(job));
  });

  // Detail GET routes (T3 - meDetailRoute)
  meDetailRoute("/me/music/stems/:id", "stems_detail");
  meDetailRoute("/me/music/video/:id", "video_detail");
  meDetailRoute("/me/music/cover/:id", "cover_detail");
  meDetailRoute("/me/music/subtitle/:id", "subtitle_detail");
  meDetailRoute("/me/music/recovery/:id", "recovery_detail");
  meDetailRoute("/me/mp4/:id", "mp4_detail");
  meDetailRoute("/me/music/midi/:id", "midi_detail");
  meDetailRoute("/me/clip/:id", "lyrics_detail");

  // GET /me/music/wav/:id — our own media pipeline (runAudioDeliveryJob),
  // independent of Suno's quota-gated download endpoint.
  app.get("/me/music/wav/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });
    if (await clipOwnedByOtherUser(u.id, id)) return denyForeignClip(reply);
    let cost = 0;
    try {
      cost = await costFor("wav_detail");
    } catch {
      cost = 0;
    }
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("wav_detail");
    job.userId = u.id;
    if (key) job.apiKeyId = key.id;
    job.endpoint = "wav_detail";
    job.credits = cost;
    void trackJob(runAudioDeliveryJob(job, id, "wav"));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // POST /me/mp4/generate — self-hosted renderer (cover art + waveform).
  app.post("/me/mp4/generate", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const clipId = body.clip_id as string;
    if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
    const cost = await costFor("mp4_generate");
    const key = await chargeUserKey(u.id, cost);
    if (cost > 0 && !key) {
      return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
    }
    const job = newJob("mp4_generate", (body.callback_url as string) || undefined);
    job.userId = u.id;
    job.apiKeyId = key?.id;
    job.endpoint = "mp4_generate";
    job.credits = cost;
    job.prompt = (body.prompt as string) || undefined;
    void trackJob(runMusicVideoJob(job, clipId, (body.aspect_ratio as string) || "16:9"));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

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

  app.get("/updates", async (req) => {
    const q = (req.query ?? {}) as { q?: string; page?: string; page_size?: string };
    const pageSize = Math.min(50, Math.max(1, Number(q.page_size ?? 20) || 20));
    const requestedPage = Math.max(1, Number(q.page ?? 1) || 1);
    const clauses = ["published = true"];
    const params: unknown[] = [];
    if (q.q && typeof q.q === "string" && q.q.trim()) {
      params.push(`%${q.q.trim()}%`);
      clauses.push(`(title ILIKE $${params.length} OR content ILIKE $${params.length})`);
    }
    const where = `WHERE ${clauses.join(" AND ")}`;
    const totalRow = await queryOne<{ count: string }>(`SELECT count(*)::text AS count FROM blog_posts ${where}`, params);
    const total = Number(totalRow?.count ?? 0);
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const page = Math.min(requestedPage, pages);
    const offset = (page - 1) * pageSize;
    const posts = await query<{ id: string; title: string; slug: string; content: string; created_at: string }>(
      `SELECT id, title, slug, content, created_at FROM blog_posts ${where} ORDER BY created_at DESC LIMIT ${pageSize} OFFSET ${offset}`,
      params,
    );
    return { posts, total, page, pages, page_size: pageSize };
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

  /**
   * The model versions this deployment can actually generate with. Read from
   * the live Suno catalog of every funded account, so a Suno-side model rollout
   * (or retirement) reaches the clients without a code change.
   */
  app.get("/models", async () => ({ models: await pool.listModels().catch(() => []) }));

  // --- settings + alerts (task 5.5, REQUIREMENTS §4.10) --------------------
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

  type AlertType =
    | "low_credits"
    | "captcha_no_solver"
    | "captcha_balance"
    | "failure_rate"
    | "queue_backlog";

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
      captcha_required: number;
      captcha_balance: number | null;
      failure_rate: number | null;
      requests: number;
      failures: number;
      queue_backlog: number;
    };
  }

  /**
   * Best-effort 2Captcha balance in USD, or null when the key is unset, the
   * request fails, or the response is unparseable. Never throws: a failed probe
   * must not produce a captcha alert.
   */
  async function fetchTwoCaptchaBalance(): Promise<number | null> {
    if (!config.twoCaptchaKey) return null;
    try {
      const res = await fetch(
        `https://2captcha.com/res.php?key=${encodeURIComponent(config.twoCaptchaKey)}&action=getbalance&json=1`,
        { signal: AbortSignal.timeout(8_000) },
      );
      if (!res.ok) return null;
      const data = (await res.json()) as { status?: number; request?: string };
      if (data.status !== 1) return null;
      const balance = Number(data.request);
      return Number.isFinite(balance) ? balance : null;
    } catch {
      return null;
    }
  }

  /**
   * Evaluate the §4.10 alert conditions against live state. Pure read — it
   * never delivers anything — so both the admin endpoint and the background loop
   * can call it freely; `syncAlertState` is what decides whether to notify.
   */
  async function evaluateAlerts(): Promise<AlertReport> {
    const thresholds = await loadAlertSettings();
    const checkedAt = new Date().toISOString();
    const summary: AlertReport["summary"] = {
      low_credits: 0,
      captcha_required: 0,
      captcha_balance: null,
      failure_rate: null,
      requests: 0,
      failures: 0,
      queue_backlog: 0,
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

    // 2. Captcha: only alert when it actually blocks generation. A funded
    //    solver makes a captcha challenge a no-op, so the actionable cases are
    //    "accounts need a captcha but no solver is configured" and "the solver
    //    is drained/broken".
    const captchaAccounts = health.filter((h) => h.captchaRequired);
    summary.captcha_required = captchaAccounts.length;
    if (captchaAccounts.length > 0 && !config.twoCaptchaKey) {
      alerts.push({
        id: "captcha_no_solver",
        type: "captcha_no_solver",
        severity: "warning",
        message: `${captchaAccounts.length} Suno account(s) require a captcha but no 2Captcha key is configured; generation on them will fail until a key is added.`,
        details: { accounts: captchaAccounts.map((h) => h.id) },
      });
    }
    if (config.twoCaptchaKey && thresholds.captcha_balance_threshold > 0) {
      const balance = await fetchTwoCaptchaBalance();
      summary.captcha_balance = balance;
      if (balance !== null && balance <= thresholds.captcha_balance_threshold) {
        alerts.push({
          id: "captcha_balance",
          type: "captcha_balance",
          severity: balance <= 0 ? "critical" : "warning",
          message: `2Captcha balance is $${balance.toFixed(2)}, at or below the $${thresholds.captcha_balance_threshold.toFixed(2)} threshold — top up so captcha-solved generations keep working.`,
          details: { balance, threshold: thresholds.captcha_balance_threshold },
        });
      }
    }

    // 3. Failure-rate spike over the configured sliding window. Jobs failed out
    //    by a deploy/restart (`recoverJobs` -> "Interrupted by server restart.")
    //    are excluded: they are operator-caused, not generation failures, and
    //    would otherwise page ops after every deploy as they sit in the window.
    //    The raw rows still land in `usage_logs` and the user/admin dashboards.
    const row = await queryOne<{ total: string; failed: string }>(
      `SELECT count(*)::text AS total,
              count(*) FILTER (
                WHERE ul.status <> 'complete'
                  AND NOT EXISTS (
                    SELECT 1 FROM jobs j
                    WHERE j.id::text = ul.task_id
                      AND j.status = 'error'
                      AND j.error = $2
                  )
              )::text AS failed
       FROM usage_logs ul
       WHERE ul.created_at > now() - ($1 || ' minutes')::interval`,
      [String(thresholds.window_minutes), RESTART_INTERRUPT_ERROR],
    );
    const total = Number(row?.total ?? 0);
    const failed = Number(row?.failed ?? 0);
    summary.requests = total;
    summary.failures = failed;
    if (total >= thresholds.failure_rate_min_requests) {
      const rate = total > 0 ? failed / total : 0;
      summary.failure_rate = rate;
      if (rate >= thresholds.failure_rate_threshold) {
        // Surface the dominant error text so an operator can act on the page
        // without digging through the DB. Terminal errors live on the `jobs`
        // row; queried only when this alert actually fires.
        let topReasons: Array<{ reason: string; count: number }> = [];
        try {
          const reasonRows = await query<{ reason: string; count: string }>(
            `SELECT COALESCE(NULLIF(left(error, 160), ''), 'unknown') AS reason,
                    count(*)::text AS count
             FROM jobs
             WHERE status = 'error'
               AND error <> $2
               AND updated_at > now() - ($1 || ' minutes')::interval
             GROUP BY 1 ORDER BY count(*) DESC LIMIT 3`,
            [String(thresholds.window_minutes), RESTART_INTERRUPT_ERROR],
          );
          topReasons = reasonRows.map((r) => ({
            reason: r.reason.replace(/\s+/g, " ").trim(),
            count: Number(r.count),
          }));
        } catch (err) {
          app.log.warn({ err }, "failure-rate reason lookup failed");
        }
        const reasonSuffix = topReasons.length
          ? ` Top causes: ${topReasons.map((r) => `${r.reason} (${r.count})`).join("; ")}.`
          : "";
        alerts.push({
          id: "failure_rate",
          type: "failure_rate",
          severity: rate >= 0.5 ? "critical" : "warning",
          message:
            `Job failure rate ${(rate * 100).toFixed(1)}% over the last ${
              thresholds.window_minutes
            } min (${failed}/${total}), above the ${(thresholds.failure_rate_threshold * 100).toFixed(1)}% threshold.` +
            reasonSuffix,
          details: {
            rate,
            failed,
            total,
            window_minutes: thresholds.window_minutes,
            top_reasons: topReasons,
          },
        });
      }
    }

    // 4. Suno concurrency gate backlog: jobs waiting for a slot to free up.
    const gate = sunoSlots.stats();
    summary.queue_backlog = gate.waiting;
    if (thresholds.queue_backlog_depth > 0 && gate.waiting >= thresholds.queue_backlog_depth) {
      alerts.push({
        id: "queue_backlog",
        type: "queue_backlog",
        severity: gate.waiting >= thresholds.queue_backlog_depth * 2 ? "critical" : "warning",
        message: `${gate.waiting} job(s) waiting for a Suno slot with ${gate.active} running (above the ${thresholds.queue_backlog_depth} threshold). The account pool can't keep up with demand.`,
        details: { waiting: gate.waiting, active: gate.active, threshold: thresholds.queue_backlog_depth },
      });
    }

    return { enabled: true, checked_at: checkedAt, thresholds, alerts, summary };
  }

  /** Deliver one Telegram message; false when creds are unset or delivery fails. */
  async function sendTelegram(text: string): Promise<boolean> {
    // Production-only. Sandbox and production share the same alert bot/chat, so
    // delivering from a non-production process would spam the live ops channel.
    if (!isProduction()) {
      app.log.debug(
        { environment: config.environment },
        "telegram alert delivery skipped (non-production)",
      );
      return false;
    }
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
   * differences: one message per newly-raised alert, one per alert whose
   * severity changed, and one per alert that has since cleared. Dedupe on
   * `type|severity` — not the message body, whose live numbers (`304/403`, a
   * dropping rate, account balances) change every evaluation. Keying on the body
   * re-paged an ongoing incident every check interval.
   */
  async function syncAlertState(report: AlertReport): Promise<void> {
    const current = new Map<string, string>();
    for (const a of report.alerts) current.set(a.id, a.severity);
    const scope = `Camxora Music API (${config.environment})`;
    for (const alert of report.alerts) {
      if (alertState.get(alert.id) !== current.get(alert.id)) {
        if (await sendTelegram(`[ALERT] ${scope} — ${alert.type}\n${alert.message}`)) {
          app.log.warn({ alert: alert.id }, "alert notification sent");
        }
      }
    }
    for (const id of [...alertState.keys()]) {
      if (!current.has(id)) {
        if (await sendTelegram(`[RESOLVED] ${scope} — ${id} cleared.`)) {
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

  // Suno session keep-alive: proactively refresh each account's JWT (and persist
  // any rotated `__client` cookie) so idle periods never lapse the session.
  // Set SUNO_KEEPALIVE_MS=0 to disable.
  function startSessionKeepAlive(): void {
    const intervalMs = Number(process.env.SUNO_KEEPALIVE_MS ?? 30 * 60_000);
    if (!(intervalMs > 0) || sessionTimer) return;
    sessionTimer = setInterval(() => {
      void pool
        .refreshSessions()
        .catch((err) => app.log.warn({ err }, "suno session keep-alive failed"));
    }, intervalMs);
    sessionTimer.unref?.();
    app.log.info({ intervalMs }, "suno session keep-alive started");
  }

  function stopSessionKeepAlive(): void {
    if (!sessionTimer) return;
    clearInterval(sessionTimer);
    sessionTimer = null;
  }

  // --- admin routes --------------------------------------------------------
  app.get("/admin/keys", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    // `credits` is the balance parked on this individual key, but spending is
    // pooled across every active key a user owns (see `charge`/`chargeUserKey`).
    // Return both so the admin console can group by owner and show the true
    // account-level balance instead of reading 0-balance keys as empty wallets.
    return query<Record<string, unknown>>(
      `SELECT k.id, k.name, k.key_prefix, k.credits, k.is_active, u.id AS user_id, u.email,
              (SELECT COALESCE(sum(k2.credits), 0) FROM api_keys k2 WHERE k2.user_id = k.user_id) AS account_credits,
              (SELECT count(*) FROM api_keys k2 WHERE k2.user_id = k.user_id) AS key_count
       FROM api_keys k JOIN users u ON u.id = k.user_id
       ORDER BY u.email, k.created_at DESC`,
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
    const [live, thresholds] = await Promise.all([
      pool.listHealth().catch(() => [] as Awaited<ReturnType<AccountPool["listHealth"]>>),
      loadAlertSettings(),
    ]);
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
          low_credits: liveCredits <= thresholds.low_credits_threshold,
          captcha_required: l?.captchaRequired ?? false,
          // When a solver key is configured, a captcha-required account is still
          // fully usable — the Turnstile is solved automatically at generation
          // time, so the UI should not flag it as broken.
          captcha_solver: Boolean(config.twoCaptchaKey),
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
    if (!label || !client_cookie) {
      return reply.code(400).send({ error: "label and client_cookie are required." });
    }
    // Each account needs its own device id; generate one when omitted so the
    // operator only has to paste the cookie.
    const deviceId = (device_id ?? "").trim() || randomUUID();
    // The label is the pool's account identity (src/pool.ts keys clients by it),
    // so a duplicate silently merges two accounts in routing and health views.
    const clash = await queryOne<{ id: string }>("SELECT id FROM suno_accounts WHERE label = $1", [label]);
    if (clash) return reply.code(409).send({ error: "An account with that label already exists." });
    const t = type === "paid" ? "paid" : "free";
    const rows = await query<{ id: string }>(
      "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, $2, $3, $4) RETURNING id",
      [label, t, encryptCookie(client_cookie), deviceId],
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
      params.push(encryptCookie(body.client_cookie));
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
    // Suno account health summary (REQUIREMENTS §4.1). Uses the same flags and
    // low-credits threshold as the Accounts page so the overview and the
    // per-account badges never disagree. `healthy` = no flag at all.
    const [accountRows, live, thresholds, creditsPerUsd] = await Promise.all([
      query<{ label: string; is_active: boolean; credits_left: number | null }>(
        "SELECT label, is_active, credits_left FROM suno_accounts",
      ),
      pool.listHealth().catch(() => [] as Awaited<ReturnType<AccountPool["listHealth"]>>),
      loadAlertSettings(),
      creditsPerUsdRate(),
    ]);
    const liveByLabel = new Map(live.map((l) => [l.id, l]));
    const captchaSolver = Boolean(config.twoCaptchaKey);
    const accountHealth = { total: accountRows.length, healthy: 0, disabled: 0, low_credits: 0, captcha_required: 0, captcha_solver: captchaSolver };
    // Aggregate Suno credit monitor (REQUIREMENTS §4.6): the size of the live
    // credit pool across the configured accounts. `active` sums only enabled
    // accounts — the credits actually available to serve requests right now —
    // while `total` includes disabled accounts for reference.
    const sunoCredits = { total: 0, active: 0 };
    for (const row of accountRows) {
      const l = liveByLabel.get(row.label);
      const liveCredits = l?.credits ?? row.credits_left ?? 0;
      const disabled = !row.is_active;
      const lowCredits = liveCredits <= thresholds.low_credits_threshold;
      const captcha = l?.captchaRequired ?? false;
      sunoCredits.total += liveCredits;
      if (!disabled) sunoCredits.active += liveCredits;
      if (disabled) accountHealth.disabled += 1;
      if (lowCredits) accountHealth.low_credits += 1;
      if (captcha) accountHealth.captcha_required += 1;
      // A captcha-required account stays healthy when a solver key is configured
      // (solved automatically at generation time). It only counts against health
      // when there is no solver — i.e. when generation would actually fail.
      if (!disabled && !lowCredits && (!captcha || captchaSolver)) accountHealth.healthy += 1;
    }
    const spentCredits = Number(spent?.sum ?? 0);
    return {
      users: Number(users?.count ?? 0),
      keys: Number(keys?.count ?? 0),
      requests: Number(logs?.count ?? 0),
      credits: Number(credits?.sum ?? 0),
      spent: spentCredits,
      revenue: spentCredits / creditsPerUsd,
      credits_per_usd: creditsPerUsd,
      accounts: pool.size,
      account_health: accountHealth,
      suno_credits: sunoCredits,
      series: series.map((s) => ({ day: s.day, count: Number(s.count) })),
    };
  });

  // Usage analytics (task 5.4, REQUIREMENTS §4.7): per-endpoint, per-model and
  // per-user breakdowns plus success/failure counts and revenue trends, all
  // derived from usage_logs. Revenue is credits_consumed converted to USD using
  // the same cheapest-active-pack rate the user-facing /me/usage reports use, so
  // the two views never disagree. `previous_totals` covers the equally long
  // window immediately before the requested range, powering period-over-period
  // deltas in the admin UI.
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
    // Same-length window immediately before the requested range, for deltas.
    const previous = await queryOne<AggRow>(
      `SELECT ${AGG} FROM usage_logs
       WHERE created_at > now() - interval '${days * 2} days'
         AND created_at <= now() - interval '${days} days'`,
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
      previous_totals: previous ? shape(previous) : { count: 0, success: 0, failed: 0, credits: 0, revenue: 0 },
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
    let key = await queryOne<DbApiKey>(
      "SELECT id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active FROM api_keys WHERE user_id = $1 ORDER BY created_at ASC LIMIT 1",
      [id],
    );
    if (!key) {
      const raw = `sk_${randomUUID().replace(/-/g, "")}`;
      await query(
        "INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits) VALUES ($1, 'default', $2, $3, 0)",
        [id, hashKey(raw), raw.slice(0, 8)],
      );
      key = await queryOne<DbApiKey>(
        "SELECT id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active FROM api_keys WHERE user_id = $1 ORDER BY created_at ASC LIMIT 1",
        [id],
      );
    }
    // Single-statement, atomic adjust so concurrent charges/adjustments can't
    // lose an update (the previous read-modify-write did). The CTE also returns
    // the pre-update balance so the ledger records the delta actually applied:
    // GREATEST(0, …) clamps the balance, so a debit larger than the balance is
    // only applied in part and the ledger must not overstate it.
    const updated = await queryOne<{ credits: number; prev_credits: number }>(
      `WITH target AS (
         SELECT id, credits FROM api_keys WHERE id = $2 FOR UPDATE
       ), applied AS (
         UPDATE api_keys SET credits = GREATEST(0, target.credits + $1), credits_expire_at = CASE WHEN $1 > 0 THEN now() + interval '12 months' ELSE credits_expire_at END
         FROM target WHERE api_keys.id = target.id
         RETURNING api_keys.credits AS credits, target.credits AS prev_credits
       )
       SELECT credits, prev_credits FROM applied`,
      [amount, key!.id],
    );
    const resulting = updated?.credits ?? key!.credits;
    const appliedAmount = updated ? updated.credits - updated.prev_credits : amount;
    await query(
      "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'adjust', $3)",
      [id, appliedAmount, "Admin credit adjustment"],
    );
    await recordAudit({
      actor: admin,
      action: "user.credits",
      targetType: "user",
      targetId: id,
      details: { amount, applied: appliedAmount, resulting_credits: resulting },
      req,
    });
    return { ok: true, credits: resulting };
  });

  app.get("/admin/users/:id/rate-limits", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { id } = req.params as { id: string };
    const row = await queryOne<{
      requests_per_window: number | null;
      requests_per_minute: number | null;
      requests_per_day: number | null;
      max_concurrent_jobs: number | null;
    }>(
      "SELECT requests_per_window, requests_per_minute, requests_per_day, max_concurrent_jobs FROM rate_limits WHERE user_id = $1 LIMIT 1",
      [id],
    );
    return {
      user_id: id,
      requests_per_window: row?.requests_per_window ?? null,
      requests_per_minute: row?.requests_per_minute ?? null,
      requests_per_day: row?.requests_per_day ?? null,
      max_concurrent_jobs: row?.max_concurrent_jobs ?? null,
      // Context so the admin UI can render the window/limit units.
      window_ms: config.rateLimit.userWindowMs,
      default_max_concurrent_jobs: config.suno.maxConcurrentPerUser,
    };
  });

  app.put("/admin/users/:id/rate-limits", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const body = (req.body ?? {}) as {
      requests_per_window?: number | null;
      requests_per_minute?: number | null;
      requests_per_day?: number | null;
      max_concurrent_jobs?: number | null;
    };
    // A limit is a positive integer, or null to clear it.
    const parseLimit = (value: unknown): { ok: true; value: number | null } | { ok: false } => {
      if (value === null || value === undefined) return { ok: true, value: null };
      if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) return { ok: false };
      return { ok: true, value };
    };
    const perWindow = parseLimit(body.requests_per_window);
    const perMinute = parseLimit(body.requests_per_minute);
    const perDay = parseLimit(body.requests_per_day);
    const maxConcurrent = parseLimit(body.max_concurrent_jobs);
    if (!perWindow.ok || !perMinute.ok || !perDay.ok || !maxConcurrent.ok) {
      return reply.code(400).send({
        error:
          "requests_per_window/requests_per_minute/requests_per_day/max_concurrent_jobs " +
          "must be positive integers or null.",
      });
    }
    const user = await queryOne<{ id: string }>("SELECT id FROM users WHERE id = $1", [id]);
    if (!user) return reply.code(404).send({ error: "User not found." });
    if (
      perWindow.value === null &&
      perMinute.value === null &&
      perDay.value === null &&
      maxConcurrent.value === null
    ) {
      await query("DELETE FROM rate_limits WHERE user_id = $1", [id]);
    } else {
      await query(
        `INSERT INTO rate_limits
           (user_id, requests_per_window, requests_per_minute, requests_per_day, max_concurrent_jobs)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (user_id) DO UPDATE SET
           requests_per_window = EXCLUDED.requests_per_window,
           requests_per_minute = EXCLUDED.requests_per_minute,
           requests_per_day = EXCLUDED.requests_per_day,
           max_concurrent_jobs = EXCLUDED.max_concurrent_jobs`,
        [id, perWindow.value, perMinute.value, perDay.value, maxConcurrent.value],
      );
    }
    // Drop the cached row so the new limits apply on the next request.
    rateLimitCache.delete(id);
    await recordAudit({
      actor: admin,
      action: "user.rate_limits",
      targetType: "user",
      targetId: id,
      details: {
        requests_per_window: perWindow.value,
        requests_per_minute: perMinute.value,
        requests_per_day: perDay.value,
        max_concurrent_jobs: maxConcurrent.value,
      },
      req,
    });
    return {
      ok: true,
      user_id: id,
      requests_per_window: perWindow.value,
      requests_per_minute: perMinute.value,
      requests_per_day: perDay.value,
      max_concurrent_jobs: maxConcurrent.value,
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
    if (
      !endpoint ||
      typeof credit_cost !== "number" ||
      !Number.isInteger(credit_cost) ||
      credit_cost < 0
    ) {
      return reply
        .code(400)
        .send({ error: "endpoint is required and credit_cost must be a non-negative integer." });
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
    if (
      !endpoint ||
      typeof credit_cost !== "number" ||
      !Number.isInteger(credit_cost) ||
      credit_cost < 0
    ) {
      return reply
        .code(400)
        .send({ error: "endpoint is required and credit_cost must be a non-negative integer." });
    }
    const updated = await query<{ id: string }>(
      "UPDATE pricing SET endpoint = $1, model = $2, credit_cost = $3 WHERE id = $4 RETURNING id",
      [endpoint, model ?? null, credit_cost, id],
    );
    if (!updated.length) return reply.code(404).send({ error: "Pricing row not found." });
    // Two rows with the same (endpoint, model) make `costFor` pick an arbitrary or
    // stale one; after this update, drop any other row that now collides so this
    // row is the single source of truth.
    const removed = await query<{ id: string }>(
      "DELETE FROM pricing WHERE endpoint = $1 AND model IS NOT DISTINCT FROM $2 AND id <> $3 RETURNING id",
      [endpoint, model ?? null, id],
    );
    await recordAudit({
      actor: admin,
      action: "pricing.update",
      targetType: "pricing",
      targetId: id,
      details: {
        endpoint,
        model: model ?? null,
        credit_cost,
        removed_duplicates: removed.map((r) => r.id),
      },
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

  // Operator-managed branding + alert thresholds (task 5.5, REQUIREMENTS §4.10).
  // Both groups are returned as-is with defaults filled in, so the panel never
  // has to special-case an empty store.
  app.get("/admin/settings", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const [brand, alerts] = await Promise.all([loadBrandSettings(), loadAlertSettings()]);
    return { brand, alerts, integrations: maskedIntegrations() };
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

  // Admin-managed integration keys (Suno, 2Captcha, Google, ChmabaPay,
  // B2, alerts). Secret fields are encrypted at rest and never returned; the
  // merged result is applied to `config` immediately (no restart).
  app.put("/admin/settings/integrations", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const body = (req.body ?? {}) as { values?: unknown };
    if (!body.values || typeof body.values !== "object") {
      return reply.code(400).send({ error: "Provide an integrations values patch." });
    }
    const values = body.values as Record<string, Record<string, unknown>>;
    await updateIntegrations(values, admin.id);
    await recordAudit({
      actor: admin,
      action: "settings.update",
      targetType: "settings",
      targetId: "integrations",
      details: { groups: Object.keys(values) },
      req,
    });
    return { integrations: maskedIntegrations() };
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

  // --- admin: payments + credit ledger (Phase 4) --------------------------
  // Read-only operator views over the money/ledger tables. Both paginate and
  // filter server-side so the console never fetches the whole table.

  /** Shared pagination parser: page >= 1, pageSize 1..100, default 25. */
  function parsePage(q: { page?: string; pageSize?: string }): {
    page: number;
    pageSize: number;
    offset: number;
  } {
    const page = Math.max(1, Math.floor(Number(q.page) || 1));
    const pageSize = Math.min(100, Math.max(1, Math.floor(Number(q.pageSize) || 25)));
    return { page, pageSize, offset: (page - 1) * pageSize };
  }

  /** CSV cell: quote when needed and neutralize spreadsheet formula injection. */
  function csvCell(value: unknown): string {
    let s = value === null || value === undefined ? "" : String(value);
    if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  app.get("/admin/payments", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const q = (req.query ?? {}) as {
      page?: string;
      pageSize?: string;
      status?: string;
      provider?: string;
      email?: string;
      format?: string;
    };
    const { page, pageSize, offset } = parsePage(q);
    const filters: string[] = [];
    const params: unknown[] = [];
    if (q.status) {
      params.push(q.status);
      filters.push(`pt.status = $${params.length}`);
    }
    if (q.provider) {
      params.push(q.provider);
      filters.push(`pt.provider = $${params.length}`);
    }
    if (q.email) {
      params.push(`%${q.email.toLowerCase()}%`);
      filters.push(`lower(u.email) LIKE $${params.length}`);
    }
    const where = filters.length ? `WHERE ${filters.join(" AND ")}` : "";
    if (q.format === "csv") {
      const all = await query<Record<string, unknown>>(
        `SELECT pt.created_at, u.email, pt.provider, pt.credit_amount, pt.currency, pt.amount,
                pt.status, pt.provider_payment_id, pt.gateway_payment_id, pt.paid_at
         FROM payment_transactions pt JOIN users u ON u.id = pt.user_id
         ${where} ORDER BY pt.created_at DESC LIMIT 10000`,
        params,
      );
      const lines = [
        "created_at,email,provider,credits,currency,amount,status,provider_payment_id,gateway_payment_id,paid_at",
        ...all.map((r) =>
          [
            r.created_at,
            r.email,
            r.provider,
            r.credit_amount,
            r.currency,
            r.amount,
            r.status,
            r.provider_payment_id,
            r.gateway_payment_id,
            r.paid_at,
          ]
            .map(csvCell)
            .join(","),
        ),
      ];
      reply.header("content-type", "text/csv; charset=utf-8");
      reply.header("content-disposition", 'attachment; filename="payments.csv"');
      return reply.send(lines.join("\n"));
    }
    const total = await queryOne<{ n: string }>(
      `SELECT count(*)::text AS n FROM payment_transactions pt
       JOIN users u ON u.id = pt.user_id ${where}`,
      params,
    );
    const rows = await query<Record<string, unknown>>(
      `SELECT pt.id, u.email, pt.provider, pt.credit_amount, pt.currency, pt.amount,
              pt.payment_method, pt.status, pt.provider_payment_id, pt.gateway_payment_id,
              pt.bill_number, pt.error_message, pt.paid_at, pt.expires_at, pt.created_at
       FROM payment_transactions pt
       JOIN users u ON u.id = pt.user_id
       ${where}
       ORDER BY pt.created_at DESC
       LIMIT $${params.length + 1} OFFSET $${params.length + 2}`,
      [...params, pageSize, offset],
    );
    return { rows, total: Number(total?.n ?? 0), page, page_size: pageSize };
  });

  // Manual refund of a settled ChmabaPay payment. Reuses `reverseChmabaPayment`,
  // which is idempotent and guards provider='chmaba' AND status='paid' and
  // clamps the clawback at zero; the pre-check only returns a clearer error.
  app.post("/admin/payments/:id/refund", async (req, reply) => {
    const admin = await requireAdmin(req, reply);
    if (!admin) return;
    const { id } = req.params as { id: string };
    const payment = await queryOne<{ status: string; provider: string }>(
      "SELECT status, provider FROM payment_transactions WHERE id = $1",
      [id],
    );
    if (!payment) return reply.code(404).send({ error: "Payment not found." });
    if (payment.provider !== "chmaba") {
      return reply.code(400).send({ error: "Only ChmabaPay payments can be refunded here." });
    }
    if (payment.status !== "paid") {
      return reply.code(409).send({ error: "Only a paid payment can be refunded." });
    }
    const refunded = await reverseChmabaPayment(id);
    if (!refunded) {
      return reply
        .code(409)
        .send({ error: "The payment could not be refunded (it may already be reversed)." });
    }
    await recordAudit({
      actor: admin,
      action: "payment.refund",
      targetType: "payment_transaction",
      targetId: id,
      details: { provider: payment.provider },
      req,
    });
    return { ok: true };
  });

  app.get("/admin/transactions", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const q = (req.query ?? {}) as {
      page?: string;
      pageSize?: string;
      type?: string;
      email?: string;
      format?: string;
    };
    const { page, pageSize, offset } = parsePage(q);
    const filters: string[] = [];
    const params: unknown[] = [];
    if (q.type) {
      params.push(q.type);
      filters.push(`ct.type = $${params.length}`);
    }
    if (q.email) {
      params.push(`%${q.email.toLowerCase()}%`);
      filters.push(`lower(u.email) LIKE $${params.length}`);
    }
    const where = filters.length ? `WHERE ${filters.join(" AND ")}` : "";
    if (q.format === "csv") {
      const all = await query<Record<string, unknown>>(
        `SELECT ct.created_at, u.email, ct.amount, ct.type, ct.description, ct.job_id
         FROM credit_transactions ct JOIN users u ON u.id = ct.user_id
         ${where} ORDER BY ct.created_at DESC LIMIT 10000`,
        params,
      );
      const lines = [
        "created_at,email,amount,type,description,job_id",
        ...all.map((r) =>
          [r.created_at, r.email, r.amount, r.type, r.description, r.job_id]
            .map(csvCell)
            .join(","),
        ),
      ];
      reply.header("content-type", "text/csv; charset=utf-8");
      reply.header("content-disposition", 'attachment; filename="credit-ledger.csv"');
      return reply.send(lines.join("\n"));
    }
    const total = await queryOne<{ n: string }>(
      `SELECT count(*)::text AS n FROM credit_transactions ct
       JOIN users u ON u.id = ct.user_id ${where}`,
      params,
    );
    const rows = await query<Record<string, unknown>>(
      `SELECT ct.id, u.email, ct.amount, ct.type, ct.description, ct.job_id, ct.created_at
       FROM credit_transactions ct
       JOIN users u ON u.id = ct.user_id
       ${where}
       ORDER BY ct.created_at DESC
       LIMIT $${params.length + 1} OFFSET $${params.length + 2}`,
      [...params, pageSize, offset],
    );
    return { rows, total: Number(total?.n ?? 0), page, page_size: pageSize };
  });

  // --- v1 API (DB-backed keys) --------------------------------------------
  app.get("/v1/credits", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const bal = await accountCredits(key.user_id);
    return { name: key.name, credits: bal.credits, credits_expire_at: bal.credits_expire_at };
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
    if (!body.gpt_description_prompt && !body.prompt && !hasReferenceMedia(body)) {
      return reply.code(400).send({ error: "gpt_description_prompt or prompt is required." });
    }
    const model = (body.model as string) || undefined;
    const cost = await costFor("music", model);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const callbackUrl = (body.callback_url as string) || undefined;
    const job = newJob("music", callbackUrl);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "music";
    job.model = model;
    job.prompt = (body.gpt_description_prompt ?? body.prompt) as string;
    job.credits = cost;
    const policy = await routingPolicy(model);
    void runClipJobWithRetry(job, musicSubmitFactory(body), { model, policy });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  app.post("/v1/sounds", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const prompt = body.prompt as string;
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const model = (body.model as string) || undefined;
    const cost = await costFor("sounds", model);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("sounds", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "sounds";
    job.model = model;
    job.prompt = prompt;
    job.credits = cost;
    const spolicy = await routingPolicy(model);
    void runClipJobWithRetry(job, processSoundsSubmit(body), { model, policy: spolicy });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  function clipRoute(path: string, type: Job["type"], pricingKey: string = type) {
    app.post(path, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const body = (req.body ?? {}) as Record<string, unknown>;
      const clipId = body.clip_id as string;
      if (!clipId) return reply.code(400).send({ error: "clip_id is required." });
      // Only remaster takes a model; the other clip operations use the
      // account's default, so they stay on the endpoint-wide price.
      const model = type === "remaster" ? (body.model as string) || undefined : undefined;
      const cost = await costFor(pricingKey, model);
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
  clipRoute("/v1/music/stems", "stems", "stems_split");
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
    const musicIndex = await clipIndexInTask((body.taskId as string) || (body.task_id as string) || undefined, clipId);
    void trackJob(runAudioDeliveryJob(job, clipId, format === "mp3" ? "mp3" : "wav", musicIndex));
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
    const job = await getJob(id);
    if (!job) return reply.code(404).send({ error: "Task not found." });
    // A job created through a user session/API key belongs to that user; other
    // keys (including other tenants) must not be able to read its result.
    if (job.userId && job.userId !== key.user_id) return reply.code(403).send({ error: "forbidden." });
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
      const data = await client.fetchAudioUploadStatus(id);
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
    const sunoTaskId =
      (body.sunoTaskId as string) || (body.task_id as string) || (body.taskId as string) || undefined;
    const clipId = body.clip_id as string | undefined;
    if (!sunoTaskId && !clipId) {
      return reply.code(400).send({ error: "clip_id or sunoTaskId is required." });
    }
    const cost = await costFor("recovery_audio");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("recovery_audio", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "recovery_audio";
    job.credits = cost;
    void submitDescribedJob(job, { op: "recovery_audio", args: { sunoTaskId, clipId } });
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- Timestamped lyrics + Lyrics detail --------
  app.get("/v1/lyrics/:id", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });
    if (await clipOwnedByOtherUser(key.user_id, id)) return denyForeignClip(reply);
    let job = await reusableLyricsJob(id, key.user_id);
    if (!job) {
      const cost = await costFor("timestamped_lyrics_detail");
      if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
      job = newJob("timestamped_lyrics_detail");
      job.userId = key.user_id;
      job.apiKeyId = key.id;
      job.endpoint = "timestamped_lyrics_detail";
      job.credits = cost;
      void submitDescribedJob(job, { op: "timestamped_lyrics_detail", args: { id } });
    }
    await awaitJobTerminal(job, LYRICS_SYNC_WAIT_MS);
    return reply.send(timestampedLyricsBody(job));
  });

  // -------- Detail GET routes for clip assets (all 1-credit details) --------
  function detailRoute(path: string, type: Job["type"]) {
    app.get(path, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const { id } = req.params as { id: string };
      if (!id) return reply.code(400).send({ error: "id is required." });
      if (await clipOwnedByOtherUser(key.user_id, id)) return denyForeignClip(reply);
      const cost = await costFor(type);
      if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

      const job = newJob(type);
      job.userId = key.user_id;
      job.apiKeyId = key.id;
      job.endpoint = type;
      job.credits = cost;
      void submitDescribedJob(job, { op: type, args: { id } });
      return reply.code(202).send({ job_id: job.id, status: job.status });
    });
  }

  detailRoute("/v1/music/stems/:id", "stems_detail");
  detailRoute("/v1/music/video/:id", "video_detail");
  detailRoute("/v1/music/cover/:id", "cover_detail");
  detailRoute("/v1/music/subtitle/:id", "subtitle_detail");
  detailRoute("/v1/music/recovery/:id", "recovery_detail");
  detailRoute("/v1/mp4/:id", "mp4_detail");
  detailRoute("/v1/music/midi/:id", "midi_detail");
  detailRoute("/v1/clip/:id", "lyrics_detail");

  // WAV detail is served from our own media pipeline (runAudioDeliveryJob),
  // because Suno's /api/download/* is gated by a per-account monthly quota.
  app.get("/v1/music/wav/:id", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const { id } = req.params as { id: string };
    if (!id) return reply.code(400).send({ error: "id is required." });
    if (await clipOwnedByOtherUser(key.user_id, id)) return denyForeignClip(reply);
    const cost = await costFor("wav_detail");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const job = newJob("wav_detail");
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "wav_detail";
    job.credits = cost;
    void trackJob(runAudioDeliveryJob(job, id, "wav"));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

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
    void trackJob(runMusicVideoJob(job, clipId, aspectRatio));
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
    const sourceTaskId = (body.task_id as string) || (body.taskId as string) || undefined;
    const audioId = (body.audio_id as string) || (body.audioId as string) || undefined;
    const clipId = (body.clip_id as string) || (sourceTaskId ? undefined : audioId);
    if (!sourceTaskId && !clipId) {
      return reply.code(400).send({ error: "task_id or clip_id is required." });
    }
    const cost = await costFor("midi_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("midi_generate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "midi_generate";
    job.credits = cost;
    void trackJob(runMidiJob(job, { sourceTaskId, audioId, clipId }));
    return reply.code(202).send({ job_id: job.id, status: job.status });
  });

  // -------- Suno Voice 6 operations --------
  app.post("/v1/voice/phrase", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const body = (req.body ?? {}) as Record<string, unknown>;
    const prompt = body.prompt as string | undefined;
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
    const uploadId = (body.upload_id as string) || (body.uploadId as string) || undefined;
    const audioUrl = (body.audio_url as string) || (body.audioUrl as string) || undefined;
    const voiceUrl = (body.voiceUrl as string) || (body.voice_url as string) || undefined;
    const language = (body.language as string) || undefined;
    const cost = await costFor("voice_validate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_validate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_validate";
    job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceValidate({ uploadId, audioUrl, voiceUrl, language }), {
      needFeature: "studio",
    });
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
    const validationTaskId = (body.taskId as string) || (body.task_id as string) || undefined;
    const verifyUrl = (body.verifyUrl as string) || (body.verify_url as string) || undefined;
    const clipId = body.clip_id as string | undefined;
    const name = (body.name as string) || (body.voiceName as string) || undefined;
    const custom = Boolean(validationTaskId && verifyUrl);
    if (!custom && (!clipId || !name)) {
      return reply
        .code(400)
        .send({ error: "clip_id and name are required (or taskId + verifyUrl for a custom voice)." });
    }
    const cost = await costFor("voice_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_generate", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_generate";
    job.credits = cost;
    job.prompt = name;
    if (custom) {
      void trackJob(runCustomVoiceJob(job, { validationTaskId: validationTaskId!, verifyUrl: verifyUrl!, voiceName: name }));
    } else {
      const styles = body.styles as string | undefined;
      void runResultJobWithRetry(
        job,
        (client) => client.voiceGenerate({ clipId: clipId!, name: name!, styles }),
        { policy: "paid_only" },
      );
    }
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
    const model = body.model as string | undefined;
    const cost = await costFor("voice_apply", model);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const job = newJob("voice_apply", body.callback_url as string | undefined);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "voice_apply";
    job.credits = cost;
    job.prompt = (body.prompt as string) || undefined;
    const vpolicy = await routingPolicy(model);
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
      image_urls: Array.isArray(in_.imageUrls)
        ? in_.imageUrls
        : Array.isArray(in_.image_urls)
          ? in_.image_urls
          : undefined,
      audio_urls: Array.isArray(in_.audioUrls)
        ? in_.audioUrls
        : Array.isArray(in_.audio_urls)
          ? in_.audio_urls
          : undefined,
      video_urls: Array.isArray(in_.videoUrls)
        ? in_.videoUrls
        : Array.isArray(in_.video_urls)
          ? in_.video_urls
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
    const bal = await accountCredits(key.user_id);
    return { code: 200, msg: "success", data: { credits: bal.credits, name: key.name, credits_expire_at: bal.credits_expire_at } };
  });
  // Alias: /v1/get-credits so both work
  app.get(`/v1/get-credits`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const bal = await accountCredits(key.user_id);
    return { code: 200, msg: "success", data: { credits: bal.credits, name: key.name, credits_expire_at: bal.credits_expire_at } };
  });

  // POST /api/v1/generate -> /v1/music (with payload translation)
  app.post(`${PREFIX}/generate`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const inBody = (req.body ?? {}) as Record<string, unknown>;
    const body = translateBodyToMusic(inBody);
    if (!body.gpt_description_prompt && !body.prompt && !hasReferenceMedia(body)) {
      return reply.code(400).send({ error: "prompt is required." });
    }
    const model = (body.model as string) || undefined;
    const cost = await costFor("music", model);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });

    const callbackUrl = body.callback_url as string | undefined;
    const job = newJob("music", callbackUrl);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "music";
    job.model = model;
    job.prompt = (body.gpt_description_prompt ?? body.prompt) as string;
    job.credits = cost;
    const policy = await routingPolicy(model);
    void runClipJobWithRetry(job, musicSubmitFactory(body), { model, policy });
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
    // sunoapi.org `type`: separate_vocal → 2-track, split_stem → multi, split_stem_advanced → single stem.
    const rawType = (in_.type as string) || "";
    const mode = rawType === "separate_vocal" ? "vocal" : rawType === "split_stem_advanced" ? "advanced" : "stems";
    const stemsKey = mode === "advanced" ? "stems_advanced" : mode === "stems" ? "stems_split" : "stems";
    const cost = await costFor(stemsKey);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const job = newJob("stems", (in_.callBackUrl as string) || (in_.callback_url as string) || undefined);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "stems"; job.credits = cost;
    void submitDescribedJob(job, { op: "stems", args: { id: clip_id, mode } });
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // GET /api/v1/generate/record-info?taskId= -> /v1/task/:id
  // Rendered in sunoapi.org's response shape: status vocabulary, `type`, `param`,
  // `errorCode`/`errorMessage`, and a `response.sunoData[]` array whose tracks
  // carry BOTH snake_case and camelCase field names. `response.data[]` is kept
  // for back-compat with our own callers.
  // Flatten a job result into individual clip-like objects. Our music/sounds
  // jobs store `[{ clips: [...] }]`, stems store `{...}`, etc.; sunoapi.org's
  // `sunoData[]` is a flat track list, so both ingest and record-info use this.
  function collectClipObjects(value: unknown, out: Array<Record<string, unknown>>): void {
    if (Array.isArray(value)) {
      for (const v of value) collectClipObjects(v, out);
      return;
    }
    if (!value || typeof value !== "object") return;
    const o = value as Record<string, unknown>;
    const id = typeof o.id === "string" ? o.id : undefined;
    const clipLike = Boolean(
      id && (o.media_urls || o.audio_url || o.audioUrl || o.image_url || o.imageUrl || o.video_url),
    );
    if (clipLike) out.push(o);
    if (Array.isArray(o.clips)) collectClipObjects(o.clips, out);
    if (Array.isArray(o.data)) collectClipObjects(o.data, out);
    if (Array.isArray(o.sunoData)) collectClipObjects(o.sunoData, out);
  }

  async function sunoRecordInfo(job: Job) {
    let status: string;
    if (job.status === "complete") status = "SUCCESS";
    else if (job.status === "error") status = "GENERATE_AUDIO_FAILED";
    else if (job.status === "running" || job.status === "streaming") status = "FIRST_SUCCESS";
    else status = "PENDING";

    const flat: Array<Record<string, unknown>> = [];
    collectClipObjects(job.result, flat);
    const tracks: unknown[] = flat.length > 0 ? flat : job.result != null ? [job.result] : [];
    // Re-sign storage URLs at read time so a long-lived job never hands back an
    // expired presigned link (the object key is what we persist).
    const sunoData = await Promise.all(
      tracks.map(async (t) => {
        const track = sunoTrack(t) as Record<string, unknown>;
        const audioKey = track.audio_storage_key;
        if (typeof audioKey === "string") {
          const url = await getReadUrl(audioKey);
          if (url) {
            track.audio_url = url;
            track.audioUrl = url;
            track.stream_audio_url = url;
            track.streamAudioUrl = url;
          }
        }
        const imageKey = track.image_storage_key;
        if (typeof imageKey === "string") {
          const url = await getReadUrl(imageKey);
          if (url) {
            track.image_url = url;
            track.imageUrl = url;
          }
        }
        // Never hand back Suno's progressive CDN URL as `audio_url`: it is
        // DRM-encrypted (unplayable). A completed clip already has a durable B2
        // copy from ingest above; if it somehow doesn't, expose an empty field so
        // clients know it isn't ready instead of a 200 that won't play.
        const bad = (v: unknown) => !v || /forbidden|undefined|null/i.test(String(v));
        if (bad(track.audio_url)) { track.audio_url = ""; track.audioUrl = ""; }
        if (bad(track.stream_audio_url)) { track.stream_audio_url = ""; track.streamAudioUrl = ""; }
        if (bad(track.source_audio_url)) { track.source_audio_url = ""; track.sourceAudioUrl = ""; }
        return track;
      }),
    );

    return {
      code: 200,
      msg: "success",
      data: {
        taskId: job.id,
        parentMusicId: "",
        param: JSON.stringify({
          model: job.model,
          prompt: job.prompt,
          callBackUrl: job.callbackUrl,
        }),
        status,
        type: job.model ? normalizeModel(job.model) : undefined,
        operationType: job.endpoint,
        errorCode: job.error ? "GENERATE_AUDIO_FAILED" : null,
        errorMessage: job.error ?? null,
        createTime: job.createdAt,
        response: job.result
          ? {
              taskId: job.id,
              sunoData,
              data: Array.isArray(job.result) ? job.result : [job.result],
            }
          : undefined,
      },
    };
  }

  /** `YYYY-MM-DD HH:MM:SS` timestamp, matching sunoapi.org's record-info. */
  function sunoTime(ms: number): string {
    const d = new Date(ms);
    const p = (n: number) => String(n).padStart(2, "0");
    return (
      `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
      `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
    );
  }

  /**
   * WAV-conversion record-info in sunoapi.org's exact shape: `data.response.audioWavUrl`
   * plus a `successFlag` (PENDING | SUCCESS | GENERATE_WAV_FAILED), instead of the
   * generic track list. Only `/convert-to-wav/record-info` (+ its `/wav/record-info`
   * alias) uses this.
   */
  function wavRecordInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const successFlag =
      job.status === "complete"
        ? "SUCCESS"
        : job.status === "error"
          ? "GENERATE_WAV_FAILED"
          : "PENDING";
    const wavUrl =
      job.status === "complete"
        ? ((res.download_url as string) ?? (res.wav_url as string) ?? null)
        : null;
    const terminal = job.status === "complete" || job.status === "error";
    return {
      code: 200,
      msg: job.status === "error" ? job.error || "WAV format conversion failed" : "success",
      data: {
        taskId: job.id,
        musicId: (res.clip_id as string) ?? null,
        musicIndex: typeof res.music_index === "number" ? res.music_index : 0,
        callbackUrl: job.callbackUrl ?? "",
        completeTime: terminal ? sunoTime(job.completedAt ?? job.createdAt) : null,
        response: { audioWavUrl: wavUrl },
        successFlag,
        createTime: sunoTime(job.createdAt),
        errorCode: job.status === "error" ? 500 : null,
        errorMessage: job.status === "error" ? job.error ?? null : null,
      },
    };
  }

  /**
   * Lyrics-generation record-info in sunoapi.org's shape:
   * `data.response.data[]` of `{text,title,status,errorMessage}`, plus `type: "LYRICS"`.
   */
  function lyricsRecordInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const status =
      job.status === "complete"
        ? "SUCCESS"
        : job.status === "error"
          ? "GENERATE_LYRICS_FAILED"
          : "PENDING";
    const hasLyrics = job.status === "complete" && typeof res.text === "string";
    return {
      code: 200,
      msg: job.status === "error" ? job.error || "Lyrics generation failed" : "success",
      data: {
        taskId: job.id,
        param: JSON.stringify({ prompt: job.prompt ?? "" }),
        response: hasLyrics
          ? {
              taskId: job.id,
              data: [
                {
                  text: res.text,
                  title: (res.title as string) ?? "",
                  status: "complete",
                  errorMessage: "",
                },
              ],
            }
          : null,
        status,
        type: "LYRICS",
        errorCode: job.status === "error" ? 500 : null,
        errorMessage: job.status === "error" ? job.error ?? null : null,
      },
    };
  }

  /** Normalised stem name → sunoapi.org vocal-removal response field. */
  const STEM_URL_FIELD: Record<string, string> = {
    vocals: "vocalUrl",
    vocal: "vocalUrl",
    instrumental: "instrumentalUrl",
    "backing vocals": "backingVocalsUrl",
    drums: "drumsUrl",
    bass: "bassUrl",
    guitar: "guitarUrl",
    keyboard: "keyboardUrl",
    piano: "keyboardUrl",
    percussion: "percussionUrl",
    strings: "stringsUrl",
    synth: "synthUrl",
    synthesizer: "synthUrl",
    fx: "fxUrl",
    effects: "fxUrl",
    brass: "brassUrl",
    woodwinds: "woodwindsUrl",
    woodwind: "woodwindsUrl",
  };

  /**
   * Vocal-separation record-info in sunoapi.org's shape: a `response` object with
   * per-stem URLs (`vocalUrl`, `instrumentalUrl`, `drumsUrl`, …) plus `originData`.
   * Derived from our stem clips' `metadata.stem_type_group_name` / `stem_from_id`.
   */
  async function vocalRemovalRecordInfo(job: Job) {
    const clips: Array<Record<string, unknown>> = [];
    collectClipObjects(job.result, clips);
    const successFlag =
      job.status === "complete"
        ? "SUCCESS"
        : job.status === "error"
          ? "GENERATE_AUDIO_FAILED"
          : "PENDING";
    const response: Record<string, unknown> = {
      id: null,
      originUrl: null,
      originData: null,
      instrumentalUrl: null,
      vocalUrl: null,
      backingVocalsUrl: null,
      drumsUrl: null,
      bassUrl: null,
      guitarUrl: null,
      keyboardUrl: null,
      percussionUrl: null,
      stringsUrl: null,
      synthUrl: null,
      fxUrl: null,
      brassUrl: null,
      woodwindsUrl: null,
    };
    let sourceId: string | null = null;
    if (job.status === "complete") {
      const originData: Array<Record<string, unknown>> = [];
      // A stem task can return several variations (e.g. two vocal + two
      // instrumental takes). sunoapi.org reports one entry per stem, so keep the
      // first take of each distinct stem name.
      const seen = new Set<string>();
      for (const c of clips) {
        const meta = (c.metadata ?? {}) as Record<string, unknown>;
        let url = (c.audio_url as string) ?? null;
        const audioKey = c.audio_storage_key;
        if (typeof audioKey === "string") {
          const signed = await getReadUrl(audioKey);
          if (signed) url = signed;
        }
        const name = String(meta.stem_type_group_name ?? c.title ?? "")
          .replace(/[()]/g, "")
          .trim();
        const norm = name.toLowerCase();
        if (!sourceId && typeof meta.stem_from_id === "string") sourceId = meta.stem_from_id;
        if (norm && seen.has(norm)) continue;
        if (norm) seen.add(norm);
        const field = STEM_URL_FIELD[norm];
        if (field && url) response[field] = url;
        originData.push({
          duration: (meta.duration as number) ?? null,
          audio_url: url,
          stem_type_group_name: name || null,
          id: c.id,
        });
      }
      response.originData = originData;
      if (sourceId) {
        try {
          const mp3Key = objectKey("clips", `${sourceId}.mp3`);
          if (await objectExists(mp3Key)) response.originUrl = await getReadUrl(mp3Key);
        } catch {
          /* best-effort */
        }
      }
    }
    const terminal = job.status === "complete" || job.status === "error";
    return {
      code: 200,
      msg: job.status === "error" ? job.error || "Vocal separation failed" : "success",
      data: {
        taskId: job.id,
        musicId: sourceId,
        musicIndex: 0,
        callbackUrl: job.callbackUrl ?? "",
        completeTime: terminal ? sunoTime(job.completedAt ?? job.createdAt) : null,
        response,
        successFlag,
        createTime: sunoTime(job.createdAt),
        errorCode: job.status === "error" ? 500 : null,
        errorMessage: job.status === "error" ? job.error ?? null : null,
      },
    };
  }

  /** Music-video record-info in sunoapi.org's shape: `data.response.videoUrl`. */
  function musicVideoRecordInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const successFlag =
      job.status === "complete"
        ? "SUCCESS"
        : job.status === "error"
          ? "GENERATE_MP4_FAILED"
          : "PENDING";
    const videoUrl =
      job.status === "complete"
        ? ((res.video_url as string) ?? (res.download_url as string) ?? null)
        : null;
    const terminal = job.status === "complete" || job.status === "error";
    return {
      code: 200,
      msg: job.status === "error" ? job.error || "MP4 generation failed" : "success",
      data: {
        taskId: job.id,
        musicId: (res.clip_id as string) ?? null,
        musicIndex: 0,
        callbackUrl: job.callbackUrl ?? "",
        completeTime: terminal ? sunoTime(job.completedAt ?? job.createdAt) : null,
        response: { videoUrl },
        successFlag,
        createTime: sunoTime(job.createdAt),
        errorCode: job.status === "error" ? 500 : null,
        errorMessage: job.status === "error" ? job.error ?? null : null,
      },
    };
  }

  /**
   * MIDI record-info in sunoapi.org's shape: an integer `successFlag`
   * (0 pending / 1 success / 2 create-failed / 3 generate-failed), `midiData`,
   * and epoch-millisecond timestamps.
   */
  function midiRecordInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const ok = job.status === "complete";
    const successFlag = ok ? 1 : job.status === "error" ? 3 : 0;
    const terminal = ok || job.status === "error";
    return {
      code: 200,
      msg: job.status === "error" ? job.error || "MIDI generation failed" : "success",
      data: {
        taskId: job.id,
        recordTaskId: -1,
        audioId: (res.audio_id as string) ?? null,
        callbackUrl: job.callbackUrl ?? "",
        completeTime: terminal ? (job.completedAt ?? job.createdAt) : null,
        midiData: ok ? (res.midi_data ?? null) : null,
        successFlag,
        createTime: job.createdAt,
        errorCode: job.status === "error" ? "500" : null,
        errorMessage: job.status === "error" ? job.error ?? null : null,
      },
    };
  }

  /**
   * Recovery record-info in sunoapi.org's shape: top-level `code` (201 running /
   * 200 recovered / 500 all failed), `task_id`, and a per-track `data` array.
   */
  function recoveryRecordInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    if (job.status !== "complete" && job.status !== "error") {
      return { code: 201, task_id: job.id, msg: "success", data: null };
    }
    const tracks = Array.isArray(res.tracks) ? (res.tracks as Array<Record<string, unknown>>) : null;
    const recovered = (tracks ?? []).filter((t) => t.status === "success");
    return {
      code: recovered.length > 0 ? 200 : 500,
      task_id: job.id,
      msg: recovered.length > 0 ? "success" : (job.error || "Recovery failed"),
      data: tracks,
    };
  }

  /** Suno Voice "get verification phrase" in sunoapi.org's shape. */
  function voiceValidateInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const phrase = typeof res.phrase_text === "string" ? res.phrase_text : "";
    const failed = job.status === "error";
    const status = failed ? "processing_validate_fail" : phrase ? "wait_validating" : "processing_validate";
    return {
      code: 200,
      msg: failed ? job.error || "Validation phrase failed" : "success",
      data: {
        taskId: job.id,
        validateInfo: phrase,
        status,
        errorCode: failed ? 500 : null,
        errorMessage: failed ? job.error ?? null : null,
      },
    };
  }

  /** Custom-voice generation record-info: `{taskId, voiceId, status, ...}`. */
  function voiceRecordInfo(job: Job) {
    const res = (job.result ?? {}) as Record<string, unknown>;
    const failed = job.status === "error";
    const pending = job.status !== "complete" && !failed;
    const voiceId = typeof res.voice_id === "string" ? res.voice_id : "";
    const status = failed
      ? "processing_validate_fail"
      : pending
        ? "processing_validate"
        : voiceId
          ? "success"
          : "wait_validating";
    return {
      code: 200,
      msg: failed ? job.error || "Voice generation failed" : "success",
      data: {
        taskId: job.id,
        voiceId,
        status,
        errorCode: failed ? 500 : null,
        errorMessage: failed ? job.error ?? null : null,
      },
    };
  }

  /** Register a family-specific record-info route (same auth/ownership checks). */
  function shapedRecordInfoRoute(sunoPath: string, build: (job: Job) => unknown | Promise<unknown>) {
    app.get(`${PREFIX}${sunoPath}`, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const q = (req.query ?? {}) as { taskId?: string; task_id?: string };
      const id = q.taskId || q.task_id;
      if (!id) return reply.code(400).send({ error: "taskId is required." });
      const job = await getJob(id);
      if (!job) return reply.code(404).send({ error: "task not found." });
      if (job.userId && job.userId !== key.user_id) return reply.code(403).send({ error: "forbidden." });
      return await build(job);
    });
  }

  function wavRecordInfoRoute() {
    app.get(`${PREFIX}/convert-to-wav/record-info`, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const q = (req.query ?? {}) as { taskId?: string; task_id?: string };
      const id = q.taskId || q.task_id;
      if (!id) return reply.code(400).send({ error: "taskId is required." });
      const job = await getJob(id);
      if (!job) return reply.code(404).send({ error: "task not found." });
      if (job.userId && job.userId !== key.user_id) return reply.code(403).send({ error: "forbidden." });
      return await wavRecordInfo(job);
    });
  }


  // Add camelCase aliases (and vice versa) for the track fields sunoapi.org
  // returns in both spellings. Leaves any other fields untouched.
  function sunoTrack(value: unknown): unknown {
    if (!value || typeof value !== "object" || Array.isArray(value)) return value;
    const out: Record<string, unknown> = { ...(value as Record<string, unknown>) };
    const pairs: Array<[string, string]> = [
      ["audio_url", "audioUrl"],
      ["source_audio_url", "sourceAudioUrl"],
      ["stream_audio_url", "streamAudioUrl"],
      ["source_stream_audio_url", "sourceStreamAudioUrl"],
      ["image_url", "imageUrl"],
      ["source_image_url", "sourceImageUrl"],
      ["wav_url", "wavUrl"],
      ["download_url", "downloadUrl"],
      ["model_name", "modelName"],
    ];
    for (const [snake, camel] of pairs) {
      if (out[snake] === undefined && out[camel] !== undefined) out[snake] = out[camel];
      if (out[camel] === undefined && out[snake] !== undefined) out[camel] = out[snake];
    }
    return out;
  }

  function recordInfoRoute(sunoPath: string) {
    app.get(`${PREFIX}${sunoPath}`, async (req, reply) => {
      const key = await requireKey(req, reply);
      if (!key) return;
      const q = (req.query ?? {}) as { taskId?: string; task_id?: string };
      const id = q.taskId || q.task_id;
      if (!id) return reply.code(400).send({ error: "taskId is required." });
      const job = await getJob(id);
      if (!job) return reply.code(404).send({ error: "task not found." });
      if (job.userId && job.userId !== key.user_id) return reply.code(403).send({ error: "forbidden." });
      return await sunoRecordInfo(job);
    });
  }

  recordInfoRoute("/generate/record-info");
  recordInfoRoute("/cover-suno/record-info");
  recordInfoRoute("/cover/record-info");
  recordInfoRoute("/extend-upload/record-info");
  recordInfoRoute("/add-vocals/record-info");
  recordInfoRoute("/add-instrumental/record-info");
  recordInfoRoute("/music-remaster/record-info");
  wavRecordInfoRoute();
  shapedRecordInfoRoute("/vocal-removal/record-info", vocalRemovalRecordInfo);
  shapedRecordInfoRoute("/create-music-video/record-info", musicVideoRecordInfo);
  shapedRecordInfoRoute("/lyrics/record-info", lyricsRecordInfo);
  recordInfoRoute("/generate-persona/record-info");
  recordInfoRoute("/generate/upload-cover/record-info");
  recordInfoRoute("/generate/upload-extend/record-info");
  recordInfoRoute("/generate/add-vocals/record-info");
  recordInfoRoute("/generate/add-instrumental/record-info");
  recordInfoRoute("/generate/boost/record-info");
  recordInfoRoute("/generate/mashup/record-info");
  shapedRecordInfoRoute("/generate/midi/record-info", midiRecordInfo);
  shapedRecordInfoRoute("/voice/validate-info", voiceValidateInfo);
  shapedRecordInfoRoute("/voice/record-info", voiceRecordInfo);
  recordInfoRoute("/generate/cover/record-info");
  recordInfoRoute("/generate/cover-image/record-info");
  shapedRecordInfoRoute("/generate/recovery/record-info", recoveryRecordInfo);

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
    const musicIndex = await clipIndexInTask((in_.taskId as string) || (in_.task_id as string) || undefined, clip_id);
    void trackJob(runAudioDeliveryJob(job, clip_id, (in_.format as string) === "mp3" ? "mp3" : "wav", musicIndex));
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
    void trackJob(runMusicVideoJob(job, clip_id, aspectRatio));
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
    const sourceTaskId = (in_.taskId as string) || (in_.task_id as string) || undefined;
    const audioId = (in_.audioId as string) || (in_.audio_id as string) || undefined;
    const clipId = (in_.clip_id as string) || (sourceTaskId ? undefined : audioId);
    if (!sourceTaskId && !clipId) {
      return reply.code(400).send({ error: "taskId or audioId (clip_id) is required." });
    }
    const cost = await costFor("midi_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("midi_generate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "midi_generate"; job.credits = cost;
    void trackJob(runMidiJob(job, { sourceTaskId, audioId, clipId }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // POST /api/v1/generate/recovery -> /v1/music/recovery
  app.post(`${PREFIX}/generate/recovery`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const sunoTaskId =
      (in_.sunoTaskId as string) || (in_.taskId as string) || (in_.task_id as string) || undefined;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    if (!sunoTaskId && !clipId) {
      return reply.code(400).send({ error: "sunoTaskId or audioId (clip_id) is required." });
    }
    const cost = await costFor("recovery_audio");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("recovery_audio", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "recovery_audio"; job.credits = cost;
    void submitDescribedJob(job, { op: "recovery_audio", args: { sunoTaskId, clipId } });
    return reply.code(202).send({ code: 200, msg: "success", data: { task_id: job.id } });
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
    const musicIndex = await clipIndexInTask((in_.taskId as string) || (in_.task_id as string) || undefined, clip_id);
    void trackJob(runAudioDeliveryJob(job, clip_id, (in_.format as string) === "mp3" ? "mp3" : "wav", musicIndex));
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
    void trackJob(runMusicVideoJob(job, clip_id, aspectRatio));
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
      const data = await client.fetchAudioUploadStatus(id);
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
    let job = await reusableLyricsJob(id, key.user_id);
    if (!job) {
      const cost = await costFor("timestamped_lyrics_detail");
      if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
      job = newJob("timestamped_lyrics_detail");
      job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "timestamped_lyrics_detail"; job.credits = cost;
      void submitDescribedJob(job, { op: "timestamped_lyrics_detail", args: { id } });
    }
    await awaitJobTerminal(job, LYRICS_SYNC_WAIT_MS);
    return reply.send(timestampedLyricsBody(job));
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
    const voiceUrl = (in_.voiceUrl as string) || (in_.voice_url as string) || undefined;
    const language = (in_.language as string) || undefined;
    const cost = await costFor("voice_validate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_validate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_validate"; job.credits = cost;
    void runResultJobWithRetry(job, (client) => client.voiceValidate({ uploadId, audioUrl, voiceUrl, language }), {
      needFeature: "studio",
    });
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
    const validationTaskId = (in_.taskId as string) || (in_.task_id as string) || undefined;
    const verifyUrl = (in_.verifyUrl as string) || (in_.verify_url as string) || undefined;
    const custom = Boolean(validationTaskId && verifyUrl);
    if (!custom && (!clipId || !name)) {
      return reply
        .code(400)
        .send({ error: "clip_id (audioId) and name (voiceName), or taskId + verifyUrl, are required." });
    }
    const cost = await costFor("voice_generate");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_generate", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_generate"; job.credits = cost; job.prompt = name;
    if (custom) {
      void trackJob(runCustomVoiceJob(job, { validationTaskId: validationTaskId!, verifyUrl: verifyUrl!, voiceName: name }));
    } else {
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
        client.voiceGenerate({ clipId: clipId!, name: name!, styles, description, vocalStartS, vocalEndS }),
      { policy: "paid_only" });
    }
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
    const model = (in_.model as string) || undefined;
    const cost = await costFor("voice_apply", model);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const cb = callbackUrl(in_);
    const job = newJob("voice_apply", cb);
    job.userId = key.user_id; job.apiKeyId = key.id; job.endpoint = "voice_apply"; job.credits = cost;
    job.prompt = (in_.prompt as string) || undefined;
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
  // sunoapi.org compatibility layer (path + response parity)
  // ============================================================
  // sunoapi.org clients call a fixed path set under /api/v1. Where our canonical
  // route differs we forward in-process with `app.inject` and return the response
  // unchanged, so no business logic is duplicated. Targets are the /api/v1 routes
  // registered above (same `{code,msg,data}` envelope), so the forward is 1:1.
  function sunoAlias(method: "GET" | "POST", from: string, to: string): void {
    const handler = async (req: FastifyRequest, reply: FastifyReply) => {
      const raw = req.raw.url ?? "";
      const qs = raw.includes("?") ? raw.slice(raw.indexOf("?")) : "";
      const payload =
        req.body == null
          ? undefined
          : typeof req.body === "string"
            ? req.body
            : JSON.stringify(req.body);
      const headers: Record<string, string> = {};
      for (const h of ["authorization", "cookie", "content-type", "x-api-key", "user-agent", "accept-language"]) {
        const v = (req.headers as Record<string, unknown>)[h];
        if (v != null) headers[h] = Array.isArray(v) ? v.join(", ") : String(v);
      }
      if (payload && !headers["content-type"]) headers["content-type"] = "application/json";
      const res = await app.inject({ method, url: to + qs, headers, payload });
      reply.code(res.statusCode);
      const ct = res.headers["content-type"];
      if (typeof ct === "string") reply.header("content-type", ct);
      return reply.send(res.payload);
    };
    if (method === "GET") app.get(from, handler);
    else app.post(from, handler);
  }

  // --- path aliases (checklist §B) ---
  sunoAlias("POST", `${PREFIX}/style/generate`, `${PREFIX}/generate/boost`);
  sunoAlias("POST", `${PREFIX}/wav/generate`, `${PREFIX}/convert-to-wav/generate`);
  sunoAlias("GET", `${PREFIX}/wav/record-info`, `${PREFIX}/convert-to-wav/record-info`);
  sunoAlias("POST", `${PREFIX}/midi/generate`, `${PREFIX}/generate/midi`);
  sunoAlias("GET", `${PREFIX}/midi/record-info`, `${PREFIX}/generate/midi/record-info`);
  sunoAlias("POST", `${PREFIX}/mp4/generate`, `${PREFIX}/generate/music-video`);
  sunoAlias("GET", `${PREFIX}/mp4/record-info`, `${PREFIX}/create-music-video/record-info`);
  sunoAlias("POST", `${PREFIX}/suno/cover/generate`, `${PREFIX}/cover-suno/generate`);
  sunoAlias("GET", `${PREFIX}/suno/cover/record-info`, `${PREFIX}/cover-suno/record-info`);
  sunoAlias("POST", `${PREFIX}/suno/recovery`, `${PREFIX}/generate/recovery`);
  sunoAlias("GET", `${PREFIX}/suno/recovery/record-info`, `${PREFIX}/generate/recovery/record-info`);
  sunoAlias("POST", `${PREFIX}/voice/regenerate`, `${PREFIX}/voice/phrase`);

  // --- credit: sunoapi returns `data` as a bare integer (checklist §B1) ---
  app.get(`${PREFIX}/generate/credit`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    // sunoapi.org reports the account's spendable balance, not a single key's
    // allocation. Credits are pooled across a user's active keys, so return the
    // pool (the same value /get-credits exposes) as a bare integer.
    const bal = await accountCredits(key.user_id);
    return { code: 200, msg: "success", data: bal.credits };
  });

  // --- missing product routes (checklist §C) ---

  // get-timestamped-lyrics: their POST {taskId} -> our timestamped-lyrics job.
  app.post(`${PREFIX}/generate/get-timestamped-lyrics`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    // sunoapi.org sends both taskId (the generation task) and audioId (the
    // clip). Alignment reads the clip record, so the clip id must win — using
    // taskId here 404s against /api/clip/{taskId}.
    const id =
      (in_.audioId as string) ||
      (in_.audio_id as string) ||
      (in_.clip_id as string) ||
      (in_.clipId as string) ||
      (in_.taskId as string) ||
      (in_.task_id as string);
    if (!id) return reply.code(400).send({ error: "audioId (the clip id) is required." });
    if (await clipOwnedByOtherUser(key.user_id, id)) return denyForeignClip(reply);
    const cb = callbackUrl(in_);
    let job = await reusableLyricsJob(id, key.user_id);
    if (!job) {
      const cost = await costFor("timestamped_lyrics_detail");
      if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
      job = newJob("timestamped_lyrics_detail", cb);
      job.userId = key.user_id;
      job.apiKeyId = key.id;
      job.endpoint = "timestamped_lyrics_detail";
      job.credits = cost;
      void submitDescribedJob(job, { op: "timestamped_lyrics_detail", args: { id } });
    }
    await awaitJobTerminal(job, LYRICS_SYNC_WAIT_MS);
    return reply.send(timestampedLyricsBody(job));
  });

  // replace-section: map their field names onto our replaceSection op.
  app.post(`${PREFIX}/generate/replace-section`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const clipId = (in_.audioId as string) || (in_.clip_id as string) || undefined;
    const startS = Number(in_.infillStartS ?? in_.startS ?? in_.start_s);
    const endS = Number(in_.infillEndS ?? in_.endS ?? in_.end_s);
    const lyrics = (in_.lyrics as string) || (in_.prompt as string) || (in_.fullLyrics as string) || undefined;
    if (!clipId || !lyrics || !Number.isFinite(startS) || !Number.isFinite(endS) || endS <= startS) {
      return reply
        .code(400)
        .send({ error: "audioId, prompt/lyrics, infillStartS and infillEndS are required (end > start)." });
    }
    const cost = await costFor("replace_section");
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const job = newJob("replace_section", callbackUrl(in_));
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "replace_section";
    job.credits = cost;
    job.prompt = lyrics;
    void runClipJobWithRetry(job, (client) => client.replaceSection(clipId, { startS, endS, lyrics }));
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // sounds: their /generate/sounds -> our sounds builder.
  app.post(`${PREFIX}/generate/sounds`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const prompt =
      (in_.prompt as string) ||
      (in_.gpt_description_prompt as string) ||
      (in_.description as string) ||
      "";
    if (!prompt) return reply.code(400).send({ error: "prompt is required." });
    const model = (in_.model as string) || undefined;
    const cost = await costFor("sounds", model);
    if (!(await charge(key, cost))) return reply.code(402).send({ error: "Insufficient credits." });
    const params = {
      prompt,
      model,
      loop: in_.loop ?? in_.make_instrumental,
      tempo: in_.tempo,
      key: in_.key,
      callback_url: callbackUrl(in_),
    };
    const job = newJob("sounds", params.callback_url);
    job.userId = key.user_id;
    job.apiKeyId = key.id;
    job.endpoint = "sounds";
    job.model = model;
    job.prompt = prompt;
    job.credits = cost;
    const spolicy = await routingPolicy(model);
    void runClipJobWithRetry(job, processSoundsSubmit(params), { model, policy: spolicy });
    return reply.code(202).send({ code: 200, msg: "success", data: { taskId: job.id } });
  });

  // check-voice: best-effort availability lookup over our own voice jobs.
  // sunoapi returns `{code:400,"msg":"Voice record not found"}` for an unknown
  // task — hold that shape, and report `available` for a completed voice job.
  app.post(`${PREFIX}/voice/check-voice`, async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    const in_ = (req.body ?? {}) as Record<string, unknown>;
    const id = (in_.taskId as string) || (in_.task_id as string);
    if (!id) return { code: 400, msg: "taskId is required", data: null };
    const job = await getJob(id);
    if (!job || (job.userId && job.userId !== key.user_id)) {
      return { code: 400, msg: "Voice record not found", data: null };
    }
    const blob = JSON.stringify(job.result ?? {});
    const available = job.status === "complete" && /voice[_-]?id|persona[_-]?id/i.test(blob);
    return { code: 200, msg: "success", data: { taskId: id, available } };
  });

  // ============================================================
  // File Upload API (sunoapi.org /api/file-*) — free, temporary media
  // ============================================================
  const MIME_EXT: Record<string, string> = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "video/mp4": "mp4",
    "application/pdf": "pdf",
    "text/plain": "txt",
  };

  function extensionFor(mimeType: string, fileName?: string): string {
    if (fileName && /\.[a-z0-9]{1,5}$/i.test(fileName)) {
      return fileName.split(".").pop()!.toLowerCase();
    }
    return MIME_EXT[mimeType] ?? "bin";
  }

  async function storeUploadedFile(
    buffer: Buffer,
    opts: { uploadPath: string; fileName?: string; mimeType: string },
  ) {
    const segments = opts.uploadPath
      .split("/")
      .map((s) => s.trim())
      .filter(Boolean);
    const safeName =
      opts.fileName && opts.fileName.trim()
        ? opts.fileName.trim().replace(/[^a-zA-Z0-9._-]+/g, "_")
        : `upload-${randomUUID()}.${extensionFor(opts.mimeType)}`;
    const key = objectKey("uploads", ...segments, safeName);
    await putObject(key, buffer, opts.mimeType);
    return {
      fileName: safeName,
      filePath: [...segments, safeName].join("/"),
      downloadUrl: await getReadUrl(key),
      fileSize: buffer.length,
      mimeType: opts.mimeType,
      uploadedAt: new Date().toISOString(),
    };
  }

  function uploadOk(reply: FastifyReply, data: unknown) {
    return reply.code(200).send({ success: true, code: 200, msg: "File uploaded successfully", data });
  }
  function uploadErr(reply: FastifyReply, code: number, msg: string) {
    return reply.code(code).send({ success: false, code, msg });
  }
  function storageUnavailable(reply: FastifyReply) {
    return uploadErr(reply, 503, "File storage is not configured.");
  }

  // POST /api/file-base64-upload { base64Data, uploadPath, fileName? }
  app.post("/api/file-base64-upload", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    if (!storageConfigured()) return storageUnavailable(reply);
    const body = (req.body ?? {}) as Record<string, unknown>;
    const raw = typeof body.base64Data === "string" ? body.base64Data : "";
    const uploadPath = typeof body.uploadPath === "string" ? body.uploadPath.trim() : "";
    const fileName = typeof body.fileName === "string" ? body.fileName : undefined;
    if (!raw) return uploadErr(reply, 400, "base64Data is required.");
    if (!uploadPath) return uploadErr(reply, 400, "uploadPath is required.");
    let mimeType = "application/octet-stream";
    let encoded = raw;
    const dataUrl = raw.match(/^data:([^;]+);base64,(.*)$/s);
    if (dataUrl) {
      mimeType = dataUrl[1];
      encoded = dataUrl[2];
    }
    let buffer: Buffer;
    try {
      buffer = Buffer.from(encoded, "base64");
    } catch {
      return uploadErr(reply, 400, "Invalid base64 data.");
    }
    if (buffer.length === 0) return uploadErr(reply, 400, "Decoded file is empty.");
    if (buffer.length > 100 * 1024 * 1024) return uploadErr(reply, 400, "File exceeds the 100MB limit.");
    try {
      return uploadOk(reply, await storeUploadedFile(buffer, { uploadPath, fileName, mimeType }));
    } catch (e) {
      return uploadErr(reply, 500, e instanceof Error ? e.message : "Upload failed.");
    }
  });

  // POST /api/file-url-upload { fileUrl, uploadPath, fileName? }
  app.post("/api/file-url-upload", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    if (!storageConfigured()) return storageUnavailable(reply);
    const body = (req.body ?? {}) as Record<string, unknown>;
    const fileUrl = typeof body.fileUrl === "string" ? body.fileUrl : "";
    const uploadPath = typeof body.uploadPath === "string" ? body.uploadPath.trim() : "";
    let fileName = typeof body.fileName === "string" ? body.fileName : undefined;
    if (!/^https?:\/\//i.test(fileUrl)) return uploadErr(reply, 400, "fileUrl must be an http(s) URL.");
    if (!uploadPath) return uploadErr(reply, 400, "uploadPath is required.");
    let resp: Response;
    try {
      resp = await fetch(fileUrl, { signal: AbortSignal.timeout(30_000), redirect: "follow" });
    } catch {
      return uploadErr(reply, 400, "Failed to download fileUrl.");
    }
    if (!resp.ok) return uploadErr(reply, 400, `Failed to download fileUrl (${resp.status}).`);
    const bytes = Buffer.from(await resp.arrayBuffer());
    if (bytes.length > 100 * 1024 * 1024) return uploadErr(reply, 400, "File exceeds the 100MB limit.");
    const mimeType = (resp.headers.get("content-type") || "application/octet-stream").split(";")[0].trim();
    if (!fileName) fileName = decodeURIComponent(fileUrl.split("/").pop() || "") || undefined;
    try {
      return uploadOk(reply, await storeUploadedFile(bytes, { uploadPath, fileName, mimeType }));
    } catch (e) {
      return uploadErr(reply, 500, e instanceof Error ? e.message : "Upload failed.");
    }
  });

  // POST /api/file-stream-upload (multipart/form-data: file, uploadPath, fileName?)
  app.post("/api/file-stream-upload", async (req, reply) => {
    const key = await requireKey(req, reply);
    if (!key) return;
    if (!storageConfigured()) return storageUnavailable(reply);
    if (!req.isMultipart || !req.isMultipart()) {
      return uploadErr(reply, 400, "multipart/form-data is required.");
    }
    let fileBuffer: Buffer | null = null;
    let mimeType = "application/octet-stream";
    let originalName: string | undefined;
    let uploadPath = "";
    let fileName: string | undefined;
    for await (const part of req.parts()) {
      if (part.type === "file") {
        mimeType = part.mimetype || mimeType;
        originalName = part.filename;
        fileBuffer = await part.toBuffer();
      } else if (part.fieldname === "uploadPath") {
        uploadPath = String(part.value ?? "").trim();
      } else if (part.fieldname === "fileName") {
        fileName = String(part.value ?? "").trim() || undefined;
      }
    }
    if (!fileBuffer || fileBuffer.length === 0) return uploadErr(reply, 400, "file is required.");
    if (!uploadPath) return uploadErr(reply, 400, "uploadPath is required.");
    try {
      return uploadOk(
        reply,
        await storeUploadedFile(fileBuffer, { uploadPath, fileName: fileName || originalName, mimeType }),
      );
    } catch (e) {
      return uploadErr(reply, 500, e instanceof Error ? e.message : "Upload failed.");
    }
  });

  // ============================================================
  // Payment helpers
  // ============================================================

  function md5(str: string): string {
    return createHash("md5").update(str).digest("hex");
  }

  async function creditUser(
    q: QueryFn,
    userId: string,
    amount: number,
    apiKeyId?: string,
    txId?: string,
    label = "Purchase",
  ): Promise<void> {
    if (apiKeyId) {
      await q(
        "UPDATE api_keys SET credits = credits + $1, credits_expire_at = now() + interval '12 months' WHERE id = $2 AND user_id = $3",
        [amount, apiKeyId, userId],
      );
    } else {
      const keys = await q<{ id: string }>(
        "SELECT id FROM api_keys WHERE user_id = $1 AND is_active = true ORDER BY created_at ASC LIMIT 1",
        [userId],
      );
      if (keys.length === 0) {
        await q(
          `INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits, credits_expire_at) VALUES ($1, $2, $3, $4, $5, now() + interval '12 months')`,
          [userId, "Auto-Created Key", md5(randomUUID() + Date.now()), "auto_" + randomUUID().slice(0, 5), amount],
        );
      } else {
        await q(
          "UPDATE api_keys SET credits = credits + $1, credits_expire_at = now() + interval '12 months' WHERE id = $2",
          [amount, keys[0].id],
        );
      }
    }
    await q(
      `INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'purchase', $3)`,
      [userId, amount, txId ? `${label} top-up (ref: ${txId})` : `${label} top-up`],
    );
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

  // ChmabaPay (KHQR / ABA PayWay) Payment Endpoints — REQUIREMENTS §3.7
  // ============================================================
  // ChmabaPay never holds funds: money settles straight into the store's own
  // ABA PayWay link. There is no sandbox, so every key is live and credits are
  // only ever granted from a signature-verified webhook or an authoritative
  // status re-check. This extends the existing `payment_transactions` ledger
  // (provider = 'chmaba') so /me/transactions and the admin views keep working.

  type ChmabaPayment = {
    id: string;
    status: string;
    qr_string?: string | null;
    checkout_url?: string | null;
    expires_at?: string | null;
  };

  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  function chmabaConfigured(): boolean {
    return !!config.chmaba.apiKey && !!config.chmaba.storeId;
  }

  /** Thin fetch wrapper for the ChmabaPay REST API (Bearer auth + JSON). */
  async function chmabaRequest<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
    const base = config.chmaba.apiBaseUrl.replace(/\/+$/, "");
    const res = await fetch(`${base}${path}`, {
      method: init?.method ?? "GET",
      headers: {
        Authorization: `Bearer ${config.chmaba.apiKey}`,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
      },
      body: init?.body ? JSON.stringify(init.body) : undefined,
      signal: AbortSignal.timeout(30_000),
    });
    const text = await res.text();
    let parsed: unknown = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }
    if (!res.ok) {
      const detail = (parsed as { detail?: string } | null)?.detail ?? text.slice(0, 200);
      throw new Error(`ChmabaPay ${res.status}: ${detail || res.statusText}`);
    }
    return parsed as T;
  }

  /**
   * Verify a ChmabaPay webhook. The `X-ChmabaPay-Signature` header is
   * `t=<unix>,v1=<hex>` and the signed payload is `${t}.${rawBody}` (HMAC-SHA256
   * with the endpoint's `whsec_…` secret); a ±5 minute window rejects replays.
   */
  function verifyChmabaSignature(rawBody: string, header: string | undefined): boolean {
    const secret = config.chmaba.webhookSecret;
    if (!secret || !header) return false;
    const parts = header.split(",");
    const t = parts.find((p) => p.startsWith("t="))?.slice(2);
    const v1 = parts.find((p) => p.startsWith("v1="))?.slice(3);
    if (!t || !v1 || !Number.isFinite(Number(t))) return false;
    if (Math.abs(Date.now() / 1000 - Number(t)) > 300) return false;
    const expected = createHmac("sha256", secret).update(`${t}.${rawBody}`, "utf8").digest("hex");
    const a = Buffer.from(v1, "hex");
    const b = Buffer.from(expected, "hex");
    return a.length === b.length && timingSafeEqual(a, b);
  }

  /**
   * Return the first string under `reference_id`, anywhere in the event. The
   * delivery envelope is not documented field-by-field, so scanning for the id
   * we set at checkout is what maps a webhook back to one of our transactions.
   */
  function findReferenceId(node: unknown, depth = 0): string | null {
    if (depth > 8 || node === null || typeof node !== "object") return null;
    if (Array.isArray(node)) {
      for (const item of node) {
        const found = findReferenceId(item, depth + 1);
        if (found) return found;
      }
      return null;
    }
    const rec = node as Record<string, unknown>;
    if (typeof rec.reference_id === "string" && rec.reference_id.trim()) return rec.reference_id.trim();
    for (const value of Object.values(rec)) {
      const found = findReferenceId(value, depth + 1);
      if (found) return found;
    }
    return null;
  }

  /**
   * Claim a pending ChmabaPay transaction and grant its credits. The guarded
   * UPDATE lets only the first caller win, so a webhook retry or a status poll
   * racing the webhook credits exactly once.
   */
  async function settleChmabaPayment(txId: string): Promise<boolean> {
    return withTransaction(async (tq) => {
      const claimed = await tq<{ user_id: string; credit_amount: number; api_key_target_id: string | null }>(
        `UPDATE payment_transactions SET status = 'paid', paid_at = now()
         WHERE id = $1 AND status = 'pending'
         RETURNING user_id, credit_amount, api_key_target_id`,
        [txId],
      );
      if (claimed.length === 0) return false;
      const row = claimed[0];
      await creditUser(tq, row.user_id, row.credit_amount, row.api_key_target_id ?? undefined, txId, "ChmabaPay");
      return true;
    });
  }

  /**
   * Reverse a settled ChmabaPay payment: claw back the granted credits and mark
   * the transaction refunded. The guarded UPDATE makes it idempotent, and the
   * debit is clamped at zero — if the user already spent the credits, the
   * balance is recovered as far as it goes and the platform absorbs the rest.
   */
  async function reverseChmabaPayment(txId: string): Promise<boolean> {
    return withTransaction(async (tq) => {
      const claimed = await tq<{ user_id: string; credit_amount: number; api_key_target_id: string | null }>(
        `UPDATE payment_transactions SET status = 'refunded'
         WHERE id = $1 AND provider = 'chmaba' AND status = 'paid'
         RETURNING user_id, credit_amount, api_key_target_id`,
        [txId],
      );
      if (claimed.length === 0) return false;
      const row = claimed[0];
      const amount = Math.max(0, Number(row.credit_amount) || 0);
      if (amount > 0) {
        if (row.api_key_target_id) {
          await tq(
            "UPDATE api_keys SET credits = GREATEST(0, credits - $1) WHERE id = $2 AND user_id = $3",
            [amount, row.api_key_target_id, row.user_id],
          );
        } else {
          // Mirrors creditUser's default: the oldest active key received the grant.
          const keys = await tq<{ id: string }>(
            "SELECT id FROM api_keys WHERE user_id = $1 AND is_active = true ORDER BY created_at ASC LIMIT 1",
            [row.user_id],
          );
          if (keys.length > 0) {
            await tq(
              "UPDATE api_keys SET credits = GREATEST(0, credits - $1) WHERE id = $2",
              [amount, keys[0].id],
            );
          }
        }
        await tq(
          "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'refund', $3)",
          [row.user_id, -amount, `ChmabaPay reversal (ref: ${txId})`],
        );
      }
      return true;
    });
  }

  // POST /payments/chmaba/create — mint a KHQR payment for a pack. The billing
  // modal renders the returned code inline via `qr_url`.
  app.post("/payments/chmaba/create", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    if (!chmabaConfigured()) {
      return reply.code(503).send({ error: "Payments are not configured yet." });
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

    // The optional target key must belong to the caller; otherwise the settled
    // credits would no-op (creditUser guards user_id) and the top-up be lost.
    if (targetKeyId) {
      if (!UUID_RE.test(targetKeyId)) {
        return reply.code(400).send({ error: "api_key_id is invalid." });
      }
      const ownedKey = await queryOne<{ id: string }>(
        "SELECT id FROM api_keys WHERE id = $1 AND user_id = $2",
        [targetKeyId, u.id],
      );
      if (!ownedKey) {
        return reply.code(400).send({ error: "api_key_id does not belong to you." });
      }
    }

    const amount = Number(pack.price);
    if (!Number.isFinite(amount) || amount <= 0) {
      return reply.code(400).send({ error: "Pack has no valid price." });
    }

    // Insert first so the row id doubles as the provider's reference_id,
    // giving the webhook a stable handle back to this transaction.
    const created = await queryOne<{ id: string }>(
      `INSERT INTO payment_transactions
         (user_id, pack_id, credit_amount, currency, amount, payment_method, provider, status, api_key_target_id)
       VALUES ($1, $2, $3, $4, $5, 'chmaba', 'chmaba', 'pending', $6)
       RETURNING id`,
      [u.id, pack.id, pack.amount, pack.currency, amount, targetKeyId || null],
    );
    if (!created) return reply.code(500).send({ error: "Could not create transaction." });

    try {
      const payment = await chmabaRequest<ChmabaPayment>("/v1/payments", {
        method: "POST",
        body: {
          amount,
          reference_id: created.id,
          idempotency_key: created.id,
          store: config.chmaba.storeId,
          metadata: { user_id: u.id, pack_id: pack.id, credits: pack.amount },
        },
      });
      await query(
        `UPDATE payment_transactions
           SET provider_payment_id = $1, checkout_url = $2, qr_string = $3,
               expires_at = COALESCE($4, expires_at)
         WHERE id = $5`,
        [payment.id, payment.checkout_url ?? null, payment.qr_string ?? null, payment.expires_at ?? null, created.id],
      );
      return {
        transaction_id: created.id,
        provider: "chmaba",
        credits: pack.amount,
        currency: pack.currency,
        amount,
        qr_string: payment.qr_string ?? null,
        // Same-origin SVG the billing modal renders inline instead of bouncing
        // the payer to the ChmabaPay hosted checkout.
        qr_url: `/payments/chmaba/qr/${created.id}`,
        checkout_url: payment.checkout_url ?? null,
        expires_at: payment.expires_at ?? null,
      };
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      await query(
        "UPDATE payment_transactions SET status = 'failed', error_message = $1 WHERE id = $2 AND status = 'pending'",
        [err, created.id],
      );
      req.log.error({ err }, "chmaba payment create failed");
      return reply.code(502).send({ error: "Payment provider error. Please try again." });
    }
  });

  // GET /payments/chmaba/qr/:id — the KHQR as an SVG image for one of the
  // caller's own transactions. Proxies ChmabaPay's public, stateless renderer
  // (`GET /v1/khqr/render.svg`) so the billing modal can show the code inline
  // and the raw payload / provider origin stay server-side.
  app.get("/payments/chmaba/qr/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    if (!UUID_RE.test(id)) return reply.code(404).send({ error: "Transaction not found." });

    const tx = await queryOne<{ qr_string: string | null; provider_payment_id: string | null }>(
      `SELECT qr_string, provider_payment_id FROM payment_transactions
       WHERE id = $1 AND user_id = $2 AND provider = 'chmaba'`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });

    const base = config.chmaba.apiBaseUrl.replace(/\/+$/, "");
    // Prefer the payload we stored at create; fall back to the provider's own
    // hosted QR (which 410s once the code is dead) when only the id is known.
    const url = tx.qr_string
      ? `${base}/v1/khqr/render.svg?payload=${encodeURIComponent(tx.qr_string)}`
      : tx.provider_payment_id
        ? `${base}/pay/${encodeURIComponent(tx.provider_payment_id)}/qr.svg`
        : null;
    if (!url) return reply.code(404).send({ error: "No QR code for this payment." });

    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(15_000) });
      if (!res.ok) throw new Error(`render ${res.status}`);
      const svg = await res.text();
      reply.header("Content-Type", "image/svg+xml; charset=utf-8");
      reply.header("Cache-Control", "private, max-age=60");
      return reply.send(svg);
    } catch (e) {
      req.log.warn({ err: e }, "chmaba qr render failed");
      return reply.code(502).send({ error: "QR code is unavailable. Please try again." });
    }
  });

  // GET /payments/chmaba/status/:id — poll local state, reconciling with the
  // provider while pending (webhooks can lag or be missed).
  app.get("/payments/chmaba/status/:id", async (req, reply) => {
    const u = requireAuth(req, reply);
    if (!u) return;
    const { id } = req.params as { id: string };
    const tx = await queryOne<{
      id: string; status: string; provider_payment_id: string | null; expires_at: string;
      credit_amount: number; amount: string; currency: string; paid_at: string | null;
    }>(
      `SELECT id, status, provider_payment_id, expires_at, credit_amount, amount, currency, paid_at
       FROM payment_transactions WHERE id = $1 AND user_id = $2 AND provider = 'chmaba'`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });

    if (tx.status === "pending" && tx.provider_payment_id && chmabaConfigured()) {
      try {
        const check = await chmabaRequest<{ status: string }>(
          `/v1/transactions/check-status/${encodeURIComponent(tx.provider_payment_id)}`,
        );
        if (check.status === "PAID") {
          await settleChmabaPayment(tx.id);
        } else if (check.status === "FAILED") {
          await query("UPDATE payment_transactions SET status = 'failed' WHERE id = $1 AND status = 'pending'", [tx.id]);
        } else if (new Date(tx.expires_at).getTime() < Date.now()) {
          await query("UPDATE payment_transactions SET status = 'expired' WHERE id = $1 AND status = 'pending'", [tx.id]);
        }
      } catch (e) {
        req.log.warn({ err: e }, "chmaba status reconcile failed");
      }
    }

    const fresh = await queryOne<{ status: string; paid_at: string | null; error_message: string | null }>(
      "SELECT status, paid_at, error_message FROM payment_transactions WHERE id = $1",
      [tx.id],
    );
    return {
      transaction_id: tx.id,
      status: fresh?.status ?? tx.status,
      credits: tx.credit_amount,
      currency: tx.currency,
      amount: Number(tx.amount),
      paid_at: fresh?.paid_at ?? tx.paid_at,
      expires_at: tx.expires_at,
      error: fresh?.error_message ?? null,
    };
  });

  // POST /payments/chmaba/webhook — PUBLIC, server-to-server. ChmabaPay has no
  // session cookie or API key, so authenticity rests entirely on the HMAC
  // signature; credits are granted only for a verified payment.completed.
  app.post("/payments/chmaba/webhook", async (req, reply) => {
    const raw = (req as FastifyRequest & { rawBody?: string }).rawBody ?? "";
    const signature = req.headers["x-chmabapay-signature"] as string | undefined;
    const event = (req.headers["x-chmabapay-event"] as string | undefined) ?? "";

    if (!config.chmaba.webhookSecret) {
      return reply.code(503).send({ error: "Webhook secret is not configured." });
    }
    if (!verifyChmabaSignature(raw, signature)) {
      req.log.warn("chmaba webhook signature rejected");
      return reply.code(400).send({ error: "Invalid signature." });
    }

    const referenceId = findReferenceId(req.body);

    if (event === "payment.completed") {
      if (!referenceId || !UUID_RE.test(referenceId)) return { ok: true, ignored: "unrecognized reference" };
      try {
        const credited = await settleChmabaPayment(referenceId);
        return { ok: true, credited };
      } catch (e) {
        req.log.error({ err: e, referenceId }, "chmaba webhook settle failed");
        // 500 so ChmabaPay retries the delivery.
        return reply.code(500).send({ error: "Could not settle payment." });
      }
    }

    if (event === "payment.reversed") {
      if (referenceId && UUID_RE.test(referenceId)) {
        await reverseChmabaPayment(referenceId);
      }
      return { ok: true };
    }

    return { ok: true, ignored: event || "unknown event" };
  });

  return app;
}
