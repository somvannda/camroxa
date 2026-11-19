import { useSessionStore } from "../../store/session";

export interface AuthActions {
  /** Re-runs bootstrap without restarting the app. Returns an error message or null. */
  refresh: () => Promise<string | null>;
  signOut: () => Promise<void>;
}

export function useAuthActions(): AuthActions {
  const applyBootstrap = useSessionStore((state) => state.applyBootstrap);
  const clear = useSessionStore((state) => state.clear);

  async function refresh(): Promise<string | null> {
    if (!window.camxora) return "Refresh is only available in the desktop application.";
    try {
      const result = await window.camxora.auth.bootstrap();
      if (!result.ok) return result.error.message;
      applyBootstrap(result.data);
      return null;
    } catch {
      return "Unable to check your account right now. Try again.";
    }
  }

  async function signOut(): Promise<void> {
    try {
      if (window.camxora) await window.camxora.auth.logout();
    } finally {
      clear();
    }
  }

  return { refresh, signOut };
}
