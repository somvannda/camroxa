import { clearSession } from "./auth";

const BASE = "/backend";

/**
 * Sign out: clears the httpOnly session cookie server-side, then drops the
 * cached profile. Safe to call even if the request fails.
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "same-origin" });
  } catch (e) {
    // The httpOnly cookie can't be cleared from JS if this fails; log so the
    // operator isn't left guessing. Local state is still dropped below.
    console.warn("Logout request failed", e);
  }
  clearSession();
}

function redirectToLogin(): void {
  clearSession();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    // Full reload clears cached client state. This runs outside React
    // (lib/api.ts), so useRouter is unavailable; the hard redirect is intended.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }
}

/** Read the readable admin CSRF cookie for double-submit on mutations. */
function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)sunosession_admin_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  // The session travels in an httpOnly cookie; mutations must also echo the
  // readable CSRF cookie set at login (SameSite=Lax + the Origin allowlist
  // remain the primary guard).
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = csrfToken();
    if (token) headers["x-csrf-token"] = token;
  }

  const res = await fetch(`${BASE}${path}`, { credentials: "same-origin", ...init, headers });
  if (res.status === 401) redirectToLogin();
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
