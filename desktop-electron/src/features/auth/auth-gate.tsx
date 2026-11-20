import { useEffect, useState, type ReactNode } from "react";
import type { AppInfo, SessionSummary } from "../../../electron/shared/types";
import { useSessionStore } from "../../store/session";
import { BootSplash } from "./boot-splash";
import { ConfirmEmailGate } from "./confirm-email-gate";
import { LoginPage } from "./login-page";
import { TopUpModal } from "./top-up-modal";

const DEV_SESSION: SessionSummary = {
  userId: "dev",
  email: "dev@camxora.local",
  displayName: "Development",
  accessExpiresAt: Date.now() + 24 * 60 * 60 * 1000,
};

export function AuthGate({ children }: { children: ReactNode }) {
  const status = useSessionStore((state) => state.status);
  const destination = useSessionStore((state) => state.destination);
  const noticePortalUrl = useSessionStore((state) => state.notice?.portalUrl);
  const [booted, setBooted] = useState(false);
  const [portalUrl, setPortalUrl] = useState("https://app.camxora.com");

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      const store = useSessionStore.getState();
      try {
        if (!window.camxora) {
          store.setSession(DEV_SESSION);
          return;
        }
        const info = (await window.camxora.app.info()) as AppInfo;
        if (cancelled) return;
        if (info.portalUrl) setPortalUrl(info.portalUrl);
        if (info.devBypass) {
          store.setSession(DEV_SESSION);
          return;
        }
        const restored = await window.camxora.auth.restore();
        if (cancelled) return;
        if (restored.ok) {
          store.applyBootstrap(restored.data);
        } else {
          store.applyBootstrap({
            destination: "login",
            session: null,
            message: restored.error.message,
            code: restored.error.code,
            portalUrl: info.portalUrl,
          });
        }
      } catch {
        if (!cancelled) {
          store.applyBootstrap({
            destination: "login",
            session: null,
            message: "Unable to reach the sign-in service. Try again.",
            code: "BOOTSTRAP_FAILED",
            portalUrl,
          });
        }
      } finally {
        if (!cancelled) setBooted(true);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
    // Boot runs once for the app lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!booted || status === "loading") return <BootSplash />;

  const resolvedPortalUrl = noticePortalUrl ?? portalUrl;

  if (status !== "authenticated") {
    return <LoginPage portalUrl={resolvedPortalUrl} />;
  }
  if (destination === "confirm_email") {
    return <ConfirmEmailGate portalUrl={resolvedPortalUrl} />;
  }
  if (destination === "topup") {
    return (
      <div className="relative h-full">
        <LoginPage portalUrl={resolvedPortalUrl} />
        <TopUpModal />
      </div>
    );
  }
  return <>{children}</>;
}
