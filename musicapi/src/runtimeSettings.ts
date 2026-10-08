/**
 * Admin-managed runtime settings.
 *
 * Integration keys (Suno, 2Captcha, Google, ChmabaPay, B2, alerts) can
 * be set in the admin console instead of `.env`. They live in the existing
 * `app_settings` table under the `integrations` key; secret fields are encrypted
 * at rest with the same AES-256-GCM master key used for Suno cookies
 * (`COOKIE_ENCRYPTION_KEY`).
 *
 * Resolution order per field: stored value → env var → built-in default. The
 * merged result is written into `config` in place, so existing call sites keep
 * reading `config.*` and pick up changes without a restart. Bootstrap values
 * that the process needs before the database is reachable (DATABASE_URL,
 * JWT_SECRET, COOKIE_ENCRYPTION_KEY, PORT, …) intentionally stay in `.env`.
 */
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { config } from "./config.js";
import { query, queryOne } from "./db.js";
import { resetStorageClient } from "./storage.js";

const SETTINGS_KEY = "integrations";
const ENC_PREFIX = "enc:v1:";
const IV_BYTES = 12;
const TAG_BYTES = 16;

export type FieldType = "string" | "secret" | "number" | "boolean";

export interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
  /** Primary env var used as the fallback when no stored value exists. */
  env: string;
  /** Additional env vars tried (e.g. platform-shared B2 secrets). */
  envFallbacks?: string[];
  def?: string | number | boolean;
  /** Short helper text shown under the field in the admin UI. */
  help?: string;
}

export interface GroupDef {
  key: string;
  label: string;
  fields: FieldDef[];
}

/**
 * Boot-time Suno concurrency defaults, captured before any stored override is
 * applied. Used as the fallback when a field is cleared in the admin console, so
 * clearing falls back to the configured value rather than the last-applied one.
 */
const SUNO_CONCURRENCY_DEFAULTS = { ...config.suno };

/**
 * Boot-time credit-gate defaults, captured before any stored override is
 * applied. Used as the fallback when the field is cleared in the admin console.
 */
const CREDIT_GATE_DEFAULTS = { ...config.creditGate };

