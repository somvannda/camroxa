import type { FastifyServerOptions } from "fastify";

/** Fastify's `trustProxy` option type, re-exported for callers/tests. */
export type TrustProxyOption = FastifyServerOptions["trustProxy"];

/**
 * Resolve Fastify's `trustProxy` from `TRUST_PROXY` so `req.ip` is the real
 * client address behind a reverse proxy (the socket address would otherwise be
 * the proxy). Defaults to off: if the server is directly reachable, blindly
 * trusting `X-Forwarded-For` lets a caller spoof its IP and defeat an API key's
 * whitelist. Accepts "true"/"false", a hop count, or a comma-separated list of
 * trusted addresses/CIDRs.
 *
 * Kept in its own config-free module so it can be unit-tested without booting
 * the server (which requires secrets and a database).
 */
export function trustProxyOption(env: NodeJS.ProcessEnv = process.env): TrustProxyOption {
  const raw = (env.TRUST_PROXY ?? "").trim();
  if (!raw || raw === "false" || raw === "0") return false;
  if (raw === "true") return true;
  // A bare number is the proxy hop count. proxy-addr honors it at runtime, but
  // Fastify's option type omits it, so it needs a cast.
  if (/^\d+$/.test(raw)) return Number(raw) as unknown as TrustProxyOption;
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}
