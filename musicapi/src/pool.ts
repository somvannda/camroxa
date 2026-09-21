import { readFileSync } from "node:fs";
import { SunoClient, AccountCreds, BillingInfo } from "./client.js";
import { query } from "./db.js";

export type RoutingPolicy = "prefer_free" | "paid_only" | "any";

export interface AccountHealth {
  credits: number;
  models: string[];
  plan: string;
}

export class AccountPool {
  private clients: SunoClient[] = [];
  private health: Map<string, { info: AccountHealth; updatedAt: number }> = new Map();

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
  async listHealth(): Promise<Array<{ id: string; plan: string; credits: number; models: string[] }>> {
    return Promise.all(
      this.clients.map(async (c) => {
        try {
          const h = await this.healthFor(c);
          return { id: c.account.id, plan: h.plan, credits: h.credits, models: h.models };
        } catch {
          return { id: c.account.id, plan: "unknown", credits: 0, models: [] };
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

  /** Load accounts from the `suno_accounts` table (single source of truth). */
  static async fromDb(): Promise<AccountPool> {
    const rows = await query<{
      label: string;
      type: string;
      client_cookie: string;
      device_id: string;
    }>(
      "SELECT label, type, client_cookie, device_id FROM suno_accounts WHERE is_active = true ORDER BY created_at",
    );
    const accounts: AccountCreds[] = rows.map((r) => ({
      id: r.label,
      clientCookie: r.client_cookie,
      deviceId: r.device_id,
      type: r.type === "paid" ? "paid" : "free",
    }));
    return new AccountPool(accounts);
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
