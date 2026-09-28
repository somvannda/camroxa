const USER_KEY = "suno_user";

export interface AuthUser {
  id: string;
  email: string;
  role: "user" | "admin";
  name?: string | null;
}

// The session JWT lives in an httpOnly cookie set by the API (see
// musicapi/src/server.ts) and is deliberately unreadable from JS. Only
// non-sensitive profile fields are cached here for rendering.
if (typeof window !== "undefined") {
  // Drop any JWT persisted by an older build so it can't linger in storage.
  localStorage.removeItem("suno_token");
}

export function setSession(user: AuthUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}
