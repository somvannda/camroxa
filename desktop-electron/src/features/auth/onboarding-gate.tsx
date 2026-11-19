import { useState } from "react";
import { ListChecks } from "lucide-react";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { useSessionStore } from "../../store/session";
import { AuthFrame } from "./auth-frame";
import { openExternal } from "./portal";
import { useAuthActions } from "./use-auth-actions";

export function OnboardingGate({ portalUrl }: { portalUrl: string }) {
  const continueToApp = useSessionStore((state) => state.continueToApp);
  const { refresh, signOut } = useAuthActions();
  const [busy, setBusy] = useState<"portal" | "refresh" | "signout" | null>(null);
  const [error, setError] = useState("");

  async function openOnboarding() {
    setError("");
    setBusy("portal");
    const failure = await openExternal(`${portalUrl.replace(/\/+$/, "")}/onboarding`);
    if (failure) setError(failure);
    setBusy(null);
  }

  async function refreshGate() {
    setError("");
    setBusy("refresh");
    const failure = await refresh();
    if (failure) setError(failure);
    setBusy(null);
  }

  async function backToSignIn() {
    setError("");
    setBusy("signout");
    await signOut();
    setBusy(null);
  }

  return (
    <AuthFrame footer="Onboarding">
      <div className="mb-6 text-center">
        <p className="text-caption text-text-muted">ACCOUNT SETUP</p>
        <h1 className="mt-1 text-page font-semibold text-text-primary">Complete your setup</h1>
        <p className="mt-1 text-body text-text-secondary">
          Add your first channel profile in the account portal, then return here.
        </p>
      </div>

      <Card className="p-5">
        <div className="space-y-4">
          {error ? (
            <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-body text-danger" role="alert">
              {error}
            </div>
          ) : null}

          <div className="flex items-start gap-3 rounded-control border border-border bg-surface-1 px-3 py-3">
            <ListChecks size={16} className="mt-0.5 shrink-0 text-text-secondary" aria-hidden />
            <p className="text-body text-text-secondary">
              Your studio needs a channel profile before generation can start. Set it up in your browser, then refresh.
            </p>
          </div>

          <Button type="button" variant="primary" className="h-9 w-full" loading={busy === "portal"} disabled={busy !== null} onClick={openOnboarding}>
            Complete setup in your browser
          </Button>

          <Button type="button" variant="secondary" className="h-9 w-full" loading={busy === "refresh"} disabled={busy !== null} onClick={refreshGate}>
            I completed setup — refresh
          </Button>

          <Button type="button" variant="secondary" className="h-9 w-full" disabled={busy !== null} onClick={continueToApp}>
            Open studio anyway
          </Button>

          <Button type="button" variant="ghost" className="h-8 w-full" loading={busy === "signout"} disabled={busy !== null} onClick={backToSignIn}>
            Back to sign in
          </Button>
        </div>
      </Card>
    </AuthFrame>
  );
}
