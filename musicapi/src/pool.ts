import { readFileSync } from "node:fs";
import { SunoClient, AccountCreds, BillingInfo } from "./client.js";
import { decryptCookie } from "./cookieCrypto.js";
import { query } from "./db.js";

export type RoutingPolicy = "prefer_free" | "paid_only" | "any";

export interface AccountHealth {
  credits: number;
  models: string[];
  plan: string;
}

export interface AccountStatus {
  id: string;
  plan: string;
  credits: number;
  models: string[];
  captchaRequired: boolean;
}

export class AccountPool {
  private clients: SunoClient[] = [];
  private health: Map<string, { info: AccountHealth; updatedAt: number }> = new Map();
  private captcha: Map<string, { required: boolean; updatedAt: number }> = new Map();

  constructor(accounts: AccountCreds[] = []) {
    this.clients = accounts.map((a) => new SunoClient(a));
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
    this.clients = accounts.map((a) => new SunoClient(a));
    this.health.clear();
    this.captcha.clear();
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
    const health: AccountHealth = {
      credits: info.total_credits_left ?? 0,
      models: (info.models ?? []).filter((m) => m.can_use).map((m) => m.external_key ?? ""),
      plan: typeof subType === "string" ? subType : subType ? "paid" : "free",
    };
    this.health.set(client.account.id, { info: health, updatedAt: Date.now() });
    return health;
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
  async pick(model?: string, policy: RoutingPolicy = "any"): Promise<SunoClient> {
    if (this.clients.length === 0) throw new Error("No Suno accounts configured.");
    const ordered = this.clients.filter((c) => {
      if (policy === "paid_only") return (c.account.type ?? "free") === "paid";
      return true;
    });
    if (policy === "prefer_free") {
      ordered.sort((a, b) => {
        const at = a.account.type === "paid" ? 1 : 0;
        const bt = b.account.type === "paid" ? 1 : 0;
        return at - bt;
      });
    }
    let lastError = "No healthy account available.";
    for (const client of ordered) {
      try {
        const health = await this.healthFor(client);
        if (health.credits <= 0) continue;
        if (model && health.models.length && !health.models.includes(model)) continue;
        return client;
      } catch (e) {
        lastError = e instanceof Error ? e.message : String(e);
      }
    }
    throw new Error(lastError);
  }

  /**
   * Like pick() but skips clients whose account id is in excludeIds.
   * Throws if no candidates remain after filtering.
   */
  async pickExcept(excludeIds: string[], model?: string, policy: RoutingPolicy = "any"): Promise<SunoClient> {
    if (this.clients.length === 0) throw new Error("No Suno accounts configured.");
    const exclude = new Set(excludeIds);
    const ordered = this.clients.filter((c) => {
      if (exclude.has(c.account.id)) return false;
      if (policy === "paid_only") return (c.account.type ?? "free") === "paid";
      return true;
    });
    if (ordered.length === 0) throw new Error("No Suno accounts available after excluding attempted ones.");
    if (policy === "prefer_free") {
      ordered.sort((a, b) => {
        const at = a.account.type === "paid" ? 1 : 0;
        const bt = b.account.type === "paid" ? 1 : 0;
        return at - bt;
      });
    }
    let lastError = "No healthy account available.";
    for (const client of ordered) {
      try {
        const health = await this.healthFor(client);
        if (health.credits <= 0) continue;
        if (model && health.models.length && !health.models.includes(model)) continue;
        return client;
      } catch (e) {
        lastError = e instanceof Error ? e.message : String(e);
      }
    }
    throw new Error(lastError);
  }
}
