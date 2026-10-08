import { readFileSync } from "node:fs";
import { SunoClient, AccountCreds, BillingInfo } from "./client.js";
import { config } from "./config.js";
import { decryptCookie, encryptCookie } from "./cookieCrypto.js";
import { query } from "./db.js";
import { normalizeModel } from "./models.js";

export type RoutingPolicy = "prefer_free" | "paid_only" | "any";

export interface AccountHealth {
  credits: number;
  models: string[];
  plan: string;
  /** `billing/info.accessible_features` names (e.g. "studio", "persona"). */
  features: string[];
  /**
   * The raw Suno model entries (usable ones only) that `models` was derived
   * from. Kept so the catalog endpoint can report names/versions without a
   * second `billing/info` round-trip.
   */
  catalog: BillingModel[];
}

type BillingModel = NonNullable<BillingInfo["models"]>[number];

/** One selectable model version, aggregated across healthy accounts. */
export interface ModelInfo {
  key: string;
  name: string;
  major_version: number | null;
  description: string | null;
  is_default: boolean;
}

export interface AccountStatus {
  id: string;
  plan: string;
  credits: number;
  models: string[];
  captchaRequired: boolean;
}

/**
 * Order eligible clients for fair dispatch: routing preference first (free
 * before paid for `prefer_free`), then accounts still below `maxPerAccount`,
 * then least in-flight. Least-loaded-first means a burst spreads across the
 * pool instead of hammering whichever account happens to be first — with a
 * global cap of `size × K`, no account ends up with more than `K` in flight.
 * Pure and exported so it can be unit-tested without a live pool.
 */
export function orderByLoad<T extends { account: { id: string; type?: string } }>(
  clients: T[],
  load: (id: string) => number,
  opts: { preferFree?: boolean; maxPerAccount?: number } = {},
): T[] {
  const rank = (c: T): [number, number, number] => [
    opts.preferFree && c.account.type === "paid" ? 1 : 0,
    opts.maxPerAccount != null && load(c.account.id) >= opts.maxPerAccount ? 1 : 0,
    load(c.account.id),
  ];
  return [...clients].sort((a, b) => {
    const ra = rank(a);
    const rb = rank(b);
    return ra[0] - rb[0] || ra[1] - rb[1] || ra[2] - rb[2];
  });
}

/**
 * Whether an account's credit balance is too low to accept new work. Suno
 * reports a positive balance right up until zero, so an account with a couple of
 * credits looks "healthy" and gets picked — then the submission is rejected with
 * 402 "not enough credits". `floor` defaults to `config.suno.minCredits`
 * (`SUNO_MIN_CREDITS`, default 10); clamping it to at least 1 keeps the historic
 * rule that an exactly-empty account is never selected. Pure and exported so it
 * can be unit-tested without a live pool.
 */
export function belowCreditFloor(
  credits: number,
  floor: number = config.suno.minCredits,
): boolean {
  return credits < Math.max(1, floor);
}

export class AccountPool {
  private clients: SunoClient[] = [];
  private health: Map<string, { info: AccountHealth; updatedAt: number }> = new Map();
  private captcha: Map<string, { required: boolean; updatedAt: number }> = new Map();

  constructor(accounts: AccountCreds[] = []) {
    this.clients = accounts.map((a) => this.makeClient(a));
  }

  /** Build a client and attach cookie-rotation persistence for this account. */
  private makeClient(a: AccountCreds): SunoClient {
    a.persistCookie = (cookie: string) => {
      void query("UPDATE suno_accounts SET client_cookie = $1 WHERE label = $2", [
        encryptCookie(cookie),
        a.id,
      ]).catch(() => {
        /* best-effort: a failed write just loses one rotation */
      });
    };
    return new SunoClient(a);
  }

  get size(): number {
    return this.clients.length;
  }

  list(): string[] {
    return this.clients.map((c) => c.account.id);
  }

  /** Best-effort live health for every account (cached per account). */
  async listHealth(): Promise<AccountStatus[]> {
    return Promise.all(
      this.clients.map(async (c) => {
        try {
          const h = await this.healthFor(c);
          const captchaRequired = await this.captchaFor(c);
          return { id: c.account.id, plan: h.plan, credits: h.credits, models: h.models, captchaRequired };
        } catch {
          return { id: c.account.id, plan: "unknown", credits: 0, models: [], captchaRequired: false };
        }
      }),
    );
  }

