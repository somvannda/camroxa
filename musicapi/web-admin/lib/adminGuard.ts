/**
 * Session-probe policy for the admin console guard (`proxy.ts`).
 *
 * Kept free of any `next/server` import so the decision can be unit-tested
 * directly with `node:test`, and so there is a single definition of how the
 * API's `/auth/me` reply maps to a guard action.
 */

/** Name of the httpOnly admin session cookie set by the API (src/appAuth.ts). */
export const SESSION_COOKIE = "sunosession_admin";

/** A minimal view of the API's `/auth/me` payload. */
export interface AdminIdentity {
  role?: string;
  status?: string;
}

export type SessionProbe =
  /** Session is a live, active admin — allow the request. */
  | { kind: "active"; user: AdminIdentity }
  /** Session is valid but not an active admin — clear it and send to /login. */
  | { kind: "inactive"; user: AdminIdentity }
  /** API definitively rejected the session (401/403) — safe to clear it. */
  | { kind: "dead" }
  /**
   * The probe could not be completed (network error, timeout, 5xx, ...). This
   * is an API fault, not a bad session, so the caller must NOT clear the
   * cookie — otherwise a transient backend hiccup logs the operator out.
   */
  | { kind: "unavailable" };

/**
 * Ask the API whether the session behind `token` belongs to an active admin.
 * Never throws: any transport failure is reported as `unavailable`.
 */
export async function probeAdminSession(
  token: string,
  backendUrl: string,
  fetchImpl: typeof fetch = fetch,
  timeoutMs = 5000,
): Promise<SessionProbe> {
  try {
    const res = await fetchImpl(`${backendUrl}/auth/me`, {
      headers: { cookie: `${SESSION_COOKIE}=${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    // 401/403 is the API saying the session itself is no good. Every other
    // non-ok status (500, 502, 503, 429, ...) is the API being unhealthy.
    if (res.status === 401 || res.status === 403) return { kind: "dead" };
    if (!res.ok) return { kind: "unavailable" };
    const user = (await res.json()) as AdminIdentity;
    if (user.role !== "admin" || user.status !== "active") return { kind: "inactive", user };
    return { kind: "active", user };
  } catch {
    return { kind: "unavailable" };
  }
}
