import { createHmac } from "node:crypto";

/**
 * Signature header for platform callbacks.
 *
 * The platform API (`platform_api/routers/callbacks.py`) verifies
 * `HMAC-SHA256(raw_body, PLATFORM_SUNO_CALLBACK_HMAC_SECRET)` and accepts the
 * bare hex or `sha256=<hex>` form. Suno's own provider webhooks are unsigned,
 * so before this every callback posted by this service was rejected
 * ("HMAC/IP validation failed") and task status relied on polling.
 *
 * Returns `{}` when no secret is configured, preserving the previous unsigned
 * behaviour for sandbox/dev (where the platform accepts a debug callback).
 */
export function callbackSignatureHeaders(
  secret: string,
  body: string,
): Record<string, string> {
  const key = (secret ?? "").trim();
  if (!key) return {};
  const digest = createHmac("sha256", key).update(body).digest("hex");
  return { "X-Signature": `sha256=${digest}` };
}