  /**
   * The model versions this pool can actually generate with right now: the
   * union of every reachable, funded account's usable Suno models, default
   * first, then newest major version. Unreachable accounts contribute nothing
   * (so an expired cookie cannot blank out the catalog).
   */
  async listModels(): Promise<ModelInfo[]> {
    const byKey = new Map<string, ModelInfo>();
    for (const client of this.clients) {
      let health: AccountHealth;
      try {
        health = await this.healthFor(client);
      } catch {
        continue;
      }
      if (health.credits <= 0) continue;
      for (const m of health.catalog) {
        const key = m.external_key;
        if (!key) continue;
        const isDefault = Boolean(m.is_default_model || m.is_default_free_model);
        const existing = byKey.get(key);
        if (existing) {
          if (isDefault) existing.is_default = true;
          continue;
        }
        byKey.set(key, {
          key,
          name: m.name ?? key,
          major_version: m.major_version ?? null,
          description: m.description ?? null,
          is_default: isDefault,
        });
      }
    }
    return [...byKey.values()].sort((a, b) => {
      if (a.is_default !== b.is_default) return a.is_default ? -1 : 1;
      if ((b.major_version ?? 0) !== (a.major_version ?? 0)) {
        return (b.major_version ?? 0) - (a.major_version ?? 0);
      }
      return a.name.localeCompare(b.name);
    });
  }

  /** Load accounts from a JSON file (array of {id, clientCookie, deviceId}). */
  static fromJsonFile(path: string): AccountPool {
    const raw = readFileSync(path, "utf8");
    const accounts = JSON.parse(raw) as AccountCreds[];
    return new AccountPool(accounts);
  }

  /** Read the active account credentials from the `suno_accounts` table. */
  private static async loadCreds(): Promise<AccountCreds[]> {
    const rows = await query<{
      label: string;
      type: string;
      client_cookie: string;
      device_id: string;
    }>(
      "SELECT label, type, client_cookie, device_id FROM suno_accounts WHERE is_active = true ORDER BY created_at",
    );
    return rows.map((r) => ({
      id: r.label,
      clientCookie: decryptCookie(r.client_cookie),
      deviceId: r.device_id,
      type: r.type === "paid" ? "paid" : "free",
    }));
  }

  /**
   * Re-read the active accounts from the DB into this instance. Called after an
   * admin edits/adds/removes an account so routing picks up the change without a
   * process restart. In-flight jobs keep their already-acquired client.
   */
  async reload(): Promise<void> {
    const accounts = await AccountPool.loadCreds();
    this.clients = accounts.map((a) => this.makeClient(a));
    this.health.clear();
    this.captcha.clear();
    this.rateLimitedUntil.clear();
  }

  /**
   * Best-effort renewal of every account's session. For `__client`-backed
   * accounts this mints a fresh JWT (and persists any rotated cookie); for
   * JWT-seeded accounts it is a no-op. Called by the keep-alive loop so long
   * idle periods don't let a session lapse.
   */
  async refreshSessions(): Promise<void> {
    await Promise.allSettled(this.clients.map((c) => c.refreshJwt()));
  }

  /** Load accounts from the `suno_accounts` table (single source of truth). */
  static async fromDb(): Promise<AccountPool> {
    return new AccountPool(await AccountPool.loadCreds());
  }

  private async healthFor(client: SunoClient, ttlMs = 30_000): Promise<AccountHealth> {
    const cached = this.health.get(client.account.id);
    if (cached && Date.now() - cached.updatedAt < ttlMs) return cached.info;
    const info = await client.billingInfo();
    const subType = info.subscription_type;
    const usable = (info.models ?? []).filter((m) => m.can_use);
    const health: AccountHealth = {
      credits: info.total_credits_left ?? 0,
      models: usable.map((m) => m.external_key ?? "").filter(Boolean),
      plan: typeof subType === "string" ? subType : subType ? "paid" : "free",
      features: (info.accessible_features ?? []).map((f) => f.name ?? "").filter(Boolean),
      catalog: usable,
    };
    this.health.set(client.account.id, { info: health, updatedAt: Date.now() });
    return health;
  }

