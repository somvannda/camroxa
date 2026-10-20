import { createHmac, randomUUID } from "node:crypto";
import { config } from "./config.js";
import { query, queryOne } from "./db.js";
import {
  buildClickToken,
  buildOpenToken,
  buildUnsubToken,
  htmlToText,
  instrumentHtml,
  renderVars,
} from "./mailTracking.js";
import type { MailEventType } from "./resendWebhook.js";

/**
 * The single outbound-mail path.
 *
 * Every message is written to `mail_sends` before delivery, so the console can
 * show what was sent to whom and what happened next. Marketing is gated on
 * consent + the suppression list; transactional mail still honours suppression
 * (mailing a hard-bounced address damages the shared sending domain) but not
 * the marketing preference.
 *
 * Delivery state (`sent`/`delivered`/`bounced`) comes from Resend webhooks.
 * Engagement (`opened`/`clicked`) comes from our own signed pixel and redirect,
 * which is why those events are recorded here rather than mapped from webhooks.
 */

export const MAIL_KINDS = ["transactional", "campaign", "automation"] as const;
export type MailKind = (typeof MAIL_KINDS)[number];

export interface OutboundMail {
  to: string;
  /** Required for marketing mail; null for one-off tests. */
  userId?: string | null;
  kind: MailKind;
  subject: string;
  html: string;
  text?: string | null;
  templateId?: string | null;
  campaignId?: string | null;
  automationId?: string | null;
  /** Idempotency guard; a repeat with the same key is dropped. */
  dedupeKey?: string | null;
  /** Extracted from a template; always merged with app-wide variables. */
  vars?: Record<string, string | number | null | undefined>;
  replyTo?: string | null;
}

export type QueueOutcome = "queued" | "skipped" | "duplicate" | "suppressed";

export interface QueueResult {
  id: string | null;
  outcome: QueueOutcome;
  reason?: string;
}

interface MailRow {
  id: string;
  user_id: string | null;
  email: string;
  kind: MailKind;
  subject: string;
  html: string | null;
  text: string | null;
  attempts: number;
  campaign_id: string | null;
}

/** Domain-separated tracking key: HMAC of the JWT secret, never the secret itself. */
export function trackingSecret(): string {
  return createHmac("sha256", config.jwtSecret)
    .update("camxora-mail-tracking-v1")
    .digest("hex");
}

/** Public origin used in pixel, click and unsubscribe URLs. */
export function mailBaseUrl(): string {
  const configured = config.mail.publicBaseUrl;
  if (configured) return configured;
  const port = process.env.PORT ?? "4003";
  return `http://localhost:${port}`;
}

export function unsubscribeUrl(userId: string): string {
  return `${mailBaseUrl()}/mail/u/${buildUnsubToken(trackingSecret(), userId)}`;
}

export function openPixelUrl(sendId: string): string {
  return `${mailBaseUrl()}/mail/o/${buildOpenToken(trackingSecret(), sendId)}.gif`;
}

export function clickUrl(sendId: string, target: string): string {
  return `${mailBaseUrl()}/mail/c/${buildClickToken(trackingSecret(), sendId, target)}`;
}

/** Sending is possible only with a key and the master switch on. */
export function mailConfigured(): boolean {
  return Boolean(config.mail.apiKey) && config.mail.enabled;
}

export async function isSuppressed(email: string): Promise<boolean> {
  const row = await queryOne<{ email: string }>(
    "SELECT email FROM mail_suppressions WHERE email = lower($1)",
    [email],
  );
  return Boolean(row);
}

export async function addSuppression(
  email: string,
  reason: "bounce" | "complaint" | "unsubscribe" | "manual",
  source: string,
): Promise<void> {
  await query(
    `INSERT INTO mail_suppressions (email, reason, source)
     VALUES (lower($1), $2, $3)
     ON CONFLICT (email) DO UPDATE
       SET reason = EXCLUDED.reason, source = EXCLUDED.source`,
    [email, reason, source],
  );
}

export async function removeSuppression(email: string): Promise<void> {
  await query("DELETE FROM mail_suppressions WHERE email = lower($1)", [email]);
}

