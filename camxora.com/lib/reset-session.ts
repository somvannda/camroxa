export const RESET_SESSION_KEY = "camxora:password-reset";

export type ResetSession = {
  email: string;
  code: string;
};

export function saveResetSession(session: ResetSession): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(RESET_SESSION_KEY, JSON.stringify(session));
}

export function readResetSession(): ResetSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(RESET_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ResetSession>;
    if (!parsed.email || !parsed.code) return null;
    return { email: String(parsed.email), code: String(parsed.code) };
  } catch {
    return null;
  }
}

export function clearResetSession(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(RESET_SESSION_KEY);
}
