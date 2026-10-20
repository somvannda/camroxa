import { query, queryOne } from "./db.js";

/**
 * Audience definition and its translation to SQL.
 *
 * Segments are evaluated at send time against the `user_value` view instead of
 * being frozen into a list, so "active in the last 7 days" is still true
 * tomorrow and a user who unsubscribes between preview and send is excluded.
 *
 * Two rules are enforced here rather than left to the operator:
 *   * marketing cooldown — nobody gets two marketing mails inside N days;
 *   * price integrity — anyone who paid full price in the last 14 days is
 *     excluded from discount mail, otherwise the next purchase waits for a sale.
 */
export interface Audience {
  lifecycle?: "active" | "warm" | "dormant" | null;
  spendTier?: "never" | "small" | "big" | null;
  language?: string | null;
  /** Exclude users who paid in the last 14 days (mandatory for discount mail). */
  excludeRecentPayers?: boolean;
  /** Override the marketing cooldown, in days. 0 disables the cap. */
  cooldownDays?: number;
}

export const LIFECYCLES = ["active", "warm", "dormant"] as const;
export const SPEND_TIERS = ["never", "small", "big"] as const;

/** Hard ceiling per send press; larger audiences should be sent in slices. */
export const MAX_CAMPAIGN_RECIPIENTS = 2000;

/** Normalize untrusted JSON (a campaign row, an admin payload) into an Audience. */
export function coerceAudience(value: unknown): Audience {
  const raw = (value ?? {}) as Record<string, unknown>;
  const lifecycle = LIFECYCLES.includes(raw.lifecycle as (typeof LIFECYCLES)[number])
    ? (raw.lifecycle as Audience["lifecycle"])
    : null;
  const spendTier = SPEND_TIERS.includes(raw.spendTier as (typeof SPEND_TIERS)[number])
    ? (raw.spendTier as Audience["spendTier"])
    : null;
  const language =
    typeof raw.language === "string" && /^[a-z]{2}(-[A-Z]{2})?$/.test(raw.language)
      ? raw.language
      : null;
  return {
    lifecycle,
    spendTier,
    language,
    excludeRecentPayers: raw.excludeRecentPayers === true,
    cooldownDays:
      typeof raw.cooldownDays === "number" && Number.isFinite(raw.cooldownDays)
        ? Math.max(0, Math.floor(raw.cooldownDays))
        : undefined,
  };
}

/**
 * Build the WHERE clause over `user_value v`. Values are always parameterized;
 * only enum membership is checked above, never string-concatenated into SQL.
 */
export function audienceWhere(
  audience: Audience,
  defaultCooldownDays: number,
): { where: string; params: unknown[] } {
  const params: unknown[] = [];
  const clauses: string[] = [
    "v.status = 'active'",
    "v.role = 'user'",
    "v.email_subscription = true",
    "v.suppressed = false",
  ];

  if (audience.lifecycle) {
    params.push(audience.lifecycle);
    clauses.push(`v.lifecycle = $${params.length}`);
  }
  if (audience.spendTier) {
    params.push(audience.spendTier);
    clauses.push(`v.spend_tier = $${params.length}`);
  }
  if (audience.language) {
    params.push(audience.language);
    clauses.push(`v.language = $${params.length}`);
  }

  const cooldown = audience.cooldownDays ?? defaultCooldownDays;
  if (cooldown > 0) {
    params.push(cooldown);
    clauses.push(
      `NOT EXISTS (
         SELECT 1 FROM mail_sends s
         WHERE s.user_id = v.user_id
           AND s.kind IN ('campaign', 'automation')
           AND s.status NOT IN ('failed', 'skipped', 'suppressed')
           AND s.created_at > now() - ($${params.length}::int * interval '1 day')
       )`,
    );
  }

  if (audience.excludeRecentPayers) {
    clauses.push(
      `NOT EXISTS (
         SELECT 1 FROM payment_transactions p
         WHERE p.user_id = v.user_id
           AND p.status = 'paid'
           AND p.paid_at > now() - interval '14 days'
       )`,
    );
  }

  return { where: clauses.join(" AND "), params };
}

export async function audienceCount(
  audience: Audience,
  defaultCooldownDays: number,
): Promise<number> {
  const { where, params } = audienceWhere(audience, defaultCooldownDays);
  const row = await queryOne<{ n: string }>(
    `SELECT COUNT(*)::text AS n FROM user_value v WHERE ${where}`,
    params,
  );
  return Number(row?.n ?? 0);
}

export interface Recipient {
  user_id: string;
  email: string;
}

/** Most recently active first, so the first slice is the warmest audience. */
export async function audienceRecipients(
  audience: Audience,
  defaultCooldownDays: number,
  limit: number = MAX_CAMPAIGN_RECIPIENTS,
): Promise<Recipient[]> {
  const { where, params } = audienceWhere(audience, defaultCooldownDays);
  params.push(limit);
  return query<Recipient>(
    `SELECT v.user_id, v.email
     FROM user_value v
     WHERE ${where}
     ORDER BY v.last_seen_at DESC NULLS LAST
     LIMIT $${params.length}`,
    params,
  );
}

/**
 * The nine-cell matrix from the mailing strategy, as ready-made segments.
 * "Active + never paid" is first because it is the highest-converting email.
 */
export const SEGMENT_PRESETS: Array<{ key: string; label: string; audience: Audience }> = [
  { key: "active-never", label: "Active, never paid", audience: { lifecycle: "active", spendTier: "never" } },
  { key: "active-small", label: "Active, small payer", audience: { lifecycle: "active", spendTier: "small" } },
  { key: "active-big", label: "Active, big payer", audience: { lifecycle: "active", spendTier: "big" } },
  { key: "warm-never", label: "Warm, never paid", audience: { lifecycle: "warm", spendTier: "never" } },
  { key: "warm-small", label: "Warm, small payer", audience: { lifecycle: "warm", spendTier: "small" } },
  { key: "warm-big", label: "Warm, big payer", audience: { lifecycle: "warm", spendTier: "big" } },
  { key: "dormant-never", label: "Dormant, never paid", audience: { lifecycle: "dormant", spendTier: "never" } },
  { key: "dormant-small", label: "Dormant, small payer", audience: { lifecycle: "dormant", spendTier: "small" } },
  { key: "dormant-big", label: "Dormant, big payer", audience: { lifecycle: "dormant", spendTier: "big" } },
];
