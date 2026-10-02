"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { setSession } from "@/lib/auth";
import GoogleSignInButton from "@/components/google-signin-button";

interface LoginResponse {
  token: string;
  user: { id: string; email: string; role: "user" | "admin"; name?: string | null };
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (res.user.role !== "admin") {
        setError("This area is for administrators only.");
        return;
      }
      // The API also sets an httpOnly session cookie; we only cache the profile.
      setSession(res.user);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={onSubmit} className="glass w-full max-w-sm rounded-2xl p-8 space-y-5">
        <div className="text-center">
          <div className="grad-bg mx-auto mb-4 h-11 w-11 rounded-xl" />
          <h1 className="text-2xl font-bold">Admin sign in</h1>
          <p className="text-sm text-[var(--muted)]">Camxora Music API admin console</p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <div className="space-y-1">
          <label className="text-xs text-[var(--muted)]">Admin email</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
            placeholder="admin@example.com"
            autoComplete="email"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-[var(--muted)]">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </div>

        <button
          disabled={loading}
          className="grad-bg w-full rounded-lg py-2.5 text-sm font-semibold text-white disabled:opacity-60"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>

        <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
          <span className="h-px flex-1 bg-[var(--border)]" />
          or
          <span className="h-px flex-1 bg-[var(--border)]" />
        </div>

        <GoogleSignInButton label="Continue with Google" redirectTo="/admin" />

        <p className="text-center text-xs text-[var(--muted)]">
          Administrators only. Contact an operator for credentials.
        </p>
      </form>
    </div>
  );
}
