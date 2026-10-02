import { lookup } from "node:dns/promises";
import { isIP } from "node:net";

// Hostnames that never make sense as a public webhook target.
const BLOCKED_HOSTNAMES = new Set(["localhost", "localhost.localdomain", "ip6-localhost"]);

// Optional comma-separated allowlist of callback hosts (e.g. "hooks.example.com,api.partner.io").
// When empty, any public host is permitted; when set, only the listed hosts (or their subdomains) are.
const ALLOWED_HOSTS = (process.env.CALLBACK_ALLOWED_HOSTS ?? "")
  .split(",")
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean);

function isPrivateIPv4(ip: string): boolean {
  const parts = ip.split(".").map(Number);
  if (parts.length !== 4 || parts.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return true;
  const [a, b] = parts;
  if (a === 0) return true; // 0.0.0.0/8 "this network"
  if (a === 10) return true; // 10.0.0.0/8 private
  if (a === 127) return true; // loopback
  if (a === 169 && b === 254) return true; // link-local (incl. cloud metadata 169.254.169.254)
  if (a === 172 && b >= 16 && b <= 31) return true; // 172.16.0.0/12 private
  if (a === 192 && b === 168) return true; // 192.168.0.0/16 private
  if (a === 100 && b >= 64 && b <= 127) return true; // 100.64.0.0/10 carrier NAT
  if (a >= 224) return true; // multicast + reserved
  return false;
}

function isPrivateIPv6(ip: string): boolean {
  const addr = ip.toLowerCase();
  if (addr === "::" || addr === "::1") return true; // unspecified / loopback
  if (addr.startsWith("fe80:")) return true; // link-local
  if (/^f[cd][0-9a-f]{2}:/.test(addr)) return true; // fc00::/7 unique-local
  if (addr.startsWith("::ffff:")) return isPrivateIPv4(addr.slice("::ffff:".length)); // IPv4-mapped
  return false;
}

/** Fail closed: anything we cannot confidently classify as public is treated as private. */
function isPrivateAddress(ip: string): boolean {
  const version = isIP(ip);
  if (version === 4) return isPrivateIPv4(ip);
  if (version === 6) return isPrivateIPv6(ip);
  return true;
}

function hostAllowed(hostname: string): boolean {
  if (ALLOWED_HOSTS.length === 0) return true;
  const h = hostname.toLowerCase();
  return ALLOWED_HOSTS.some((entry) => h === entry || h.endsWith(`.${entry}`));
}

/**
 * Returns `null` when the URL is safe to call, or a human-readable reason when it
 * must be blocked. Guards against SSRF into loopback / private / link-local ranges
 * and against non-HTTP schemes.
 */
export async function checkCallbackUrl(raw: string): Promise<string | null> {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return "callback URL is not a valid URL";
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return "callback URL must use http or https";
  }
  const hostname = url.hostname.replace(/^\[|\]$/g, "");
  if (!hostname) return "callback URL has no host";
  if (BLOCKED_HOSTNAMES.has(hostname.toLowerCase())) return "callback URL host is not allowed";
  if (!hostAllowed(hostname)) return "callback URL host is not in CALLBACK_ALLOWED_HOSTS";

  let addresses: string[];
  if (isIP(hostname)) {
    addresses = [hostname];
  } else {
    try {
      const records = await lookup(hostname, { all: true });
      addresses = records.map((r) => r.address);
    } catch {
      return "callback URL host could not be resolved";
    }
  }
  if (addresses.length === 0) return "callback URL host could not be resolved";
  if (addresses.some(isPrivateAddress)) {
    return "callback URL resolves to a private or reserved address";
  }
  return null;
}