  /**
   * Mark an account as just-out-of-credits after a 402. Sets its cached health
   * to zero so `belowCreditFloor` skips it until the cache expires and the next
   * `billing/info` refresh runs. Without this a drained account keeps looking
   * funded for up to the health TTL and every job in that window fails with 402.
   */
  markCreditExhausted(id: string): void {
    const client = this.clients.find((c) => c.account.id === id);
    if (!client) return;
    const existing = this.health.get(id)?.info;
    const info: AccountHealth = existing
      ? { ...existing, credits: 0 }
      : { credits: 0, models: [], plan: "unknown", features: [], catalog: [] };
    this.health.set(id, { info, updatedAt: Date.now() });
  }

  /** Accounts a 429 put on a short cooldown (epoch ms until they may be picked). */
  private readonly rateLimitedUntil = new Map<string, number>();

  /** Put an account on a short cooldown after a 429 so it isn't re-picked immediately. */
  markRateLimited(id: string, cooldownMs: number): void {
    if (cooldownMs <= 0) return;
    this.rateLimitedUntil.set(id, Date.now() + cooldownMs);
  }

  /**
   * Move accounts currently in a 429 cooldown to the end so a warm account is
   * preferred; when every candidate is cooling they are still tried (a brief
   * pause beats failing outright).
   */
  private prioritizeCooling(clients: SunoClient[]): SunoClient[] {
    const now = Date.now();
    const warm: SunoClient[] = [];
    const cooling: SunoClient[] = [];
    for (const c of clients) {
      const until = this.rateLimitedUntil.get(c.account.id);
      if (until && until > now) cooling.push(c);
      else {
        if (until) this.rateLimitedUntil.delete(c.account.id);
        warm.push(c);
      }
    }
    return cooling.length ? [...warm, ...cooling] : clients;
  }

  /**
   * Best-effort per-account captcha status, cached for a minute. Never throws:
   * a probe failure falls back to the last known value (or `false`).
   */
  private async captchaFor(client: SunoClient, ttlMs = 60_000): Promise<boolean> {
    const cached = this.captcha.get(client.account.id);
    if (cached && Date.now() - cached.updatedAt < ttlMs) return cached.required;
    try {
      const required = await client.captchaRequired();
      this.captcha.set(client.account.id, { required, updatedAt: Date.now() });
      return required;
    } catch {
      return cached?.required ?? false;
    }
  }

  /**
   * Pick a healthy account that can use `model`, has credits, and matches the
   * routing `policy` (prefer_free / paid_only / any).
   */
  async pick(
    model?: string,
    policy: RoutingPolicy = "any",
    opts: { load?: (id: string) => number; maxPerAccount?: number } = {},
  ): Promise<SunoClient> {
    if (this.clients.length === 0) throw new Error("No Suno accounts configured.");
    // Retired keys are folded onto the current model first, so an old client's
    // request still matches the account catalog instead of falling through.
    const want = normalizeModel(model);
    const filtered = this.clients.filter((c) => {
      if (policy === "paid_only") return (c.account.type ?? "free") === "paid";
      return true;
    });
    if (filtered.length === 0 && policy === "paid_only") {
      throw new Error(
        "No paid Suno account is available for this model; premium models require a paid account.",
      );
    }
    const ordered = orderByLoad(filtered, opts.load ?? (() => 0), {
      preferFree: policy === "prefer_free",
      maxPerAccount: opts.maxPerAccount,
    });
    let lastError = "No healthy account available.";
    let fallback: SunoClient | null = null;
    let sawLowCredits = false;
    for (const client of this.prioritizeCooling(ordered)) {
      try {
        const health = await this.healthFor(client);
        if (belowCreditFloor(health.credits)) {
          sawLowCredits = true;
          continue;
        }
        if (want && health.models.length && !health.models.includes(want)) {
          // Suno isn't advertising this model for the account — but a key it
          // won't advertise may still be accepted, so keep the account as a
          // last resort rather than failing with "no healthy account".
          fallback ??= client;
          continue;
        }
        return client;
      } catch (e) {
        lastError = e instanceof Error ? e.message : String(e);
      }
    }
    if (fallback) return fallback;
    if (sawLowCredits) {
      throw new Error("No Suno account with available credits for this model.");
    }
    throw new Error(lastError);
  }

