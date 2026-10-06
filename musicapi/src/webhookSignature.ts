import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Payment-webhook signature verification, kept in a config-free module so the
 * security-critical logic can be unit-tested without booting the server.
 */

/** Max accepted age/drift of a webhook timestamp, in seconds (±5 minutes). */
export const SIGNATURE_TOLERANCE_SECONDS = 300;

/**
 * Verify a ChmabaPay webhook. The `X-ChmabaPay-Signature` header is
 * `t=<unix>,v1=<hex>` and the signed payload is `${t}.${rawBody}` (HMAC-SHA256
 * with the endpoint's `whsec_…` secret). A timestamp outside the tolerance
 * window is rejected, which blunts replay of a captured delivery. Comparison is
 * constant-time.
 *
 * `nowSeconds` is injectable so the replay window can be tested deterministically.
 */
export function verifyChmabaSignature(
  rawBody: string,
  header: string | undefined,
  secret: string,
  nowSeconds: number = Date.now() / 1000,
): boolean {
  if (!secret || !header) return false;
  const parts = header.split(",");
  const t = parts.find((p) => p.startsWith("t="))?.slice(2);
  const v1 = parts.find((p) => p.startsWith("v1="))?.slice(3);
  if (!t || !v1 || !Number.isFinite(Number(t))) return false;
  if (Math.abs(nowSeconds - Number(t)) > SIGNATURE_TOLERANCE_SECONDS) return false;
  const expected = createHmac("sha256", secret).update(`${t}.${rawBody}`, "utf8").digest("hex");
  const a = Buffer.from(v1, "hex");
  const b = Buffer.from(expected, "hex");
  return a.length === b.length && timingSafeEqual(a, b);
}

/**
 * Return the first string under `reference_id`, anywhere in the event. The
 * delivery envelope is not documented field-by-field, so scanning for the id we
 * set at checkout is what maps a webhook back to one of our transactions.
 */
export function findReferenceId(node: unknown, depth = 0): string | null {
  if (depth > 8 || node === null || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    for (const item of node) {
      const found = findReferenceId(item, depth + 1);
      if (found) return found;
    }
    return null;
  }
  const rec = node as Record<string, unknown>;
  if (typeof rec.reference_id === "string" && rec.reference_id.trim()) return rec.reference_id.trim();
  for (const value of Object.values(rec)) {
    const found = findReferenceId(value, depth + 1);
    if (found) return found;
  }
  return null;
}
