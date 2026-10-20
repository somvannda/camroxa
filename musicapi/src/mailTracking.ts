import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Signed tokens and body instrumentation for open/click tracking.
 *
 * Kept free of config and database access so the security-relevant parts
 * (signature packing, link rewriting, redirect safety) can be unit-tested
 * without booting the server — same split as `webhookSignature.ts`.
 *
 * Token shape: `<base64url(payload)>.<base64url(HMAC-SHA256(payload))>`. The
 * payload is short and structured with a type prefix, so a token minted for one
 * purpose (open) can never be replayed as another (click, unsubscribe).
 */

const TYPE_OPEN = "o1";
const TYPE_CLICK = "c1";
const TYPE_UNSUB = "u1";

function hmac(secret: string, value: string): Buffer {
  return createHmac("sha256", secret).update(value, "utf8").digest();
}

function b64url(buf: Buffer): string {
  return buf.toString("base64url");
}

function pack(secret: string, payload: string): string {
  const body = b64url(Buffer.from(payload, "utf8"));
  return `${body}.${b64url(hmac(secret, body))}`;
}

/** Constant-time verification. Returns the payload, or null when untrusted. */
export function unpack(secret: string, token: string): string | null {
  if (!secret || !token) return null;
  const dot = token.lastIndexOf(".");
  if (dot <= 0 || dot === token.length - 1) return null;
  const body = token.slice(0, dot);
  const given = token.slice(dot + 1);
  const expected = b64url(hmac(secret, body));
  const a = Buffer.from(given, "utf8");
  const b = Buffer.from(expected, "utf8");
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    return Buffer.from(body, "base64url").toString("utf8");
  } catch {
    return null;
  }
}

/** Token embedded in the tracking pixel for one delivery. */
export function buildOpenToken(secret: string, sendId: string): string {
  return pack(secret, `${TYPE_OPEN}.${sendId}`);
}

export function parseOpenToken(secret: string, token: string): { sendId: string } | null {
  const payload = unpack(secret, token);
  if (!payload) return null;
  const [type, sendId] = payload.split(".");
  if (type !== TYPE_OPEN || !sendId) return null;
  return { sendId };
}

/**
 * Click token. The destination is part of the signed payload, so a tampered
 * `u=` parameter cannot turn the redirect endpoint into an open redirect.
 */
export function buildClickToken(secret: string, sendId: string, url: string): string {
  return pack(secret, `${TYPE_CLICK}.${sendId}.${b64url(Buffer.from(url, "utf8"))}`);
}

export function parseClickToken(
  secret: string,
  token: string,
): { sendId: string; url: string } | null {
  const payload = unpack(secret, token);
  if (!payload) return null;
  const [type, sendId, encoded] = payload.split(".");
  if (type !== TYPE_CLICK || !sendId || !encoded) return null;
  let url: string;
  try {
    url = Buffer.from(encoded, "base64url").toString("utf8");
  } catch {
    return null;
  }
  if (!isSafeRedirect(url)) return null;
  return { sendId, url };
}

/** Only absolute http(s) destinations are ever redirected to. */
export function isSafeRedirect(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}

/**
 * Unsubscribe token. Keyed on the user id, not the send id, so a person who
 * manages to open an old email can still unsubscribe after their record has
 * been re-mailed many times.
 */
export function buildUnsubToken(secret: string, userId: string): string {
  return pack(secret, `${TYPE_UNSUB}.${userId}`);
}

export function parseUnsubToken(secret: string, token: string): { userId: string } | null {
  const payload = unpack(secret, token);
  if (!payload) return null;
  const [type, userId] = payload.split(".");
  if (type !== TYPE_UNSUB || !userId) return null;
  return { userId };
}

/** Links we must not wrap: anchors, mailto/tel, placeholders, and our own routes. */
function shouldInstrument(href: string): boolean {
  const value = href.trim();
  if (!value) return false;
  if (value.startsWith("#")) return false;
  if (/^(mailto|tel|sms):/i.test(value)) return false;
  if (value.includes("{{") || value.includes("{%")) return false;
  if (value.startsWith("/mail/")) return false;
  return isSafeRedirect(value);
}

/**
 * Rewrite every clickable link through the redirect endpoint and append the
 * open pixel. Returns the html plus the number of links rewritten, so a caller
 * can warn when a template has no links at all.
 */
export function instrumentHtml(
  html: string,
  opts: {
    clickUrl: (target: string) => string;
    openUrl: string;
  },
): { html: string; links: number } {
  let links = 0;
  const rewritten = html.replace(
    /(<a\b[^>]*?\shref\s*=\s*)(["'])(.*?)\2/gi,
    (match, prefix: string, quote: string, href: string) => {
      if (!shouldInstrument(href)) return match;
      links += 1;
      const tracked = opts.clickUrl(href.trim());
      return `${prefix}${quote}${tracked}${quote}`;
    },
  );

  const pixel =
    `<img src="${opts.openUrl}" width="1" height="1" alt="" ` +
    `style="display:block;width:1px;height:1px;border:0;outline:none;" />`;

  const withPixel = /<\/body>/i.test(rewritten)
    ? rewritten.replace(/<\/body>/i, `${pixel}</body>`)
    : rewritten + pixel;

  return { html: withPixel, links };
}

/** Strip tags for the plain-text alternative (no dependency, good enough). */
export function htmlToText(html: string): string {
  return html
    .replace(/<style\b[\s\S]*?<\/style>/gi, "")
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/<head\b[\s\S]*?<\/head>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|tr|li|h[1-6])>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch] ?? ch);
}

/**
 * Replace `{{name}}` placeholders. Unknown placeholders are left intact so a
 * template bug is visible in the sent mail instead of silently blanking a line.
 */
export function renderVars(
  source: string,
  vars: Record<string, string | number | null | undefined>,
  escape = true,
): string {
  return source.replace(/\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g, (match, key: string) => {
    const value = vars[key];
    if (value === undefined || value === null) return match;
    const text = String(value);
    return escape ? escapeHtml(text) : text;
  });
}
