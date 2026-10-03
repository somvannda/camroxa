import { clearSession } from "./auth";

const BASE = "/backend";

/**
 * Sign out: clears the httpOnly session cookie server-side, then drops the
 * cached profile. Safe to call even if the request fails.
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "same-origin" });
  } catch {
    // Ignore — clearing local state below is what matters.
  }
  clearSession();
}

export function redirectToLogin(): void {
  clearSession();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

/** Absolute same-origin URL for a backend asset (e.g. an `<img src>`). */
export function backendUrl(path: string): string {
  return `${BASE}${path}`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  let res: Response;
  try {
    // The session travels in an httpOnly cookie set by the API, so it is sent
    // automatically on same-origin calls — no token to attach here.
    res = await fetch(`${BASE}${path}`, { credentials: "same-origin", ...init, headers });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    if (e instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(e.message)) {
      throw new Error("Cannot reach server. Check your connection or the backend service.");
    }
    throw new Error(e instanceof Error ? e.message : "Request failed");
  }
  if (res.status === 401) redirectToLogin();
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
