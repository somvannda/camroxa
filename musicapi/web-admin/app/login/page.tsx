"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { setSession } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

interface LoginResponse {
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
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />
        </Field>

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? "Signing in…" : "Sign in"}
        </Button>

        <p className="text-center text-xs text-[var(--muted)]">
          Administrators only. Contact an operator for credentials.
        </p>
      </form>
    </div>
  );
}
