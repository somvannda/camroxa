import { useEffect, useState, type ReactNode } from "react";
import type { AppInfo, SessionSummary } from "../../../electron/shared/types";
import { useSessionStore } from "../../store/session";
import { BootSplash } from "./boot-splash";
import { LoginPage } from "./login-page";

const DEV_SESSION: SessionSummary = {
  userId: "dev",
  email: "dev@camxora.local",
  displayName: "Development",
  accessExpiresAt: Date.now() + 24 * 60 * 60 * 1000,
};

export function AuthGate({ children }: { children: ReactNode }) {
  const status = useSessionStore((state) => state.status);
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        if (!window.camxora) {
          useSessionStore.getState().setSession(DEV_SESSION);
          return;
        }
        const info = (await window.camxora.app.info()) as AppInfo;
        if (info.devBypass) {
          useSessionStore.getState().setSession(DEV_SESSION);
          return;
        }
        const restored = await window.camxora.auth.restore();
        if (restored.ok && restored.data) {
          useSessionStore.getState().setSession(restored.data);
        } else {
          useSessionStore.getState().clear();
        }
      } catch {
        useSessionStore.getState().clear();
      } finally {
        if (!cancelled) setBooted(true);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!booted || status === "loading") return <BootSplash />;
  if (status !== "authenticated") return <LoginPage />;
  return <>{children}</>;
}