/** Every key that can be managed from the admin console. */
export const INTEGRATION_GROUPS: GroupDef[] = [
  {
    key: "suno",
    label: "Suno account auth",
    fields: [
      { key: "clientCookie", label: "Durable __client cookie", type: "secret", env: "SUNO_CLIENT_COOKIE", def: "", help: "Boot-seed only. Each Suno login has its own __client cookie — add extra accounts on the Suno Accounts page." },
      { key: "cookie", label: "Full cookie header", type: "secret", env: "SUNO_COOKIE", def: "" },
      { key: "jwt", label: "One-off access JWT", type: "secret", env: "SUNO_JWT", def: "", help: "Expires in ~1 hour and cannot refresh. Prefer __client." },
      { key: "deviceId", label: "Device id", type: "string", env: "SUNO_DEVICE_ID", def: config.deviceId, help: "Per-account. Leave blank when adding accounts and one is generated." },
      { key: "captchaToken", label: "Captcha token", type: "secret", env: "SUNO_CAPTCHA_TOKEN", def: "" },
      { key: "model", label: "Default model", type: "string", env: "SUNO_MODEL", def: "chirp-hawk" },
      { key: "clerkUrl", label: "Clerk URL", type: "string", env: "SUNO_CLERK_URL", def: "https://auth.suno.com" },
      { key: "apiUrl", label: "Suno API URL", type: "string", env: "SUNO_API_URL", def: "https://studio-api-prod.suno.com" },
      { key: "turnstileSitekey", label: "Turnstile sitekey", type: "string", env: "SUNO_TURNSTILE_SITEKEY", def: "0x4AAAAAADI7xDNyj-3LcIbi" },
      { key: "turnstilePageUrl", label: "Turnstile page URL", type: "string", env: "SUNO_TURNSTILE_PAGEURL", def: "https://suno.com/create" },
    ],
  },
  {
    key: "sunoConcurrency",
    label: "Suno concurrency (jobs)",
    fields: [
      {
        key: "concurrentPerAccount",
        label: "Parallel jobs per Suno account",
        type: "number",
        env: "SUNO_CONCURRENT_PER_ACCOUNT",
        def: SUNO_CONCURRENCY_DEFAULTS.concurrentPerAccount,
        help: "The global ceiling is pool size × this value (unless Global max is set). Adding Suno accounts raises capacity automatically — no change needed here.",
      },
      {
        key: "maxConcurrent",
        label: "Global max concurrent (blank = auto)",
        type: "number",
        env: "SUNO_MAX_CONCURRENT",
        def: SUNO_CONCURRENCY_DEFAULTS.maxConcurrent ?? "",
        help: "Leave blank to derive the ceiling from the account pool. Set a number to pin it regardless of pool size.",
      },
      {
        key: "maxConcurrentPerUser",
        label: "Max concurrent per user",
        type: "number",
        env: "SUNO_MAX_CONCURRENT_PER_USER",
        def: SUNO_CONCURRENCY_DEFAULTS.maxConcurrentPerUser,
        help: "How many jobs one user may run at once across all their API keys. A per-user rate-limits override wins over this.",
      },
      {
        key: "maxConcurrentPerAccount",
        label: "Max in-flight per account",
        type: "number",
        env: "SUNO_MAX_CONCURRENT_PER_ACCOUNT",
        def: SUNO_CONCURRENCY_DEFAULTS.maxConcurrentPerAccount,
        help: "Per-account cap; selection is least-loaded-first so a burst spreads across the pool.",
      },
      {
        key: "maxQueue",
        label: "Max waiting jobs (0 = unlimited)",
        type: "number",
        env: "SUNO_MAX_QUEUE",
        def: SUNO_CONCURRENCY_DEFAULTS.maxQueue,
        help: "Jobs beyond the ceiling wait for a slot; past this depth new jobs fail fast with a retryable error.",
      },
      {
        key: "requestsPerAccount",
        label: "Requests per account per window (0 = unlimited)",
        type: "number",
        env: "SUNO_REQUESTS_PER_ACCOUNT",
        def: SUNO_CONCURRENCY_DEFAULTS.requestsPerAccount,
        help: "Paces calls to each Suno account to stay under its rate limit (Suno allows ~20 per 10s). Prevents 429s; extra calls wait instead of failing.",
      },
      {
        key: "rateWindowMs",
        label: "Rate-limit window (ms)",
        type: "number",
        env: "SUNO_RATE_WINDOW_MS",
        def: SUNO_CONCURRENCY_DEFAULTS.rateWindowMs,
        help: "Window for the per-account request budget above. Default 10000 (10 seconds).",
      },
      {
        key: "rateLimitCooldownMs",
        label: "429 cooldown (ms)",
        type: "number",
        env: "SUNO_RATE_LIMIT_COOLDOWN_MS",
        def: SUNO_CONCURRENCY_DEFAULTS.rateLimitCooldownMs,
        help: "How long an account sits out after a 429 so it isn't re-hit immediately. 0 disables.",
      },
      {
        key: "minCredits",
        label: "Min credits per account",
        type: "number",
        env: "SUNO_MIN_CREDITS",
        def: SUNO_CONCURRENCY_DEFAULTS.minCredits,
        help: "Accounts below this balance are skipped for new work, avoiding 402 'not enough credits' submissions.",
      },
    ],
  },
  {
    key: "creditGate",
    label: "Customer credit gate",
    fields: [
      {
        key: "minCredits",
        label: "Min credits to run free endpoints",
        type: "number",
        env: "USER_MIN_CREDITS",
        def: CREDIT_GATE_DEFAULTS.minCredits,
        help: "A customer must hold at least this many credits to run free (0-cost) generation endpoints. The credits are not spent — free stays free for paying customers — but a drained account cannot use them. Paid endpoints are unaffected; 0 disables the gate.",
      },
    ],
  },
  {
    key: "captcha",
    label: "Captcha solving",
    fields: [{ key: "twoCaptchaKey", label: "2Captcha key", type: "secret", env: "TWOCAPTCHA_KEY", def: "", help: "Solves Suno's captcha gate at generation time. Get it from 2captcha.com." }],
  },
  {
    key: "google",
    label: "Google sign-in",
    fields: [
      { key: "clientId", label: "Client id", type: "string", env: "GOOGLE_CLIENT_ID", def: "", help: "Google Cloud Console → Credentials (OAuth client). Users sign in ONLY via Google." },
      { key: "clientSecret", label: "Client secret", type: "secret", env: "GOOGLE_CLIENT_SECRET", def: "" },
      { key: "redirectUriUser", label: "User redirect URI", type: "string", env: "GOOGLE_REDIRECT_URI_USER", def: "http://localhost:4001/auth/callback" },
    ],
  },
  {
    key: "chmaba",
    label: "ChmabaPay",
    fields: [
      { key: "apiKey", label: "API key", type: "secret", env: "CHMABA_API_KEY", def: "", help: "ChmabaPay live key (ck_live_…). Checkout stays disabled until key + store id are set." },
      { key: "storeId", label: "Store id", type: "string", env: "CHMABA_STORE_ID", def: "" },
      { key: "webhookSecret", label: "Webhook secret", type: "secret", env: "CHMABA_WEBHOOK_SECRET", def: "", help: "whsec_… used to verify ChmabaPay payment webhooks." },
      { key: "apiBaseUrl", label: "API base URL", type: "string", env: "CHMABA_API_BASE_URL", def: "https://pay.chmaba.com" },
    ],
  },
  {
    key: "storage",
    label: "Media storage (B2)",
    fields: [
      { key: "endpoint", label: "Endpoint", type: "string", env: "MUSICAPI_B2_ENDPOINT", envFallbacks: ["PLATFORM_STREAMING_B2_ENDPOINT"], def: "https://s3.us-east-005.backblazeb2.com" },
      { key: "region", label: "Region", type: "string", env: "MUSICAPI_B2_REGION", envFallbacks: ["PLATFORM_STREAMING_B2_REGION"], def: "us-east-005" },
      { key: "bucket", label: "Bucket", type: "string", env: "MUSICAPI_B2_BUCKET", envFallbacks: ["PLATFORM_STREAMING_B2_BUCKET"], def: "", help: "Backblaze B2 bucket that stores the generated MP3/WAV and cover images." },
      { key: "keyId", label: "Key id", type: "secret", env: "MUSICAPI_B2_KEY_ID", envFallbacks: ["PLATFORM_STREAMING_B2_KEY_ID"], def: "" },
      { key: "applicationKey", label: "Application key", type: "secret", env: "MUSICAPI_B2_APPLICATION_KEY", envFallbacks: ["PLATFORM_STREAMING_B2_APPLICATION_KEY"], def: "" },
      { key: "prefix", label: "Key prefix", type: "string", env: "MUSICAPI_B2_PREFIX", def: "musicapi" },
      { key: "publicBaseUrl", label: "Public CDN base URL", type: "string", env: "MUSICAPI_B2_PUBLIC_BASE_URL", def: "" },
      { key: "urlTtlSeconds", label: "Signed URL TTL (s)", type: "number", env: "MUSICAPI_B2_URL_TTL_SECONDS", def: 604800 },
    ],
  },
  {
    key: "alerts",
    label: "Alert delivery",
    fields: [
      { key: "telegramBotToken", label: "Telegram bot token", type: "secret", env: "ALERT_TELEGRAM_BOT_TOKEN", def: "" },
      { key: "telegramChatId", label: "Telegram chat id", type: "string", env: "ALERT_TELEGRAM_CHAT_ID", def: "" },
    ],
  },
  {
    key: "callbacks",
    label: "Webhook callbacks",
    fields: [
      { key: "allowedHosts", label: "Allowed callback hosts (comma-separated)", type: "string", env: "CALLBACK_ALLOWED_HOSTS", def: "", help: "Optional SSRF guard for customer webhooks. Each API request can set its own callback_url; when this is set, the callback host must match an entry (or a subdomain). Empty = any public host is allowed; private/internal addresses are always blocked." },
    ],
  },
];