function appVariables(userId: string | null): Record<string, string> {
  const base = mailBaseUrl();
  return {
    // `app_url` is the product site; `mail_base_url` is this backend. Templates
    // must link the product, never the API host.
    app_url: config.mail.appUrl || base,
    mail_base_url: base,
    year: String(new Date().getFullYear()),
    unsubscribe_url: userId ? unsubscribeUrl(userId) : `${base}/mail/u/invalid`,
  };
}

/**
 * Record that a user was active, for the recency axis of segmentation.
 *
 * Throttled in SQL (`where last_active_at < now() - 1 hour`) rather than in
 * memory, so the write is skipped at the database and stays correct when the
 * API runs as several processes. Fire-and-forget: activity tracking must never
 * fail a request.
 */
export function touchUserActivity(userId: string): void {
  void query(
    `UPDATE users SET last_active_at = now()
     WHERE id = $1
       AND (last_active_at IS NULL OR last_active_at < now() - interval '1 hour')`,
    [userId],
  ).catch(() => undefined);
}

/** Append a compliant footer when a marketing template omits one. */
function ensureMarketingFooter(html: string, userId: string | null): string {
  if (!userId || html.includes("/mail/u/")) return html;
  const url = unsubscribeUrl(userId);
  const footer =
    `<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;` +
    `font-size:12px;line-height:1.5;color:#6b7280;text-align:center;">` +
    `You received this because you have a CAMXORA account. ` +
    `<a href="${url}" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>` +
    `</div>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, `${footer}</body>`) : html + footer;
}

/**
 * Render a template, instrument it, and persist a queued row.
 *
 * The row id is generated up front because the tracking URLs embed it: the
 * pixel/click tokens are only meaningful once the delivery row exists.
 */
export async function queueMail(mail: OutboundMail): Promise<QueueResult> {
  const to = mail.to.trim().toLowerCase();
  if (!to || !to.includes("@")) {
    return { id: null, outcome: "skipped", reason: "invalid recipient" };
  }

  if (!config.mail.enabled) {
    return { id: null, outcome: "skipped", reason: "mail disabled (MAIL_ENABLED=false)" };
  }
  if (!config.mail.apiKey) {
    return { id: null, outcome: "skipped", reason: "Resend API key is not configured" };
  }

  // A hard bounce or complaint blocks every kind of mail: re-sending to it
  // damages the domain that also carries receipts.
  if (await isSuppressed(to)) {
    return { id: null, outcome: "suppressed", reason: "recipient is suppressed" };
  }

  if (mail.kind !== "transactional" && mail.userId) {
    const prefs = await queryOne<{ email_subscription: boolean }>(
      "SELECT email_subscription FROM users WHERE id = $1",
      [mail.userId],
    );
    if (!prefs) return { id: null, outcome: "skipped", reason: "unknown user" };
    if (!prefs.email_subscription) {
      return { id: null, outcome: "skipped", reason: "user opted out of marketing mail" };
    }
  }

  const id = randomUUID();
  const vars = { ...appVariables(mail.userId ?? null), ...(mail.vars ?? {}) };

  let html = renderVars(mail.html, vars);
  if (mail.kind !== "transactional") html = ensureMarketingFooter(html, mail.userId ?? null);

  const instrumented = instrumentHtml(html, {
    openUrl: openPixelUrl(id),
    clickUrl: (target) => clickUrl(id, target),
  });

  const text =
    mail.text && mail.text.trim()
      ? renderVars(mail.text, vars, false)
      : htmlToText(instrumented.html);

  const inserted = await query<{ id: string }>(
    `INSERT INTO mail_sends
       (id, user_id, email, kind, campaign_id, automation_id, template_id,
        subject, html, text, status, dedupe_key)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'queued', $11)
     ON CONFLICT DO NOTHING
     RETURNING id`,
    [
      id,
      mail.userId ?? null,
      to,
      mail.kind,
      mail.campaignId ?? null,
      mail.automationId ?? null,
      mail.templateId ?? null,
      renderVars(mail.subject, vars, false),
      instrumented.html,
      text,
      mail.dedupeKey ?? null,
    ],
  );

  if (!inserted.length) {
    // Either the dedupe key or (campaign, user) uniqueness already fired.
    return { id: null, outcome: "duplicate", reason: "already queued" };
  }
  return { id, outcome: "queued" };
}

/** Platform acceptance of a delivery attempt, as reported by Resend. */
async function postToResend(payload: Record<string, unknown>): Promise<
  { ok: true; id: string } | { ok: false; error: string; retryable: boolean }
> {
  let res: Response;
  try {
    res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        authorization: `Bearer ${config.mail.apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "network error",
      retryable: true,
    };
  }

  const body = (await res.json().catch(() => ({}))) as { id?: string; message?: string };
  if (res.ok && body.id) return { ok: true, id: body.id };

  const retryable = res.status === 429 || res.status >= 500;
  return {
    ok: false,
    error: body.message ?? `Resend responded ${res.status}`,
    retryable,
  };
}

