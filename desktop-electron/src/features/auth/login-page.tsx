import { useState, type FormEvent } from "react";
import { Eye, EyeOff, LogIn } from "lucide-react";
import type { ApiError } from "../../../electron/shared/types";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Input } from "../../components/input";
import { useSessionStore } from "../../store/session";
import { AuthFrame } from "./auth-frame";
import { openExternal } from "./portal";
import { useAuthActions } from "./use-auth-actions";

function friendlyAuthError(error: ApiError): string {
  switch (error.code) {
    case "AUTHENTICATION_ERROR":
      return "Wrong email or password. Try again.";
    case "ACCOUNT_LOCKED":
      return error.message;
    case "NETWORK_ERROR":
      return "Cannot reach Camxora. Check your connection.";
    default:
      return error.message || "Unable to sign in right now. Try again.";
  }
}

function friendlyGoogleError(error: ApiError): string {
  switch (error.code) {
    case "OAUTH_PORT_BUSY":
    case "OAUTH_TIMEOUT":
    case "OAUTH_ERROR":
    case "OAUTH_IN_PROGRESS":
      return error.message;
    case "NETWORK_ERROR":
      return "Cannot reach Camxora. Check your connection.";
    default:
      return error.message || "Google sign-in could not be completed. Try again.";
  }
}

