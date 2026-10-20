import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Resend webhook verification and event mapping.
 *
 * Resend signs deliveries with Svix: the secret is `whsec_<base64 key>` and the
 * headers are `svix-id`, `svix-timestamp` and `svix-signature`. The signed
 * content is `${id}.${timestamp}.${rawBody}`, HMAC-SHA256, base64. Multiple
 * space-separated `v1,<sig>` entries are accepted (key rotation).
 *
 * Config-free and database-free so it can be unit-tested directly, matching the
 * split used for the ChmabaPay signature helper.
 */

/** Max accepted age/drift of a webhook timestamp, in seconds (±5 minutes). */
export const RESEND_TOLERANCE_SECONDS = 300;

export interface ResendHeaders {
  id: string | undefined;
  timestamp: string | undefined;
  signature: string | undefined;
}

/** Parse a `whsec_…` secret into the raw HMAC key. */
function webhookKey(secret: string): Buffer | null {
  const raw = secret.startsWith("whsec_") ? secret.slice("whsec_".length) : secret;
  if (!raw) return null;
  try {
    const key = Buffer.from(raw, "base64");
    return key.length > 0 ? key : null;
  } catch {
    return null;
  }
}

/**
 * Verify a Resend delivery. Rejects a missing/old timestamp (blunts replay of a
 * captured request) and compares signatures in constant time.
 */
export function verifyResendSignature(
  rawBody: string,
  headers: ResendHeaders,
  secret: string,
  nowSeconds: number = Date.now() / 1000,
): boolean {
  if (!secret || !rawBody) return false;
  const { id, timestamp, signature } = headers;
  if (!id || !timestamp || !signature) return false;

  const ts = Number(timestamp);
  if (!Number.isFinite(ts)) return false;
  if (Math.abs(nowSeconds - ts) > RESEND_TOLERANCE_SECONDS) return false;

  const key = webhookKey(secret);
  if (!key) return false;

  const expected = createHmac("sha256", key)
    .update(`${id}.${timestamp}.${rawBody}`, "utf8")
    .digest();

  for (const part of signature.split(" ")) {
    const [version, value] = part.split(",");
    if (version !== "v1" || !value) continue;
    let given: Buffer;
    try {
      given = Buffer.from(value, "base64");
    } catch {
      continue;
    }
    if (given.length === expected.length && timingSafeEqual(given, expected)) return true;
  }
  return false;
}

export type MailEventType =
  | "delivered"
  | "opened"
  | "clicked"
  | "bounced"
  | "complained"
  | "failed";

export interface MappedResendEvent {
  type: MailEventType;
  /** Provider message id (`data.email_id`) used to find our `mail_sends` row. */
  emailId: string;
  /** First recipient, used for suppression on bounces/complaints. */
  recipient: string | null;
  subject: string | null;
  /** `click.link` for clicks; null otherwise. */
  url: string | null;
}

/**
 * Map a Resend event to our event vocabulary.
 *
 * `email.opened` and `email.clicked` are intentionally NOT consumed: opens and
 * clicks are recorded by this service's signed pixel/redirect so a provider
 * setting cannot double-count them. Delivery state is the provider's to report.
 */
export function mapResendEvent(payload: unknown): MappedResendEvent | null {
  if (!payload || typeof payload !== "object") return null;
  const body = payload as { type?: unknown; data?: unknown };
  if (typeof body.type !== "string" || !body.data || typeof body.data !== "object") return null;

  const data = body.data as Record<string, unknown>;
  const emailId = typeof data.email_id === "string" ? data.email_id : null;
  if (!emailId) return null;

  const to = Array.isArray(data.to) ? data.to : [];
  const recipient =
    typeof to[0] === "string" && to[0].trim() ? to[0].trim().toLowerCase() : null;
  const subject = typeof data.subject === "string" ? data.subject : null;

  const click = data.click as { link?: unknown } | undefined;
  const url = typeof click?.link === "string" ? click.link : null;

  switch (body.type) {
    case "email.delivered":
      return { type: "delivered", emailId, recipient, subject, url: null };
    case "email.bounced":
      return { type: "bounced", emailId, recipient, subject, url: null };
    case "email.complained":
      return { type: "complained", emailId, recipient, subject, url: null };
    case "email.failed":
      return { type: "failed", emailId, recipient, subject, url: null };
    default:
      return null;
  }
}

/** Reason a bounce/complaint should land on the suppression list. */
export function suppressionReasonFor(type: MailEventType): "bounce" | "complaint" | null {
  if (type === "bounced") return "bounce";
  if (type === "complained") return "complaint";
  return null;
}