  /**
   * Pick a healthy account that advertises a capability, falling back to the
   * generic pick when none does. Used for features only some plans have — e.g.
   * custom Voice needs a Premier account (`studio`).
   */
  async pickFeature(
    feature: string,
    model?: string,
    policy: RoutingPolicy = "any",
    opts: { load?: (id: string) => number; maxPerAccount?: number } = {},
  ): Promise<SunoClient> {
    const want = normalizeModel(model);
    const ordered = orderByLoad(this.clients, opts.load ?? (() => 0), {
      preferFree: policy === "prefer_free",
      maxPerAccount: opts.maxPerAccount,
    });
    for (const client of this.prioritizeCooling(ordered)) {
      if (policy === "paid_only" && (client.account.type ?? "free") !== "paid") continue;
      try {
        const health = await this.healthFor(client);
        if (belowCreditFloor(health.credits) || !health.features.includes(feature)) continue;
        if (want && health.models.length && !health.models.includes(want)) continue;
        return client;
      } catch {
        /* try the next account */
      }
    }
    return this.pick(model, policy, opts);
  }

  /** Feature-aware `pickExcept` for retries across accounts. */
  async pickFeatureExcept(
    feature: string,
    excludeIds: string[],
    model?: string,
    policy: RoutingPolicy = "any",
    opts: { load?: (id: string) => number; maxPerAccount?: number } = {},
  ): Promise<SunoClient> {
    const exclude = new Set(excludeIds);
    const want = normalizeModel(model);
    const ordered = orderByLoad(
      this.clients.filter((c) => !exclude.has(c.account.id)),
      opts.load ?? (() => 0),
      { preferFree: policy === "prefer_free", maxPerAccount: opts.maxPerAccount },
    );
    for (const client of this.prioritizeCooling(ordered)) {
      if (policy === "paid_only" && (client.account.type ?? "free") !== "paid") continue;
      try {
        const health = await this.healthFor(client);
        if (belowCreditFloor(health.credits) || !health.features.includes(feature)) continue;
        if (want && health.models.length && !health.models.includes(want)) continue;
        return client;
      } catch {
        /* try the next account */
      }
    }
    return this.pickExcept(excludeIds, model, policy, opts);
  }

  /** Return the client for a specific account id, or null when not pooled. */
  get(accountId: string): SunoClient | null {
    return this.clients.find((c) => c.account.id === accountId) ?? null;
  }

  /**
   * Like pick() but skips clients whose account id is in excludeIds.
   * Throws if no candidates remain after filtering.
   */
  async pickExcept(
    excludeIds: string[],
    model?: string,
    policy: RoutingPolicy = "any",
    opts: { load?: (id: string) => number; maxPerAccount?: number } = {},
  ): Promise<SunoClient> {
    if (this.clients.length === 0) throw new Error("No Suno accounts configured.");
    const want = normalizeModel(model);
    const exclude = new Set(excludeIds);
    const filtered = this.clients.filter((c) => {
      if (exclude.has(c.account.id)) return false;
      if (policy === "paid_only") return (c.account.type ?? "free") === "paid";
      return true;
    });
    if (filtered.length === 0) {
      const anyPaid = this.clients.some((c) => (c.account.type ?? "free") === "paid");
      if (policy === "paid_only" && !anyPaid) {
        throw new Error(
          "No paid Suno account is available for this model; premium models require a paid account.",
        );
      }
      throw new Error("No Suno accounts available after excluding attempted ones.");
    }
    const ordered = orderByLoad(filtered, opts.load ?? (() => 0), {
      preferFree: policy === "prefer_free",
      maxPerAccount: opts.maxPerAccount,
    });
    let lastError = "No healthy account available.";
    let fallback: SunoClient | null = null;
    let sawLowCredits = false;
    for (const client of this.prioritizeCooling(ordered)) {
      try {
        const health = await this.healthFor(client);
        if (belowCreditFloor(health.credits)) {
          sawLowCredits = true;
          continue;
        }
        if (want && health.models.length && !health.models.includes(want)) {
          // See pick(): an unlisted model is attempted with a healthy account
          // rather than filtered out, so a key Suno accepts but doesn't
          // advertise still works.
          fallback ??= client;
          continue;
        }
        return client;
      } catch (e) {
        lastError = e instanceof Error ? e.message : String(e);
      }
    }
    if (fallback) return fallback;
    if (sawLowCredits) {
      throw new Error("No Suno account with available credits for this model.");
    }
    throw new Error(lastError);
  }
}