export function LoginPage({ portalUrl }: { portalUrl: string }) {
  const applyBootstrap = useSessionStore((state) => state.applyBootstrap);
  const notice = useSessionStore((state) => state.notice);
  const setNotice = useSessionStore((state) => state.setNotice);
  const { signOut } = useAuthActions();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [googleWaiting, setGoogleWaiting] = useState(false);
  const [paidGate, setPaidGate] = useState<{ message: string; portalUrl: string } | null>(null);
  const [openingPortal, setOpeningPortal] = useState(false);

  const noticePaid =
    notice?.code === "DESKTOP_PLAN_REQUIRED"
      ? { message: notice.message ?? "Desktop studio requires a paid plan.", portalUrl: notice.portalUrl ?? portalUrl }
      : null;
  const gate = paidGate ?? noticePaid;

  async function openAccountPortal(url: string) {
    setError("");
    setOpeningPortal(true);
    const failure = await openExternal(url);
    if (failure) setError(failure);
    setOpeningPortal(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || googleWaiting) return;
    setError("");
    setNotice(null);

    const trimmed = email.trim();
    if (!trimmed || !password) {
      setError("Enter your email and password.");
      return;
    }
    if (!window.camxora) {
      setError("Sign-in is only available in the desktop application.");
      return;
    }

    setBusy(true);
    try {
      const result = await window.camxora.auth.login(trimmed, password, remember);
      if (!result.ok) {
        if (result.error.code === "DESKTOP_PLAN_REQUIRED") {
          setPaidGate({
            message: result.error.message,
            portalUrl,
          });
          return;
        }
        setError(friendlyAuthError(result.error));
        return;
      }
      setPassword("");
      applyBootstrap(result.data);
    } catch {
      setError("Unable to sign in right now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function startGoogle() {
    if (busy || googleWaiting) return;
    if (!window.camxora) {
      setError("Sign-in is only available in the desktop application.");
      return;
    }
    setError("");
    setGoogleWaiting(true);
    try {
      const result = await window.camxora.auth.google(remember);
      if (!result.ok) {
        if (result.error.code === "DESKTOP_PLAN_REQUIRED") {
          setPaidGate({ message: result.error.message, portalUrl });
          return;
        }
        if (result.error.code !== "OAUTH_CANCELLED") {
          setError(friendlyGoogleError(result.error));
        }
        return;
      }
      applyBootstrap(result.data);
    } catch {
      setError("Google sign-in could not be completed. Try again.");
    } finally {
      setGoogleWaiting(false);
    }
  }

  async function cancelGoogle() {
    try {
      await window.camxora?.auth.cancelGoogle();
    } catch {
      // The pending sign-in attempt reports the cancellation.
    }
  }

  function dismissGate() {
    setPaidGate(null);
    setNotice(null);
    setPassword("");
  }

  if (gate) {
    return (
      <AuthFrame footer="Plan required">
        <Card className="p-5">
          <div className="space-y-4">
            <div>
              <p className="text-caption text-text-muted">DESKTOP STUDIO</p>
              <h1 className="mt-1 text-title font-semibold text-text-primary">A paid plan is required</h1>
            </div>

            {error ? (
              <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-body text-danger" role="alert">
                {error}
              </div>
            ) : null}

            <p className="text-body text-text-secondary">{gate.message}</p>

            <Button
              type="button"
              variant="primary"
              className="h-9 w-full"
              loading={openingPortal}
              disabled={openingPortal}
              onClick={() => void openAccountPortal(gate.portalUrl)}
            >
              Open account portal
            </Button>

            <Button type="button" variant="secondary" className="h-9 w-full" disabled={openingPortal} onClick={dismissGate}>
              Use a different account
            </Button>

            <Button type="button" variant="ghost" className="h-8 w-full" disabled={openingPortal} onClick={() => void signOut()}>
              Sign out
            </Button>
          </div>
        </Card>
      </AuthFrame>
    );
  }

  const banner = error || notice?.message || "";

  return (
    <AuthFrame footer="Sign in">
      <div className="mb-6 text-center">
        <p className="text-caption text-text-muted">FACELESS DESKTOP STUDIO</p>
        <h1 className="mt-1 text-page font-semibold text-text-primary">Welcome back</h1>
        <p className="mt-1 text-body text-text-secondary">Sign in to continue to your studio</p>
      </div>

      <Card className="p-5">
        <form className="space-y-4" onSubmit={submit}>
          {banner ? (
            <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-body text-danger" role="alert">
              {banner}
            </div>
          ) : null}

          <div>
            <label className="mb-1.5 block text-meta text-text-secondary" htmlFor="email">
              Email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              autoFocus
              placeholder="you@example.com"
              value={email}
              disabled={busy || googleWaiting}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>

          <div>
            <label className="mb-1.5 block text-meta text-text-secondary" htmlFor="password">
              Password
            </label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Enter your password"
                className="pr-10"
                value={password}
                disabled={busy || googleWaiting}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                className="absolute right-1 top-1 flex h-6 w-7 items-center justify-center rounded-[5px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-meta text-text-secondary">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border bg-surface-1 accent-[var(--accent)]"
                checked={remember}
                disabled={busy || googleWaiting}
                onChange={(event) => setRemember(event.target.checked)}
              />
              Remember me
            </label>
            <button
              type="button"
              className="text-meta text-text-secondary underline-offset-2 hover:text-text-primary hover:underline"
              disabled={busy || googleWaiting}
              onClick={() => void openAccountPortal(portalUrl)}
            >
              Forgot password?
            </button>
          </div>

          <Button type="submit" variant="primary" className="h-9 w-full" loading={busy} disabled={busy || googleWaiting}>
            <LogIn size={15} />
            Sign in
          </Button>

          {googleWaiting ? (
            <div className="flex items-center justify-between gap-3 rounded-control border border-border bg-surface-1 px-3 py-2">
              <span className="flex items-center gap-2 text-body text-text-secondary">
                <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                Waiting for browser…
              </span>
              <Button type="button" variant="ghost" className="h-7 px-2" onClick={() => void cancelGoogle()}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button type="button" variant="secondary" className="h-9 w-full" disabled={busy} onClick={() => void startGoogle()}>
              Continue with Google
            </Button>
          )}

          <p className="text-center text-caption text-text-muted">
            Accounts, plans and channel setup are managed in your Camxora account portal.
          </p>
        </form>
      </Card>
    </AuthFrame>
  );
}
