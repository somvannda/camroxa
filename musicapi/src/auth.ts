import { config } from "./config.js";

const CLERK_VERSION = "5.117.0";
const CLERK_API_VERSION = "2025-11-10";
const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";

export function baseHeaders(): Record<string, string> {
  return {
    "user-agent": USER_AGENT,
    "accept-language": "en",
    origin: "https://suno.com",
    referer: "https://suno.com/",
  };
}

/**
 * browser-token is a per-request value derived from a timestamp.
 * Format (confirmed live): {"token":"<base64({"timestamp":<ms>})>"}
 */
export function makeBrowserTokenHeader(): string {
  const payload = Buffer.from(JSON.stringify({ timestamp: Date.now() })).toString(
    "base64",
  );
  return JSON.stringify({ token: payload });
}

/**
 * Full header set for Suno API requests (confirmed live):
 * authorization + device-id + browser-token + origin/referer.
 */
export function apiHeaders(
  jwt: string,
  deviceId: string,
  extra: Record<string, string> = {},
): Record<string, string> {
  return {
    ...baseHeaders(),
    authorization: `Bearer ${jwt}`,
    "device-id": deviceId,
    "browser-token": makeBrowserTokenHeader(),
    ...extra,
  };
}

function clerkHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const cookies = [`__client=${config.clientCookie}`];
  if (config.cookie) cookies.push(config.cookie);
  return {
    ...baseHeaders(),
    authorization: config.clientCookie,
    cookie: cookies.join("; "),
    ...extra,
  };
}

async function getActiveSessionId(): Promise<string> {
  const url = `${config.clerkUrl}/v1/client?__clerk_api_version=${CLERK_API_VERSION}&_clerk_js_version=${CLERK_VERSION}`;
  const res = await fetch(url, { headers: clerkHeaders(), signal: AbortSignal.timeout(15_000) });
  if (!res.ok) {
    throw new Error(`Clerk /client failed (${res.status}): ${await res.text()}`);
  }
  const data = (await res.json()) as {
    response?: { last_active_session_id?: string };
  };
  const sessionId = data.response?.last_active_session_id;
  if (!sessionId) {
    throw new Error(
      "No active Clerk session. SUNO_CLIENT_COOKIE is missing, invalid, or expired.",
    );
  }
  return sessionId;
}

async function mintJwt(sessionId: string): Promise<string> {
  const url = `${config.clerkUrl}/v1/client/sessions/${sessionId}/tokens?__clerk_api_version=${CLERK_API_VERSION}&_clerk_js_version=${CLERK_VERSION}`;
  const res = await fetch(url, {
    method: "POST",
    headers: clerkHeaders({ "content-type": "application/x-www-form-urlencoded" }),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) {
    throw new Error(`Clerk token mint failed (${res.status}): ${await res.text()}`);
  }
  const data = (await res.json()) as { jwt?: string };
  if (!data.jwt) throw new Error("Clerk returned no jwt.");
  return data.jwt;
}

let cachedJwt: string | undefined;

/**
 * Resolve a valid Bearer JWT, in priority order:
 *   1. SUNO_JWT (one-off, expires ~1h)
 *   2. SUNO_CLIENT_COOKIE -> mint from Clerk (durable, auto-refresh)
 */
export async function resolveJwt(): Promise<string> {
  if (config.jwt) return config.jwt;
  if (!config.clientCookie) {
    throw new Error(
      "Set SUNO_CLIENT_COOKIE (durable) or SUNO_JWT in .env (see .env.example).",
    );
  }
  if (!cachedJwt) {
    const sessionId = await getActiveSessionId();
    cachedJwt = await mintJwt(sessionId);
  }
  return cachedJwt;
}

/** Force a fresh JWT (call after an auth failure or on expiry). */
export async function refreshJwt(): Promise<string> {
  cachedJwt = undefined;
  return resolveJwt();
}