type GroupValues = Record<string, unknown>;
type StoredSettings = Record<string, GroupValues>;

let current: StoredSettings = {};

function envValue(f: FieldDef): unknown {
  const names = [f.env, ...(f.envFallbacks ?? [])];
  for (const name of names) {
    const raw = process.env[name];
    if (raw === undefined || raw === "") continue;
    if (f.type === "number") return Number(raw);
    if (f.type === "boolean") return raw === "true";
    return raw;
  }
  return f.def;
}

function encryptSecret(plain: string): string {
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv("aes-256-gcm", config.cookieEncryptionKey, iv);
  const ciphertext = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  return ENC_PREFIX + Buffer.concat([iv, cipher.getAuthTag(), ciphertext]).toString("base64");
}

function decryptSecret(stored: string): string {
  const payload = Buffer.from(stored.slice(ENC_PREFIX.length), "base64");
  if (payload.length < IV_BYTES + TAG_BYTES) throw new Error("Malformed encrypted setting.");
  const iv = payload.subarray(0, IV_BYTES);
  const tag = payload.subarray(IV_BYTES, IV_BYTES + TAG_BYTES);
  const ciphertext = payload.subarray(IV_BYTES + TAG_BYTES);
  const decipher = createDecipheriv("aes-256-gcm", config.cookieEncryptionKey, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf8");
}

function isEncrypted(value: unknown): value is string {
  return typeof value === "string" && value.startsWith(ENC_PREFIX);
}

async function readStored(): Promise<StoredSettings> {
  const row = await queryOne<{ value: StoredSettings | null }>(
    "SELECT value FROM app_settings WHERE key = $1",
    [SETTINGS_KEY],
  );
  return (row?.value ?? {}) as StoredSettings;
}

function applyToConfig(): void {
  const str = (group: string, field: string, fallback: string): string => {
    const v = current[group]?.[field];
    return v === undefined || v === null ? fallback : String(v);
  };
  const num = (group: string, field: string, fallback: number): number => {
    const v = current[group]?.[field];
    if (v === undefined || v === null || v === "") return fallback;
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? n : fallback;
  };
  const bool = (group: string, field: string, fallback: boolean): boolean => {
    const v = current[group]?.[field];
    return typeof v === "boolean" ? v : fallback;
  };

  config.clientCookie = str("suno", "clientCookie", config.clientCookie);
  config.cookie = str("suno", "cookie", config.cookie);
  config.jwt = str("suno", "jwt", config.jwt);
  config.deviceId = str("suno", "deviceId", config.deviceId);
  config.captchaToken = str("suno", "captchaToken", config.captchaToken);
  config.model = str("suno", "model", config.model);
  config.clerkUrl = str("suno", "clerkUrl", config.clerkUrl);
  config.apiUrl = str("suno", "apiUrl", config.apiUrl);
  config.turnstileSitekey = str("suno", "turnstileSitekey", config.turnstileSitekey);
  config.turnstilePageUrl = str("suno", "turnstilePageUrl", config.turnstilePageUrl);

  // Suno concurrency (see the `suno` block in src/config.ts and
  // src/concurrency.ts). Applied on every save; the ConcurrencyGate and the
  // per-job caps read these live, so changes take effect without a restart.
  config.suno.concurrentPerAccount = Math.max(
    1,
    num("sunoConcurrency", "concurrentPerAccount", SUNO_CONCURRENCY_DEFAULTS.concurrentPerAccount),
  );
  config.suno.maxConcurrent = (() => {
    const v = current["sunoConcurrency"]?.["maxConcurrent"];
    if (v === undefined || v === null || v === "") return SUNO_CONCURRENCY_DEFAULTS.maxConcurrent;
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? Math.max(1, n) : SUNO_CONCURRENCY_DEFAULTS.maxConcurrent;
  })();
  config.suno.maxConcurrentPerUser = Math.max(
    1,
    num("sunoConcurrency", "maxConcurrentPerUser", SUNO_CONCURRENCY_DEFAULTS.maxConcurrentPerUser),
  );
  config.suno.maxConcurrentPerAccount = Math.max(
    1,
    num("sunoConcurrency", "maxConcurrentPerAccount", SUNO_CONCURRENCY_DEFAULTS.maxConcurrentPerAccount),
  );
  config.suno.maxQueue = Math.max(
    0,
    num("sunoConcurrency", "maxQueue", SUNO_CONCURRENCY_DEFAULTS.maxQueue),
  );
  config.suno.requestsPerAccount = Math.max(
    0,
    num("sunoConcurrency", "requestsPerAccount", SUNO_CONCURRENCY_DEFAULTS.requestsPerAccount),
  );
  config.suno.rateWindowMs = Math.max(
    100,
    num("sunoConcurrency", "rateWindowMs", SUNO_CONCURRENCY_DEFAULTS.rateWindowMs),
  );
  config.suno.rateLimitCooldownMs = Math.max(
    0,
    num("sunoConcurrency", "rateLimitCooldownMs", SUNO_CONCURRENCY_DEFAULTS.rateLimitCooldownMs),
  );
  config.suno.minCredits = Math.max(
    0,
    num("sunoConcurrency", "minCredits", SUNO_CONCURRENCY_DEFAULTS.minCredits),
  );

  // Customer credit gate (see the `creditGate` block in src/config.ts). Applied
  // on every save; the job-admission helpers read it live, so changes take
  // effect without a restart.
  config.creditGate.minCredits = Math.max(
    0,
    num("creditGate", "minCredits", CREDIT_GATE_DEFAULTS.minCredits),
  );

  config.twoCaptchaKey = str("captcha", "twoCaptchaKey", config.twoCaptchaKey);

  config.google.clientId = str("google", "clientId", config.google.clientId);
  config.google.clientSecret = str("google", "clientSecret", config.google.clientSecret);
  config.google.redirectUriUser = str("google", "redirectUriUser", config.google.redirectUriUser);

  config.chmaba.apiKey = str("chmaba", "apiKey", config.chmaba.apiKey);
  config.chmaba.storeId = str("chmaba", "storeId", config.chmaba.storeId);
  config.chmaba.webhookSecret = str("chmaba", "webhookSecret", config.chmaba.webhookSecret);
  config.chmaba.apiBaseUrl = str("chmaba", "apiBaseUrl", config.chmaba.apiBaseUrl);

  config.storage.endpoint = str("storage", "endpoint", config.storage.endpoint);
  config.storage.region = str("storage", "region", config.storage.region);
  config.storage.bucket = str("storage", "bucket", config.storage.bucket);
  config.storage.keyId = str("storage", "keyId", config.storage.keyId);
  config.storage.applicationKey = str("storage", "applicationKey", config.storage.applicationKey);
  config.storage.prefix = str("storage", "prefix", config.storage.prefix).replace(/^\/+|\/+$/g, "");
  config.storage.publicBaseUrl = str("storage", "publicBaseUrl", config.storage.publicBaseUrl).replace(/\/+$/, "");
  config.storage.urlTtlSeconds = num("storage", "urlTtlSeconds", config.storage.urlTtlSeconds);

  config.alerts.telegramBotToken = str("alerts", "telegramBotToken", config.alerts.telegramBotToken);
  config.alerts.telegramChatId = str("alerts", "telegramChatId", config.alerts.telegramChatId);

  config.callbackAllowedHosts = str("callbacks", "allowedHosts", "")
    .split(",")
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);

  // Storage caches its S3 client on first use; drop it so new creds take effect.
  resetStorageClient();
}