async function deliverRow(row: MailRow): Promise<boolean> {
  const headers: Record<string, string> = {};
  if (row.kind !== "transactional" && row.user_id) {
    const url = unsubscribeUrl(row.user_id);
    // RFC 8058 one-click unsubscribe: Gmail/Yahoo surface this as the native
    // unsubscribe button, which is what keeps complaint rates down.
    headers["List-Unsubscribe"] = `<${url}>`;
    headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click";
  }

  const payload: Record<string, unknown> = {
    from:
      row.kind === "transactional"
        ? config.mail.fromTransactional
        : config.mail.fromCampaign,
    to: [row.email],
    subject: row.subject,
    html: row.html ?? "",
    text: row.text ?? undefined,
    tags: [
      { name: "kind", value: row.kind },
      ...(row.campaign_id ? [{ name: "campaign", value: row.campaign_id }] : []),
    ],
  };
  if (config.mail.replyTo) payload.reply_to = config.mail.replyTo;
  if (Object.keys(headers).length) payload.headers = headers;

  const result = await postToResend(payload);

  if (result.ok) {
    await query(
      `UPDATE mail_sends
       SET status = 'sent', provider_id = $2, sent_at = now(), error = NULL, claimed_at = now()
       WHERE id = $1`,
      [row.id, result.id],
    );
    return true;
  }

  const exhausted = row.attempts >= config.mail.maxAttempts;
  await query(
    `UPDATE mail_sends
     SET status = $2, error = $3, claimed_at = now()
     WHERE id = $1`,
    [row.id, exhausted ? "failed" : "queued", result.error],
  );
  return false;
}

/**
 * Claim queued rows atomically and deliver them.
 *
 * `FOR UPDATE SKIP LOCKED` is what makes this safe when the API runs as more
 * than one process: each replica claims a disjoint batch, so no recipient is
 * mailed twice by two workers.
 */
export async function processMailQueue(limit = 25): Promise<number> {
  if (!mailConfigured()) return 0;

  const rows = await query<MailRow>(
    `UPDATE mail_sends s
     SET status = 'sending', claimed_at = now(), attempts = s.attempts + 1
     WHERE s.id IN (
       SELECT id FROM mail_sends
       WHERE status = 'queued'
         AND attempts < $2
         AND (claimed_at IS NULL OR claimed_at < now() - interval '2 minutes')
       ORDER BY created_at
       FOR UPDATE SKIP LOCKED
       LIMIT $1
     )
     RETURNING s.id, s.user_id, s.email, s.kind, s.subject, s.html, s.text,
               s.attempts, s.campaign_id`,
    [limit, config.mail.maxAttempts],
  );

  let sent = 0;
  const pauseMs = Math.ceil(1000 / config.mail.ratePerSecond);
  for (const row of rows) {
    if (await deliverRow(row)) sent += 1;
    if (pauseMs > 0) await new Promise((resolve) => setTimeout(resolve, pauseMs));
  }
  return sent;
}

/** Queue one message and try to deliver it immediately (admin test sends). */
export async function sendMailNow(mail: OutboundMail): Promise<QueueResult> {
  const queued = await queueMail(mail);
  if (queued.id) {
    await processMailQueue(1);
    const row = await queryOne<{ status: string; error: string | null }>(
      "SELECT status, error FROM mail_sends WHERE id = $1",
      [queued.id],
    );
    if (row && row.status === "failed") {
      return { id: queued.id, outcome: "skipped", reason: row.error ?? "delivery failed" };
    }
  }
  return queued;
}

