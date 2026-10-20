import { config } from "./config.js";
import { query } from "./db.js";
import { mailConfigured, mailVarsForUser, packLadderVars, queueMail } from "./mail.js";
import { audienceWhere, coerceAudience, type Audience, type Recipient } from "./mailSegments.js";

/**
 * State-triggered mail (welcome, no-first-generation, low balance, win-back).
 *
 * An automation is "when the user looks like X, send template Y, at most once
 * per cooldown window". Two guards stack:
 *   * the shared marketing cooldown from `audienceWhere` (never two marketing
 *     mails in a week, whatever combination of campaign and automation);
 *   * the automation's own `cooldown_days`, which is what makes repeatable
 *     journeys like win-back repeatable and one-shots stay one-shot.
 *
 * A deterministic `dedupe_key` per (automation, user, cooldown bucket) makes a
 * double run of the loop harmless: the second insert conflicts and is dropped.
 */

export type TriggerKey = "welcome" | "no_first_generation" | "low_balance" | "inactive";

export interface TriggerDef {
  key: TriggerKey;
  label: string;
  description: string;
  /** What `triggerValue` means for this trigger, if anything. */
  paramLabel?: string;
  defaultParam?: number;
  /** Sensible cooldown: one-shots get a decade, journeys get 30 days. */
  defaultCooldownDays: number;
}

export const TRIGGERS: TriggerDef[] = [
  {
    key: "welcome",
    label: "Welcome",
    description: "Signed up at least N minutes ago and has not received this automation yet.",
    paramLabel: "Minutes after signup",
    defaultParam: 30,
    defaultCooldownDays: 3650,
  },
  {
    key: "no_first_generation",
    label: "Signed up, never generated",
    description:
      "Account is older than N minutes and has zero music generations. The highest-intent free-user email you can send.",
    paramLabel: "Minutes after signup",
    defaultParam: 60 * 24 * 3,
    defaultCooldownDays: 3650,
  },
  {
    key: "low_balance",
    label: "Low credit balance",
    description:
      "Pooled credits fell below the user's own alert threshold (Settings), or N when they set none. Applies only to users who have bought credits.",
    paramLabel: "Fallback credit threshold",
    defaultParam: 50,
    defaultCooldownDays: 7,
  },
  {
    key: "inactive",
    label: "Inactive",
    description: "Last seen more than N days ago.",
    paramLabel: "Days inactive",
    defaultParam: 30,
    defaultCooldownDays: 30,
  },
];

const TRIGGER_KEYS = new Set<string>(TRIGGERS.map((t) => t.key));

export function coerceTrigger(value: unknown): TriggerKey {
  return typeof value === "string" && TRIGGER_KEYS.has(value) ? (value as TriggerKey) : "welcome";
}

export function triggerDef(key: string): TriggerDef | undefined {
  return TRIGGERS.find((t) => t.key === key);
}

export interface AutomationRow {
  id: string;
  key: string;
  name: string;
  template_id: string;
  trigger: string;
  audience: unknown;
  delay_minutes: number;
  cooldown_days: number;
  /** Optional per-trigger parameter stored inside `audience`. */
  trigger_value?: number | null;
  is_active: boolean;
  last_run_at: string | null;
  subject: string;
  html: string;
  text: string | null;
}