/** Load stored settings (decrypting secrets), merge over env, and apply to config. */
export async function loadRuntimeSettings(): Promise<void> {
  const stored = await readStored();
  const merged: StoredSettings = {};
  for (const group of INTEGRATION_GROUPS) {
    merged[group.key] = {};
    for (const f of group.fields) {
      const raw = stored[group.key]?.[f.key];
      if (raw === undefined || raw === null || raw === "") {
        merged[group.key][f.key] = envValue(f);
      } else if (f.type === "secret" && isEncrypted(raw)) {
        try {
          merged[group.key][f.key] = decryptSecret(raw);
        } catch {
          // Key mismatch → fall back to env rather than crashing boot.
          merged[group.key][f.key] = envValue(f);
        }
      } else {
        merged[group.key][f.key] = raw;
      }
    }
  }
  current = merged;
  applyToConfig();
}

/** Apply a partial patch (group → field → value); empty string clears a field. */
export async function updateIntegrations(patch: StoredSettings, updatedBy: string): Promise<void> {
  const stored = await readStored();
  for (const [groupKey, fields] of Object.entries(patch)) {
    const group = INTEGRATION_GROUPS.find((g) => g.key === groupKey);
    if (!group) continue;
    stored[groupKey] = stored[groupKey] ?? {};
    for (const [fieldKey, value] of Object.entries(fields)) {
      const f = group.fields.find((x) => x.key === fieldKey);
      if (!f) continue;
      if (value === "" || value === null || value === undefined) {
        delete stored[groupKey][fieldKey];
        continue;
      }
      stored[groupKey][fieldKey] = f.type === "secret" ? encryptSecret(String(value)) : value;
    }
  }
  await query(
    `INSERT INTO app_settings (key, value, updated_at, updated_by)
     VALUES ($1, $2, now(), $3)
     ON CONFLICT (key) DO UPDATE
       SET value = EXCLUDED.value, updated_at = now(), updated_by = EXCLUDED.updated_by`,
    [SETTINGS_KEY, JSON.stringify(stored), updatedBy],
  );
  await loadRuntimeSettings();
}

export interface MaskedField {
  key: string;
  label: string;
  type: FieldType;
  /** Secret fields always return ""; the UI shows a masked placeholder instead. */
  value: string | number | boolean;
  configured: boolean;
  help?: string;
}
export interface MaskedGroup {
  key: string;
  label: string;
  fields: MaskedField[];
}

/** UI-safe view: secrets are never returned, only their configured state. */
export function maskedIntegrations(): MaskedGroup[] {
  return INTEGRATION_GROUPS.map((group) => ({
    key: group.key,
    label: group.label,
    fields: group.fields.map((f) => {
      const value = current[group.key]?.[f.key];
      const configured = value !== undefined && value !== null && value !== "";
      if (f.type === "secret") {
        return { key: f.key, label: f.label, type: f.type, value: "", configured, help: f.help };
      }
      return { key: f.key, label: f.label, type: f.type, value: (value ?? f.def ?? "") as string | number | boolean, configured, help: f.help };
    }),
  }));
}
