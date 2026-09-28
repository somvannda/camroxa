import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import { config } from "./config.js";

/**
 * Raised when a caller-supplied callback URL must not be fetched. The message is
 * written to be safe to return to API clients (it never echoes DNS results).
 */
export class CallbackUrlError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CallbackUrlError";
  }
}

/** IPv4 ranges a webhook target must never be able to reach. */
const BLOCKED_IPV4: RegExp[] = [
  /^0\./, // "this" network
  /^10\./, // private
  /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./, // CGNAT
  /^127\./, // loopback
  /^169\.254\./, // link-local (includes 169.254.169.254 cloud metadata)
  /^172\.(1[6-9]|2\d|3[01])\./, // private
  /^192\.0\.0\./, // IETF protocol assignments
  /^192\.168\./, // private
  /^198\.1[89]\./, // benchmarking
  /^22[4-9]\./, // multicast
  /^2[3-5]\d\./, // reserved / broadcast
];

/** Hostname suffixes that only ever name the local machine. */
const LOCAL_HOST_SUFFIXES = [".localhost", ".local", ".internal", ".home.arpa"];

/** True when an IP literal is loopback, private, link-local, or otherwise internal. */
function isBlockedIp(ip: string): boolean {
  const version = isIP(ip);
  if (version === 4) return BLOCKED_IPV4.some((re) => re.test(ip));
  if (version !== 6) return true; // not an address at all — refuse rather than guess
  const v6 = ip.toLowerCase();
  return (
    v6 === "::" || // unspecified
    v6 === "::1" || // loopback
    v6.startsWith("fe80:") || // link-local
    v6.startsWith("fc") || // unique-local fc00::/7
    v6.startsWith("fd") || // unique-local fd00::/8
    v6.startsWith("ff") || // multicast
    v6.startsWith("::ffff:") // IPv4-mapped, e.g. ::ffff:127.0.0.1
  );
}

/** When `CALLBACK_ALLOWED_HOSTS` is set, the host must match one of its entries. */
function isHostAllowed(host: string): boolean {
  const allow = config.callbackAllowedHosts;
  if (allow.length === 0) return true;
  return allow.some((h) => host === h || host.endsWith(`.${h}`));
}

/**
 * Validate a caller-supplied webhook `callback_url` and return it parsed, or
 * throw `CallbackUrlError`. Rejects non-http(s) schemes, embedded credentials,
 * and any target that is — or resolves to — a loopback/private/link-local
 * address, so a caller can't point the server at its own internal network.
 */
export async function assertCallbackUrlAllowed(raw: string): Promise<URL> {
  const trimmed = raw.trim();
  if (!trimmed) throw new CallbackUrlError("callback_url must be a non-empty URL.");

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new CallbackUrlError("callback_url is not a valid absolute URL.");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new CallbackUrlError("callback_url must use the http or https scheme.");
  }
  if (url.username || url.password) {
    throw new CallbackUrlError("callback_url must not contain embedded credentials.");
  }

  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (!host) throw new CallbackUrlError("callback_url must include a host.");

  if (!isHostAllowed(host)) {
    throw new CallbackUrlError("callback_url host is not on the configured allowlist.");
  }
  if (host === "localhost" || LOCAL_HOST_SUFFIXES.some((s) => host.endsWith(s))) {
    throw new CallbackUrlError("callback_url must not target a local host.");
  }

  if (isIP(host)) {
    if (isBlockedIp(host)) throw new CallbackUrlError("callback_url must not target a private address.");
    return url;
  }

  // Resolve the name too: a public hostname can be pointed at an internal
  // address (e.g. 127.0.0.1.nip.io), which an IP-literal check alone misses.
  let addresses: { address: string }[];
  try {
    addresses = await lookup(host, { all: true });
  } catch {
    throw new CallbackUrlError("callback_url host could not be resolved.");
  }
  if (addresses.length === 0 || addresses.some((a) => isBlockedIp(a.address))) {
    throw new CallbackUrlError("callback_url must not target a private address.");
  }
  return url;
}