/**
 * Record an engagement/delivery event and advance the delivery row.
 *
 * Returns false when the event was already recorded (provider retry, duplicate
 * pixel load) so counters never inflate.
 */
export async function recordMailEvent(
  sendId: string,
  type: MailEventType,
  meta: { url?: string | null; userAgent?: string | null; ip?: string | null; eventId?: string | null } = {},
): Promise<boolean> {
  const inserted = await query<{ id: string }>(
    `INSERT INTO mail_events (send_id, type, url, user_agent, ip, provider_event_id)
     VALUES ($1, $2, $3, $4, $5, $6)
     ON CONFLICT DO NOTHING
     RETURNING id`,
    [sendId, type, meta.url ?? null, meta.userAgent ?? null, meta.ip ?? null, meta.eventId ?? null],
  );
  if (!inserted.length) return false;

  switch (type) {
    case "opened":
      await query(
        `UPDATE mail_sends
         SET open_count = open_count + 1,
             first_opened_at = COALESCE(first_opened_at, now()),
             last_opened_at = now(),
             status = CASE WHEN status IN ('sent', 'delivered') THEN 'opened' ELSE status END
         WHERE id = $1`,
        [sendId],
      );
      break;
    case "clicked":
      await query(
        `UPDATE mail_sends
         SET click_count = click_count + 1,
             first_clicked_at = COALESCE(first_clicked_at, now()),
             last_clicked_at = now(),
             status = CASE
               WHEN status IN ('bounced', 'complained', 'failed') THEN status
               ELSE 'clicked'
             END
         WHERE id = $1`,
        [sendId],
      );
      break;
    case "delivered":
      await query(
        `UPDATE mail_sends
         SET status = CASE WHEN status = 'sent' THEN 'delivered' ELSE status END,
             delivered_at = COALESCE(delivered_at, now())
         WHERE id = $1`,
        [sendId],
      );
      break;
    case "bounced":
    case "complained":
    case "failed":
      await query("UPDATE mail_sends SET status = $2 WHERE id = $1", [sendId, type]);
      break;
  }
  return true;
}

/** Look up the delivery row behind a provider id (webhook → our send). */
export async function findSendByProviderId(
  providerId: string,
): Promise<{ id: string; user_id: string | null; email: string } | null> {
  return queryOne<{ id: string; user_id: string | null; email: string }>(
    "SELECT id, user_id, email FROM mail_sends WHERE provider_id = $1 LIMIT 1",
    [providerId],
  );
}

export interface MailHealth {
  configured: boolean;
  enabled: boolean;
  baseUrl: string;
  fromTransactional: string;
  fromCampaign: string;
  queueDepth: number;
  counts: Record<string, number>;
}

export async function mailHealth(): Promise<MailHealth> {
  const counts = await query<{ status: string; n: string }>(
    "SELECT status, COUNT(*)::text AS n FROM mail_sends GROUP BY status",
  );
  const map: Record<string, number> = {};
  for (const row of counts) map[row.status] = Number(row.n);

  return {
    configured: Boolean(config.mail.apiKey),
    enabled: config.mail.enabled,
    baseUrl: mailBaseUrl(),
    fromTransactional: config.mail.fromTransactional,
    fromCampaign: config.mail.fromCampaign,
    queueDepth: map.queued ?? 0,
    counts: map,
  };
}

/**
 * Per-user variables handed to a template: identity, pooled credit balance and
 * generation count. Templates link the product, never the API host.
 */
export async function mailVarsForUser(userId: string): Promise<Record<string, string>> {
  const row = await queryOne<{
    email: string;
    name: string | null;
    credits: string;
    songs: string;
  }>(
    `SELECT u.email,
            u.name,
            COALESCE((SELECT SUM(k.credits) FROM api_keys k
                      WHERE k.user_id = u.id AND k.is_active), 0)::text AS credits,
            COALESCE((SELECT COUNT(*) FROM usage_logs l
                      WHERE l.user_id = u.id AND l.endpoint = 'music'), 0)::text AS songs
     FROM users u WHERE u.id = $1`,
    [userId],
  );
  const vars = appVariables(userId);
  if (!row) return vars;

  const firstName = (row.name ?? "").trim().split(/\s+/)[0] ?? "";
  return {
    ...vars,
    email: row.email,
    name: row.name ?? (firstName || "there"),
    first_name: firstName || "there",
    credits: row.credits,
    songs: row.songs,
  };
}

