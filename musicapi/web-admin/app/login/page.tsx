"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { setSession } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

interface LoginBody {
  user?: { id: string; email: string; role: "user" | "admin"; name?: string | null };
  error?: string;
  totp_required?: boolean;
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [totpRequired, setTotpRequired] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      // Raw fetch (not apiFetch) so the 2FA challenge in the body is visible.
      const res = await fetch("/backend/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(totpRequired ? { email, password, code } : { email, password }),
      });
      const body = (await res.json().catch(() => ({}))) as LoginBody;
      if (!res.ok) {
        if (body.totp_required) {
          setTotpRequired(true);
          setError("");
          return;
        }
        setError(body.error ?? `Login failed (${res.status})`);
        return;
      }
      if (!body.user) {
        setError("Login failed.");
        return;
      }
      if (body.user.role !== "admin") {
        setError("This area is for administrators only.");
        return;
      }
      // The API also sets an httpOnly session cookie; we only cache the profile.
      setSession(body.user);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={onSubmit} className="glass w-full max-w-sm space-y-5 rounded-2xl p-8">
        <div className="text-center">
          <Image
            src="/camxora-logo.svg"
            alt="Camxora"
            width={44}
            height={44}
            unoptimized
            className="mx-auto mb-4 h-11 w-11 rounded-xl"
          />
          <h1 className="text-2xl font-bold">Admin sign in</h1>
          <p className="text-sm text-[var(--muted)]">Camxora Music API admin console</p>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300"
          >
            {error}
          </div>
        )}

        <Field label="Admin email" htmlFor="login-email">
          <Input
            id="login-email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@example.com"
            autoComplete="email"
            disabled={totpRequired}
            required
          />
        </Field>

        <Field label="Password" htmlFor="login-password">
          <Input
            id="login-password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password"
            autoComplete="current-password"
            disabled={totpRequired}
            required
          />
        </Field>

        {totpRequired && (
          <Field
            label="Two-factor code"
            htmlFor="login-code"
            hint="Enter the 6-digit code from your authenticator app."
          >
            <Input
              id="login-code"
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              autoFocus
              required
            />
          </Field>
        )}

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? (totpRequired ? "Verifying…" : "Signing in…") : totpRequired ? "Verify" : "Sign in"}
        </Button>

        {totpRequired && (
          <button
            type="button"
            onClick={() => {
              setTotpRequired(false);
              setCode("");
              setError("");
            }}
            className="block w-full text-center text-xs text-[var(--muted)] hover:text-white hover:underline"
          >
            Back
          </button>
        )}

        <p className="text-center text-xs text-[var(--muted)]">
          Administrators only. Contact an operator for credentials.
        </p>
      </form>
    </div>
  );
}
