import { useState } from "react";
import logoUrl from "../../assets/brand/camxora-logo.svg";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { ToastViewport } from "../../components/toast";
import { useSessionStore } from "../../store/session";
import { PlanPage } from "../plan/plan-page";

export function TopUpGate() {
  const applyBootstrap = useSessionStore((state) => state.applyBootstrap);
  const session = useSessionStore((state) => state.session);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function refreshAccess() {
    setBusy(true);
    setMessage("");
    try {
      const restored = await window.camxora.auth.restore();
      if (restored.ok) {
        applyBootstrap(restored.data);
        if (restored.data.destination === "topup") {
          setMessage("No credits detected yet. If you just paid, wait a moment and try again.");
        }
      } else {
        setMessage(restored.error.message);
      }
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Unable to refresh your balance.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await window.camxora.auth.logout();
    useSessionStore.getState().clear();
  }

  return (
    <div className="flex h-full flex-col bg-bg">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-surface-1 px-4">
        <div className="flex items-center gap-2.5">
          <img src={logoUrl} alt="" className="h-7 w-7 rounded-[7px]" />
          <span className="text-[15px] font-semibold tracking-[-0.01em] text-text-primary">
            Camxora
          </span>
        </div>
        <div className="flex items-center gap-3 text-meta text-text-secondary">
          <span className="truncate">{session?.email ?? ""}</span>
          <Button variant="ghost" className="h-8 px-2" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-accent-line bg-accent-soft px-5 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-2">
              <Icon name="fa-credit-card" size={15} className="mt-0.5 text-accent" />
              <div>
                <p className="text-body font-medium text-text-primary">
                  Top up to unlock Desktop Studio
                </p>
                <p className="text-meta text-text-secondary">
                  Your account can sign in, but generation needs a positive credit balance.
                </p>
              </div>
            </div>
            <Button variant="primary" loading={busy} onClick={() => void refreshAccess()}>
              I&apos;ve paid — check access
            </Button>
          </div>
          {message ? <p className="mt-2 text-meta text-text-secondary">{message}</p> : null}
        </div>
        <PlanPage />
      </main>
      <ToastViewport />
    </div>
  );
}