/**
 * Pack ladder facts rendered from `credit_packs` and `pricing`, so a "bigger
 * packs are cheaper" email stays true when an operator reprices the ladder.
 *
 * `best_*` is the pack with the most credits per dollar. Percentages are stated
 * against the smallest pack, which is the honest comparison a user can verify.
 */
export async function packLadderVars(): Promise<Record<string, string>> {
  const music = await queryOne<{ credit_cost: number }>(
    "SELECT credit_cost FROM pricing WHERE endpoint = 'music' AND model IS NULL LIMIT 1",
  );
  const perSong = Math.max(1, Number(music?.credit_cost ?? 10));

  const packs = await query<{ amount: number; price: string }>(
    "SELECT amount, price::text AS price FROM credit_packs WHERE is_active ORDER BY amount",
  );
  if (packs.length === 0) {
    return { packs_html: "", best_pack_price: "", best_pack_songs: "", best_pack_bonus: "" };
  }

  const rows = packs.map((p) => {
    const credits = Number(p.amount);
    const price = Number(p.price);
    return {
      price,
      credits,
      songs: Math.floor(credits / perSong),
      perDollar: price > 0 ? credits / price : 0,
    };
  });

  const base = rows[0];
  const best = rows.reduce((a, b) => (b.perDollar > a.perDollar ? b : a));

  const packsHtml = rows
    .map((r) => {
      const bonus = base.perDollar > 0 ? Math.round((r.perDollar / base.perDollar - 1) * 100) : 0;
      const highlight = r === best;
      return (
        `<tr style="border-bottom:1px solid #e5e7eb;">` +
        `<td style="padding:10px 8px;font-weight:${highlight ? 700 : 400};">$${r.price}</td>` +
        `<td style="padding:10px 8px;">${r.credits.toLocaleString("en-US")} credits</td>` +
        `<td style="padding:10px 8px;">${r.songs.toLocaleString("en-US")} songs</td>` +
        `<td style="padding:10px 8px;color:${bonus > 0 ? "#059669" : "#6b7280"};">` +
        `${bonus > 0 ? `+${bonus}%` : "—"}</td>` +
        `</tr>`
      );
    })
    .join("");

  return {
    packs_html:
      `<table role="presentation" style="width:100%;border-collapse:collapse;font-size:14px;">` +
      `<thead><tr style="text-align:left;color:#6b7280;font-size:12px;">` +
      `<th style="padding:8px;">Price</th><th style="padding:8px;">Credits</th>` +
      `<th style="padding:8px;">Songs</th><th style="padding:8px;">vs smallest</th>` +
      `</tr></thead><tbody>${packsHtml}</tbody></table>`,
    best_pack_price: `$${best.price}`,
    best_pack_songs: best.songs.toLocaleString("en-US"),
    best_pack_bonus:
      base.perDollar > 0 ? String(Math.round((best.perDollar / base.perDollar - 1) * 100)) : "0",
  };
}

/** Admin test send: a plain transactional message proving the wiring works. */
export function testMailHtml(appUrl: string): string {
  return `<!doctype html><html><body style="margin:0;padding:24px;background:#f6f7fb;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;">
    <h1 style="margin:0 0 12px;font-size:20px;color:#111827;">CAMXORA mail is connected</h1>
    <p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#374151;">
      This is a test message from the admin console. If you can read it, Resend is
      wired up and the delivery ledger is recording.
    </p>
    <p style="margin:0 0 20px;font-size:13px;color:#6b7280;">Sent from the transactional identity.</p>
    <a href="${appUrl}" style="display:inline-block;background:#7466F1;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px;">Open CAMXORA</a>
  </div>
</body></html>`;
}