/** `triggerValue` rides inside the audience document to avoid a migration. */
export function triggerValueOf(audience: unknown): number | null {
  const raw = (audience ?? {}) as Record<string, unknown>;
  const value = raw.triggerValue;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function bucketKey(automationId: string, userId: string, cooldownDays: number): string {
  const bucket = Math.floor(Date.now() / Math.max(1, cooldownDays) / 86_400_000);
  return `automation:${automationId}:${userId}:${bucket}`;
}

/**
 * Build the eligibility query. The audience clause is reused verbatim so an
 * automation inherits consent, suppression and the shared cooldown for free.
 */
function eligibility(
  automation: AutomationRow,
  limit: number,
): { sql: string; params: unknown[] } {
  const audience: Audience = coerceAudience(automation.audience);
  const { where, params } = audienceWhere(audience, config.mail.marketingCooldownDays);

  const def = triggerDef(automation.trigger);
  const paramValue =
    triggerValueOf(automation.audience) ?? def?.defaultParam ?? automation.delay_minutes ?? 0;

  const triggerClauses: string[] = [];
  switch (automation.trigger) {
    case "welcome":
      params.push(paramValue);
      triggerClauses.push(`u.created_at <= now() - ($${params.length}::int * interval '1 minute')`);
      break;
    case "no_first_generation":
      params.push(paramValue);
      triggerClauses.push(`u.created_at <= now() - ($${params.length}::int * interval '1 minute')`);
      triggerClauses.push(
        `NOT EXISTS (SELECT 1 FROM usage_logs l WHERE l.user_id = u.id AND l.endpoint = 'music')`,
      );
      break;
    case "low_balance":
      params.push(paramValue);
      triggerClauses.push(
        `COALESCE((SELECT SUM(k.credits) FROM api_keys k
                   WHERE k.user_id = u.id AND k.is_active), 0)
         < COALESCE((SELECT MAX(t) FROM unnest(u.credit_alert_thresholds) AS t), $${params.length})`,
      );
      // Never "alert" a user who has never had credits: that is a campaign, not
      // an account notice, and a 0 balance is not news to a free user.
      triggerClauses.push(
        `EXISTS (SELECT 1 FROM payment_transactions p
                 WHERE p.user_id = u.id AND p.status = 'paid')`,
      );
      break;
    case "inactive":
      params.push(paramValue);
      triggerClauses.push(
        `v.last_seen_at <= now() - ($${params.length}::int * interval '1 day')`,
      );
      break;
    default:
      triggerClauses.push("false");
  }

  // The automation's own cooldown, on top of the shared marketing one.
  params.push(automation.id, Math.max(1, automation.cooldown_days));
  triggerClauses.push(
    `NOT EXISTS (
       SELECT 1 FROM mail_sends s
       WHERE s.user_id = u.id
         AND s.automation_id = $${params.length - 1}
         AND s.status NOT IN ('failed', 'skipped', 'suppressed')
         AND s.created_at > now() - ($${params.length}::int * interval '1 day')
     )`,
  );

  params.push(limit);
  const sql = `
    SELECT v.user_id, v.email
    FROM user_value v
    JOIN users u ON u.id = v.user_id
    WHERE (${where})
      AND ${triggerClauses.map((c) => `(${c})`).join(" AND ")}
    ORDER BY v.last_seen_at DESC NULLS LAST
    LIMIT $${params.length}`;

  return { sql, params };
}

export async function eligibleRecipients(
  automation: AutomationRow,
  limit = 200,
): Promise<Recipient[]> {
  const { sql, params } = eligibility(automation, limit);
  return query<Recipient>(sql, params);
}

export async function automationAudienceCount(automation: AutomationRow): Promise<number> {
  const { sql, params } = eligibility(automation, 10_000);
  const rows = await query<Recipient>(sql, params);
  return rows.length;
}

async function loadAutomations(where = "a.is_active", params: unknown[] = []): Promise<AutomationRow[]> {
  return query<AutomationRow>(
    `SELECT a.id, a.key, a.name, a.template_id, a.trigger, a.audience, a.delay_minutes,
            a.cooldown_days, a.is_active, a.last_run_at,
            t.subject, t.html, t.text
     FROM mail_automations a
     JOIN mail_templates t ON t.id = a.template_id
     WHERE ${where}
     ORDER BY a.key`,
    params,
  );
}

async function deliverFor(automation: AutomationRow, limit: number): Promise<number> {
  const recipients = await eligibleRecipients(automation, limit);
  if (recipients.length === 0) {
    await query("UPDATE mail_automations SET last_run_at = now() WHERE id = $1", [automation.id]);
    return 0;
  }

  const ladder = await packLadderVars();
  let queued = 0;
  for (const recipient of recipients) {
    const vars = { ...(await mailVarsForUser(recipient.user_id)), ...ladder };
    const result = await queueMail({
      to: recipient.email,
      userId: recipient.user_id,
      kind: "automation",
      automationId: automation.id,
      templateId: automation.template_id,
      subject: automation.subject,
      html: automation.html,
      text: automation.text,
      vars,
      dedupeKey: bucketKey(automation.id, recipient.user_id, automation.cooldown_days),
    });
    if (result.outcome === "queued") queued += 1;
  }

  await query("UPDATE mail_automations SET last_run_at = now() WHERE id = $1", [automation.id]);
  return queued;
}

/** Run one automation now (admin "Run" button). Returns how many were queued. */
export async function runAutomation(id: string, limit = 200): Promise<number> {
  const rows = await loadAutomations("a.id = $1", [id]);
  if (!rows.length) return 0;
  return deliverFor(rows[0], limit);
}

/**
 * Evaluate every active automation. Called from the mail loop on a throttle, so
 * the cost is bounded even with many journeys configured.
 */
export async function runDueAutomations(limitPerAutomation = 200): Promise<number> {
  if (!mailConfigured()) return 0;
  const automations = await loadAutomations();
  let queued = 0;
  for (const automation of automations) {
    try {
      queued += await deliverFor(automation, limitPerAutomation);
    } catch {
      // One broken journey must not stop the others; the next tick retries.
    }
  }
  return queued;
}

/** Rows plus the current eligible count, for the console table. */
export async function listAutomations(): Promise<
  Array<AutomationRow & { eligible: number; cooldown_days: number }>
> {
  const rows = await loadAutomations("true");
  const withCounts = [];
  for (const row of rows) {
    withCounts.push({ ...row, eligible: await automationAudienceCount(row) });
  }
  return withCounts;
}
