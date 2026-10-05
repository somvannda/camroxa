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
    window.location.href = "/login";
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  // The session travels in an httpOnly cookie set by the API, so it is sent
  // automatically on same-origin calls — no token to attach here.
  const res = await fetch(`${BASE}${path}`, { credentials: "same-origin", ...init, headers });
  if (res.status === 401) redirectToLogin();
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
