import { readFileSync } from "node:fs";
import { SunoClient, AccountCreds, BillingInfo } from "./client.js";
import { config, CreditStrategy } from "./config.js";
import { decryptCookie, encryptCookie } from "./cookieCrypto.js";
import { query } from "./db.js";
import { normalizeModel } from "./models.js";

export type RoutingPolicy = "prefer_free" | "paid_only" | "any";

export interface AccountHealth {
  credits: number;
  models: string[];
  plan: string;
  /** ISO timestamp of the next subscription charge, or null for free plans. */
  renewsOn: string | null;
  /** Suno reports the paid subscription's payment as past due. */
  pastDue: boolean;
  /** The paid subscription is paused, so it will not renew or refresh credits. */
  paused: boolean;
  /** The subscription is scheduled to pause at the end of the current period. */
  pauseScheduled: boolean;
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

/**
 * Next subscription charge from a `billing/info` payload, normalised to ISO, or
 * null when the account is on a free plan / the payload has no usable date.
 *
 * `renews_on` is the documented-for-us field; `period_end` carries the same
 * instant on current plans and is kept as the fallback, so a rename on Suno's
 * side degrades to the other field instead of silently blanking the admin
 * console. Pure and exported so the parsing can be unit-tested without a pool.
 */
export function parseRenewsOn(
  info: Pick<BillingInfo, "renews_on" | "period_end">,
): string | null {
  for (const value of [info.renews_on, info.period_end]) {
    if (typeof value !== "string") continue;
    const trimmed = value.trim();
    if (!trimmed) continue;
    const ms = Date.parse(trimmed);
    if (Number.isFinite(ms)) return new Date(ms).toISOString();
  }
  return null;
}

/**
 * Whole days from `now` until an ISO timestamp, rounded up so "renews in six
 * hours" reads as 1 day instead of 0. Negative once the date has passed. Null
 * for a missing/unparseable timestamp. Pure and exported so the renewal-alert
 * window can be unit-tested without a live pool.
 */
export function daysUntilRenewal(
  renewsOn: string | null,
  now: number = Date.now(),
): number | null {
  if (!renewsOn) return null;
  const ms = Date.parse(renewsOn);
  return Number.isFinite(ms) ? Math.ceil((ms - now) / 86_400_000) : null;
}

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
  /** Next subscription charge from `billing/info`, null when free/unknown. */
  renewsOn: string | null;
  /** Suno reports the paid subscription's payment as past due. */
  pastDue: boolean;
  /** The paid subscription is paused (no renewal, no monthly refresh). */
  paused: boolean;
  /** The subscription is scheduled to pause at the end of the period. */
  pauseScheduled: boolean;
}

/**
 * Order eligible clients for dispatch. The ranking is, in order:
 *   1. `prefer_free` routing preference (free before paid when set);
 *   2. accounts still below `maxPerAccount` (an over-cap account is a last resort);
 *   3. credit balance, highest first — skipped entirely for `off`;
 *   4. least in-flight.
 *
 * The final tiebreak is what spreads a burst across the pool instead of
 * hammering whichever account happens to be first — with a global cap of
 * `size × K`, no account ends up with more than `K` in flight. The credit term
 * sits *above* load so a burst draws down the funded accounts rather than merely
 * equalising job counts (equal counts would preserve an existing balance gap).
 *
 * `credits` must already be the *effective* balance (live credits minus the
 * credits reserved by in-flight jobs). The strategy does not change this sort —
 * `balanced` and `max_first` order identically here; what separates them is
 * `AccountPool.reserveCredits`, which only `balanced` applies. Reserving makes
 * concurrent picks see the richest account's balance fall as it is used, so
 * dispatch converges on a common level; `max_first` reserves nothing and keeps
 * drawing from the single highest-balance account until a fresh read.
 *
 * Pure and exported so it can be unit-tested without a live pool.
 */
