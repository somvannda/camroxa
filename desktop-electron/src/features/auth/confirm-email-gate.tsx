import { useState } from "react";
import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { useSessionStore } from "../../store/session";
import { AuthFrame } from "./auth-frame";
import { openExternal } from "./portal";
import { useAuthActions } from "./use-auth-actions";

export function ConfirmEmailGate({ portalUrl }: { portalUrl: string }) {
  const email = useSessionStore((state) => state.session?.email);
  const { refresh, signOut } = useAuthActions();
  const [busy, setBusy] = useState<"portal" | "refresh" | "signout" | null>(null);
  const [error, setError] = useState("");

  async function openPortal() {
    setError("");
    setBusy("portal");
    const failure = await openExternal(portalUrl);
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
    <AuthFrame footer="Confirm email" variant="solo">
      <div className="mb-6 text-center">
        <p className="text-caption text-text-muted">ACCOUNT SETUP</p>
        <h1 className="mt-1 text-page font-semibold text-text-primary">Confirm your email</h1>
        <p className="mt-1 text-body text-text-secondary">
          {email ? `Confirm ${email} to continue to your studio.` : "Confirm your email to continue to your studio."}
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
            <Icon name="fa-envelope-circle-check" size={16} className="mt-0.5 shrink-0 text-text-secondary" />
            <p className="text-body text-text-secondary">
              Open your Camxora account portal to confirm your email address. Return here and refresh once it is done.
            </p>
          </div>

          <Button type="button" variant="primary" className="h-9 w-full" loading={busy === "portal"} disabled={busy !== null} onClick={openPortal}>
            Open account portal
          </Button>

          <Button type="button" variant="secondary" className="h-9 w-full" loading={busy === "refresh"} disabled={busy !== null} onClick={refreshGate}>
            I confirmed my email — refresh
          </Button>

          <Button type="button" variant="ghost" className="h-8 w-full" loading={busy === "signout"} disabled={busy !== null} onClick={backToSignIn}>
            Back to sign in
          </Button>
        </div>
      </Card>
    </AuthFrame>
  );
}
