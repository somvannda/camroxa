import { useState, type FormEvent } from "react";
import { LogIn } from "lucide-react";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Input } from "../../components/input";
import { useSessionStore } from "../../store/session";

export function LoginPage() {
  const setSession = useSessionStore((state) => state.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    if (!window.camxora) {
      setError("Sign-in is only available in the desktop application.");
      return;
    }

    setBusy(true);
    try {
      const result = await window.camxora.auth.login(email.trim(), password, remember);
      if (!result.ok) {
        setError(result.error.message);
        return;
      }
      setSession(result.data);
    } catch {
      setError("Unable to sign in right now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="drag-region flex h-12 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-6 w-6 items-center justify-center rounded-[6px] bg-accent text-[11px] font-semibold text-accent-ink">
            C
          </div>
          <span className="text-meta font-semibold tracking-[0.12em] text-text-primary">CAMXORA</span>
          <span className="text-caption text-text-muted">Desktop 2.0</span>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-[400px]">
          <div className="mb-6 text-center">
            <p className="text-caption text-text-muted">FACELESS DESKTOP STUDIO</p>
            <h1 className="mt-1 text-page font-semibold text-text-primary">Welcome back</h1>
            <p className="mt-1 text-body text-text-secondary">Sign in to continue to your studio</p>
          </div>

          <Card className="p-5">
            <form className="space-y-4" onSubmit={submit}>
              {error ? (
                <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-body text-danger" role="alert">
                  {error}
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
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>

              <div>
                <label className="mb-1.5 block text-meta text-text-secondary" htmlFor="password">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>

              <label className="flex cursor-pointer items-center gap-2 text-meta text-text-secondary">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border bg-surface-1 accent-[var(--accent)]"
                  checked={remember}
                  onChange={(event) => setRemember(event.target.checked)}
                />
                Remember me on this computer
              </label>

              <Button type="submit" variant="primary" className="h-9 w-full" loading={busy}>
                <LogIn size={15} />
                Sign in
              </Button>

              <p className="text-center text-caption text-text-muted">
                Accounts, plans and channel setup are managed in your Camxora account portal.
              </p>
            </form>
          </Card>
        </div>
      </div>

      <div className="flex h-8 items-center justify-between border-t border-border px-4 text-caption text-text-muted">
        <span>Camxora Desktop 2.0.0</span>
        <span className="font-mono">Sign in</span>
      </div>
    </div>
  );
}