export function orderForDispatch<T extends { account: { id: string; type?: string } }>(
  clients: T[],
  opts: {
    load?: (id: string) => number;
    credits?: (id: string) => number;
    maxPerAccount?: number;
    preferFree?: boolean;
    strategy?: CreditStrategy;
  } = {},
): T[] {
  const load = opts.load ?? (() => 0);
  const credits = opts.credits ?? (() => 0);
  const creditAware = (opts.strategy ?? "off") !== "off";
  const rank = (c: T): [number, number, number, number] => [
    opts.preferFree && c.account.type === "paid" ? 1 : 0,
    opts.maxPerAccount != null && load(c.account.id) >= opts.maxPerAccount ? 1 : 0,
    creditAware ? -credits(c.account.id) : 0,
    load(c.account.id),
  ];
  return [...clients].sort((a, b) => {
    const ra = rank(a);
    const rb = rank(b);
    for (let i = 0; i < ra.length; i += 1) {
      if (ra[i] !== rb[i]) return ra[i] - rb[i];
    }
    return 0;
  });
}

/**
 * Legacy least-loaded-only ordering, kept as the `creditStrategy: "off"` case
 * and for callers that don't want credit awareness. Pure and exported for tests.
 */
export function orderByLoad<T extends { account: { id: string; type?: string } }>(
  clients: T[],
  load: (id: string) => number,
  opts: { preferFree?: boolean; maxPerAccount?: number } = {},
): T[] {
  return orderForDispatch(clients, { ...opts, load, strategy: "off" });
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
  /**
   * Effective live credits an in-flight job has consumed but the last
   * `billing/info` read has not yet reflected (the health cache lives 30s).
   * Subtracting this from a cached balance keeps concurrent picks from all
   * reading one snapshot and dogpiling the same account. Cleared whenever a
   * fresh `billing/info` arrives, because that value already includes the spend.
   */
  private readonly reservedCredits: Map<string, number> = new Map();

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
          return {
            id: c.account.id,
            plan: h.plan,
            credits: h.credits,
            models: h.models,
            captchaRequired,
            renewsOn: h.renewsOn,
            pastDue: h.pastDue,
            paused: h.paused,
            pauseScheduled: h.pauseScheduled,
          };
        } catch {
          return {
            id: c.account.id,
            plan: "unknown",
            credits: 0,
            models: [],
            captchaRequired: false,
            renewsOn: null,
            pastDue: false,
            paused: false,
            pauseScheduled: false,
          };
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
    this.reservedCredits.clear();
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
      renewsOn: parseRenewsOn(info),
      pastDue: info.is_past_due === true,
      paused: info.is_paused === true,
      pauseScheduled: info.is_pause_scheduled === true,
      features: (info.accessible_features ?? []).map((f) => f.name ?? "").filter(Boolean),
      catalog: usable,
    };
    this.health.set(client.account.id, { info: health, updatedAt: Date.now() });
    // The fresh balance already reflects every settled spend, so any outstanding
    // reservation for this account is now double-counting.
    this.reservedCredits.delete(client.account.id);
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
      : {
          credits: 0,
          models: [],
          plan: "unknown",
          renewsOn: null,
          pastDue: false,
          paused: false,
          pauseScheduled: false,
          features: [],
          catalog: [],
        };
    this.health.set(id, { info, updatedAt: Date.now() });
  }

  /**
   * Reserve `amount` credits against an account's cached balance while a job it
   * was picked for is in flight. This is what makes `balanced` dispatch converge:
   * without it every concurrent pick reads the same 30s snapshot and chooses the
   * same richest account, so `balanced` and `max_first` would behave alike.
   * Only the `balanced` strategy reserves; `off` ignores credits and `max_first`
   * deliberately keeps drawing from the highest-balance account. Over-counting is
   * safe — a fresh `billing/info` read clears the reservation.
   */
  reserveCredits(id: string, amount: number): void {
    if (config.suno.creditStrategy !== "balanced") return;
    if (!(amount > 0)) return;
    this.reservedCredits.set(id, (this.reservedCredits.get(id) ?? 0) + amount);
  }

  /** Release a reservation made by `reserveCredits` (e.g. when a job settles). */
  releaseCredits(id: string, amount: number): void {
    if (!(amount > 0)) return;
    const next = (this.reservedCredits.get(id) ?? 0) - amount;
    if (next > 0) this.reservedCredits.set(id, next);
    else this.reservedCredits.delete(id);
  }

  /** Cached credits minus the reservations still outstanding for this account. */
  private effectiveCredits(id: string, credits: number): number {
    return Math.max(0, credits - (this.reservedCredits.get(id) ?? 0));
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
   * Live health for every candidate, keyed by account id. A probe failure is
   * captured (not thrown) so one unreachable account cannot blank out routing:
   * the caller's scan still records the message and moves on, exactly as the
   * old inline `try/catch` did.
   */
  private async probeHealth(
    clients: SunoClient[],
  ): Promise<Map<string, { health: AccountHealth } | { error: string }>> {
    const entries = await Promise.all(
      clients.map(async (c): Promise<[string, { health: AccountHealth } | { error: string }]> => {
        try {
          return [c.account.id, { health: await this.healthFor(c) }];
        } catch (e) {
          return [c.account.id, { error: e instanceof Error ? e.message : String(e) }];
        }
      }),
    );
    return new Map(entries);
  }

  /**
   * Order candidates with the configured credit strategy, using a pre-fetched
   * health map. One place so the plain, exclude, and feature pick paths all
   * balance identically.
   */
  private orderCandidates(
    candidates: SunoClient[],
    healths: Map<string, { health: AccountHealth } | { error: string }>,
    policy: RoutingPolicy,
    opts: { load?: (id: string) => number; maxPerAccount?: number },
  ): SunoClient[] {
    return orderForDispatch(candidates, {
      load: opts.load ?? (() => 0),
      maxPerAccount: opts.maxPerAccount,
      preferFree: policy === "prefer_free",
      strategy: config.suno.creditStrategy,
      credits: (id) => {
        const probed = healths.get(id);
        return probed && "health" in probed ? this.effectiveCredits(id, probed.health.credits) : 0;
      },
    });
  }

  /**
   * Shared selection scan: order the candidates, then return the first that is
   * funded, advertises `model` (or is kept as a last-resort fallback when it
   * doesn't), and isn't cooling after a 429.
   */
  private async pickFrom(
    candidates: SunoClient[],
    model: string | undefined,
    policy: RoutingPolicy,
    opts: { load?: (id: string) => number; maxPerAccount?: number },
  ): Promise<SunoClient> {
    // Retired keys are folded onto the current model first, so an old client's
    // request still matches the account catalog instead of falling through.
    const want = normalizeModel(model);
    const healths = await this.probeHealth(candidates);
    const ordered = this.orderCandidates(candidates, healths, policy, opts);
    let lastError = "No healthy account available.";
    let fallback: SunoClient | null = null;
    let sawLowCredits = false;
    for (const client of this.prioritizeCooling(ordered)) {
      const probed = healths.get(client.account.id);
      if (!probed) continue;
      if ("error" in probed) {
        lastError = probed.error;
        continue;
      }
      const health = probed.health;
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
    }
    if (fallback) return fallback;
    if (sawLowCredits) {
      throw new Error("No Suno account with available credits for this model.");
    }
    throw new Error(lastError);
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
    const filtered = this.clients.filter((c) => {
      if (policy === "paid_only") return (c.account.type ?? "free") === "paid";
      return true;
    });
    if (filtered.length === 0 && policy === "paid_only") {
      throw new Error(
        "No paid Suno account is available for this model; premium models require a paid account.",
      );
    }
    return this.pickFrom(filtered, model, policy, opts);
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
    const candidates = this.clients.filter(
      (c) => policy !== "paid_only" || (c.account.type ?? "free") === "paid",
    );
    const healths = await this.probeHealth(candidates);
    const ordered = this.orderCandidates(candidates, healths, policy, opts);
    for (const client of this.prioritizeCooling(ordered)) {
      const probed = healths.get(client.account.id);
      if (!probed || "error" in probed) continue;
      const health = probed.health;
      if (belowCreditFloor(health.credits) || !health.features.includes(feature)) continue;
      if (want && health.models.length && !health.models.includes(want)) continue;
      return client;
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
    const candidates = this.clients.filter(
      (c) =>
        !exclude.has(c.account.id) &&
        (policy !== "paid_only" || (c.account.type ?? "free") === "paid"),
    );
    const healths = await this.probeHealth(candidates);
    const ordered = this.orderCandidates(candidates, healths, policy, opts);
    for (const client of this.prioritizeCooling(ordered)) {
      const probed = healths.get(client.account.id);
      if (!probed || "error" in probed) continue;
      const health = probed.health;
      if (belowCreditFloor(health.credits) || !health.features.includes(feature)) continue;
      if (want && health.models.length && !health.models.includes(want)) continue;
      return client;
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
    return this.pickFrom(filtered, model, policy, opts);
  }
}
