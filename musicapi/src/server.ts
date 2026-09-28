import Fastify, { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { AccountPool, RoutingPolicy } from "./pool.js";
import { SunoClient } from "./client.js";
import { encryptCookie } from "./cookieCrypto.js";
import { query, queryOne, withTransaction, type QueryFn } from "./db.js";
import { hashPassword, verifyPassword, signToken, verifyToken, signOAuthState, verifyOAuthState, UserPayload } from "./appAuth.js";
import { OAuth2Client } from "google-auth-library";
import { config } from "./config.js";
import { assertCallbackUrlAllowed, CallbackUrlError } from "./callbackUrl.js";

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
}

export interface ServerDeps {
  pool: AccountPool;
}

export function loadApiKeys(path: string): ApiKey[] {
  return JSON.parse(readFileSync(path, "utf8")) as ApiKey[];
}

export function buildServer({ pool }: ServerDeps): FastifyInstance {
  const app = Fastify({
    logger: false,
    requestTimeout: 600_000,
    connectionTimeout: 600_000,
    keepAliveTimeout: 600_000,
  });
  const jobs = new Map<string, Job>();

  // Reject unsafe caller-supplied webhook targets before any handler runs, so a
  // bad callback_url can't later reach the internal network — or, on routes that
  // charge first, cost the caller credits before failing.
  app.addHook("preHandler", async (req, reply) => {
    const body = req.body as Record<string, unknown> | undefined;
    if (!body || typeof body !== "object") return;
    for (const field of ["callback_url", "callBackUrl"]) {
      const value = body[field];
      if (typeof value !== "string" || !value.trim()) continue;
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
    return key;
  }

  async function charge(key: DbApiKey, amount: number): Promise<boolean> {
    const effectiveTotalLimit =
      key.safe_spend_total ?? key.safe_spend_limit ?? null;

    if (effectiveTotalLimit != null) {
      const spent = await queryOne<{ sum: string }>(
        "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1",
        [key.id],
      );
      if (Number(spent?.sum ?? 0) + amount > effectiveTotalLimit) return false;
    }

    if (key.safe_spend_hourly != null) {
      const spent = await queryOne<{ sum: string }>(
        "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND created_at >= now() - interval '1 hour'",
        [key.id],
      );
      if (Number(spent?.sum ?? 0) + amount > key.safe_spend_hourly) return false;
    }

    if (key.safe_spend_daily != null) {
      const spent = await queryOne<{ sum: string }>(
        "SELECT COALESCE(sum(credits_consumed),0)::text AS sum FROM usage_logs WHERE api_key_id = $1 AND created_at >= now() - interval '1 day'",
        [key.id],
      );
      if (Number(spent?.sum ?? 0) + amount > key.safe_spend_daily) return false;
    }

    const rows = await query<{ credits: number }>(
      "UPDATE api_keys SET credits = credits - $1, last_used_at = now() WHERE id = $2 AND credits >= $1 RETURNING credits",
      [amount, key.id],
    );
    if (rows.length === 0) return false;
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
           AND (COALESCE(safe_spend_total, safe_spend_limit) IS NULL
                OR (SELECT COALESCE(sum(credits_consumed), 0) FROM usage_logs WHERE api_key_id = api_keys.id) + $2
                   <= COALESCE(safe_spend_total, safe_spend_limit))
           AND (safe_spend_hourly IS NULL
                OR (SELECT COALESCE(sum(credits_consumed), 0) FROM usage_logs
                    WHERE api_key_id = api_keys.id AND created_at >= now() - interval '1 hour') + $2 <= safe_spend_hourly)
           AND (safe_spend_daily IS NULL
                OR (SELECT COALESCE(sum(credits_consumed), 0) FROM usage_logs
                    WHERE api_key_id = api_keys.id AND created_at >= now() - interval '1 day') + $2 <= safe_spend_daily)
         ORDER BY created_at ASC
         LIMIT 1
       )
       UPDATE api_keys SET credits = credits - $2, last_used_at = now()
       WHERE id IN (SELECT id FROM candidate) AND credits >= $2
       RETURNING id, user_id, name, key_prefix, credits, safe_spend_limit, safe_spend_hourly, safe_spend_daily, safe_spend_total, ip_whitelist, is_active`,
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
    const auth = req.headers.authorization ?? "";
    const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    const user = token ? verifyToken(token) : null;
    if (!user) {
      reply.code(401).send({ error: "Unauthorized." });
      return null;
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

  // --- job persistence -----------------------------------------------------
  // Live job state lives in the in-memory `jobs` map for fast handler reads, but
  // every transition is mirrored to the `jobs` table so an in-flight job survives
  // a restart. On boot `recoverJobs()` fails out anything left pending/running.
  async function saveJob(job: Job): Promise<void> {
    await query(
      `INSERT INTO jobs
         (id, type, status, account_id, result_json, error, callback_url,
          user_id, api_key_id, endpoint, model, prompt, credits, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13, to_timestamp($14 / 1000.0), now())
       ON CONFLICT (id) DO UPDATE SET
         status = EXCLUDED.status,
         account_id = EXCLUDED.account_id,
         result_json = EXCLUDED.result_json,
         error = EXCLUDED.error,
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
    created_at: Date;
  }

  const JOB_COLUMNS =
    "id, type, status, account_id, result_json, error, callback_url, user_id, api_key_id, endpoint, model, prompt, credits, created_at";

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
      createdAt: new Date(row.created_at).getTime(),
    };
  }

  /** Read a job from the in-memory cache, falling back to the persisted row. */
  async function getJob(id: string): Promise<Job | null> {
    const cached = jobs.get(id);
    if (cached) return cached;
    const row = await queryOne<JobRow>(`SELECT ${JOB_COLUMNS} FROM jobs WHERE id = $1`, [id]);
    if (!row) return null;
    const job = rowToJob(row);
    jobs.set(job.id, job);
    return job;
  }

  /**
   * Fail out jobs that were still pending/running when the process stopped: the
   * in-memory worker that would have finished them is gone, so mark them errored
   * and finalize (usage log + callback) instead of leaving clients polling a job
   * the server no longer knows about.
   */
  async function recoverJobs(): Promise<void> {
    const rows = await query<JobRow>(
      `SELECT ${JOB_COLUMNS} FROM jobs WHERE status IN ('pending','running','streaming')`,
    );
    if (rows.length === 0) return;
    for (const row of rows) {
      const job = rowToJob(row);
      job.status = "error";
      job.error = "Interrupted by server restart.";
      jobs.set(job.id, job);
      await saveJob(job);
      await finalizeJob(job);
    }
    console.warn(`[jobs] recovered ${rows.length} interrupted job(s) as errors.`);
  }

  // Fail out interrupted jobs once the server is ready (after the DB is
  // reachable), before we start accepting requests.
  app.addHook("onReady", async () => {
    await recoverJobs();
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
      const key = await chargeUserKey(u.id, cost);
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    try {
      // Re-check at the sink as well: a public hostname accepted earlier can be
      // re-pointed at an internal address before the job finishes (DNS rebinding).
      await assertCallbackUrlAllowed(job.callbackUrl);
      await fetch(job.callbackUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        // Do not follow redirects — a 3xx to an internal address would otherwise
        // bypass the check above.
        redirect: "manual",
        body: JSON.stringify({
          job_id: job.id,
          type: job.type,
          status: job.status,
          account_id: job.accountId,
          result: job.result,
          error: job.error,
        }),
      });
    } catch {
      // callback failures are non-fatal
    }
  }

  // --- background workers --------------------------------------------------
  async function finalizeJob(job: Job): Promise<void> {
    await saveJob(job);
    if (job.userId && job.apiKeyId) {
      await recordUsage({
        userId: job.userId,
        apiKeyId: job.apiKeyId,
        endpoint: job.endpoint ?? job.type,
        model: job.model,
        prompt: job.prompt,
        status: job.status,
        credits: job.credits ?? 0,
        taskId: job.id,
        result: job.result,
      });
    }
    await notify(job);
  }

  const RETRYABLE_ERROR = /captcha|timeout|timed out|rate limit|5\d{2}|no healthy|No healthy/i;

  interface RetryOptions {
    model?: string;
    policy?: RoutingPolicy;
  }

  async function runClipJobWithRetry(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<import("./client.js").Clip[]>,
    options?: RetryOptions,
  ): Promise<void> {
    const excludeAttemptedIds: string[] = [];
    const maxAttempts = Math.min(3, pool.size);
    const errors: string[] = [];

    await saveJob(job);
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
      await saveJob(job);
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
  async function runResultJobWithRetry(
    job: Job,
    submitFactory: (client: SunoClient) => Promise<unknown>,
    options?: RetryOptions,
  ): Promise<void> {
    const excludeAttemptedIds: string[] = [];
    const maxAttempts = Math.min(3, pool.size);
    const errors: string[] = [];

    await saveJob(job);
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
      await saveJob(job);
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

  // --- auth routes ---------------------------------------------------------
  // Self-service registration disabled — Google sign-in is the only user onboarding path.
  // Admins are seeded directly into the `users` table via scripts/seed.ts or SQL.
  app.post("/auth/register", async (_req, reply) => {
    return reply.code(405).send({ error: "Self-registration is disabled. Please sign in with Google." });
  });

  // Email/password login is ADMIN-ONLY.
  // Non-admin users (created via Google sign-in) have password_hash=NULL and cannot use this route.
  // Defense-in-depth: even if a non-admin somehow had a password set, they are explicitly denied here.
  app.post("/auth/login", async (req, reply) => {
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
    return {
      token: signToken({ id: user.id, email: user.email, role: user.role }),
      user: { id: user.id, email: user.email, role: user.role, name: user.name },
    };
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
    const { client } = resolveGoogleClient(verifiedState.redirectUri);
    if (!client) {
      return reply.code(503).send({ error: "Google sign-in is not configured." });
    }
    try {
      const { tokens } = await client.getToken(code);
      const idToken = tokens.id_token;
      if (!idToken) return reply.code(400).send({ error: "Google did not return an id_token." });
      const ticket = await client.verifyIdToken({ idToken, audience: GOOGLE_CLIENT_ID });
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

      return reply.code(200).send({
        token: signToken({ id: user.id, email: user.email, role: user.role }),
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });

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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const pack = await queryOne<{ amount: string; price: string }>(
      "SELECT amount::text, price::text FROM credit_packs WHERE is_active = true ORDER BY amount LIMIT 1",
    );
    const creditsPerUsd = pack && Number(pack.amount) > 0 && Number(pack.price) > 0
      ? Number(pack.amount) / Number(pack.price)
      : 200;
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
      const cost = await costFor("download").catch(() => 0);
      const key = await chargeUserKey(u.id, cost);
      if (cost > 0 && !key) {
        return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
      const cost = await costFor(type);
      const key = await chargeUserKey(u.id, cost);
      if (!key) {
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
      const key = await chargeUserKey(u.id, cost);
      if (!key) {
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) return reply.code(402).send({ error: "Insufficient credits. Add credits to an API key first." });
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
    const key = await chargeUserKey(u.id, cost);
    if (!key) {
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
    const live = await pool.listHealth().catch(() => [] as Awaited<ReturnType<AccountPool["listHealth"]>>);
    const liveById = new Map(live.map((l) => [l.id, l]));
    const accounts = dbRows.map((row) => {
      const l = liveById.get(row.label);
      return {
        id: row.id,
        label: row.label,
        type: row.type,
        is_active: row.is_active,
        created_at: row.created_at,
        live_plan: l?.plan ?? row.plan ?? "unknown",
        live_credits: l?.credits ?? row.credits_left ?? 0,
        live_models: l?.models ?? [],
      };
    });
    return { accounts };
  });

  app.post("/admin/accounts", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { label, type, client_cookie, device_id } = (req.body ?? {}) as {
      label?: string;
      type?: string;
      client_cookie?: string;
      device_id?: string;
    };
    if (!label || !client_cookie || !device_id) {
      return reply.code(400).send({ error: "label, client_cookie and device_id are required." });
    }
    const t = type === "paid" ? "paid" : "free";
    const rows = await query<{ id: string }>(
      "INSERT INTO suno_accounts (label, type, client_cookie, device_id) VALUES ($1, $2, $3, $4) RETURNING id",
      [label, t, encryptCookie(client_cookie), device_id],
    );
    return reply.code(201).send({ id: rows[0].id });
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
    if (!(await requireAdmin(req, reply))) return;
    const { id } = req.params as { id: string };
    const { status } = (req.body ?? {}) as { status?: string };
    if (status !== "active" && status !== "suspended") {
      return reply.code(400).send({ error: "status must be active or suspended." });
    }
    await query("UPDATE users SET status = $1 WHERE id = $2", [status, id]);
    return { ok: true };
  });

  app.post("/admin/users/:id/credits", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
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
    // lose an update (the previous read-modify-write did).
    const updated = await queryOne<{ credits: number }>(
      "UPDATE api_keys SET credits = GREATEST(0, credits + $1) WHERE id = $2 RETURNING credits",
      [amount, key!.id],
    );
    await query(
      "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'adjust', $3)",
      [id, amount, "Admin credit adjustment"],
    );
    return { ok: true, credits: updated?.credits ?? key!.credits };
  });

  app.get("/admin/pricing", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      "SELECT id, endpoint, model, credit_cost FROM pricing ORDER BY endpoint, model NULLS LAST",
    );
  });

  app.post("/admin/pricing", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
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
      return { id: existing.id, updated: true };
    }
    const rows = await query<{ id: string }>(
      "INSERT INTO pricing (endpoint, model, credit_cost) VALUES ($1, $2, $3) RETURNING id",
      [endpoint, model ?? null, credit_cost],
    );
    return reply.code(201).send({ id: rows[0].id, updated: false });
  });

  app.delete("/admin/pricing/:id", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM pricing WHERE id = $1", [id]);
    return { ok: true };
  });

  app.get("/admin/routing", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    return query<Record<string, unknown>>(
      "SELECT id, model, policy FROM routing_rules ORDER BY model",
    );
  });

  app.post("/admin/routing", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { model, policy } = (req.body ?? {}) as { model?: string; policy?: string };
    if (!model || !policy) return reply.code(400).send({ error: "model and policy are required." });
    if (policy !== "prefer_free" && policy !== "paid_only" && policy !== "any") {
      return reply.code(400).send({ error: "policy must be prefer_free, paid_only, or any." });
    }
    const existing = await queryOne<{ id: string }>("SELECT id FROM routing_rules WHERE model = $1 LIMIT 1", [model]);
    if (existing) {
      await query("UPDATE routing_rules SET policy = $1 WHERE id = $2", [policy, existing.id]);
      return { id: existing.id, updated: true };
    }
    const rows = await query<{ id: string }>(
      "INSERT INTO routing_rules (model, policy) VALUES ($1, $2) RETURNING id",
      [model, policy],
    );
    return reply.code(201).send({ id: rows[0].id, updated: false });
  });

  app.delete("/admin/routing/:id", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM routing_rules WHERE id = $1", [id]);
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
    if (!(await requireAdmin(req, reply))) return;
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
    return reply.code(201).send({ id: rows[0].id });
  });

  app.put("/admin/content/:id", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
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
    return { ok: true };
  });

  app.delete("/admin/content/:id", async (req, reply) => {
    if (!(await requireAdmin(req, reply))) return;
    const { id } = req.params as { id: string };
    await query("DELETE FROM blog_posts WHERE id = $1", [id]);
    return { ok: true };
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
    const job = await getJob(id);
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
      const job = await getJob(id);
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
    q: QueryFn,
    user: UserPayload,
    amount: number,
    apiKeyId?: string,
    txId?: string,
  ): Promise<void> {
    if (apiKeyId) {
      await q(
        "UPDATE api_keys SET credits = credits + $1 WHERE id = $2 AND user_id = $3",
        [amount, apiKeyId, user.id],
      );
    } else {
      const keys = await q<{ id: string }>(
        "SELECT id FROM api_keys WHERE user_id = $1 AND is_active = true ORDER BY created_at ASC LIMIT 1",
        [user.id],
      );
      if (keys.length === 0) {
        await q(
          `INSERT INTO api_keys (user_id, name, key_hash, key_prefix, credits) VALUES ($1, $2, $3, $4, $5)`,
          [user.id, "Auto-Created Key", md5(randomUUID() + Date.now()), "auto_" + randomUUID().slice(0, 5), amount],
        );
      } else {
        await q(
          "UPDATE api_keys SET credits = credits + $1 WHERE id = $2",
          [amount, keys[0].id],
        );
      }
    }
    await q(
      `INSERT INTO credit_transactions (user_id, amount, type, description) VALUES ($1, $2, 'purchase', $3)`,
      [user.id, amount, txId ? `KHQR top-up (ref: ${txId})` : "KHQR top-up"],
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
      id: string; status: string; md5_hash: string | null; expires_at: string; credit_amount: number;
      api_key_target_id: string | null; error_message: string | null; paid_at: string | null;
      amount: string; currency: string; bill_number: string;
    }>(
      `SELECT id, status, md5_hash, expires_at, credit_amount, api_key_target_id, error_message, paid_at, amount, currency, bill_number
       FROM payment_transactions WHERE id = $1 AND user_id = $2`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });

    let currentStatus = tx.status;
    let paidAt = tx.paid_at;
    let errorMessage = tx.error_message;
    const expired = new Date(tx.expires_at).getTime() < Date.now();

    if (currentStatus === "pending") {
      if (expired) {
        await query("UPDATE payment_transactions SET status = 'expired' WHERE id = $1 AND status = 'pending'", [tx.id]);
        currentStatus = "expired";
      } else if (tx.md5_hash) {
        const bakongStatus = await khqrCheck(tx.md5_hash);
        if (bakongStatus === "PAID") {
          try {
            // Claim the pending transaction and apply the credits in one DB
            // transaction. The guarded UPDATE lets only the first poll claim it,
            // so concurrent polls credit exactly once; a rollback leaves it
            // 'pending' rather than half-credited.
            await withTransaction(async (tq) => {
              const claimed = await tq<{ id: string }>(
                "UPDATE payment_transactions SET status = 'paid', paid_at = now() WHERE id = $1 AND status = 'pending' RETURNING id",
                [tx.id],
              );
              if (claimed.length === 0) return;
              await creditUser(tq, u, tx.credit_amount, tx.api_key_target_id ?? undefined, tx.id);
            });
          } catch (e) {
            const err = e instanceof Error ? e.message : String(e);
            await query(
              "UPDATE payment_transactions SET status = 'failed', error_message = $1 WHERE id = $2 AND status = 'pending'",
              [err, tx.id],
            );
          }
          const fresh = await queryOne<{ status: string; paid_at: string | null; error_message: string | null }>(
            "SELECT status, paid_at, error_message FROM payment_transactions WHERE id = $1",
            [tx.id],
          );
          currentStatus = fresh?.status ?? tx.status;
          paidAt = fresh?.paid_at ?? paidAt;
          errorMessage = fresh?.error_message ?? errorMessage;
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
      paid_at: paidAt,
      expires_at: tx.expires_at,
      error: errorMessage,
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
      id: string; status: string; credit_amount: number; api_key_target_id: string | null;
    }>(
      `SELECT id, status, credit_amount, api_key_target_id FROM payment_transactions WHERE id = $1 AND user_id = $2`,
      [id, u.id],
    );
    if (!tx) return reply.code(404).send({ error: "Transaction not found." });
    if (tx.status !== "pending") return reply.code(409).send({ error: `Transaction already ${tx.status}.` });
    try {
      const credited = await withTransaction(async (tq) => {
        const claimed = await tq<{ id: string }>(
          "UPDATE payment_transactions SET status = 'paid', paid_at = now() WHERE id = $1 AND status = 'pending' RETURNING id",
          [tx.id],
        );
        if (claimed.length === 0) return false;
        await creditUser(tq, u, tx.credit_amount, tx.api_key_target_id ?? undefined, tx.id);
        return true;
      });
      if (!credited) return reply.code(409).send({ error: "Transaction already processed." });
      return { ok: true, status: "paid" };
    } catch (e) {
      return reply.code(500).send({ error: e instanceof Error ? e.message : String(e) });
    }
  });

  return app;
}
